# boardtalk

**A live canvas of what your AI agent is doing, kept as a durable, append-only record you can
trust.**

While an agent works, boardtalk draws its session as a canvas beside it: goals, attempts, dead
ends, decisions and state, as cards that appear the moment a tool starts and fill in seconds
later. When the session ends, the same log *is* the canvas. Open it later and you get the story
zoomed out, the detail zoomed in, and every card one click from the exact messages it came from.

> **Status: pre-alpha.** Nothing to install yet. This repository holds the design, the
> experiments behind it, and the core board model. Follow the roadmap below.

## Why

Agent sessions vanish into compaction summaries and unreadable JSONL. Summaries drop exactly what
you need later. In our experiments a rewritten summary kept 33–40% of the *failed attempts* in a
session, while a boardtalk-style board kept 63–96% at the same or larger size
([S0](docs/spikes/s0-results.md), [S0b](docs/spikes/s0b-results.md)).

boardtalk's canvas is:

- **Faithful.** Every card cites its source messages. Exact strings (paths, commands, errors)
  are checked against the source, and anything unverified is marked as such.
- **Append-only.** Nothing is edited or deleted; corrections are new cards. Any earlier state can
  be replayed.
- **Durable.** One self-contained log per session, in an open format, readable offline.
- **Safe to share.** Secrets are redacted before anything leaves your machine.

## How it will work

boardtalk is built as a package for the [pi](https://github.com/earendil-works/pi) coding agent
([ADR 0002](docs/adr/0002-build-on-pi.md)):

- **`@boardtalk/pi`:** a pi extension that watches the session, writes cards using *your* configured
  model, stores them in the session itself (never in the model's context), and serves the live
  canvas on localhost.
- **`@boardtalk/viewer`:** the canvas, live or as one offline HTML file.
- **`@boardtalk/core`:** the board model, with no dependency on any agent (this repository, today).

## Try the core

Requires Node.js ≥ 22.18.

```bash
npm ci
npm run check   # typecheck and test
```

## Roadmap to v0.1

The acceptance check is in [docs/design/brief.md](docs/design/brief.md#v01-acceptance-check-machine-runnable-unless-marked).

- [x] Board model: append-only events, supersede, verbatim check, prefix property (`@boardtalk/core`)
- [ ] pi extension: live observation, pending → scribe cards, persistence as session entries
- [ ] Viewer: live canvas, static offline HTML, source panel
- [ ] Phase digests (second-level fold), redaction, `boardtalk verify`

## Documents

- Product brief: [docs/design/brief.md](docs/design/brief.md)
- Decisions: [docs/adr/](docs/adr/)
- Research and experiments: [docs/research/](docs/research/), [docs/spikes/](docs/spikes/)

## Support

Best effort, no SLA. Questions and ideas go in GitHub Discussions once the repository is public;
bugs go in issues. Security reports: see [SECURITY.md](SECURITY.md).

## License

[Apache-2.0](LICENSE).
