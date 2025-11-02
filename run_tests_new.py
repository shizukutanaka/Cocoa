#!/usr/bin/env python3
"""
Cocoaテストランナー
包括的テストスイートの実行とレポート生成
"""
import os
import sys
import time
import json
import subprocess
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

# プロジェクトルートをPythonパスに追加
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "main"))

def setup_test_environment():
    """テスト環境をセットアップ"""
    print("🔧 テスト環境をセットアップしています...")

    # 必要なディレクトリ作成
    dirs_to_create = [
        "logs",
        "temp",
        "backups",
        "data",
        "config",
        "tests/reports"
    ]

    for dir_path in dirs_to_create:
        Path(dir_path).mkdir(parents=True, exist_ok=True)

    # テスト用設定ファイル作成
    test_config = {
        "environment": "test",
        "database": {
            "type": "sqlite",
            "database": "data/test.db"
        },
        "logging": {
            "level": "INFO",
            "enable_console": False
        }
    }

    config_path = Path("config/test_config.json")
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(test_config, f, indent=2)

    print("✅ テスト環境のセットアップが完了しました")

def check_dependencies():
    """依存関係をチェック"""
    print("📦 依存関係をチェックしています...")

    required_packages = [
        "pytest",
        "unittest-xml-reporting",
        "coverage"
    ]

    missing_packages = []

    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing_packages.append(package)

    if missing_packages:
        print("⚠️  以下のパッケージが不足しています:")
        for package in missing_packages:
            print(f"   - {package}")

        print("\n以下のコマンドでインストールしてください:")
        print(f"pip install {' '.join(missing_packages)}")
        return False

    print("✅ すべての依存関係が満たされています")
    return True

def run_unit_tests():
    """単体テストを実行"""
    print("🧪 単体テストを実行しています...")

    try:
        # 基本的なテスト実行
        result = subprocess.run([
            sys.executable, "-m", "unittest",
            "discover", "-s", "tests", "-p", "test_*.py", "-v"
        ], capture_output=True, text=True, cwd=PROJECT_ROOT)

        if result.returncode == 0:
            print("✅ 単体テストが成功しました")
            return True, result.stdout
        else:
            print("❌ 単体テストが失敗しました")
            print(result.stdout)
            print(result.stderr)
            return False, result.stderr

    except Exception as e:
        print(f"❌ テスト実行エラー: {e}")
        return False, str(e)

def run_integration_tests():
    """統合テストを実行"""
    print("🔗 統合テストを実行しています...")

    try:
        from tests.test_suite import TestIntegration
        import unittest

        loader = unittest.TestLoader()
        suite = loader.loadTestsFromTestCase(TestIntegration)
        runner = unittest.TextTestRunner(verbosity=2)

        start_time = time.time()
        result = runner.run(suite)
        end_time = time.time()

        success = result.wasSuccessful()
        duration = end_time - start_time

        print(f"{'✅' if success else '❌'} 統合テスト完了 (実行時間: {duration:.2f}秒)")
        return success, f"Tests: {result.testsRun}, Failures: {len(result.failures)}, Errors: {len(result.errors)}"

    except Exception as e:
        print(f"❌ 統合テスト実行エラー: {e}")
        return False, str(e)

def run_performance_tests():
    """パフォーマンステストを実行"""
    print("⚡ パフォーマンステストを実行しています...")

    try:
        from tests.test_suite import TestPerformance
        import unittest

        loader = unittest.TestLoader()
        suite = loader.loadTestsFromTestCase(TestPerformance)
        runner = unittest.TextTestRunner(verbosity=2)

        start_time = time.time()
        result = runner.run(suite)
        end_time = time.time()

        success = result.wasSuccessful()
        duration = end_time - start_time

        print(f"{'✅' if success else '❌'} パフォーマンステスト完了 (実行時間: {duration:.2f}秒)")
        return success, f"Tests: {result.testsRun}, Duration: {duration:.2f}s"

    except Exception as e:
        print(f"❌ パフォーマンステスト実行エラー: {e}")
        return False, str(e)

def run_security_tests():
    """セキュリティテストを実行"""
    print("🔒 セキュリティテストを実行しています...")

    try:
        from tests.test_suite import TestSecurityManager
        import unittest

        loader = unittest.TestLoader()
        suite = loader.loadTestsFromTestCase(TestSecurityManager)
        runner = unittest.TextTestRunner(verbosity=2)

        start_time = time.time()
        result = runner.run(suite)
        end_time = time.time()

        success = result.wasSuccessful()
        duration = end_time - start_time

        print(f"{'✅' if success else '❌'} セキュリティテスト完了 (実行時間: {duration:.2f}秒)")
        return success, f"Security tests passed: {result.wasSuccessful()}"

    except Exception as e:
        print(f"❌ セキュリティテスト実行エラー: {e}")
        return False, str(e)

def generate_test_report(results: Dict[str, Any]):
    """テスト結果レポートを生成"""
    print("📊 テストレポートを生成しています...")

    report = {
        "timestamp": datetime.now().isoformat(),
        "environment": {
            "python_version": sys.version,
            "platform": sys.platform,
            "working_directory": str(PROJECT_ROOT)
        },
        "test_results": results,
        "summary": {
            "total_test_categories": len(results),
            "passed_categories": sum(1 for r in results.values() if r.get("success", False)),
            "overall_success": all(r.get("success", False) for r in results.values())
        }
    }

    # JSONレポート
    report_path = Path("tests/reports/test_report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # HTMLレポート
    html_report = generate_html_report(report)
    html_path = Path("tests/reports/test_report.html")
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_report)

    print(f"✅ テストレポートを生成しました:")
    print(f"   - JSON: {report_path}")
    print(f"   - HTML: {html_path}")

    return report

def generate_html_report(report: Dict[str, Any]) -> str:
    """HTMLレポートを生成"""
    html = f"""
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cocoa テストレポート</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 20px; }}
        .header {{ background: #2d3748; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
        .summary {{ background: #f7fafc; padding: 15px; border-radius: 8px; margin-bottom: 20px; }}
        .test-category {{ background: white; border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 15px; padding: 15px; }}
        .success {{ border-left: 4px solid #48bb78; }}
        .failure {{ border-left: 4px solid #f56565; }}
        .status-badge {{ display: inline-block; padding: 4px 12px; border-radius: 16px; font-size: 12px; font-weight: bold; }}
        .status-success {{ background: #c6f6d5; color: #2f855a; }}
        .status-failure {{ background: #fed7d7; color: #c53030; }}
        pre {{ background: #f7fafc; padding: 10px; border-radius: 4px; overflow-x: auto; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🍫 Cocoa テストレポート</h1>
        <p>実行時刻: {report['timestamp']}</p>
    </div>

    <div class="summary">
        <h2>📊 サマリー</h2>
        <p>総テストカテゴリ: {report['summary']['total_test_categories']}</p>
        <p>成功したカテゴリ: {report['summary']['passed_categories']}</p>
        <p>全体結果: <span class="status-badge {'status-success' if report['summary']['overall_success'] else 'status-failure'}">
            {'SUCCESS' if report['summary']['overall_success'] else 'FAILURE'}
        </span></p>
    </div>

    <div class="test-results">
        <h2>🧪 テスト結果詳細</h2>
"""

    for category, result in report['test_results'].items():
        success = result.get('success', False)
        status_class = 'success' if success else 'failure'
        status_text = '✅ SUCCESS' if success else '❌ FAILURE'

        html += f"""
        <div class="test-category {status_class}">
            <h3>{category} {status_text}</h3>
            <p><strong>詳細:</strong> {result.get('details', 'No details available')}</p>
        </div>
        """

    html += """
    </div>

    <div class="environment">
        <h2>🖥️ 環境情報</h2>
        <pre>""" + json.dumps(report['environment'], indent=2) + """</pre>
    </div>
</body>
</html>"""

    return html

def cleanup_test_artifacts():
    """テストアーティファクトをクリーンアップ"""
    print("🧹 テストアーティファクトをクリーンアップしています...")

    cleanup_paths = [
        "temp",
        "__pycache__",
        ".pytest_cache",
        "*.pyc",
        "*.pyo",
        "*.coverage"
    ]

    import glob
    import shutil

    for pattern in cleanup_paths:
        for path in glob.glob(pattern, recursive=True):
            path_obj = Path(path)
            try:
                if path_obj.is_file():
                    path_obj.unlink()
                elif path_obj.is_dir():
                    shutil.rmtree(path_obj, ignore_errors=True)
            except Exception as e:
                print(f"   ⚠️  クリーンアップできませんでした: {path} ({e})")

    print("✅ クリーンアップ完了")

def main():
    """メイン処理"""
    print("🍫 Cocoa 包括的テストスイート")
    print("=" * 50)

    start_time = time.time()

    # 引数処理
    import argparse
    parser = argparse.ArgumentParser(description="Cocoa テストスイート実行")
    parser.add_argument("--unit", action="store_true", help="単体テストのみ実行")
    parser.add_argument("--integration", action="store_true", help="統合テストのみ実行")
    parser.add_argument("--performance", action="store_true", help="パフォーマンステストのみ実行")
    parser.add_argument("--security", action="store_true", help="セキュリティテストのみ実行")
    parser.add_argument("--skip-deps", action="store_true", help="依存関係チェックをスキップ")
    parser.add_argument("--no-cleanup", action="store_true", help="クリーンアップをスキップ")
    args = parser.parse_args()

    # テスト環境セットアップ
    setup_test_environment()

    # 依存関係チェック
    if not args.skip_deps and not check_dependencies():
        print("❌ 依存関係が不足しているため、テストを中止します")
        sys.exit(1)

    # テスト結果を格納
    results = {}

    # テスト実行
    if args.unit or not any([args.integration, args.performance, args.security]):
        success, details = run_unit_tests()
        results["unit_tests"] = {"success": success, "details": details}

    if args.integration:
        success, details = run_integration_tests()
        results["integration_tests"] = {"success": success, "details": details}

    if args.performance:
        success, details = run_performance_tests()
        results["performance_tests"] = {"success": success, "details": details}

    if args.security:
        success, details = run_security_tests()
        results["security_tests"] = {"success": success, "details": details}

    # レポート生成
    if results:
        report = generate_test_report(results)
    else:
        print("⚠️  実行されたテストがありません")
        sys.exit(1)

    # クリーンアップ
    if not args.no_cleanup:
        cleanup_test_artifacts()

    # 結果サマリー
    end_time = time.time()
    total_duration = end_time - start_time

    print("\n" + "=" * 50)
    print("📊 テスト実行結果サマリー")
    print(f"⏱️  総実行時間: {total_duration:.2f}秒")

    overall_success = report['summary']['overall_success']
    print(f"🎯 全体結果: {'✅ SUCCESS' if overall_success else '❌ FAILURE'}")

    for category, result in results.items():
        success = result['success']
        print(f"   {category}: {'✅' if success else '❌'}")

    if not overall_success:
        print("\n❌ 一部のテストが失敗しました。詳細はレポートを確認してください。")
        sys.exit(1)
    else:
        print("\n🎉 すべてのテストが成功しました！")
        sys.exit(0)

if __name__ == "__main__":
    main()