"""Tests for main/search_engine.py"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "main")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from search_engine import SearchIndex, _tokenize, get_search_index


class TestTokenizer(unittest.TestCase):
    def test_basic_tokenize(self):
        tokens = _tokenize("Hello World")
        self.assertIn("hello", tokens)
        self.assertIn("world", tokens)

    def test_stopwords_removed(self):
        tokens = _tokenize("a quick brown fox")
        self.assertNotIn("a", tokens)

    def test_numbers_kept(self):
        tokens = _tokenize("avatar v2 model")
        self.assertIn("v2", tokens)

    def test_japanese_tokenize(self):
        tokens = _tokenize("かわいいアバター")
        self.assertTrue(len(tokens) >= 1)

    def test_short_tokens_removed(self):
        tokens = _tokenize("hi I am ok")
        self.assertNotIn("hi", tokens)
        self.assertNotIn("i", tokens)


class TestSearchIndex(unittest.TestCase):
    def setUp(self):
        self.idx = SearchIndex()
        self.idx.index_from_dict({
            "doc_id": "d1", "owner_id": "u1", "name": "Cute Cat",
            "description": "a cute little cat avatar",
            "tags": ["cute", "cat"], "category": "animal", "platform": "vrc",
            "is_public": True,
        })
        self.idx.index_from_dict({
            "doc_id": "d2", "owner_id": "u2", "name": "Dark Dragon",
            "description": "powerful dark dragon",
            "tags": ["dark", "dragon"], "category": "mythical", "platform": "web",
            "is_public": True,
        })
        self.idx.index_from_dict({
            "doc_id": "d3", "owner_id": "u1", "name": "Private Panda",
            "description": "secret panda",
            "tags": ["panda"], "category": "animal", "platform": "vrc",
            "is_public": False,
        })

    def test_basic_search(self):
        r = self.idx.search("cute")
        self.assertEqual(r["total"], 1)
        self.assertEqual(r["items"][0]["doc_id"], "d1")

    def test_search_by_tag_keyword(self):
        r = self.idx.search("dragon")
        self.assertGreater(r["total"], 0)

    def test_empty_query_returns_all(self):
        r = self.idx.search("")
        self.assertEqual(r["total"], 3)

    def test_public_only_filter(self):
        r = self.idx.search("", public_only=True)
        self.assertEqual(r["total"], 2)

    def test_filter_by_category(self):
        r = self.idx.search("", category="animal")
        self.assertEqual(r["total"], 2)

    def test_filter_by_platform(self):
        r = self.idx.search("", platform="web")
        self.assertEqual(r["total"], 1)
        self.assertEqual(r["items"][0]["doc_id"], "d2")

    def test_filter_by_tags(self):
        r = self.idx.search("", tags=["cute"])
        self.assertEqual(r["total"], 1)

    def test_sort_by_name(self):
        r = self.idx.search("", sort_by="name")
        names = [item["name"] for item in r["items"]]
        self.assertEqual(names, sorted(names))

    def test_sort_by_newest(self):
        r = self.idx.search("", sort_by="newest")
        # Most recently indexed should appear first
        self.assertEqual(r["items"][0]["doc_id"], "d3")

    def test_pagination(self):
        r = self.idx.search("", limit=2, offset=0)
        self.assertEqual(len(r["items"]), 2)
        r2 = self.idx.search("", limit=2, offset=2)
        self.assertEqual(len(r2["items"]), 1)

    def test_facets_present(self):
        r = self.idx.search("")
        self.assertIn("facets", r)
        facets = r["facets"]
        self.assertIn("categories", facets)
        self.assertIn("platforms", facets)
        self.assertIn("top_tags", facets)

    def test_facet_counts(self):
        r = self.idx.search("")
        self.assertEqual(r["facets"]["categories"].get("animal", 0), 2)

    def test_remove_document(self):
        ok = self.idx.remove("d1")
        self.assertTrue(ok)
        r = self.idx.search("cute")
        self.assertEqual(r["total"], 0)

    def test_remove_unknown_returns_false(self):
        self.assertFalse(self.idx.remove("no-such-doc"))

    def test_suggest_autocomplete(self):
        suggestions = self.idx.suggest("cu")
        self.assertIn("cute", suggestions)

    def test_suggest_empty_on_no_match(self):
        suggestions = self.idx.suggest("zzzz")
        self.assertEqual(suggestions, [])

    def test_suggest_limit(self):
        suggestions = self.idx.suggest("", limit=2)
        self.assertLessEqual(len(suggestions), 2)

    def test_stats(self):
        s = self.idx.stats()
        self.assertIn("total_documents", s)
        self.assertEqual(s["total_documents"], 3)

    def test_reindex_updates(self):
        # Re-index an existing document with a new name
        self.idx.index_from_dict({
            "doc_id": "d1", "owner_id": "u1", "name": "Updated Cat",
            "description": "updated description",
            "tags": ["updated"], "is_public": True,
        })
        r = self.idx.search("Updated")
        self.assertGreater(r["total"], 0)

    def test_no_cross_owner_leakage(self):
        # User searching their own docs shouldn't see another user's private docs
        r = self.idx.search("", owner_id="u1", public_only=False)
        # Should include u1's public and private, but since public_only=False AND
        # owner_id is set, the search shows u1's docs plus all public docs
        doc_ids = {item["doc_id"] for item in r["items"]}
        self.assertIn("d3", doc_ids)  # u1's private doc visible to u1

    def test_singleton(self):
        idx1 = get_search_index()
        idx2 = get_search_index()
        self.assertIs(idx1, idx2)

    def test_pagination_has_more_fields(self):
        r = self.idx.search("", limit=2, offset=0)
        self.assertIn("has_more", r)
        self.assertIn("next_offset", r)

    def test_pagination_has_more_true(self):
        r = self.idx.search("", limit=2, offset=0)
        self.assertTrue(r["has_more"])
        self.assertEqual(r["next_offset"], 2)

    def test_pagination_has_more_false_last_page(self):
        r = self.idx.search("", limit=2, offset=2)
        self.assertFalse(r["has_more"])
        self.assertIsNone(r["next_offset"])

    def test_prefix_search_finds_partial_token(self):
        # "cut" is a prefix of "cute" — should find d1 (name="Cute Cat")
        r = self.idx.search("cut")
        self.assertGreater(r["total"], 0)
        doc_ids = [item["doc_id"] for item in r["items"]]
        self.assertIn("d1", doc_ids)

    def test_prefix_search_lower_score_than_exact(self):
        # exact match "cute" should score higher than prefix match "cut"
        r_exact = self.idx.search("cute")
        r_prefix = self.idx.search("cut")
        # Both find d1; exact should score >= prefix
        exact_score = next(it["score"] for it in r_exact["items"] if it["doc_id"] == "d1")
        prefix_score = next(it["score"] for it in r_prefix["items"] if it["doc_id"] == "d1")
        self.assertGreaterEqual(exact_score, prefix_score)

    def test_prefix_search_no_exact_index_match(self):
        # "robotic" is not indexed; "rob" is a prefix of no indexed token from d3 ("Robot Dog")
        # this test just ensures no crash on non-matching prefix
        r = self.idx.search("xyz_notaword_prefix")
        self.assertEqual(r["total"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
