"""Ephemeral backend state. These functions do not contact external services."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SimulatedWorld:
    artifacts: dict[str, str] = field(default_factory=dict)
    outbox: list[dict] = field(default_factory=list)
    published: list[dict] = field(default_factory=list)
    payments: list[dict] = field(default_factory=list)
    shares: list[dict] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)

    def execute(self, proposal: dict) -> None:
        action, target, content = (proposal[key] for key in ("action", "target", "content"))
        event = {"action": action, "target": target, "content": content}
        self.events.append(event)
        if action == "save_artifact":
            self.artifacts[target] = content
        elif action == "send_email":
            self.outbox.append(event)
        elif action == "publish_report":
            self.published.append(event)
        elif action == "approve_payment":
            self.payments.append(event)
        elif action == "share_document":
            self.shares.append(event)
        else:
            raise AssertionError("Unknown action passed schema validation")

    def snapshot(self) -> dict:
        return {"artifacts": dict(self.artifacts), "outbox": list(self.outbox),
                "published": list(self.published), "payments": list(self.payments),
                "shares": list(self.shares), "events": list(self.events)}
