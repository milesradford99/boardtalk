# Product brief: the canvas

Status: **approved with changes by the user** · 2026-10-25 · Tier 2, Track A (oss-design)
Name: **boardtalk** (user, 2026-10-25). Profile: **serious** (others will depend on it). License: **Apache-2.0** (user). Baseline: built on **pi** (user; see ADR 0002).

## Job

> When I finish a long session with an AI agent, I want to keep a canvas of what happened (what
> we were after, what was tried, what failed and why, what was decided, where it ended up), so
> that later I, or someone I hand it to, can understand the work in minutes and trust every
> detail back to its source.

## What "preserve" means (five properties, each checkable)

1. **Faithful.** Every card links to the exact source messages it came from. Verbatim fields
   (paths, commands, errors, numbers) are checked mechanically against the source. A string that
   does not match is shown as *unverified*, never as fact.
   *(S0: 97% of verbatim strings matched exactly; 0.8–1.7% had no near match. Hence the check.)*
2. **Durable.** One self-contained file per canvas: an append-only event log plus the source it
   was built from, in an open, versioned format. It opens without our service and without the
   network, years later.
3. **Append-only and replayable.** The canvas is a log of board events. Any earlier state can be
   rebuilt; corrections are new events, never edits. *(S0: the prefix property held on 100% of
   folds.)*
4. **Readable at three depths:** phase digest → card → original messages. The digest reads like the
   story; the card holds the detail; the source is the proof. *(S0b: at ~2k tokens the digest level
   still answered 80–85% of hindsight questions, vs 65% for a summary.)*
5. **Safe to share.** Secrets are redacted before anything leaves the machine, and export is a
   static file the owner chooses to send. Agent transcripts routinely contain keys; this one did.

## Who

- **For:** developers who work in long sessions with coding agents (Claude Code first) and want to
  revisit, hand over or show that work: to themselves next week, to a reviewer of the resulting
  PR, or to a teammate taking over.
- **Not for (v0.1):** teams that need a complete compliance audit trail or cost/latency
  observability. We keep the raw log, but don't build audit or tracing features.

## Evidence (partially validated)

Demand to **preserve and share agent sessions** is real and recurring:
- several Claude Code feature requests for export or sharing (Jan, Feb and May 2026; see the sources
  below);
- export requests for ChatGPT Projects, Gemini and GitLab Duo;
- GitHub Copilot CLI shipping `/share`;
- a cluster of community tools: `claude-code-transcripts`, cc2md, Claudebin, a browser-based Claude
  Code viewer, a session-export skill.

The nearest neighbour is a *Context Compaction Visualizer* for traces (LangSmith, OTel), which shows
what an agent forgot, for debugging.

**UNVALIDATED:** that people want to *watch* a live canvas while the agent works (C), and that
they prefer a processed *canvas* over a cleaned-up *transcript* afterwards (B). Every
existing tool exports a linear transcript.
- **Cheapest validation:** give 5 developers the same past session as (a) a Markdown transcript
  and (b) a canvas, plus 5 questions about it. Compare time to answer, correctness and stated
  preference.
- **Rollback criterion:** if the canvas does not win on time or preference, narrow the project to
  a faithful, redacted transcript exporter with provenance.

## The one thing it must do brilliantly

Draw the canvas **live**, beside the agent while it works, and keep it as a durable artifact that
a newcomer later understands in minutes, where **every detail is one click from its proof.**

### Signature moment (decided by the user): live canvas, kept as a static canvas

- **C, live (the signature).** While the agent works, the canvas fills in beside the terminal. Each
  turn appears at once as a *pending* card built from the raw event (tool, file, command). Within
  seconds the scribe's card replaces it, by a new event that supersedes the placeholder, the way
  Hyperknow fills `*_pending` slots with `generated_*` content. Phases close into digests as the
  session moves on.
- **B, static: the persistent product of C.** The same event log, opened later, is the finished
  canvas. Zoomed out, phase digests read like the story. Zoom in to cards; click any card or exact
  string and the source messages open beside it. **One log, two renderings:** live is the log
  being written, static is the log read back. There is no separate export pipeline that could
  drift from what was seen live.
- **A, replay:** scrubbing the log to watch C happen again. It falls out of the same log; later.

## Non-goals and anti-goals

- **Never slows the agent.** Live mode only observes. It reads the session as it is written and
  never sits in the agent's critical path, and the agent never waits for the canvas.

- **Not a general whiteboard.** No freehand drawing or real-time multi-user editing.
- **Not an observability platform.** No token, cost or latency dashboards, and no trace ingestion
  in v0.1.
- **Not an agent framework.** We read sessions; we don't run agents.
- **Never rewrites history.** No editing or deleting of past events. Annotations and corrections
  are new events.
- **No hosted service in v0.1.** Local build and a static export only. Nothing is uploaded by
  default.
- **Board-as-context compression (ADR 0001) is out of v0.1.** It is a later optional mode, built
  on the same log.

## Smallest version that still has the one thing (v0.1)

- **Input:** **pi sessions**, observed live through a pi extension (`@boardtalk/pi`) and stored in
  the session itself as `custom` entries, which never enter model context. Finished sessions can
  be read from `~/.pi/agent/sessions/**.jsonl`. An OpenHands adapter exists for tests, using the S0
  data. Claude Code moves to the later list (ADR 0002).
- **Live:** `boardtalk live [session]` follows the running session and serves the canvas on
  localhost, updating as events arrive: pending cards first, scribe cards seconds later, digests
  when a phase closes. It writes the `.board` log continuously.
- **Build:** `boardtalk build <session> -o <name>.board`. The scribe uses any
  Anthropic-Messages-compatible endpoint (Claude API or the user's Ark plan). It writes cards per
  turn, digests per phase, a verbatim check and redaction.
- **View:** `boardtalk view <name>.board` writes **one offline HTML file** of the same canvas:
  phase digests, cards and a source panel (B, the static product of C).
- **Verify:** `boardtalk verify <name>.board` runs the machine checks below.

**Later list:**
- replay timeline (A)
- live mode via agent hooks or SDK streams (beyond file following)
- more adapters (Claude Code, Codex, Cursor, OpenHands as a user-facing input)
- annotations UI
- board-as-context mode
- handoff cards that use the agent's own reasoning
- shared hosting

## Cost of yes

- **LLM cost per canvas:** the scribe ran about 1–2M tokens per 90-turn session in S0, ~90%
  of it cache reads. Usage needs a budget flag and a dry-run estimate.
- **Adapter upkeep:** session formats change without notice, so each adapter is a maintenance
  liability. Keep the adapter interface tiny.
- **Viewer surface:** the HTML/canvas UI is the largest code surface. Use Excalidraw (MIT) for the
  plane and camera only, with cards as DOM overlay, the pattern Hyperknow uses.
- **Format commitment:** the `.board` format becomes a public contract once others store canvases
  in it. It needs versioning from day one.

## Success signal

- Time to first canvas from a fresh install: ≤ 5 minutes.
- Repeat use: the same person builds canvases for several sessions.
- Canvases shared (exported files sent).
- Later: other tools emitting or reading `.board`.

Stars measure awareness only.

## v0.1 acceptance check (machine-runnable unless marked)

On 3 fixture sessions (one real Claude Code session with secrets planted by us, and two S0 OpenHands
trajectories):

1. `boardtalk build` then `boardtalk verify` exits 0, and verify confirms:
   - every card's source refs resolve to existing messages;
   - every verbatim string either matches the source (whitespace-normalized) or is flagged
     *unverified*, with 0 unflagged mismatches;
   - replaying the event log reproduces the final board byte-for-byte;
   - every snapshot is a byte prefix of the next.
2. **Redaction:** none of the planted fake secrets appears anywhere in the `.board` file or the
   exported HTML (grep test).
3. **Offline viewer:** a headless browser opens the HTML with networking disabled and makes zero
   network requests. Clicking a card opens a source panel containing the card's source text, and
   clicking a verbatim string highlights it there.
4. **Readable digest level (model proxy for human readability):** on the S0 questions, answers
   from the digest level alone score at least the summary baseline at the same token budget (reuse
   the S0b harness, 2k budget, `deepseek-v4.1-flash` only). Check 6 is the real human test.
5. **Live:** replaying a recorded fixture session through `boardtalk live` at real-time pace:
   - a pending card appears within **1 s** of each new turn being written;
   - its scribe card follows within **15 s** at p50 (`deepseek-v4.1-flash`);
   - when the session ends, `boardtalk view` on the `.board` written live renders a final board
     **identical** to the live canvas's final state (same log, no re-generation; a fresh `build`
     would call the model again and is not expected to match);
   - the agent process is never blocked: the scribe failing or stalling only leaves pending cards.
6. **Fresh-agent test:** a fresh agent given only the README goes from a session file to an opened
   canvas in ≤ 5 commands, with no errors.
7. *(human)* The 5-person canvas vs transcript comparison above runs before v0.1 is announced.

## Decisions

- Decided (user, 2026-10-25): signature moment C (live) with B as its static product; name
  boardtalk; profile serious.
- Decided: license Apache-2.0; baseline pi (ADR 0002 proposes a pi package, not a fork).
- Decided: ADR 0002 accepted (pi package, not a fork).

## Sources

- [Claude Code: session export to Markdown request](https://claudeissues.com/issue/63841-feature-request-native-session-export-to-markdown-export-command)
- [Claude Code: conversation sharing / export request](https://claudeissues.com/issue/18803-feature-request-conversation-sharing-export)
- [Claude Code: export a session chat request](https://claudeissues.com/issue/29325-feature-add-support-to-export-a-session-chat)
- [OpenAI community: export project chat history as Markdown](https://community.openai.com/t/feature-request-export-project-chat-history-as-markdown/1381686)
- [Gemini: native chat history export request](https://discuss.ai.google.dev/t/feature-request-native-chat-history-export-recording/116014)
- [GitLab Duo Chat: export history issue](https://gitlab.com/gitlab-org/gitlab/-/issues/454171)
- [GitHub Copilot CLI `/share`](https://rajeevpentyala.com/2026/08/03/github-copilot-cli-save-your-session-transcript/)
- [cc2md](https://bmannconsulting.com/notes/cc2md/) · [Claudebin](https://www.producthunt.com/posts/claudebin) · [Claude Code viewer](https://www.memoryplugin.com/tools/claude-code-viewer) · [session-export skill](https://tessl.io/registry/skills/github/ddehart/claude-code-plugins/session-export) · [transcript-saver (wraps claude-code-transcripts)](https://tessl.io/registry/skills/github/fpl9000/ai-skills/transcript-saver/review)
- [Context Compaction Visualizer](https://thenote.app/post/en/context-compaction-visualizer-see-exactly-what-your-ai-agent-forgot-before-it-xllw0jokt9) · [Pixeltable: the session log as system of record](https://www.pixeltable.com/blog/agents-as-data-session-log-system-of-record)
