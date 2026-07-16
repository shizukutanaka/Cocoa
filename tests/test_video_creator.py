"""Tests for main/video_creator.py — dataclasses and pure methods."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "main"))

from video_creator import VideoCreationRequest, VideoCreationResult, VideoCreator


def _raw_creator():
    """Return a VideoCreator instance without running __init__ (no deps needed)."""
    return object.__new__(VideoCreator)


class TestVideoCreationRequest(unittest.TestCase):

    def test_required_fields(self):
        req = VideoCreationRequest(user_id="u1", script="Hello world")
        self.assertEqual(req.user_id, "u1")
        self.assertEqual(req.script, "Hello world")

    def test_default_avatar_style(self):
        req = VideoCreationRequest(user_id="u1", script="s")
        self.assertEqual(req.avatar_style, "professional")

    def test_default_output_format(self):
        req = VideoCreationRequest(user_id="u1", script="s")
        self.assertEqual(req.output_format, "mp4")

    def test_default_quality(self):
        req = VideoCreationRequest(user_id="u1", script="s")
        self.assertEqual(req.quality, "high")

    def test_voice_settings_default_populated(self):
        req = VideoCreationRequest(user_id="u1", script="s")
        self.assertIsInstance(req.voice_settings, dict)
        self.assertIn("voice", req.voice_settings)
        self.assertIn("speed", req.voice_settings)
        self.assertIn("pitch", req.voice_settings)

    def test_video_settings_default_populated(self):
        req = VideoCreationRequest(user_id="u1", script="s")
        self.assertIsInstance(req.video_settings, dict)
        self.assertIn("resolution", req.video_settings)
        self.assertIn("fps", req.video_settings)

    def test_custom_voice_settings_not_overwritten(self):
        custom = {"voice": "male", "speed": 1.5, "pitch": 0.5}
        req = VideoCreationRequest(user_id="u1", script="s", voice_settings=custom)
        self.assertEqual(req.voice_settings["voice"], "male")

    def test_background_music_none_by_default(self):
        req = VideoCreationRequest(user_id="u1", script="s")
        self.assertIsNone(req.background_music)


class TestVideoCreationResult(unittest.TestCase):

    def test_successful_result(self):
        result = VideoCreationResult(success=True, video_path="/tmp/v.mp4")
        self.assertTrue(result.success)
        self.assertEqual(result.video_path, "/tmp/v.mp4")

    def test_failed_result(self):
        result = VideoCreationResult(success=False, error_message="network error")
        self.assertFalse(result.success)
        self.assertEqual(result.error_message, "network error")

    def test_metadata_defaults_to_empty_dict(self):
        result = VideoCreationResult(success=True)
        self.assertIsInstance(result.metadata, dict)
        self.assertEqual(result.metadata, {})

    def test_creation_time_defaults_to_zero(self):
        result = VideoCreationResult(success=True)
        self.assertEqual(result.creation_time, 0.0)

    def test_custom_metadata_not_overwritten(self):
        meta = {"key": "value"}
        result = VideoCreationResult(success=True, metadata=meta)
        self.assertEqual(result.metadata["key"], "value")


class TestSplitScriptIntoSentences(unittest.TestCase):

    def setUp(self):
        self.creator = _raw_creator()

    def _split(self, text):
        return self.creator._split_script_into_sentences(text)

    def test_splits_on_period(self):
        parts = self._split("Hello。World")
        self.assertEqual(len(parts), 2)
        self.assertIn("Hello", parts)
        self.assertIn("World", parts)

    def test_splits_on_exclamation(self):
        parts = self._split("Hello！World")
        self.assertEqual(len(parts), 2)

    def test_splits_on_question_mark(self):
        parts = self._split("Hello？World")
        self.assertEqual(len(parts), 2)

    def test_splits_on_newline(self):
        parts = self._split("Hello\nWorld")
        self.assertEqual(len(parts), 2)

    def test_strips_whitespace(self):
        parts = self._split("  Hello  。  World  ")
        for p in parts:
            self.assertEqual(p, p.strip())

    def test_empty_parts_filtered(self):
        parts = self._split("Hello。。。World")
        # consecutive separators produce empty strings — those should be filtered
        self.assertNotIn("", parts)

    def test_empty_string_returns_empty_list(self):
        self.assertEqual(self._split(""), [])

    def test_whitespace_only_returns_empty_list(self):
        self.assertEqual(self._split("   \n   "), [])

    def test_single_sentence_no_split(self):
        text = "This is a short sentence"
        parts = self._split(text)
        self.assertEqual(parts, [text])

    def test_long_sentence_split_into_chunks(self):
        # Create a sentence longer than 100 chars
        long_sentence = " ".join(["word"] * 30)  # ~150 chars
        parts = self._split(long_sentence)
        self.assertGreater(len(parts), 1)
        for part in parts:
            self.assertLessEqual(len(part), 110)  # some slack for word boundaries

    def test_multiple_sentences(self):
        parts = self._split("First。Second。Third")
        self.assertEqual(len(parts), 3)

    def test_full_stop_variant(self):
        parts = self._split("Hello．World")
        self.assertEqual(len(parts), 2)


if __name__ == "__main__":
    unittest.main()
