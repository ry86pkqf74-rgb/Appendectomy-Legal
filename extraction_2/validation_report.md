# LLM Pass Validation Report

**Before:** AppendectomyMaster.xlsx
**After:** AppendectomyMaster_updated.xlsx

- Core_Analytic_Case == YES: 82 → 82

## Pipeline status (Core cases only)

- Full extraction:    46 → 82
- first_pass_only:    36 → 0

## Reviewer_Confidence_Score distribution (Core cases)

| score | before | after |
|---:|---:|---:|
| 2 | 4 | 2 |
| 3 | 40 | 48 |
| 4 | 2 | 32 |

### UNKNOWN-rate deltas (Core cases)

| Column | Before %UNK | After %UNK | Δ |
|---|---:|---:|---:|
| Legal_Outcome | 43.9 | 0.0 | -43.9 |
| Procedure_Approach | 92.7 | 76.8 | -15.9 |
| Disease_State_at_Presentation | 68.3 | 32.9 | -35.4 |
| Injury_Severity | 53.7 | 46.3 | -7.3 |
| Perforated_or_Gangrenous_Appendix | 69.5 | 61.0 | -8.5 |
| Delayed_Diagnosis_Alleged | 43.9 | 8.5 | -35.4 |
| Inadequate_Informed_Consent_Alleged | 48.8 | 22.0 | -26.8 |
| Poor_Communication_Alleged | 47.6 | 34.1 | -13.4 |
| Failure_to_Refer_Alleged | 45.1 | 12.2 | -32.9 |
| Plaintiff_Demographics | 57.3 | 14.6 | -42.7 |
| Year | 0.0 | 0.0 | +0.0 |
| Court | 43.9 | 0.0 | -43.9 |

## Extended_Extraction coverage (Core cases)

| Field | Before non-null | After non-null |
|---|---:|---:|
| Comorbid_Diagnoses_Text | 0 | 14 |
| Operative_Findings_Detail | 0 | 50 |
| Plaintiff_Claims_Expanded | 0 | 82 |
| Plaintiff_Medical_Support_Summary | 0 | 80 |
| Defense_Medical_Rebuttal_Summary | 0 | 64 |
| Plaintiff_Expert_Summary | 0 | 14 |
| Defense_Expert_Summary | 0 | 14 |
| Court_Medical_Reasoning_Summary | 0 | 69 |
| Claim_Support_Matrix_JSON | 0 | 80 |
| Evidence_Quotes_JSON | 0 | 82 |
| Extended_Extraction_Notes | 0 | 82 |

## Validation issues flagged in Reviewer_Notes

- Rows with validation tags: **80**

First 10 issue rows:

- `westlaw_100_full_text_items_for_appendectomy_0000`: [JOB B VALIDATION: missing_fields=['Is_Malpractice_Case', 'Appendicitis_or_Appendectomy_Index_Episode', 'Index_Procedure_Appendectomy', 'Appendicitis_Diagnosis_Case', 'Has_Clinically_Meaningful_Appendicitis_or_Appendectomy_Harm']]
- `westlaw_100_full_text_items_for_appendectomy_0004`: The opinion provides detailed legal analysis but limited clinical detail; many procedure‑specific fields are unclear or not mentioned. [JOB A VALIDATION: missing_fields=['Is_Malpractice_Case', 'Appendicitis_or_Appendectomy_Index_Episode', 'Index_Procedure_Appendectomy', 'Appendicitis_Diagnosis_Case', 'Has_Clinically_Meaningful_Appendicitis_or_Appendectomy_Harm']]
- `westlaw_100_full_text_items_for_appendectomy_0010`: Many clinical details such as procedure approach, disease state, and timing metrics are not provided; custody status and claim type are inferred from context. [JOB A VALIDATION: missing_fields=['Is_Malpractice_Case', 'Appendicitis_or_Appendectomy_Index_Episode', 'Index_Procedure_Appendectomy', 'Appendicitis_Diagnosis_Case', 'Has_Clinically_Meaningful_Appendicitis_or_Appendectomy_Harm']]
- `westlaw_100_full_text_items_for_appendectomy_0012`: Many clinical detail fields are uncertain due to limited description; procedural and expert information largely absent. [JOB B VALIDATION: missing_fields=['Is_Malpractice_Case', 'Appendicitis_or_Appendectomy_Index_Episode', 'Index_Procedure_Appendectomy', 'Appendicitis_Diagnosis_Case', 'Has_Clinically_Meaningful_Appendicitis_or_Appendectomy_Harm']; Expert_Testimony_Mentioned: 'UNKNOWN' not in ['YES', 'NO']; Poor_Communication_Alleged: 'UNKNOWN' not in ['YES', 'NO']]
- `westlaw_100_full_text_items_for_appendectomy_0017`: [JOB B VALIDATION: missing_fields=['Is_Malpractice_Case', 'Appendicitis_or_Appendectomy_Index_Episode', 'Index_Procedure_Appendectomy', 'Appendicitis_Diagnosis_Case', 'Has_Clinically_Meaningful_Appendicitis_or_Appendectomy_Harm']; Improper_Postop_Management_Alleged: 'UNKNOWN' not in ['YES', 'NO']; Problematic_Visualization_Alleged: 'UNKNOWN' not in ['YES', 'NO']; Inadequate_Informed_Consent_Alleged: 'UNKNOWN' not in ['YES', 'NO']; Poor_Communication_Alleged: 'UNKNOWN' not in ['YES', 'NO']]
- `westlaw_100_full_text_items_for_appendectomy_0018`: Many clinical detail fields are not addressed in the opinion; extraction relies on limited factual statements about the foreign object and procedural timeline. [JOB B VALIDATION: missing_fields=['Is_Malpractice_Case', 'Appendicitis_or_Appendectomy_Index_Episode', 'Index_Procedure_Appendectomy', 'Appendicitis_Diagnosis_Case', 'Has_Clinically_Meaningful_Appendicitis_or_Appendectomy_Harm']]
- `westlaw_100_full_text_items_for_appendectomy_0019`: [JOB B VALIDATION: missing_fields=['Is_Malpractice_Case', 'Appendicitis_or_Appendectomy_Index_Episode', 'Index_Procedure_Appendectomy', 'Appendicitis_Diagnosis_Case', 'Has_Clinically_Meaningful_Appendicitis_or_Appendectomy_Harm']]
- `westlaw_100_full_text_items_for_appendectomy_0042`: Limited clinical detail; many fields uncertain or not addressed in the order. [JOB B VALIDATION: missing_fields=['Is_Malpractice_Case', 'Appendicitis_or_Appendectomy_Index_Episode', 'Index_Procedure_Appendectomy', 'Appendicitis_Diagnosis_Case', 'Has_Clinically_Meaningful_Appendicitis_or_Appendectomy_Harm']; Problematic_Visualization_Alleged: 'UNKNOWN' not in ['YES', 'NO']; Inadequate_Informed_Consent_Alleged: 'UNKNOWN' not in ['YES', 'NO']; Poor_Communication_Alleged: 'UNKNOWN' not in ['YES', 'NO']]
- `westlaw_100_full_text_items_for_appendectomy_0045`: Many clinical details such as procedure type, disease state, and injury specifics are not provided in the opinion, leading to numerous UNKNOWN values. [JOB A VALIDATION: missing_fields=['Is_Malpractice_Case', 'Appendicitis_or_Appendectomy_Index_Episode', 'Index_Procedure_Appendectomy', 'Appendicitis_Diagnosis_Case', 'Has_Clinically_Meaningful_Appendicitis_or_Appendectomy_Harm']]
- `westlaw_100_full_text_items_for_appendectomy_0058`: Limited clinical detail; many fields rely on inference from procedural order. [JOB B VALIDATION: missing_fields=['Is_Malpractice_Case', 'Appendicitis_or_Appendectomy_Index_Episode', 'Index_Procedure_Appendectomy', 'Appendicitis_Diagnosis_Case', 'Has_Clinically_Meaningful_Appendicitis_or_Appendectomy_Harm']]

## Year = 2026 artifacts remaining
- 1 (was 7 before)
- westlaw_100_full_text_items_for_appendectomy7_0039 — JUAN HERNÁNDEZ-SÁNCHEZ, et al., Plaintiffs, v. HOSPITAL SAN CRISTOBAL, et al., Defendants. — citation: 2026 WL 765523