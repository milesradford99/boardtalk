# Hyperknow whiteboard: teardown, plus what it means for boardtalk

Status: research note, 2026-10-24. **Not a spec.** Nothing here is decided until the user signs off.

Sources: static reading of Hyperknow's public, minified client bundle (`WhiteboardPage-*.js`,
`MessageBubble-*.js`, `BoardZoomControl-*.js`, the bundled Excalidraw chunk), then one live
session ("How AI actually Works" → "What Counts as AI?", about 5 minutes, 2 credits) with
WebSocket frames logged. See §2b. The server's prompts and models are still **inferred**.

## 1. What it is (product)

An AI "lecture" on an infinite board. The agent talks (TTS) and writes on the board at the same time:
cards of markdown + KaTeX, Mermaid graphs, generated images, generated SVG figures, generated HTML
animations, highlights and circles over earlier content, quiz prompts ("ask") and mastery rewards.
You can interrupt by voice mid-sentence. It answers, then either resumes, stops, or re-plans the rest of the lecture.

## 2. How it works (technology)

```
 LLM "teacher" (server)
   │  emits numbered STEPS: speak · board · graph · highlight/circle · new_column · new_page
   │                        figure/animation/image (async: *_pending → generated_*) · ask · reward_user
   ▼
 WebSocket /api/v1/whiteboard/ws   (JSON frames; TTS audio by URL, with per-step timing)
   ▼
 Client step player ──► plays audio + reveals board content in sync
   │                └──► sends action_step_complete{step_id}  ◄── back-pressure: server paces itself on this
   ▼
 Board = Excalidraw (camera, zoom, infinite plane only)
        + DOM overlay layer (cards, graphs, figures) positioned in scene coordinates
        + column/tile layout engine (auto-placement, not LLM coordinates)
   ▼
 sync_whiteboard_state / pause_session{whiteboard_state}  ──► server keeps the board model
 transcript persisted as NDJSON action lines                ──► replay rebuilds the board
```

The key mechanisms, in order of how much they matter for boardtalk:

1. **The LLM never chooses coordinates.** Layout is a deterministic column grid
   (`colCount` 2–3, `tileW`, 12px gaps, `columnIndex`, `activeIndex`). The model only says *what*
   to write and coarse structure (`new_column`, `new_page`). Placement is code.
2. **Annotations are anchored by text, not geometry.** `highlight`/`circle` carry
   `target_board_id` + `snippet` + `occurrence` (an optional `rect` is a fallback). LLMs are good
   at quoting text and bad at pixels. This is the right addressing scheme.
3. **Step protocol with acks.** Every action has a `step_id`. The client reports completion after
   the animation or narration finishes, and the server paces on that. Reveal of a card can be
   gated on a narration step (`revealGateStep`).
4. **Narration ↔ board pointers.** `tts_segment` carries sentence splits and `points`
   `{board, target, kind: text|math|formula, cjk, latin}`: character offsets in the speech at which
   to point at a snippet on a given board item. Speech and ink are time-aligned.
5. **Slow content is placeholdered.** Figures, animations and images first arrive as `*_pending`
   with a reserved slot (`placement_step_id`), then get filled by `generated_*`. The timeline never
   blocks on a slow generator.
6. **Camera policy, not free camera.** Modes `follow`, `newcol`, `anchor`, `center-y`, `top`,
   with eased `scrollX/scrollY` via Excalidraw `updateScene`.
7. **Board state is a document.** `{version, revision, activePageId, pages:[{id, title,
   overlayItems, columnLayout, excalidrawElements}]}`. Items look like `{id, kind, x, y, w, h,
   columnIndex, keypoint|mermaidGraph|boardImage|..., decorations}`.
8. **Interjection.** `interject_start{step_id, offset_ms}` tells the server exactly where in the
   lecture the user cut in. `interject_done{control: none|stop|replan, skip_segment}` decides
   how the lecture continues.
9. **Safety detail worth copying:** generated SVG is parsed and stripped of
   `script/style/foreignObject/image/a/iframe/animate*/on*` and external `url()`
   before render.

Stack: Vite + React (React Router), Excalidraw (MIT), KaTeX, Mermaid, lucide icons.

## 2b. Live session: verified on the wire

**Handshake.** Client sends `resume_or_start_course_session` and `set_tts_config`. Server replies
`connection_established`, `tts_config{voice_id:"calm"}`, then `session_ready{messages,
whiteboard_state, can_continue}` and `lecture_outline_selected`. Client sends `sync_whiteboard_state`,
then `start_teaching`. A `ping`/`pong` heartbeat runs every few seconds.

**Lockstep pacing (confirmed).** Each next step arrives 0.2–0.3 s after the client's
`action_step_complete`. The server generates ahead and *holds* steps until the ack, so audio
length sets the tempo. Excerpt of the timeline (seconds):

```
94.4 out action_step_complete#3
94.7 in  group[board#4, speak#5]       ← write and talk in parallel
94.7 in  tts_segment#5
95.2 out sync_whiteboard_state         ← client reports new card geometry
101.1 out action_step_complete#4       ← card finished "writing"
110.4 out action_step_complete#5       ← audio finished
110.7 in  speak#6
```

**`group` = parallel actions.** `{type:"group", actions:[{type:"board", board_content:<markdown>,
board_uid:1, page_id:"page-1", title:"The Core Divide", step_id:8}, {type:"speak", spoken_text,
step_id:9}]}`. Board content is plain **markdown** (lists, bold, tables, `$math$`). The model writes
markdown; the client renders it.

**Short integer ids for the model, UUIDs for the client.** The model addresses cards by `board_uid`
0, 1, 2…; the client assigns a UUID per overlay item. Step ids restart at 0 on each turn.

**Text-anchored annotation (confirmed).** I typed "circle the if-then part in the table". 1.8 s
later the server sent `{type:"circle", target_board_id:1, snippet:"\"If-Then\" logic"}` with **no
rect**. The client found the text and drew the circle. The first action streaming that fast
suggests actions are parsed out of a streaming LLM response as they complete.

**Narration pointers (confirmed).** `tts_segment.points:[{board:2, kind:"text", target:"Explicit",
latin:11}]`: at character 11 of the spoken text, point at "Explicit" on card 2. The sentence
splits come with character counts for caption timing.

**Interruption via text is just a new turn.** `user_message{message, lecture_outline_id}`. The
reply turn began with the `circle` action, then wrote a new card (`board_uid:2`) under the table.
Nothing on the board was edited: the interruption **appended**.

**Board is 100% DOM overlay.** `excalidrawElements: []`. Each card is an absolutely positioned
`div.overlay-handwriting.overlay-note-card`, with `left/top` and `transform: scale(zoom)` kept in sync
with Excalidraw's scroll and zoom, set in **Virgil** (Excalidraw's hand font). Excalidraw provides
only the dotted infinite plane and the camera.

**Board state is tiny.** 2 cards are about 1.1 KB, 3 cards about 1.6 KB:
`{version:1, revision, activePageId, pages:[{id, overlayItems:[{id, kind:"note_card", x,y,w,h,
columnIndex, keypoint:{title, content, type, importance, column}, boardUid, decorations:[]}],
columnLayout:{lp:{colCount:2, tileW:325, …}, columns:[{x, w, nextY}], activeIndex}}]}`.
`nextY` per column is all the state the auto-layout needs.

**Persistence = action log + snapshot.** After a reconnect, `session_ready.messages` held one
assistant message whose `content` is **NDJSON of the actions** (`speak` with `audio_url`, `board`,
…), flagged `interrupted:true`, plus a `whiteboard_state` snapshot. The LLM's
"assistant message" *is* the action stream.

**Pause.** The pause button sends `turn_pause{paused:true}`.

## 3. Why it matters for boardtalk

Hyperknow's board is **mostly append-only already**: cards are added. "Edits" are
decorations (highlight, circle) layered on top, and fullness is handled by `new_column` and `new_page`.
boardtalk makes that a hard rule and turns it into a context-management strategy:

- **The board is the compressed context.** Each raw message (tool call, tool result, reasoning)
  is processed into board items. Once a raw message's distillate is committed to the board, the raw
  message can leave the model's context. The board's serialization replaces it.
- **Append-only makes prompts cache-friendly.** Rolling summaries rewrite history, so the
  prompt prefix changes and prompt caching misses. An append-only board serializes to a
  monotonically growing prefix, so the cache keeps hitting. Corrections are new items
  ("supersedes #12") or decorations, never rewrites.
- **Compression = folding pages, not rewriting.** When a page fills, open a new page. Old pages
  serialize as their title plus card titles and ids; the full text stays retrievable by id
  (`read_board(12)`). Hyperknow's `new_page` is the UI analogue.
- **Text-anchored references** (`#12 "snippet"`) give the agent a cheap way to point back at old
  evidence without re-quoting it.
- **Copy from the live protocol:** small integer card ids for the model; markdown as the
  card body; `group` for "show while saying"; a held, ack-paced step queue; board geometry kept
  client-side and only `nextY` per column needed for placement; the transcript stored as NDJSON
  actions, from which the board can be rebuilt.

## 4. Prior art (2026-10)

| Project | What it does | Gap vs boardtalk |
|---|---|---|
| tldraw Agent Starter Kit (MIT kit; SDK has its own license, check before adopting) | Agent reads/manipulates a tldraw canvas via structured actions | Canvas is the *task*, not a view of the loop; no compression story |
| tldraw "fairies" (experiment) | Spatialized agents on canvas | Same |
| LangSmith / Langfuse / AgentOps style trace viewers | Tree/timeline of LLM calls | Raw, not processed; not spatial; no feedback into context |
| DrawDash (arXiv 2512.01234) | Proactive whiteboard diagram completion | Education, not agent loops |
| Hyperknow whiteboard | Teacher LLM → board steps | Closed; teaches content, does not visualize its own loop |

No healthy open project covers "processed, append-only board of the agent loop that also
serves as the agent's memory". Recommendation: **build**, on Excalidraw (MIT) or a plain DOM
canvas, rather than contribute upstream.

## 5. Architecture options (Track B, for the user to pick)

**A. Scribe sidecar (view only).** The agent loop is unchanged. A cheap model watches the message
stream and emits board ops. The board is purely visual.
Simplest; zero risk to the agent; does not test the compression idea.

**B. Scribe + board-as-context (recommended).** Same as A, plus a context projector: messages
whose distillate is committed get replaced in the next request by the serialized board.
Tests the core idea. Needs an eval: task success and tokens with board-context vs native compaction.
Risk: a scribe that loses a detail the agent needed. Mitigation: `read_board(id)` / `read_raw(id)`
tools that recover the original.

**C. Board-native agent.** The agent itself emits board ops as tool calls, the way Hyperknow's
teacher emits steps. Highest fidelity, but it costs main-model tokens and couples to one agent.

Board-op vocabulary to start with (borrowed shape, our own names):
`card{kind: goal|plan|tool|observation|decision|error, title, body_md, refs[]}`,
`link{from, to, label}`, `mark{target, snippet, style: highlight|strike|circle}`,
`supersede{old, new}`, `column`, `page{title}`. Every op has `seq` and `source_msg_ids`. The log is
NDJSON, and replay builds the board (as Hyperknow does).
