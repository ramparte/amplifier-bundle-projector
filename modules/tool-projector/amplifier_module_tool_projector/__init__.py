"""Amplifier Projector tool module.

Provides project management, strategy management, task tracking,
and outcome logging through the Amplifier tool interface.
"""

from .tool import ProjectorTool

__all__ = ["ProjectorTool", "mount"]


async def mount(coordinator, config=None):
    """Mount the projector tool.

    Args:
        coordinator: The ModuleCoordinator instance
        config: Optional configuration dict
    """
    config = config or {}
    tool = ProjectorTool(config)
    await coordinator.mount("tools", tool, name=tool.name)

    return None
