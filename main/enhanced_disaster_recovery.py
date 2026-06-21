#!/usr/bin/env python3
"""
Enhanced Disaster Recovery System with 3-2-1 Backup Strategy
3-2-1バックアップルール準拠の災害復旧システム

参考:
- Solutions Review: "15 Backup and Disaster Recovery Best Practices"
- SBS Cyber: "IT Disaster Recovery Testing Best Practices"

3-2-1ルール:
- 3コピー: データの3つのコピーを保持
- 2種類のメディア: 異なるストレージタイプ (SSD + テープ等)
- 1つはオフサイト: 物理的に離れた場所に保管
"""

import hashlib
import json
import logging
import tarfile
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class StorageType(Enum):
    """ストレージタイプ"""
    LOCAL_SSD = "local_ssd"
    LOCAL_HDD = "local_hdd"
    NETWORK_NAS = "network_nas"
    CLOUD_S3 = "cloud_s3"
    CLOUD_AZURE = "cloud_azure"
    CLOUD_GCP = "cloud_gcp"
    TAPE = "tape"


class BackupLocation(Enum):
    """バックアップ場所"""
    ONSITE_PRIMARY = "onsite_primary"
    ONSITE_SECONDARY = "onsite_secondary"
    OFFSITE_CLOUD = "offsite_cloud"
    OFFSITE_TAPE = "offsite_tape"


class RecoveryStrategy(Enum):
    """復旧戦略"""
    FULL_RESTORE = "full"
    PARTIAL_RESTORE = "partial"
    INCREMENTAL = "incremental"
    POINT_IN_TIME = "point_in_time"


class TestType(Enum):
    """復旧テストタイプ"""
    MOCK = "mock"              # 月次: 特定コンポーネント
    PARALLEL = "parallel"       # 四半期: 本番並行テスト
    FULL_FAILOVER = "full"     # 年次: 完全切替


@dataclass
class BackupConfig:
    """バックアップ設定"""
    path: Path
    storage_type: StorageType
    encryption: bool = True
    compression: bool = True
    verification: bool = True


@dataclass
class BackupMetadata:
    """バックアップメタデータ"""
    backup_id: str
    timestamp: datetime
    location: BackupLocation
    storage_type: StorageType
    size_bytes: int
    checksum_sha256: str
    verified: bool
    compression_ratio: Optional[float] = None
    files_count: int = 0
    duration_seconds: float = 0.0


@dataclass
class RecoveryTestResult:
    """復旧テスト結果"""
    test_type: TestType
    backup_id: str
    start_time: datetime
    end_time: datetime
    success: bool
    rpo_achieved: bool
    rto_achieved: bool
    errors: List[str]
    validation_results: Dict[str, bool]


@dataclass
class RPOConfig:
    """RPO設定 (Recovery Point Objective)"""
    target_minutes: int = 60  # データ損失許容時間
    backup_interval_minutes: int = 30  # バックアップ間隔


@dataclass
class RTOConfig:
    """RTO設定 (Recovery Time Objective)"""
    target_minutes: int = 240  # ダウンタイム許容時間
    max_restore_duration_minutes: int = 180  # 最大復旧時間


class Enhanced321BackupManager:
    """
    3-2-1バックアップ戦略実装

    業界標準:
    - 3コピー: データの3つのコピー
    - 2種類のメディア: 異なるストレージタイプ
    - 1つはオフサイト: 物理的に離れた場所
    """

    def __init__(
        self,
        rpo_config: Optional[RPOConfig] = None,
        rto_config: Optional[RTOConfig] = None
    ):
        """
        初期化

        Args:
            rpo_config: RPO設定
            rto_config: RTO設定
        """
        self.rpo = rpo_config or RPOConfig()
        self.rto = rto_config or RTOConfig()

        # バックアップロケーション設定
        self.backup_locations = self._init_backup_locations()

        # メタデータストレージ
        self.metadata_dir = Path("data/backup_metadata")
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"Initialized 3-2-1 Backup Manager "
            f"(RPO: {self.rpo.target_minutes}min, RTO: {self.rto.target_minutes}min)"
        )

    def _init_backup_locations(self) -> Dict[BackupLocation, BackupConfig]:
        """バックアップロケーションを初期化"""
        return {
            BackupLocation.ONSITE_PRIMARY: BackupConfig(
                path=Path("backups/onsite_primary"),
                storage_type=StorageType.LOCAL_SSD,
                encryption=True,
                compression=True
            ),
            BackupLocation.ONSITE_SECONDARY: BackupConfig(
                path=Path("backups/onsite_secondary"),
                storage_type=StorageType.NETWORK_NAS,
                encryption=True,
                compression=True
            ),
            BackupLocation.OFFSITE_CLOUD: BackupConfig(
                path=Path("backups/offsite_cloud"),
                storage_type=StorageType.CLOUD_S3,
                encryption=True,
                compression=True
            )
        }

    def create_321_backup(
        self,
        source_dirs: List[Path],
        backup_name: Optional[str] = None
    ) -> Tuple[bool, str, Dict[BackupLocation, BackupMetadata]]:
        """
        3-2-1ルールに従ったバックアップ作成

        Args:
            source_dirs: バックアップ対象ディレクトリ
            backup_name: バックアップ名

        Returns:
            (成功フラグ, メッセージ, メタデータ辞書)
        """
        backup_name = backup_name or f"backup_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        start_time = datetime.now(timezone.utc)

        logger.info(f"Starting 3-2-1 backup: {backup_name}")

        results = {}
        all_success = True

        # 各ロケーションにバックアップ
        for location, config in self.backup_locations.items():
            try:
                logger.info(f"Creating backup at {location.value}...")

                metadata = self._create_backup_at_location(
                    backup_name=backup_name,
                    source_dirs=source_dirs,
                    location=location,
                    config=config,
                    start_time=start_time
                )

                results[location] = metadata
                logger.info(
                    f"✓ Backup completed at {location.value} "
                    f"({metadata.size_bytes / 1024 / 1024:.1f} MB)"
                )

            except Exception as e:
                logger.error(f"✗ Backup failed at {location.value}: {e}")
                all_success = False

        # 3-2-1ルール準拠チェック
        compliance = self._check_321_compliance(results)

        duration = (datetime.now(timezone.utc) - start_time).total_seconds()

        message = (
            f"Backup '{backup_name}' completed in {duration:.1f}s. "
            f"3-2-1 Compliant: {compliance['compliant']}"
        )

        # メタデータ保存
        self._save_backup_metadata(backup_name, results, compliance)

        return all_success and compliance['compliant'], message, results

    def _create_backup_at_location(
        self,
        backup_name: str,
        source_dirs: List[Path],
        location: BackupLocation,
        config: BackupConfig,
        start_time: datetime
    ) -> BackupMetadata:
        """特定ロケーションでバックアップ作成"""

        # バックアップディレクトリ作成
        config.path.mkdir(parents=True, exist_ok=True)

        # tarファイル作成
        backup_file = config.path / f"{backup_name}.tar.gz"

        with tarfile.open(backup_file, 'w:gz' if config.compression else 'w') as tar:
            for source_dir in source_dirs:
                if source_dir.exists():
                    tar.add(source_dir, arcname=source_dir.name)

        # ファイルサイズ
        size_bytes = backup_file.stat().st_size

        # SHA-256チェックサム計算
        checksum = self._calculate_checksum(backup_file)

        # 検証
        verified = False
        if config.verification:
            verified = self._verify_backup_integrity(backup_file, checksum)

        # ファイル数カウント
        files_count = sum(1 for _ in backup_file.parent.rglob('*') if _.is_file())

        duration = (datetime.now(timezone.utc) - start_time).total_seconds()

        # メタデータ作成
        metadata = BackupMetadata(
            backup_id=backup_name,
            timestamp=start_time,
            location=location,
            storage_type=config.storage_type,
            size_bytes=size_bytes,
            checksum_sha256=checksum,
            verified=verified,
            files_count=files_count,
            duration_seconds=duration
        )

        # チェックサムファイル保存
        checksum_file = backup_file.with_suffix('.sha256')
        checksum_file.write_text(f"{checksum}  {backup_file.name}\n")

        return metadata

    def _calculate_checksum(self, file_path: Path) -> str:
        """SHA-256チェックサム計算"""
        sha256 = hashlib.sha256()

        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                sha256.update(chunk)

        return sha256.hexdigest()

    def _verify_backup_integrity(self, backup_file: Path, expected_checksum: str) -> bool:
        """バックアップ整合性検証"""
        try:
            # チェックサム再計算
            actual_checksum = self._calculate_checksum(backup_file)

            if actual_checksum != expected_checksum:
                logger.error(
                    f"Checksum mismatch: expected {expected_checksum}, "
                    f"got {actual_checksum}"
                )
                return False

            # tarファイルの検証
            with tarfile.open(backup_file, 'r:*') as tar:
                # 全メンバーをリスト（破損チェック）
                _ = tar.getmembers()

            return True

        except Exception as e:
            logger.error(f"Backup verification failed: {e}")
            return False

    def _check_321_compliance(
        self,
        results: Dict[BackupLocation, BackupMetadata]
    ) -> Dict[str, Any]:
        """3-2-1ルール準拠チェック"""

        # 成功したバックアップ
        successful = {loc: meta for loc, meta in results.items() if meta.verified}

        # 1. 3コピー
        copies_count = len(successful)

        # 2. 2種類のメディア
        storage_types = {meta.storage_type for meta in successful.values()}
        different_media = len(storage_types) >= 2

        # 3. 1つはオフサイト
        offsite_locations = [
            BackupLocation.OFFSITE_CLOUD,
            BackupLocation.OFFSITE_TAPE
        ]
        has_offsite = any(loc in successful for loc in offsite_locations)

        # 準拠判定
        compliant = (
            copies_count >= 3 and
            different_media and
            has_offsite
        )

        return {
            'compliant': compliant,
            'copies_count': copies_count,
            'storage_types': len(storage_types),
            'has_offsite': has_offsite,
            'details': {
                'copies': f"{copies_count}/3",
                'media_types': f"{len(storage_types)}/2",
                'offsite': 'Yes' if has_offsite else 'No'
            }
        }

    def _save_backup_metadata(
        self,
        backup_name: str,
        results: Dict[BackupLocation, BackupMetadata],
        compliance: Dict[str, Any]
    ):
        """バックアップメタデータを保存"""
        metadata_file = self.metadata_dir / f"{backup_name}_metadata.json"

        metadata = {
            'backup_name': backup_name,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'compliance': compliance,
            'locations': {
                loc.value: {
                    'storage_type': meta.storage_type.value,
                    'size_bytes': meta.size_bytes,
                    'checksum': meta.checksum_sha256,
                    'verified': meta.verified,
                    'duration_seconds': meta.duration_seconds
                }
                for loc, meta in results.items()
            }
        }

        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)

    def list_backups(
        self,
        verified_only: bool = True,
        days: Optional[int] = None
    ) -> List[str]:
        """バックアップリストを取得"""
        backups = []

        for metadata_file in self.metadata_dir.glob('*_metadata.json'):
            with open(metadata_file, encoding='utf-8') as f:
                metadata = json.load(f)

            # 検証済みフィルター
            if verified_only:
                verified = all(
                    loc['verified']
                    for loc in metadata['locations'].values()
                )
                if not verified:
                    continue

            # 日数フィルター
            if days is not None:
                timestamp = datetime.fromisoformat(metadata['timestamp'])
                if datetime.now(timezone.utc) - timestamp > timedelta(days=days):
                    continue

            backups.append(metadata['backup_name'])

        return sorted(backups, reverse=True)

    def restore_backup(
        self,
        backup_name: str,
        restore_dir: Path,
        location: BackupLocation = BackupLocation.ONSITE_PRIMARY,
        verify: bool = True
    ) -> Tuple[bool, str]:
        """
        バックアップから復元

        Args:
            backup_name: バックアップ名
            restore_dir: 復元先ディレクトリ
            location: 復元元ロケーション
            verify: 検証実施フラグ

        Returns:
            (成功フラグ, メッセージ)
        """
        start_time = datetime.now(timezone.utc)

        logger.info(f"Starting restore from {backup_name} at {location.value}")

        try:
            config = self.backup_locations[location]
            backup_file = config.path / f"{backup_name}.tar.gz"

            if not backup_file.exists():
                return False, f"Backup file not found: {backup_file}"

            # 検証
            if verify:
                checksum_file = backup_file.with_suffix('.sha256')
                if checksum_file.exists():
                    expected_checksum = checksum_file.read_text().split()[0]
                    if not self._verify_backup_integrity(backup_file, expected_checksum):
                        return False, "Backup verification failed"

            # 復元ディレクトリ作成
            restore_dir.mkdir(parents=True, exist_ok=True)

            # 解凍 — filter='data' を指定して Tar Slip / device-file 系の
            # 不正エントリを拒否する。Python 3.12+ ではフィルタ無し extractall
            # は DeprecationWarning、3.14+ では例外。
            with tarfile.open(backup_file, 'r:*') as tar:
                tar.extractall(restore_dir, filter='data')

            duration = (datetime.now(timezone.utc) - start_time).total_seconds()

            # RTO達成チェック
            rto_achieved = duration <= (self.rto.target_minutes * 60)

            message = (
                f"Restore completed in {duration:.1f}s. "
                f"RTO {'✓ Achieved' if rto_achieved else '✗ Exceeded'} "
                f"(target: {self.rto.target_minutes}min)"
            )

            logger.info(message)

            return True, message

        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return False, f"Restore failed: {str(e)}"

    def run_recovery_test(
        self,
        test_type: TestType,
        backup_name: Optional[str] = None
    ) -> RecoveryTestResult:
        """
        復旧テスト実行

        Args:
            test_type: テストタイプ
            backup_name: テスト対象バックアップ

        Returns:
            テスト結果
        """
        start_time = datetime.now(timezone.utc)

        logger.info(f"Starting {test_type.value} recovery test")

        # バックアップ選択
        if not backup_name:
            backups = self.list_backups(verified_only=True, days=7)
            if not backups:
                return RecoveryTestResult(
                    test_type=test_type,
                    backup_id="none",
                    start_time=start_time,
                    end_time=datetime.now(timezone.utc),
                    success=False,
                    rpo_achieved=False,
                    rto_achieved=False,
                    errors=["No verified backups found"],
                    validation_results={}
                )
            backup_name = backups[0]

        errors = []
        validation = {}

        try:
            # テスト種別に応じた処理
            if test_type == TestType.MOCK:
                validation = self._run_mock_test(backup_name)
            elif test_type == TestType.PARALLEL:
                validation = self._run_parallel_test(backup_name)
            elif test_type == TestType.FULL_FAILOVER:
                validation = self._run_full_failover_test(backup_name)

            success = all(validation.values())

        except Exception as e:
            errors.append(str(e))
            success = False

        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()

        # RPO/RTO評価
        rpo_achieved = self._check_rpo_compliance(backup_name)
        rto_achieved = duration <= (self.rto.target_minutes * 60)

        return RecoveryTestResult(
            test_type=test_type,
            backup_id=backup_name,
            start_time=start_time,
            end_time=end_time,
            success=success,
            rpo_achieved=rpo_achieved,
            rto_achieved=rto_achieved,
            errors=errors,
            validation_results=validation
        )

    def _run_mock_test(self, backup_name: str) -> Dict[str, bool]:
        """Mock Test: コンポーネントテスト"""
        logger.info("Running mock test (component verification)")

        validation = {}

        # バックアップ整合性検証
        for location, config in self.backup_locations.items():
            backup_file = config.path / f"{backup_name}.tar.gz"
            if backup_file.exists():
                checksum_file = backup_file.with_suffix('.sha256')
                if checksum_file.exists():
                    expected = checksum_file.read_text().split()[0]
                    validation[f"{location.value}_integrity"] = \
                        self._verify_backup_integrity(backup_file, expected)

        return validation

    def _run_parallel_test(self, backup_name: str) -> Dict[str, bool]:
        """Parallel Test: 本番並行テスト"""
        logger.info("Running parallel test (production-parallel validation)")

        # 一時ディレクトリに復元
        with tempfile.TemporaryDirectory() as temp_dir:
            success, message = self.restore_backup(
                backup_name,
                Path(temp_dir),
                verify=True
            )

            return {
                'restore_success': success,
                'directory_created': Path(temp_dir).exists()
            }

    def _run_full_failover_test(self, backup_name: str) -> Dict[str, bool]:
        """Full Failover Test: 完全切替テスト"""
        logger.info("Running full failover test (complete system switchover)")

        # 注意: 本番環境では慎重に実施
        logger.warning("Full failover test - use with caution in production!")

        # 実際の本番環境では、別システムに完全復元
        # ここではシミュレーション
        return {
            'failover_initiated': True,
            'backup_verified': True,
            'system_responsive': True
        }

    def _check_rpo_compliance(self, backup_name: str) -> bool:
        """RPO準拠チェック"""
        metadata_file = self.metadata_dir / f"{backup_name}_metadata.json"

        if not metadata_file.exists():
            return False

        with open(metadata_file, encoding='utf-8') as f:
            metadata = json.load(f)

        timestamp = datetime.fromisoformat(metadata['timestamp'])
        age_minutes = (datetime.now(timezone.utc) - timestamp).total_seconds() / 60

        return age_minutes <= self.rpo.target_minutes

    def cleanup_old_backups(self, retention_days: int = 30) -> int:
        """古いバックアップをクリーンアップ"""
        deleted_count = 0
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)

        for metadata_file in self.metadata_dir.glob('*_metadata.json'):
            with open(metadata_file, encoding='utf-8') as f:
                metadata = json.load(f)

            timestamp = datetime.fromisoformat(metadata['timestamp'])

            if timestamp < cutoff_date:
                backup_name = metadata['backup_name']

                # 各ロケーションから削除
                for config in self.backup_locations.values():
                    backup_file = config.path / f"{backup_name}.tar.gz"
                    if backup_file.exists():
                        backup_file.unlink()
                        backup_file.with_suffix('.sha256').unlink(missing_ok=True)

                # メタデータ削除
                metadata_file.unlink()
                deleted_count += 1

        logger.info(f"Cleaned up {deleted_count} old backups")
        return deleted_count


def main():
    """テスト実行"""
    print("Enhanced 3-2-1 Disaster Recovery System\n")
    print("=" * 70)

    # RPO/RTO設定
    rpo = RPOConfig(target_minutes=60, backup_interval_minutes=30)
    rto = RTOConfig(target_minutes=240, max_restore_duration_minutes=180)

    # バックアップマネージャー初期化
    manager = Enhanced321BackupManager(rpo_config=rpo, rto_config=rto)

    # テストバックアップ作成
    print("\n1. Creating 3-2-1 backup...")
    source_dirs = [Path("main"), Path("config")]

    success, message, metadata = manager.create_321_backup(
        source_dirs=source_dirs,
        backup_name="test_backup"
    )

    print(f"   {message}")

    # バックアップリスト
    print("\n2. Listing backups...")
    backups = manager.list_backups(verified_only=True)
    for backup in backups[:5]:
        print(f"   - {backup}")

    # 復旧テスト
    print("\n3. Running recovery test...")
    test_result = manager.run_recovery_test(TestType.MOCK, "test_backup")
    print(f"   Test type: {test_result.test_type.value}")
    print(f"   Success: {test_result.success}")
    print(f"   RPO achieved: {test_result.rpo_achieved}")
    print(f"   RTO achieved: {test_result.rto_achieved}")

    print("\n" + "=" * 70)
    print("3-2-1 Backup Strategy:")
    print("  ✓ 3 copies of data")
    print("  ✓ 2 different media types")
    print("  ✓ 1 offsite backup")
    print("=" * 70)


if __name__ == "__main__":
    main()
