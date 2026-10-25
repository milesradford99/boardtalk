# ADR 0002: Build boardtalk on pi as a pi package, not a fork

Status: **accepted** · 2026-10-25 by the user (pi package, not a fork).
Facts verified 2026-10-25 against `earendil-works/pi` docs and npm (re-verify before
implementing):
- pi: MIT, ~118k stars, pushed daily;
- `@earendil-works/pi-coding-agent` 1.4.0 (2026-10-21);
- `@excalidraw/excalidraw` 0.18.1, MIT.

## Context

boardtalk's signature (brief) is a **live canvas** beside the agent (C), kept as a **static
canvas** of the same log (B). Its principles are faithful, durable, append-only, readable at three
depths, and safe to share. pi already has most of the substrate:

| boardtalk needs | pi provides |
|---|---|
| Live feed of what the agent does | Extension events: `message_end`, `tool_execution_start/end`, `turn_end`, `agent_settled` |
| Pending card the moment a tool starts | `tool_execution_start` (args are known before the result) |
| Scribe calls on the user's own models (e.g. Ark flash) | `ctx.modelRegistry.streamSimple()`: nested calls through the user's configured providers, with usage accounted |
| Durable append-only storage of board events | `pi.appendEntry()` → `custom` entries in the session JSONL: persisted, **excluded from model context**, branch-aware |
| Provenance (card → source message) | Every session entry has a stable `id`; cards cite entry ids |
| Branches (forks, `/tree`) | The session is a tree (`id`/`parentId`), so the canvas can show branches as lanes |
| Later: board-as-context (ADR 0001) | `session_before_compact` (extension-provided compaction, `fromHook`), plus append-only `context_edit` entries |
| Distribution | Pi packages via npm or git (`pi install`) |

## Options

1. **A pi package: extension plus viewer (recommended).** `boardtalk` ships as a pi package:
   - an extension that observes events, runs the scribe, appends `custom` board entries and serves
     the live canvas on localhost from `session_start`;
   - a viewer that renders the board from any pi session file (live over WebSocket, static as one
     offline HTML).

   *Pros:* no fork to maintain; users keep their pi and their models; the board lives inside the
   session they already keep; works in interactive, RPC and SDK modes. *Cons:* bound to pi's
   extension API, which moves fast, so we pin a minimum version and keep a thin adapter layer.
2. **Fork pi.** Full control of the UI and loop. *Cons:* tracking a daily-moving 118k-star
   codebase is a permanent tax, users must switch agents, and nothing boardtalk needs requires
   core changes.
3. **Standalone tool that only reads session files.** Most decoupled, but it can't show pending
   cards at `tool_execution_start`, can't use the user's model registry, and can't store board
   events in the session. It weakens the live signature (C).

## Decision (proposed)

Option 1. Layout:
- **`boardtalk` core (TypeScript, Apache-2.0):** the board event model, the `.board` export format,
  the verbatim checker, redaction, layout, and the digest fold. It has **no pi import**, so other
  agents (Claude Code, OpenHands) can be added later as adapters.
- **`@boardtalk/pi`:** the pi extension. Events → core; scribe via `streamSimple`; persistence via
  `appendEntry` (`customType: "boardtalk.*"`); live server.
- **`@boardtalk/viewer`:** React plus Excalidraw (plane and camera only) with DOM card overlay, the
  Hyperknow pattern. Live mode (WebSocket) and static mode (single offline HTML) share the same
  renderer, so B is literally C read back.

Board events live in the pi session as `custom` entries. Those **never enter model context**, so
the canvas cannot disturb the agent, its cache or its preserved thinking. `.board` files are
exported from them for sharing outside pi.

## Consequences

- **Input order changes:** v0.1 input becomes **pi sessions first** (brief updated). The Claude Code
  adapter moves to the later list.
- **Licenses:** boardtalk is Apache-2.0 and depends on pi and Excalidraw (both MIT). The
  combination is compatible; we keep their notices in third-party attributions.
- **Safety:** extensions run with full pi-process permissions and can see prompts and credentials.
  boardtalk must never send session content anywhere except the user's configured model provider,
  and the live server binds to localhost only. This goes in SECURITY.md.
- **Version pinning:** pin a minimum pi version, and CI tests against the latest pi to catch API
  drift early.

## How to reverse

Core has no pi dependency. Switching to option 3 (file reader) or adding another agent means
writing a new adapter; the board model and viewer don't change.
