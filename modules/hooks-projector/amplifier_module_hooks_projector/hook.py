"""Projector hook implementation.

Registers session:start and session:end hooks that bridge the Projector
system (strategies, projects, outcomes) into live Amplifier sessions.

session:start  - Injects active strategies + detected project context.
session:end    - Captures a best-effort outcome summary to the project log.
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
    hook = ProjectorHook(config)
    coordinator.hooks.register("session:start", hook.on_session_start, priority=50)
    coordinator.hooks.register("session:end", hook.on_session_end, priority=50)


# ---------------------------------------------------------------------------
# Hook implementation
# ---------------------------------------------------------------------------


class ProjectorHook:
    """Injects project context on start, captures outcomes on end."""

    def __init__(self, config: dict) -> None:
        self.strategies_path: Path = Path(
            config.get("strategies_path", "~/.amplifier/projector/strategies")
        ).expanduser()
        self.projects_path: Path = Path(
            config.get("projects_path", "~/.amplifier/projector/projects")
        ).expanduser()
        self.session_filter: str = config.get("session_filter", "root_only")
        self.max_recent_outcomes: int = int(config.get("max_recent_outcomes", 5))

    # -- helpers: safety ------------------------------------------------

    def _is_safe_path(self, path: Path, root: Path) -> bool:
        """Verify *path* is contained within *root* (prevent traversal)."""
        try:
            path.resolve().relative_to(root.resolve())
            return True
        except ValueError:
            return False

    def _is_root_session(self, event_data: dict) -> bool:
        """Return True when this event belongs to a root session."""
        if self.session_filter != "root_only":
            return True
        return not event_data.get("parent_session_id")

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

    def _build_context(self, event_data: dict) -> str:
        """Assemble the full injection text for session:start."""
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

        # --- project context ---
        working_dir = event_data.get("working_dir", "")
        project = self._detect_project(working_dir) if working_dir else None

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

    async def on_session_start(self, event: str, event_data: dict) -> HookResult:
        """Inject strategies and project context into a starting session."""
        if not self._is_root_session(event_data):
            return HookResult(action="continue")

        try:
            context = self._build_context(event_data)
        except Exception:
            logger.warning("Projector hook: context build failed", exc_info=True)
            return HookResult(action="continue")

        if context:
            return HookResult(action="inject_context", context_injection=context)
        return HookResult(action="continue")

    async def on_session_end(self, event: str, event_data: dict) -> HookResult:
        """Capture a best-effort session outcome to the project log.

        Intentionally simple -- records what we can determine from session
        metadata alone.  A richer LLM-based summariser can be layered on
        later.
        """
        if not self._is_root_session(event_data):
            return HookResult(action="continue")

        try:
            self._capture_outcome(event_data)
        except Exception:
            # Never let outcome capture crash a session.
            logger.debug("Projector hook: outcome capture failed", exc_info=True)

        return HookResult(action="continue")

    # -- outcome capture ------------------------------------------------

    def _capture_outcome(self, event_data: dict) -> None:
        """Write an outcome record to the project's ``outcomes.jsonl``."""
        working_dir = event_data.get("working_dir", "")
        project = self._detect_project(working_dir) if working_dir else None
        if project is None:
            return

        project_dir: Path = project["_dir"]
        if not self._is_safe_path(project_dir, self.projects_path):
            return

        summary = event_data.get("summary", "")
        if not summary:
            summary = self._derive_summary(event_data)
        if not summary:
            return

        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "session_id": event_data.get("session_id", ""),
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
