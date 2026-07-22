# Clara (Receptionist Agent) — Fix & Redesign Plan

Scoped to Clara only. Don't touch the other 5 agents in this pass — get one
agent right, then the pattern ports to the rest. Same rules as before: one
task at a time, Verify before checking the box, commit per task, stop on
anything flagged **DECISION**.

---

## Phase 0 — Reproduce & diagnose (no code changes)

- [ ] Collect 10-15 real conversation transcripts where Clara "didn't work
      correctly" — misrouted, lost context, gave a canned/wrong response,
      failed to book something it should have. Paste them into
      `docs/clara_failure_log.md` verbatim with what you expected vs what
      happened.
- [ ] For each failure, trace it to one of: (a) router misclassified intent,
      (b) sticky booking state got out of sync with what the user actually
      said, (c) Clara only made one tool call when the request needed a
      follow-up call, (d) a tool call failed and the error wasn't surfaced
      usably, (e) session history (last-6-turns cap) dropped context the
      reply needed. Tag each transcript with its cause.
- [ ] Read the current `max_consecutive_auto_reply` (or equivalent) setting
      for Clara's `AssistantAgent` in `orchestrator.py`'s `_build_agents()`
      and confirm whether it's actually capped at 1 tool call per turn.
      **Verify:** `docs/clara_failure_log.md` has all transcripts tagged with
      a root cause from the list above; you know the current tool-call cap.

---

## Phase 1 — Decouple routing from state

- [ ] **Router does agent selection only.** Strip booking-state tracking out
      of the orchestrator's intent-detection code path. It should answer one
      question — "which of the 6 agents" — using the existing keyword
      fast-path + LLM-classifier fallback, and nothing else.
      **Verify:** a test conversation that changes topic mid-flow (booking →
      "actually, what's my last review say" → back to booking) routes each
      message to the correct agent without the router itself getting stuck.
- [ ] **Remove the external sticky-state store** for booking slots (or repurpose
      it as a passive cache Clara can read, never one that gates behavior).
      Booking-in-progress context should live in the conversation history
      Clara sees, not a side-channel the orchestrator enforces.
      **Verify:** a "change my mind" conversation ("book me for 2pm" → "actually
      3pm" → "ok confirm") completes correctly using only conversation history.

---

## Phase 2 — Give Clara a real multi-step tool loop

- [ ] Configure Clara's `AssistantAgent` (and its AutoGen chat driver) to allow
      multiple sequential tool calls within a single turn — e.g. call
      `check_availability`, read the result, then call `book` — instead of
      stopping after one call. Raise `max_consecutive_auto_reply` (or the
      equivalent AutoGen setting) and confirm the wrapper in
      `ai/tools/capabilities.py` doesn't short-circuit after the first call.
      **Verify:** a single-turn test — "book me a haircut tomorrow at 10am if
      it's free" — results in both a `check_availability` call and a `book`
      call happening in the same turn, with no extra user round-trip needed.
- [ ] **Tool errors feed back into the loop, not a canned failure message.**
      When `book` fails (slot taken, past date, etc.), the error should go
      back into Clara's context so it can respond naturally ("that slot's
      taken, how about 11am?") instead of surfacing a raw error or a static
      apology string.
      **Verify:** test that books a slot, then tries to double-book it, and
      asserts Clara's reply proposes an alternative rather than just failing.
- [ ] **Widen session memory beyond a hard 6-turn cutoff.** Replace the fixed
      window with a sliding window that summarizes older turns instead of
      dropping them outright, so context from 8-10 turns back (a service
      mentioned earlier, an earlier date change) isn't silently lost.
      **Verify:** a 10+ turn conversation where turn 2 sets a detail used in
      turn 10; response is correct with the new memory handling, wrong with
      the old fixed cutoff (write this as a regression test, not just manual
      confirmation).

---

## Phase 3 — Make it feel real-time

- [ ] Add SSE (or websocket) streaming to `/api/agent/chat` for Clara's
      responses specifically — tokens should reach the frontend as they're
      generated, not after the full response is assembled.
      **Verify:** manual check in the browser: response text appears
      incrementally, not all at once after a pause.
- [ ] Update the frontend chat component to render streamed chunks instead of
      waiting for a full response payload.
      **Verify:** same manual check from the UI; no regression in how tool
      results get formatted into the final message.
- [ ] Drop (or make optional/last-resort only) the separate "format tool
      result into friendly text" step if it's a distinct LLM call — let
      Clara's own generation produce the final reply in the same streamed
      pass, so wording feels like one continuous voice rather than two
      LLM calls stitched together.
      **Verify:** response latency measured before/after; should drop since
      you removed a full extra LLM round-trip.

---

## Phase 4 — Lock it in

- [ ] Turn every transcript from `docs/clara_failure_log.md` (Phase 0) into a
      permanent regression test.
      **Verify:** full suite green, including these.
- [ ] Update `KETHAM_ARCHITECTURE.md`'s Clara/orchestrator sections and
      CLAUDE.md to describe the new router/tool-loop/streaming design instead
      of the old intent-gate/sticky-state one.

---

## Definition of done

Every transcript in `docs/clara_failure_log.md` now passes as a regression
test, Clara completes multi-step bookings in one turn, and responses stream
live in the UI.