"""Amplifier Projector session hooks.

Injects active strategies and project context at session start,
captures session outcomes at session end.
"""

from .hook import mount

__all__ = ["mount"]
