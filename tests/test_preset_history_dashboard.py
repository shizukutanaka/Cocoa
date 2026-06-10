"""Tests for main/preset_history_dashboard.py."""
import os
import sys
import types
import unittest
from datetime import datetime
from unittest.mock import MagicMock

# Mock flask and its dependencies before importing the module
_flask_mock = types.ModuleType("flask")
_flask_mock.Flask = MagicMock(return_value=MagicMock())
_flask_mock.render_template_string = MagicMock()
_flask_mock.request = MagicMock()
sys.modules.setdefault("flask", _flask_mock)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "main"))

import preset_history_dashboard as dashboard


class TestDtFilter(unittest.TestCase):

    def test_epoch_zero_is_valid_date(self):
        result = dashboard.dt_filter(0)
        # Result should be a date string; exact value depends on local timezone
        self.assertRegex(result, r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")

    def test_known_timestamp(self):
        # 2024-01-01 00:00:00 UTC = 1704067200 seconds
        # We don't assert the exact hour because local timezone differs,
        # but we can verify the format and that the date is 2024-xx-xx.
        ts = 1704067200.0
        result = dashboard.dt_filter(ts)
        self.assertRegex(result, r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")
        # Year must be 2023 or 2024 depending on local TZ offset
        year = int(result[:4])
        self.assertIn(year, [2023, 2024])

    def test_returns_string(self):
        self.assertIsInstance(dashboard.dt_filter(1000000), str)

    def test_length_is_19(self):
        # "YYYY-MM-DD HH:MM:SS" is exactly 19 characters
        self.assertEqual(len(dashboard.dt_filter(1000000)), 19)

    def test_round_trip(self):
        # Convert a datetime to timestamp and back
        dt = datetime(2024, 6, 15, 12, 30, 45)
        ts = dt.timestamp()
        result = dashboard.dt_filter(ts)
        reparsed = datetime.strptime(result, "%Y-%m-%d %H:%M:%S")
        self.assertEqual(reparsed, dt)

    def test_float_timestamp_accepted(self):
        result = dashboard.dt_filter(1700000000.999)
        self.assertRegex(result, r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")


class TestModuleConstants(unittest.TestCase):

    def test_template_contains_required_fields(self):
        tmpl = dashboard.TEMPLATE
        self.assertIn("{{preset}}", tmpl)
        self.assertIn("{{e.timestamp", tmpl)
        self.assertIn("{{e.change_type}}", tmpl)
        self.assertIn("{{e.user}}", tmpl)
        self.assertIn("{{e.note}}", tmpl)

    def test_template_is_string(self):
        self.assertIsInstance(dashboard.TEMPLATE, str)

    def test_template_has_html_structure(self):
        self.assertIn("<html>", dashboard.TEMPLATE)
        self.assertIn("</html>", dashboard.TEMPLATE)


if __name__ == "__main__":
    unittest.main()
