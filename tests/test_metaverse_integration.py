"""Tests for metaverse_integration module."""
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'main'))


class TestMetaverseAvatarRequest(unittest.TestCase):
    def _make(self, **kw):
        from metaverse_integration import MetaverseAvatarRequest
        defaults = {
            'user_id': "u1",
            'avatar_id': "av1",
            'platform': "unity",
            'environment': "vr",
        }
        defaults.update(kw)
        return MetaverseAvatarRequest(**defaults)

    def test_creation(self):
        req = self._make()
        self.assertEqual(req.user_id, "u1")
        self.assertEqual(req.platform, "unity")

    def test_position_default(self):
        req = self._make()
        self.assertEqual(req.position, (0.0, 0.0, 0.0))


class TestMetaverseAvatarResult(unittest.TestCase):
    def test_creation(self):
        from metaverse_integration import MetaverseAvatarResult
        result = MetaverseAvatarResult(success=True)
        self.assertTrue(result.success)
        self.assertIsNone(result.error_message)

    def test_defaults(self):
        from metaverse_integration import MetaverseAvatarResult
        result = MetaverseAvatarResult(success=False, error_message="fail")
        self.assertEqual(result.avatar_data, {})
        self.assertEqual(result.error_message, "fail")


class TestVRARIntegration(unittest.TestCase):
    def _make(self):
        with patch('metaverse_integration.get_security_manager', return_value=MagicMock()):
            from metaverse_integration import VRARIntegration
            return VRARIntegration()

    def test_init(self):
        svc = self._make()
        self.assertIsNotNone(svc)

    def test_supported_platforms(self):
        svc = self._make()
        self.assertIsInstance(svc.supported_platforms, (list, dict))
        self.assertGreater(len(svc.supported_platforms), 0)

    def test_has_platform_data(self):
        svc = self._make()
        if isinstance(svc.supported_platforms, dict):
            self.assertIn("unity", svc.supported_platforms)
        else:
            self.assertGreater(len(svc.supported_platforms), 0)


class TestMetaverseIntegration(unittest.TestCase):
    def _make(self):
        with patch('metaverse_integration.get_security_manager', return_value=MagicMock()):
            from metaverse_integration import MetaverseIntegration
            return MetaverseIntegration()

    def test_init(self):
        svc = self._make()
        self.assertIsNotNone(svc)

    def test_platform_configs(self):
        svc = self._make()
        self.assertIsInstance(svc.platform_configs, dict)
        self.assertGreater(len(svc.platform_configs), 0)


class TestOptimizeForEdgeAiNullGuard(unittest.IsolatedAsyncioTestCase):
    """_optimize_for_edge_ai must not crash when global_edge_manager is None.

    Bug: the method guarded on `if self.edge_ai_manager:` but then unconditionally
    called `self.global_edge_manager.find_optimal_route(...)`, raising AttributeError
    when edge_ai_manager is initialised but global_edge_manager is not yet available.
    Fix: change guard to `if self.edge_ai_manager and self.global_edge_manager:`.
    """

    def _make(self):
        with patch('metaverse_integration.get_security_manager', return_value=MagicMock()):
            from metaverse_integration import MetaverseIntegration, MetaverseAvatarRequest
            svc = MetaverseIntegration()
            return svc, MetaverseAvatarRequest

    async def test_edge_ai_set_but_global_manager_none_does_not_crash(self):
        svc, MetaverseAvatarRequest = self._make()
        svc.edge_ai_manager = MagicMock()
        svc.global_edge_manager = None
        req = MetaverseAvatarRequest(user_id="u1", avatar_id="av1", platform="unity", environment="vr")
        result = await svc._optimize_for_edge_ai({"key": "val"}, req)
        # No crash; original data returned unchanged since no route could be found
        self.assertIsInstance(result, dict)
        self.assertNotIn("edge_optimization", result)

    async def test_both_managers_set_calls_find_optimal_route(self):
        svc, MetaverseAvatarRequest = self._make()
        mock_route = MagicMock()
        mock_route.route_id = "r1"
        mock_route.estimated_latency_ms = 10.0
        mock_route.bandwidth_capacity_mbps = 100.0
        mock_route.reliability_score = 0.99
        mock_route.optimal_nodes = ["n1"]
        mock_global = MagicMock()
        # find_optimal_route is async
        async def fake_find(*a, **kw):
            return mock_route
        mock_global.find_optimal_route = fake_find
        svc.edge_ai_manager = MagicMock()
        svc.global_edge_manager = mock_global
        req = MetaverseAvatarRequest(user_id="u1", avatar_id="av1", platform="unity", environment="vr")
        result = await svc._optimize_for_edge_ai({}, req)
        self.assertIn("edge_optimization", result)
        self.assertEqual(result["edge_optimization"]["optimal_route"], "r1")


if __name__ == '__main__':
    unittest.main()
