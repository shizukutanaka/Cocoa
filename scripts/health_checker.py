#!/usr/bin/env python3
"""
Cocoa プロジェクト健全性チェッカー
Project Health Checker for Cocoa

このスクリプトはプロジェクト全体の健全性をチェックし、
改善点を自動的に検出・報告します。
"""
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List


class CocoaHealthChecker:
    """Cocoaプロジェクトの健全性チェッカー"""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.issues: List[Dict[str, Any]] = []
        self.warnings: List[Dict[str, Any]] = []
        self.passed_checks: List[str] = []

    def run_all_checks(self) -> Dict[str, Any]:
        """すべての健全性チェックを実行"""
        print("🔍 Cocoaプロジェクト健全性チェックを開始します...")
        print("=" * 60)

        # 基本構造チェック
        self._check_project_structure()
        self._check_language_files()
        self._check_duplicate_files()
        self._check_security_issues()
        self._check_code_quality()
        self._check_dependencies()
        self._check_documentation()

        # 結果集計
        total_checks = len(self.passed_checks) + len(self.warnings) + len(self.issues)
        score = (len(self.passed_checks) / total_checks) * 100 if total_checks > 0 else 0

        result = {
            "timestamp": time.time(),
            "score": round(score, 1),
            "total_checks": total_checks,
            "passed": len(self.passed_checks),
            "warnings": len(self.warnings),
            "issues": len(self.issues),
            "passed_checks": self.passed_checks,
            "warning_details": self.warnings,
            "issue_details": self.issues
        }

        self._print_report(result)
        return result

    def _check_project_structure(self):
        """プロジェクト構造のチェック"""
        required_dirs = ['main', 'docs', 'tests', 'config', 'locales', 'scripts']
        required_files = ['README.md', 'requirements.txt']

        # 必須ディレクトリの存在チェック
        for dir_name in required_dirs:
            if (self.project_root / dir_name).exists():
                self.passed_checks.append(f"必須ディレクトリ '{dir_name}' が存在します")
            else:
                self.issues.append({
                    "type": "structure",
                    "severity": "high",
                    "message": f"必須ディレクトリ '{dir_name}' が存在しません"
                })

        # 必須ファイルの存在チェック
        for file_name in required_files:
            if (self.project_root / file_name).exists():
                self.passed_checks.append(f"必須ファイル '{file_name}' が存在します")
            else:
                self.issues.append({
                    "type": "structure",
                    "severity": "high",
                    "message": f"必須ファイル '{file_name}' が存在しません"
                })

    def _check_language_files(self):
        """言語ファイルのチェック"""
        locales_dir = self.project_root / 'locales'
        main_dir = self.project_root / 'main'

        if not locales_dir.exists():
            self.issues.append({
                "type": "localization",
                "severity": "medium",
                "message": "localesディレクトリが存在しません"
            })
            return

        # locales内の言語ファイル
        locales_files = list(locales_dir.glob('*.json'))
        # 2文字言語コードのファイル (例: ja.json, en.json) を検出する。
        # ステム長で判定する ("ja.json" -> stem "ja" -> len 2)。
        main_lang_files = [f for f in main_dir.glob('*.json') if len(f.stem) == 2]

        if main_lang_files:
            self.warnings.append({
                "type": "localization",
                "severity": "medium",
                "message": f"mainディレクトリに言語ファイルが{len(main_lang_files)}個存在します。localesディレクトリに統合することを推奨します",
                "files": [str(f) for f in main_lang_files]
            })

        if len(locales_files) < 2:
            self.warnings.append({
                "type": "localization",
                "severity": "low",
                "message": "言語ファイルが2つ未満です。多言語対応の拡充を推奨します"
            })
        else:
            self.passed_checks.append(f"言語ファイルが{len(locales_files)}個存在します")

    def _check_duplicate_files(self):
        """重複ファイルのチェック"""
        hashes = {}
        duplicates = []

        for root, dirs, files in os.walk(str(self.project_root)):
            # .git, __pycache__などは除外
            dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']

            for file in files:
                if file.endswith(('.py', '.json', '.md')):
                    filepath = Path(root) / file
                    try:
                        with open(filepath, 'rb') as f:
                            file_hash = hashlib.md5(f.read()).hexdigest()

                        if file_hash in hashes:
                            duplicates.append((str(filepath), str(hashes[file_hash])))
                        else:
                            hashes[file_hash] = filepath
                    except Exception:
                        pass

        if duplicates:
            self.issues.append({
                "type": "duplicates",
                "severity": "medium",
                "message": f"重複ファイルが{len(duplicates)}組検出されました",
                "duplicates": duplicates
            })
        else:
            self.passed_checks.append("重複ファイルは検出されませんでした")

    def _check_security_issues(self):
        """セキュリティ問題のチェック"""
        # ハードコードされたパスワードなどのチェック
        suspicious_patterns = [
            r'password\s*=\s*["\'][^"\']*["\']',
            r'api_key\s*=\s*["\'][^"\']*["\']',
            r'secret\s*=\s*["\'][^"\']*["\']',
            r'token\s*=\s*["\'][^"\']*["\']'
        ]

        security_issues = []
        for pattern in suspicious_patterns:
            try:
                result = subprocess.run([
                    'grep', '-r', '-n', pattern, str(self.project_root)
                ], capture_output=True, text=True, cwd=self.project_root)

                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    if lines and lines[0]:
                        security_issues.extend(lines)
            except Exception:
                pass

        if security_issues:
            self.issues.append({
                "type": "security",
                "severity": "high",
                "message": "潜在的なセキュリティ問題が検出されました",
                "details": security_issues[:10]  # 最初の10件のみ
            })
        else:
            self.passed_checks.append("重大なセキュリティ問題は検出されませんでした")

    def _check_code_quality(self):
        """コード品質のチェック"""
        python_files = list(self.project_root.rglob('*.py'))

        # 構文チェック
        syntax_errors = []
        for py_file in python_files:
            try:
                compile(py_file.read_text(), str(py_file), 'exec')
            except SyntaxError as e:
                syntax_errors.append(f"{py_file}: {e}")

        if syntax_errors:
            self.issues.append({
                "type": "code_quality",
                "severity": "high",
                "message": f"構文エラーが{len(syntax_errors)}件検出されました",
                "errors": syntax_errors
            })
        else:
            self.passed_checks.append(f"Pythonファイル{len(python_files)}個の構文チェックが完了しました")

        # 大きなファイルの警告
        large_files = []
        for py_file in python_files:
            if py_file.stat().st_size > 100000:  # 100KB以上
                large_files.append((str(py_file), py_file.stat().st_size))

        if large_files:
            self.warnings.append({
                "type": "code_quality",
                "severity": "low",
                "message": f"大容量ファイルが{len(large_files)}個検出されました。分割を検討してください",
                "files": large_files
            })

    def _check_dependencies(self):
        """依存関係のチェック"""
        req_file = self.project_root / 'requirements.txt'
        if req_file.exists():
            self.passed_checks.append("requirements.txtが存在します")

            # 依存関係の解析
            try:
                with open(req_file, 'r') as f:
                    deps = [line.strip() for line in f if line.strip() and not line.startswith('#')]

                if len(deps) > 50:
                    self.warnings.append({
                        "type": "dependencies",
                        "severity": "medium",
                        "message": f"依存関係が{len(deps)}個と多いです。整理を検討してください"
                    })
                else:
                    self.passed_checks.append(f"依存関係が{len(deps)}個適切に定義されています")

            except Exception as e:
                self.warnings.append({
                    "type": "dependencies",
                    "severity": "low",
                    "message": f"requirements.txtの解析に失敗しました: {e}"
                })
        else:
            self.warnings.append({
                "type": "dependencies",
                "severity": "medium",
                "message": "requirements.txtが見つかりません"
            })

    def _check_documentation(self):
        """ドキュメントのチェック"""
        docs_dir = self.project_root / 'docs'
        readme_file = self.project_root / 'README.md'

        if not readme_file.exists():
            self.issues.append({
                "type": "documentation",
                "severity": "high",
                "message": "README.mdが見つかりません"
            })
        else:
            self.passed_checks.append("README.mdが存在します")

        if docs_dir.exists():
            doc_files = list(docs_dir.glob('*.md'))
            if len(doc_files) > 5:
                self.passed_checks.append(f"ドキュメントファイルが{len(doc_files)}個存在します")
            else:
                self.warnings.append({
                    "type": "documentation",
                    "severity": "low",
                    "message": f"ドキュメントファイルが{len(doc_files)}個と少ないです。拡充を検討してください"
                })
        else:
            self.warnings.append({
                "type": "documentation",
                "severity": "medium",
                "message": "docsディレクトリが存在しません"
            })

    def _print_report(self, result: Dict[str, Any]):
        """結果レポートを表示"""
        print("\n" + "=" * 60)
        print("🏥 健全性チェック結果 / Health Check Results")
        print("=" * 60)

        print(f"📊 スコア / Score: {result['score']}%")
        print(f"✅ 成功 / Passed: {result['passed']}")
        print(f"⚠️  警告 / Warnings: {result['warnings']}")
        print(f"❌ 問題 / Issues: {result['issues']}")
        print()

        if result['issue_details']:
            print("🔴 修正が必要な問題 / Issues requiring fixes:")
            for issue in result['issue_details']:
                severity_icon = "🔴" if issue['severity'] == 'high' else "🟡" if issue['severity'] == 'medium' else "🟢"
                print(f"  {severity_icon} {issue['message']}")

        if result['warning_details']:
            print("\n🟡 改善推奨事項 / Recommended improvements:")
            for warning in result['warning_details']:
                print(f"  🟡 {warning['message']}")

        print("\n✅ 正常に確認された項目 / Successfully verified:")
        for check in result['passed_checks'][:10]:  # 最初の10件のみ表示
            print(f"  ✅ {check}")

        if len(result['passed_checks']) > 10:
            print(f"  ... 他 {len(result['passed_checks']) - 10} 件")

        print("\n" + "=" * 60)


def main():
    """メイン実行関数"""
    project_root = Path(__file__).resolve().parent.parent

    checker = CocoaHealthChecker(project_root)
    result = checker.run_all_checks()

    # JSON出力
    output_file = project_root / 'health_check_report.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\n📄 詳細レポートを保存しました / Detailed report saved: {output_file}")

    # 終了コード
    sys.exit(0 if result['issues'] == 0 else 1)


if __name__ == "__main__":
    main()
