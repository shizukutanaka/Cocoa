"""Acceptance tests for template_filters (REQ-TL-01..05).

Spec: docs/SPEC_TEMPLATE_LIBRARY.md
Runnable without pytest:  python3 -m unittest tests.test_template_filters -v
"""
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "main")):
    if p not in sys.path:
        sys.path.insert(0, p)

import template_filters as tf  # noqa: E402


class TestSanitizeTemplateId(unittest.TestCase):
    def test_accepts_safe_ids(self):
        for tid in ("business_executive", "custom_a-1.2", "Tmpl_01"):
            self.assertEqual(tf.sanitize_template_id(tid), tid)

    def test_rejects_path_traversal(self):
        for bad in ("../etc", "..", "a/b", "a\\b", "../../x", "foo/../bar"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    tf.sanitize_template_id(bad)

    def test_rejects_empty_and_non_string(self):
        for bad in ("", "   ", None, 123):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    tf.sanitize_template_id(bad)

    def test_rejects_invalid_chars(self):
        for bad in ("a b", "tmpl!", "name#1", "x\x00y"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    tf.sanitize_template_id(bad)


class TestValidateTemplate(unittest.TestCase):
    def _avatar(self, **over):
        base = {"template_id": "t1", "name": "N", "description": "D",
                "category": "business", "style": "professional"}
        base.update(over)
        return base

    def test_valid_avatar(self):
        self.assertTrue(tf.validate_avatar_template(self._avatar())["valid"])

    def test_missing_required(self):
        r = tf.validate_avatar_template(self._avatar(style=""))
        self.assertFalse(r["valid"])
        self.assertTrue(any("style" in e for e in r["errors"]))

    def test_bad_tags(self):
        r = tf.validate_avatar_template(self._avatar(tags=["ok", 5]))
        self.assertFalse(r["valid"])

    def test_unsafe_template_id_in_data(self):
        r = tf.validate_avatar_template(self._avatar(template_id="../evil"))
        self.assertFalse(r["valid"])

    def test_video_requires_script(self):
        r = tf.validate_video_template({"template_id": "v", "name": "n",
                                        "description": "d", "category": "tutorial"})
        self.assertFalse(r["valid"])
        self.assertTrue(any("script_template" in e for e in r["errors"]))

    def test_non_object(self):
        self.assertFalse(tf.validate_avatar_template(["x"])["valid"])


class TestFilterAndSearch(unittest.TestCase):
    def setUp(self):
        self.items = [
            {"template_id": "a", "name": "Exec", "description": "boss", "category": "business",
             "tags": ["business", "pro"], "is_premium": True, "usage_count": 5},
            {"template_id": "b", "name": "Gamer", "description": "play", "category": "casual",
             "tags": ["gaming"], "is_premium": False, "usage_count": 9},
            {"template_id": "c", "name": "Teacher", "description": "teach business", "category": "education",
             "tags": ["edu"], "is_premium": False, "usage_count": 2},
        ]

    def test_filter_by_category(self):
        r = tf.filter_templates(self.items, category="casual")
        self.assertEqual([t["template_id"] for t in r], ["b"])

    def test_filter_by_tags_or(self):
        r = tf.filter_templates(self.items, tags=["gaming", "edu"])
        self.assertEqual({t["template_id"] for t in r}, {"b", "c"})

    def test_filter_premium_only(self):
        r = tf.filter_templates(self.items, premium_only=True)
        self.assertEqual([t["template_id"] for t in r], ["a"])

    def test_search_matches_name_desc_tags_sorted_by_usage(self):
        r = tf.search_templates(self.items, "business")
        # 'a' (tag/name) and 'c' (description) match; sorted by usage_count desc
        self.assertEqual([t["template_id"] for t in r], ["a", "c"])

    def test_search_no_match(self):
        self.assertEqual(tf.search_templates(self.items, "zzz"), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
