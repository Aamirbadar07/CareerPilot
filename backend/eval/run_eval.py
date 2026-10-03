"""Evaluation for docs/evaluation.md. Run from backend/:

    uv run python -m eval.run_eval            # code-guard section only, no API calls
    uv run python -m eval.run_eval --live     # everything; calls the model and costs money

Three questions:
  1. Fabrication catch rate on deliberately poisoned resumes, per layer (code guard, validator).
  2. Fit-band agreement between the scorer and hand labels.
  3. Latency and token cost of the calls made.
"""

import argparse
import copy
import json
import statistics
import time
from pathlib import Path

from app import sample
from app.agents.fit_scorer.agent import score_job
from app.agents.job_discovery.schema import Job
from app.agents.resume_tailor.agent import fabrications, validate
from app.agents.resume_tailor.schema import TailoredResume
from app.core.config import settings
from app.core.llm import LLM, LLMError

HERE = Path(__file__).parent
LUMEN = "https://example.com/sample-jobs/lumen-forge-genai-developer"
# USD per million tokens (input, output). Update when the model or its price changes.
PRICES = {
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-opus-5-5": (4.0, 20.0),
}


def poisoned_cases() -> list[tuple[dict, TailoredResume]]:
    clean = sample.load("tailored.json")[LUMEN]["resume"]
    cases = []
    for case in json.loads((HERE / "poisoned.json").read_text(encoding="utf-8"))["cases"]:
        data = copy.deepcopy(clean)
        if case["path"]:
            target = data
            for key in case["path"][:-1]:
                target = target[key]
            target[case["path"][-1]] = case["value"]
        cases.append((case, TailoredResume(**data)))
    return cases


def code_guard(profile) -> None:
    print("\n1a. Code guard on poisoned resumes (deterministic, no model)")
    caught = {"code": [0, 0], "semantic": [0, 0], "clean": [0, 0]}
    for case, resume in poisoned_cases():
        flagged = bool(fabrications(profile, resume))
        caught[case["layer"]][0] += flagged
        caught[case["layer"]][1] += 1
        print(f"   {'CAUGHT' if flagged else 'passed':6}  [{case['layer']:8}] {case['name']}")
    print(f"   code-layer poison caught:     {caught['code'][0]}/{caught['code'][1]}")
    print(
        f"   semantic poison caught:       {caught['semantic'][0]}/{caught['semantic'][1]} (expected 0: these need the validator)"
    )
    print(f"   clean resumes wrongly flagged: {caught['clean'][0]}/{caught['clean'][1]}")


def validator(llm: LLM, profile, timings: list[float]) -> None:
    print("\n1b. Validator model on poisoned resumes that pass the code guard")
    caught = total = false_alarms = clean_total = 0
    for case, resume in poisoned_cases():
        if case["layer"] == "code":
            continue  # never reaches the validator in the pipeline
        start = time.perf_counter()
        try:
            failed = validate(llm, profile, resume).verdict == "fail"
        except LLMError as e:
            print(f"   ERROR   {case['name']}: {e}")
            continue
        timings.append(time.perf_counter() - start)
        if case["layer"] == "clean":
            clean_total += 1
            false_alarms += failed
        else:
            total += 1
            caught += failed
        print(f"   {'FAIL' if failed else 'pass':5}   [{case['layer']:8}] {case['name']}")
    print(f"   semantic poison caught:        {caught}/{total}")
    print(f"   clean resumes wrongly failed:  {false_alarms}/{clean_total}")


def fit_agreement(llm: LLM, profile, timings: list[float]) -> None:
    print("\n2. Fit-band agreement with hand labels")
    jobs = {j["url"]: Job(**j) for j in sample.jobs()}
    labels = json.loads((HERE / "labels.json").read_text(encoding="utf-8"))["pairs"]
    agree = 0
    for pair in labels:
        if pair["profile"] != "sample":
            print(
                f"   skipped {pair['job_url']}: only the sample profile is wired into this script"
            )
            continue
        start = time.perf_counter()
        report = score_job(llm, profile, jobs[pair["job_url"]])
        timings.append(time.perf_counter() - start)
        same = report.band == pair["band"]
        agree += same
        print(
            f"   {'agree' if same else 'DIFFER':6}  hand={pair['band']:11} model={report.band:11} score={report.score:3}  {jobs[pair['job_url']].title}"
        )
    print(f"   agreement: {agree}/{len(labels)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="call the model (costs money)")
    args = parser.parse_args()
    profile = sample.profile()

    code_guard(profile)
    if not args.live:
        print("\nSections 1b, 2 and 3 need the model. Re-run with --live.")
        return

    llm = LLM()  # no cache: every call is real, so latency and cost are too
    timings: list[float] = []
    validator(llm, profile, timings)
    fit_agreement(llm, profile, timings)

    print("\n3. Latency and cost")
    if timings:
        print(
            f"   calls: {llm.usage['calls']}, median latency per agent call: {statistics.median(timings):.1f}s"
        )
    price_in, price_out = PRICES.get(settings.anthropic_model, (0.0, 0.0))
    cost = llm.usage["input_tokens"] / 1e6 * price_in + llm.usage["output_tokens"] / 1e6 * price_out
    print(
        f"   tokens: {llm.usage['input_tokens']} in, {llm.usage['output_tokens']} out on {settings.anthropic_model}"
    )
    print(
        f"   cost of this evaluation: ${cost:.2f}"
        if price_in
        else "   no price listed for this model"
    )


if __name__ == "__main__":
    main()
