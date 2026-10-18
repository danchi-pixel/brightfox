# Evals: is a cheaper model good enough for this job?

A family can pick another model for an AI job (Foxy's chat, oral-exam checking, feedback on written
answers) only after that model passed this eval for the job. Passing models are added by hand to
`app/llm/approved_models.json`.

**Running it calls the real API and costs money.** Ask the user first, say the estimated cost, and always
pass `--max-usd`. Start with `--dry-run`, which only prints the estimate.

```
cd backend
.venv\Scripts\python.exe -m evals.run_eval --job tutor_chat --models claude-opus-5-5,claude-sonnet-5-5,claude-haiku-5-5 --repeat 2 --max-usd 3 --dry-run
```

- **Cases** (`cases/*.jsonl`) are synthetic Slovenian school situations: first asks, wrong tries, right
  answers, "just tell me", decimal comma, written division, an English grammar question, off-topic. They
  are never real chats.
- **Automatic checks** (`checks.py`): decimal comma, gender-neutral Slovene, no answer on the first ask,
  the right language, ends with a question, short.
- **Judge**: Claude Opus 5.5 at high effort scores correctness, pedagogy, clarity and tone (1–5) and flags
  critical failures (a maths error, calling a right answer wrong, unsafe content).
- **Pass rule**: average judge score within 0.3 of the baseline (the first model), no critical failure, and
  automatic checks passing at least as often as the baseline's minus 5 points.
- **Output**: `results/<date>/report.md` and `results.csv` (commit the report); `raw/` holds every reply
  (not committed).
