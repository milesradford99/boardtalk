# Contributing to boardtalk

Thanks for your interest. boardtalk is pre-alpha; the design is moving, so **please open an issue
or discussion before writing a non-trivial PR.** Small fixes (typos, obvious bugs with a test) are
welcome directly.

## Development

```bash
npm ci
npm run check   # typecheck and tests; must pass before you open a PR
```

See [AGENTS.md](AGENTS.md) for conventions. The two that matter most:
- the board is **append-only**: no API may edit or delete events;
- `@boardtalk/core` stays free of agent-specific dependencies.

## What a good PR looks like

- One change per PR, with a test that fails before it and passes after.
- Public API changes reference an issue where the shape was agreed. Before 1.0, minor versions may
  break; deprecated APIs get at least one minor release of warning.
- No new runtime dependency without prior discussion (maintenance, license, size, security
  history).
- Changes to `.github/workflows/`, `AGENTS.md`/`CLAUDE.md`, or build and release config are reviewed
  separately and more strictly.

## AI-assisted contributions

> **Draft policy, pending maintainer approval.**

AI-assisted contributions are welcome. You are the author, so you must:
- understand and be able to explain every line you submit;
- have run the tests yourself;
- disclose substantial AI assistance in the PR description (the PR template has a field for it).

PRs that look machine-generated without human review (unrelated churn, invented APIs,
untested code, generic descriptions) will be closed without detailed review.

## How we say no

boardtalk has a deliberately narrow scope: see the non-goals in
[docs/design/brief.md](docs/design/brief.md#non-goals-and-anti-goals). We will kindly decline
features outside it, such as freehand whiteboarding, observability dashboards, or editing history,
even when well implemented. A "no" is about scope, not about you.
