"""
build_tidy.py  —  Canonical tidy-dataset builder for the Appendectomy medicolegal corpus.

Input
    AppendectomyMaster_updated.xlsx   (post-RUNPROD master workbook)
        sheet "Case_Master_Template"

Output
    appendectomy_core_analytic_tidy.csv
        82 core rows (Core_Analytic_Case == "YES") × all raw + derived columns

Derived-column rules (locked, per handoff prompt — DO NOT silently re-litigate)
--------------------------------------------------------------------------------
Synthesises the best of three prior reviews (DA, Pro, Claude). Rules:

 (1) `inmate_case` scans Case_Name, Facility_Type, First_Pass_Rationale,
     Defense_Strategy_Summary, Plaintiff_Demographics  [DA rule — broader]

 (2) `breach_*` columns: an `Alleged_Breach_Categories` list containing
     named breaches WITHOUT a given breach-term is affirmative NO evidence
     for that breach (not UNKNOWN).  [DA rule]

 (3) `adaptation_performed`: `Adaptation_Type == "none"` → NO.  [DA rule]

 (4) `difficult_case_composite`: difficulty signal set includes
     Abscess_or_Phlegmon and Bowel_Resection_or_Ileocecectomy in addition
     to the standard markers.  [DA rule — broader]

 (5) `plaintiff_favorable`: fallback to `Appellate_Status` when
     `Legal_Outcome` is Unknown/Mixed.  [DA rule]

 (6) `high_severity_injury`: `Need_for_Reoperation == YES` is an
     escalator alongside major severity, Death, Long_Term_Morbidity,
     Need_for_Bowel_Resection, Need_for_Stoma.  [Claude rule — preserved]

 (7) `resolution_involved_payment`: decoupled from `plaintiff_favorable`.
     A Settlement counts as plaintiff-favorable AND as payment; a directed
     verdict for plaintiff counts as plaintiff-favorable but not
     necessarily payment.  [Claude rule — preserved]

Age-group variants:
     `plaintiff_age_group`          — permissive: numeric age OR role
                                       keywords ("prisoner", "seaman",
                                       "Marine", "veteran", etc.) map
                                       to "adult" when no peds/elderly
                                       signal present.
     `plaintiff_age_group_strict`   — numeric age only; everything else
                                       is UNKNOWN unless an explicit
                                       "adult"/"pediatric"/"elderly"
                                       word appears in demographic text.

Read_Me rule (non-negotiable): if the source does not clearly support a
value, the output is UNKNOWN (categorical/boolean) or blank (text/numeric).
We never impute, force, or guess.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def clean_str(x):
    if pd.isna(x):
        return None
    s = str(x).strip()
    if s == "" or s.lower() == "nan":
        return None
    return s


def parse_money(val):
    if pd.isna(val):
        return np.nan
    if isinstance(val, (int, float, np.integer, np.floating)):
        return float(val)
    s = str(val).strip()
    if s == "" or s.lower() == "nan":
        return np.nan
    if re.fullmatch(r"[-+]?\$?\s*[\d,]+(?:\.\d+)?", s):
        s = s.replace("$", "").replace(",", "").replace(" ", "")
        try:
            return float(s)
        except Exception:
            return np.nan
    return np.nan


def split_multi(val):
    if pd.isna(val):
        return []
    s = str(val).strip()
    if s == "" or s.lower() == "nan":
        return []
    return [t.strip().lower() for t in re.split(r"\s*,\s*", s) if t.strip()]


def has_any_token(tokens, patterns):
    for tok in tokens:
        for pat in patterns:
            if pat.search(tok):
                return True
    return False


# ---------------------------------------------------------------------------
# Breach-allegation patterns
# ---------------------------------------------------------------------------

delay_patterns = [
    re.compile(r"delayed diagnosis"),
    re.compile(r"failure to diagnose"),
    re.compile(r"\bmisdiagnosis\b"),
    re.compile(r"failure to order imaging"),
    re.compile(r"failure to obtain patient history"),
]
postop_patterns = [
    re.compile(r"postop|post-operative|postoperative"),
    re.compile(r"failure to provide postoperative antibiotics"),
    re.compile(r"delayed antibiotic administration"),
    re.compile(r"failure to remove surgical drain"),
    re.compile(r"delayed discovery of foreign object"),
    re.compile(r"failure to administer appropriate antibiotics"),
    re.compile(r"failure to prescribe antibiotics"),
]
refer_patterns = [
    re.compile(r"failure to refer"),
    re.compile(r"failure to transfer"),
    re.compile(r"timely surgical evaluation"),
]
consent_patterns = [re.compile(r"informed consent|consent")]
comm_patterns = [
    re.compile(r"communication"),
    re.compile(r"notification"),
    re.compile(r"misreporting"),
]
failure_remove_patterns = [
    re.compile(r"failure to remove appendix"),
    re.compile(r"failed appendectomy"),
    re.compile(r"failure to remove entire appendix"),
    re.compile(r"failure to identify appendix"),
    re.compile(r"removal of wrong tissue"),
]
surg_patterns = [
    re.compile(r"negligence in surgical care"),
    re.compile(r"negligent performance of appendectomy"),
    re.compile(r"foreign object"),
    re.compile(r"retained surgical item"),
    re.compile(r"failed appendectomy"),
    re.compile(r"removal of wrong tissue"),
    re.compile(r"failure to identify appendix"),
    re.compile(r"failure to remove surgical drain"),
    re.compile(r"postoperative leak"),
    re.compile(r"untrained intern"),
    re.compile(r"failure to manage airway"),
    re.compile(r"overinduction of anesthesia"),
    re.compile(r"negligence in surgical"),
]


# ---------------------------------------------------------------------------
# Breach derivations (rule 2: list-with-other-items-but-not-this-one → NO)
# ---------------------------------------------------------------------------

def derive_breach_delay(row):
    direct = clean_str(row["Delayed_Diagnosis_Alleged"])
    tokens = split_multi(row["Alleged_Breach_Categories"])
    if direct == "YES" or has_any_token(tokens, delay_patterns):
        return "YES"
    if direct == "NO" or (len(tokens) > 0 and not has_any_token(tokens, delay_patterns)):
        return "NO"
    return "UNKNOWN"


def derive_breach_postop(row):
    direct = clean_str(row["Improper_Postop_Management_Alleged"])
    tokens = split_multi(row["Alleged_Breach_Categories"])
    if direct == "YES" or has_any_token(tokens, postop_patterns):
        return "YES"
    if direct == "NO" or (len(tokens) > 0 and not has_any_token(tokens, postop_patterns)):
        return "NO"
    return "UNKNOWN"


def derive_breach_refer(row):
    direct = clean_str(row["Failure_to_Refer_Alleged"])
    tokens = split_multi(row["Alleged_Breach_Categories"])
    if direct == "YES" or has_any_token(tokens, refer_patterns):
        return "YES"
    if direct == "NO" or (len(tokens) > 0 and not has_any_token(tokens, refer_patterns)):
        return "NO"
    return "UNKNOWN"


def derive_breach_consent(row):
    direct = clean_str(row["Inadequate_Informed_Consent_Alleged"])
    tokens = split_multi(row["Alleged_Breach_Categories"])
    if direct == "YES" or has_any_token(tokens, consent_patterns):
        return "YES"
    if direct == "NO" or (len(tokens) > 0 and not has_any_token(tokens, consent_patterns)):
        return "NO"
    return "UNKNOWN"


def derive_breach_comm(row):
    direct = clean_str(row["Poor_Communication_Alleged"])
    tokens = split_multi(row["Alleged_Breach_Categories"])
    if direct == "YES" or has_any_token(tokens, comm_patterns):
        return "YES"
    if direct == "NO" or (len(tokens) > 0 and not has_any_token(tokens, comm_patterns)):
        return "NO"
    return "UNKNOWN"


def derive_breach_failure_remove(row):
    tokens = split_multi(row["Alleged_Breach_Categories"])
    srcs = [
        clean_str(row["Appendix_Not_Removed"]),
        clean_str(row["Appendix_Not_Removed_or_Wrong_Tissue"]),
        clean_str(row["Wrong_Structure_Removed"]),
    ]
    yes = ("YES" in srcs) or has_any_token(tokens, failure_remove_patterns)
    if yes:
        return "YES"
    has_evidence = any(v is not None for v in srcs) or bool(tokens)
    no_evidence = ("NO" in srcs) or (len(tokens) > 0 and not has_any_token(tokens, failure_remove_patterns))
    if has_evidence and no_evidence:
        return "NO"
    return "UNKNOWN"


def derive_breach_surg(row):
    tokens = split_multi(row["Alleged_Breach_Categories"])
    srcs = {
        "Wrong_Structure_Removed": clean_str(row["Wrong_Structure_Removed"]),
        "Stump_Leak_or_Stump_Problem": clean_str(row["Stump_Leak_or_Stump_Problem"]),
        "Problematic_Visualization_Alleged": clean_str(row["Problematic_Visualization_Alleged"]),
        "NonSpecialist_Repair_or_Management": clean_str(row["NonSpecialist_Repair_or_Management"]),
        "Appendix_Not_Removed_or_Wrong_Tissue": clean_str(row["Appendix_Not_Removed_or_Wrong_Tissue"]),
    }
    yes = any(v == "YES" for v in srcs.values()) or has_any_token(tokens, surg_patterns)
    if yes:
        return "YES"
    has_evidence = bool(tokens) or any(v is not None for v in srcs.values())
    noish = any(v == "NO" for v in srcs.values()) or (len(tokens) > 0 and not has_any_token(tokens, surg_patterns))
    if has_evidence and noish:
        return "NO"
    return "UNKNOWN"


# ---------------------------------------------------------------------------
# Clinical derivations
# ---------------------------------------------------------------------------

def derive_perforated(row):
    state = clean_str(row["Disease_State_at_Presentation"])
    flag = clean_str(row["Perforated_or_Gangrenous_Appendix"])
    if flag == "YES":
        return "YES"
    if state is not None:
        st = state.strip().lower()
        if st in {"perforated appendicitis", "gangrenous-necrotic appendicitis"}:
            return "YES"
        if st in {"uncomplicated appendicitis", "chronic-recurrent appendicitis"}:
            return "NO"
    if flag == "NO":
        return "NO"
    return "UNKNOWN"


# Rule 4: broader difficulty signal set
difficulty_yes_cols = [
    "Abscess_or_Phlegmon",
    "Severe_Inflammation",
    "Dense_Adhesions",
    "Obesity_or_Habitus_Difficulty",
    "Retrocecal_or_Unusual_Appendix_Location",
    "Difficult_Dissection",
    "Bleeding_Obscuring_Field",
    "Conversion_to_Open",
    "Bowel_Resection_or_Ileocecectomy",
    "Stump_Leak_or_Stump_Problem",
]


def derive_difficult(row):
    difficult_case = clean_str(row["Difficult_Case"])
    diff_doc = clean_str(row["Difficulty_Documented"])
    diff_rec = clean_str(row["Difficulty_Recognized_By_Surgeon"])
    assess = clean_str(row["Difficulty_Assessability"])
    markers = [clean_str(row[c]) for c in difficulty_yes_cols]
    if (difficult_case == "YES"
            or diff_doc in {"explicit", "inferred"}
            or diff_rec == "YES"
            or any(v == "YES" for v in markers)):
        return "YES"
    if difficult_case == "NO":
        return "NO"
    if (assess == "clear"
            and diff_doc == "not documented"
            and diff_rec == "NO"
            and all(v in {None, "NO", "UNKNOWN"} for v in markers)):
        return "NO"
    return "UNKNOWN"


# Rule 5: plaintiff_favorable with Appellate_Status fallback
def derive_plaintiff_favorable(row):
    out = clean_str(row["Legal_Outcome"])
    app = clean_str(row["Appellate_Status"])
    if out is not None:
        lo = out.lower()
        if lo == "plaintiff-favorable":
            return "YES"
        if lo == "settlement":
            return "YES"
        if lo == "defense-favorable":
            return "NO"
        # "mixed" / "unknown" → fall through to Appellate_Status
    if app is not None:
        ap = app.lower()
        if "plaintiff win" in ap:
            return "YES"
        if "defense win" in ap:
            return "NO"
    return "UNKNOWN"


# Rule 7: decoupled payment column
def derive_resolution_payment(row):
    """YES when the opinion describes an actual exchange of money —
    settlement, verdict for plaintiff with damages, jury award, consent
    judgment. NO when a defense-favorable disposition forecloses payment.
    UNKNOWN otherwise (including Mixed and many procedural dispositions)."""
    out = clean_str(row["Legal_Outcome"])
    dmg = row.get("Damages_Award")
    stl = row.get("Settlement_Amount")
    app = clean_str(row["Appellate_Status"])
    if pd.notna(dmg) and float(dmg) > 0:
        return "YES"
    if pd.notna(stl) and float(stl) > 0:
        return "YES"
    if out is not None:
        lo = out.lower()
        if lo == "settlement":
            return "YES"
        if lo == "plaintiff-favorable":
            # Plaintiff-favorable without an explicit dollar figure could still
            # be a directed verdict, summary-judgment denial, etc. — payment
            # cannot be confirmed from the opinion alone.
            return "UNKNOWN"
        if lo == "defense-favorable":
            return "NO"
    if app is not None and "defense win" in app.lower():
        return "NO"
    return "UNKNOWN"


# ---------------------------------------------------------------------------
# Demographics
# ---------------------------------------------------------------------------

male_pat = re.compile(r"(?i)\b(male|man|boy)\b")
female_pat = re.compile(r"(?i)\b(female|woman|girl)\b")
peds_pat = re.compile(r"(?i)\b(infant|minor|child|pediatric|paediatric|adolescent|teen|newborn|baby)\b")
elderly_pat = re.compile(r"(?i)\b(elderly|senior|geriatric|world war ii veteran|wwii veteran)\b")
adult_word_pat = re.compile(r"(?i)\badult\b")
adult_role_pat = re.compile(r"(?i)\b(dr\.|doctor|m\.d\.|mother|father|pregnant|marine|seaman|hospitalist|veteran|prisoner|inmate|detainee|state prisoner|federal prisoner|pretrial detainee|active.?duty)\b")
inmate_pat = re.compile(r"(?i)\b(inmate|prisoner|incarcerat\w*|detainee|jail|correctional|prison)\b")
gender_unspecified_pat = re.compile(r"(?i)gender not specified")
age_regex = re.compile(r"(?i)\b(\d{1,3})\s*[- ]?(?:year|yr)s?\s*[- ]?old\b|\b(\d{1,3})\s*years?\s*old\b")


def combined_demo_text(row):
    parts = []
    for c in ("Plaintiff_Demographics", "Case_Name", "First_Pass_Rationale"):
        v = row[c]
        if pd.notna(v):
            parts.append(str(v))
    return " | ".join(parts)


def derive_age_group_permissive(row):
    """Default: uses numeric age if present, else elderly/peds words,
    else the adult role keywords (prisoner, seaman, Marine, veteran, etc.)."""
    txt = combined_demo_text(row)
    m = age_regex.search(txt)
    if m:
        age = int(m.group(1) or m.group(2))
        if age < 18:
            return "pediatric"
        if age >= 65:
            return "elderly"
        return "adult"
    if elderly_pat.search(txt):
        return "elderly"
    if peds_pat.search(txt):
        return "pediatric"
    if adult_word_pat.search(txt) or adult_role_pat.search(txt):
        return "adult"
    return "unknown"


def derive_age_group_strict(row):
    """Strict: numeric age OR an explicit peds/elderly/adult WORD in demo
    text. Role keywords (prisoner, seaman, etc.) alone do NOT map to adult."""
    txt = combined_demo_text(row)
    m = age_regex.search(txt)
    if m:
        age = int(m.group(1) or m.group(2))
        if age < 18:
            return "pediatric"
        if age >= 65:
            return "elderly"
        return "adult"
    if elderly_pat.search(txt):
        return "elderly"
    if peds_pat.search(txt):
        return "pediatric"
    if adult_word_pat.search(txt):
        return "adult"
    return "unknown"


def derive_gender(row):
    txt = combined_demo_text(row)
    if gender_unspecified_pat.search(txt):
        return "unknown"
    has_male = bool(male_pat.search(txt))
    has_female = bool(female_pat.search(txt))
    if has_male and has_female:
        return "unknown"
    if has_male:
        return "Male"
    if has_female:
        return "Female"
    return "unknown"


lap_pat = re.compile(r"(?i)\blaparoscop|\blaproscopic")
open_pat = re.compile(r"(?i)\bopen\b|\blaparotomy\b|\bexploratory laparotomy\b")


# Rule 1: broader inmate scan
def derive_inmate(row):
    scan_cols = ("Plaintiff_Demographics", "Case_Name", "Facility_Type",
                 "Defense_Strategy_Summary", "First_Pass_Rationale")
    txt = " | ".join(str(row[c]) for c in scan_cols if pd.notna(row[c]))
    if inmate_pat.search(txt):
        return "YES"
    if txt.strip():
        return "NO"
    return "UNKNOWN"


def derive_approach(row):
    approach = clean_str(row["Procedure_Approach"])
    conv = clean_str(row["Conversion_to_Open"])
    optext = clean_str(row["Operative_Text_Snippet"])
    if conv == "YES":
        return "conversion"
    if approach is not None:
        a = approach.strip().lower()
        if a in {"converted", "conversion", "converted to open"}:
            return "conversion"
        if a in {"laparoscopic", "robotic"}:
            return "laparoscopic"
        if a == "open":
            return "open"
    if optext is not None:
        if lap_pat.search(optext):
            return "laparoscopic"
        if open_pat.search(optext):
            return "open"
    return "unclear"


# Rule 3: Adaptation_Type == "none" → NO
def derive_adaptation(row):
    perf = clean_str(row["Adaptation_Performed"])
    atype = clean_str(row["Adaptation_Type"])
    if perf == "YES":
        return "YES"
    if atype is not None:
        atl = atype.lower()
        if atl not in {"none", "unknown"}:
            return "YES"
        if atl == "none":
            return "NO"
    if perf == "NO":
        return "NO"
    return "UNKNOWN"


def derive_death_or_ltm(row):
    death = clean_str(row["Death"])
    ltm = clean_str(row["Long_Term_Morbidity"])
    if death == "YES" or ltm == "YES":
        return "YES"
    if death == "NO" and ltm == "NO":
        return "NO"
    return "UNKNOWN"


# Rule 6: Need_for_Reoperation as severity escalator
def derive_high_severity(row):
    sev = clean_str(row["Injury_Severity"])
    death = clean_str(row["Death"])
    ltm = clean_str(row["Long_Term_Morbidity"])
    bowel = clean_str(row["Need_for_Bowel_Resection"])
    stoma = clean_str(row["Need_for_Stoma"])
    reop = clean_str(row["Need_for_Reoperation"])
    if (sev == "major"
            or death == "YES"
            or ltm == "YES"
            or bowel == "YES"
            or stoma == "YES"
            or reop == "YES"):
        return "YES"
    if sev == "minor" and all(v != "YES" for v in (death, ltm, bowel, stoma, reop)):
        return "NO"
    return "UNKNOWN"


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

MONEY_COLS = (
    "Damages_Award",
    "Settlement_Amount",
    "Economic_Damages",
    "NonEconomic_Damages",
    "Punitive_Damages",
    "Damages_Award_Adjusted_2026",
)


def build_tidy_dataframe(xlsx_path: Path) -> pd.DataFrame:
    df = pd.read_excel(xlsx_path, sheet_name="Case_Master_Template")

    # Strip whitespace on all object columns
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].map(lambda x: x.strip() if isinstance(x, str) else x)

    # Coerce money fields
    for col in MONEY_COLS:
        if col in df.columns:
            df[col] = df[col].map(parse_money)

    # Core subset
    core_df = df[df["Core_Analytic_Case"].astype(str).str.upper().eq("YES")].copy()

    # Breach derivations
    core_df["breach_delayed_diagnosis"]           = core_df.apply(derive_breach_delay, axis=1)
    core_df["breach_surgical_technique_error"]    = core_df.apply(derive_breach_surg, axis=1)
    core_df["breach_failure_to_remove_appendix"]  = core_df.apply(derive_breach_failure_remove, axis=1)
    core_df["breach_improper_postop_management"]  = core_df.apply(derive_breach_postop, axis=1)
    core_df["breach_failure_to_refer"]            = core_df.apply(derive_breach_refer, axis=1)
    core_df["breach_inadequate_informed_consent"] = core_df.apply(derive_breach_consent, axis=1)
    core_df["breach_communication_failure"]       = core_df.apply(derive_breach_comm, axis=1)

    # Clinical
    core_df["perforated_or_gangrenous"]    = core_df.apply(derive_perforated, axis=1)
    core_df["difficult_case_composite"]    = core_df.apply(derive_difficult, axis=1)
    core_df["operative_approach"]          = core_df.apply(derive_approach, axis=1)
    core_df["adaptation_performed"]        = core_df.apply(derive_adaptation, axis=1)
    core_df["death_or_long_term_morbidity"] = core_df.apply(derive_death_or_ltm, axis=1)
    core_df["high_severity_injury"]        = core_df.apply(derive_high_severity, axis=1)

    # Outcome
    core_df["plaintiff_favorable"]         = core_df.apply(derive_plaintiff_favorable, axis=1)
    core_df["resolution_involved_payment"] = core_df.apply(derive_resolution_payment, axis=1)

    # Demographics
    core_df["plaintiff_age_group"]         = core_df.apply(derive_age_group_permissive, axis=1)
    core_df["plaintiff_age_group_strict"]  = core_df.apply(derive_age_group_strict, axis=1)
    core_df["plaintiff_gender"]            = core_df.apply(derive_gender, axis=1)
    core_df["inmate_case"]                 = core_df.apply(derive_inmate, axis=1)

    return core_df


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="xlsx_in", type=Path,
                    default=Path("AppendectomyMaster_updated.xlsx"),
                    help="Path to the post-RUNPROD master workbook.")
    ap.add_argument("--out", dest="csv_out", type=Path,
                    default=Path("appendectomy_core_analytic_tidy.csv"),
                    help="Output tidy CSV path.")
    args = ap.parse_args()

    tidy = build_tidy_dataframe(args.xlsx_in)
    tidy.to_csv(args.csv_out, index=False)
    print(f"Wrote {len(tidy)} core analytic rows × {tidy.shape[1]} cols → {args.csv_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
