"""
Unit tests for main/api_integration.py
"""

import os
import sys
import inspect
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'main'))

# Patch heavy optional deps and internal imports before importing the module
import types

# Stub aiohttp
aiohttp_stub = types.ModuleType('aiohttp')
web_stub = types.ModuleType('aiohttp.web')
aiohttp_stub.web = web_stub
sys.modules.setdefault('aiohttp', aiohttp_stub)
sys.modules.setdefault('aiohttp.web', web_stub)

# Stub aiofiles
aiofiles_stub = types.ModuleType('aiofiles')
sys.modules.setdefault('aiofiles', aiofiles_stub)

# Stub video_creator
vc_stub = types.ModuleType('video_creator')
vc_stub.get_video_creator = MagicMock()
vc_stub.VideoCreationRequest = MagicMock()
sys.modules.setdefault('video_creator', vc_stub)

# Stub template_library
tl_stub = types.ModuleType('template_library')
tl_stub.get_template_library = MagicMock()
sys.modules.setdefault('template_library', tl_stub)

# Stub integrated_security
mock_security_manager = MagicMock()
is_stub = types.ModuleType('integrated_security')
is_stub.get_security_manager = MagicMock(return_value=mock_security_manager)
sys.modules.setdefault('integrated_security', is_stub)

with patch('integrated_security.get_security_manager', return_value=mock_security_manager):
    from api_integration import (
        IntegrationConfig,
        WorkflowTrigger,
        WorkflowExecution,
        APIIntegrationService,
        get_api_integration_service,
    )


class TestIntegrationConfig(unittest.TestCase):
    """Tests for IntegrationConfig dataclass"""

    def _make_config(self, **kwargs):
        defaults = dict(
            integration_id="test_id",
            name="Test Integration",
            type="webhook",
            provider="custom",
            config={"key": "value"},
        )
        defaults.update(kwargs)
        return IntegrationConfig(**defaults)

    def test_basic_creation(self):
        cfg = self._make_config()
        self.assertEqual(cfg.integration_id, "test_id")
        self.assertEqual(cfg.name, "Test Integration")
        self.assertEqual(cfg.type, "webhook")
        self.assertEqual(cfg.provider, "custom")

    def test_default_webhooks_is_empty_list(self):
        cfg = self._make_config()
        self.assertIsInstance(cfg.webhooks, list)
        self.assertEqual(len(cfg.webhooks), 0)

    def test_default_api_keys_is_empty_dict(self):
        cfg = self._make_config()
        self.assertIsInstance(cfg.api_keys, dict)
        self.assertEqual(len(cfg.api_keys), 0)

    def test_default_enabled_is_true(self):
        cfg = self._make_config()
        self.assertTrue(cfg.enabled)

    def test_created_at_auto_set(self):
        cfg = self._make_config()
        self.assertIsInstance(cfg.created_at, datetime)
        self.assertIsNotNone(cfg.created_at.tzinfo)

    def test_explicit_values_override_defaults(self):
        cfg = self._make_config(enabled=False, api_keys={"token": "abc"})
        self.assertFalse(cfg.enabled)
        self.assertEqual(cfg.api_keys["token"], "abc")


class TestWorkflowTrigger(unittest.TestCase):
    """Tests for WorkflowTrigger dataclass"""

    def _make_trigger(self, **kwargs):
        defaults = dict(
            trigger_id="trig_1",
            integration_id="int_1",
            event_type="content_created",
            conditions={},
            actions=[],
        )
        defaults.update(kwargs)
        return WorkflowTrigger(**defaults)

    def test_basic_creation(self):
        t = self._make_trigger()
        self.assertEqual(t.trigger_id, "trig_1")
        self.assertEqual(t.event_type, "content_created")

    def test_default_enabled_true(self):
        t = self._make_trigger()
        self.assertTrue(t.enabled)

    def test_default_last_triggered_none(self):
        t = self._make_trigger()
        self.assertIsNone(t.last_triggered)


class TestWorkflowExecution(unittest.TestCase):
    """Tests for WorkflowExecution dataclass"""

    def _make_execution(self, **kwargs):
        defaults = dict(
            execution_id="exec_1",
            trigger_id="trig_1",
            input_data={"foo": "bar"},
            status="pending",
        )
        defaults.update(kwargs)
        return WorkflowExecution(**defaults)

    def test_basic_creation(self):
        e = self._make_execution()
        self.assertEqual(e.execution_id, "exec_1")
        self.assertEqual(e.status, "pending")

    def test_default_results_is_empty_dict(self):
        e = self._make_execution()
        self.assertIsInstance(e.results, dict)

    def test_default_error_message_none(self):
        e = self._make_execution()
        self.assertIsNone(e.error_message)

    def test_started_at_auto_set(self):
        e = self._make_execution()
        self.assertIsInstance(e.started_at, datetime)

    def test_completed_at_default_none(self):
        e = self._make_execution()
        self.assertIsNone(e.completed_at)


class TestAPIIntegrationServiceInit(unittest.TestCase):
    """Tests for APIIntegrationService class"""

    def setUp(self):
        with patch('api_integration.get_security_manager', return_value=mock_security_manager):
            self.service = APIIntegrationService()

    def test_instance_created(self):
        self.assertIsInstance(self.service, APIIntegrationService)

    def test_initial_integrations_empty(self):
        self.assertIsInstance(self.service.integrations, dict)
        self.assertEqual(len(self.service.integrations), 0)

    def test_initial_triggers_empty(self):
        self.assertIsInstance(self.service.triggers, dict)

    def test_initial_executions_empty(self):
        self.assertIsInstance(self.service.executions, dict)

    def test_default_host_and_port(self):
        self.assertEqual(self.service.host, "0.0.0.0")
        self.assertEqual(self.service.port, 8081)

    def test_video_creator_none_before_init(self):
        self.assertIsNone(self.service.video_creator)

    def test_async_method_signatures(self):
        """Key methods that interact with external services should be async"""
        async_methods = [
            'initialize',
            'create_integration_config',
            'start_service',
            'stop_service',
            'webhook_handler',
            'zapier_webhook_handler',
            '_process_webhook_trigger',
            '_execute_workflow_trigger',
            'create_default_integrations',
        ]
        for name in async_methods:
            method = getattr(self.service, name)
            self.assertTrue(
                inspect.iscoroutinefunction(method),
                f"Expected {name} to be a coroutine function"
            )

    def test_check_trigger_conditions_no_conditions_returns_true(self):
        result = self.service._check_trigger_conditions({}, {"any": "data"})
        self.assertTrue(result)

    def test_check_trigger_conditions_matching(self):
        result = self.service._check_trigger_conditions({"status": "active"}, {"status": "active"})
        self.assertTrue(result)

    def test_check_trigger_conditions_mismatch(self):
        result = self.service._check_trigger_conditions({"status": "active"}, {"status": "inactive"})
        self.assertFalse(result)

    def test_extract_script_from_input_with_dict(self):
        action = {"script_template": "Hello {name}!"}
        result = self.service._extract_script_from_input(action, {"name": "World"})
        self.assertEqual(result, "Hello World!")

    def test_extract_script_from_input_non_dict(self):
        action = {}
        result = self.service._extract_script_from_input(action, "raw text")
        self.assertEqual(result, "raw text")


if __name__ == '__main__':
    unittest.main()
