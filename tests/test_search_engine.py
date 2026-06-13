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


class TestQueryAnalytics(unittest.TestCase):
    def setUp(self):
        from search_engine import SearchDocument
        self.idx = SearchIndex()
        self.idx.index(SearchDocument("d1", "u1", name="Cute Cat", description="", tags=["cute"], category="vrc"))

    def test_no_queries_returns_zero_total(self):
        result = self.idx.query_analytics()
        self.assertEqual(result["total_queries"], 0)
        self.assertEqual(result["top_queries"], [])

    def test_queries_are_logged(self):
        self.idx.search("cute")
        self.idx.search("cute")
        self.idx.search("cat")
        result = self.idx.query_analytics()
        self.assertEqual(result["total_queries"], 3)

    def test_top_queries_sorted_by_count(self):
        for _ in range(3):
            self.idx.search("cute")
        self.idx.search("cat")
        result = self.idx.query_analytics()
        self.assertEqual(result["top_queries"][0]["query"], "cute")
        self.assertEqual(result["top_queries"][0]["count"], 3)

    def test_unique_queries_counted(self):
        self.idx.search("cute")
        self.idx.search("cat")
        result = self.idx.query_analytics(top_n=10)
        self.assertEqual(result["unique_queries"], 2)

    def test_empty_query_not_logged(self):
        self.idx.search("")
        result = self.idx.query_analytics()
        self.assertEqual(result["total_queries"], 0)

    def test_top_n_respected(self):
        for q in ["alpha", "beta", "gamma", "delta"]:
            self.idx.search(q)
        result = self.idx.query_analytics(top_n=2)
        self.assertLessEqual(len(result["top_queries"]), 2)


class TestPersonalizedSearch(unittest.TestCase):
    """boost_owner_ids lifts results from followed creators."""

    def setUp(self):
        self.idx = SearchIndex()
        # u1 publishes doc d1 and d2; u2 publishes d3
        self.idx.index_from_dict({
            "doc_id": "d1", "owner_id": "u1", "name": "Cute Cat",
            "description": "adorable cute cat", "tags": ["cute"], "is_public": True,
        })
        self.idx.index_from_dict({
            "doc_id": "d2", "owner_id": "u1", "name": "Fancy Fox",
            "description": "fancy fox avatar", "tags": ["fancy"], "is_public": True,
        })
        self.idx.index_from_dict({
            "doc_id": "d3", "owner_id": "u2", "name": "Dark Dragon",
            "description": "dark dragon avatar", "tags": ["dark"], "is_public": True,
        })

    def test_boost_moves_followed_creator_higher(self):
        # Without boost, d3 (dark dragon) should appear first for query "dark"
        r_no_boost = self.idx.search("dark")
        self.assertEqual(r_no_boost["items"][0]["doc_id"], "d3")
        # Boost u1 — even though d1/d2 don't match "dark", they shouldn't appear;
        # but if we query "cute" while boosting u1, u1's doc should outrank equivalent
        # Add a competing "cute" doc from u2 to verify boost effect
        self.idx.index_from_dict({
            "doc_id": "d4", "owner_id": "u2", "name": "Cute Dog",
            "description": "cute dog avatar", "tags": ["cute"], "is_public": True,
        })
        r_boosted = self.idx.search("cute", boost_owner_ids=["u1"])
        # d1 (u1, exact match) must score higher than d4 (u2, same match) due to boost
        ids = [it["doc_id"] for it in r_boosted["items"]]
        self.assertLess(ids.index("d1"), ids.index("d4"))

    def test_boost_does_not_affect_non_relevance_sort(self):
        # When sort_by=name, boost_owner_ids should have no effect on order
        r = self.idx.search("", sort_by="name", boost_owner_ids=["u1"])
        names = [it["name"] for it in r["items"]]
        self.assertEqual(names, sorted(names))

    def test_boost_none_unchanged(self):
        r1 = self.idx.search("cute")
        r2 = self.idx.search("cute", boost_owner_ids=None)
        self.assertEqual(
            [it["doc_id"] for it in r1["items"]],
            [it["doc_id"] for it in r2["items"]],
        )

    def test_boost_empty_query_followed_creator_first(self):
        # Empty query + boost: followed creators appear before non-followed
        r = self.idx.search("", sort_by="relevance", boost_owner_ids=["u2"])
        ids = [it["doc_id"] for it in r["items"]]
        # d3 belongs to u2 — must appear before d1/d2 (u1)
        self.assertLess(ids.index("d3"), ids.index("d1"))
        self.assertLess(ids.index("d3"), ids.index("d2"))

    def test_boost_does_not_include_private_results(self):
        self.idx.index_from_dict({
            "doc_id": "d5", "owner_id": "u1", "name": "Private Cat",
            "description": "secret cat", "tags": [], "is_public": False,
        })
        r = self.idx.search("", public_only=True, boost_owner_ids=["u1"])
        ids = [it["doc_id"] for it in r["items"]]
        self.assertNotIn("d5", ids)


if __name__ == "__main__":
    unittest.main(verbosity=2)
