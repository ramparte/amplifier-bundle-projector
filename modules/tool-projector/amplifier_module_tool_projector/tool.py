"""Projector Tool - Project management and strategy tool for Amplifier.

Provides CRUD operations for projects, strategies, tasks, and session outcomes.
All state is stored as files on disk at ~/.amplifier/projector/.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from amplifier_core import ToolResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """Return current UTC time as ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe_name(name: str) -> str:
    """Sanitize a name for use as a directory/file component.

    Raises ValueError on path-traversal attempts or empty names.
    """
    if not name or not name.strip():
        raise ValueError("Name must not be empty")
    name = name.strip()
    # Reject path traversal
    if ".." in name or "/" in name or "\\" in name:
        raise ValueError(f"Invalid name (path traversal rejected): {name!r}")
    # Slugify: lowercase, replace non-alphanum with hyphens, collapse runs
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if not slug:
        raise ValueError(f"Name produces empty slug: {name!r}")
    return slug


def _read_yaml(path: Path) -> dict[str, Any]:
    """Read a YAML file, returning an empty dict if it doesn't exist."""
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    return yaml.safe_load(text) or {}


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    """Write data to a YAML file with human-friendly formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def _ok(result: Any) -> str:
    """Return a success JSON envelope."""
    return json.dumps({"ok": True, "result": result}, indent=2, default=str)


def _err(message: str) -> str:
    """Return an error JSON envelope."""
    return json.dumps({"ok": False, "error": message})


# ---------------------------------------------------------------------------
# Task ID generation
# ---------------------------------------------------------------------------


def _project_prefix(project_name: str) -> str:
    """Derive a short uppercase prefix from a project name.

    'amplifier-core' -> 'AC', 'projector' -> 'PRO', 'my-big-project' -> 'MBP'
    """
    parts = project_name.split("-")
    if len(parts) >= 2:
        return "".join(p[0] for p in parts if p).upper()
    # Single word: first 3 chars
    return project_name[:3].upper()


def _next_task_id(tasks: list[dict[str, Any]], prefix: str) -> str:
    """Generate the next sequential task ID for a project."""
    max_num = 0
    pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)$")
    for t in tasks:
        m = pattern.match(t.get("id", ""))
        if m:
            max_num = max(max_num, int(m.group(1)))
    return f"{prefix}-{max_num + 1:03d}"


# ---------------------------------------------------------------------------
# ProjectorTool
# ---------------------------------------------------------------------------

OPERATIONS = [
    "list_projects",
    "get_project",
    "update_project",
    "create_project",
    "list_strategies",
    "get_strategy",
    "set_strategy",
    "toggle_strategy",
    "add_task",
    "update_task",
    "list_tasks",
    "log_outcome",
    "get_status",
]


class ProjectorTool:
    """Amplifier tool for managing projects, strategies, tasks, and outcomes.

    All state lives as flat files under a configurable base directory
    (default ``~/.amplifier/projector/``).
    """

    # -- Amplifier Tool protocol ------------------------------------------------

    name: str = "projector"
    description: str = (
        "Manage projects, strategies, tasks, and session outcomes for the "
        "Projector system. Supports CRUD on projects and strategies, task "
        "tracking, outcome logging, and cross-project status queries."
    )

    @property
    def input_schema(self) -> dict[str, Any]:
        """JSON Schema describing the tool's input."""
        return {
            "type": "object",
            "required": ["operation"],
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": OPERATIONS,
                    "description": "The operation to perform.",
                },
                "project": {
                    "type": "string",
                    "description": "Project name (for project-specific operations).",
                },
                "strategy": {
                    "type": "string",
                    "description": "Strategy name (for strategy-specific operations).",
                },
                "data": {
                    "type": "object",
                    "description": "Payload for create/update/log operations.",
                },
                "query": {
                    "type": "string",
                    "description": "Optional query or filter for status/list operations.",
                },
            },
        }

    # -- Init -------------------------------------------------------------------

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        config = config or {}
        base = config.get("base_path", "~/.amplifier/projector")
        self._base = Path(base).expanduser().resolve()

    @property
    def _projects_dir(self) -> Path:
        return self._base / "projects"

    @property
    def _strategies_dir(self) -> Path:
        return self._base / "strategies"

    # -- Execute (dispatch) -----------------------------------------------------

    async def execute(self, input: dict[str, Any]) -> ToolResult:
        """Dispatch to the appropriate operation handler."""
        op = input.get("operation")
        if not op:
            return ToolResult(success=False, error={"message": "Missing required parameter: operation"})
        if op not in OPERATIONS:
            return ToolResult(success=False, error={"message": f"Unknown operation: {op!r}. Valid: {', '.join(OPERATIONS)}"})

        handler = getattr(self, f"_op_{op}", None)
        if handler is None:  # pragma: no cover
            return ToolResult(success=False, error={"message": f"Operation {op!r} is not implemented"})

        try:
            result = handler(input)
            return ToolResult(success=True, output=result)
        except ValueError as exc:
            return ToolResult(success=False, error={"message": str(exc)})
        except Exception as exc:
            return ToolResult(success=False, error={"message": f"Unexpected error in {op}: {exc}"})

    # ===================================================================
    # PROJECT operations
    # ===================================================================

    def _op_list_projects(self, args: dict[str, Any]) -> str:
        """List all project definitions with status."""
        if not self._projects_dir.exists():
            return _ok([])

        projects: list[dict[str, Any]] = []
        for proj_dir in sorted(self._projects_dir.iterdir()):
            pfile = proj_dir / "project.yaml"
            if not pfile.exists():
                continue
            data = _read_yaml(pfile)
            projects.append(
                {
                    "name": proj_dir.name,
                    "title": data.get("title", proj_dir.name),
                    "status": data.get("status", "unknown"),
                    "updated": data.get("updated", ""),
                }
            )
        return _ok(projects)

    def _op_get_project(self, args: dict[str, Any]) -> str:
        """Get a specific project's full state."""
        name = _safe_name(args.get("project", ""))
        proj_dir = self._projects_dir / name
        pfile = proj_dir / "project.yaml"

        if not pfile.exists():
            return _err(f"Project not found: {name}")

        project = _read_yaml(pfile)

        # Attach recent outcomes (last 20)
        outcomes_file = proj_dir / "outcomes.jsonl"
        recent_outcomes: list[dict[str, Any]] = []
        if outcomes_file.exists():
            lines = outcomes_file.read_text(encoding="utf-8").strip().splitlines()
            for line in lines[-20:]:
                try:
                    recent_outcomes.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        # Attach tasks
        tasks = _read_yaml(proj_dir / "tasks.yaml").get("tasks", [])

        return _ok(
            {
                "project": project,
                "recent_outcomes": recent_outcomes,
                "tasks": tasks,
            }
        )

    def _op_create_project(self, args: dict[str, Any]) -> str:
        """Create a new project definition."""
        name = _safe_name(args.get("project", ""))
        data: dict[str, Any] = args.get("data") or {}

        proj_dir = self._projects_dir / name
        pfile = proj_dir / "project.yaml"

        if pfile.exists():
            return _err(f"Project already exists: {name}")

        project = {
            "name": name,
            "title": data.get("title", name),
            "status": data.get("status", "active"),
            "description": data.get("description", ""),
            "relationships": data.get("relationships", []),
            "notes": data.get("notes", ""),
            "created": _now_iso(),
            "updated": _now_iso(),
        }
        # Merge any extra fields from data
        for k, v in data.items():
            if k not in project:
                project[k] = v

        _write_yaml(pfile, project)
        return _ok({"created": name, "project": project})

    def _op_update_project(self, args: dict[str, Any]) -> str:
        """Update a project's fields."""
        name = _safe_name(args.get("project", ""))
        data: dict[str, Any] = args.get("data") or {}

        if not data:
            return _err("No data provided for update")

        pfile = self._projects_dir / name / "project.yaml"
        if not pfile.exists():
            return _err(f"Project not found: {name}")

        project = _read_yaml(pfile)
        # Don't allow overwriting structural keys via casual update
        protected = {"name", "created"}
        for k, v in data.items():
            if k not in protected:
                project[k] = v
        project["updated"] = _now_iso()

        _write_yaml(pfile, project)
        return _ok({"updated": name, "project": project})

    # ===================================================================
    # STRATEGY operations
    # ===================================================================

    def _op_list_strategies(self, args: dict[str, Any]) -> str:
        """List all strategies with active/inactive status."""
        if not self._strategies_dir.exists():
            return _ok([])

        strategies: list[dict[str, Any]] = []
        for sfile in sorted(self._strategies_dir.glob("*.yaml")):
            data = _read_yaml(sfile)
            strategies.append(
                {
                    "name": sfile.stem,
                    "title": data.get("title", sfile.stem),
                    "active": data.get("active", True),
                    "updated": data.get("updated", ""),
                }
            )
        return _ok(strategies)

    def _op_get_strategy(self, args: dict[str, Any]) -> str:
        """Get a specific strategy's full definition."""
        name = _safe_name(args.get("strategy", ""))
        sfile = self._strategies_dir / f"{name}.yaml"

        if not sfile.exists():
            return _err(f"Strategy not found: {name}")

        return _ok(_read_yaml(sfile))

    def _op_set_strategy(self, args: dict[str, Any]) -> str:
        """Create or update a strategy."""
        name = _safe_name(args.get("strategy", ""))
        data: dict[str, Any] = args.get("data") or {}

        if not data:
            return _err("No data provided for strategy")

        sfile = self._strategies_dir / f"{name}.yaml"
        existing = _read_yaml(sfile) if sfile.exists() else {}

        strategy = {
            "name": name,
            "title": data.get("title", existing.get("title", name)),
            "active": data.get("active", existing.get("active", True)),
            "description": data.get("description", existing.get("description", "")),
            "guidelines": data.get("guidelines", existing.get("guidelines", [])),
            "updated": _now_iso(),
        }
        if not existing:
            strategy["created"] = _now_iso()
        else:
            strategy["created"] = existing.get("created", _now_iso())

        # Merge any extra fields
        for k, v in data.items():
            if k not in strategy:
                strategy[k] = v

        _write_yaml(sfile, strategy)
        created = not bool(existing)
        return _ok(
            {
                "action": "created" if created else "updated",
                "strategy": strategy,
            }
        )

    def _op_toggle_strategy(self, args: dict[str, Any]) -> str:
        """Enable or disable a strategy."""
        name = _safe_name(args.get("strategy", ""))
        sfile = self._strategies_dir / f"{name}.yaml"

        if not sfile.exists():
            return _err(f"Strategy not found: {name}")

        strategy = _read_yaml(sfile)
        was_active = strategy.get("active", True)
        strategy["active"] = not was_active
        strategy["updated"] = _now_iso()

        _write_yaml(sfile, strategy)
        return _ok(
            {
                "name": name,
                "active": strategy["active"],
                "changed_from": was_active,
            }
        )

    # ===================================================================
    # TASK operations
    # ===================================================================

    def _read_tasks(self, project_name: str) -> tuple[Path, list[dict[str, Any]]]:
        """Read the task list for a project. Returns (path, tasks)."""
        tfile = self._projects_dir / project_name / "tasks.yaml"
        data = _read_yaml(tfile)
        return tfile, data.get("tasks", [])

    def _write_tasks(self, tfile: Path, tasks: list[dict[str, Any]]) -> None:
        """Write the task list back to disk."""
        _write_yaml(tfile, {"tasks": tasks})

    def _op_add_task(self, args: dict[str, Any]) -> str:
        """Add a task to a project."""
        name = _safe_name(args.get("project", ""))
        data: dict[str, Any] = args.get("data") or {}

        pfile = self._projects_dir / name / "project.yaml"
        if not pfile.exists():
            return _err(f"Project not found: {name}")

        if not data.get("title"):
            return _err("Task requires a 'title' in data")

        tfile, tasks = self._read_tasks(name)
        prefix = _project_prefix(name)
        task_id = _next_task_id(tasks, prefix)

        task: dict[str, Any] = {
            "id": task_id,
            "title": data["title"],
            "status": data.get("status", "todo"),
            "priority": data.get("priority", "normal"),
            "notes": data.get("notes", ""),
            "created": _now_iso(),
            "updated": _now_iso(),
        }
        # Merge extra fields
        for k, v in data.items():
            if k not in task:
                task[k] = v

        tasks.append(task)
        self._write_tasks(tfile, tasks)
        return _ok({"added": task})

    def _op_update_task(self, args: dict[str, Any]) -> str:
        """Update a task's status or details."""
        name = _safe_name(args.get("project", ""))
        data: dict[str, Any] = args.get("data") or {}
        task_id = data.get("id", "")

        if not task_id:
            return _err("Task update requires 'id' in data")

        pfile = self._projects_dir / name / "project.yaml"
        if not pfile.exists():
            return _err(f"Project not found: {name}")

        tfile, tasks = self._read_tasks(name)

        target = None
        for t in tasks:
            if t.get("id") == task_id:
                target = t
                break

        if target is None:
            return _err(f"Task not found: {task_id}")

        protected = {"id", "created"}
        for k, v in data.items():
            if k not in protected:
                target[k] = v
        target["updated"] = _now_iso()

        self._write_tasks(tfile, tasks)
        return _ok({"updated": target})

    def _op_list_tasks(self, args: dict[str, Any]) -> str:
        """List tasks for a specific project or across all projects."""
        project_name = args.get("project", "")
        query = args.get("query", "")  # optional status filter

        all_tasks: list[dict[str, Any]] = []

        if project_name:
            name = _safe_name(project_name)
            pfile = self._projects_dir / name / "project.yaml"
            if not pfile.exists():
                return _err(f"Project not found: {name}")
            _, tasks = self._read_tasks(name)
            for t in tasks:
                t["project"] = name
            all_tasks = tasks
        else:
            # All projects
            if self._projects_dir.exists():
                for proj_dir in sorted(self._projects_dir.iterdir()):
                    if not (proj_dir / "project.yaml").exists():
                        continue
                    _, tasks = self._read_tasks(proj_dir.name)
                    for t in tasks:
                        t["project"] = proj_dir.name
                    all_tasks.extend(tasks)

        # Filter by status if query looks like a status
        if query:
            q = query.lower()
            all_tasks = [
                t
                for t in all_tasks
                if q in t.get("status", "").lower() or q in t.get("title", "").lower()
            ]

        return _ok(all_tasks)

    # ===================================================================
    # OUTCOME operations
    # ===================================================================

    def _op_log_outcome(self, args: dict[str, Any]) -> str:
        """Append a session outcome to a project's log."""
        name = _safe_name(args.get("project", ""))
        data: dict[str, Any] = args.get("data") or {}

        pfile = self._projects_dir / name / "project.yaml"
        if not pfile.exists():
            return _err(f"Project not found: {name}")

        if not data.get("summary"):
            return _err("Outcome requires a 'summary' in data")

        outcome: dict[str, Any] = {
            "timestamp": _now_iso(),
            "summary": data["summary"],
            "tags": data.get("tags", []),
            "session_id": data.get("session_id", ""),
            "details": data.get("details", ""),
        }

        outcomes_file = self._projects_dir / name / "outcomes.jsonl"
        outcomes_file.parent.mkdir(parents=True, exist_ok=True)
        with outcomes_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(outcome, default=str) + "\n")

        return _ok({"logged": outcome})

    # ===================================================================
    # STATUS operation
    # ===================================================================

    def _op_get_status(self, args: dict[str, Any]) -> str:
        """Cross-project status summary: what needs attention, recent activity."""
        status: dict[str, Any] = {
            "timestamp": _now_iso(),
            "projects": [],
            "strategies": {"active": 0, "inactive": 0, "list": []},
            "attention": [],
            "recent_outcomes": [],
        }

        # -- Projects ----------------------------------------------------------
        if self._projects_dir.exists():
            for proj_dir in sorted(self._projects_dir.iterdir()):
                pfile = proj_dir / "project.yaml"
                if not pfile.exists():
                    continue
                project = _read_yaml(pfile)
                name = proj_dir.name

                # Task counts
                _, tasks = self._read_tasks(name)
                task_counts: dict[str, int] = {}
                for t in tasks:
                    s = t.get("status", "unknown")
                    task_counts[s] = task_counts.get(s, 0) + 1

                # Recent outcomes count
                outcomes_file = proj_dir / "outcomes.jsonl"
                outcome_count = 0
                latest_outcome: dict[str, Any] | None = None
                if outcomes_file.exists():
                    lines = (
                        outcomes_file.read_text(encoding="utf-8").strip().splitlines()
                    )
                    outcome_count = len(lines)
                    if lines:
                        try:
                            latest_outcome = json.loads(lines[-1])
                        except json.JSONDecodeError:
                            pass

                proj_summary = {
                    "name": name,
                    "title": project.get("title", name),
                    "status": project.get("status", "unknown"),
                    "task_counts": task_counts,
                    "outcome_count": outcome_count,
                    "updated": project.get("updated", ""),
                }
                status["projects"].append(proj_summary)

                # -- Attention signals -----------------------------------------
                # Stale: no update in project.yaml and no recent outcomes
                if project.get("status") == "active" and not tasks:
                    status["attention"].append(
                        {
                            "project": name,
                            "signal": "active_no_tasks",
                            "message": f"Project '{name}' is active but has no tasks.",
                        }
                    )

                blocked = [t for t in tasks if t.get("status") == "blocked"]
                if blocked:
                    status["attention"].append(
                        {
                            "project": name,
                            "signal": "blocked_tasks",
                            "message": (
                                f"Project '{name}' has {len(blocked)} blocked "
                                f"task(s): {', '.join(t['id'] for t in blocked)}."
                            ),
                        }
                    )

                if latest_outcome:
                    status["recent_outcomes"].append(
                        {
                            "project": name,
                            **latest_outcome,
                        }
                    )

        # -- Strategies --------------------------------------------------------
        if self._strategies_dir.exists():
            for sfile in sorted(self._strategies_dir.glob("*.yaml")):
                data = _read_yaml(sfile)
                is_active = data.get("active", True)
                if is_active:
                    status["strategies"]["active"] += 1
                else:
                    status["strategies"]["inactive"] += 1
                status["strategies"]["list"].append(
                    {
                        "name": sfile.stem,
                        "active": is_active,
                    }
                )

        # Sort recent outcomes by timestamp (newest first)
        status["recent_outcomes"].sort(
            key=lambda o: o.get("timestamp", ""),
            reverse=True,
        )

        return _ok(status)
