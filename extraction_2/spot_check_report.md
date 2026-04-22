# Pre-token segment alignment spot-check — Appendectomy LLM Passes

**Checked by:** Claude
**Date:** 2026-04-21
**Inputs:** `Appendectomy/*.rtf` (13 files, 12 actually referenced by manifests) + `AppendectomyMaster.xlsx`
**Segmenter used:** `scripts/split_rtf.py` from the package (original `appendectomy_extractor.py` is not on disk in this environment).
**Bottom line:** ✅ Segment → Case_Name alignment holds across all 6 probes. Safe to proceed to token commit **once an LLM endpoint is available** (see limitations below).

---

## Segment counts per RTF

Every 100-item RTF splits into 101 chunks; index `0100` is a copyright-only trailer ("© 2026 Thomson Reuters. No claim…"). The 25-item RTF splits into 26 chunks with the same pattern. All manifest Search_IDs fall within `0000..N-1`, so the trailer is harmless — just don't feed it to the LLM. No RTF came out short.

| File | Segments | Usable case indices | Trailer |
|---|---:|---|---|
| `...appendectomy.rtf` through `...appendectomy11.rtf` (12 files) | 101 each | 0000–0099 | 0100 |
| `...25 full text items for appendectomy12.rtf` | 26 | 0000–0024 | 0025 |

(`appendectomy11.rtf` and `appendectomy12.rtf` appear not to contribute any core cases — the combined manifest has 0 rows from those stubs.)

Cross-manifest dedupe: A (36) + B (44) + D (2) = **82 unique Search_IDs**, matching the runbook's coverage claim. Job C lists all 82 separately on the Extended_Extraction sheet.

## Spot-check: 6 Search_IDs vs Case_Name

Probes intentionally span (a) different RTFs, (b) segment index 0 and mid-file indices, and (c) both pass-2-target rows and Job D rows.

| # | Search_ID | Xlsx Case_Name | Opening of segment (first ~250 chars, whitespace collapsed) | Match |
|---:|---|---|---|:--:|
| 1 | `...appendectomy_0000` | Kandie R. Wright v. David H. Smith, M.D. … | `641 F.Supp.2d 536 … W.D. Virginia … Kandie R. WRIGHT, Plaintiff v. David H. SMITH, M.D. and Abingdon Surgical Associates, P.C. … June 30, 2009` | ✅ |
| 2 | `...appendectomy_0010` | Ronald W. YOUNG v. Frederick C. FISHBACK | `\|© 2026 Thomson Reuters…\| 262 F.2d 469 … D.C. Cir. … Ronald W. YOUNG, Appellant, v. Frederick C. FISHBACK … Argued Oct. 17, 1958` | ✅ |
| 3 | `...appendectomy1_0002` | Eric Drenner v. United States of America | `\|© 2026 Thomson Reuters…\| 2021 WL 5359712 … N.D. Oklahoma … Eric DRENNER, Plaintiff, v. UNITED STATES of America … Signed 11/17/2021` | ✅ |
| 4 | `...appendectomy3_0023` | UNITED STATES of America v. Richard MELGOZA, Joshua Garcia | `\|© 2026 Thomson Reuters…\| 248 F.Supp.2d 691 … S.D. Ohio … UNITED STATES of America, Plaintiff, v. Richard MELGOZA, Joshua Garcia, Defendants … Jan. 21, 2003` | ✅ |
| 5 | `...appendectomy10_0055` | Pegram v. Herdrich | `\|© 2026 Thomson Reuters…\| 120 S.Ct. 2143 … Supreme Court … Lori PEGRAM, et al., Petitioners, v. Cynthia HERDRICH … Decided June 12, 2000` | ✅ |
| 6 | `...appendectomy1_0023` (Job D) | Israel Garcia, Jr. v. The United States of America | `\|© 2026 Thomson Reuters…\| 2023 WL 4234177 … D. Oregon … Israel GARCIA, Jr., Plaintiff, v. The UNITED STATES of America … Signed June 27, 2023` | ✅ |

6/6 match. Citations and decision dates also line up exactly with the xlsx `Citation` and, where populated correctly, `Year`. In probes 2 and 4 the xlsx `Year=2026` is a known pass-1 artifact flagged in the runbook's success criteria ("`Year = 2026` artifacts: 7 → 0") — the segment shows the true year (1958 / 2003), so these are legitimate Job A/B targets and the misalignment is in the xlsx, not the segmenter.

## Two segmenter quirks worth flagging (both harmless for this run)

1. **Trailing copyright prefix on segments 0001+.** Because we split on `End of Document` (which comes at the *end* of each case, followed by the copyright line), every segment after index 0 starts with `|© 2026 Thomson Reuters. No claim…|` then the real case text. Not a case-boundary problem — the real opinion follows immediately — but worth knowing for prompt design. The pass-2 prompts should already be robust to it since RTFs in the original pipeline presumably had the same artifact.
2. **Extra trailer at index N (100 / 25).** Already noted above. Nothing in the manifest references it, so nothing will touch it.

Neither changes the Search_ID ↔ case mapping.

## Recommendation

Alignment verified — OK to commit tokens on Jobs A → B → C → D once the LLM endpoint is up.
