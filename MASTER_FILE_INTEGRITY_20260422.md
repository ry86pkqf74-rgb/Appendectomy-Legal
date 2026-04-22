# Master Canonical File — Integrity Summary

**File:** `AppendectomyMaster_updated.xlsx`
**Built:** 2026-04-22
**Source merge:** `scripts/merge_results.py` applied to `AppendectomyMaster.xlsx`
**Pre-run snapshot:** `AppendectomyMaster_PRE_RUNPROD_20260422.xlsx`
**Model:** gpt-oss-120b (RUNPROD)
**Jobs merged:** A (first-pass pass-2, n=36) · B (low-confidence rerun, n=44) · C (extended extraction, n=82) · D (new-domain 3-field, n=2)

## Workbook structure

| Sheet | Shape | Notes |
|---|---|---|
| Read_Me | 43 × 1 | Strict UNKNOWN rule governs all analytic decisions |
| Case_Master_Template | 1,225 × 100 | 3 columns newly added post-run (see below) |
| Data_Dictionary | 96 × 4 | |
| Extended_Extraction | 1,225 × 13 | Narrative/JSON fields, populated for all 82 core |
| Manual_Review_Queue | 120 × 9 | |

## Core-case integrity (Core_Analytic_Case == YES)

| Check | Expected | Actual | Pass |
|---|---|---|---|
| Core count | 82 | 82 | YES |
| LLM_Status == "full" | 82 | 82 | YES |
| Full_Extraction_Performed == "YES" | 82 | 82 | YES |
| Non-null `Claim_Type` | 82 | 82 | YES |
| Non-null `Plaintiff_Custodial_Status_Detail` | 82 | 82 | YES |
| Non-null `Deliberate_Indifference_Standard_Applied` | 82 | 82 | YES |
| Year=2026 artifacts removed | 0 | 1* | see note |

*The single remaining Year=2026 case (`westlaw_…_appendectomy7_0039`, Hernández-Sánchez v. Hospital San Cristóbal) carries citation `2026 WL 765523` — this is a genuine 2026 opinion, not an artifact. Pre-run count was 7.

## Reviewer_Confidence_Score distribution (core, 82 rows)

| Score | Pre-run | Post-run |
|---:|---:|---:|
| 2 | 4 | 2 |
| 3 | 40 | 48 |
| 4 | 2 | 32 |
| 5 | 0 | 0 |

Core cases still at score ≤3 after Job B are genuinely information-sparse opinions (MTD orders, §1983 screening orders, SOL rulings), not LLM failures — they should be flagged in sensitivity analysis rather than re-run.

## New legal-type fields (drive FTCA vs §1983 vs state-law bifurcation)

| Field | Distribution (core, n=82) |
|---|---|
| `Claim_Type` | section_1983_civil_rights: 41 · FTCA_malpractice: 19 · state_law_malpractice: 14 · EMTALA: 5 · other: 3 |
| `Plaintiff_Custodial_Status_Detail` | not_custodial: 39 · state_prisoner: 33 · federal_prisoner: 7 · pretrial_detainee: 3 |
| `Deliberate_Indifference_Standard_Applied` | NO: 41 · YES: 40 · UNKNOWN: 1 |

The split is clean: 50% of core cases apply the deliberate-indifference subjective-knowledge standard (§1983 / 8th-/14th-Amendment), 50% do not (FTCA, state-law malpractice, EMTALA). These two populations must be analyzed separately — pooling them conflates two legally distinct liability standards.

## Extended_Extraction coverage (core, n=82)

| Field | Non-null |
|---|---:|
| Plaintiff_Claims_Expanded | 82/82 |
| Evidence_Quotes_JSON | 82/82 |
| Extended_Extraction_Notes | 82/82 |
| Plaintiff_Medical_Support_Summary | 80/82 |
| Claim_Support_Matrix_JSON | 80/82 |
| Court_Medical_Reasoning_Summary | 69/82 |
| Defense_Medical_Rebuttal_Summary | 64/82 |
| Operative_Findings_Detail | 50/82 |
| Comorbid_Diagnoses_Text | 14/82 |
| Plaintiff_Expert_Summary | 14/82 |
| Defense_Expert_Summary | 14/82 |

Low rates for Operative_Findings_Detail (50/82), Expert summaries (14/82), and Comorbid_Diagnoses (14/82) reflect Read_Me discipline — these opinions don't mention the detail, so the field is legitimately blank rather than hallucinated.

## Key UNKNOWN-rate deltas (core, from validation_report.md)

Biggest improvements in the RUNPROD pass:

| Column | Pre %UNK | Post %UNK | Δ |
|---|---:|---:|---:|
| Legal_Outcome | 43.9 | 0.0 | −43.9 |
| Court | 43.9 | 0.0 | −43.9 |
| Plaintiff_Demographics | 57.3 | 14.6 | −42.7 |
| Disease_State_at_Presentation | 68.3 | 32.9 | −35.4 |
| Delayed_Diagnosis_Alleged | 43.9 | 8.5 | −35.4 |
| Failure_to_Refer_Alleged | 45.1 | 12.2 | −32.9 |
| Inadequate_Informed_Consent_Alleged | 48.8 | 22.0 | −26.8 |
| Procedure_Approach | 92.7 | 76.8 | −15.9 |

## Validation flags

80/82 core rows carry a Reviewer_Notes validation tag from the run. Majority are structural: the 5 screening-gate fields (`Is_Malpractice_Case`, `Appendicitis_or_Appendectomy_Index_Episode`, `Index_Procedure_Appendectomy`, `Appendicitis_Diagnosis_Case`, `Has_Clinically_Meaningful_Appendicitis_or_Appendectomy_Harm`) were intentionally not re-extracted by Jobs A/B (those fields come from the first-pass screen), so the `missing_fields=[…]` tags on those five are expected. A small number of rows also have boolean fields flagged as `'UNKNOWN' not in ['YES','NO']` — those are genuine UNKNOWNs preserved per the Read_Me rule. No silent coercion occurred.

## Files promoted to the workspace root

- `AppendectomyMaster_updated.xlsx` — canonical post-RUNPROD master
- `AppendectomyMaster_PRE_RUNPROD_20260422.xlsx` — pre-run archive snapshot
- `validation_report.md` — before/after diff
- `spot_check_report.md` — reviewer spot checks on the run
- `segment_counts.txt` — segmentation provenance
- `LLM_PASSES_RUNBOOK.md` — methods-section material for the manuscript

All four JSONL outputs (A/B/C/D raw + parsed), pipeline scripts, manifests, prompts, and allowed_values config already live in `extraction_2/` on GitHub (commit `51b470e` on `main` in `ry86pkqf74-rgb/Appendectomy-Legal`).
