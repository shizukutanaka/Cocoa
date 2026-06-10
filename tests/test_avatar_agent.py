"""Tests for avatar_agent module."""
import sys
import os
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

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


if __name__ == '__main__':
    unittest.main()
