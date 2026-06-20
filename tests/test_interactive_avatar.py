"""
Tests for main/interactive_avatar.py
"""

import inspect
import os
import sys
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'main'))


# Patch heavy deps before import
_mock_security = MagicMock()
_mock_ai_gen = MagicMock()

with patch.dict('sys.modules', {
    'integrated_security': MagicMock(get_security_manager=MagicMock(return_value=_mock_security)),
    'ai_avatar_generator': MagicMock(
        get_ai_avatar_generator=MagicMock(return_value=_mock_ai_gen),
        AvatarGenerationRequest=MagicMock,
    ),
    'websockets': MagicMock(),
}):
    import interactive_avatar as ia


class TestInteractionMessageDataclass(unittest.TestCase):

    def test_basic_creation(self):
        now = datetime.now(timezone.utc)
        msg = ia.InteractionMessage(
            message_id="m1",
            user_id="u1",
            message_type="text",
            content="hello",
            timestamp=now,
        )
        self.assertEqual(msg.message_id, "m1")
        self.assertEqual(msg.user_id, "u1")
        self.assertEqual(msg.message_type, "text")
        self.assertEqual(msg.content, "hello")

    def test_metadata_defaults_to_empty_dict(self):
        now = datetime.now(timezone.utc)
        msg = ia.InteractionMessage(
            message_id="m2", user_id="u2", message_type="emotion",
            content="happy", timestamp=now, metadata=None,
        )
        self.assertEqual(msg.metadata, {})

    def test_metadata_preserved_when_provided(self):
        now = datetime.now(timezone.utc)
        meta = {"key": "value"}
        msg = ia.InteractionMessage(
            message_id="m3", user_id="u3", message_type="command",
            content="status", timestamp=now, metadata=meta,
        )
        self.assertEqual(msg.metadata, meta)


class TestAvatarResponseDataclass(unittest.TestCase):

    def test_basic_creation_with_defaults(self):
        resp = ia.AvatarResponse(
            response_id="r1",
            avatar_id="av1",
            response_type="text",
            content="Hi!",
        )
        self.assertEqual(resp.response_id, "r1")
        self.assertEqual(resp.emotion, "neutral")
        self.assertEqual(resp.animation_data, {})
        self.assertIsNone(resp.audio_data)
        self.assertIsInstance(resp.timestamp, datetime)

    def test_animation_data_defaults_to_empty_dict(self):
        resp = ia.AvatarResponse(
            response_id="r2", avatar_id="av2",
            response_type="animation", content="wave", animation_data=None,
        )
        self.assertEqual(resp.animation_data, {})

    def test_timestamp_auto_set_utc(self):
        before = datetime.now(timezone.utc)
        resp = ia.AvatarResponse(
            response_id="r3", avatar_id="av3",
            response_type="text", content="test",
        )
        after = datetime.now(timezone.utc)
        self.assertGreaterEqual(resp.timestamp, before)
        self.assertLessEqual(resp.timestamp, after)


class TestInteractiveAvatarClass(unittest.TestCase):

    def _make_avatar(self, avatar_id="test_av", style="casual"):
        with patch('interactive_avatar.get_security_manager', return_value=MagicMock()):
            return ia.InteractiveAvatar(avatar_id, style)

    def test_init_sets_avatar_id_and_style(self):
        avatar = self._make_avatar("av42", "professional")
        self.assertEqual(avatar.avatar_id, "av42")
        self.assertEqual(avatar.style, "professional")

    def test_init_default_state(self):
        avatar = self._make_avatar()
        self.assertFalse(avatar.is_active)
        self.assertEqual(avatar.current_emotion, "neutral")
        self.assertEqual(avatar.conversation_history, [])
        self.assertEqual(avatar.connected_clients, {})

    def test_analyze_emotion_positive(self):
        avatar = self._make_avatar()
        result = avatar._analyze_emotion("嬉しい！素晴らしい！")
        self.assertEqual(result, "happy")

    def test_analyze_emotion_negative(self):
        avatar = self._make_avatar()
        result = avatar._analyze_emotion("悲しい、辛い")
        self.assertEqual(result, "sad")

    def test_analyze_emotion_neutral(self):
        avatar = self._make_avatar()
        result = avatar._analyze_emotion("テスト")
        self.assertEqual(result, "neutral")

    def test_get_status_returns_dict(self):
        avatar = self._make_avatar("status_test")
        # avatar_image_path is only set after initialize; set manually
        avatar.avatar_image_path = None
        status = avatar.get_status()
        self.assertIn("avatar_id", status)
        self.assertEqual(status["avatar_id"], "status_test")
        self.assertEqual(status["is_active"], False)

    def test_get_conversation_history_respects_limit(self):
        avatar = self._make_avatar()
        avatar.conversation_history = [{"entry": i} for i in range(20)]
        history = avatar.get_conversation_history(limit=5)
        self.assertEqual(len(history), 5)

    def test_async_methods_are_coroutines(self):
        for method_name in ['initialize', 'start_server', 'stop_server',
                            '_generate_response', '_generate_text_response',
                            '_process_messages']:
            method = getattr(ia.InteractiveAvatar, method_name)
            self.assertTrue(
                inspect.iscoroutinefunction(method),
                f"{method_name} should be a coroutine function",
            )


class TestCleanupInactiveClientsTotalSeconds(unittest.IsolatedAsyncioTestCase):
    """_cleanup_inactive_clients must use total_seconds() not .seconds.

    Bug: `(now - last_activity).seconds > 300` wraps at 60 seconds:
    a client inactive for 5m5s would have .seconds == 305 (ok), but one
    inactive for 1h5s would have .seconds == 5 and NOT be evicted.
    Fix: use .total_seconds() so the full elapsed duration is compared.
    """

    def _make_avatar(self):
        avatar = ia.InteractiveAvatar.__new__(ia.InteractiveAvatar)
        avatar.avatar_id = "test"
        avatar.connected_clients = {}
        return avatar

    async def test_client_inactive_over_one_hour_is_evicted(self):
        from datetime import datetime, timedelta, timezone
        avatar = self._make_avatar()
        stale_time = datetime.now(timezone.utc) - timedelta(hours=1, seconds=5)
        avatar.connected_clients["stale"] = {"last_activity": stale_time}
        await avatar._cleanup_inactive_clients()
        self.assertNotIn("stale", avatar.connected_clients)

    async def test_client_inactive_5_minutes_is_evicted(self):
        from datetime import datetime, timedelta, timezone
        avatar = self._make_avatar()
        stale_time = datetime.now(timezone.utc) - timedelta(seconds=301)
        avatar.connected_clients["stale"] = {"last_activity": stale_time}
        await avatar._cleanup_inactive_clients()
        self.assertNotIn("stale", avatar.connected_clients)

    async def test_recently_active_client_is_kept(self):
        from datetime import datetime, timedelta, timezone
        avatar = self._make_avatar()
        active_time = datetime.now(timezone.utc) - timedelta(seconds=60)
        avatar.connected_clients["active"] = {"last_activity": active_time}
        await avatar._cleanup_inactive_clients()
        self.assertIn("active", avatar.connected_clients)


class TestModuleFunctions(unittest.TestCase):

    def test_list_interactive_avatars_returns_list(self):
        result = ia.list_interactive_avatars()
        self.assertIsInstance(result, list)

    def test_get_interactive_avatar_is_coroutine(self):
        self.assertTrue(inspect.iscoroutinefunction(ia.get_interactive_avatar))

    def test_create_interactive_avatar_is_coroutine(self):
        self.assertTrue(inspect.iscoroutinefunction(ia.create_interactive_avatar))


if __name__ == '__main__':
    unittest.main()
