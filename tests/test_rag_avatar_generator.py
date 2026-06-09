"""Tests for rag_avatar_generator module."""
import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'main'))


class TestAvatarRAGSystem(unittest.TestCase):
    def _make(self):
        with patch('rag_avatar_generator.get_security_manager', return_value=MagicMock()):
            from rag_avatar_generator import AvatarRAGSystem
            return AvatarRAGSystem.__new__(AvatarRAGSystem)

    def _make_full(self):
        with patch('rag_avatar_generator.get_security_manager', return_value=MagicMock()):
            from rag_avatar_generator import AvatarRAGSystem
            import tempfile, os
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


class TestGetRAGSystem(unittest.TestCase):
    def test_get_rag_system_is_async(self):
        import inspect
        from rag_avatar_generator import get_rag_system
        self.assertTrue(inspect.iscoroutinefunction(get_rag_system))


if __name__ == '__main__':
    unittest.main()
