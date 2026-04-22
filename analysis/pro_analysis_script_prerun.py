
import re, json, zipfile
from pathlib import Path
from collections import Counter
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

INPUT_XLSX = Path("/mnt/data/AppendectomyMaster.xlsx")
OUTPUT_DIR = Path("/mnt/data")

def normalize_text(value) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip().lower()
    text = text.replace("‑","-").replace("–","-").replace("—","-").replace("“",'"').replace("”",'"').replace("’","'").replace("‘","'")
    text = re.sub(r"\s+"," ",text)
    return text

def parse_money(value):
    if pd.isna(value):
        return np.nan
    text = str(value).strip()
    if not text or text.lower() in {"nan","none"}:
        return np.nan
    text = text.replace("$","").replace(",","").replace("(","-").replace(")","").strip()
    try:
        return float(text)
    except Exception:
        return np.nan

def ynu_to_bool(value):
    if pd.isna(value):
        return pd.NA
    text = str(value).strip().upper()
    if text == "YES":
        return True
    if text == "NO":
        return False
    return pd.NA

def normalize_legal_outcome(value):
    if pd.isna(value):
        return pd.NA
    text = str(value).strip()
    return text if text else pd.NA

def normalize_appellate_status(value):
    text = normalize_text(value)
    if not text:
        return pd.NA
    mapping = {
        "original":"original",
        "appeal - plaintiff win":"appeal_plaintiff_win",
        "appeal - defense win":"appeal_defense_win",
        "appeal - remanded":"appeal_remanded",
        "appeal - mixed":"appeal_mixed",
        "unknown":"unknown",
    }
    return mapping.get(text, text.replace(" ","_"))

def split_breaches(value):
    text = normalize_text(value)
    if not text:
        return []
    return [p.strip() for p in text.split(",") if p and p.strip()]

BREACH_PATTERNS = [
    ("delayed_diagnosis",[r"delayed diagnosis", r"failure to diagnose", r"misdiagnosis", r"failure to diagnose/ treat", r"diagnose acute appendicitis"]),
    ("failure_to_order_imaging_or_tests",[r"imaging", r"diagnostic tests", r"hiv testing"]),
    ("inadequate_exam_or_history",[r"properly examine", r"patient history", r"history-taking", r"physical exam", r"failure to obtain patient history"]),
    ("failure_to_refer_or_transfer",[r"failure to refer", r"failure to transfer", r"delayed transfer", r"refer to hospital", r"refer to surgery"]),
    ("failure_to_treat_or_timely_surgery",[r"failure to treat", r"delayed treatment", r"delayed surgery", r"timely appendectomy", r"schedule appendectomy", r"timely surgical", r"promptly treat", r"prompt medical", r"timely medical care", r"admit for surgery", r"operating room promptly", r"timely surgical evaluation", r"timely surgical treatment", r"timely surgical care"]),
    ("improper_postop_management",[r"postoperative", r"post-surgery", r"aftercare", r"follow up", r"follow-up", r"postop", r"pain management", r"failure to provide antibiotics", r"antibiotic administration", r"pain medication", r"perioperative care"]),
    ("surgical_technique_error",[r"failed appendectomy", r"negligent performance of appendectomy", r"negligent appendectomy", r"negligent performance of surgery", r"improper surgical care", r"negligence in surgical care", r"removal of wrong tissue", r"failure to identify appendix", r"allowing untrained intern to perform", r"misreporting of successful surgery", r"foreign object left during appendectomy", r"failure to remove surgical drain"]),
    ("failure_to_remove_appendix",[r"failure to remove appendix", r"failure to remove entire appendix", r"appendix not removed", r"failure to perform appendectomy", r"failed appendectomy"]),
    ("foreign_body_retention",[r"foreign object retention", r"retained surgical item", r"foreign object left", r"remove surgical drain", r"needle fragments", r"delayed discovery of foreign object"]),
    ("anesthesia_or_airway_event",[r"anesthesia", r"airway", r"anoxic", r"prevent anoxia", r"overinduction"]),
    ("deliberate_indifference_or_civil_rights",[r"deliberate indifference", r"willful and malicious", r"gross negligence"]),
    ("equipment_or_system_failure",[r"medical equipment", r"thermometer", r"supervisory liability", r"supervise nursing staff", r"corporate negligence", r"vicarious liability", r"respondeat superior"]),
    ("documentation_or_disclosure_issue",[r"misreporting", r"falsifying medical records", r"disclose cause of injury", r"delayed filing of claim"]),
]

def map_breach_categories(value):
    tokens = split_breaches(value)
    if not tokens:
        return []
    joined = " | ".join(tokens)
    out = []
    for category, patterns in BREACH_PATTERNS:
        if any(re.search(p, joined) for p in patterns):
            out.append(category)
    return sorted(set(out))

def derive_perforated_or_gangrenous(row):
    raw = normalize_text(row.get("Perforated_or_Gangrenous_Appendix"))
    disease = normalize_text(row.get("Disease_State_at_Presentation"))
    if raw == "yes":
        return True
    if raw == "no":
        return False
    if "perforated" in disease or "gangrenous" in disease or "necrotic" in disease:
        return True
    if "uncomplicated" in disease:
        return False
    return pd.NA

def derive_difficult_case(row):
    difficult = normalize_text(row.get("Difficult_Case"))
    documented = normalize_text(row.get("Difficulty_Documented"))
    if difficult == "yes":
        return True
    if difficult == "no":
        return False
    if documented in {"explicit","inferred"}:
        return True
    return pd.NA

def derive_difficulty_assessable(row):
    assess = normalize_text(row.get("Difficulty_Assessability"))
    if assess in {"clear","possible"}:
        return True
    if assess == "not assessable":
        return False
    return pd.NA

def derive_bowel_resection(row):
    vals = [normalize_text(row.get("Need_for_Bowel_Resection")), normalize_text(row.get("Bowel_Resection_or_Ileocecectomy"))]
    if "yes" in vals:
        return True
    known = [v for v in vals if v in {"yes","no"}]
    if known and all(v=="no" for v in known):
        return False
    return pd.NA

def derive_procedure_approach(row):
    approach = normalize_text(row.get("Procedure_Approach"))
    conversion = normalize_text(row.get("Conversion_to_Open"))
    if conversion == "yes":
        return "converted"
    if approach in {"laparoscopic","open","converted","robotic"}:
        return approach
    return pd.NA

def derive_recognition_timing(value):
    text = normalize_text(value)
    if not text:
        return pd.NA
    if text == "postoperative":
        return "postoperative_unspecified"
    return text

def derive_outcome_flags(value):
    outcome = normalize_legal_outcome(value)
    if pd.isna(outcome):
        return {"plaintiff_favorable":pd.NA, "defense_favorable":pd.NA, "mixed_outcome":pd.NA, "unknown_outcome":pd.NA}
    if outcome in {"Plaintiff-favorable","Settlement"}:
        return {"plaintiff_favorable":True, "defense_favorable":False, "mixed_outcome":False, "unknown_outcome":False}
    if outcome == "Defense-favorable":
        return {"plaintiff_favorable":False, "defense_favorable":True, "mixed_outcome":False, "unknown_outcome":False}
    if outcome == "Mixed":
        return {"plaintiff_favorable":pd.NA, "defense_favorable":pd.NA, "mixed_outcome":True, "unknown_outcome":False}
    return {"plaintiff_favorable":pd.NA, "defense_favorable":pd.NA, "mixed_outcome":False, "unknown_outcome":True}

def classify_procedural_stage(value):
    text = normalize_text(value)
    if not text:
        return pd.NA
    if "appeal" in text or "supreme court" in text or "reversal" in text or "affirmed" in text:
        return "appeal"
    if "settlement" in text:
        return "settlement"
    if "trial verdict" in text or text == "judgment" or "trial - directed verdict" in text or "new trial" in text:
        return "trial"
    if "summary judgment" in text:
        return "summary_judgment"
    if "dismiss" in text or "screening order" in text:
        return "dismissal_or_screening"
    if "motion" in text or "order" in text or "recommendation" in text:
        return "pretrial_motion_or_order"
    return "other"

def parse_demographics(value):
    text = normalize_text(value)
    out = {"age_years_extracted":np.nan, "age_group":np.nan, "gender_tidy":np.nan, "inmate_status":np.nan, "pregnancy_related":np.nan, "military_or_veteran":np.nan, "pediatric_or_minor":np.nan, "elderly_flag":np.nan}
    if not text or text in {"unknown","nan"}:
        return out
    age = None
    m = re.search(r"(\d+)\s*-\s*year-old", text)
    if not m:
        m = re.search(r"(\d+)\s+years old", text)
    if m:
        age = int(m.group(1))
        out["age_years_extracted"] = age
    if age is not None:
        if age < 2:
            out["age_group"] = "infant"
        elif age < 12:
            out["age_group"] = "child"
        elif age < 18:
            out["age_group"] = "adolescent"
        elif age < 40:
            out["age_group"] = "young_adult"
        elif age < 65:
            out["age_group"] = "middle_adult"
        else:
            out["age_group"] = "older_adult"
    elif "infant" in text:
        out["age_group"] = "infant"
    elif any(k in text for k in ["minor","child"]):
        out["age_group"] = "pediatric_unspecified"
    elif "adult" in text:
        out["age_group"] = "adult_unspecified"
    age_group = out["age_group"]
    if isinstance(age_group, str) and age_group in {"infant","child","adolescent","pediatric_unspecified"}:
        out["pediatric_or_minor"] = True
    elif isinstance(age_group, str):
        out["pediatric_or_minor"] = False
    if age is not None:
        out["elderly_flag"] = age >= 65
    elif "elderly" in text:
        out["elderly_flag"] = True
    male = bool(re.search(r"\bmale\b", text))
    female = bool(re.search(r"\bfemale\b", text))
    if male and female:
        out["gender_tidy"] = "mixed_multiple_plaintiffs"
    elif male:
        out["gender_tidy"] = "male"
    elif female:
        out["gender_tidy"] = "female"
    out["inmate_status"] = True if re.search(r"prison|prisoner|inmate|detainee|incarcerat", text) else False
    out["pregnancy_related"] = True if "pregnan" in text else False
    out["military_or_veteran"] = True if any(k in text for k in ["marine","veteran","seaman","military","air force"]) else False
    return out

def outcome_group(outcome):
    if outcome in {"Plaintiff-favorable","Settlement"}:
        return "Plaintiff or settlement"
    if outcome == "Defense-favorable":
        return "Defense"
    if outcome == "Mixed":
        return "Mixed"
    return "Unknown"

def save_csv(df, name):
    path = OUTPUT_DIR / name
    df.to_csv(path, index=False)
    return path

def horizontal_bar(series, title, xlabel, ylabel, path):
    ax = series.sort_values().plot(kind="barh", figsize=(9,6))
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    plt.tight_layout()
    plt.savefig(path, dpi=200, bbox_inches="tight")
    plt.close()

def stacked_bar(df, category_col, outcome_col, title, xlabel, ylabel, path, order=None):
    table = pd.crosstab(df[category_col], df[outcome_col].map(outcome_group))
    desired = ["Defense","Plaintiff or settlement","Mixed","Unknown"]
    for c in desired:
        if c not in table.columns:
            table[c] = 0
    table = table[desired]
    if order is not None:
        table = table.reindex(order).dropna(how="all")
    ax = table.plot(kind="bar", stacked=True, figsize=(10,6))
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(path, dpi=200, bbox_inches="tight")
    plt.close()

def payout_plot(df, path):
    plot_df = df.dropna(subset=["payout_primary_num"]).copy().sort_values("payout_primary_num", ascending=False)
    labels = plot_df["Case_Name"].str.slice(0,40)
    ax = plt.figure(figsize=(11,6)).gca()
    ax.bar(labels, plot_df["payout_primary_num"])
    ax.set_yscale("log")
    ax.set_title("Explicit payout figures (log scale; adjusted award preferred, else settlement/award)")
    ax.set_xlabel("Case")
    ax.set_ylabel("US dollars (log scale)")
    plt.xticks(rotation=60, ha="right")
    plt.tight_layout()
    plt.savefig(path, dpi=200, bbox_inches="tight")
    plt.close()

def main():
    xl = pd.ExcelFile(INPUT_XLSX)
    if "Case_Master_Template" not in xl.sheet_names:
        raise ValueError(f"Case_Master_Template not found: {xl.sheet_names}")
    main_df = pd.read_excel(INPUT_XLSX, sheet_name="Case_Master_Template", dtype=object)
    extended_df = pd.read_excel(INPUT_XLSX, sheet_name="Extended_Extraction", dtype=object)
    original_columns = list(main_df.columns)
    core = main_df.loc[main_df["Core_Analytic_Case"] == "YES"].copy()
    core["breach_tokens_raw"] = core["Alleged_Breach_Categories"].apply(split_breaches)
    core["breach_categories_std"] = core["Alleged_Breach_Categories"].apply(map_breach_categories)
    core["breach_tokens_raw_pipe"] = core["breach_tokens_raw"].apply(lambda x: "|".join(x) if x else pd.NA)
    core["breach_categories_std_pipe"] = core["breach_categories_std"].apply(lambda x: "|".join(x) if x else pd.NA)
    for category, _ in BREACH_PATTERNS:
        core[f"breach_{category}"] = core["breach_categories_std"].apply(lambda values, c=category: True if c in values else False)
    core["perforated_or_gangrenous_flag"] = core.apply(derive_perforated_or_gangrenous, axis=1)
    core["difficult_case_flag"] = core.apply(derive_difficult_case, axis=1)
    core["difficulty_assessable_flag"] = core.apply(derive_difficulty_assessable, axis=1)
    core["delayed_diagnosis_alleged_flag"] = core["Delayed_Diagnosis_Alleged"].apply(ynu_to_bool)
    core["need_for_reoperation_flag"] = core["Need_for_Reoperation"].apply(ynu_to_bool)
    core["need_for_bowel_resection_flag"] = core["Need_for_Bowel_Resection"].apply(ynu_to_bool)
    core["bowel_resection_flag"] = core.apply(derive_bowel_resection, axis=1)
    core["death_flag"] = core["Death"].apply(ynu_to_bool)
    core["long_term_morbidity_flag"] = core["Long_Term_Morbidity"].apply(ynu_to_bool)
    core["adaptation_performed_flag"] = core["Adaptation_Performed"].apply(ynu_to_bool)
    core["expert_testimony_mentioned_flag"] = core["Expert_Testimony_Mentioned"].apply(ynu_to_bool)
    core["informed_consent_alleged_flag"] = core["Inadequate_Informed_Consent_Alleged"].apply(ynu_to_bool)
    core["poor_communication_alleged_flag"] = core["Poor_Communication_Alleged"].apply(ynu_to_bool)
    core["failure_to_refer_alleged_flag"] = core["Failure_to_Refer_Alleged"].apply(ynu_to_bool)
    core["improper_postop_management_alleged_flag"] = core["Improper_Postop_Management_Alleged"].apply(ynu_to_bool)
    core["procedure_approach_tidy"] = core.apply(derive_procedure_approach, axis=1)
    core["adaptation_type_tidy"] = core["Adaptation_Type"].apply(lambda x: pd.NA if normalize_text(x) in {"","unknown"} else normalize_text(x))
    core["recognition_timing_tidy"] = core["Recognition_Timing"].apply(derive_recognition_timing)
    core["legal_outcome_tidy"] = core["Legal_Outcome"].apply(normalize_legal_outcome)
    core["appellate_status_tidy"] = core["Appellate_Status"].apply(normalize_appellate_status)
    core["procedural_stage"] = core["Procedural_Posture"].apply(classify_procedural_stage)
    outcome_flags = core["Legal_Outcome"].apply(derive_outcome_flags).apply(pd.Series)
    core = pd.concat([core, outcome_flags], axis=1)
    for col in ["Damages_Award","Settlement_Amount","Economic_Damages","NonEconomic_Damages","Punitive_Damages","Damages_Award_Adjusted_2026"]:
        core[f"{col}_num"] = core[col].apply(parse_money)
    core["payout_primary_num"] = core["Damages_Award_Adjusted_2026_num"]
    core["payout_source"] = np.where(core["Damages_Award_Adjusted_2026_num"].notna(), "damages_award_adjusted_2026", pd.NA)
    mask = core["payout_primary_num"].isna() & core["Settlement_Amount_num"].notna()
    core.loc[mask, "payout_primary_num"] = core.loc[mask, "Settlement_Amount_num"]
    core.loc[mask, "payout_source"] = "settlement_amount_nominal"
    mask = core["payout_primary_num"].isna() & core["Damages_Award_num"].notna()
    core.loc[mask, "payout_primary_num"] = core.loc[mask, "Damages_Award_num"]
    core.loc[mask, "payout_source"] = "damages_award_nominal"
    demo = core["Plaintiff_Demographics"].apply(parse_demographics).apply(pd.Series)
    core = pd.concat([core, demo], axis=1)
    extended_nonempty = extended_df.set_index("Search_ID").drop(columns=["LLM_Status"], errors="ignore").notna().any(axis=1)
    core["has_any_extended_extraction_text"] = core["Search_ID"].map(extended_nonempty).fillna(False)
    derived_columns = [c for c in core.columns if c not in original_columns]
    core = core[original_columns + derived_columns]
    full_core = core.loc[core["LLM_Status"] == "full"].copy()

    high_level_summary = pd.DataFrame([
        {"metric":"total_rows_case_master_template","value":len(main_df)},
        {"metric":"core_analytic_case_yes","value":int((main_df["Core_Analytic_Case"]=="YES").sum())},
        {"metric":"core_analytic_case_yes_pct","value":float((main_df["Core_Analytic_Case"]=="YES").mean())},
        {"metric":"full_extraction_cases_in_core","value":int((core["LLM_Status"]=="full").sum())},
        {"metric":"first_pass_only_cases_in_core","value":int((core["LLM_Status"]=="first_pass_only").sum())},
    ])
    llm_status_dist = main_df["LLM_Status"].value_counts(dropna=False).rename_axis("LLM_Status").reset_index(name="n")
    reviewer_conf_dist = pd.to_numeric(main_df["Reviewer_Confidence_Score"], errors="coerce").value_counts(dropna=False).rename_axis("Reviewer_Confidence_Score").reset_index(name="n")
    case_type_dist_all = main_df["First_Pass_Likely_Case_Type"].value_counts(dropna=False).rename_axis("First_Pass_Likely_Case_Type").reset_index(name="n")
    case_type_dist_core = core["First_Pass_Likely_Case_Type"].value_counts(dropna=False).rename_axis("First_Pass_Likely_Case_Type").reset_index(name="n")
    outcome_dist = full_core["Legal_Outcome"].value_counts(dropna=False).rename_axis("Legal_Outcome").reset_index(name="n")
    outcome_by_case_type = pd.crosstab(full_core["First_Pass_Likely_Case_Type"], full_core["Legal_Outcome"]).reset_index()
    case_type_directional_rows = []
    for case_type, sub in full_core.groupby("First_Pass_Likely_Case_Type", dropna=False):
        p = ((sub["Legal_Outcome"]=="Plaintiff-favorable") | (sub["Legal_Outcome"]=="Settlement")).sum()
        d = (sub["Legal_Outcome"]=="Defense-favorable").sum()
        m = (sub["Legal_Outcome"]=="Mixed").sum()
        u = (sub["Legal_Outcome"]=="Unknown").sum()
        case_type_directional_rows.append({
            "case_type":case_type, "n":len(sub), "plaintiff_or_settlement":int(p), "defense":int(d), "mixed":int(m), "unknown":int(u),
            "plaintiff_share_among_directional_known": float(p/(p+d)) if (p+d) else np.nan
        })
    case_type_directional = pd.DataFrame(case_type_directional_rows).sort_values("n", ascending=False)

    breach_counter = Counter()
    for values in full_core["breach_categories_std"]:
        breach_counter.update(values)
    breach_counts = pd.DataFrame([{"breach_category":cat,"n_cases":count} for cat,count in breach_counter.most_common()])
    top_breaches = breach_counts.head(10)["breach_category"].tolist()
    breach_outcome_rows = []
    for cat in top_breaches:
        sub = full_core.loc[full_core[f"breach_{cat}"] == True]
        vc = sub["Legal_Outcome"].value_counts(dropna=False)
        breach_outcome_rows.append({
            "breach_category":cat, "n_cases":len(sub),
            "Defense-favorable":int(vc.get("Defense-favorable",0)),
            "Plaintiff-favorable":int(vc.get("Plaintiff-favorable",0)),
            "Settlement":int(vc.get("Settlement",0)),
            "Mixed":int(vc.get("Mixed",0)),
            "Unknown":int(vc.get("Unknown",0)),
        })
    breach_by_outcome = pd.DataFrame(breach_outcome_rows)
    breach_by_outcome["known_directional_n"] = breach_by_outcome["Defense-favorable"] + breach_by_outcome["Plaintiff-favorable"] + breach_by_outcome["Settlement"]
    breach_by_outcome["plaintiff_or_settlement_share_among_directional_known"] = (breach_by_outcome["Plaintiff-favorable"] + breach_by_outcome["Settlement"]) / breach_by_outcome["known_directional_n"].replace({0:np.nan})

    perforation_by_outcome = pd.crosstab(full_core["perforated_or_gangrenous_flag"], full_core["Legal_Outcome"], dropna=False).reset_index()
    difficulty_by_outcome = pd.crosstab(full_core["difficult_case_flag"], full_core["Legal_Outcome"], dropna=False).reset_index()
    recognition_timing_dist = full_core["recognition_timing_tidy"].value_counts(dropna=False).rename_axis("recognition_timing_tidy").reset_index(name="n")
    recognition_by_outcome = pd.crosstab(full_core["recognition_timing_tidy"], full_core["Legal_Outcome"], dropna=False).reset_index()
    expert_by_outcome = pd.crosstab(full_core["Expert_Testimony_Mentioned"], full_core["Legal_Outcome"], dropna=False).reset_index()
    communication_by_outcome = pd.crosstab(full_core["Poor_Communication_Alleged"], full_core["Legal_Outcome"], dropna=False).reset_index()
    informed_consent_by_outcome = pd.crosstab(full_core["Inadequate_Informed_Consent_Alleged"], full_core["Legal_Outcome"], dropna=False).reset_index()

    payout_cases = full_core.loc[full_core["payout_primary_num"].notna(), [
        "Search_ID","Case_Name","Year","Legal_Outcome","First_Pass_Likely_Case_Type","Injury_Type_Primary","Plaintiff_Demographics","Delayed_Diagnosis_Alleged",
        "Damages_Award","Settlement_Amount","Damages_Award_Adjusted_2026","payout_primary_num","payout_source"
    ]].sort_values("payout_primary_num", ascending=False)

    payout_summary_rows = []
    payout_groups = [
        ("overall", pd.Series(["all"] * len(full_core), index=full_core.index)),
        ("first_pass_case_type", full_core["First_Pass_Likely_Case_Type"]),
        ("delayed_diagnosis_alleged", full_core["Delayed_Diagnosis_Alleged"]),
        ("injury_type_primary", full_core["Injury_Type_Primary"]),
        ("injury_severity", full_core["Injury_Severity"]),
        ("gender_tidy", full_core["gender_tidy"]),
        ("inmate_status", full_core["inmate_status"].map({True:"yes",False:"no"})),
        ("pediatric_or_minor", full_core["pediatric_or_minor"].map({True:"yes",False:"no"})),
    ]
    for grouping_name, grouping_series in payout_groups:
        temp = full_core.assign(_group=grouping_series)
        for group_value, sub in temp.groupby("_group", dropna=False):
            vals = sub["payout_primary_num"].dropna()
            payout_summary_rows.append({
                "grouping":grouping_name, "group_value":group_value, "n_cases_in_group":len(sub),
                "n_with_explicit_payout":int(vals.notna().sum()),
                "mean_payout": float(vals.mean()) if len(vals) else np.nan,
                "median_payout": float(vals.median()) if len(vals) else np.nan,
                "min_payout": float(vals.min()) if len(vals) else np.nan,
                "max_payout": float(vals.max()) if len(vals) else np.nan,
            })
    payout_summary = pd.DataFrame(payout_summary_rows)
    delayed_dx_payout = full_core.groupby("Delayed_Diagnosis_Alleged", dropna=False)["payout_primary_num"].agg(n_with_explicit_payout="count", mean_payout="mean", median_payout="median", min_payout="min", max_payout="max").reset_index()

    key_fields = ["Legal_Outcome","Alleged_Breach_Categories","Procedure_Approach","Perforated_or_Gangrenous_Appendix","Difficult_Case","Difficulty_Documented","Adaptation_Performed","Recognition_Timing","Expert_Testimony_Mentioned","Inadequate_Informed_Consent_Alleged","Plaintiff_Demographics","Damages_Award_Adjusted_2026","Settlement_Amount","Reviewer_Confidence_Score"]
    quality_rows = []
    for col in key_fields:
        s = core[col]
        text = s.astype(str)
        missing_n = int(s.isna().sum())
        unknown_n = int(text.str.upper().eq("UNKNOWN").sum())
        not_documented_n = int(text.str.lower().eq("not documented").sum())
        unclear_n = int(text.str.lower().eq("unclear").sum())
        not_assessable_n = int(text.str.lower().eq("not assessable").sum())
        noninformative_n = missing_n + unknown_n + not_documented_n + unclear_n + not_assessable_n
        quality_rows.append({
            "field":col, "n_total_core":len(core), "missing_n":missing_n, "unknown_n":unknown_n, "not_documented_n":not_documented_n, "unclear_n":unclear_n, "not_assessable_n":not_assessable_n,
            "noninformative_n":noninformative_n, "noninformative_pct":noninformative_n/len(core), "available_n": int(len(core)-missing_n),
        })
    key_field_quality = pd.DataFrame(quality_rows).sort_values("noninformative_pct", ascending=False)

    full_core["Reviewer_Confidence_Score_num"] = pd.to_numeric(full_core["Reviewer_Confidence_Score"], errors="coerce")
    manual_review_priority = full_core.loc[(full_core["Reviewer_Confidence_Score_num"] <= 3) | (full_core["Needs_Manual_Review"]=="YES"),
        ["Search_ID","Case_Name","Reviewer_Confidence_Score","Needs_Manual_Review","LLM_Status","First_Pass_Likely_Case_Type","Reviewer_Notes"]
    ].sort_values(["Reviewer_Confidence_Score","Case_Name"], na_position="last")

    demo_summary = {
        "gender_tidy": full_core["gender_tidy"].value_counts(dropna=False),
        "age_group": full_core["age_group"].value_counts(dropna=False),
        "inmate_status": full_core["inmate_status"].map({True:"yes",False:"no"}).value_counts(dropna=False),
        "pregnancy_related": full_core["pregnancy_related"].map({True:"yes",False:"no"}).value_counts(dropna=False),
        "military_or_veteran": full_core["military_or_veteran"].map({True:"yes",False:"no"}).value_counts(dropna=False),
        "pediatric_or_minor": full_core["pediatric_or_minor"].map({True:"yes",False:"no"}).value_counts(dropna=False),
    }
    max_len = max(len(s) for s in demo_summary.values())
    demo_df = pd.DataFrame({
        "category_value": range(max_len)
    })
    for name, series in demo_summary.items():
        vals = list(series.items())
        col_values = [f"{idx}: {cnt}" for idx, cnt in vals] + [np.nan] * (max_len - len(vals))
        demo_df[name] = col_values

    cleaned_csv = save_csv(core, "appendectomy_core_tidy.csv")
    cleaned_full_csv = save_csv(full_core, "appendectomy_core_full_only.csv")
    head5_csv = save_csv(core.head(5), "appendectomy_tidy_head5.csv")
    outputs = [
        save_csv(high_level_summary, "table_core_high_level_summary.csv"),
        save_csv(llm_status_dist, "table_llm_status_distribution.csv"),
        save_csv(reviewer_conf_dist, "table_reviewer_confidence_distribution.csv"),
        save_csv(case_type_dist_all, "table_first_pass_case_type_distribution_all.csv"),
        save_csv(case_type_dist_core, "table_first_pass_case_type_distribution_core.csv"),
        save_csv(outcome_dist, "table_legal_outcome_full_core.csv"),
        save_csv(outcome_by_case_type, "table_outcome_by_case_type_full_core.csv"),
        save_csv(case_type_directional, "table_case_type_directional_shares_full_core.csv"),
        save_csv(breach_counts, "table_breach_counts_full_core.csv"),
        save_csv(breach_by_outcome, "table_breach_by_outcome_full_core.csv"),
        save_csv(perforation_by_outcome, "table_perforation_by_outcome_full_core.csv"),
        save_csv(difficulty_by_outcome, "table_difficulty_by_outcome_full_core.csv"),
        save_csv(recognition_timing_dist, "table_recognition_timing_distribution_full_core.csv"),
        save_csv(recognition_by_outcome, "table_recognition_timing_by_outcome_full_core.csv"),
        save_csv(expert_by_outcome, "table_expert_testimony_by_outcome_full_core.csv"),
        save_csv(communication_by_outcome, "table_communication_by_outcome_full_core.csv"),
        save_csv(informed_consent_by_outcome, "table_informed_consent_by_outcome_full_core.csv"),
        save_csv(payout_cases, "table_payout_cases_full_core.csv"),
        save_csv(payout_summary, "table_payout_summary_full_core.csv"),
        save_csv(delayed_dx_payout, "table_delayed_diagnosis_vs_payout_full_core.csv"),
        save_csv(key_field_quality, "table_key_field_quality_core.csv"),
        save_csv(manual_review_priority, "table_manual_review_priority_full_core.csv"),
        save_csv(demo_df, "table_demographics_summary_full_core.csv"),
    ]
    fig1 = OUTPUT_DIR / "fig_case_type_distribution_core.png"
    fig2 = OUTPUT_DIR / "fig_top_breach_categories_full_core.png"
    fig3 = OUTPUT_DIR / "fig_case_type_by_outcome_full_core.png"
    fig4 = OUTPUT_DIR / "fig_explicit_payout_cases_full_core.png"
    horizontal_bar(core["First_Pass_Likely_Case_Type"].value_counts(), "Core analytic cases by first-pass case type", "Number of cases", "Case type", fig1)
    horizontal_bar(breach_counts.head(10).set_index("breach_category")["n_cases"], "Top standardized breach categories (full extraction subset)", "Number of cases", "Standardized breach category", fig2)
    stacked_bar(full_core, "First_Pass_Likely_Case_Type", "Legal_Outcome", "Legal outcome by first-pass case type (full extraction subset)", "Case type", "Number of cases", fig3, order=["delayed_diagnosis","operative_complication","postop_management"])
    payout_plot(full_core, fig4)
    zip_path = OUTPUT_DIR / "appendectomy_analysis_outputs.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in [cleaned_csv, cleaned_full_csv, head5_csv, fig1, fig2, fig3, fig4, Path(__file__)] + outputs:
            zf.write(p, p.name)
    print(json.dumps({
        "sheet_names": xl.sheet_names,
        "total_rows_case_master_template": len(main_df),
        "core_analytic_cases": len(core),
        "core_full_extraction_cases": len(full_core),
        "cleaned_csv": str(cleaned_csv),
        "cleaned_full_csv": str(cleaned_full_csv),
        "zip_path": str(zip_path),
    }, indent=2))

if __name__ == "__main__":
    main()
