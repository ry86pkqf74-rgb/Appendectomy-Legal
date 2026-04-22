# Appendectomy Malpractice — Final LLM Extraction Passes

**Comprehensive runbook for RUNPROD.** Executes four LLM jobs against **gpt-oss-120b** and merges the output back into `AppendectomyMaster.xlsx`.

---

## What this package does

Fills every gap identified in the audit of `AppendectomyMaster.xlsx`:

| Job | What it does | Target cases | Writes to | Prompt |
|---|---|---:|---|---|
| **A** | Pass-2 full extraction on cases that only got first-pass screening (missing Case_Name, Year, Court, all clinical/legal fields) | **36** | `Case_Master_Template` (every pass-2 field) | `system_pass2.md` |
| **B** | Re-extraction on low-confidence fully-extracted cases (Reviewer_Confidence_Score ≤ 3) | **44** | `Case_Master_Template` (overwrites existing) | `system_pass2.md` |
| **C** | Extended narrative extraction — the `Extended_Extraction` sheet is currently 100% empty across all 1,225 rows | **82** | `Extended_Extraction` (11 narrative fields) | `system_extended.md` |
| **D** | Targeted new-domain fields on cases not touched by A or B (i.e., fully-extracted + high-confidence) | **2** | `Case_Master_Template` (3 new fields only — does NOT touch existing data) | `system_new_domains_only.md` |

**Coverage math:** A(36) + B(44) + D(2) = **82 unique core cases**. Every core case gets the new `Claim_Type`, `Plaintiff_Custodial_Status_Detail`, and `Deliberate_Indifference_Standard_Applied` fields, and every core case either gets fresh extraction (A) or refreshed extraction (B) or targeted legal-type classification (D) on top of existing data.

**Total LLM calls:** 36 + 44 + 82 + 2 = **164** (assuming no retries).

---

## The 3 new fields added since the original package

Based on the Pro-review analysis, three new columns are now part of the main `Case_Master_Template` schema. They capture the legal-framework bifurcation that dominates this federal/Westlaw corpus:

1. **`Claim_Type`** — one of: `FTCA_malpractice` | `section_1983_civil_rights` | `state_law_malpractice` | `EMTALA` | `military_Feres` | `other` | `unknown`
2. **`Plaintiff_Custodial_Status_Detail`** — one of: `state_prisoner` | `federal_prisoner` | `pretrial_detainee` | `immigration_detainee` | `probationer_parolee` | `not_custodial` | `unknown`
3. **`Deliberate_Indifference_Standard_Applied`** — YES / NO / UNKNOWN

These are uniformly populated across all 82 core cases by the Job A + B + D combination. No case is left unclassified. Jobs A and B write the full pass-2 schema, which now includes the 3 new fields; Job D fills them in on the 2 remaining cases without touching any other field.

Why these three specifically: the Pro analysis strongly recommended splitting the analytical subset on FTCA-vs-§1983-vs-state-law claim type — these claim types have different legal standards, different plaintiff-favorable rates, and different damages exposure, but the original workbook had no structured way to distinguish them. Adding these three fields unlocks every FTCA-vs-§1983 comparison the analysis plan calls for.

---

## Prerequisites on RUNPROD

1. **gpt-oss-120b served over an OpenAI-compatible HTTP endpoint.** vLLM ≥ 0.6 is the most common way:
   ```bash
   vllm serve openai/gpt-oss-120b \
       --tensor-parallel-size 8 \
       --max-model-len 32768 \
       --port 8000
   ```
   sglang, llama.cpp-server, TGI, LMDeploy, and Ollama also work if they expose `/v1/chat/completions` and accept `response_format: {"type": "json_object"}`.

2. **Context window ≥ 32k tokens.** Several Westlaw opinions run 15–25k characters.

3. **The original Westlaw RTF files.** The package needs `/data/westlaw_rtfs/*.rtf` — the same RTFs fed to the original `appendectomy_extractor.py`. Expected filenames:
   ```
   Westlaw - 100 full text items for appendectomy.rtf
   Westlaw - 100 full text items for appendectomy1.rtf
   ...
   Westlaw - 100 full text items for appendectomy10.rtf
   ```

4. **Python 3.10+** and `pip install -r requirements.txt`.

---

## Package layout

```
run_llm_passes/
├── README.md                             ← this file
├── requirements.txt
├── .env.example
├── manifests/
│   ├── manifest_job_A_firstpass_pass2.csv       (36 cases)
│   ├── manifest_job_B_lowconfidence_rerun.csv   (44 cases)
│   ├── manifest_job_C_extended_extraction.csv   (82 cases)
│   └── manifest_job_D_new_domains_only.csv      (2 cases)
├── config/
│   ├── allowed_values.json               ← controlled vocab + validators
│   └── prompts/
│       ├── system_pass2.md               ← Jobs A + B (includes 3 new fields)
│       ├── system_extended.md            ← Job C (narrative extraction)
│       └── system_new_domains_only.md    ← Job D (3-field targeted pass)
├── scripts/
│   ├── split_rtf.py                      ← RTF → per-case plain text
│   ├── run_extraction.py                 ← LLM driver (accepts --job A|B|C|D)
│   ├── merge_results.py                  ← JSONL → updated xlsx
│   └── validate_output.py                ← before/after diff report
├── output_jsonl/                         ← empty, fills at runtime
└── logs/
```

---

## End-to-end run (happy path)

```bash
cd run_llm_passes/
cp .env.example .env     # edit endpoint/model if needed
export $(cat .env | xargs)

# 1. Split RTFs into per-case segments ---------------------------------
# Build a union manifest so split covers every case touched by any job.
cat manifests/manifest_job_*.csv | \
  awk -F',' 'NR==1 || !seen[$1]++' > /tmp/all_core.csv

python scripts/split_rtf.py \
    --input-dir /data/westlaw_rtfs \
    --output-dir /data/segments \
    --manifest /tmp/all_core.csv

# --- CRITICAL: verify segment alignment before spending tokens ---
# Pick 3 Search_IDs you trust from the original extraction and confirm
# the first ~200 chars of /data/segments/<sid>.txt matches the
# Case_Name in AppendectomyMaster.xlsx for that Search_ID.
head -c 300 /data/segments/westlaw_100_full_text_items_for_appendectomy_0000.txt
# should mention "Kandie R. Wright v. David H. Smith"

# 2. Run the four LLM jobs --------------------------------------------
# Start with Job A (smoke test, 36 cases, ~5 min)
python scripts/run_extraction.py --job A \
    --segments-dir /data/segments \
    --concurrency 4

# Inspect logs/A.log and output_jsonl/A_parsed.jsonl. If good, continue:
python scripts/run_extraction.py --job B --segments-dir /data/segments --concurrency 4
python scripts/run_extraction.py --job C --segments-dir /data/segments --concurrency 4
python scripts/run_extraction.py --job D --segments-dir /data/segments --concurrency 4

# 3. Merge into a fresh copy of the workbook --------------------------
python scripts/merge_results.py \
    --in  /data/AppendectomyMaster.xlsx \
    --out /data/AppendectomyMaster_updated.xlsx \
    --jsonl-dir output_jsonl \
    --jobs A B C D

# 4. Validate ---------------------------------------------------------
python scripts/validate_output.py \
    --before /data/AppendectomyMaster.xlsx \
    --after  /data/AppendectomyMaster_updated.xlsx \
    --report /data/validation_report.md

cat /data/validation_report.md | head -80
```

**Expected wall-clock** on a single H100/H200 with 4-way concurrency: Job A ~5 min, Job B ~7 min, Job C ~15 min, Job D <1 min. **Total under 30 minutes.**

---

## ⚠️ Critical: segment alignment

Each `Search_ID` encodes `<file_stub>_<segment_index>`. For example `westlaw_100_full_text_items_for_appendectomy1_0050` = "the 50th (0-indexed) case in `Westlaw - 100 full text items for appendectomy1.rtf`". If segmentation drifts between the original extraction and this re-run, results will land on the **wrong cases**.

**Mitigations:**

1. **Re-use the original segmenter if available.** If `appendectomy_extractor.py` is still on disk from the original pipeline, use its segmenter rather than `scripts/split_rtf.py`. The original pipeline's output is the ground truth.
2. **Verify by spot-check.** Before any LLM calls, open 5 segment `.txt` files and confirm the first 200 characters match the `Case_Name` already in the xlsx for the matching Search_ID. If alignment is off, STOP.
3. **Check segment counts.** Each RTF should yield ~100 segments (file names advertise "100 full text items"). If `split_rtf.py` yields 98 or 102, indices will shift.

`split_rtf.py` splits on Westlaw's "End of Document" marker with form-feed fallback. This is the common case, but manual verification is mandatory.

---

## Job-by-job details

### Job A — 36 first-pass-only cases

**Problem:** These cases passed the three-field screening gate based on pass-1 alone, but pass-2 extraction never ran. Result:
- `Case_Name` missing for 5 cases
- `Year = 2026` artifact for 7 cases (true year is in the Citation, e.g. `262 F.2d 469` → 1959)
- `Court`, `Jurisdiction` = NaN for all 36
- Every clinical, legal, and allegation field = NaN

**What Job A does:** Full pass-2 extraction using `config/prompts/system_pass2.md`. The prompt explicitly instructs the model to re-extract metadata (not trust pass-1), rejects `Year = 2026` defaults, and includes the pass-1 `Case_Name` as a soft hint for cross-checking.

**Merge behavior:** After merge, `merge_results.py` re-evaluates `Core_Analytic_Case` from the three gate fields. Expect 2–5 cases to drop out of Core once the model sees the full opinion — this is by design.

### Job B — 44 low-confidence fully-extracted cases

**Problem:** Read_Me says "confidence ≤ 3 deserves a manual pass"; 44/46 fully-extracted cases (95.7%) are at ≤ 3. Reviewer notes commonly cite "limited clinical detail" or "procedural-only ruling."

**What Job B does:** Same pass-2 prompt as Job A, applied to already-extracted cases. May converge with original extraction (confirming sparse source) or yield improved coverage.

**Caveat:** If Job B produces meaningfully different values for outcome/severity than the original extraction, the validation report flags those rows for human adjudication.

### Job C — Extended narrative extraction (all 82 core cases)

**Problem:** `Extended_Extraction` sheet is 100% empty (0/1,225 rows have content in any of the 11 narrative columns).

**What Job C does:** Runs `system_extended.md` on every core case and produces eight paragraph-length narrative summaries (plaintiff's theory, defense theory, plaintiff/defense experts, court's medical reasoning, operative findings, comorbidities), plus a JSON-encoded claim-support matrix and verbatim evidence-quote list.

**Output size:** 1–4k tokens per case. Total output ~150k tokens for Job C.

### Job D — Targeted new-domain pass (2 cases)

**Problem:** Adding three new legal-type fields (`Claim_Type`, `Plaintiff_Custodial_Status_Detail`, `Deliberate_Indifference_Standard_Applied`) to the main schema means every core case must be classified on those fields. Jobs A and B already touch 80 of the 82 core cases (A + B write the full pass-2 schema, which now includes the 3 new fields). The 2 remaining cases (both fully-extracted and at confidence 4) would otherwise never be touched.

**What Job D does:** Uses a minimal, focused prompt (`system_new_domains_only.md`) that classifies ONLY the 3 new fields. The merge step (`merge_new_domains` in `merge_results.py`) writes ONLY those 3 columns and never touches any other field — so existing high-confidence extraction data is preserved byte-for-byte.

**Target cases:**
- `westlaw_100_full_text_items_for_appendectomy1_0002` — Eric Drenner v. United States of America (2021 WL 5359712)
- `westlaw_100_full_text_items_for_appendectomy1_0023` — Israel Garcia, Jr. v. The United States of America (2023 WL 4234177)

---

## Concurrency & rate limits

`--concurrency 4` is a safe default for gpt-oss-120b on a single node. Push to 8–16 if the server has headroom; watch `nvidia-smi` during Job C (longest outputs). If the server is shared, drop to 2 and run jobs serially.

---

## Resumption & idempotency

Every script is resumable:

- `run_extraction.py` appends to `output_jsonl/<job>_parsed.jsonl` and skips any `Search_ID` already present. Pass `--overwrite` to force re-run.
- `merge_results.py` always copies the input xlsx first; never modifies the source.
- `split_rtf.py` overwrites existing segment files.

A crash mid-run is recoverable with the same command.

---

## Validation checklist

Open `validation_report.md` and verify:

- [ ] `Core_Analytic_Case == YES` count is 82 or close (minor drops from Job A gate re-evaluation are expected)
- [ ] `Full_Extraction_Performed == YES` went from 46 → 82
- [ ] `Reviewer_Confidence_Score` distribution has some 4s and 5s (up from 44 × ≤3 before)
- [ ] `Year = 2026` artifacts dropped from 7 → 0
- [ ] `Extended_Extraction` non-null count went from 0 → ~80 per narrative column
- [ ] `Claim_Type` non-null on all 82 core cases
- [ ] `Plaintiff_Custodial_Status_Detail` non-null on all 82 core cases
- [ ] `Deliberate_Indifference_Standard_Applied` non-null on all 82 core cases
- [ ] UNKNOWN rates on `Plaintiff_Demographics`, `Legal_Outcome`, `Procedure_Approach`, `Disease_State_at_Presentation` dropped substantially
- [ ] Validation tags in `Reviewer_Notes` appear on zero or very few rows

If any fail, inspect `logs/<job>.log` and `output_jsonl/<job>_raw.jsonl` for problematic cases.

---

## Known edge cases & mitigations

| Edge case | Mitigation built in |
|---|---|
| Model emits markdown fences around JSON | Parser strips ` ```json ... ``` ` |
| Model invents `Year = 2025` when unknown | Prompt forbids; validator rejects `Year > today` |
| Model fabricates dollar amounts | Prompt: "only when explicit"; validator flags for review |
| Transient 500/timeout | 3 retries with exponential backoff (2s / 4s / 8s) |
| Model produces extra keys | Ignored by merger; logged in `_validation_issues` |
| Model omits required keys | Logged in `_validation_issues` + appended to `Reviewer_Notes` |
| Job D would overwrite existing Job A/B values | `merge_new_domains()` only writes 3 specific columns; never touches others |
| Segment alignment drift | Manual spot-check (see "Critical: segment alignment") — no automated defense |

---

## What this run will NOT fix

1. **Opinions genuinely lacking clinical detail** (motion-to-dismiss orders, statute-of-limitations rulings, §1983 screening orders) — the model cannot extract what isn't there. Expect ~15–20 cases to remain at confidence ≤ 3 after Job B.
2. **Duplicate detection.** Only exact case-name+citation matches are caught.
3. **Thin damages data.** Only 4 of 82 cases have explicit dollar awards. Corpus limitation, not extraction limitation.

---

## Pre-flight checklist

- [ ] gpt-oss-120b up; `curl $LLM_ENDPOINT/models` returns the model name
- [ ] `/data/westlaw_rtfs/` contains all `Westlaw - 100 full text items for appendectomy*.rtf` files
- [ ] `pip install -r requirements.txt` clean
- [ ] `python scripts/split_rtf.py ...` produced segment files
- [ ] Spot-checked 5 segments against `Case_Name` in xlsx
- [ ] Ran Job A first as smoke test; reviewed `output_jsonl/A_parsed.jsonl`
- [ ] Ran Jobs B, C, D
- [ ] Merge performed on a fresh copy of the xlsx
- [ ] `validation_report.md` reviewed
- [ ] Original `AppendectomyMaster.xlsx` archived untouched; analysis proceeds against `AppendectomyMaster_updated.xlsx`

---

## Contact points in the code

- Prompt tuning → `config/prompts/system_pass2.md`, `system_extended.md`, `system_new_domains_only.md`
- Schema / vocabulary changes → `config/allowed_values.json` (also update validators in `scripts/run_extraction.py`)
- Different LLM server → change `LLM_ENDPOINT`
- Different model → change `LLM_MODEL`
- Add cases post-hoc → append to appropriate manifest CSV and re-run
