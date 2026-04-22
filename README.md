# Appendectomy Medicolegal Extraction — Pipeline Overview

This package extracts structured medicolegal data from 13 Westlaw RTF exports covering appendectomy- and appendicitis-related litigation. Everything runs against a single local OpenAI-compatible inference server hosting `gpt-oss-120b` (vLLM, XGrammar guided-JSON, `temperature=0`). The workflow is deterministic and resumable.

## Deliverables (in `results/`)

| File | Role |
|---|---|
| `AppendectomyMaster.xlsx` | Five-sheet workbook (Read_Me, Case_Master_Template, Data_Dictionary, Extended_Extraction, Manual_Review_Queue) |
| `case_master.csv` | Flat master table: one row per parsed case, all ~96 columns |
| `extended.csv` | Narrative-heavy second-pass fields (case summary, allegations, expert opinions, plaintiff profile, etc.) |
| `cases.jsonl` | Per-case audit log — pass-1 result, pass-2 raw response, merged record. Resumable checkpoint file |
| `manifest.csv` | Deterministic preprocessing index (Search_ID, File_Name, Segment_Index, hints, char count) |
| `exclusions.csv` | Every excluded case with the reason and first-pass classifier hints |
| `run.log` | Wall-clock progress of the full run |

Scripts that produced it all, in the `appendectomy_pipeline/` folder:

| Script | Role |
|---|---|
| `make_template.py` | Builds `Template.xlsx` with the Read_Me, Case_Master_Template, Data_Dictionary, and Manual_Review_Queue sheets |
| `appendectomy_extractor.py` | Two-pass pipeline (preprocessing + pass-1 classifier + pass-2 structured extractor + dedup + output writers) |
| `post_process.py` | Year normalization, BLS-CPI-U inflation-adjusted damages, and Manual_Review_Queue population |
| `vllm_serve.sh` | Launches vLLM for `gpt-oss-120b`, TP=2, port 8000, guided-JSON via XGrammar |
| `requirements.txt` | Python deps: `openpyxl`, `requests`, `striprtf`, `pandas` |

## Run results

- 13 RTF files → 1,225 parsed case chunks (delimited by "End of Document")
- 82 Core_Analytic_Case=YES
- 1,143 excluded (with categorical reasons)
- Top exclusion drivers: non-malpractice (VA/ERISA/employment/insurance/civil-rights), no appendicitis index episode, or UNKNOWN on the malpractice gate
- Manual review queue surfaces 120 cases where a human should double-check the AI output
- Full run wall-clock: ~17 minutes on 2× H200 SXM (pass-1 on 1,225 cases in 454s, pass-2 on 164 candidates in 565s)

## Core analytic case mix

- **Injury_Type_Primary**: 21 delayed-diagnosis-with-perforation, 10 failed appendectomy, 8 other, 5 abscess/infection, 1 obstruction/adhesive complication, 1 leak
- 4 cases have monetary damages awarded + CPI-adjusted to 2026 dollars (column `Damages_Award_Adjusted_2026`)

## Screening logic (A + B + C)

A case is `Core_Analytic_Case=YES` only when all three gate questions are YES:

- **A — Is_Malpractice_Case**: medical malpractice / professional negligence, not benefits, employment, insurance, or administrative disputes
- **B — Appendicitis_or_Appendectomy_Index_Episode**: the clinical index episode is appendicitis or an appendectomy. A delayed / missed appendicitis diagnosis QUALIFIES even if no appendectomy was performed
- **C — Has_Clinically_Meaningful_Appendicitis_or_Appendectomy_Harm**: documented injury (perforation, peritonitis, bowel injury, stump leak, wrongful death, etc.)

Any UNKNOWN on A or B, or an explicit NO on any of A/B/C, excludes the case. The exclusion reason and each gate flag are preserved in the master row for auditability.

## Prompting and structured output

- **Pass 1 — classifier** (low-token, ~600 completion tokens max): outputs JSON with the three gates plus `likely_case_type`, `full_extraction_warranted`, and a ≤200-char rationale.
- **Pass 2 — structured extractor** (~4,500 completion tokens max): produces one JSON object per case matching the Template columns. Includes the appendectomy-specific extensions: `Disease_State_at_Presentation`, `Injury_Type_Primary`, `Perforated_or_Gangrenous_Appendix`, `Stump_Leak_or_Stump_Problem`, `Appendix_Not_Removed`, `Appendicitis_Diagnosis_Case`. Only cases whose pass-1 classifier hits A+B+C=YES are sent through pass-2; every other case keeps its pass-1 flags + first-pass rationale and is marked `Full_Extraction_Performed=NO`.
- Both passes use `response_format={"type":"json_object"}` so vLLM's XGrammar guided-JSON decoding constrains the output.

## Determinism and resumability

- `temperature=0`, `top_p=1.0`, single model, single server.
- `cases.jsonl` is a per-case checkpoint; re-running the extractor skips cases whose Search_ID is already present in the JSONL.
- `Search_ID`, `Search_Group`, `Search_Term`, `Source_Database`, and `File_Name` are assigned deterministically during preprocessing and re-applied AFTER the pass-2 merge so the LLM can never overwrite them.

## Post-processing (post_process.py)

- `Year` normalization: when the Citation field contains a 4-digit year (e.g. `2010 WL 2522703`), that year is authoritative. This fixes the "Year=2026" artifact caused by Westlaw's export-date header leaking into raw year hints.
- `Damages_Award_Adjusted_2026`: parses `Damages_Award` as a monetary amount, inflation-adjusts to 2026 USD using BLS CPI-U annual averages (interpolation between anchor years; no network dependency).
- `Manual_Review_Queue` sheet: populated with every case where
    - `Core_Analytic_Case=YES` and narrative fields are empty (pass-2 may have errored), OR
    - pass-2 status is `error` / `json_error`, OR
    - a gate question is UNKNOWN and `Is_Malpractice_Case != NO`.

## Reproducing

1. Start the inference server:
   ```bash
   bash vllm_serve.sh gptoss120b
   # Model: openai/gpt-oss-120b, TP=2, port 8000, XGrammar guided-JSON
   ```

2. Build the template:
   ```bash
   python3 make_template.py --out Template.xlsx
   ```

3. Run extraction:
   ```bash
   python3 appendectomy_extractor.py \
       --input-glob "/workspace/appendectomy_data/*.rtf" \
       --template Template.xlsx \
       --output-xlsx  AppendectomyMaster.xlsx \
       --output-csv   case_master.csv \
       --output-jsonl cases.jsonl \
       --output-extended-csv extended.csv \
       --output-manifest     manifest.csv \
       --output-exclusions   exclusions.csv \
       --base-url http://127.0.0.1:8000/v1 \
       --model gptoss120b \
       --workers 12 \
       --search-group "Westlaw appendectomy search" \
       --search-term  "appendectomy malpractice Westlaw full-text export"
   ```

4. Post-process:
   ```bash
   python3 post_process.py \
       --xlsx AppendectomyMaster.xlsx \
       --csv  case_master.csv \
       --target-year 2026
   ```

## Infrastructure

- Runpod pod `dkmm9hy0y7jcu3` (appendectomy-server-gptoss)
- 2× H200 SXM (141 GB each)
- vLLM 0.19.1 on PyTorch 2.10 / CUDA 12.8
- Network volume `/workspace` (persistent between pod restarts)
- Container image `runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04`

## Known caveats

- 413 rows still carry `Year=2026` because their Citation field is either a cross-reference pointer ("Declined to Follow by ...") without a usable reporter year, or the raw citation_hint was a reporter volume without a year anchor. The vast majority of the 82 core analytic cases have correct years.
- Some pass-2 second-pass extractions returned partial structures; those cases are flagged in `Manual_Review_Queue` for human review.
- gpt-oss-120b emits chain-of-thought in the `reasoning` field (harmony format); we read only the `content` field so the saved outputs never include the model's reasoning trace.
