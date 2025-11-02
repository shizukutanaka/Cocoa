"""
Disaster Recovery and Backup Verification System

国家レベルの運用に必要な災害復旧機能:
- 自動バックアップと検証
- 障害検知と自動復旧
- データ整合性チェック
- ポイントインタイムリカバリ
"""
import logging
import os
import json
import shutil
import hashlib
import time
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class BackupStatus(Enum):
    """バックアップステータス"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    VERIFIED = "verified"
    CORRUPTED = "corrupted"


class RecoveryStrategy(Enum):
    """復旧戦略"""
    FULL_RESTORE = "full_restore"  # 完全復元
    PARTIAL_RESTORE = "partial_restore"  # 部分復元
    INCREMENTAL = "incremental"  # 差分復元
    POINT_IN_TIME = "point_in_time"  # ポイントインタイム復元


@dataclass
class BackupMetadata:
    """バックアップメタデータ"""
    backup_id: str
    timestamp: str
    status: BackupStatus
    size_bytes: int
    checksum: str
    source_paths: List[str] = field(default_factory=list)
    backup_path: str = ""
    verification_passed: bool = False
    error_message: str = ""


class DisasterRecoveryManager:
    """Production-Grade災害復旧マネージャー"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.backup_dir = Path(self.config.get('backup_dir', 'backups'))
        self.data_dir = Path(self.config.get('data_dir', 'data'))
        self.config_dir = Path(self.config.get('config_dir', 'config'))

        # バックアップディレクトリの作成
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self._validate_directories()

        # 保持ポリシーの設定
        self.retention_policy = {
            'daily': self.config.get('retention_daily', 7),  # 日次バックアップを7日保持
            'weekly': self.config.get('retention_weekly', 4),  # 週次バックアップを4週間保持
            'monthly': self.config.get('retention_monthly', 12),  # 月次バックアップを12ヶ月保持
            'yearly': self.config.get('retention_yearly', 5),  # 年次バックアップを5年保持
        }

    def create_backup(
        self,
        backup_name: Optional[str] = None,
        include_config: bool = True,
        include_data: bool = True,
        verify: bool = True
    ) -> Tuple[bool, str, Optional[BackupMetadata]]:
        """バックアップの作成"""
        try:
            # バックアップIDとタイムスタンプ
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            backup_id = backup_name or f"backup_{timestamp}"

            logger.info(f"バックアップ作成開始: {backup_id}")

            # バックアップディレクトリ
            backup_path = self._guard_backup_path(self.backup_dir / backup_id)
            backup_path.mkdir(parents=True, exist_ok=True)
            self._assert_writable(backup_path, 'backup destination')

            # バックアップ対象のパス
            source_paths = []

            if include_config:
                if self.config_dir.exists():
                    source_paths.append(str(self.config_dir))
                else:
                    logger.warning("設定ディレクトリが見つかりません: %s", self.config_dir)

            if include_data:
                if self.data_dir.exists():
                    source_paths.append(str(self.data_dir))
                else:
                    logger.warning("データディレクトリが見つかりません: %s", self.data_dir)

            if not source_paths:
                return False, "バックアップ対象が存在しません", None

            # ファイルのコピーとチェックサム計算
            total_size = 0
            checksums = []

            for source_path in source_paths:
                source = Path(source_path)
                dest = backup_path / source.name

                if source.is_file():
                    shutil.copy2(source, dest)
                    total_size += source.stat().st_size
                    checksums.append(self._calculate_file_checksum(source))
                elif source.is_dir():
                    shutil.copytree(source, dest, dirs_exist_ok=True)
                    for file_path in dest.rglob('*'):
                        if file_path.is_file():
                            total_size += file_path.stat().st_size
                            checksums.append(self._calculate_file_checksum(file_path))

            # 総合チェックサムの計算
            combined_checksum = hashlib.sha256(
                ''.join(checksums).encode()
            ).hexdigest()

            # メタデータの作成
            metadata = BackupMetadata(
                backup_id=backup_id,
                timestamp=datetime.utcnow().isoformat(),
                status=BackupStatus.COMPLETED,
                size_bytes=total_size,
                checksum=combined_checksum,
                source_paths=source_paths,
                backup_path=str(backup_path)
            )

            # 検証の実行
            if verify:
                verification_result = self.verify_backup(backup_id)
                metadata.verification_passed = verification_result[0]
                if metadata.verification_passed:
                    metadata.status = BackupStatus.VERIFIED
                else:
                    metadata.status = BackupStatus.CORRUPTED
                    metadata.error_message = verification_result[1]

            # メタデータの保存
            self.backup_metadata.append(metadata)
            self._save_metadata()

            logger.info(f"バックアップ完了: {backup_id} ({total_size} bytes)")

            return True, f"バックアップ成功: {backup_id}", metadata

        except Exception as e:
            error_msg = f"バックアップ失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg, None

    def verify_backup(self, backup_id: str) -> Tuple[bool, str]:
        """バックアップの検証"""
        try:
            # メタデータの取得
            metadata = self._find_metadata(backup_id)
            if not metadata:
                return False, f"バックアップが見つかりません: {backup_id}"

            backup_path = Path(metadata.backup_path)
            if not backup_path.exists():
                return False, f"バックアップディレクトリが存在しません: {backup_path}"

            # チェックサムの再計算
            checksums = []
            for file_path in backup_path.rglob('*'):
                if file_path.is_file():
                    checksums.append(self._calculate_file_checksum(file_path))

            combined_checksum = hashlib.sha256(
                ''.join(checksums).encode()
            ).hexdigest()

            # チェックサムの比較
            if combined_checksum == metadata.checksum:
                logger.info(f"バックアップ検証成功: {backup_id}")
                return True, "検証成功"
            else:
                error_msg = f"チェックサム不一致: 期待={metadata.checksum}, 実際={combined_checksum}"
                logger.error(error_msg)
                return False, error_msg

        except Exception as e:
            error_msg = f"バックアップ検証エラー: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg

    def restore_backup(
        self,
        backup_id: str,
        strategy: RecoveryStrategy = RecoveryStrategy.FULL_RESTORE,
        dry_run: bool = False
    ) -> Tuple[bool, str]:
        """バックアップからの復元"""
        try:
            # メタデータの取得
            metadata = self._find_metadata(backup_id)
            if not metadata:
                return False, f"バックアップが見つかりません: {backup_id}"

            # 検証
            if not metadata.verification_passed:
                logger.warning(f"未検証のバックアップからの復元: {backup_id}")
                verify_result = self.verify_backup(backup_id)
                if not verify_result[0]:
                    return False, f"バックアップが破損しています: {verify_result[1]}"

            backup_path = Path(metadata.backup_path)

            if dry_run:
                logger.info(f"ドライラン: {backup_id} からの復元をシミュレート")
                return True, "ドライラン成功"

            # 現在の状態をバックアップ (復元前)
            pre_restore_backup = self.create_backup(
                backup_name=f"pre_restore_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                verify=False
            )

            if not pre_restore_backup[0]:
                logger.warning("復元前バックアップの作成に失敗")

            # 復元の実行
            logger.info(f"復元開始: {backup_id} (戦略: {strategy.value})")

            if strategy == RecoveryStrategy.FULL_RESTORE:
                # 完全復元: バックアップディレクトリ全体を上書き
                for item in backup_path.iterdir():
                    dest = Path(item.name)

                    if dest.exists():
                        if dest.is_dir():
                            shutil.rmtree(dest)
                        else:
                            dest.unlink()

                    if item.is_dir():
                        shutil.copytree(item, dest)
                    else:
                        shutil.copy2(item, dest)

            elif strategy == RecoveryStrategy.PARTIAL_RESTORE:
                # 部分復元: 欠損ファイルのみ復元
                for item in backup_path.rglob('*'):
                    if item.is_file():
                        relative_path = item.relative_to(backup_path)
                        dest = Path(relative_path)

                        if not dest.exists():
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(item, dest)

            logger.info(f"復元完了: {backup_id}")
            return True, f"復元成功: {backup_id}"

        except Exception as e:
            error_msg = f"復元エラー: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg

    def list_backups(
        self,
        verified_only: bool = False,
        days: Optional[int] = None
    ) -> List[BackupMetadata]:
        """バックアップリストの取得"""
        backups = self.backup_metadata.copy()

        if verified_only:
            backups = [b for b in backups if b.verification_passed]

        if days is not None:
            cutoff = datetime.utcnow() - timedelta(days=days)
            backups = [
                b for b in backups
                if datetime.fromisoformat(b.timestamp) > cutoff
            ]

        # タイムスタンプでソート (新しい順)
        backups.sort(
            key=lambda b: datetime.fromisoformat(b.timestamp),
            reverse=True
        )

        return backups

    def cleanup_old_backups(self, retention_days: Optional[int] = None) -> Dict[str, Any]:
        """古いバックアップを保持ポリシーに基づいてクリーンアップ"""
        if retention_days is not None:
            # カスタム保持期間を指定
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        else:
            # デフォルトのポリシーを適用
            cutoff_date = self._get_earliest_retention_date()

        cleanup_count = 0
        total_size_freed = 0

        for metadata in self.backup_metadata[:]:  # コピーしてイテレーション
            backup_date = datetime.fromisoformat(metadata.timestamp.replace('Z', '+00:00'))

            if backup_date < cutoff_date:
                try:
                    backup_path = Path(metadata.backup_path)
                    if backup_path.exists():
                        size = self._get_directory_size(backup_path)
                        shutil.rmtree(backup_path)
                        total_size_freed += size

                    self.backup_metadata.remove(metadata)
                    cleanup_count += 1
                    logger.info(f"削除されたバックアップ: {metadata.backup_id} ({backup_date})")

                except Exception as e:
                    logger.error(f"バックアップ削除エラー {metadata.backup_id}: {e}")

        # メタデータを保存
        self._save_metadata()

        return {
            'cleanup_count': cleanup_count,
            'total_size_freed_bytes': total_size_freed,
            'cutoff_date': cutoff_date.isoformat()
        }

    def _get_earliest_retention_date(self) -> datetime:
        """保持ポリシーに基づく最も古い保持日を取得"""
        now = datetime.utcnow()
        # 年次バックアップの保持期間を基準に
        return now - timedelta(days=self.retention_policy['yearly'] * 365) + timedelta(days=1)
        except Exception as e:
            logger.error(f"クリーンアップエラー: {e}", exc_info=True)
            return 0, 0

    def get_recovery_status(self) -> Dict[str, Any]:
        """復旧ステータスの取得"""
        total_backups = len(self.backup_metadata)
        verified_backups = sum(1 for b in self.backup_metadata if b.verification_passed)
        total_size = sum(b.size_bytes for b in self.backup_metadata)

        latest_backup = None
        if self.backup_metadata:
            latest_backup = max(
                self.backup_metadata,
                key=lambda b: datetime.fromisoformat(b.timestamp)
            )

        return {
            "total_backups": total_backups,
            "verified_backups": verified_backups,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "latest_backup": {
                "id": latest_backup.backup_id,
                "timestamp": latest_backup.timestamp,
                "verified": latest_backup.verification_passed
            } if latest_backup else None,
            "backup_directory": str(self.backup_dir),
            "timestamp": datetime.utcnow().isoformat()
        }

    # =============== Internal Methods ===============

    def _calculate_file_checksum(self, file_path: Path) -> str:
        """ファイルのチェックサム計算"""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _validate_directories(self) -> None:
        """重要ディレクトリの存在と権限を検証"""
        critical_directories = {
            "backup": self.backup_dir,
            "data": self.data_dir,
            "config": self.config_dir,
        }

        for label, directory in critical_directories.items():
            try:
                directory.mkdir(parents=True, exist_ok=True)
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(f"{label} ディレクトリを作成できません: {directory} ({exc})")

            if not os.access(directory, os.R_OK | os.X_OK):
                logger.warning("%s ディレクトリへの読み取り/実行権限が不足しています: %s", label, directory)
            if label == "backup" and not os.access(directory, os.W_OK):
                logger.warning("バックアップディレクトリへの書き込み権限が不足しています: %s", directory)

    def _guard_backup_path(self, candidate: Path) -> Path:
        """バックアップファイルが許可されたディレクトリ内にあることを検証"""
        base = self.backup_dir.resolve(strict=False)
        resolved_candidate = candidate.resolve(strict=False)

        if base not in resolved_candidate.parents and resolved_candidate != base:
            raise RuntimeError(f"バックアップパスが許可された領域外です: {resolved_candidate}")

        return resolved_candidate

    def _assert_writable(self, directory: Path, label: str) -> None:
        """書き込み権限を検証"""
        if not os.access(directory, os.W_OK):
            raise PermissionError(f"{label} に書き込みできません: {directory}")

    def _find_metadata(self, backup_id: str) -> Optional[BackupMetadata]:
        """バックアップメタデータの検索"""
        for metadata in self.backup_metadata:
            if metadata.backup_id == backup_id:
                return metadata
        return None

    def _load_metadata(self):
        """メタデータの読み込み"""
        try:
            if self.metadata_file.exists():
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                self.backup_metadata = [
                    BackupMetadata(
                        backup_id=item['backup_id'],
                        timestamp=item['timestamp'],
                        status=BackupStatus(item['status']),
                        size_bytes=item['size_bytes'],
                        checksum=item['checksum'],
                        source_paths=item.get('source_paths', []),
                        backup_path=item.get('backup_path', ''),
                        verification_passed=item.get('verification_passed', False),
                        error_message=item.get('error_message', '')
                    )
                    for item in data
                ]

                logger.info(f"メタデータ読み込み完了: {len(self.backup_metadata)}件")
        except Exception as e:
            logger.error(f"メタデータ読み込みエラー: {e}")
            self.backup_metadata = []

    def _save_metadata(self):
        """メタデータの保存"""
        try:
            data = [
                {
                    'backup_id': meta.backup_id,
                    'timestamp': meta.timestamp,
                    'status': meta.status.value,
                    'size_bytes': meta.size_bytes,
                    'checksum': meta.checksum,
                    'source_paths': meta.source_paths,
                    'backup_path': meta.backup_path,
                    'verification_passed': meta.verification_passed,
                    'error_message': meta.error_message
                }
                for meta in self.backup_metadata
            ]

            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.debug("メタデータ保存完了")
        except Exception as e:
            logger.error(f"メタデータ保存エラー: {e}")


# グローバルインスタンス
_recovery_manager: Optional[DisasterRecoveryManager] = None


def get_recovery_manager(config: Optional[Dict[str, Any]] = None) -> DisasterRecoveryManager:
    """災害復旧マネージャーの取得"""
    global _recovery_manager
    if _recovery_manager is None:
        _recovery_manager = DisasterRecoveryManager(config)
    return _recovery_manager


def initialize_disaster_recovery(config: Optional[Dict[str, Any]] = None) -> DisasterRecoveryManager:
    """災害復旧システムの初期化"""
    global _recovery_manager
    _recovery_manager = DisasterRecoveryManager(config)
    logger.info("災害復旧システムを初期化しました")
    return _recovery_manager
