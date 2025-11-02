# Cocoa Data Security Guide / Cocoaデータセキュリティガイド

## Table of Contents / 目次
- [日本語セクション](#日本語セクション)
- [English Section](#english-section)

---

## 日本語セクション

### 概要
`main/integrated_security.py` は AES-256-GCM 暗号化、入力検証、監査ログ、アクセス制御を統合し、Otedama のデータ保護レイヤーを形成します。本ドキュメントでは、コンポーネント構造、設定手順、運用フロー、インシデント対応のベストプラクティスを整理します。

### コンポーネント概要
- **`DataEncryptor`**: `OTEDAMA_ENCRYPTION_KEY` を PBKDF2 (100,000 回) で派生し、`encrypt_data()` と `decrypt_data()` を提供します。
- **`SecurityValidator`**: 17 種類の危険パターンとサイズ上限で `validate_input_data()`、`sanitize_input()`、`validate_password()` を実行します。
- **`SecurityPolicy`**: セッションタイムアウト、ロックアウト回数、2FA 要件、IP 制御範囲などを宣言的に設定します。
- **`SecurityAuditor`**: SQLite ベースの監査台帳を管理し、`log_event()` と `get_events()` で完全な証跡を維持します。
- **`IntegratedSecurityManager`**: 検証・暗号化・監査を統合し、`secure_operation()` と `get_security_report()` を通じて日々の統制を簡素化します。

### 初期化手順
```python
from main.integrated_security import get_security_manager, SecurityPolicy, SecurityLevel

policy = SecurityPolicy(
    level=SecurityLevel.STRICT,
    allowed_ips=["192.168.0.0/24"],
    max_login_attempts=5,
    lockout_duration=900,
    require_2fa=True,
)

manager = get_security_manager()
manager.policy = policy
manager.initialize()

payload = {"username": "admin", "operation": "preset_update"}
encrypted = manager.encryptor.encrypt_data(payload)
restored = manager.encryptor.decrypt_data(encrypted)
```

### 設定チェックリスト
- **環境変数**: `.env` の `OTEDAMA_SECRET_KEY` と `OTEDAMA_ENCRYPTION_KEY` は 32 文字以上のランダム値に更新し、アクセス制御リストで保護します。
- **ポリシー**: `SecurityPolicy.allowed_ips`／`blocked_ips` を CIDR で指定し、承認済みの変更リストを保持します。
- **ログディレクトリ**: `logs/security.log` と `security.db` の OS 権限を `600` 相当に制限します。
- **監査 DB バックアップ**: `backups/` 配下に日次バックアップを作成し、`DisasterRecoveryManager` の `verify_backup()` で整合性を確認します。

### 運用ベストプラクティス
- **鍵ローテーション**: 半期ごと、またはインシデント発生時に以下の手順を実施します。
  1. 新しい鍵を安全な端末で生成 (`secrets.token_urlsafe(48)`)。
  2. `.env` を更新し、アプリケーションを段階的に再起動。
  3. 旧鍵を破棄し、監査ログにローテーション完了を記録。
  4. 監査 DB のバックアップを取得し、復号テストを実施。
- **入力検証の前段適用**: API や GUI からの入力を受け取る場所で `SecurityValidator.validate_input_data()` を呼び出し、異常値を即座に拒否します。
- **脅威監視**: `manager.get_security_report()` を日次で取得し、`statistics` セクションのイベント増加を確認します。
- **監査ログ保全**: `security.db` を週次でアーカイブし、長期保管用に暗号化したストレージへ転送します。

### インシデント対応手順
1. **検知**: アラートメールまたはレポートで異常を確認。
2. **封じ込め**: `SecurityPolicy.allowed_ips` を一時的に限定、影響セッションを `manager.validator.lockouts.clear()` で無効化。
3. **調査**: `SecurityAuditor.get_events(hours_back=72)` でイベント履歴を抽出し、タイムスタンプとユーザー ID を整理。
4. **復旧**: 必要に応じて `DisasterRecoveryManager.restore_backup()` で直近のクリーンデータを復元。
5. **再発防止**: ポリシー閾値の調整、脆弱性修正、レポート送付を完了させてから運用再開。

### 定常タスク
- **日次**: `manager.get_security_report()` と `SecurityAuditor.get_events(hours_back=24)` をレビュー。
- **週次**: 失敗試行数が閾値を超えたユーザーを棚卸し、フォレンジックレポートに追記。
- **月次**: `SecurityPolicy` 設定をレビューし、ライフサイクル管理表に更新日を記録。

### トラブルシューティング
- **暗号化失敗**: `len(os.environ.get("OTEDAMA_ENCRYPTION_KEY", ""))` が 32 以上か確認し、`cryptography` を再インストール。
- **ロックアウト多発**: `SecurityPolicy.max_login_attempts` を調整し、ブルートフォースの兆候がないか監査ログで確認。
- **IP ブロック誤判定**: 設定ファイルの CIDR 指定ミスがないか検証し、`ipaddress` モジュールで範囲テストを実施。
- **監査 DB 増大**: `VACUUM` を適用し、不要イベントをアーカイブ後に削除。

---

## English Section

### Overview
`main/integrated_security.py` bundles AES-256-GCM encryption, policy-driven validation, and durable audit logging. This section details component behaviour, configuration checkpoints, operational cadence, and incident response guidelines for Otedama.

### Component Summary
- **`DataEncryptor`** uses PBKDF2-derived keys from `OTEDAMA_ENCRYPTION_KEY` and enforces authenticated encryption.
- **`SecurityValidator`** implements strict pattern detection, payload size limits, and password strength enforcement.
- **`SecurityPolicy`** centralises lockout thresholds, session lifetimes, and network restrictions.
- **`SecurityAuditor`** persists tamper-evident event records inside `security.db`.
- **`IntegratedSecurityManager`** coordinates validation, encryption, auditing, and exposes `secure_operation()` / `get_security_report()`.

### Initialization Workflow
```python
from main.integrated_security import get_security_manager, SecurityPolicy, SecurityLevel

policy = SecurityPolicy(
    level=SecurityLevel.ENHANCED,
    allowed_ips=["10.10.0.0/24"],
    blocked_ips=["198.51.100.0/24"],
    max_login_attempts=5,
    lockout_duration=900,
)

manager = get_security_manager()
manager.policy = policy
manager.initialize()

payload = {"action": "config_change", "resource": "preset"}
encrypted = manager.encryptor.encrypt_data(payload)
assert manager.encryptor.decrypt_data(encrypted) == payload
```

### Configuration Checklist
- Replace `OTEDAMA_SECRET_KEY` and `OTEDAMA_ENCRYPTION_KEY` with freshly generated 32+ character secrets stored outside version control.
- Lock down `logs/security.log` and `security.db` with least-privilege filesystem ACLs.
- Document and approve updates to `SecurityPolicy.allowed_ips`/`blocked_ips` before deployment.
- Schedule nightly archives of the audit database and confirm integrity via `verify_backup()`.

### Operational Best Practices
- **Key Rotation**: Perform at least semi-annually or after any compromise.
  1. Generate new secrets using `secrets.token_urlsafe(48)`.
  2. Update `.env`, restart services gracefully, and verify encryption/decryption.
  3. Invalidate historical credentials and record the rotation in the change log.
  4. Export audit data for retention.
- **Input Safeguards**: Invoke `validate_input_data()` on all untrusted payloads and reject failures before persistence.
- **Threat Monitoring**: Capture `get_security_report()` daily and track `statistics.incidents` for trend analysis.
- **Audit Preservation**: Export `security.db` weekly and ship copies to long-term storage with encryption-at-rest guarantees.

### Incident Response Flow
1. **Detect** anomalies via alerting or elevated incident counts.
2. **Contain** by tightening `allowed_ips` and clearing active sessions or lockouts where appropriate.
3. **Investigate** using `SecurityAuditor.get_events(hours_back=72)` and correlating timestamps.
4. **Recover** with `DisasterRecoveryManager.restore_backup()` if data tampering is confirmed.
5. **Improve** by updating policies, documenting lessons learned, and validating mitigations.

### Recurring Tasks
- **Daily**: Review `get_security_report()` output and cross-check recent audit entries.
- **Weekly**: Reconcile failed login attempts with IAM records and adjust policies if abuse is detected.
- **Monthly**: Review policy settings, verify backup restorability, and run targeted penetration tests if available.

### Troubleshooting
- **Encryption failures**: Validate `OTEDAMA_ENCRYPTION_KEY` length and reinstall `cryptography` if binaries are corrupted.
- **Excessive lockouts**: Adjust `max_login_attempts` and inspect event histories for attack signatures.
- **False positive IP blocks**: Confirm CIDR accuracy and test with Python's `ipaddress` module.
- **Audit database growth**: Archive or prune aged events; execute `VACUUM` to reclaim space.

---

---
