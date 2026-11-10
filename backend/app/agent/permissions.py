"""Central permission engine. Levels are ordered; higher means more dangerous.

READ_ONLY=0  INTERACTIVE=1  MODIFY=2  DESTRUCTIVE=3  SYSTEM=4
A tool declares the minimum level it needs. Risky classes always require an
explicit confirmation unless the session pre-approved that exact tool+scope.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class Level(IntEnum):
    READ_ONLY = 0
    INTERACTIVE = 1
    MODIFY = 2
    DESTRUCTIVE = 3
    SYSTEM = 4


LEVEL_NAMES = {level: level.name.lower() for level in Level}

# Risk classes that may never be pre-approved for the whole session.
NEVER_PREAPPROVABLE = frozenset({"destructive", "system"})


@dataclass(frozen=True)
class Decision:
    allowed: bool
    needs_confirmation: bool
    reason: str


class PermissionEngine:
    """Enforces per-tool level ceilings and confirmation policy.

    `level_overrides` maps tool name -> maximum allowed Level. Tools absent
    from the map fall back to `default_ceiling`. `approved` holds session
    pre-approvals of the form "tool_name" granted by the user for this run.
    """

    def __init__(self, default_ceiling: Level = Level.INTERACTIVE,
                 level_overrides: dict[str, Level] | None = None,
                 approved: set[str] | None = None) -> None:
        self.default_ceiling = default_ceiling
        self.level_overrides = dict(level_overrides or {})
        self.approved = set(approved or ())

    def ceiling_for(self, tool_name: str) -> Level:
        return self.level_overrides.get(tool_name, self.default_ceiling)

    def check(self, tool_name: str, required: Level, risk_class: str) -> Decision:
        ceiling = self.ceiling_for(tool_name)
        if required > ceiling:
            return Decision(False, False,
                            f"{tool_name} requires {LEVEL_NAMES[required]} but ceiling is {LEVEL_NAMES[ceiling]}")
        needs_confirmation = required >= Level.MODIFY or risk_class in {"destructive", "system"}
        if needs_confirmation and risk_class not in NEVER_PREAPPROVABLE and tool_name in self.approved:
            needs_confirmation = False
        if needs_confirmation and required >= Level.DESTRUCTIVE:
            # Destructive/system always confirm per action; never session-approved.
            needs_confirmation = True
        return Decision(True, needs_confirmation,
                        "ok" if not needs_confirmation else f"{tool_name} requires explicit confirmation")

    def approve(self, tool_name: str, risk_class: str) -> bool:
        """Session pre-approval; refused for never-pre-approvable risk classes."""
        if risk_class in NEVER_PREAPPROVABLE:
            return False
        self.approved.add(tool_name)
        return True
