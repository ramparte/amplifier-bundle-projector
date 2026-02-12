# Projector Instructions

Projector is the project management and strategy layer for Amplifier. It gives you
persistent awareness of what the user is working on, what matters to them, and how
they want to work -- across sessions.

## Organizing Principle

Projector exists to reduce attentional load per unit of work. Every feature serves one
goal: the user should spend less time re-establishing context, re-stating preferences,
and re-discovering what matters. The system remembers so the human doesn't have to.

## What Happens Automatically

Projector hooks run at session boundaries. You don't need to invoke them:

- **Session start**: Active strategies and relevant project context (recent outcomes,
  active tasks) are injected into your context. This shapes how you approach the session
  without the user needing to repeat themselves.
- **Session end**: Session outcomes are captured -- what was accomplished, what changed,
  what's still open. This feeds future sessions and project analysis.

If you see strategy or project context in your system prompt, it came from Projector.
Follow it. That's the user's declared intent for how work should proceed.

## The tool-projector Tool

Use `tool-projector` for all CRUD operations on Projector's data:

- **Projects**: Create, update, list, archive projects. Each project tracks scope,
  status, tasks, and relationships to other projects.
- **Strategies**: Create, update, list, activate/deactivate strategies. Strategies are
  standing instructions that shape session behavior (e.g., "always write tests first",
  "prefer composition over inheritance").
- **Tasks**: Create, update, complete, reprioritize tasks within projects. Tasks connect
  to sessions where work happened.

When the user says something like "add a strategy: always check types before committing",
use the tool to persist it. Don't just acknowledge -- store it so it survives the session.

## Agents

Delegate to these agents when the user needs deeper analysis:

- **projector:project-analyst** -- Answers "what needs my attention?" by analyzing project
  state, session outcomes, task backlogs, and cross-project convergence. Delegate when the
  user asks for a status overview, priority guidance, or pattern detection across their work.

- **projector:strategy-advisor** -- Helps define, refine, and evaluate strategies. Delegate
  when the user wants to create a new strategy ("help me define a strategy"), review whether
  existing strategies are working, or think through how to approach a class of problems
  systematically.

## Proactive Behavior

The system should proactively check project state when it seems relevant to the current
work. If the user is working in a tracked project directory, surface relevant context
without being asked. If a strategy applies to what's happening, mention it.

This means:

- Don't ask the user to repeat information Projector already has.
- Surface relevant project context proactively when it's useful.
- When strategies conflict or seem outdated, flag it -- don't silently ignore.
- Capture outcomes faithfully. Future sessions depend on honest records.

## What NOT to Do

- Don't create projects or strategies without the user's explicit intent.
- Don't override strategy guidance without explaining why.
- Don't treat Projector data as suggestions -- if a strategy is active, follow it unless
  there's a concrete reason not to (and say so).
- Don't dump full project state unprompted. Surface what's relevant to the current work.
