#!/usr/bin/env python3
"""
merge_results.py
================

Merges JSONL extraction outputs back into a COPY of
AppendectomyMaster.xlsx, producing AppendectomyMaster_updated.xlsx.

Rules
-----
1. Never touch rows not in the job's manifest.
2. Never touch columns not explicitly produced by that job.
3. For Job A cases: set LLM_Status="full", Full_Extraction_Performed="YES".
4. For Job B cases: set LLM_Status="full" (already YES). Mark
   Needs_Manual_Review from new Reviewer_Confidence_Score: <=3 → "YES".
5. For Job C cases: only write into the Extended_Extraction sheet rows
   matching the Search_ID; also set LLM_Status there to "full".
6. If _validation_issues for a row is non-empty, append issues into
   Reviewer_Notes (or Extended_Extraction_Notes) so reviewers see them.
7. Always re-evaluate Core_Analytic_Case from the three gate fields after
   merging A (screening may have changed if the model now says NO to
   Is_Malpractice_Case, etc.).

Usage
-----
    python scripts/merge_results.py \\
        --in AppendectomyMaster.xlsx \\
        --out AppendectomyMaster_updated.xlsx \\
        --jsonl-dir output_jsonl \\
        --jobs A B C
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
ALLOWED = json.loads((ROOT / "config" / "allowed_values.json").read_text())


def _coerce(df: pd.DataFrame, col: str, v):
    """Coerce v to fit df[col]'s dtype. LLMs sometimes emit '$2,500.00'
    or '25%' for numeric columns; strip those and parse. If the column is
    numeric and v can't be parsed, return None rather than crashing."""
    if v is None:
        return None
    if col not in df.columns:
        return v
    dtype = df[col].dtype
    if pd.api.types.is_numeric_dtype(dtype) and isinstance(v, str):
        s = v.strip().replace("$", "").replace(",", "").replace("%", "")
        if s.lower() in ("", "none", "null", "n/a", "na", "unknown", "not reported"):
            return None
        try:
            return float(s)
        except ValueError:
            return None
    return v


def load_parsed(job: str, jsonl_dir: Path) -> dict[str, dict]:
    path = jsonl_dir / f"{job}_parsed.jsonl"
    if not path.exists():
        print(f"WARN: no parsed file for job {job} at {path}", file=sys.stderr)
        return {}
    out = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            out[rec["Search_ID"]] = rec
    return out


def merge_new_domains(df: pd.DataFrame, parsed: dict[str, dict]) -> tuple[pd.DataFrame, int]:
    """Apply Job D results — writes ONLY the 3 new-domain fields. Never touches
    existing clinical/legal fields. Safe to run on cases already fully extracted.

    Also: if the target column doesn't exist in the workbook yet (because this is
    the first time new-domain fields are being merged), add it.
    """
    new_fields = ["Claim_Type",
                  "Plaintiff_Custodial_Status_Detail",
                  "Deliberate_Indifference_Standard_Applied"]
    # Ensure columns exist
    for f in new_fields:
        if f not in df.columns:
            df[f] = pd.NA
    # Ensure notes column is object-typed so we can append string tags
    if "Reviewer_Notes" in df.columns:
        df["Reviewer_Notes"] = df["Reviewer_Notes"].astype(object)

    touched = 0
    for sid, rec in parsed.items():
        mask = df["Search_ID"] == sid
        if not mask.any():
            print(f"  WARN: Search_ID {sid} not in Case_Master_Template", file=sys.stderr)
            continue
        idx = df.index[mask][0]
        for f in new_fields:
            if f in rec and rec[f] is not None:
                df.at[idx, f] = _coerce(df, f, rec[f])

        issues = rec.get("_validation_issues", [])
        if issues:
            note = df.at[idx, "Reviewer_Notes"]
            note = "" if pd.isna(note) else str(note)
            tag = f" [JOB D VALIDATION: {'; '.join(issues)}]"
            df.at[idx, "Reviewer_Notes"] = (note + tag).strip()
        touched += 1
    return df, touched


def merge_case_master(df: pd.DataFrame, parsed: dict[str, dict], job: str) -> tuple[pd.DataFrame, int]:
    """Apply Job A or Job B results to Case_Master_Template dataframe (in place copy)."""
    # Ensure new-domain columns exist so Jobs A/B can populate them too
    for f in ("Claim_Type", "Plaintiff_Custodial_Status_Detail",
              "Deliberate_Indifference_Standard_Applied"):
        if f not in df.columns:
            df[f] = pd.NA
    # Ensure notes/exclusion columns are object-typed so string tags fit
    for f in ("Reviewer_Notes", "Exclusion_Reason"):
        if f in df.columns:
            df[f] = df[f].astype(object)

    fields = set(df.columns)
    touched = 0
    for sid, rec in parsed.items():
        mask = df["Search_ID"] == sid
        if not mask.any():
            print(f"  WARN: Search_ID {sid} not found in Case_Master_Template", file=sys.stderr)
            continue
        idx = df.index[mask][0]
        for k, v in rec.items():
            if k.startswith("_") or k == "Search_ID":
                continue
            if k not in fields:
                continue  # unexpected — ignore silently; run_extraction logs it
            df.at[idx, k] = _coerce(df, k, v)

        # Pipeline bookkeeping
        df.at[idx, "LLM_Status"] = "full"
        df.at[idx, "Full_Extraction_Performed"] = "YES"

        # Needs_Manual_Review derived from new confidence
        rcs = rec.get("Reviewer_Confidence_Score")
        if rcs is not None:
            df.at[idx, "Needs_Manual_Review"] = "YES" if int(rcs) <= 3 else "NO"

        # Validation issues → append to Reviewer_Notes
        issues = rec.get("_validation_issues", [])
        if issues:
            note = df.at[idx, "Reviewer_Notes"]
            note = "" if pd.isna(note) else str(note)
            tag = f" [JOB {job} VALIDATION: {'; '.join(issues)}]"
            df.at[idx, "Reviewer_Notes"] = (note + tag).strip()
        touched += 1

    # Re-evaluate Core_Analytic_Case for any Job A rows
    gate = ["Is_Malpractice_Case",
            "Appendicitis_or_Appendectomy_Index_Episode",
            "Has_Clinically_Meaningful_Appendicitis_or_Appendectomy_Harm"]
    for sid in parsed:
        mask = df["Search_ID"] == sid
        if not mask.any():
            continue
        idx = df.index[mask][0]
        all_yes = all(str(df.at[idx, g]).strip() == "YES" for g in gate)
        df.at[idx, "Core_Analytic_Case"] = "YES" if all_yes else "NO"
        if not all_yes:
            # Record why it fell out
            reasons = [g for g in gate if str(df.at[idx, g]).strip() != "YES"]
            df.at[idx, "Exclusion_Reason"] = "post-rerun gate fail: " + ",".join(reasons)

    return df, touched


def merge_extended(df_ext: pd.DataFrame, parsed: dict[str, dict]) -> tuple[pd.DataFrame, int]:
    fields = set(df_ext.columns)
    # ALL extended-extraction content columns are free-text / JSON strings.
    # The sheet arrives with these as float64 (empty → NaN), which would
    # cause _coerce to nuke the LLM's string values. Cast them up-front.
    extended_string_cols = [
        "Comorbid_Diagnoses_Text", "Operative_Findings_Detail",
        "Plaintiff_Claims_Expanded", "Plaintiff_Medical_Support_Summary",
        "Defense_Medical_Rebuttal_Summary", "Plaintiff_Expert_Summary",
        "Defense_Expert_Summary", "Court_Medical_Reasoning_Summary",
        "Claim_Support_Matrix_JSON", "Evidence_Quotes_JSON",
        "Extended_Extraction_Notes", "LLM_Status",
    ]
    for c in extended_string_cols:
        if c in df_ext.columns:
            df_ext[c] = df_ext[c].astype(object)
    touched = 0
    for sid, rec in parsed.items():
        mask = df_ext["Search_ID"] == sid
        if not mask.any():
            print(f"  WARN: Search_ID {sid} not in Extended_Extraction", file=sys.stderr)
            continue
        idx = df_ext.index[mask][0]
        for k, v in rec.items():
            if k.startswith("_") or k == "Search_ID":
                continue
            if k not in fields:
                continue
            df_ext.at[idx, k] = _coerce(df_ext, k, v)
        df_ext.at[idx, "LLM_Status"] = "full"

        issues = rec.get("_validation_issues", [])
        if issues:
            notes = df_ext.at[idx, "Extended_Extraction_Notes"]
            notes = "" if pd.isna(notes) else str(notes)
            tag = f" [JOB C VALIDATION: {'; '.join(issues)}]"
            df_ext.at[idx, "Extended_Extraction_Notes"] = (notes + tag).strip()
        touched += 1
    return df_ext, touched


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="xlsx_in", required=True, type=Path)
    ap.add_argument("--out", dest="xlsx_out", required=True, type=Path)
    ap.add_argument("--jsonl-dir", type=Path, default=ROOT / "output_jsonl")
    ap.add_argument("--jobs", nargs="+", default=["A", "B", "C", "D"],
                    choices=["A", "B", "C", "D"])
    args = ap.parse_args()

    # Copy first so we never clobber the input on partial failure
    shutil.copy2(args.xlsx_in, args.xlsx_out)

    sheets = pd.read_excel(args.xlsx_out, sheet_name=None)
    cm = sheets["Case_Master_Template"]
    ext = sheets["Extended_Extraction"]

    total_cm_updates = 0
    for job in [j for j in args.jobs if j in ("A", "B")]:
        parsed = load_parsed(job, args.jsonl_dir)
        print(f"Job {job}: merging {len(parsed)} cases into Case_Master_Template …")
        cm, n = merge_case_master(cm, parsed, job)
        total_cm_updates += n
        print(f"  updated {n} rows")

    if "C" in args.jobs:
        parsed = load_parsed("C", args.jsonl_dir)
        print(f"Job C: merging {len(parsed)} cases into Extended_Extraction …")
        ext, n = merge_extended(ext, parsed)
        print(f"  updated {n} rows")

    if "D" in args.jobs:
        parsed = load_parsed("D", args.jsonl_dir)
        print(f"Job D: merging {len(parsed)} cases (new-domain fields only) "
              f"into Case_Master_Template …")
        cm, n = merge_new_domains(cm, parsed)
        print(f"  updated {n} rows")

    sheets["Case_Master_Template"] = cm
    sheets["Extended_Extraction"] = ext
    with pd.ExcelWriter(args.xlsx_out, engine="openpyxl") as xw:
        for name, df in sheets.items():
            df.to_excel(xw, sheet_name=name, index=False)

    print(f"\n✓ Wrote {args.xlsx_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
