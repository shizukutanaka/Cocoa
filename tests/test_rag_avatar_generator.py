"""Tests for rag_avatar_generator module."""
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'main'))


class TestAvatarRAGSystem(unittest.TestCase):
    def _make(self):
        with patch('rag_avatar_generator.get_security_manager', return_value=MagicMock()):
            from rag_avatar_generator import AvatarRAGSystem
            return AvatarRAGSystem.__new__(AvatarRAGSystem)

    def _make_full(self):
        with patch('rag_avatar_generator.get_security_manager', return_value=MagicMock()):
            from rag_avatar_generator import AvatarRAGSystem
            # Patch mkdir to avoid FS side effects
            with patch('pathlib.Path.mkdir'):
                obj = AvatarRAGSystem.__new__(AvatarRAGSystem)
                obj.security_manager = MagicMock()
                obj.embedding_model = None
                obj.vector_store = None
                obj.chroma_client = None
                obj.collection = None
                obj.cache_dir = MagicMock()
                obj.avatar_knowledge_base = obj._build_avatar_knowledge_base()
                return obj

    def test_build_knowledge_base_returns_dict(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'main'))
        with patch('rag_avatar_generator.get_security_manager', return_value=MagicMock()):
            from rag_avatar_generator import AvatarRAGSystem
            obj = AvatarRAGSystem.__new__(AvatarRAGSystem)
            kb = obj._build_avatar_knowledge_base()
            self.assertIsInstance(kb, dict)
            self.assertGreater(len(kb), 0)

    def test_knowledge_base_has_style_category(self):
        with patch('rag_avatar_generator.get_security_manager', return_value=MagicMock()):
            from rag_avatar_generator import AvatarRAGSystem
            obj = AvatarRAGSystem.__new__(AvatarRAGSystem)
            kb = obj._build_avatar_knowledge_base()
            self.assertTrue(any("style" in k.lower() or "スタイル" in k for k in kb))

    def test_get_default_suggestions(self):
        obj = self._make_full()
        suggestions = obj._get_default_suggestions("professional", 3)
        self.assertIsInstance(suggestions, list)
        self.assertLessEqual(len(suggestions), 3)

    def test_get_default_suggestions_count(self):
        obj = self._make_full()
        suggestions = obj._get_default_suggestions("any context", 2)
        self.assertLessEqual(len(suggestions), 2)

    def test_attributes_initialized(self):
        obj = self._make_full()
        self.assertIsNone(obj.chroma_client)
        self.assertIsNone(obj.collection)


class TestGetAvatarSuggestionsEmptyCollection(unittest.TestCase):
    """get_avatar_suggestions() must fall back to defaults when Chroma returns empty docs.

    Bug: the condition `if user_preferences and "documents" in user_preferences`
    was True even when user_preferences["documents"] == [[]] (no stored history),
    causing _generate_suggestions_from_preferences() to be called and return [].
    The user then received an empty suggestion list instead of the default suggestions.
    Fix: check that pref_docs[0] is non-empty before choosing the preference branch.
    """

    def _make_full(self):
        with patch('rag_avatar_generator.get_security_manager', return_value=MagicMock()):
            from rag_avatar_generator import AvatarRAGSystem
            with patch('pathlib.Path.mkdir'):
                obj = AvatarRAGSystem.__new__(AvatarRAGSystem)
                obj.security_manager = MagicMock()
                obj.embedding_model = None
                obj.vector_store = None
                obj.chroma_client = None
                obj.collection = MagicMock()
                obj.cache_dir = MagicMock()
                obj.avatar_knowledge_base = obj._build_avatar_knowledge_base()
                return obj

    def test_empty_chroma_result_falls_back_to_defaults(self):
        import asyncio
        obj = self._make_full()
        # Simulate Chroma returning empty results for both queries
        obj.collection.query.return_value = {"documents": [[]], "ids": [[]], "distances": [[]]}

        suggestions = asyncio.run(obj.get_avatar_suggestions("u1", "professional", count=3))
        self.assertGreater(len(suggestions), 0, "Must return defaults, not empty list")

    def test_nonempty_chroma_result_uses_preferences(self):
        import asyncio
        obj = self._make_full()
        # First call: user has preferences; second call: knowledge base has docs
        obj.collection.query.side_effect = [
            {"documents": [["past_preference_doc"]], "ids": [["id1"]]},
            {"documents": [["kb doc 1", "kb doc 2"]], "ids": [["k1", "k2"]]},
        ]

        suggestions = asyncio.run(obj.get_avatar_suggestions("u1", "casual", count=2))
        # Should have come from the knowledge-base preference path, not defaults
        self.assertGreater(len(suggestions), 0)


class TestGetRAGSystem(unittest.TestCase):
    def test_get_rag_system_is_async(self):
        import inspect

        from rag_avatar_generator import get_rag_system
        self.assertTrue(inspect.iscoroutinefunction(get_rag_system))


if __name__ == '__main__':
    unittest.main()
