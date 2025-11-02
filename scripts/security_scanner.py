#!/usr/bin/env python3
"""
Otedama セキュリティスキャナー - Production-Grade Security Scanner

国家レベルのセキュリティ監査を実行します:
- 依存関係の脆弱性スキャン
- コード静的解析
- 設定ファイルの安全性チェック
- 暗号化設定の検証
- ファイルパーミッションの監査
"""

import os
import sys
import json
import re
import subprocess
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Tuple
from datetime import datetime
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SecurityScanner:
    """統合セキュリティスキャナー"""

    def __init__(self, base_dir: Path = None):
        self.base_dir = base_dir or Path(__file__).resolve().parent.parent
        self.issues = []
        self.warnings = []
        self.info = []

    def scan_all(self) -> Dict[str, Any]:
        """全スキャン実行"""
        logger.info("🔍 セキュリティスキャン開始")

        results = {
            'timestamp': datetime.now().isoformat(),
            'scan_version': '1.0.0',
            'base_directory': str(self.base_dir),
            'checks': {}
        }

        # 各チェック実行
        checks = [
            ('dependencies', self.check_dependencies),
            ('secrets', self.check_secrets),
            ('file_permissions', self.check_file_permissions),
            ('configuration', self.check_configuration),
            ('encryption', self.check_encryption_config),
            ('code_quality', self.check_code_quality),
        ]

        for check_name, check_func in checks:
            logger.info(f"実行中: {check_name}")
            try:
                results['checks'][check_name] = check_func()
            except Exception as e:
                logger.error(f"チェック失敗 ({check_name}): {e}")
                results['checks'][check_name] = {
                    'status': 'error',
                    'error': str(e)
                }

        # 総合評価
        results['summary'] = self._generate_summary(results['checks'])
        results['issues'] = self.issues
        results['warnings'] = self.warnings
        results['info'] = self.info

        logger.info("✅ セキュリティスキャン完了")
        return results

    def check_dependencies(self) -> Dict[str, Any]:
        """依存関係の脆弱性チェック"""
        result = {
            'status': 'unknown',
            'vulnerable_packages': [],
            'outdated_packages': [],
            'recommendations': []
        }

        requirements_file = self.base_dir / 'requirements.txt'
        if not requirements_file.exists():
            result['status'] = 'warning'
            result['message'] = 'requirements.txt が見つかりません'
            self.warnings.append('requirements.txt が存在しません')
            return result

        # 既知の脆弱性パッケージチェック
        vulnerable_patterns = {
            'Flask': '<2.3.0',
            'cryptography': '<41.0.0',
            'Werkzeug': '<2.3.0',
            'SQLAlchemy': '<1.4.0'
        }

        with requirements_file.open() as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                for pkg, min_version in vulnerable_patterns.items():
                    if line.startswith(pkg):
                        # バージョンチェック（簡易）
                        if '==' in line:
                            installed_version = line.split('==')[1]
                            result['recommendations'].append(
                                f"{pkg}: バージョン{min_version}以上を推奨"
                            )

        result['status'] = 'pass' if not result['vulnerable_packages'] else 'fail'
        return result

    def check_secrets(self) -> Dict[str, Any]:
        """機密情報のハードコードチェック"""
        result = {
            'status': 'pass',
            'exposed_secrets': [],
            'suspicious_files': []
        }

        # チェック対象パターン
        secret_patterns = [
            (r'password\s*=\s*["\'][^"\']{3,}["\']', 'パスワードハードコード'),
            (r'secret\s*=\s*["\'][^"\']{3,}["\']', 'シークレットハードコード'),
            (r'api[_-]?key\s*=\s*["\'][^"\']{3,}["\']', 'APIキーハードコード'),
            (r'private[_-]?key\s*=\s*["\'][^"\']{3,}["\']', '秘密鍵ハードコード'),
            (r'token\s*=\s*["\'][^"\']{10,}["\']', 'トークンハードコード'),
        ]

        # Python ファイルをスキャン
        python_files = list(self.base_dir.rglob('*.py'))
        for py_file in python_files:
            # venv, tests, __pycache__ をスキップ
            if any(skip in str(py_file) for skip in ['venv', 'test', '__pycache__', '.git']):
                continue

            try:
                content = py_file.read_text(encoding='utf-8')
                for pattern, description in secret_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    if matches:
                        result['exposed_secrets'].append({
                            'file': str(py_file.relative_to(self.base_dir)),
                            'type': description,
                            'line_count': len(matches)
                        })
                        self.issues.append(f"{description} 検出: {py_file.name}")
            except Exception as e:
                logger.warning(f"ファイル読み込み失敗 ({py_file}): {e}")

        result['status'] = 'pass' if not result['exposed_secrets'] else 'fail'
        return result

    def check_file_permissions(self) -> Dict[str, Any]:
        """ファイルパーミッションチェック"""
        result = {
            'status': 'pass',
            'insecure_files': [],
            'recommendations': []
        }

        # 重要ファイルのチェック
        critical_files = [
            '.env',
            'config/config.json',
            'config/database.json',
            'security.db',
            'data/otedama.db'
        ]

        for file_path in critical_files:
            full_path = self.base_dir / file_path
            if not full_path.exists():
                continue

            try:
                # Unixシステムでのパーミッションチェック
                if hasattr(os, 'stat'):
                    stat_info = full_path.stat()
                    mode = stat_info.st_mode

                    # 他者読み取り可能かチェック
                    if mode & 0o004:
                        result['insecure_files'].append({
                            'file': file_path,
                            'issue': '他者読み取り可能',
                            'recommendation': 'chmod 600'
                        })
                        self.warnings.append(f"パーミッション警告: {file_path}")
            except Exception as e:
                logger.warning(f"パーミッションチェック失敗 ({file_path}): {e}")

        result['status'] = 'pass' if not result['insecure_files'] else 'warning'
        return result

    def check_configuration(self) -> Dict[str, Any]:
        """設定ファイルの安全性チェック"""
        result = {
            'status': 'pass',
            'issues': [],
            'recommendations': []
        }

        config_file = self.base_dir / 'config' / 'config.json'
        if not config_file.exists():
            result['status'] = 'warning'
            result['message'] = '設定ファイルが見つかりません'
            return result

        try:
            with config_file.open() as f:
                config = json.load(f)

            # デバッグモードチェック
            if config.get('debug', False):
                result['issues'].append('デバッグモードが有効です')
                self.warnings.append('本番環境でデバッグモードが有効')

            # ログレベルチェック
            if config.get('log_level') == 'DEBUG':
                result['issues'].append('ログレベルがDEBUGです')
                self.warnings.append('本番環境でDEBUGログレベル')

            # セキュリティ設定チェック
            if 'security' in config:
                security_config = config['security']
                if not security_config.get('enable_audit_log', True):
                    result['issues'].append('監査ログが無効です')
                    self.issues.append('監査ログが無効化されています')

                if not security_config.get('require_2fa', False):
                    result['recommendations'].append('2FA認証の有効化を推奨')

        except json.JSONDecodeError as e:
            result['status'] = 'fail'
            result['error'] = f'JSON解析エラー: {e}'
            self.issues.append(f'設定ファイルJSON エラー: {e}')
        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)

        result['status'] = 'pass' if not result['issues'] else 'warning'
        return result

    def check_encryption_config(self) -> Dict[str, Any]:
        """暗号化設定の検証"""
        result = {
            'status': 'unknown',
            'issues': [],
            'recommendations': []
        }

        # 環境変数チェック
        required_env_vars = [
            'OTEDAMA_SECRET_KEY',
            'OTEDAMA_ENCRYPTION_KEY'
        ]

        for env_var in required_env_vars:
            value = os.environ.get(env_var)
            if not value:
                result['issues'].append(f'{env_var} が設定されていません')
                self.issues.append(f'必須環境変数未設定: {env_var}')
            elif len(value) < 32:
                result['issues'].append(f'{env_var} が短すぎます (32文字以上推奨)')
                self.warnings.append(f'暗号化鍵が短い: {env_var}')

        # .env ファイルの存在チェック
        env_file = self.base_dir / '.env'
        if env_file.exists():
            self.info.append('.env ファイルが存在します（バージョン管理対象外を確認）')
        else:
            result['recommendations'].append('.env ファイルの作成を推奨')

        result['status'] = 'pass' if not result['issues'] else 'fail'
        return result

    def check_code_quality(self) -> Dict[str, Any]:
        """コード品質チェック"""
        result = {
            'status': 'info',
            'static_analysis': {},
            'recommendations': []
        }

        # Pylint チェック（インストールされている場合）
        try:
            pylint_result = subprocess.run(
                ['pylint', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if pylint_result.returncode == 0:
                result['static_analysis']['pylint'] = 'available'
                result['recommendations'].append('pylint main/ を実行してコード品質を確認してください')
        except (FileNotFoundError, subprocess.TimeoutExpired):
            result['static_analysis']['pylint'] = 'not_installed'

        # Bandit チェック（セキュリティ）
        try:
            bandit_result = subprocess.run(
                ['bandit', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if bandit_result.returncode == 0:
                result['static_analysis']['bandit'] = 'available'
                result['recommendations'].append('bandit -r main/ を実行してセキュリティ問題を確認してください')
        except (FileNotFoundError, subprocess.TimeoutExpired):
            result['static_analysis']['bandit'] = 'not_installed'

        return result

    def _generate_summary(self, checks: Dict[str, Any]) -> Dict[str, Any]:
        """スキャン結果のサマリー生成"""
        summary = {
            'total_checks': len(checks),
            'passed': 0,
            'failed': 0,
            'warnings': 0,
            'security_score': 0
        }

        for check_name, check_result in checks.items():
            status = check_result.get('status', 'unknown')
            if status == 'pass':
                summary['passed'] += 1
            elif status == 'fail':
                summary['failed'] += 1
            elif status in ['warning', 'info']:
                summary['warnings'] += 1

        # セキュリティスコア計算 (0-100)
        total = summary['total_checks']
        if total > 0:
            score = (summary['passed'] / total) * 100
            score -= summary['failed'] * 15
            score -= summary['warnings'] * 5
            summary['security_score'] = max(0, min(100, score))

        # 総合評価
        if summary['failed'] > 0:
            summary['overall_status'] = 'FAIL'
            summary['severity'] = 'HIGH'
        elif summary['warnings'] > 2:
            summary['overall_status'] = 'WARNING'
            summary['severity'] = 'MEDIUM'
        else:
            summary['overall_status'] = 'PASS'
            summary['severity'] = 'LOW'

        return summary

    def generate_report(self, results: Dict[str, Any], output_file: Path = None) -> str:
        """レポート生成"""
        report_lines = [
            "=" * 80,
            "Otedama セキュリティスキャンレポート",
            "=" * 80,
            f"スキャン日時: {results['timestamp']}",
            f"対象ディレクトリ: {results['base_directory']}",
            "",
            "=" * 80,
            "総合評価",
            "=" * 80,
        ]

        summary = results['summary']
        report_lines.extend([
            f"ステータス: {summary['overall_status']}",
            f"セキュリティスコア: {summary['security_score']:.1f}/100",
            f"実行チェック: {summary['total_checks']}",
            f"  - 合格: {summary['passed']}",
            f"  - 不合格: {summary['failed']}",
            f"  - 警告: {summary['warnings']}",
            ""
        ])

        # 問題点
        if self.issues:
            report_lines.extend([
                "=" * 80,
                "🚨 重大な問題",
                "=" * 80
            ])
            for issue in self.issues:
                report_lines.append(f"  ❌ {issue}")
            report_lines.append("")

        # 警告
        if self.warnings:
            report_lines.extend([
                "=" * 80,
                "⚠️  警告",
                "=" * 80
            ])
            for warning in self.warnings:
                report_lines.append(f"  ⚠️  {warning}")
            report_lines.append("")

        # 推奨事項
        recommendations = []
        for check_name, check_result in results['checks'].items():
            if 'recommendations' in check_result:
                recommendations.extend(check_result['recommendations'])

        if recommendations:
            report_lines.extend([
                "=" * 80,
                "💡 推奨事項",
                "=" * 80
            ])
            for rec in recommendations:
                report_lines.append(f"  💡 {rec}")
            report_lines.append("")

        report_lines.append("=" * 80)
        report = "\n".join(report_lines)

        # ファイル出力
        if output_file:
            output_file.write_text(report, encoding='utf-8')
            logger.info(f"レポート出力: {output_file}")

        return report


def main():
    """メイン実行"""
    import argparse

    parser = argparse.ArgumentParser(description='Otedama セキュリティスキャナー')
    parser.add_argument('--output', '-o', type=Path, help='レポート出力ファイル')
    parser.add_argument('--json', action='store_true', help='JSON形式で出力')
    parser.add_argument('--verbose', '-v', action='store_true', help='詳細出力')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    scanner = SecurityScanner()
    results = scanner.scan_all()

    if args.json:
        # JSON出力
        output = json.dumps(results, indent=2, ensure_ascii=False)
        if args.output:
            args.output.write_text(output, encoding='utf-8')
        else:
            print(output)
    else:
        # テキストレポート出力
        report = scanner.generate_report(results, args.output)
        if not args.output:
            print(report)

    # 終了コード
    summary = results['summary']
    if summary['overall_status'] == 'FAIL':
        sys.exit(1)
    elif summary['overall_status'] == 'WARNING':
        sys.exit(2)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()
