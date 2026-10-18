"""Compare models on a job before a family may pick a cheaper one.

Every reply goes through the automatic checks (checks.py) and an Opus judge (scores 1-5 and "critical"
failures such as a maths error or calling a right answer wrong). A model passes a job when its average
judge score is within 0.3 of the baseline (the first model), it has no critical failure, and its automatic
checks pass at least as often as the baseline's minus 5 points.

THIS CALLS THE REAL API AND COSTS MONEY. Run it only with the user's go-ahead, with --max-usd, and first
with --dry-run, which estimates the cost without calling anything. Cases are synthetic, never real chats.

    .venv\\Scripts\\python.exe -m evals.run_eval --job tutor_chat --models claude-opus-5-5,claude-sonnet-5-5,claude-haiku-5-5 --repeat 2 --max-usd 3 --dry-run
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from app import llm  # noqa: E402
from app.llm import service as llm_service  # noqa: E402
from app.llm.models import JOBS, MODELS, cost_usd  # noqa: E402
from app.tutor import prompts  # noqa: E402

from evals.checks import CHECKS, run_checks  # noqa: E402

EVALS = Path(__file__).resolve().parent
CASES = {"tutor_chat": EVALS / "cases" / "tutor_maths_sl.jsonl"}
JUDGE_MODEL = "claude-opus-5-5"

JUDGE_RULES = """\
You grade one reply of a homework tutor for a child at a Slovenian school. The tutor's rules: hints before
answers (the full solution only after real attempts), Slovenian school methods and notation (decimal comma,
"·" and ":"), very short messages ending with one question, warm tone, never gendered "you" in Slovene,
answer in the child's language. Judge only the LAST tutor reply, given the conversation.

Return only JSON: {"correct": 1-5, "pedagogy": 1-5, "clarity": 1-5, "tone": 1-5, "critical": true|false,
"why": "<one sentence>"}. "correct": the maths/language facts are right. "pedagogy": hints first, checks the
child's thinking, does not do the homework. "clarity": fits the grade, short. "critical": true only for a
factual/maths error, telling the child a right answer is wrong (or a wrong one is right), or unsafe content."""


def load_cases(job: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in CASES[job].read_text(encoding="utf-8").splitlines() if line.strip()]


def request_for(case: dict[str, Any]) -> llm.LLMRequest:
    system = [llm.SystemBlock(prompts.RULES, cache=True),
              llm.SystemBlock(prompts.learner_context(name="Ana", grade=case["grade"], language=case["language"],
                                                      subject=case["subject"], interests="nogomet", notes=None))]
    turns = [llm.Turn(t["role"], t["text"]) for t in case["turns"]]
    return llm.LLMRequest(job="tutor_chat", system=system, turns=turns)


def judge(case: dict[str, Any], reply: str) -> tuple[dict[str, Any], float]:
    convo = "\n".join(f"{t['role'].upper()}: {t['text']}" for t in case["turns"])
    text = (f"Child: grade {case['grade']}, language {case['language']}, subject {case['subject']}.\n"
            f"What a good reply does here: {case['expect']}\n\nConversation:\n{convo}\n\nTUTOR (to grade): {reply}")
    req = llm.LLMRequest(job="judge", system=[llm.SystemBlock(JUDGE_RULES, cache=True)], turns=[llm.Turn("user", text)],
                         max_tokens=4000)
    out = llm_service.complete(req, MODELS[JUDGE_MODEL], "high")
    m = re.search(r"\{.*\}", out.text, re.S)
    try:
        verdict = json.loads(m.group(0)) if m else {}
    except ValueError:
        verdict = {}
    return verdict, out.cost_usd


def estimate(cases: list[dict[str, Any]], models: list[str], repeat: int) -> float:
    """A rough upper estimate: ~4 characters per token, 1,500 output tokens per reply (thinking included)."""
    total = 0.0
    for case in cases:
        prompt_tokens = (len(prompts.RULES) + sum(len(t["text"]) for t in case["turns"]) + 400) // 4
        for m in models:
            total += cost_usd(m, prompt_tokens, 1500, 0, 0) * repeat
        total += cost_usd(JUDGE_MODEL, prompt_tokens + 600, 1500, 0, 0) * repeat * len(models)
    return total


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--job", choices=list(CASES), default="tutor_chat")
    ap.add_argument("--models", required=True, help="comma list; the first is the baseline")
    ap.add_argument("--effort", default=None, help="default: the job's default effort")
    ap.add_argument("--repeat", type=int, default=2)
    ap.add_argument("--max-usd", type=float, required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    unknown = [m for m in models if m not in MODELS]
    if unknown:
        print(f"Unknown models: {unknown}. Known: {list(MODELS)}")
        return 1
    cases = load_cases(args.job)
    est = estimate(cases, models, args.repeat)
    print(f"{len(cases)} cases × {len(models)} models × {args.repeat} repeats; estimated at most ${est:.2f} (limit ${args.max_usd:.2f}).")
    if args.dry_run:
        return 0
    if est > args.max_usd:
        print("The estimate is above --max-usd: lower --repeat or the number of models.")
        return 1
    if not llm.configured():
        print("ANTHROPIC_API_KEY is not set.")
        return 1
    effort = args.effort or JOBS[args.job]["effort"]
    out_dir = EVALS / "results" / datetime.now().strftime("%Y-%m-%d-%H%M")
    (out_dir / "raw").mkdir(parents=True, exist_ok=True)
    spent = 0.0
    rows: list[dict[str, Any]] = []
    for case in cases:
        for model in models:
            for rep in range(args.repeat):
                if spent >= args.max_usd:
                    print(f"Stopped: spent ${spent:.2f} of ${args.max_usd:.2f}.")
                    break
                reply = llm_service.complete(request_for(case), MODELS[model], effort)
                spent += reply.cost_usd
                checks = run_checks(case, reply.text)
                verdict, judge_cost = judge(case, reply.text)
                spent += judge_cost
                row = {"case": case["id"], "model": model, "rep": rep, "cost_usd": round(reply.cost_usd, 5),
                       "latency_ms": reply.latency_ms, "refused": reply.refused,
                       **{f"check_{k}": v[0] for k, v in checks.items()},
                       **{k: verdict.get(k) for k in ("correct", "pedagogy", "clarity", "tone", "critical")},
                       "why": verdict.get("why", "")}
                rows.append(row)
                (out_dir / "raw" / f"{case['id']}-{model}-{rep}.json").write_text(
                    json.dumps({"case": case, "reply": reply.text, "checks": checks, "verdict": verdict}, ensure_ascii=False, indent=1),
                    encoding="utf-8")
                print(f"  {case['id']:<26} {model:<20} judge {verdict.get('correct')}/{verdict.get('pedagogy')} "
                      f"critical={verdict.get('critical')}  ${spent:.2f}")
    with (out_dir / "results.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    write_report(out_dir, rows, models, args, spent)
    print(f"Report: {out_dir / 'report.md'}  (spent about ${spent:.2f})")
    return 0


def _score(r: dict[str, Any]) -> float | None:
    vals = [r.get(k) for k in ("correct", "pedagogy", "clarity", "tone")]
    nums = [v for v in vals if isinstance(v, (int, float))]
    return mean(nums) if nums else None


def write_report(out_dir: Path, rows: list[dict[str, Any]], models: list[str], args, spent: float) -> None:
    lines = [f"# Eval: {args.job}", "", f"{datetime.now():%Y-%m-%d %H:%M}, {args.repeat} repeats, spent about ${spent:.2f}.", "",
             "| model | judge avg | critical | checks passed | avg cost per reply | verdict |", "|---|---|---|---|---|---|"]
    stats = {}
    for m in models:
        rs = [r for r in rows if r["model"] == m]
        scores = [s for s in (_score(r) for r in rs) if s is not None]
        checks = [r[f"check_{k}"] for r in rs for k in CHECKS]
        stats[m] = {"score": mean(scores) if scores else 0.0, "critical": sum(1 for r in rs if r.get("critical")),
                    "checks": 100 * sum(checks) / len(checks) if checks else 0.0,
                    "cost": mean(r["cost_usd"] for r in rs) if rs else 0.0}
    base = stats[models[0]]
    for m in models:
        s = stats[m]
        passed = m == models[0] or (s["score"] >= base["score"] - 0.3 and s["critical"] == 0 and s["checks"] >= base["checks"] - 5)
        lines.append(f"| {m} | {s['score']:.2f} | {s['critical']} | {s['checks']:.0f}% | ${s['cost']:.4f} | "
                     f"{'baseline' if m == models[0] else 'PASS' if passed else 'fail'} |")
    lines += ["", "A model that passes may be added to `app/llm/approved_models.json` for this job (by hand, after reading the raw replies)."]
    (out_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
