#!/usr/bin/env python3
"""
validate_output.py
==================

Post-merge sanity checks. Produces a human-readable diff report
comparing AppendectomyMaster.xlsx (before) and
AppendectomyMaster_updated.xlsx (after).

Flags:
  - Cases where Job A/B was supposed to fill metadata but didn't
  - Cases where Core_Analytic_Case flipped YES → NO after re-run
  - Unknown-rate deltas per major column
  - Cases with validation issues appended to Reviewer_Notes
  - Extended_Extraction cells still NaN after Job C

Usage:
    python scripts/validate_output.py \\
        --before AppendectomyMaster.xlsx \\
        --after  AppendectomyMaster_updated.xlsx \\
        --report validation_report.md
"""

import argparse
import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
ALLOWED = json.loads((ROOT / "config" / "allowed_values.json").read_text())


def unknown_rate(series):
    tokens = {"UNKNOWN", "unknown", "unclear", "not assessable", "None mentioned"}
    mask = series.isna() | series.astype(str).isin(tokens) | (series.astype(str).str.strip() == "")
    return mask.mean() * 100


def compare(before_df, after_df, cols, label):
    lines = [f"\n### {label}\n", "| Column | Before %UNK | After %UNK | Δ |", "|---|---:|---:|---:|"]
    for c in cols:
        if c not in before_df.columns or c not in after_df.columns:
            continue
        b = unknown_rate(before_df[c])
        a = unknown_rate(after_df[c])
        lines.append(f"| {c} | {b:.1f} | {a:.1f} | {a-b:+.1f} |")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True, type=Path)
    ap.add_argument("--after", required=True, type=Path)
    ap.add_argument("--report", required=True, type=Path)
    args = ap.parse_args()

    b = pd.read_excel(args.before, sheet_name="Case_Master_Template")
    a = pd.read_excel(args.after, sheet_name="Case_Master_Template")
    be = pd.read_excel(args.before, sheet_name="Extended_Extraction")
    ae = pd.read_excel(args.after, sheet_name="Extended_Extraction")

    b_core = b[b["Core_Analytic_Case"] == "YES"]
    a_core = a[a["Core_Analytic_Case"] == "YES"]

    out = ["# LLM Pass Validation Report\n"]
    out.append(f"**Before:** {args.before.name}")
    out.append(f"**After:** {args.after.name}\n")
    out.append(f"- Core_Analytic_Case == YES: {len(b_core)} → {len(a_core)}")
    # flips
    gained = set(a_core["Search_ID"]) - set(b_core["Search_ID"])
    lost = set(b_core["Search_ID"]) - set(a_core["Search_ID"])
    if lost:
        out.append(f"- ⚠ {len(lost)} cases dropped from Core after re-extraction: {sorted(lost)[:5]} ...")
    if gained:
        out.append(f"- {len(gained)} cases newly admitted to Core (unexpected — investigate)")

    # Extraction status progression
    out.append("\n## Pipeline status (Core cases only)\n")
    out.append(f"- Full extraction:    {int((b_core['Full_Extraction_Performed']=='YES').sum())} → "
               f"{int((a_core['Full_Extraction_Performed']=='YES').sum())}")
    out.append(f"- first_pass_only:    {int((b_core['Full_Extraction_Performed']=='NO').sum())} → "
               f"{int((a_core['Full_Extraction_Performed']=='NO').sum())}")

    # Confidence distribution
    out.append("\n## Reviewer_Confidence_Score distribution (Core cases)\n")
    bcs = pd.to_numeric(b_core["Reviewer_Confidence_Score"], errors="coerce").value_counts().sort_index()
    acs = pd.to_numeric(a_core["Reviewer_Confidence_Score"], errors="coerce").value_counts().sort_index()
    out.append("| score | before | after |")
    out.append("|---:|---:|---:|")
    for k in sorted(set(bcs.index) | set(acs.index)):
        out.append(f"| {int(k)} | {int(bcs.get(k, 0))} | {int(acs.get(k, 0))} |")

    # UNKNOWN rate deltas on key clinical fields (core cases only)
    key_cols = [
        "Legal_Outcome", "Procedure_Approach", "Disease_State_at_Presentation",
        "Injury_Severity", "Perforated_or_Gangrenous_Appendix",
        "Delayed_Diagnosis_Alleged", "Inadequate_Informed_Consent_Alleged",
        "Poor_Communication_Alleged", "Failure_to_Refer_Alleged",
        "Plaintiff_Demographics", "Year", "Court",
    ]
    out.append(compare(b_core, a_core, key_cols, "UNKNOWN-rate deltas (Core cases)"))

    # Extended_Extraction coverage
    b_ext_core = be[be["Search_ID"].isin(b_core["Search_ID"])]
    a_ext_core = ae[ae["Search_ID"].isin(a_core["Search_ID"])]
    ext_cols = ALLOWED["extended_extraction_fields"]
    out.append("\n## Extended_Extraction coverage (Core cases)\n")
    out.append("| Field | Before non-null | After non-null |")
    out.append("|---|---:|---:|")
    for c in ext_cols:
        bn = int(b_ext_core[c].notna().sum()) if c in b_ext_core.columns else 0
        an = int(a_ext_core[c].notna().sum()) if c in a_ext_core.columns else 0
        out.append(f"| {c} | {bn} | {an} |")

    # Validation tags
    tagged = a_core[a_core["Reviewer_Notes"].astype(str).str.contains("JOB .* VALIDATION", na=False)]
    out.append(f"\n## Validation issues flagged in Reviewer_Notes\n")
    out.append(f"- Rows with validation tags: **{len(tagged)}**")
    if len(tagged):
        out.append("\nFirst 10 issue rows:\n")
        for _, r in tagged.head(10).iterrows():
            out.append(f"- `{r['Search_ID']}`: {r['Reviewer_Notes']}")

    # Year artifacts check
    y2026 = a_core[a_core["Year"] == 2026]
    out.append(f"\n## Year = 2026 artifacts remaining\n- {len(y2026)} (was 7 before)")
    if len(y2026):
        for _, r in y2026.iterrows():
            out.append(f"- {r['Search_ID']} — {r['Case_Name']} — citation: {r['Citation']}")

    args.report.write_text("\n".join(out), encoding="utf-8")
    print(f"✓ Wrote {args.report}")
    # Print summary to stdout
    print("\n".join(out[:30]))


if __name__ == "__main__":
    raise SystemExit(main())
