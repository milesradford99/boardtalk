# Spike S0 (throwaway)

Plans and results: `../../docs/spikes/` (S0, S0b). Kept in the repo so the results can be reproduced. It is not part of the product. Last runs used the Volcengine Ark agent plan (`.env` with `ARK_API_KEY`/`ARK_BASE_URL`, gitignored); future Ark runs use `deepseek-v4.1-flash` only.

## Setup (one time, done by a human)

1. Python packaging. This machine's Python 3.14 has no pip/ensurepip:
   `sudo apt install python3-pip python3-venv`
2. API key. Put it in `spikes/s0/.env` as `ANTHROPIC_API_KEY=...` and run `chmod 600 .env`. The
   file is ignored by `.gitignore`. Nothing in the spike prints it.

## Run order (each step is resumable; the ledger stops everything at $30)

```
python3 -m venv .venv && .venv/bin/pip install anthropic==2.3.0
python3 sample.py                     # already done: data/trajectories/
.venv/bin/python questions.py
.venv/bin/python fold.py              # summary baseline
.venv/bin/python scribe.py haiku
.venv/bin/python scribe.py sonnet     # most expensive arm, run last
.venv/bin/python answer.py
.venv/bin/python grade.py             # writes report.md
```

Run the real steps with `ANTHROPIC_BASE_URL` unset, so requests go to the Anthropic API rather than
to an inherited proxy.

Dry run, free: `S0_FAKE=1 S0_OUT=data/dry <step>`.
