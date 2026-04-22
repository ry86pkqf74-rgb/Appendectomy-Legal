#!/usr/bin/env python3
"""
split_rtf.py
============

Reads a directory of Westlaw RTF exports, converts each to plain text, and
splits them into per-case segments that align with the Search_ID scheme used
by AppendectomyMaster.xlsx.

Search_ID format: <file_stub>_<segment_index>
    e.g. westlaw_100_full_text_items_for_appendectomy_0004
    → file_stub = "westlaw_100_full_text_items_for_appendectomy"
    → segment_index = 4 (0-based, the 5th case in that RTF)

Westlaw "Full Text" RTF exports delimit successive cases with either
"End of Document" markers or Westlaw's thumb-index preamble. This script
tries the most common patterns in order and falls back to form feeds.

IMPORTANT — Re-using the ORIGINAL pipeline's segmenter is safer
---------------------------------------------------------------
If you still have access to appendectomy_extractor.py from the original
extraction run, USE ITS SEGMENTER instead of this one. The guarantee we
need is that segment N of file X in this run == segment N of file X in
the original run. Any drift in boundaries breaks the Search_ID mapping.

This script tries to reproduce the canonical Westlaw splitting behavior,
but verify alignment by spot-checking a few known Search_IDs (e.g. the
Case_Name you already have in the xlsx should match the first ~200 chars
of the corresponding segment file).

Usage
-----
    python scripts/split_rtf.py \\
        --input-dir /data/westlaw_rtfs \\
        --output-dir /data/segments \\
        --manifest manifests/manifest_job_A_firstpass_pass2.csv

If --manifest is supplied, the script ONLY writes segments referenced
in the manifest (efficient for targeted re-runs). Otherwise all segments
in all RTFs are emitted.
"""

import argparse
import csv
import re
import sys
from pathlib import Path

try:
    from striprtf.striprtf import rtf_to_text
except ImportError:
    print("Missing dependency: pip install striprtf", file=sys.stderr)
    sys.exit(1)


# Westlaw "End of Document" markers — Westlaw RTF exports consistently end
# each case with a line that reads "End of Document" followed by
# "© <year> Thomson Reuters ...". We split on that marker.
END_OF_DOC_PATTERNS = [
    r"\bEnd of Document\b",
    r"\f",                   # form feed (secondary fallback)
]


def split_rtf_text(text: str) -> list[str]:
    """Split plain text of a Westlaw RTF into individual case segments.

    Strategy: try primary delimiter ("End of Document"); if too few hits,
    fall back to form-feed. Returns a list of non-empty stripped segments.
    """
    primary_re = re.compile(END_OF_DOC_PATTERNS[0], flags=re.IGNORECASE)
    parts = primary_re.split(text)
    # The split leaves trailing copyright blurbs; trim them.
    segs = [s.strip() for s in parts if s.strip()]

    if len(segs) >= 2:
        return segs

    # Fallback: form-feed
    parts = re.split(END_OF_DOC_PATTERNS[1], text)
    return [s.strip() for s in parts if s.strip()]


def file_stub_from_path(p: Path) -> str:
    """Derive the file_stub used in Search_IDs from an RTF filename.

    Search_IDs look like:
        westlaw_100_full_text_items_for_appendectomy_0004
        westlaw_100_full_text_items_for_appendectomy1_0050
        westlaw_100_full_text_items_for_appendectomy10_0055

    The corresponding filenames are:
        Westlaw - 100 full text items for appendectomy.rtf
        Westlaw - 100 full text items for appendectomy1.rtf
        Westlaw - 100 full text items for appendectomy10.rtf
    """
    name = p.stem                                     # "Westlaw - 100 full text items for appendectomy1"
    stub = name.lower()
    stub = re.sub(r"[^a-z0-9]+", "_", stub)           # collapse non-alnum
    stub = re.sub(r"_+", "_", stub).strip("_")
    return stub


def needed_indices(manifest_path: Path) -> dict[str, set[int]] | None:
    """If a manifest is provided, parse it to { file_stub: {segment_indices} }."""
    if not manifest_path:
        return None
    needed: dict[str, set[int]] = {}
    with open(manifest_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sid = row["Search_ID"]
            m = re.match(r"^(.*)_(\d{4})$", sid)
            if not m:
                print(f"WARN: cannot parse Search_ID '{sid}'", file=sys.stderr)
                continue
            stub, idx = m.group(1), int(m.group(2))
            needed.setdefault(stub, set()).add(idx)
    return needed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-dir", required=True, type=Path,
                    help="Directory containing Westlaw *.rtf files")
    ap.add_argument("--output-dir", required=True, type=Path,
                    help="Where per-segment .txt files will be written")
    ap.add_argument("--manifest", type=Path, default=None,
                    help="Optional manifest CSV: only emit segments for listed Search_IDs")
    ap.add_argument("--strict-align", action="store_true",
                    help="Abort if a manifest-requested segment index is not present")
    args = ap.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    needed = needed_indices(args.manifest)

    rtfs = sorted(args.input_dir.glob("*.rtf"))
    if not rtfs:
        print(f"No .rtf files found in {args.input_dir}", file=sys.stderr)
        return 1

    total_written = 0
    total_missing = 0
    for rtf_path in rtfs:
        stub = file_stub_from_path(rtf_path)
        if needed is not None and stub not in needed:
            continue  # no requested segments from this file

        print(f"[+] {rtf_path.name}  → stub={stub}")
        raw = rtf_path.read_text(encoding="utf-8", errors="replace")
        text = rtf_to_text(raw)
        segments = split_rtf_text(text)
        print(f"    split into {len(segments)} segments")

        indices_to_emit = range(len(segments))
        if needed is not None:
            indices_to_emit = sorted(needed[stub])

        for idx in indices_to_emit:
            if idx >= len(segments):
                print(f"    WARN: segment {idx:04d} requested but file only has {len(segments)}",
                      file=sys.stderr)
                total_missing += 1
                if args.strict_align:
                    return 2
                continue
            sid = f"{stub}_{idx:04d}"
            out = args.output_dir / f"{sid}.txt"
            out.write_text(segments[idx], encoding="utf-8")
            total_written += 1

    print(f"\nDone. Wrote {total_written} segments. Missing {total_missing}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
