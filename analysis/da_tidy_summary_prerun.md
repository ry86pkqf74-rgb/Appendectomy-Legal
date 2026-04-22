# Appendectomy core analytic tidy dataset summary

- Total workbook rows in `Case_Master_Template`: 1,225
- Core analytic rows retained (`Core_Analytic_Case == YES`): 82
- Core analytic share: 6.7%
- Full extraction already present: 46
- First-pass-only core rows: 36

## Plaintiff-favorable distribution
| plaintiff_favorable   |   n |   pct |
|:----------------------|----:|------:|
| UNKNOWN               |  46 |  56.1 |
| NO                    |  23 |  28   |
| YES                   |  13 |  15.9 |

## Damages (adjusted 2026 dollars)
- Non-missing adjusted awards: 4
- Mean adjusted award: $536,687.43
- Median adjusted award: $23,753.82
- Min adjusted award: $6,910.46
- Max adjusted award: $2,092,331.62

## Top breach types (derived YES counts)
| breach_type                       |   n_yes |   pct_core_cases |
|:----------------------------------|--------:|-----------------:|
| breach_delayed_diagnosis          |      32 |             39   |
| breach_improper_postop_management |      21 |             25.6 |
| breach_surgical_technique_error   |      13 |             15.9 |
| breach_communication_failure      |      13 |             15.9 |
| breach_failure_to_refer           |      13 |             15.9 |

## Major derived columns: UNKNOWN or missing rate
| column                             |   unknown_pct |   n_unknown_or_missing |
|:-----------------------------------|--------------:|-----------------------:|
| operative_approach                 |          92.7 |                     76 |
| death_or_long_term_morbidity       |          80.5 |                     66 |
| difficult_case_composite           |          80.5 |                     66 |
| perforated_or_gangrenous           |          67.1 |                     55 |
| plaintiff_gender                   |          65.9 |                     54 |
| plaintiff_favorable                |          56.1 |                     46 |
| plaintiff_age_group                |          54.9 |                     45 |
| high_severity_injury               |          52.4 |                     43 |
| adaptation_performed               |          45.1 |                     37 |
| breach_delayed_diagnosis           |          43.9 |                     36 |
| breach_communication_failure       |          43.9 |                     36 |
| breach_inadequate_informed_consent |          43.9 |                     36 |
| breach_failure_to_refer            |          43.9 |                     36 |
| breach_failure_to_remove_appendix  |          43.9 |                     36 |
| breach_surgical_technique_error    |          43.9 |                     36 |
| breach_improper_postop_management  |          43.9 |                     36 |
| inmate_case                        |           0.0 |                      0 |

## Major source columns: UNKNOWN or missing rate
| column                              |   unknown_or_missing_pct |
|:------------------------------------|-------------------------:|
| Difficult_Case                      |                     97.6 |
| Damages_Award_Adjusted_2026         |                     95.1 |
| Procedure_Approach                  |                     92.7 |
| Adaptation_Performed                |                     91.5 |
| Long_Term_Morbidity                 |                     80.5 |
| Perforated_or_Gangrenous_Appendix   |                     69.5 |
| Disease_State_at_Presentation       |                     68.3 |
| Plaintiff_Demographics              |                     57.3 |
| Injury_Severity                     |                     53.7 |
| Death                               |                     52.4 |
| Legal_Outcome                       |                     51.2 |
| Inadequate_Informed_Consent_Alleged |                     48.8 |
| Poor_Communication_Alleged          |                     47.6 |
| Improper_Postop_Management_Alleged  |                     45.1 |
| Failure_to_Refer_Alleged            |                     45.1 |
| Delayed_Diagnosis_Alleged           |                     43.9 |
| Difficulty_Assessability            |                     43.9 |

## Parsing ambiguities flagged
- `Legal_Outcome == Mixed` was left as `plaintiff_favorable = UNKNOWN` unless `Appellate_Status` explicitly indicated plaintiff or defense win.
- `Disease_State_at_Presentation == abscess-phlegmon` was **not** forced to perforated/gangrenous without explicit support from `Perforated_or_Gangrenous_Appendix`.
- Free-text demographics with multiple plaintiffs (e.g., parent/child or male/female co-plaintiffs) were left as `plaintiff_gender = unknown` unless the patient-specific sex was explicit.
- `operative_approach` remained `unclear` unless `Procedure_Approach`, `Conversion_to_Open`, or an explicit operative snippet stated laparoscopic/open/conversion.
- High UNKNOWN rates are driven in part by 36 core rows marked `LLM_Status = first_pass_only` / `Full_Extraction_Performed = NO`.