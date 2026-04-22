# HANDOFF — PASTE THIS INTO A NEW CLAUDE CHAT

---

## Context & role

You are picking up an established medico-legal research project — an empirical analysis of appendectomy- and appendicitis-related medical-malpractice litigation, built from a Westlaw case corpus. The data-extraction phase is complete. Your job is the analytical layer: build the final tidy dataset, produce publication-ready tables and figures, perform the stratified statistical analyses the project plan calls for, and draft the Methods/Results/Discussion sections.

**Repository:** `https://github.com/ry86pkqf74-rgb/Appendectomy-Legal`
**Branch:** `main` (latest commit on extraction: `51b470e`)
**Primary data file:** `AppendectomyMaster_updated.xlsx` (post-RUNPROD, produced by `scripts/merge_results.py`)
**Pre-run snapshot for comparison:** `AppendectomyMaster_PRE_RUNPROD_20260422.xlsx`

Note: the GitHub repo currently contains the extraction-phase artifacts under `extraction_2/` (master Excel, validation and spot-check reports, all four JSONL outputs, pipeline scripts, manifests, prompts, allowed-values config). Other context files — `build_tidy.py`, `codebook_derived_columns.md`, prior pro-review analysis outputs, and the Elicit literature report — are attached to this chat rather than in the repo.

Clone the repo, read `README.md` first, then `LLM_PASSES_RUNBOOK.md`, then `validation_report.md`. That will give you the state of play.

## Project one-paragraph summary

Corpus: 1,225 Westlaw federal-court opinions related to appendectomy/appendicitis malpractice, narrowed through a three-field screening gate (`Is_Malpractice_Case`, `Appendicitis_or_Appendectomy_Index_Episode`, `Has_Clinically_Meaningful_Harm` — all must be YES) to 82 core-analytic cases. Each case was LLM-extracted into ~85 structured clinical/legal fields plus 11 narrative fields. Extraction was staged in four jobs (A: pass-2 on 36 first-pass-only cases; B: re-extraction on 44 low-confidence cases; C: extended narrative for all 82; D: targeted 3-field classification on 2 high-confidence cases). All four jobs ran on RUNPROD against gpt-oss-120b and are now complete. Merged output is `AppendectomyMaster_updated.xlsx`.

## Non-negotiable rules (these govern every analytic decision)

1. **Read_Me strict compliance.** The workbook's `Read_Me` sheet says: "If the source does not clearly support a value, leave the field as UNKNOWN (categorical/boolean) or blank (text/numeric)." You never impute, never force, never guess. UNKNOWN is a legitimate and expected value.
2. **YES / NO / UNKNOWN** for clinical boolean fields.
3. **YES / NO** for allegation-style fields (default NO when reviewed and not alleged; UNKNOWN when cannot be determined).
4. **Money fields** are populated only when an explicit dollar figure appears in the opinion.
5. **Never over-claim from sparse data.** Only 4 of 82 cases carry explicit damages awards. Do not run regressions on n=4. The project plan defers payout modeling until more data are available.
6. **Respect the corpus's selection bias.** This is a federal-court Westlaw subset heavily weighted toward FTCA and §1983 prisoner cases. Do not generalize findings to the state-court malpractice landscape without explicit caveat.

## The three new legal-type fields added in this run (critical for your analyses)

These were added to the main schema specifically to unlock the FTCA-vs-§1983-vs-state-law split that drives the key analytical bifurcation. All three are populated on all 82 core cases.

- `Claim_Type` — `FTCA_malpractice` | `section_1983_civil_rights` | `state_law_malpractice` | `EMTALA` | `military_Feres` | `other` | `unknown`
- `Plaintiff_Custodial_Status_Detail` — `state_prisoner` | `federal_prisoner` | `pretrial_detainee` | `immigration_detainee` | `probationer_parolee` | `not_custodial` | `unknown`
- `Deliberate_Indifference_Standard_Applied` — YES / NO / UNKNOWN

These should stratify virtually every outcome analysis. In particular: §1983 / deliberate-indifference cases operate under a subjective-knowledge-of-risk standard with a much higher plaintiff bar than ordinary FTCA or state-law negligence claims — treating them as a single pool would conflate two legally distinct populations.

## Key historical decisions — do NOT re-litigate these

1. **Derived-column coding rules are locked.** The canonical `build_tidy.py` is in the repo. It synthesizes the best of three prior reviews:
   - Uses ChatGPT DA's broader source fields for `inmate_case` (scans Case_Name, Facility_Type, First_Pass_Rationale, Defense_Strategy_Summary, not just Plaintiff_Demographics)
   - Uses ChatGPT DA's rule that `Alleged_Breach_Categories` containing a named list without a given breach-term is affirmative NO evidence for that breach
   - Uses ChatGPT DA's rule that `Adaptation_Type == "none"` → `adaptation_performed = NO`
   - Uses ChatGPT DA's broader difficulty signal set (adds `Abscess_or_Phlegmon`, `Bowel_Resection_or_Ileocecectomy` to difficulty composite)
   - Uses ChatGPT DA's fallback: `Appellate_Status` drives `plaintiff_favorable` when `Legal_Outcome` is Unknown/Mixed
   - Preserves Claude's `Need_for_Reoperation == YES` as an escalator in `high_severity_injury`
   - Preserves a separate `resolution_involved_payment` column to decouple Settlement treatment from `plaintiff_favorable`
   - Includes both strict and permissive `plaintiff_age_group` variants (strict = numeric age only; permissive = also infers "adult" from role keywords like "prisoner", "seaman", "Marine")
2. `Claim_Type`, `Plaintiff_Custodial_Status_Detail`, `Deliberate_Indifference_Standard_Applied` are authoritative — all three came from the gpt-oss-120b extraction run and should be trusted barring obvious validation issues flagged in `Reviewer_Notes`.
3. Cases that dropped from Core after Job A's full-opinion re-screening should stay dropped unless you find a specific merge bug. Expected: 2–5 such cases.
4. Cases still at Reviewer_Confidence_Score ≤ 3 after Job B are genuinely information-sparse opinions (motion-to-dismiss orders, statute-of-limitations rulings, §1983 screening orders), not LLM failures. Include them in descriptives but flag them as low-confidence in any sensitivity analysis.

## What the repo contains (read these first)

- `README.md` — top-level repo orientation
- `LLM_PASSES_RUNBOOK.md` — how the extraction was executed (methods-section material)
- `validation_report.md` — before/after diff from the RUNPROD run; lists UNKNOWN-rate deltas, flipped cases, validation issues
- `run_llm_passes/` (or `extraction_2/`) — the extraction package (prompts, manifests, scripts) — reference for methods documentation
- `build_tidy.py` — canonical script for building the 82-row analytic dataset from `AppendectomyMaster_updated.xlsx`. Run this first. Output: `appendectomy_core_analytic_tidy.csv` (82 rows × ~160 columns).
- `codebook_derived_columns.md` — tabular definitions of every derived column and its creation rule
- `analysis/` — Pro-review analytical layer (21 summary tables + 4 figures + descriptive-findings document) based on the pre-run data; needs to be re-run against updated data
- `elicit_report.pdf` — literature synthesis on appendicitis malpractice (Serban 2021, Chaudhary 2025, Glauser 2001, Brown-Forestiere 2020, Saber 2011, Lefebvre 2021, Cassaro 2015, Cobb 2015, Karki 2021). Comparator for Discussion section.

## Your tasks (prioritized)

### Phase 1 — Rebuild the tidy dataset and validate the run (first hour)

1. Pull the repo. Verify `AppendectomyMaster_updated.xlsx` and the pre-run archive snapshot are both present.
2. Run `build_tidy.py` against `AppendectomyMaster_updated.xlsx`. Produce the updated `appendectomy_core_analytic_tidy.csv`.
3. Run a diagnostic comparison vs. the pre-run tidy (if archived): UNKNOWN-rate deltas per column, cases that flipped values, new explicit damages figures, Core-set membership changes.
4. Confirm all 82 core cases have non-null `Claim_Type`, `Plaintiff_Custodial_Status_Detail`, `Deliberate_Indifference_Standard_Applied`. If any are null, investigate the merge logic in `scripts/merge_results.py`.
5. Confirm `Reviewer_Confidence_Score` distribution now has 4s and 5s (before: 44 × ≤3, 2 × =4, 0 × =5). Report the new distribution.
6. Confirm `Year = 2026` artifacts are eliminated (was 7 pre-run, should be near 0 post-run — the true year comes from the Citation).

**Deliverable:** a short `post_run_diagnostic.md` summarizing what changed and flagging anything unexpected.

### Phase 2 — Rebuild the analytical layer (second hour)

Re-run the Pro-style analysis on the updated tidy dataset. Produce:

- Tables for core high-level summary, legal outcome, outcome by case type, breach counts, breach by outcome, recognition timing, demographics, damages/payout summary, key field quality, manual-review priority
- Tables stratified on `Claim_Type` (FTCA_malpractice vs section_1983_civil_rights vs state_law_malpractice vs other): outcome distribution, breach distribution, severity distribution, demographics, damages where available
- Tables stratified on `Deliberate_Indifference_Standard_Applied` (YES vs NO): outcome distribution especially
- Tables stratified on `Plaintiff_Custodial_Status_Detail` where cell sizes permit
- Figures: top breach categories, case-type distribution, outcome by case type, Claim_Type × outcome, Claim_Type × severity, outcome by procedural_stage

Keep the "82 core cases" and "fully-extracted subset" framing separate and explicit. Outcome analyses should use the fully-extracted subset; descriptive demographics and claim-type distribution can use all 82.

### Phase 3 — Statistical modeling (second session onward)

Constraints: n = 82 core, fewer in any stratified cell. Default to exact/penalized methods. Pro-review recommended:

1. Penalized (Firth) logistic regression for `plaintiff_favorable ~ breach_delayed_diagnosis + breach_surgical_technique_error + breach_failure_to_remove_appendix + perforated_or_gangrenous + need_for_reoperation + long_term_morbidity + claim_type + plaintiff_custodial_status_detail + procedural_stage`. Use Firth's bias-reduced logistic (R `logistf` or Python `firthlogist`) because you will have quasi-complete separation with this n.
2. Fisher's exact tests on key 2×2 contingencies (e.g., breach × outcome, Claim_Type × plaintiff-favorable).
3. Sensitivity analyses: run every model twice — once on all 82 with Mixed/Settlement treated as UNKNOWN for outcome, once on the directional subset only. Report both.
4. Stratified models — fit separate models for FTCA-style and §1983-style claims; do not pool unless a formal interaction test confirms homogeneity.
5. Explicitly defer any payout/damages regression until more dollar figures are available. Report descriptive payout statistics only.

Do not overfit. Pre-register the variable list above before looking at the outcome. Do not stepwise-select from the full column space.

### Phase 4 — Manuscript drafting

Draft in this order, one section at a time, checking with me between sections:

1. **Methods** — corpus construction (Westlaw search → segmentation → screening gate → pass-2 extraction → four-job RUNPROD run). Full methodological transparency including model, prompt versions, validator enforcement, and the dated pre-run snapshot as provenance anchor. The runbook in the repo is the raw material.
2. **Results** — start with CONSORT-style corpus flow (1,225 → 82 → 46/80 depending on analysis), then descriptive tables, then stratified descriptive tables on Claim_Type, then inferential results with confidence intervals and p-values.
3. **Discussion** — convergence and divergence from the Elicit literature synthesis. Pro's pre-run findings already laid out the scaffolding: delayed diagnosis dominates allegations in this corpus (convergent with Elicit); plaintiff-favorable rate is ~28–45% depending on Mixed treatment (below Elicit's ~50% estimate, likely opinion-selection bias); operative-complication cases are less frequent but higher plaintiff-favorable and higher payout (divergent from Elicit's "less frequent but high severity" framing — actually also higher-win); the federal/custodial/male-dominant corpus profile diverges strongly from Elicit's pediatric/elderly/reproductive-age-women risk populations. Expand on all of these with updated numbers.
4. **Limitations** — opinion selection bias, small n, information-sparse opinions, no state-court verdicts, no confidential settlements, LLM extraction is new methodology (cite the run + validation report).

## Deliverables for this session

At minimum:

- `post_run_diagnostic.md` — what changed between pre-run and post-run tidy
- `appendectomy_core_analytic_tidy.csv` — updated 82-case tidy
- `analysis/tables/` — refreshed summary tables (CSVs)
- `analysis/figures/` — refreshed figures (PNGs)
- `analysis/findings_updated.md` — refreshed descriptive findings document incorporating the new `Claim_Type` and custodial splits
- An update to the top-level `README.md` documenting what this session produced

Commit these in logical units (diagnostic, tidy, tables, figures, findings) with clear commit messages. Don't squash the history — the git log is part of the methods-section provenance trail.

## Ground rules for working with me

- **Show intermediate results.** Don't run 30 analyses silently and drop a 50-table report. Produce the diagnostic first, show me UNKNOWN-rate deltas, and let me react before proceeding.
- **Flag anything that looks off.** If post-run Core count is 75 instead of 82, stop and tell me — do not paper over it.
- **Prefer shorter, more focused conversations.** Finish Phase 1 completely, deliver it, then start a new task for Phase 2.
- **When you cite a number in prose, also cite which table or cell in the tidy CSV it came from.**
- **If any derived-column rule in `build_tidy.py` seems wrong to you, surface the disagreement with a concrete example — do not silently change the rule.**
- **Respect the Read_Me rule.** If you find yourself typing "we'll assume..." stop. The answer is UNKNOWN.

## First turn

Start by cloning the repo, reading the three briefing files (`README.md`, `LLM_PASSES_RUNBOOK.md`, `validation_report.md`), and the `codebook_derived_columns.md`. Then report back with:

1. Repo contents (high-level `ls -la` / tree)
2. Confirmation that `AppendectomyMaster_updated.xlsx` is present
3. Your read of the validation report — any red flags worth discussing before Phase 1
4. Your proposed sequencing for Phase 1

Do not run `build_tidy.py` or touch any analysis until we've confirmed there are no validation red flags in the run output.

---

**END OF HANDOFF PROMPT**
