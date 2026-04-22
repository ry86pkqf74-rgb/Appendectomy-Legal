#!/usr/bin/env python3
"""
run_extraction.py
=================

Driver for three LLM extraction jobs against gpt-oss-120b served over an
OpenAI-compatible HTTP endpoint (vLLM / sglang / llama.cpp-server / TGI).

Jobs
----
  A : Pass-2 Case_Master extraction for first-pass-only core cases   (n=36)
  B : Pass-2 Case_Master RE-extraction for low-confidence cases       (n=44)
  C : Extended_Extraction narrative pass for all core cases           (n=82)

A and B share the same prompt + schema (pass2). C uses its own prompt + schema.

Outputs
-------
  output_jsonl/<job>_raw.jsonl       — one line per case, raw model response
  output_jsonl/<job>_parsed.jsonl    — validated & normalized JSON
  logs/<job>.log                     — per-case status, latencies, retries

The script is RESUMABLE — it skips any Search_ID already present in the
parsed JSONL for that job. To force re-run, delete the file or pass --overwrite.

Usage examples
--------------
    # Single job
    python scripts/run_extraction.py --job A \\
        --segments-dir /data/segments \\
        --endpoint http://localhost:8000/v1 \\
        --model gpt-oss-120b

    # All three jobs sequentially
    for job in A B C; do
        python scripts/run_extraction.py --job $job \\
            --segments-dir /data/segments \\
            --endpoint http://localhost:8000/v1 \\
            --model gpt-oss-120b
    done

    # With a local api key (vLLM / sglang usually accept any string)
    python scripts/run_extraction.py --job A ... --api-key dummy

Env vars
--------
  LLM_ENDPOINT, LLM_MODEL, LLM_API_KEY — override --endpoint / --model / --api-key
"""

import argparse
import concurrent.futures as cf
import csv
import datetime as dt
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

try:
    import requests
except ImportError:
    print("pip install requests", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATHS = {
    "A": ROOT / "manifests" / "manifest_job_A_firstpass_pass2.csv",
    "B": ROOT / "manifests" / "manifest_job_B_lowconfidence_rerun.csv",
    "C": ROOT / "manifests" / "manifest_job_C_extended_extraction.csv",
    "D": ROOT / "manifests" / "manifest_job_D_new_domains_only.csv",
}
PROMPT_PATHS = {
    "A": ROOT / "config" / "prompts" / "system_pass2.md",
    "B": ROOT / "config" / "prompts" / "system_pass2.md",
    "C": ROOT / "config" / "prompts" / "system_extended.md",
    "D": ROOT / "config" / "prompts" / "system_new_domains_only.md",
}
ALLOWED = json.loads((ROOT / "config" / "allowed_values.json").read_text())


# --------------------------------------------------------------------------- #
# Expected fields per job (for validation)                                    #
# --------------------------------------------------------------------------- #
PASS2_FIELDS = (
    [
        "Case_Name", "Citation", "Year", "Court", "Jurisdiction",
        "Legal_Case_Type", "Procedural_Posture", "Legal_Outcome",
        "Damages_Award", "Settlement_Amount", "Economic_Damages",
        "NonEconomic_Damages", "Punitive_Damages", "Time_to_Resolution_Years",
        "Appellate_Status",
        "Claim_Type", "Plaintiff_Custodial_Status_Detail",
        "Expert_Testimony_Mentioned", "Expert_Testimony_Type",
        "Expert_Criticism_Text", "Defense_Strategy_Summary",
        "Alleged_Breach_Categories",
        "Index_Procedure_Type", "Procedure_Approach",
        "Disease_State_at_Presentation",
        "Injury_Type_Primary", "Injury_Type_Secondary", "Injury_Severity",
        "Recognition_Timing", "Recognition_Timing_Detail",
        "Time_From_Presentation_To_Diagnosis_Hours",
        "Time_From_Surgery_To_Recognition_Days", "Delay_Days",
        "Operative_Text_Snippet", "Difficulty_Text_Snippet",
        "Recognition_Text_Snippet",
        "Difficulty_Assessability", "Difficulty_Documented",
        "Adaptation_Type",
        "Plaintiff_Demographics", "Surgeon_Characteristics", "Facility_Type",
        "Preventability_Assessment",
        "Reviewer_Confidence_Score", "Reviewer_Notes",
    ]
    + ALLOWED["yes_no_unknown_fields_case_master"]
    + ALLOWED["yes_no_fields_case_master"]
)
EXTENDED_FIELDS = ALLOWED["extended_extraction_fields"]
NEW_DOMAINS_FIELDS = [
    "Claim_Type",
    "Plaintiff_Custodial_Status_Detail",
    "Deliberate_Indifference_Standard_Applied",
]


# --------------------------------------------------------------------------- #
@dataclass
class Case:
    search_id: str
    file_name: str
    text: str            # full plain-text segment
    case_name_hint: str | None = None
    year_hint: int | None = None


# --------------------------------------------------------------------------- #
def load_cases(job: str, segments_dir: Path) -> list[Case]:
    manifest = MANIFEST_PATHS[job]
    cases = []
    missing = []
    with open(manifest, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            sid = row["Search_ID"]
            seg_path = segments_dir / f"{sid}.txt"
            if not seg_path.exists():
                missing.append(sid)
                continue
            cases.append(Case(
                search_id=sid,
                file_name=row.get("File_Name", ""),
                text=seg_path.read_text(encoding="utf-8"),
                case_name_hint=row.get("Case_Name") or None,
                year_hint=int(row["Year"]) if row.get("Year") and str(row["Year"]).isdigit() else None,
            ))
    if missing:
        print(f"\n⚠  {len(missing)} segments missing on disk for job {job}. "
              f"Run scripts/split_rtf.py first.  First 5: {missing[:5]}",
              file=sys.stderr)
    return cases


def already_done(parsed_path: Path) -> set[str]:
    done = set()
    if not parsed_path.exists():
        return done
    with open(parsed_path, encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
                done.add(rec["Search_ID"])
            except Exception:
                continue
    return done


# --------------------------------------------------------------------------- #
def build_messages(job: str, case: Case) -> list[dict]:
    system_prompt = PROMPT_PATHS[job].read_text(encoding="utf-8")
    # Hints in the user message help the model self-correct metadata
    # extraction (particularly the Year=2026 default artifact we saw before).
    hints_block = ""
    if case.case_name_hint and case.case_name_hint != "nan":
        hints_block += f"\n[Case-name hint from prior pass, for your reference only — verify against the opinion text; do not blindly trust]: {case.case_name_hint}\n"

    user_prompt = f"""Search_ID: {case.search_id}
Source file: {case.file_name}
{hints_block}
--- BEGIN OPINION TEXT ---
{case.text}
--- END OPINION TEXT ---

Extract the required JSON object according to the system instructions. Output JSON ONLY."""
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def call_llm(messages, endpoint, model, api_key, temperature=0.1, max_tokens=8192, timeout=300):
    """POST to an OpenAI-compatible /v1/chat/completions endpoint."""
    url = endpoint.rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},  # supported by vLLM ≥0.6 / sglang
        # gpt-oss is a reasoning model; "low" keeps CoT brief so max_tokens
        # isn't eaten before the JSON emits. If content still comes back empty,
        # bump to "medium".
        "reasoning_effort": "low",
    }
    t0 = time.time()
    r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=timeout)
    elapsed = time.time() - t0
    r.raise_for_status()
    data = r.json()
    content = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    return content, elapsed, usage


# --------------------------------------------------------------------------- #
def parse_and_validate(job: str, raw_content: str, case: Case) -> dict:
    """Strip code fences, json.loads, normalize, validate against vocab.
    Returns the validated dict including Search_ID + validation issues list.
    Raises on unrecoverable JSON parse failure."""
    txt = raw_content.strip()
    # Strip common fence patterns
    if txt.startswith("```"):
        txt = txt.split("```", 2)
        # txt is now ["", "json\n{...}", ""] or similar
        if len(txt) >= 2:
            inner = txt[1]
            if inner.startswith("json"):
                inner = inner[4:].lstrip()
            txt = inner.rstrip("`").strip()
        else:
            txt = raw_content
    obj = json.loads(txt)

    issues = []
    if job in ("A", "B"):
        expected = PASS2_FIELDS
    elif job == "C":
        expected = EXTENDED_FIELDS
    else:  # D
        expected = NEW_DOMAINS_FIELDS
    missing = [f for f in expected if f not in obj]
    extra = [k for k in obj.keys() if k not in expected]
    if missing:
        issues.append(f"missing_fields={missing}")
    if extra:
        issues.append(f"unexpected_fields={extra}")

    if job in ("A", "B"):
        _validate_pass2_values(obj, issues)
    elif job == "C":
        _validate_extended_values(obj, issues)
    else:  # D
        _validate_new_domains_values(obj, issues)

    obj["Search_ID"] = case.search_id
    obj["_validation_issues"] = issues
    return obj


def _check_enum(obj, field, allowed, issues, allow_null=True):
    v = obj.get(field)
    if v is None:
        if not allow_null:
            issues.append(f"{field}: null not allowed")
        return
    if v not in allowed:
        issues.append(f"{field}: '{v}' not in {allowed}")


def _check_yes_no_unknown(obj, field, issues):
    _check_enum(obj, field, ALLOWED["yes_no_unknown"], issues)


def _check_yes_no(obj, field, issues):
    _check_enum(obj, field, ALLOWED["yes_no"], issues)


def _validate_pass2_values(obj: dict, issues: list) -> None:
    _check_enum(obj, "Jurisdiction", ALLOWED["Jurisdiction"], issues)
    _check_enum(obj, "Legal_Outcome", ALLOWED["Legal_Outcome"], issues)
    _check_enum(obj, "Appellate_Status", ALLOWED["Appellate_Status"], issues)
    _check_enum(obj, "Expert_Testimony_Type", ALLOWED["Expert_Testimony_Type"], issues)
    _check_enum(obj, "Index_Procedure_Type", ALLOWED["Index_Procedure_Type"], issues)
    _check_enum(obj, "Procedure_Approach", ALLOWED["Procedure_Approach"], issues)
    _check_enum(obj, "Disease_State_at_Presentation",
                ALLOWED["Disease_State_at_Presentation"], issues)
    _check_enum(obj, "Injury_Type_Primary", ALLOWED["Injury_Type_Primary"], issues)
    _check_enum(obj, "Injury_Severity", ALLOWED["Injury_Severity"], issues)
    _check_enum(obj, "Recognition_Timing", ALLOWED["Recognition_Timing"], issues)
    _check_enum(obj, "Difficulty_Assessability", ALLOWED["Difficulty_Assessability"], issues)
    _check_enum(obj, "Difficulty_Documented", ALLOWED["Difficulty_Documented"], issues)
    _check_enum(obj, "Adaptation_Type", ALLOWED["Adaptation_Type"], issues)
    _check_enum(obj, "Claim_Type", ALLOWED["Claim_Type"], issues)
    _check_enum(obj, "Plaintiff_Custodial_Status_Detail",
                ALLOWED["Plaintiff_Custodial_Status_Detail"], issues)

    for f in ALLOWED["yes_no_unknown_fields_case_master"]:
        _check_yes_no_unknown(obj, f, issues)
    for f in ALLOWED["yes_no_fields_case_master"]:
        _check_yes_no(obj, f, issues)

    # Reviewer_Confidence_Score ∈ 1..5
    rcs = obj.get("Reviewer_Confidence_Score")
    if rcs is not None and rcs not in (1, 2, 3, 4, 5):
        issues.append(f"Reviewer_Confidence_Score: '{rcs}' not in [1..5]")

    # Snippet char limits
    lim = ALLOWED["snippet_char_limit"]
    for f in ("Operative_Text_Snippet", "Difficulty_Text_Snippet", "Recognition_Text_Snippet"):
        v = obj.get(f)
        if isinstance(v, str) and len(v) > lim + 20:
            issues.append(f"{f}: length {len(v)} > {lim}")

    # Year sanity check — reject the 2026 default artifact
    y = obj.get("Year")
    if y is not None:
        try:
            yi = int(y)
            if yi < 1900 or yi > dt.date.today().year:
                issues.append(f"Year: {yi} out of range 1900..today")
        except Exception:
            issues.append(f"Year: '{y}' not parseable as int")


def _validate_new_domains_values(obj: dict, issues: list) -> None:
    """Validator for Job D: only the 3 legal-type fields."""
    _check_enum(obj, "Claim_Type", ALLOWED["Claim_Type"], issues, allow_null=False)
    _check_enum(obj, "Plaintiff_Custodial_Status_Detail",
                ALLOWED["Plaintiff_Custodial_Status_Detail"], issues, allow_null=False)
    _check_yes_no_unknown(obj, "Deliberate_Indifference_Standard_Applied", issues)


def _validate_extended_values(obj: dict, issues: list) -> None:
    # JSON-string fields — verify they parse as JSON if non-null
    for f in ("Claim_Support_Matrix_JSON", "Evidence_Quotes_JSON"):
        v = obj.get(f)
        if v is None:
            continue
        if not isinstance(v, str):
            issues.append(f"{f}: must be a string containing JSON")
            continue
        try:
            parsed = json.loads(v)
            if not isinstance(parsed, list):
                issues.append(f"{f}: parsed JSON is not a list")
        except Exception as e:
            issues.append(f"{f}: JSON parse error: {e}")


# --------------------------------------------------------------------------- #
def process_one(case, job, endpoint, model, api_key, raw_fh, parsed_fh, log_fh, lock):
    attempts = 0
    last_err = ""
    while attempts < 3:
        attempts += 1
        try:
            msgs = build_messages(job, case)
            raw, elapsed, usage = call_llm(msgs, endpoint, model, api_key)
            with lock:
                raw_fh.write(json.dumps({
                    "Search_ID": case.search_id,
                    "job": job, "attempt": attempts,
                    "raw": raw, "elapsed_s": elapsed, "usage": usage,
                }) + "\n")
                raw_fh.flush()

            parsed = parse_and_validate(job, raw, case)
            with lock:
                parsed_fh.write(json.dumps(parsed, ensure_ascii=False) + "\n")
                parsed_fh.flush()
                log_fh.write(f"{dt.datetime.now().isoformat()}  OK  "
                             f"{case.search_id}  {elapsed:.1f}s  "
                             f"issues={len(parsed.get('_validation_issues', []))}\n")
                log_fh.flush()
            return True
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            time.sleep(2 ** attempts)

    with lock:
        log_fh.write(f"{dt.datetime.now().isoformat()}  FAIL {case.search_id}  {last_err}\n")
        log_fh.flush()
    return False


# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True, choices=["A", "B", "C", "D"])
    ap.add_argument("--segments-dir", type=Path, required=True)
    ap.add_argument("--endpoint", default=os.environ.get("LLM_ENDPOINT", "http://localhost:8000/v1"))
    ap.add_argument("--model", default=os.environ.get("LLM_MODEL", "gpt-oss-120b"))
    ap.add_argument("--api-key", default=os.environ.get("LLM_API_KEY", ""))
    ap.add_argument("--concurrency", type=int, default=4,
                    help="Parallel requests (keep modest for 120B on a single node)")
    ap.add_argument("--overwrite", action="store_true",
                    help="Re-run cases already in parsed JSONL")
    args = ap.parse_args()

    raw_path = ROOT / "output_jsonl" / f"{args.job}_raw.jsonl"
    parsed_path = ROOT / "output_jsonl" / f"{args.job}_parsed.jsonl"
    log_path = ROOT / "logs" / f"{args.job}.log"
    for p in (raw_path, parsed_path, log_path):
        p.parent.mkdir(parents=True, exist_ok=True)

    cases = load_cases(args.job, args.segments_dir)
    done = set() if args.overwrite else already_done(parsed_path)
    todo = [c for c in cases if c.search_id not in done]

    print(f"Job {args.job}: {len(cases)} total, {len(done)} already done, {len(todo)} to process")
    if not todo:
        print("Nothing to do.")
        return 0

    mode = "a" if not args.overwrite else "w"
    lock = Lock()
    t0 = time.time()
    ok = 0
    with open(raw_path, mode, encoding="utf-8") as raw_fh, \
         open(parsed_path, mode, encoding="utf-8") as parsed_fh, \
         open(log_path, mode, encoding="utf-8") as log_fh:
        with cf.ThreadPoolExecutor(max_workers=args.concurrency) as ex:
            futs = [ex.submit(process_one, c, args.job, args.endpoint,
                              args.model, args.api_key,
                              raw_fh, parsed_fh, log_fh, lock)
                    for c in todo]
            for i, fut in enumerate(cf.as_completed(futs), 1):
                if fut.result():
                    ok += 1
                if i % 5 == 0 or i == len(futs):
                    print(f"  [{i}/{len(futs)}] ok={ok} elapsed={time.time()-t0:.0f}s")

    print(f"\nJob {args.job} done. OK={ok}/{len(todo)}.")
    print(f"  raw:     {raw_path}")
    print(f"  parsed:  {parsed_path}")
    print(f"  log:     {log_path}")
    return 0 if ok == len(todo) else 3


if __name__ == "__main__":
    raise SystemExit(main())
