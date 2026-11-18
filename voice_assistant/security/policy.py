from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Awaitable, Callable


class RiskLevel(IntEnum):
    SAFE = 0
    CONFIRM = 1
    DANGEROUS = 2
    FORBIDDEN = 3


class ApprovalRequired(PermissionError):
    """Raised when a non-safe action was not explicitly approved."""


@dataclass
class ApprovalGate:
    approve: Callable[[str], Awaitable[bool]]

    async def check(self, action: str, risk: RiskLevel, *, confirmed: bool = False) -> None:
        if risk == RiskLevel.FORBIDDEN:
            raise ApprovalRequired(f"Запрещённое действие: {action}")
        if risk == RiskLevel.SAFE or confirmed:
            return
        if not await self.approve(action):
            raise ApprovalRequired(f"Действие не подтверждено: {action}")
