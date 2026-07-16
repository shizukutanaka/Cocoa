"""Tests for emotional_intelligence module."""
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'main'))


class TestEmotionAnalysisRequest(unittest.TestCase):
    def test_creation(self):
        from emotional_intelligence import EmotionAnalysisRequest
        req = EmotionAnalysisRequest(user_id="u1", input_type="text", input_data="I am happy today!")
        self.assertEqual(req.user_id, "u1")

    def test_defaults(self):
        from emotional_intelligence import EmotionAnalysisRequest
        req = EmotionAnalysisRequest(user_id="u1", input_type="text", input_data="test")
        self.assertIsNone(req.context)
        self.assertEqual(req.previous_emotions, [])


class TestEmotionAnalysisResult(unittest.TestCase):
    def test_creation(self):
        from emotional_intelligence import EmotionAnalysisResult
        result = EmotionAnalysisResult(
            success=True,
            primary_emotion="happy",
            emotion_scores={"joy": 0.9, "neutral": 0.1},
            confidence=0.9,
            adaptation_suggestions=["smile"],
            context_aware_responses={"greeting": "Hello!"},
        )
        self.assertEqual(result.primary_emotion, "happy")
        self.assertTrue(result.success)

    def test_default_metadata(self):
        from emotional_intelligence import EmotionAnalysisResult
        result = EmotionAnalysisResult(
            success=True,
            primary_emotion="neutral",
            emotion_scores={},
            confidence=0.5,
            adaptation_suggestions=[],
            context_aware_responses={},
        )
        self.assertEqual(result.processing_metadata, {})


class TestEmotionRecognitionInit(unittest.TestCase):
    def test_init(self):
        with patch('emotional_intelligence.get_security_manager', return_value=MagicMock()):
            from emotional_intelligence import EmotionRecognition
            er = EmotionRecognition()
            self.assertIsNotNone(er)

    def test_emotion_response_patterns(self):
        with patch('emotional_intelligence.get_security_manager', return_value=MagicMock()):
            from emotional_intelligence import EmotionRecognition
            er = EmotionRecognition()
            # Check the emotion response patterns exist if available
            if hasattr(er, 'emotion_response_patterns'):
                self.assertIsInstance(er.emotion_response_patterns, dict)


class TestEmotionalIntelligenceInit(unittest.TestCase):
    def test_init(self):
        with patch('emotional_intelligence.get_security_manager', return_value=MagicMock()):
            from emotional_intelligence import EmotionalIntelligence
            ei = EmotionalIntelligence()
            self.assertIsNotNone(ei)

    def test_emotion_response_patterns_initialized(self):
        with patch('emotional_intelligence.get_security_manager', return_value=MagicMock()):
            from emotional_intelligence import EmotionalIntelligence
            ei = EmotionalIntelligence()
            self.assertIsInstance(ei.emotion_response_patterns, dict)
            self.assertGreater(len(ei.emotion_response_patterns), 0)

    def test_joy_in_patterns(self):
        with patch('emotional_intelligence.get_security_manager', return_value=MagicMock()):
            from emotional_intelligence import EmotionalIntelligence
            ei = EmotionalIntelligence()
            self.assertIn("joy", ei.emotion_response_patterns)

    def test_get_emotional_intelligence_is_async(self):
        import inspect

        from emotional_intelligence import get_emotional_intelligence
        self.assertTrue(inspect.iscoroutinefunction(get_emotional_intelligence))


class TestGenerateAdaptationSuggestionsEmptyScores(unittest.TestCase):
    """_generate_adaptation_suggestions must not crash with empty emotion_scores.

    Bug: max(emotion_scores.values()) raises ValueError when emotion_scores is {}.
    Fix: max(...) if emotion_scores else 0.0 guards the empty case.
    """

    def _make_ei(self):
        with patch('emotional_intelligence.get_security_manager', return_value=MagicMock()):
            from emotional_intelligence import EmotionalIntelligence
            return EmotionalIntelligence()

    def test_empty_emotion_scores_does_not_crash(self):
        import asyncio
        from emotional_intelligence import EmotionAnalysisRequest
        ei = self._make_ei()
        req = EmotionAnalysisRequest(user_id="u1", input_type="text", input_data="test")
        result = asyncio.run(ei._generate_adaptation_suggestions("neutral", {}, req))
        self.assertIsInstance(result, list)

    def test_nonempty_emotion_scores_returns_suggestions(self):
        import asyncio
        from emotional_intelligence import EmotionAnalysisRequest
        ei = self._make_ei()
        req = EmotionAnalysisRequest(user_id="u1", input_type="text", input_data="happy")
        result = asyncio.run(ei._generate_adaptation_suggestions("joy", {"joy": 0.9, "neutral": 0.1}, req))
        self.assertIsInstance(result, list)


if __name__ == '__main__':
    unittest.main()
