import asyncio

import pytest

from hub_service.services.reminder_service import HubPipelineService, ReminderService


class StubOutboundSuccess:
    def __init__(self) -> None:
        self.agent_calls: list[str] = []
        self.reply_calls: list[tuple[str, str]] = []

    async def call_agent(self, session_id: str, user_message: str) -> str:
        self.agent_calls.append(f"{session_id}:{user_message}")
        return f"reply:{user_message}"

    async def send_reply(self, session_id: str, content: str) -> None:
        self.reply_calls.append((session_id, content))


class StubOutboundAgentFail(StubOutboundSuccess):
    async def call_agent(self, session_id: str, user_message: str) -> str:
        raise RuntimeError("agent failed")


class StubOutboundReplyFail(StubOutboundSuccess):
    async def send_reply(self, session_id: str, content: str) -> None:
        raise RuntimeError("reply failed")


def test_private_event_adds_reminder_and_sends_reply() -> None:
    reminder_service = ReminderService()
    outbound = StubOutboundSuccess()
    pipeline = HubPipelineService(reminder_service=reminder_service, outbound_service=outbound)

    asyncio.run(
        pipeline.handle_private_event(
            user_id="qq_1",
            session_id="private_1",
            content="hello",
            raw_event={"x": 1},
        )
    )

    reminders = reminder_service.list_reminders("qq_1")
    assert len(reminders) == 1
    assert reminders[0].content == "hello"
    assert outbound.agent_calls == ["private_1:hello"]
    assert outbound.reply_calls == [("private_1", "reply:hello")]


def test_agent_failure_raises() -> None:
    reminder_service = ReminderService()
    outbound = StubOutboundAgentFail()
    pipeline = HubPipelineService(reminder_service=reminder_service, outbound_service=outbound)

    with pytest.raises(RuntimeError):
        asyncio.run(
            pipeline.handle_private_event(
                user_id="qq_2",
                session_id="private_2",
                content="hello",
                raw_event={"x": 1},
            )
        )

    reminders = reminder_service.list_reminders("qq_2")
    assert len(reminders) == 1


def test_reply_failure_raises() -> None:
    reminder_service = ReminderService()
    outbound = StubOutboundReplyFail()
    pipeline = HubPipelineService(reminder_service=reminder_service, outbound_service=outbound)

    with pytest.raises(RuntimeError):
        asyncio.run(
            pipeline.handle_private_event(
                user_id="qq_3",
                session_id="private_3",
                content="hello",
                raw_event={"x": 1},
            )
        )

    reminders = reminder_service.list_reminders("qq_3")
    assert len(reminders) == 1


def test_reminders_are_isolated_by_user() -> None:
    reminder_service = ReminderService()

    reminder_service.add_reminder("qq_1", "private_1", "a", {"x": 1})
    reminder_service.add_reminder("qq_2", "private_2", "b", {"x": 2})

    assert [x.content for x in reminder_service.list_reminders("qq_1")] == ["a"]
    assert [x.content for x in reminder_service.list_reminders("qq_2")] == ["b"]
