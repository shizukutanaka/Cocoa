"""Tests for avatar_agent module."""
import os
import sys
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'main'))


class TestAgentSession(unittest.TestCase):
    def test_creation(self):
        from avatar_agent import AgentSession
        now = datetime.now(timezone.utc)
        s = AgentSession(
            session_id="sess_1",
            agent_id="agent_1",
            client_id="client_1",
            start_time=now,
            last_activity=now,
        )
        self.assertEqual(s.session_id, "sess_1")
        self.assertEqual(s.message_count, 0)


class TestAgenticTask(unittest.TestCase):
    def test_creation(self):
        from avatar_agent import AgenticTask
        task = AgenticTask(
            task_id="t1",
            task_type="greeting",
            priority=1,
            context={"user": "Alice"},
            trigger_conditions={"time": "morning"},
            action_sequence=["say_hello", "ask_how_are_you"],
        )
        self.assertEqual(task.status, "pending")
        self.assertIsNone(task.completed_at)

    def test_status_default(self):
        from avatar_agent import AgenticTask
        task = AgenticTask(
            task_id="t2",
            task_type="farewell",
            priority=2,
            context={},
            trigger_conditions={},
            action_sequence=[],
        )
        self.assertEqual(task.status, "pending")


class TestAgentConfiguration(unittest.TestCase):
    def test_creation(self):
        from avatar_agent import AgentConfiguration
        cfg = AgentConfiguration(
            agent_id="a1",
            avatar_id="av1",
            style="professional",
            name="Assistant",
            description="A helpful assistant",
            personality={"friendly": True},
            capabilities=["chat", "answer_questions"],
            embedding_options={},
            security_settings={},
        )
        self.assertEqual(cfg.agent_id, "a1")
        self.assertEqual(cfg.style, "professional")


class TestAgenticAIManager(unittest.TestCase):
    def _make(self):
        with patch('avatar_agent.get_security_manager', return_value=MagicMock()):
            from avatar_agent import AgenticAIManager
            with patch('pathlib.Path.mkdir'):
                return AgenticAIManager()

    def test_init(self):
        mgr = self._make()
        self.assertIsNotNone(mgr)

    def test_active_tasks_empty(self):
        mgr = self._make()
        self.assertIsInstance(mgr.active_tasks, dict)

    def test_autonomous_mode_default(self):
        mgr = self._make()
        self.assertTrue(mgr.autonomous_mode)

    def test_learning_enabled(self):
        mgr = self._make()
        self.assertTrue(mgr.learning_enabled)


class TestAvatarAgentServiceInitializeWithoutAiohttp(unittest.TestCase):
    """AvatarAgentService.initialize() must not crash when aiohttp/jinja2 are absent.

    Bug: initialize() called web.Application() and jinja2.Environment() unconditionally,
    raising NameError when AIOHTTP_AVAILABLE / JINJA2_AVAILABLE are False.
    Fix: wrap those blocks with availability guards.
    """

    def _run_initialize(self):
        import asyncio
        from unittest.mock import AsyncMock, MagicMock, patch
        import avatar_agent

        async def _do():
            with patch('avatar_agent.get_security_manager', return_value=MagicMock()), \
                 patch('avatar_agent.get_agentic_ai_manager', new=AsyncMock(return_value=MagicMock())), \
                 patch.object(avatar_agent, 'AIOHTTP_AVAILABLE', False), \
                 patch.object(avatar_agent, 'JINJA2_AVAILABLE', False), \
                 patch('pathlib.Path.mkdir'), \
                 patch.object(avatar_agent.AvatarAgentService, 'create_default_agents', new=AsyncMock()):
                svc = avatar_agent.AvatarAgentService()
                await svc.initialize()
                return svc

        return asyncio.run(_do())

    def test_initialize_no_crash_without_aiohttp(self):
        svc = self._run_initialize()
        # web_app stays None when aiohttp is absent
        self.assertIsNone(svc.web_app)

    def test_initialize_no_crash_without_jinja2(self):
        svc = self._run_initialize()
        # template_env stays unset when jinja2 is absent
        self.assertFalse(hasattr(svc, 'template_env'))


if __name__ == '__main__':
    unittest.main()
