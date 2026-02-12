# Projector Architecture

## 1. Organizing Principle

**Reduce attentional load for humans per unit of work done by the system.**

AI scales; human attention doesn't. Every Projector feature is evaluated by one question: does this reduce how much the human has to think about things the system could handle?

Re-establishing context is attentional waste. Repeating preferences is attentional waste. Manually checking what needs attention across projects is attentional waste. Projector eliminates these categories of waste by making the system remember, enforce, and synthesize on behalf of the human.

## 2. The Three Problems

**Repetition.** Users re-explain context, strategies, and preferences every session. "I'm working on the TUI, we use this testing approach, here's what happened last time." Projector makes every session start with that knowledge already loaded.

**Fragmentation.** Work spans multiple sessions, projects, and repositories. There's no unified view of what's active, what's stalled, what was accomplished. Projector maintains a persistent project graph with outcome history that any session can query.

**Coordination.** Multiple people building related things without shared awareness. Convergent work goes undetected until it conflicts. Projector tracks cross-person activity and surfaces convergence before it becomes a problem.

## 3. Architecture (Three Parts)

Projector is three things composed together:

### Capability Bundle (tools + agents)

The `projector` behavior provides the interactive surface:

- **tool-projector** -- CRUD tool for projects, strategies, tasks, and outcomes. Operations: `list_projects`, `get_project`, `create_project`, `update_project`, `list_strategies`, `get_strategy`, `set_strategy`, `toggle_strategy`, `add_task`, `update_task`, `list_tasks`, `log_outcome`, `get_status`. All state is flat files on disk.
- **projector:project-analyst** -- Agent for cross-project analysis. Answers "what needs my attention?" by reading project state, outcome logs, git activity, and task backlogs. Detects convergence across projects and people.
- **projector:strategy-advisor** -- Agent for strategy lifecycle. Helps define, refine, evaluate, and retire strategies. Ensures strategies are concrete and operational, not aspirational.

### Policy Behavior (hooks)

The `projector-policy` behavior provides automatic session integration:

- **hooks-projector** registers `session:start` and `session:end` hooks.
- On **session:start**: loads active strategies from `~/.amplifier/projector/strategies/`, detects the current project from git remote or directory path, loads recent outcomes and active tasks. Injects all of this as context. Root sessions only (sub-agents don't get injected).
- On **session:end**: captures a session outcome record (timestamp, summary, tasks completed/created) and appends it to the project's `outcomes.jsonl`.

The hook is intentionally simple. Context building reads YAML files and formats text. Outcome capture is append-only JSONL. No database, no service, no complexity.

### Surface Integration (distro plugin -- future)

The distro plugin wraps the bundle for multi-surface consumption:

- REST API at `/apps/projector/` consumed by TUI, web, Slack, voice.
- Hooks into Bridge API session creation to inject context server-side.
- Uses the distro's provider configuration and authentication.

**The bundle doesn't know about the distro. The distro plugin wraps the bundle.** Clean dependency direction: distro depends on bundle, never the reverse.

## 4. Strategy Enforcement Levels

**Level 1 -- Advisory (current).** Context injection. Active strategies are loaded from YAML and injected into session context at start. The LLM reads them and follows them. No enforcement mechanism beyond the model's instruction-following. This is what's built today.

**Level 2 -- Reactive (future).** Hook-enforced. Hooks check actions after they happen and nudge on drift. Example: if a "test-before-commit" strategy is active and a commit happens without test results in the session, the hook injects a reminder. Requires `action:post` hooks.

**Level 3 -- Proactive (future).** System-initiated. The system auto-spawns sessions to enforce strategies without human prompting. Example: after a complex build session completes, auto-spawn an antagonistic review session. Uses self-driving bundle patterns for autonomous orchestration.

## 5. Data Model

A tree of YAML files with fuzzy semantic connections. Projects have structured fields (status, repos, people, tags) plus free-text descriptions and notes. Relationships (`part_of`, `related_to`, `depends_on`) are declared but semantically interpreted -- the LLM reads project descriptions and understands how things relate. No foreign keys, no referential integrity enforcement.

All data lives at `~/.amplifier/projector/`:

```
config.yaml                          # Global settings (tracked users, enforcement defaults)
strategies/*.yaml                    # Working strategies (active/inactive)
projects/<slug>/project.yaml         # Project definition (status, repos, people, relationships)
projects/<slug>/tasks.yaml           # Per-project task list
projects/<slug>/outcomes.jsonl       # Session outcome log (append-only)
```

Strategy YAML schema:
```yaml
name: strategy-name
description: What it does and why
active: true
scope: global              # or project-scoped
enforcement: soft          # soft | directive | automated
injection: |               # Text injected into session context
  Concrete instructions for the LLM...
tags: [category, ...]
```

Project YAML schema:
```yaml
name: project-slug
description: What this project is
repos: [org/repo-name]
people: [github-handle]
status: active
tags: [category, ...]
relationships:
  part_of: [parent-project]
  related_to: [sibling-project]
notes: |
  Free-text context...
```

## 6. Two Deployment Modes

**Standalone bundle.** Install the bundle, get hooks + tool + agents in any Amplifier session. No server required. Everything is local file I/O. This is the current mode.

**Distro plugin.** REST API consumed by all surfaces (TUI, web, Slack, voice). The plugin wraps `tool-projector` as HTTP endpoints and hooks into the distro's session lifecycle. Uses the distro's provider choices. Enables features like periodic attention digests and cross-surface notifications.

The standalone bundle is always the foundation. The distro plugin is an optional wrapper that adds network accessibility and scheduling.

## 7. Passive-First Coordination

Coordination starts passive: any session can ask "what needs attention?" and the `project-analyst` agent does the work on demand. It reads project definitions, outcome logs, git activity, and task state, then synthesizes a prioritized view.

Always-on coordination is just a scheduled prompt. A cron job or background process asks the same question periodically and stores the results. The intelligence is the LLM reading the data, not a custom algorithm. This means coordination quality improves with model quality for free.

Detection priorities:
1. Blocked tasks -- something is waiting
2. Stale projects -- active but no recent outcomes
3. Convergence -- parallel work that should be coordinated
4. Upcoming deadlines -- time pressure
5. Opportunities -- momentum patterns suggesting a good moment to act

## 8. Self-Driving Integration (Future)

The `amplifier-bundle-self-driving` provides autonomous orchestration patterns: worker-reviewer triangle, task decomposition, wisdom store. Projector can invoke these for Level 3 proactive strategies:

- Auto-spawning antagonistic reviews after complex build sessions
- Running multi-step project tasks autonomously (decompose, execute, verify)
- Periodic strategy effectiveness analysis (do strategies correlate with better outcomes?)

The integration point is strategy enforcement: a Level 3 strategy can specify a self-driving pattern to execute, and Projector triggers it at the right moment.

## 9. The Nine Strategies

Current strategies in `~/.amplifier/projector/strategies/`:

1. **subagent-first** -- Delegate multi-file exploration to sub-agents; never burn main session context on raw file reads.
2. **test-before-presenting** -- Never claim work is done without running tests and verifying output.
3. **incremental-validation** -- Validate after every 3 modified files; never accumulate 7+ unvalidated changes.
4. **antagonistic-review** -- After complex work, spawn a fresh review session with no shared context to audit output.
5. **shadow-testing** -- Require shadow environment verification for cross-repo changes.
6. **project-awareness** -- Establish project context at session start from working directory, git remote, and history.
7. **cross-person-tracking** -- Track contributor activity across the ecosystem for coordination intelligence.
8. **identity-map** -- Maintain and verify known identities, repos, and tools before referencing them.
9. **local-working-notes** -- Persist working state in project files rather than relying on conversation memory.

## 10. What's Next

- **Level 2 enforcement** -- Reactive hooks that check actions and nudge on strategy drift.
- **TUI project sidebar** -- Surface project state and tasks in the terminal UI.
- **Periodic attention digest** -- Scheduled analysis pushed to Slack or notification channel.
- **Strategy effectiveness tracking** -- Correlate strategy activation with session outcome quality.
- **Cross-person convergence alerts** -- Proactive notification when parallel work is detected.
- **Self-driving integration** -- Level 3 autonomous strategies using worker-reviewer patterns.
- **Distro plugin** -- REST API wrapping the bundle for multi-surface consumption.
