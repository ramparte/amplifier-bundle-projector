# Strategy Awareness

Strategies are persistent working instructions managed by Projector. They are injected
into sessions automatically via hooks -- if active strategies exist, they appear in your
context at session start.

## Quick Reference

- **Add a strategy**: When the user says "add a strategy: X", use `tool-projector` to
  create and activate it. Strategies persist across sessions.
- **Remove/toggle a strategy**: Use `tool-projector` to deactivate or delete. Users can
  manage strategies conversationally -- don't ask them to edit YAML files.
- **List strategies**: Use `tool-projector` to show active and inactive strategies.
- **What needs attention?**: Delegate to `projector:project-analyst` for cross-project
  status analysis, priority recommendations, and pattern detection.
- **Refine a strategy**: Delegate to `projector:strategy-advisor` when the user wants to
  define a new strategy, evaluate whether existing ones are working, or restructure
  their strategic approach.

## Strategy Hierarchy

Strategies can be global (apply to all sessions) or project-scoped (apply only when
working in a specific project). Project-scoped strategies take precedence when both exist
for the same concern.

Follow active strategies. If a strategy seems counterproductive in context, say so
explicitly rather than silently ignoring it.
