#!/usr/bin/env python3
"""Run the dependency-light Cocoa test subset.

These test modules import only the standard library plus pure Cocoa modules,
so they run in minimal environments where the full pytest suite cannot —
e.g. when pytest is not installed, or when the cryptography native binding,
torch, flask, etc. are unavailable.

    python3 tests/run_safe.py            # run all safe tests
    python3 tests/run_safe.py -v         # verbose

Exit code is 0 on success, 1 on any failure (CI-friendly).
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "main")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Test modules that are safe to run without heavy/native dependencies.
SAFE_MODULES = [
    "tests.test_repairs",
    "tests.test_validation",
    "tests.test_preset_diff",
    "tests.test_vrchat_budget",
    "tests.test_preset_schema",
    "tests.test_template_filters",
    "tests.test_preset_history",
    "tests.test_preset_history_diff",
    "tests.test_batch_validator",
    "tests.test_i18n",
    "tests.test_avatar_parameters",
    "tests.test_logging_config",
    "tests.test_dependency_injection",
    "tests.test_async_base",
    "tests.test_vrchat_analyzer",
    "tests.test_cache_manager",
    "tests.test_secret_manager",
    "tests.test_config_validator",
    "tests.test_health_monitor",
    "tests.test_config",
    "tests.test_disaster_recovery",
    "tests.test_performance_monitor",
    "tests.test_validate_and_repair_presets",
    "tests.test_redis_cache_manager",
    "tests.test_global_edge_manager",
    "tests.test_grafana_integration",
    "tests.test_enhanced_disaster_recovery",
    "tests.test_joint_range_report",
    "tests.test_security_scanner",
    "tests.test_services_config",
    "tests.test_health_checker",
    "tests.test_perf_log_viewer",
    "tests.test_language_scripts",
    "tests.test_generate_languages",
    "tests.test_generate_languages_improved",
    "tests.test_preset_history_alert",
    "tests.test_avatar_parameter_sets",
    "tests.test_parameters",
    "tests.test_preset_change_history",
    "tests.test_notification_system",
    "tests.test_logging_manager",
    "tests.test_i18n_manager",
    "tests.test_billing_service",
    "tests.test_database_manager",
    "tests.test_avatar_performance_monitor",
    "tests.test_template_library_manager",
    "tests.test_multi_avatar_manager",
    "tests.test_social_media_optimizer",
    "tests.test_rag_avatar_generator",
    "tests.test_nft_avatar_manager",
    "tests.test_video_analytics",
    "tests.test_preset_manager",
    "tests.test_two_factor_auth",
    "tests.test_integrated_security",
    "tests.test_vr_ar_avatar_system",
    "tests.test_metaverse_integration",
    "tests.test_emotional_intelligence",
    "tests.test_config_encryptor",
    "tests.test_enhanced_encryption",
    "tests.test_template_library",
    "tests.test_blockchain_audit",
    "tests.test_performance_monitor_module",
    "tests.test_avatar_personality_tuner",
    "tests.test_avatar_agent",
    "tests.test_advanced_security_2025",
    "tests.test_ai_avatar_generator",
    "tests.test_interactive_ai_agent",
    "tests.test_photo_to_avatar_generator",
    "tests.test_voice_cloning",
    "tests.test_prometheus_monitor",
    "tests.test_ar_cloud_manager",
    "tests.test_bci_manager",
    "tests.test_edge_ai_manager",
    "tests.test_performance_analyzer",
    "tests.test_virtual_backgrounds",
    "tests.test_interactive_avatar",
    "tests.test_vrchat_sdk_integration",
    "tests.test_api_integration",
    "tests.test_avatar_video_creator",
    "tests.test_vrchat_parameter_budget",
    "tests.test_preset_diff_core",
    "tests.test_parameters_batch_validator",
    "tests.test_preset_history_diff",
    "tests.test_vrchat_performance_analyzer",
    "tests.test_preset_history_diff_and_rollback",
    "tests.test_parameter_optimizer",
    "tests.test_main",
    "tests.test_video_creator",
    "tests.test_preset_history_dashboard",
    "tests.test_api_server",
]


def build_suite() -> unittest.TestSuite:
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for name in SAFE_MODULES:
        suite.addTests(loader.loadTestsFromName(name))
    return suite


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    verbosity = 2 if ("-v" in argv or "--verbose" in argv) else 1
    result = unittest.TextTestRunner(verbosity=verbosity).run(build_suite())
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
