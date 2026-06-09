#!/usr/bin/env python3
"""
Cocoaデータベース移行スクリプト
ファイルベースのデータをデータベースに移行

使用法:
    python scripts/migrate_to_database.py [--backup] [--dry-run] [--config database.json]

オプション:
    --backup        移行前にバックアップを作成
    --dry-run       実際の移行を行わずに処理内容を表示
    --config        データベース設定ファイルのパス
    --force         移行済みでも強制実行
"""

import sys
import os
import json
import argparse
import logging
import shutil
from typing import Dict, Any, List
from pathlib import Path
from datetime import datetime, timezone

# Cocoaモジュールのパスを追加
sys.path.insert(0, str(Path(__file__).parent.parent / "main"))

try:
    from database_integration import CocoaDatabaseIntegration
    from database_manager import DatabaseType
except ImportError as e:
    print(f"エラー: Cocoaモジュールをインポートできません: {e}")
    sys.exit(1)

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('migration.log')
    ]
)
logger = logging.getLogger(__name__)


class CocoaDataMigrator:
    """Cocoaデータ移行クラス"""

    def __init__(self, config_path: str = "config/database.json", dry_run: bool = False):
        """初期化"""
        self.config_path = Path(config_path)
        self.dry_run = dry_run
        self.project_root = Path(__file__).parent.parent
        self.migration_stats = {
            "presets_migrated": 0,
            "configs_migrated": 0,
            "errors": 0,
            "start_time": datetime.now(timezone.utc)
        }

        # プロジェクトルートに移動
        os.chdir(self.project_root)

        logger.info(f"データ移行{'（ドライラン）' if dry_run else ''}を開始します")
        logger.info(f"プロジェクトルート: {self.project_root}")

    def create_backup(self) -> str:
        """移行前バックアップ作成"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = Path(f"backups/migration_backup_{timestamp}")
            backup_dir.mkdir(parents=True, exist_ok=True)

            # バックアップ対象
            backup_targets = [
                "presets",
                "config",
                "data",
                "logs"
            ]

            for target in backup_targets:
                source_path = Path(target)
                if source_path.exists():
                    if source_path.is_dir():
                        shutil.copytree(source_path, backup_dir / target, dirs_exist_ok=True)
                    else:
                        shutil.copy2(source_path, backup_dir / target)

            logger.info(f"バックアップ作成完了: {backup_dir}")
            return str(backup_dir)

        except Exception as e:
            logger.error(f"バックアップ作成エラー: {e}")
            raise

    def scan_existing_data(self) -> Dict[str, Any]:
        """既存データのスキャン"""
        scan_results = {
            "presets": [],
            "config_files": [],
            "other_json_files": [],
            "total_files": 0
        }

        try:
            # プリセットディレクトリのスキャン
            presets_dir = Path("presets")
            if presets_dir.exists():
                for preset_file in presets_dir.glob("*.json"):
                    try:
                        with open(preset_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)

                        scan_results["presets"].append({
                            "file": str(preset_file),
                            "id": preset_file.stem,
                            "name": data.get('name', preset_file.stem),
                            "size": preset_file.stat().st_size,
                            "modified": datetime.fromtimestamp(preset_file.stat().st_mtime)
                        })
                    except Exception as e:
                        logger.warning(f"プリセットファイル読み込み警告: {preset_file} - {e}")

            # 設定ファイルのスキャン
            config_files = [
                "config/config.json",
                "config/plugins.json",
                "config/users.json"
            ]

            for config_file in config_files:
                config_path = Path(config_file)
                if config_path.exists():
                    scan_results["config_files"].append({
                        "file": str(config_path),
                        "size": config_path.stat().st_size,
                        "modified": datetime.fromtimestamp(config_path.stat().st_mtime)
                    })

            # その他のJSONファイル
            for json_file in Path(".").rglob("*.json"):
                if (json_file.name not in ["package.json", "package-lock.json"] and
                    "node_modules" not in str(json_file) and
                    ".git" not in str(json_file) and
                    "backups" not in str(json_file)):

                    scan_results["other_json_files"].append({
                        "file": str(json_file),
                        "size": json_file.stat().st_size
                    })

            scan_results["total_files"] = (
                len(scan_results["presets"]) +
                len(scan_results["config_files"]) +
                len(scan_results["other_json_files"])
            )

            logger.info(f"データスキャン完了: {scan_results['total_files']}個のファイル")
            return scan_results

        except Exception as e:
            logger.error(f"データスキャンエラー: {e}")
            raise

    def migrate_presets(self, db_integration: CocoaDatabaseIntegration,
                       presets_info: List[Dict[str, Any]]) -> int:
        """プリセットデータの移行"""
        migrated_count = 0

        try:
            with db_integration.transaction():
                for preset_info in presets_info:
                    try:
                        # プリセットファイル読み込み
                        preset_file = Path(preset_info["file"])
                        with open(preset_file, 'r', encoding='utf-8') as f:
                            preset_data = json.load(f)

                        preset_id = preset_info["id"]
                        preset_name = preset_info["name"]

                        if not self.dry_run:
                            # データベースに保存
                            success = db_integration.save_preset(
                                preset_id, preset_name, preset_data
                            )

                            if success:
                                migrated_count += 1
                                logger.info(f"プリセット移行完了: {preset_id}")
                            else:
                                logger.error(f"プリセット移行失敗: {preset_id}")
                                self.migration_stats["errors"] += 1
                        else:
                            logger.info(f"[ドライラン] プリセット移行予定: {preset_id}")
                            migrated_count += 1

                    except Exception as e:
                        logger.error(f"プリセット移行エラー: {preset_info['file']} - {e}")
                        self.migration_stats["errors"] += 1

                if not self.dry_run:
                    logger.info(f"プリセット移行トランザクション完了: {migrated_count}個")

        except Exception as e:
            logger.error(f"プリセット移行トランザクションエラー: {e}")
            raise

        return migrated_count

    def migrate_configurations(self, db_integration: CocoaDatabaseIntegration,
                             config_files: List[Dict[str, Any]]) -> int:
        """設定ファイルの移行"""
        migrated_count = 0

        try:
            with db_integration.transaction():
                for config_info in config_files:
                    try:
                        config_file = Path(config_info["file"])

                        with open(config_file, 'r', encoding='utf-8') as f:
                            config_data = json.load(f)

                        # 設定ファイル名をキーのプレフィックスとして使用
                        file_prefix = config_file.stem

                        # 設定を個別のキーとして保存
                        for key, value in config_data.items():
                            config_key = f"{file_prefix}.{key}"

                            if not self.dry_run:
                                success = db_integration.set_configuration(config_key, value)
                                if success:
                                    migrated_count += 1
                                    logger.info(f"設定移行完了: {config_key}")
                                else:
                                    logger.error(f"設定移行失敗: {config_key}")
                                    self.migration_stats["errors"] += 1
                            else:
                                logger.info(f"[ドライラン] 設定移行予定: {config_key}")
                                migrated_count += 1

                    except Exception as e:
                        logger.error(f"設定ファイル移行エラー: {config_info['file']} - {e}")
                        self.migration_stats["errors"] += 1

                if not self.dry_run:
                    logger.info(f"設定移行トランザクション完了: {migrated_count}個")

        except Exception as e:
            logger.error(f"設定移行トランザクションエラー: {e}")
            raise

        return migrated_count

    def verify_migration(self, db_integration: CocoaDatabaseIntegration,
                        original_data: Dict[str, Any]) -> Dict[str, Any]:
        """移行後の検証"""
        verification_results = {
            "presets_verified": 0,
            "presets_failed": 0,
            "configs_verified": 0,
            "configs_failed": 0,
            "success": False
        }

        try:
            # プリセット検証
            db_presets = db_integration.list_presets()
            db_preset_ids = {preset["id"] for preset in db_presets}

            for preset_info in original_data["presets"]:
                preset_id = preset_info["id"]
                if preset_id in db_preset_ids:
                    # データ整合性チェック
                    db_preset = db_integration.load_preset(preset_id)
                    if db_preset:
                        verification_results["presets_verified"] += 1
                    else:
                        verification_results["presets_failed"] += 1
                        logger.error(f"プリセット検証失敗: {preset_id}")
                else:
                    verification_results["presets_failed"] += 1
                    logger.error(f"プリセットが見つかりません: {preset_id}")

            # 設定検証
            for config_info in original_data["config_files"]:
                config_file = Path(config_info["file"])
                file_prefix = config_file.stem

                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        original_config = json.load(f)

                    for key in original_config.keys():
                        config_key = f"{file_prefix}.{key}"
                        db_value = db_integration.get_configuration(config_key)

                        if db_value is not None:
                            verification_results["configs_verified"] += 1
                        else:
                            verification_results["configs_failed"] += 1
                            logger.error(f"設定が見つかりません: {config_key}")

                except Exception as e:
                    logger.error(f"設定検証エラー: {config_file} - {e}")

            # 全体的な成功判定
            total_failures = (
                verification_results["presets_failed"] +
                verification_results["configs_failed"]
            )
            verification_results["success"] = total_failures == 0

            logger.info(f"移行検証完了: 成功={verification_results['success']}")
            return verification_results

        except Exception as e:
            logger.error(f"移行検証エラー: {e}")
            verification_results["success"] = False
            return verification_results

    def generate_migration_report(self, scan_results: Dict[str, Any],
                                verification_results: Dict[str, Any]) -> str:
        """移行レポート生成"""
        end_time = datetime.now(timezone.utc)
        duration = end_time - self.migration_stats["start_time"]

        report = f"""
# Cocoaデータベース移行レポート

## 移行概要
- 実行時刻: {self.migration_stats['start_time'].strftime('%Y-%m-%d %H:%M:%S')}
- 完了時刻: {end_time.strftime('%Y-%m-%d %H:%M:%S')}
- 実行時間: {duration.total_seconds():.2f}秒
- モード: {'ドライラン' if self.dry_run else '実際の移行'}

## スキャン結果
- プリセットファイル: {len(scan_results['presets'])}個
- 設定ファイル: {len(scan_results['config_files'])}個
- その他JSONファイル: {len(scan_results['other_json_files'])}個
- 合計ファイル数: {scan_results['total_files']}個

## 移行結果
- プリセット移行数: {self.migration_stats['presets_migrated']}個
- 設定移行数: {self.migration_stats['configs_migrated']}個
- エラー数: {self.migration_stats['errors']}個

## 検証結果
- プリセット検証成功: {verification_results['presets_verified']}個
- プリセット検証失敗: {verification_results['presets_failed']}個
- 設定検証成功: {verification_results['configs_verified']}個
- 設定検証失敗: {verification_results['configs_failed']}個
- 全体成功: {'✅' if verification_results['success'] else '❌'}

## 詳細ログ
詳細な実行ログは migration.log をご確認ください。
"""

        return report

    def run_migration(self, backup: bool = False, force: bool = False) -> bool:
        """移行実行メイン処理"""
        try:
            # 既存の移行完了チェック
            migration_flag = Path("data/.migration_completed")
            if migration_flag.exists() and not force:
                logger.warning("データベース移行は既に完了しています。--force オプションで強制実行できます。")
                return True

            # バックアップ作成
            if backup and not self.dry_run:
                backup_path = self.create_backup()
                logger.info(f"バックアップ作成完了: {backup_path}")

            # 既存データスキャン
            logger.info("既存データをスキャンしています...")
            scan_results = self.scan_existing_data()

            if scan_results["total_files"] == 0:
                logger.info("移行対象のデータが見つかりません")
                return True

            # データベース統合初期化
            logger.info("データベース接続を初期化しています...")
            db_integration = CocoaDatabaseIntegration(str(self.config_path))

            # ヘルスチェック
            health = db_integration.health_check()
            if health["status"] != "healthy":
                logger.error(f"データベースヘルスチェック失敗: {health['message']}")
                return False

            # プリセット移行
            if scan_results["presets"]:
                logger.info(f"プリセット移行開始: {len(scan_results['presets'])}個")
                self.migration_stats["presets_migrated"] = self.migrate_presets(
                    db_integration, scan_results["presets"]
                )

            # 設定移行
            if scan_results["config_files"]:
                logger.info(f"設定移行開始: {len(scan_results['config_files'])}個")
                self.migration_stats["configs_migrated"] = self.migrate_configurations(
                    db_integration, scan_results["config_files"]
                )

            # 移行後検証
            if not self.dry_run:
                logger.info("移行後検証を実行しています...")
                verification_results = self.verify_migration(db_integration, scan_results)
            else:
                verification_results = {
                    "presets_verified": self.migration_stats["presets_migrated"],
                    "presets_failed": 0,
                    "configs_verified": self.migration_stats["configs_migrated"],
                    "configs_failed": 0,
                    "success": True
                }

            # レポート生成
            report = self.generate_migration_report(scan_results, verification_results)

            # レポート保存
            report_file = Path(f"migration_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")
            report_file.write_text(report, encoding='utf-8')

            logger.info(f"移行レポート保存: {report_file}")
            print(report)

            # 移行完了フラグ設定
            if not self.dry_run and verification_results["success"]:
                migration_flag.parent.mkdir(parents=True, exist_ok=True)
                migration_flag.write_text(datetime.now(timezone.utc).isoformat())
                logger.info("移行完了フラグを設定しました")

            db_integration.shutdown()
            return verification_results["success"]

        except Exception as e:
            logger.error(f"移行実行エラー: {e}")
            return False


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description="Cocoaデータベース移行スクリプト",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "--backup",
        action="store_true",
        help="移行前にバックアップを作成"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="実際の移行を行わずに処理内容を表示"
    )

    parser.add_argument(
        "--config",
        default="config/database.json",
        help="データベース設定ファイルのパス"
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="移行済みでも強制実行"
    )

    args = parser.parse_args()

    # 移行実行
    migrator = CocoaDataMigrator(args.config, args.dry_run)

    try:
        success = migrator.run_migration(args.backup, args.force)

        if success:
            logger.info("データベース移行が正常に完了しました")
            sys.exit(0)
        else:
            logger.error("データベース移行が失敗しました")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.warning("移行がユーザーによって中断されました")
        sys.exit(1)
    except Exception as e:
        logger.error(f"予期しないエラー: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()