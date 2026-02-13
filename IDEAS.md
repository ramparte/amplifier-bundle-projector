# Project Ideas from the Field

Ideas sourced from WhatsApp group discussions (Feb 10-12, 2026), mapped to existing projector projects. Updated as new signals emerge.

Last updated: 2026-02-12

---

## amplifier-tui

### Semantic code search integration (ColGrep)
**Signal:** Ryan shared ColGrep (lightonai/next-plaid) -- embedding-based code search. Paul noted it's "a long way from ctags." Currently stores indexes in a non-standard location.

**Idea:** Integrate ColGrep or similar semantic search as a `/search` enhancement. Today's `/search` and `/grep` are text-based. A `/semantic` command could find conceptually related code, not just string matches. Could also power the existing session scanner's cross-session search with embeddings (currently flagged as "no embeddings yet" in the backlog).

**Effort:** Medium. Requires ColGrep or equivalent as a dependency.

---

### Non-code text editing mode
**Signal:** Bryan: "if the goal is to write 'not code text' with AI, I claim there still isn't a decent option." Hilary has a full AI workflow for game narrative content (chained skills with evals).

**Idea:** A `/prose` or `/write` mode that switches the TUI into a writing-focused experience: wider text area, distraction-free layout, writing-specific slash commands (`/tone`, `/expand`, `/condense`, `/rephrase`), and a different system prompt optimized for prose rather than code. Hilary's chained-skills-with-evals pattern could be a recipe that plugs in.

**Effort:** Medium. Mode switch + new command mixin + layout variant.

---

### Cerebras fast-codegen integration
**Signal:** Harper shared sugi's "speed-run" skill that uses Cerebras for fast codegen inside Claude Code. Eran: "cerebras is sooooo fast."

**Idea:** A `/fast` command or model-routing option that sends simple codegen tasks to Cerebras (or similar fast inference) while keeping complex reasoning on Sonnet/Opus. The TUI's existing `/compare` A/B testing feature could be extended to benchmark fast-vs-smart routing. Ties into the "Model Hot-Swap" idea already in FEATURE-IDEAS.md.

**Effort:** Medium. Provider routing + model selection UX.

---

### Jira/project-tracker MCP panel
**Signal:** Kellan: "are folks using MCP for talking to Jira or one of the command line options?" Self-described #suitz persona.

**Idea:** A `/jira` (or generic `/tracker`) command that connects to project trackers via MCP. Show current sprint, assigned tickets, and let the agent reference ticket context when working. Could also surface projector tasks in a similar panel.

**Effort:** Medium-high. MCP integration + panel widget.

---

## amplifier-self-driving

### Ralph loop with TODO-driven serial execution
**Signal:** Ian built a TODO checkbox system + `/next` command for serial autonomous execution. Jeff LC: "Has anyone got a good Ralph loop working end-to-end?" Ian: "almost -- still need to check progress between big steps." Ate all tokens running in a loop.

**Idea:** A first-class Ralph loop implementation: autonomous agent reads TODO.md, works on next item, validates, checks off, moves to next. Key additions over Ian's approach: (1) budget awareness to stop before token exhaustion, (2) checkpoint validation between steps (not just at end), (3) progress reporting to a monitoring surface. Self-driving already has approval gates -- extend with budget gates.

**Effort:** Medium. Recipe + budget-aware loop logic.

---

### Sleep-mode overnight execution
**Signal:** Shane: "making progress while you sleep is an undefeated feeling." Ian's loop runs but eats all tokens. Jesse working on Claude-driving-Claude with terminal access.

**Idea:** A "sleep mode" recipe that queues a TODO list, runs autonomously overnight with conservative token budgets per step, checkpoints to disk after each step, and produces a morning briefing of what was accomplished. Integrates with distro's existing overnight build system. Failures are captured, not retried -- human reviews in the morning.

**Effort:** Medium-high. Recipe + overnight scheduling + morning briefing generation.

---

## projector

### Rewrite-readiness assessment
**Signal:** Shane Chin asking if "never rewrite from scratch" still holds. Josh Whiting: "can the foggy behavior of the system be made well-understood? Expressed as specs or full coverage test suites, then rewrite away."

**Idea:** A projector assessment tool: for any tracked project, analyze test coverage, spec coverage, documentation completeness, and institutional knowledge capture. Produce a "rewrite readiness score" -- can we confidently rewrite this from specs? Surfaces which projects have enough captured context to be safely regenerated vs. which ones still have critical knowledge only in the code.

**Effort:** Medium. Analysis recipe + scoring rubric.

---

### Strategy: compaction and summarization rules
**Signal:** Craig Soules asked about rules for when to compact/summarize. Jay: "we push everything all the time." Current Amplifier compaction is automatic but not strategic.

**Idea:** A new projector strategy: `smart-compaction`. Instead of compacting when the context is full (reactive), proactively summarize and compact based on task boundaries. After completing a TODO item, compact the implementation details but keep the decision trail. After a review pass, compact the review but keep the verdict. The strategy would inject compaction guidance that the orchestrator could act on.

**Effort:** Medium. New strategy file + orchestrator awareness.

---

### Agent memory hygiene strategy
**Signal:** Jesse: "wondering how much I'm gonna have to go clean up its memories so it doesn't get weird ideas about me ignoring it." Braydon: building layered memory with semantic hints because "so many threads that the main chat agent becomes confused."

**Idea:** A projector strategy for memory hygiene: periodically audit agent memories for staleness, contradictions, and confusion. Flag memories that reference completed projects, outdated decisions, or stale context. Could be a weekly recipe that runs a memory audit and presents a cleanup report. Ties into projector's existing outcome capture -- outcomes could inform which memories to retire.

**Effort:** Low-medium. Strategy file + audit recipe.

---

## amplifier-distro

### Message sync bridge (Beeper/chat integration)
**Signal:** Jesse told Harper not to waste tokens on beeper message sync "in the next couple hours" (implying something coming from Jesse's side). Harper: "I did build a tui for beeper."

**Idea:** A distro bridge for chat platforms (Beeper, iMessage, WhatsApp) -- the same pattern as the existing Slack bridge. Read incoming messages, route to an Amplifier session, respond through the chat platform. Could power the "personal assistant managing too many threads" use case Braydon described. Jesse may already be working on this.

**Effort:** High. New bridge plugin + chat platform API integration.

---

### Cerebras/fast-inference provider plugin
**Signal:** Cerebras speed-run skill is popular. Gemini 3 Deep Think announced. lhl switching between providers. People want fast inference for simple tasks.

**Idea:** A distro provider plugin that routes to Cerebras (or Groq, or local cluster models) for fast inference tasks. Configuration in the distro server, exposed to all surfaces (TUI, web, Slack, voice). Could use the cluster project's local models as another fast-inference backend.

**Effort:** Medium. New provider module + routing logic.

---

## amplifier-voice

### Voice-driven diff review
**Signal:** Ian: "I stopped opening any IDE -- I mostly review diffs now." The review bottleneck is the #1 problem. Voice could make review faster than reading.

**Idea:** A voice mode specifically for code review: the agent reads you a summary of changes, you ask questions verbally ("what changed in auth?", "why did it touch the database layer?"), approve or reject with voice commands. Could work great for the "morning briefing after overnight run" scenario. Brian's voice project + the TUI's diff view + the self-driving overnight results.

**Effort:** High. Voice UX design + integration with diff/review features.

---

## amplifier-stories

### Automated agent PR narratives
**Signal:** A claw bot submitted a PR to matplotlib, got rejected, then wrote a blog post about it. Peter: "the last thing they need to deal with." The agent-generated-PR-with-no-context problem is real.

**Idea:** Use amplifier-stories to automatically generate rich PR descriptions: not just "what changed" but "why this approach was chosen, what alternatives were considered, what tests verify it, what the reviewer should focus on." The storytelling agents could turn a session transcript into a reviewer-friendly narrative. Attacks the review bottleneck from the PR quality side.

**Effort:** Medium. New recipe wiring session transcript to PR description generation.

---

## albert

### Layered memory with semantic routing
**Signal:** Braydon: building personal assistant but "so many threads that the main chat agent becomes confused easily -- building layered memory system with semantic hints."

**Idea:** Albert's self-directed agent could benefit from a tiered memory architecture: (1) hot context (current task), (2) warm context (related recent work, semantically retrieved), (3) cold context (archived, only pulled on explicit query). Semantic hints at the routing layer decide what to promote/demote. This is the same problem Braydon is solving for his personal assistant -- Albert could be the reference implementation.

**Effort:** High. Memory architecture redesign + semantic retrieval.

---

## cluster

### Local fast-inference service for agent routing
**Signal:** Cerebras is fast but external. Gemini 3 Deep Think announced. Multiple providers in play. The cluster already hosts Qwen and image models.

**Idea:** Run a fast-inference-optimized model on the cluster (Qwen, Llama, or similar) specifically for the "simple tasks" routing use case. Expose as a distro provider. When the TUI's model router decides a task is simple (linting, formatting, simple refactors), route to local cluster instead of burning API tokens. Free, fast, private.

**Effort:** Medium. Model deployment + provider module + routing heuristic.

---

## amplifier-web

### Post-IDE mission control dashboard
**Signal:** Ian: "I stopped opening any IDE." Hilary ditching Cursor. The group consensus is drifting toward "the IDE is dead, long live the terminal + diff reviewer."

**Idea:** Rather than recreating an IDE in the browser, lean into what people actually do now: review diffs, manage agent tasks, monitor progress. The web UI should be a mission control dashboard, not a code editor. Show: active agents, recent diffs awaiting review, token budget, project status (from projector), overnight run results. The TUI's panels translated to a spatial web layout.

**Effort:** Medium-high. Web frontend architecture work, but SharedAppBase provides the foundation.

---

## How to use this document

These are living ideas, not commitments. To act on one:

1. Pick an idea that fits current priorities
2. Create a task in the relevant project's tasks.yaml via `tool-projector`
3. Use `deliberate-planner` to decompose before implementing
4. After shipping, capture the outcome in projector

Ideas that age out without action can be archived or deleted. New signals from the chats should be added as they emerge.
