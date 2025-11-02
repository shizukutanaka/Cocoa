#!/usr/bin/env python3
"""
Cocoaパフォーマンステスト統合実行スクリプト
パフォーマンステスト、最適化、レポート生成を統合実行

使用法:
    python scripts/run_performance_tests.py [オプション]

オプション:
    --test-only      テストのみ実行（最適化は行わない）
    --optimize-only  最適化のみ実行（テストは行わない）
    --quick          クイックテストモード
    --output DIR     レポート出力ディレクトリ
    --format FORMAT  レポート形式 (json, markdown, both)
"""

import sys
import os
import argparse
import logging
import json
from pathlib import Path
from datetime import datetime
import subprocess

# Cocoaモジュールのパスを追加
sys.path.insert(0, str(Path(__file__).parent.parent / "main"))

try:
    from performance_tester import CocoaPerformanceTester
    from performance_optimizer import PerformanceOptimizer
except ImportError as e:
    print(f"エラー: Cocoaパフォーマンスモジュールをインポートできません: {e}")
    sys.exit(1)

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('performance_execution.log')
    ]
)
logger = logging.getLogger(__name__)


class PerformanceTestRunner:
    """パフォーマンステスト統合実行クラス"""

    def __init__(self, output_dir: str = "performance_reports", report_format: str = "both"):
        """初期化"""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.report_format = report_format
        self.execution_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 実行結果格納
        self.test_results = None
        self.optimization_results = None

        logger.info(f"パフォーマンステスト統合実行を初期化しました")
        logger.info(f"出力ディレクトリ: {self.output_dir}")

    def run_performance_tests(self, quick_mode: bool = False) -> bool:
        """パフォーマンステスト実行"""
        logger.info("パフォーマンステストを開始します")

        try:
            tester = CocoaPerformanceTester()

            if quick_mode:
                # クイックモード: 重要なテストのみ実行
                logger.info("クイックテストモードで実行します")
                # 個別テストを選択的に実行
                test_results = {
                    "test_execution": {
                        "start_time": datetime.now().isoformat(),
                        "quick_mode": True
                    },
                    "test_results": [],
                    "optimization_recommendations": []
                }

                # 基本的なテストのみ実行
                basic_tests = [
                    tester.test_json_processing_performance,
                    tester.test_memory_usage_patterns
                ]

                for test_func in basic_tests:
                    try:
                        result = test_func()
                        tester.test_results.append(result)
                        logger.info(f"完了: {test_func.__name__}")
                    except Exception as e:
                        logger.error(f"テストエラー: {test_func.__name__} - {e}")

                # 結果をまとめ
                test_results["test_execution"]["end_time"] = datetime.now().isoformat()
                test_results["test_results"] = [
                    {
                        "test_name": r.test_name,
                        "success": r.success,
                        "duration": r.duration,
                        "metrics": {
                            "cpu_percent": r.metrics.cpu_percent,
                            "memory_usage_mb": r.metrics.memory_usage,
                            "response_time": r.metrics.response_time
                        }
                    }
                    for r in tester.test_results
                ]

                self.test_results = test_results
            else:
                # フルテストスイート実行
                self.test_results = tester.run_full_performance_suite()

            # テスト結果保存
            test_report_path = self.output_dir / f"performance_test_{self.execution_timestamp}"
            if self.report_format in ["json", "both"]:
                with open(f"{test_report_path}.json", 'w', encoding='utf-8') as f:
                    json.dump(self.test_results, f, indent=2, ensure_ascii=False, default=str)

            if self.report_format in ["markdown", "both"]:
                markdown_report = tester.generate_performance_report(self.test_results)
                with open(f"{test_report_path}.md", 'w', encoding='utf-8') as f:
                    f.write(markdown_report)

            logger.info(f"パフォーマンステスト完了: {test_report_path}")
            return True

        except Exception as e:
            logger.error(f"パフォーマンステストエラー: {e}")
            return False

    def run_optimization(self) -> bool:
        """パフォーマンス最適化実行"""
        logger.info("パフォーマンス最適化を開始します")

        try:
            optimizer = PerformanceOptimizer()
            self.optimization_results = optimizer.run_comprehensive_optimization()

            # 最適化結果保存
            optimization_report_path = self.output_dir / f"optimization_{self.execution_timestamp}"

            if self.report_format in ["json", "both"]:
                with open(f"{optimization_report_path}.json", 'w', encoding='utf-8') as f:
                    json.dump(self.optimization_results, f, indent=2, ensure_ascii=False, default=str)

            if self.report_format in ["markdown", "both"]:
                markdown_report = optimizer.generate_optimization_report(self.optimization_results)
                with open(f"{optimization_report_path}.md", 'w', encoding='utf-8') as f:
                    f.write(markdown_report)

            logger.info(f"パフォーマンス最適化完了: {optimization_report_path}")
            return True

        except Exception as e:
            logger.error(f"パフォーマンス最適化エラー: {e}")
            return False

    def generate_comprehensive_report(self) -> str:
        """統合レポート生成"""
        logger.info("統合レポートを生成します")

        try:
            # 統合レポートデータ
            comprehensive_data = {
                "execution_info": {
                    "timestamp": self.execution_timestamp,
                    "execution_time": datetime.now().isoformat(),
                    "reports_generated": []
                },
                "performance_test_results": self.test_results,
                "optimization_results": self.optimization_results,
                "summary": self._generate_summary()
            }

            # JSONレポート保存
            comprehensive_json_path = self.output_dir / f"comprehensive_report_{self.execution_timestamp}.json"
            with open(comprehensive_json_path, 'w', encoding='utf-8') as f:
                json.dump(comprehensive_data, f, indent=2, ensure_ascii=False, default=str)

            # Markdownレポート生成
            comprehensive_md_path = self.output_dir / f"comprehensive_report_{self.execution_timestamp}.md"
            markdown_content = self._generate_comprehensive_markdown(comprehensive_data)
            with open(comprehensive_md_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)

            logger.info(f"統合レポート生成完了: {comprehensive_md_path}")
            return str(comprehensive_md_path)

        except Exception as e:
            logger.error(f"統合レポート生成エラー: {e}")
            return ""

    def _generate_summary(self) -> dict:
        """サマリー生成"""
        summary = {
            "overall_status": "unknown",
            "test_success_rate": 0.0,
            "optimization_success_rate": 0.0,
            "key_metrics": {},
            "recommendations_count": 0,
            "critical_issues": []
        }

        try:
            # テスト結果サマリー
            if self.test_results:
                test_execution = self.test_results.get("test_execution", {})
                test_results = self.test_results.get("test_results", [])

                if test_results:
                    successful_tests = sum(1 for t in test_results if t.get("success", False))
                    summary["test_success_rate"] = (successful_tests / len(test_results)) * 100

                    # 主要メトリクスの平均
                    avg_cpu = sum(t.get("metrics", {}).get("cpu_percent", 0) for t in test_results) / len(test_results)
                    avg_memory = sum(t.get("metrics", {}).get("memory_usage_mb", 0) for t in test_results) / len(test_results)
                    avg_response = sum(t.get("metrics", {}).get("response_time", 0) for t in test_results) / len(test_results)

                    summary["key_metrics"] = {
                        "average_cpu_percent": avg_cpu,
                        "average_memory_mb": avg_memory,
                        "average_response_time": avg_response
                    }

                # 推奨事項数
                recommendations = self.test_results.get("optimization_recommendations", [])
                summary["recommendations_count"] = len(recommendations)

                # 重要な問題の特定
                for rec in recommendations:
                    if rec.get("priority") == "high":
                        summary["critical_issues"].append(rec.get("issue", "不明な問題"))

            # 最適化結果サマリー
            if self.optimization_results:
                opt_execution = self.optimization_results.get("optimization_execution", {})
                opt_results = self.optimization_results.get("optimization_results", [])

                if opt_results:
                    successful_optimizations = sum(1 for o in opt_results if o.get("success", False))
                    summary["optimization_success_rate"] = (successful_optimizations / len(opt_results)) * 100

            # 全体ステータスの決定
            if summary["test_success_rate"] >= 80 and summary["optimization_success_rate"] >= 80:
                summary["overall_status"] = "excellent"
            elif summary["test_success_rate"] >= 60 and summary["optimization_success_rate"] >= 60:
                summary["overall_status"] = "good"
            elif summary["test_success_rate"] >= 40 or summary["optimization_success_rate"] >= 40:
                summary["overall_status"] = "needs_improvement"
            else:
                summary["overall_status"] = "critical"

        except Exception as e:
            logger.error(f"サマリー生成エラー: {e}")

        return summary

    def _generate_comprehensive_markdown(self, data: dict) -> str:
        """統合Markdownレポート生成"""
        summary = data.get("summary", {})
        status_icons = {
            "excellent": "🟢",
            "good": "🟡",
            "needs_improvement": "🟠",
            "critical": "🔴",
            "unknown": "⚫"
        }

        overall_icon = status_icons.get(summary.get("overall_status", "unknown"), "⚫")

        markdown = f"""
# Cocoa総合パフォーマンスレポート

## 実行概要 {overall_icon}
- 実行日時: {data['execution_info']['execution_time']}
- 全体ステータス: {summary.get('overall_status', 'unknown')}
- テスト成功率: {summary.get('test_success_rate', 0):.1f}%
- 最適化成功率: {summary.get('optimization_success_rate', 0):.1f}%

## 主要メトリクス
"""

        key_metrics = summary.get("key_metrics", {})
        if key_metrics:
            markdown += f"""
- 平均CPU使用率: {key_metrics.get('average_cpu_percent', 0):.1f}%
- 平均メモリ使用量: {key_metrics.get('average_memory_mb', 0):.1f}MB
- 平均レスポンス時間: {key_metrics.get('average_response_time', 0):.3f}秒
"""

        # 重要な問題
        critical_issues = summary.get("critical_issues", [])
        if critical_issues:
            markdown += f"""
## 🔴 重要な問題 ({len(critical_issues)}件)
"""
            for i, issue in enumerate(critical_issues, 1):
                markdown += f"{i}. {issue}\n"
        else:
            markdown += "\n## ✅ 重要な問題は検出されませんでした\n"

        # パフォーマンステスト結果
        if data.get("performance_test_results"):
            test_results = data["performance_test_results"].get("test_results", [])
            markdown += f"""
## パフォーマンステスト結果 ({len(test_results)}件)
"""
            for test in test_results:
                status_icon = "✅" if test.get("success", False) else "❌"
                markdown += f"""
### {status_icon} {test.get('test_name', 'Unknown Test')}
- 実行時間: {test.get('duration', 0):.3f}秒
- CPU使用率: {test.get('metrics', {}).get('cpu_percent', 0):.1f}%
- メモリ使用量: {test.get('metrics', {}).get('memory_usage_mb', 0):.1f}MB
"""

        # 最適化結果
        if data.get("optimization_results"):
            opt_results = data["optimization_results"].get("optimization_results", [])
            successful_opts = [o for o in opt_results if o.get("success", False)]

            markdown += f"""
## 最適化結果 ({len(successful_opts)}/{len(opt_results)}件成功)
"""

            # カテゴリ別にグループ化
            categories = {}
            for opt in successful_opts:
                category = opt.get("category", "その他")
                if category not in categories:
                    categories[category] = []
                categories[category].append(opt)

            for category, optimizations in categories.items():
                markdown += f"\n### {category}\n"
                for opt in optimizations:
                    improvement = opt.get("improvement_percent", 0)
                    markdown += f"- {opt.get('optimization', 'Unknown')}: {improvement:.1f}%改善\n"

        # 推奨事項
        recommendations_count = summary.get("recommendations_count", 0)
        if recommendations_count > 0:
            markdown += f"""
## 追加推奨事項 ({recommendations_count}件)

詳細な推奨事項については、個別のテストレポートをご確認ください。
"""

        # 次のステップ
        markdown += """
## 次のステップ

### 1. 設定の適用
最適化された設定を有効にするため、アプリケーションを再起動してください。

### 2. 継続監視
定期的なパフォーマンステストの実行を推奨します。

### 3. 追加改善
個別のテストレポートで特定された問題の対応を検討してください。

---

📊 このレポートは自動生成されました。詳細な分析については個別のレポートファイルをご確認ください。
"""

        return markdown

    def cleanup_old_reports(self, keep_days: int = 30):
        """古いレポートファイルのクリーンアップ"""
        try:
            cutoff_time = datetime.now().timestamp() - (keep_days * 24 * 60 * 60)

            for report_file in self.output_dir.glob("*report_*.json"):
                if report_file.stat().st_mtime < cutoff_time:
                    report_file.unlink()
                    logger.info(f"古いレポートを削除: {report_file}")

            for report_file in self.output_dir.glob("*report_*.md"):
                if report_file.stat().st_mtime < cutoff_time:
                    report_file.unlink()
                    logger.info(f"古いレポートを削除: {report_file}")

        except Exception as e:
            logger.error(f"レポートクリーンアップエラー: {e}")


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description="Cocoaパフォーマンステスト統合実行",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "--test-only",
        action="store_true",
        help="テストのみ実行（最適化は行わない）"
    )

    parser.add_argument(
        "--optimize-only",
        action="store_true",
        help="最適化のみ実行（テストは行わない）"
    )

    parser.add_argument(
        "--quick",
        action="store_true",
        help="クイックテストモード"
    )

    parser.add_argument(
        "--output",
        default="performance_reports",
        help="レポート出力ディレクトリ"
    )

    parser.add_argument(
        "--format",
        choices=["json", "markdown", "both"],
        default="both",
        help="レポート形式"
    )

    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="古いレポートファイルをクリーンアップ"
    )

    args = parser.parse_args()

    # 実行前のバリデーション
    if args.test_only and args.optimize_only:
        print("エラー: --test-only と --optimize-only は同時に指定できません")
        sys.exit(1)

    # テストランナー初期化
    runner = PerformanceTestRunner(args.output, args.format)

    # 古いレポートのクリーンアップ
    if args.cleanup:
        runner.cleanup_old_reports()

    try:
        success_count = 0
        total_operations = 0

        # テスト実行
        if not args.optimize_only:
            total_operations += 1
            if runner.run_performance_tests(args.quick):
                success_count += 1

        # 最適化実行
        if not args.test_only:
            total_operations += 1
            if runner.run_optimization():
                success_count += 1

        # 統合レポート生成
        if success_count > 0:
            comprehensive_report = runner.generate_comprehensive_report()
            if comprehensive_report:
                print(f"\n📊 統合レポート生成完了: {comprehensive_report}")

        # 結果サマリー表示
        print(f"\n✅ パフォーマンス処理完了!")
        print(f"成功: {success_count}/{total_operations}")
        print(f"レポート出力先: {runner.output_dir}")

        # 失敗時の終了コード
        if success_count < total_operations:
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n処理がユーザーによって中断されました")
        sys.exit(1)
    except Exception as e:
        print(f"処理実行エラー: {e}")
        logging.error(f"処理実行エラー: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()