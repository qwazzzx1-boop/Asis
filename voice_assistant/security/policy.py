from __future__ import annotations
from dataclasses import dataclass
from enum import IntEnum
from typing import Awaitable, Callable


class RiskLevel(IntEnum):
    SAFE = 0
    CONFIRM = 1
    DANGEROUS = 2


class ApprovalRequired(PermissionError):
    pass


@dataclass
class ApprovalGate:
    approve: Callable[[str], Awaitable[bool]]

    async def check(self, action: str, risk: RiskLevel, *, confirmed: bool = False) -> None:
        if risk == RiskLevel.SAFE:
            return
        if confirmed:
            return
        if not await self.approve(action):
            raise ApprovalRequired(f"Action was not approved: {action}")
