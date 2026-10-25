# Spike S0 (throwaway)

Plans and results: `../../docs/spikes/` (S0, S0b). Kept in the repo so the results can be reproduced. It is not part of the product. Last runs used the Volcengine Ark agent plan (`.env` with `ARK_API_KEY`/`ARK_BASE_URL`, gitignored); future Ark runs use `deepseek-v4.1-flash` only.

## Setup

- Python 3.10+, standard library only (the client is plain `urllib` against an
  Anthropic-Messages-compatible endpoint).
- `spikes/s0/.env` (gitignored, `chmod 600`) with `ARK_API_KEY=...` and `ARK_BASE_URL=...`.
  Nothing in the spike prints the key.

## Run order (each step is resumable; the ledger stops at a token cap, `TOKEN_CAP` in `common.py`)

```
python3 sample.py                     # already done: data/trajectories/
python3 questions.py
python3 fold.py              # summary baseline
python3 scribe.py flash
python3 scribe.py pro
python3 answer.py
python3 grade.py             # writes report.md
python3 s0b.py build && python3 s0b.py answer && python3 s0b.py grade   # S0b, equal budget
```

Run the real steps with `ANTHROPIC_BASE_URL` unset (`env -u ANTHROPIC_BASE_URL ...`). The
spike reads its endpoint from `.env` only.

Dry run, free: `S0_FAKE=1 S0_OUT=data/dry <step>`.
