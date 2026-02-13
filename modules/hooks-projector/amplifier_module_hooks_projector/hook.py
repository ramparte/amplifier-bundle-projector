"""Projector hook implementation.

Registers hooks that bridge the Projector system (strategies, projects,
outcomes) into live Amplifier sessions.

provider:request - Injects active strategies + detected project context
                   as ephemeral user-role content right before each LLM call.
                   This places strategies at the highest-attention position
                   (matches the hooks-status-context pattern).
session:end      - Captures a best-effort outcome summary to the project log.
"""

from __future__ import annotations

import json
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from amplifier_core.hooks import HookResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public mount point - called by the Amplifier coordinator
# ---------------------------------------------------------------------------


async def mount(coordinator: Any, config: dict) -> None:
    """Mount projector hooks onto the coordinator."""
    # Resolve working_dir from session capability (same pattern as hooks-status-context)
    if "working_dir" not in config:
        working_dir = coordinator.get_capability("session.working_dir")
        if working_dir:
            config = {**config, "working_dir": working_dir}

    hook = ProjectorHook(config, coordinator=coordinator)
    coordinator.hooks.register(
        "provider:request",
        hook.on_provider_request,
        priority=50,
        name="hooks-projector",
    )
    coordinator.hooks.register(
        "session:end",
        hook.on_session_end,
        priority=50,
        name="hooks-projector-end",
    )


# ---------------------------------------------------------------------------
# Hook implementation
# ---------------------------------------------------------------------------


class ProjectorHook:
    """Injects project context on provider:request, captures outcomes on end."""

    def __init__(self, config: dict, coordinator: Any = None) -> None:
        self._coordinator = coordinator
        self.strategies_path: Path = Path(
            config.get("strategies_path", "~/.amplifier/projector/strategies")
        ).expanduser()
        self.projects_path: Path = Path(
            config.get("projects_path", "~/.amplifier/projector/projects")
        ).expanduser()
        self.session_filter: str = config.get("session_filter", "root_only")
        self.max_recent_outcomes: int = int(config.get("max_recent_outcomes", 5))

        # Working directory - resolved once at mount time from session capability
        self._working_dir: str = config.get("working_dir", "")

        # Cache: built once on first provider:request, reused for the session.
        # Strategies and project context don't change mid-session.
        self._cached_injection: str | None = None

    # -- helpers: safety ------------------------------------------------

    def _is_safe_path(self, path: Path, root: Path) -> bool:
        """Verify *path* is contained within *root* (prevent traversal)."""
        try:
            path.resolve().relative_to(root.resolve())
            return True
        except ValueError:
            return False

    def _is_root_session(self) -> bool:
        """Return True when this session is a root session (not a sub-agent)."""
        if self.session_filter != "root_only":
            return True
        if self._coordinator is None:
            return True
        try:
            parent_id = self._coordinator.parent_id
            return parent_id is None
        except AttributeError:
            return True

    # -- helpers: YAML file loading ------------------------------------

    def _read_yaml(self, path: Path) -> dict:
        """Read a YAML file, returning ``{}`` on any error."""
        try:
            if not path.is_file():
                return {}
            text = path.read_text(encoding="utf-8")
            data = yaml.safe_load(text)
            return data if isinstance(data, dict) else {}
        except Exception:
            logger.debug("Failed to read YAML: %s", path, exc_info=True)
            return {}

    # -- strategies ----------------------------------------------------

    def _load_active_strategies(self) -> list[dict]:
        """Load every active strategy from the strategies directory.

        A strategy file is YAML with at minimum::

            name: str
            active: bool
            injection: str
        """
        strategies: list[dict] = []
        if not self.strategies_path.is_dir():
            return strategies

        for path in sorted(self.strategies_path.glob("*.yaml")):
            if not self._is_safe_path(path, self.strategies_path):
                continue
            data = self._read_yaml(path)
            if data.get("active") and data.get("injection"):
                strategies.append(data)

        return strategies

    # -- projects ------------------------------------------------------

    def _load_all_projects(self) -> list[dict]:
        """Load every project definition from the projects directory.

        Each project lives in ``projects/<slug>/project.yaml``.
        """
        projects: list[dict] = []
        if not self.projects_path.is_dir():
            return projects

        for project_dir in sorted(self.projects_path.iterdir()):
            if not project_dir.is_dir():
                continue
            if not self._is_safe_path(project_dir, self.projects_path):
                continue
            data = self._read_yaml(project_dir / "project.yaml")
            if data:
                data.setdefault("slug", project_dir.name)
                data["_dir"] = project_dir
                projects.append(data)

        return projects

    def _detect_project(self, working_dir: str) -> dict | None:
        """Detect which project the session belongs to.

        Resolution order:
        1. Git remote URL matched against project ``repos`` list.
        2. Directory-name heuristic against repo slugs.
        """
        if not working_dir:
            return None
        resolved = Path(working_dir).resolve()
        projects = self._load_all_projects()

        # --- try git remote first ---
        try:
            result = subprocess.run(
                ["git", "-C", str(resolved), "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                remote_url = result.stdout.strip()
                for project in projects:
                    for repo in project.get("repos", []):
                        if repo in remote_url:
                            return project
        except Exception:
            pass

        # --- fall back to path matching ---
        resolved_str = str(resolved)
        for project in projects:
            for repo in project.get("repos", []):
                repo_name = repo.rstrip("/").split("/")[-1]
                if repo_name and repo_name in resolved_str:
                    return project

        return None

    def _load_recent_outcomes(self, project_dir: Path) -> list[dict]:
        """Return the last N outcome entries for a project."""
        outcomes_file = project_dir / "outcomes.jsonl"
        if not outcomes_file.is_file():
            return []
        if not self._is_safe_path(outcomes_file, self.projects_path):
            return []

        entries: list[dict] = []
        try:
            for line in outcomes_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        except Exception:
            logger.debug("Failed reading outcomes: %s", outcomes_file, exc_info=True)
            return []

        return entries[-self.max_recent_outcomes :]

    def _load_active_tasks(self, project_dir: Path) -> list[dict]:
        """Return active tasks for a project from ``tasks.yaml``."""
        tasks_file = project_dir / "tasks.yaml"
        if not self._is_safe_path(tasks_file, self.projects_path):
            return []
        data = self._read_yaml(tasks_file)
        tasks = data.get("tasks", [])
        if not isinstance(tasks, list):
            return []
        return [t for t in tasks if isinstance(t, dict) and t.get("status") != "done"]

    # -- context building -----------------------------------------------

    def _build_context(self) -> str:
        """Assemble the full injection text from strategies + project state."""
        sections: list[str] = []

        # --- active strategies ---
        strategies = self._load_active_strategies()
        if strategies:
            lines = ["## Active Strategies", ""]
            for strat in strategies:
                name = strat.get("name", "Unnamed")
                text = strat["injection"].strip()
                lines.append(f"### {name}")
                lines.append(text)
                lines.append("")
            sections.append("\n".join(lines))

        # --- project context (using working_dir from session capability) ---
        project = self._detect_project(self._working_dir)

        if project:
            project_dir: Path = project["_dir"]
            name = project.get("name", project.get("slug", "unknown"))

            proj_lines = [f"## Current Project: {name}", ""]

            description = project.get("description", "")
            if description:
                proj_lines.append(description.strip())
                proj_lines.append("")

            notes = project.get("notes", "")
            if notes:
                proj_lines.append(f"**Notes:** {notes.strip()}")
                proj_lines.append("")

            sections.append("\n".join(proj_lines))

            # --- recent outcomes ---
            outcomes = self._load_recent_outcomes(project_dir)
            if outcomes:
                out_lines = ["## Recent Session Outcomes", ""]
                for entry in outcomes:
                    ts = entry.get("timestamp", "?")
                    summary = entry.get("summary", "(no summary)")
                    out_lines.append(f"- **{ts}**: {summary}")
                out_lines.append("")
                sections.append("\n".join(out_lines))

            # --- active tasks ---
            tasks = self._load_active_tasks(project_dir)
            if tasks:
                task_lines = ["## Active Tasks", ""]
                for task in tasks:
                    title = task.get("title", task.get("name", "(untitled)"))
                    status = task.get("status", "")
                    suffix = f" [{status}]" if status else ""
                    task_lines.append(f"- {title}{suffix}")
                task_lines.append("")
                sections.append("\n".join(task_lines))

        return "\n".join(sections).strip()

    # -- event handlers -------------------------------------------------

    async def on_provider_request(self, event: str, data: dict) -> HookResult:
        """Inject strategies and project context before each LLM call.

        Uses ephemeral=True so content is injected fresh each request
        (highest-attention position) without accumulating in stored context.
        Matches the hooks-status-context pattern.
        """
        if not self._is_root_session():
            return HookResult(action="continue")

        # Build once, cache for the session
        if self._cached_injection is None:
            try:
                context = self._build_context()
            except Exception:
                logger.warning("Projector hook: context build failed", exc_info=True)
                context = ""
            self._cached_injection = context

        if not self._cached_injection:
            return HookResult(action="continue")

        injection = (
            '<system-reminder source="hooks-projector">\n'
            f"{self._cached_injection}\n"
            "</system-reminder>"
        )

        return HookResult(
            action="inject_context",
            context_injection=injection,
            context_injection_role="user",
            ephemeral=True,
            suppress_output=True,
        )

    async def on_session_end(self, event: str, event_data: dict) -> HookResult:
        """Capture a best-effort session outcome to the project log.

        Intentionally simple -- records what we can determine from session
        metadata alone.  A richer LLM-based summariser can be layered on
        later.
        """
        if not self._is_root_session():
            return HookResult(action="continue")

        try:
            self._capture_outcome(event_data)
        except Exception:
            # Never let outcome capture crash a session.
            logger.debug("Projector hook: outcome capture failed", exc_info=True)

        return HookResult(action="continue")

    # -- outcome capture ------------------------------------------------

    def _capture_outcome(self, event_data: dict) -> None:
        """Write an outcome record to the project's ``outcomes.jsonl``.

        Uses self._working_dir (resolved from session.working_dir capability
        at mount time) instead of relying on event_data which may not
        contain working_dir.
        """
        # Try event_data first, fall back to the session capability we stored
        working_dir = event_data.get("working_dir", "") or self._working_dir
        project = self._detect_project(working_dir) if working_dir else None
        if project is None:
            return

        project_dir: Path = project["_dir"]
        if not self._is_safe_path(project_dir, self.projects_path):
            return

        summary = event_data.get("summary", "")
        if not summary:
            summary = self._derive_summary(event_data)

        # Also try to get session_id from coordinator if not in event_data
        session_id = event_data.get("session_id", "")
        if not session_id and self._coordinator is not None:
            try:
                session_id = self._coordinator.session_id or ""
            except AttributeError:
                pass

        # Build a description from whatever we have even if summary is empty
        if not summary:
            summary = f"Session {session_id[:8]}..." if session_id else "(no summary)"

        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "session_id": session_id,
            "project": project.get("slug", project.get("name", "")),
            "summary": summary,
            "tasks_completed": event_data.get("tasks_completed", []),
            "tasks_created": event_data.get("tasks_created", []),
        }

        outcomes_file = project_dir / "outcomes.jsonl"
        try:
            outcomes_file.parent.mkdir(parents=True, exist_ok=True)
            with outcomes_file.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, separators=(",", ":")) + "\n")
        except Exception:
            logger.debug("Failed to write outcome: %s", outcomes_file, exc_info=True)

    @staticmethod
    def _derive_summary(event_data: dict) -> str:
        """Build a minimal summary from whatever metadata is available."""
        parts: list[str] = []

        title = event_data.get("title", "")
        if title:
            parts.append(title)

        topic = event_data.get("topic", "")
        if topic and topic != title:
            parts.append(topic)

        if not parts:
            return ""

        return " - ".join(parts)
