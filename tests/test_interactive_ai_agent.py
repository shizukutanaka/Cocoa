"""Tests for interactive_ai_agent module."""
import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'main'))


class TestConversationContext(unittest.TestCase):
    def test_creation(self):
        from interactive_ai_agent import ConversationContext
        ctx = ConversationContext(user_id="u1", avatar_id="av1", session_id="sess_1")
        self.assertEqual(ctx.session_id, "sess_1")
        self.assertIsInstance(ctx.conversation_history, list)

    def test_defaults(self):
        from interactive_ai_agent import ConversationContext
        ctx = ConversationContext(user_id="u", avatar_id="av", session_id="s")
        self.assertEqual(ctx.conversation_history, [])
        self.assertEqual(ctx.language, "ja")


class TestAgentResponse(unittest.TestCase):
    def test_creation(self):
        from interactive_ai_agent import AgentResponse
        resp = AgentResponse(
            response_text="Hello there!",
            confidence_score=0.95,
            response_time=0.1,
            language="ja",
            emotion="happy",
        )
        self.assertEqual(resp.response_text, "Hello there!")
        self.assertAlmostEqual(resp.confidence_score, 0.95)

    def test_defaults(self):
        from interactive_ai_agent import AgentResponse
        resp = AgentResponse(
            response_text="test",
            confidence_score=0.5,
            response_time=0.1,
            language="ja",
        )
        self.assertIsInstance(resp.suggestions, list)
        self.assertIsInstance(resp.metadata, dict)


class TestPersonalityManager(unittest.TestCase):
    def test_init(self):
        with patch('interactive_ai_agent.get_security_manager', return_value=MagicMock()):
            from interactive_ai_agent import PersonalityManager
            pm = PersonalityManager()
            self.assertIsNotNone(pm)

    def test_personality_templates(self):
        with patch('interactive_ai_agent.get_security_manager', return_value=MagicMock()):
            from interactive_ai_agent import PersonalityManager
            pm = PersonalityManager()
            self.assertIsInstance(pm.personality_templates, dict)
            self.assertIn("friendly", pm.personality_templates)


class TestInteractiveAIAgentFactory(unittest.TestCase):
    def test_factory_is_async(self):
        import inspect
        from interactive_ai_agent import get_interactive_ai_agent
        self.assertTrue(inspect.iscoroutinefunction(get_interactive_ai_agent))


if __name__ == '__main__':
    unittest.main()
