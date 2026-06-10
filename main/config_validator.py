"""
設定ファイルバリデーションシステム
軽量で実用的なJSON設定ファイルの検証機能を提供
"""
import copy
import ipaddress
import json
import logging
import os
import re
from email.utils import parseaddr
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def _is_within_directory(base: Path, target: Path) -> bool:
    try:
        base_resolved = base.resolve()
        target_resolved = target.resolve()
    except OSError:
        return False
    try:
        target_resolved.relative_to(base_resolved)
        return True
    except ValueError:
        return False


class ConfigValidator:
    """軽量で実用的な設定ファイル検証システム"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初期化"""
        self.config = config or {}
        self.validation_rules = self._get_default_validation_rules()
        self.streaming_rules = self._get_streaming_validation_rules()

    def _get_default_validation_rules(self) -> Dict[str, Any]:
        """デフォルトの検証ルールを定義"""
        return {
            "app_name": {
                "type": "string",
                "required": True,
                "min_length": 1,
                "max_length": 100,
                "description": "アプリケーション名"
            },
            "version": {
                "type": "string",
                "required": True,
                "pattern": r"^\d+\.\d+\.\d+$",
                "description": "バージョン番号 (例: 1.0.0)"
            },
            "language": {
                "type": "string",
                "required": True,
                "allowed_values": ["ja", "en"],
                "description": "言語設定"
            },
            "debug": {
                "type": "boolean",
                "required": True,
                "description": "デバッグモード"
            },
            "log_level": {
                "type": "string",
                "required": True,
                "allowed_values": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                "description": "ログレベル"
            },
            "backup": {
                "type": "object",
                "required": False,
                "schema": {
                    "enabled": {"type": "boolean", "required": True},
                    "interval_minutes": {"type": "integer", "required": True, "min": 1, "max": 1440},
                    "max_backups": {"type": "integer", "required": True, "min": 1, "max": 100},
                    "backup_path": {"type": "string", "required": True}
                },
                "description": "バックアップ設定"
            },
            "performance_monitoring": {
                "type": "object",
                "required": False,
                "schema": {
                    "enabled": {"type": "boolean", "required": True},
                    "interval_seconds": {"type": "integer", "required": True, "min": 1, "max": 3600},
                    "alert_thresholds": {
                        "type": "object",
                        "required": True,
                        "schema": {
                            "cpu_percent": {"type": "integer", "required": True, "min": 1, "max": 100},
                            "memory_percent": {"type": "integer", "required": True, "min": 1, "max": 100},
                            "disk_usage_percent": {"type": "integer", "required": True, "min": 1, "max": 100},
                            "response_time_ms": {"type": "integer", "required": False, "min": 1}
                        }
                    }
                },
                "description": "パフォーマンス監視設定"
            },
            "plugins": {
                "type": "object",
                "required": False,
                "schema": {
                    "enabled": {"type": "array", "required": True, "item_type": "string"},
                    "config_path": {"type": "string", "required": True}
                },
                "description": "プラグイン設定"
            },
            "avatar": {
                "type": "object",
                "required": False,
                "schema": {
                    "default_path": {"type": "string", "required": True},
                    "max_parameters": {"type": "integer", "required": True, "min": 1, "max": 100000},
                    "auto_save": {"type": "boolean", "required": True}
                },
                "description": "アバター設定"
            },
            "web_admin": {
                "type": "object",
                "required": False,
                "schema": {
                    "enabled": {"type": "boolean", "required": True},
                    "host": {"type": "string", "required": True},
                    "port": {"type": "integer", "required": True, "min": 1024, "max": 65535},
                    "debug": {"type": "boolean", "required": True},
                    "ssl": {
                        "type": "object",
                        "required": False,
                        "schema": {
                            "enabled": {"type": "boolean", "required": True},
                            "cert_path": {"type": "string", "required": False, "nullable": True},
                            "key_path": {"type": "string", "required": False, "nullable": True}
                        }
                    },
                    "session": {
                        "type": "object",
                        "required": False,
                        "schema": {
                            "timeout_minutes": {"type": "integer", "required": True, "min": 1},
                            "max_sessions": {"type": "integer", "required": True, "min": 1}
                        }
                    }
                },
                "description": "Web管理システム設定"
            },
            "database": {
                "type": "object",
                "required": False,
                "schema": {
                    "enabled": {"type": "boolean", "required": True},
                    "type": {"type": "string", "required": True, "allowed_values": ["sqlite", "postgresql", "mysql", "mariadb", "sqlserver"]},
                    "connection_string": {"type": "string", "required": True},
                    "pool_size": {"type": "integer", "required": False, "min": 1},
                    "backup_enabled": {"type": "boolean", "required": False}
                },
                "description": "データベース設定"
            },
            "security": {
                "type": "object",
                "required": False,
                "schema": {
                    "password_min_length": {"type": "integer", "required": True, "min": 8, "max": 128},
                    "password_require_special": {"type": "boolean", "required": True},
                    "password_require_numbers": {"type": "boolean", "required": True},
                    "password_require_lowercase": {"type": "boolean", "required": True},
                    "password_require_uppercase": {"type": "boolean", "required": True},
                    "max_login_attempts": {"type": "integer", "required": True, "min": 1, "max": 20},
                    "lockout_duration_minutes": {"type": "integer", "required": True, "min": 1, "max": 1440},
                    "enable_2fa": {"type": "boolean", "required": True},
                    "enable_audit_log": {"type": "boolean", "required": True},
                    "allowed_ips": {"type": "array", "required": False, "item_type": "string", "max_items": 100},
                    "blocked_ips": {"type": "array", "required": False, "item_type": "string", "max_items": 100}
                },
                "description": "セキュリティ設定"
            },
            "notification": {
                "type": "object",
                "required": False,
                "schema": {
                    "enabled": {"type": "boolean", "required": True},
                    "email": {
                        "type": "object",
                        "required": False,
                        "schema": {
                            "smtp_server": {"type": "string", "required": False, "nullable": True},
                            "smtp_port": {"type": "integer", "required": False, "min": 1, "max": 65535, "nullable": True},
                            "from_address": {"type": "string", "required": False, "nullable": True},
                            "to_addresses": {"type": "array", "required": False, "item_type": "string", "nullable": True}
                        }
                    },
                    "webhook": {
                        "type": "object",
                        "required": False,
                        "schema": {
                            "url": {"type": "string", "required": False, "nullable": True},
                            "method": {"type": "string", "required": False, "allowed_values": ["GET", "POST", "PUT", "PATCH", "DELETE"], "nullable": True}
                        }
                    }
                },
                "description": "通知設定"
            },
            "rate_limiting": {
                "type": "object",
                "required": False,
                "schema": {
                    "enabled": {"type": "boolean", "required": True},
                    "requests_per_minute": {"type": "integer", "required": True, "min": 1},
                    "requests_per_hour": {"type": "integer", "required": True, "min": 1},
                    "requests_per_day": {"type": "integer", "required": True, "min": 1}
                },
                "description": "レート制限設定"
            },
            "billing": {
                "type": "object",
                "required": False,
                "schema": {
                    "enabled": {"type": "boolean", "required": True},
                    "mode": {"type": "string", "required": False, "allowed_values": ["buy_once", "subscription"]},
                    "currency": {"type": "string", "required": False, "pattern": r"^[A-Za-z]{3}$"},
                    "default_price_tier": {"type": "string", "required": False},
                    "trial_period_days": {"type": "integer", "required": False, "min": 0, "max": 365},
                    "tiers": {"type": "object", "required": True},
                    "webhook": {
                        "type": "object",
                        "required": False,
                        "schema": {
                            "enabled": {"type": "boolean", "required": True},
                            "endpoint_secret_env": {"type": "string", "required": False}
                        }
                    },
                    "checkout": {
                        "type": "object",
                        "required": False,
                        "schema": {
                            "success_url": {"type": "string", "required": True},
                            "cancel_url": {"type": "string", "required": True}
                        }
                    }
                },
                "description": "課金設定"
            }
        }

    def _get_streaming_validation_rules(self) -> Dict[str, Any]:
        return {
            "enabled": {"type": "boolean", "required": True},
            "target": {
                "type": "string",
                "required": True,
                "allowed_values": ["obs", "obc"],
            },
            "connection": {
                "type": "object",
                "required": True,
                "schema": {
                    "host": {"type": "string", "required": True, "min_length": 1},
                    "port": {"type": "integer", "required": True, "min": 1, "max": 65535},
                    "password": {"type": "string", "required": False, "nullable": True},
                    "use_ssl": {"type": "boolean", "required": False},
                    "reconnect_attempts": {"type": "integer", "required": False, "min": 0, "max": 50},
                    "reconnect_interval": {"type": "number", "required": False, "min": 0.1, "max": 60.0},
                },
            },
            "options": {
                "type": "object",
                "required": False,
                "schema": {
                    "auto_reconnect": {"type": "boolean", "required": False},
                    "heartbeat_interval": {"type": "integer", "required": False, "min": 1, "max": 60},
                    "request_timeout": {"type": "number", "required": False, "min": 1.0, "max": 120.0},
                },
            },
        }

    def validate(self, config_path: str) -> Dict[str, Any]:
        """設定ファイルを検証"""
        try:
            # 設定ファイルの読み込み
            if not os.path.exists(config_path):
                return {
                    "valid": False,
                    "errors": [f"設定ファイルが存在しません: {config_path}"],
                    "warnings": [],
                    "config": None
                }

            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            # JSONパースエラーのチェック
            if not isinstance(config, dict):
                return {
                    "valid": False,
                    "errors": ["設定ファイルがJSONオブジェクトではありません"],
                    "warnings": [],
                    "config": None
                }

            # 検証実行
            errors = []
            warnings = []
            validated_config = copy.deepcopy(config)

            # 各フィールドの検証
            for field_name, rules in self.validation_rules.items():
                field_value = config.get(field_name)

                # 必須フィールドのチェック
                if rules.get("required", False) and field_name not in config:
                    errors.append(f"必須フィールド '{field_name}' が存在しません")
                    continue

                # フィールドが存在する場合の検証
                if field_name in config:
                    field_errors, field_warnings, validated_value = self._validate_field(
                        field_name, field_value, rules
                    )
                    errors.extend(field_errors)
                    warnings.extend(field_warnings)

                    if validated_value is not None:
                        validated_config[field_name] = validated_value

            streaming_config_path = Path(config_path).with_name("streaming.json")
            if streaming_config_path.exists():
                try:
                    with streaming_config_path.open(encoding="utf-8") as s_handle:
                        streaming_config = json.load(s_handle)
                    self._validate_streaming(streaming_config, errors, warnings)
                except json.JSONDecodeError as s_exc:
                    errors.append(f"streaming.json のJSON解析に失敗しました: {s_exc}")
                except Exception as s_exc:  # noqa: BLE001
                    warnings.append(f"streaming.json の読み込みで問題が発生しました: {s_exc}")

            self._apply_post_validation(config, validated_config, errors, warnings)

            # 検証結果の返却
            is_valid = len(errors) == 0

            result = {
                "valid": is_valid,
                "errors": errors,
                "warnings": warnings,
                "config": validated_config if is_valid else None
            }

            if is_valid:
                logger.info(f"設定ファイルの検証が成功しました: {config_path}")
            else:
                logger.error(f"設定ファイルの検証でエラーが発生しました: {config_path}")

            return result

        except json.JSONDecodeError as e:
            return {
                "valid": False,
                "errors": [f"JSONパースエラー: {str(e)}"],
                "warnings": [],
                "config": None
            }
        except Exception as e:
            logger.error(f"設定ファイル検証中にエラーが発生しました: {e}")
            return {
                "valid": False,
                "errors": [f"検証処理エラー: {str(e)}"],
                "warnings": [],
                "config": None
            }

    def _validate_streaming(self, streaming_config: Any, errors: List[str], warnings: List[str]) -> None:
        if not isinstance(streaming_config, dict):
            errors.append("streaming.json はオブジェクト形式である必要があります")
            return

        for field_name, rules in self.streaming_rules.items():
            if rules.get("required") and field_name not in streaming_config:
                errors.append(f"streaming.json: 必須フィールド '{field_name}' が存在しません")
                continue

            if field_name in streaming_config:
                field_value = streaming_config[field_name]
                field_errors, field_warnings, _ = self._validate_field(f"streaming.{field_name}", field_value, rules)
                errors.extend(field_errors)
                warnings.extend(field_warnings)

        target = streaming_config.get("target")
        if target == "obs":
            connection = streaming_config.get("connection", {})
            if isinstance(connection, dict) and not connection.get("password"):
                warnings.append("OBS接続でパスワードが未設定です。OBS側で認証が必要な場合は設定してください。")
        elif target == "obc":
            warnings.append("OBC連携は実装準備中です。設定を反映するには追加実装が必要です。")

    def _validate_field(self, field_name: str, value: Any, rules: Dict[str, Any]) -> Tuple[List[str], List[str], Any]:
        """フィールドの検証"""
        errors = []
        warnings = []
        validated_value = value

        try:
            field_type = rules.get("type")
            nullable = rules.get("nullable", False)

            if value is None:
                if nullable:
                    return errors, warnings, None
                errors.append(f"フィールド '{field_name}' はnullを許容していません")
                return errors, warnings, None

            # 型チェック
            if field_type == "string":
                if not isinstance(value, str):
                    errors.append(f"フィールド '{field_name}' は文字列である必要があります")
                    return errors, warnings, None

                # 文字列の長さチェック
                min_length = rules.get("min_length")
                if min_length is not None and len(value) < min_length:
                    errors.append(f"フィールド '{field_name}' は{min_length}文字以上である必要があります")

                max_length = rules.get("max_length")
                if max_length is not None and len(value) > max_length:
                    errors.append(f"フィールド '{field_name}' は{max_length}文字以下である必要があります")

                # パターンチェック
                pattern = rules.get("pattern")
                if pattern and not self._match_pattern(value, pattern):
                    errors.append(f"フィールド '{field_name}' の形式が正しくありません")

                # 許可値チェック
                allowed_values = rules.get("allowed_values")
                if allowed_values and value not in allowed_values:
                    errors.append(f"フィールド '{field_name}' の値が許可されていません: {allowed_values}")

            elif field_type == "integer":
                if not isinstance(value, int) or isinstance(value, bool):
                    errors.append(f"フィールド '{field_name}' は整数である必要があります")
                    return errors, warnings, None

                # 範囲チェック
                min_val = rules.get("min")
                if min_val is not None and value < min_val:
                    errors.append(f"フィールド '{field_name}' は{min_val}以上である必要があります")

                max_val = rules.get("max")
                if max_val is not None and value > max_val:
                    errors.append(f"フィールド '{field_name}' は{max_val}以下である必要があります")

                allowed_values = rules.get("allowed_values")
                if allowed_values and value not in allowed_values:
                    errors.append(f"フィールド '{field_name}' の値が許可されていません: {allowed_values}")

            elif field_type == "number":
                if not isinstance(value, (int, float)):
                    errors.append(f"フィールド '{field_name}' は数値である必要があります")
                    return errors, warnings, None

                min_val = rules.get("min")
                if min_val is not None and value < min_val:
                    errors.append(f"フィールド '{field_name}' は{min_val}以上である必要があります")

                max_val = rules.get("max")
                if max_val is not None and value > max_val:
                    errors.append(f"フィールド '{field_name}' は{max_val}以下である必要があります")

            elif field_type == "boolean":
                if not isinstance(value, bool):
                    errors.append(f"フィールド '{field_name}' は真偽値である必要があります")
                    return errors, warnings, None

            elif field_type == "array":
                if not isinstance(value, list):
                    errors.append(f"フィールド '{field_name}' は配列である必要があります")
                    return errors, warnings, None

                # 配列要素の型チェック
                item_type = rules.get("item_type")
                if item_type:
                    for i, item in enumerate(value):
                        expected_type = str if item_type == "string" else int if item_type == "integer" else type(None)
                        if not isinstance(item, expected_type):
                            errors.append(f"フィールド '{field_name}[{i}]' の型が正しくありません")

                min_items = rules.get("min_items")
                if min_items is not None and len(value) < min_items:
                    errors.append(f"フィールド '{field_name}' の要素数は{min_items}以上である必要があります")

                max_items = rules.get("max_items")
                if max_items is not None and len(value) > max_items:
                    errors.append(f"フィールド '{field_name}' の要素数は{max_items}以下である必要があります")

            elif field_type == "object":
                if not isinstance(value, dict):
                    errors.append(f"フィールド '{field_name}' はオブジェクトである必要があります")
                    return errors, warnings, None

                # ネストされたスキーマの検証
                schema = rules.get("schema", {})
                for sub_field, sub_rules in schema.items():
                    if sub_rules.get("required") and sub_field not in value:
                        errors.append(f"必須フィールド '{field_name}.{sub_field}' が存在しません")
                        continue

                    if sub_field in value:
                        sub_errors, sub_warnings, sub_validated = self._validate_field(
                            f"{field_name}.{sub_field}", value[sub_field], sub_rules
                        )
                        errors.extend(sub_errors)
                        warnings.extend(sub_warnings)

                        if sub_validated is not None:
                            validated_value[sub_field] = sub_validated

            return errors, warnings, validated_value

        except Exception as e:
            errors.append(f"フィールド '{field_name}' の検証中にエラーが発生しました: {str(e)}")
            return errors, warnings, None

    def _match_pattern(self, value: str, pattern: str) -> bool:
        """パターンマッチング"""
        try:
            return bool(re.match(pattern, value))
        except re.error:
            return False

    def fix_config(self, config_path: str) -> bool:
        """設定ファイルを修正"""
        try:
            validation_result = self.validate(config_path)

            if validation_result["valid"]:
                logger.info("設定ファイルは既に有効です")
                return True

            if validation_result["config"] is None:
                logger.error("設定ファイルの修正ができません")
                return False

            # 修正された設定を保存
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(validation_result["config"], f, indent=2, ensure_ascii=False)

            logger.info(f"設定ファイルを修正しました: {config_path}")
            return True

        except Exception as e:
            logger.error(f"設定ファイル修正中にエラーが発生しました: {e}")
            return False

    def validate_from_dict(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """辞書から設定を検証"""
        errors = []
        warnings = []
        validated_config = copy.deepcopy(config)

        # 各フィールドの検証
        for field_name, rules in self.validation_rules.items():
            field_value = config.get(field_name)

            # 必須フィールドのチェック
            if rules.get("required", False) and field_name not in config:
                errors.append(f"必須フィールド '{field_name}' が存在しません")
                continue

            # フィールドが存在する場合の検証
            if field_name in config:
                field_errors, field_warnings, validated_value = self._validate_field(
                    field_name, field_value, rules
                )
                errors.extend(field_errors)
                warnings.extend(field_warnings)

                if validated_value is not None:
                    validated_config[field_name] = validated_value

        self._apply_post_validation(config, validated_config, errors, warnings)

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "config": validated_config if len(errors) == 0 else None
        }

    def _apply_post_validation(
        self,
        original_config: Dict[str, Any],
        validated_config: Dict[str, Any],
        errors: List[str],
        warnings: List[str],
    ) -> None:
        """構造間の整合性検証やパス検証などの後処理を行う"""
        self._validate_web_admin_section(original_config, validated_config, errors, warnings)

        language = original_config.get("language")
        if isinstance(language, str) and language.lower() not in {"ja", "en"}:
            warnings.append(
                f"language '{language}' は未対応です。デフォルトにフォールバックされる可能性があります。"
            )

        self._validate_backup_section(original_config, warnings, errors)
        self._validate_plugins_section(original_config, warnings)
        self._validate_security_section(original_config, validated_config, errors, warnings)

        # billing / notification / rate_limiting のクロスフィールド検証
        security_cfg = original_config.get("security")
        if not isinstance(security_cfg, dict):
            security_cfg = {}
        self._validate_password_policy(security_cfg, errors, warnings, original_config, validated_config)

    def _validate_web_admin_section(
        self,
        original_config: Dict[str, Any],
        validated_config: Dict[str, Any],
        errors: List[str],
        warnings: List[str],
    ) -> None:
        """web_admin セクション（host / debug / ssl）の検証"""
        web_admin_config = original_config.get("web_admin")
        web_admin_validated = validated_config.get("web_admin") if isinstance(validated_config.get("web_admin"), dict) else None
        if isinstance(web_admin_config, dict):
            host = web_admin_config.get("host", "")
            if host in {"0.0.0.0", ""}:
                warnings.append(
                    "web_admin.host が '0.0.0.0' もしくは空です。公開環境では安全なアドレスを指定してください。"
                )
            if isinstance(host, str) and (host.startswith("http://") or host.startswith("https://")):
                errors.append("web_admin.host にはURLではなくホスト名のみを指定してください。")

            if web_admin_config.get("enabled") and not isinstance(host, str):
                errors.append("web_admin.host は文字列である必要があります。")

            debug_flag = web_admin_config.get("debug")
            if web_admin_config.get("enabled") and debug_flag:
                warnings.append("web_admin.debug が有効です。公開環境では無効化を検討してください。")

            ssl_config = web_admin_config.get("ssl")
            if isinstance(ssl_config, dict) and isinstance(web_admin_validated, dict):
                ssl_validated = web_admin_validated.get("ssl")
                if not isinstance(ssl_validated, dict):
                    ssl_validated = {}
                    web_admin_validated["ssl"] = ssl_validated

                ssl_enabled = ssl_config.get("enabled")
                if ssl_enabled:
                    cert_path = ssl_config.get("cert_path")
                    key_path = ssl_config.get("key_path")

                    if not cert_path:
                        errors.append("web_admin.ssl.enabled が true の場合は cert_path を設定してください。")
                    else:
                        normalized_cert = self._validate_secure_file_path(
                            "web_admin.ssl.cert_path", cert_path, errors, warnings
                        )
                        if normalized_cert:
                            ssl_validated["cert_path"] = normalized_cert

                    if not key_path:
                        errors.append("web_admin.ssl.enabled が true の場合は key_path を設定してください。")
                    else:
                        normalized_key = self._validate_secure_file_path(
                            "web_admin.ssl.key_path", key_path, errors, warnings
                        )
                        if normalized_key:
                            ssl_validated["key_path"] = normalized_key

                elif not ssl_enabled:
                    if ssl_config.get("cert_path") or ssl_config.get("key_path"):
                        warnings.append(
                            "web_admin.ssl.enabled が false の状態で cert_path または key_path が設定されています。不要な機密情報を削除してください。"
                        )

    def _validate_backup_section(
        self,
        original_config: Dict[str, Any],
        warnings: List[str],
        errors: List[str],
    ) -> None:
        """backup セクション（保存先パス）の検証"""
        backup_config = original_config.get("backup")
        if isinstance(backup_config, dict) and backup_config.get("enabled"):
            backup_path = backup_config.get("backup_path")
            if isinstance(backup_path, str):
                candidate = Path(backup_path).expanduser()
                if not candidate.is_absolute():
                    warnings.append("backup.backup_path には絶対パスを指定してください。")
                else:
                    try:
                        resolved = candidate.resolve()
                    except OSError:
                        resolved = candidate
                    if not resolved.exists():
                        warnings.append(
                            f"backup.backup_path '{resolved}' が存在しません。バックアップ保存先を確認してください。"
                        )
                    elif not resolved.is_dir():
                        errors.append("backup.backup_path にはディレクトリを指定してください。")

    def _validate_plugins_section(
        self,
        original_config: Dict[str, Any],
        warnings: List[str],
    ) -> None:
        """plugins セクション（重複・設定パス）の検証"""
        plugins_config = original_config.get("plugins")
        if isinstance(plugins_config, dict):
            enabled_plugins = plugins_config.get("enabled")
            if isinstance(enabled_plugins, list):
                duplicates = {name for name in enabled_plugins if enabled_plugins.count(name) > 1}
                if duplicates:
                    warnings.append(
                        f"plugins.enabled に重複があります: {', '.join(sorted(duplicates))}"
                    )

            config_path = plugins_config.get("config_path")
            if isinstance(config_path, str) and isinstance(enabled_plugins, list) and enabled_plugins:
                config_candidate = Path(config_path).expanduser()
                if not config_candidate.is_absolute():
                    warnings.append("plugins.config_path には絶対パスを指定してください。")
                elif not config_candidate.exists():
                    warnings.append(
                        f"plugins.config_path '{config_candidate}' が存在しません。プラグイン設定を確認してください。"
                    )

    def _validate_security_section(
        self,
        original_config: Dict[str, Any],
        validated_config: Dict[str, Any],
        errors: List[str],
        warnings: List[str],
    ) -> None:
        """security セクション（IPリスト・監査ログ・2FA）の検証"""
        security_config = original_config.get("security")
        security_validated = validated_config.get("security")
        if isinstance(security_config, dict) and isinstance(security_validated, dict):
            allowed = security_config.get("allowed_ips", [])
            blocked = security_config.get("blocked_ips", [])
            normalized_allowed = self._normalize_ip_entries(
                "security.allowed_ips", allowed, errors, warnings
            )
            normalized_blocked = self._normalize_ip_entries(
                "security.blocked_ips", blocked, errors, warnings
            )
            if normalized_allowed is not None:
                security_validated["allowed_ips"] = normalized_allowed
            if normalized_blocked is not None:
                security_validated["blocked_ips"] = normalized_blocked
            if isinstance(allowed, list) and isinstance(blocked, list):
                overlaps = set(allowed).intersection(blocked)
                if overlaps:
                    errors.append(
                        "allowed_ips と blocked_ips に重複があります: " + ", ".join(sorted(overlaps))
                    )
            if not security_config.get("enable_audit_log"):
                errors.append("security.enable_audit_log は true に設定してください。国家レベル運用では監査ログが必須です。")
            if not security_config.get("enable_2fa"):
                errors.append("security.enable_2fa は true に設定してください。多要素認証を無効化することは許可されていません。")
            if normalized_allowed is not None:
                if not normalized_allowed:
                    warnings.append("security.allowed_ips が空です。許可リストを設定してアクセス境界を明確にしてください。")
                overly_broad = [entry for entry in normalized_allowed if entry in {"0.0.0.0/0", "::/0"}]
                if overly_broad:
                    errors.append(
                        "security.allowed_ips に全許可ネットワークが含まれています: " + ", ".join(overly_broad)
                    )
            if security_config.get("max_login_attempts", 5) > 10:
                warnings.append("security.max_login_attempts が高すぎます。10以下に調整してください。")

    def _validate_password_policy(
        self,
        security_config: Dict[str, Any],
        errors: List[str],
        warnings: List[str],
        original_config: Optional[Dict[str, Any]] = None,
        validated_config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """パスワードポリシーおよび billing/notification/rate_limiting セクションの詳細な検証"""
        original_config = original_config or {}
        validated_config = validated_config or {}
        self._validate_password_section(security_config, errors, warnings)
        self._validate_billing_section(original_config, validated_config, errors, warnings)
        self._validate_notification_section(original_config, validated_config, errors, warnings)
        self._validate_rate_limiting_section(original_config, validated_config, errors, warnings)

    def _validate_password_section(
        self,
        security_config: Dict[str, Any],
        errors: List[str],
        warnings: List[str],
    ) -> None:
        """パスワードポリシー・ログイン試行・ロックアウト設定の検証"""
        password_config = security_config.get("password_policy", {})
        if not isinstance(password_config, dict):
            return

        min_length = password_config.get("min_length", 8)
        if min_length < 8:
            errors.append("パスワードの最小長は8文字以上に設定してください。")
        elif min_length > 128:
            warnings.append("パスワードの最小長が128文字を超えています。通常は12-16文字で十分です。")

        # 文字種別の要件チェック
        requirements = {
            "require_uppercase": "大文字",
            "require_lowercase": "小文字",
            "require_numbers": "数字",
            "require_special_chars": "特殊文字"
        }

        missing_requirements = []
        for req_key, req_name in requirements.items():
            if password_config.get(req_key, False):
                continue
            missing_requirements.append(req_name)

        if missing_requirements:
            warnings.append(
                f"パスワードポリシーの要件が緩和されています。以下を有効化することを検討してください: {', '.join(missing_requirements)}"
            )

        # 最大試行回数チェック
        max_attempts = security_config.get("max_login_attempts", 5)
        if max_attempts > 10:
            warnings.append("最大ログイン試行回数が高すぎます。DDoS攻撃のリスクが高まります。")
        elif max_attempts < 3:
            warnings.append("最大ログイン試行回数が低すぎます。アカウントロックアウトが頻発する可能性があります。")

        # ロックアウト時間チェック
        lockout_minutes = security_config.get("lockout_duration_minutes", 15)
        if lockout_minutes > 60:
            warnings.append("ロックアウト時間が長すぎます。ユーザビリティが低下します。")
        elif lockout_minutes < 5:
            warnings.append("ロックアウト時間が短すぎます。ブルートフォース攻撃に対する防御が不十分です。")

    def _validate_billing_section(
        self,
        original_config: Dict[str, Any],
        validated_config: Dict[str, Any],
        errors: List[str],
        warnings: List[str],
    ) -> None:
        """billing セクション（tiers / checkout / webhook）の検証"""
        billing_config = original_config.get("billing")
        billing_validated = (
            validated_config.get("billing")
            if isinstance(validated_config.get("billing"), dict)
            else None
        )
        if isinstance(billing_config, dict):
            enabled = bool(billing_config.get("enabled"))
            tiers = billing_config.get("tiers")
            default_price_tier = billing_config.get("default_price_tier")

            if enabled:
                if not isinstance(tiers, dict) or not tiers:
                    errors.append("billing.enabled が true の場合は tiers を辞書で定義してください。")
                else:
                    price_ids: Dict[str, str] = {}
                    for tier_key, tier_data in tiers.items():
                        if not isinstance(tier_key, str) or not tier_key:
                            errors.append("billing.tiers のキーは空ではない文字列である必要があります。")
                            continue
                        if not isinstance(tier_data, dict):
                            errors.append(f"billing.tiers.{tier_key} はオブジェクトである必要があります。")
                            continue

                        price_id = tier_data.get("price_id")
                        if not price_id:
                            errors.append(f"billing.tiers.{tier_key}.price_id を設定してください。")
                        elif not isinstance(price_id, str) or not price_id.startswith("price_"):
                            errors.append(
                                f"billing.tiers.{tier_key}.price_id は 'price_' で始まるStripe価格IDを指定してください。"
                            )
                        else:
                            duplicated_key = price_ids.get(price_id)
                            if duplicated_key and duplicated_key != tier_key:
                                warnings.append(
                                    f"billing.tiers で price_id '{price_id}' が複数のティア ({duplicated_key}, {tier_key}) に設定されています。"
                                )
                            price_ids[price_id] = tier_key

                        description = tier_data.get("description")
                        if description is not None and not isinstance(description, str):
                            errors.append(
                                f"billing.tiers.{tier_key}.description は文字列である必要があります。"
                            )

            if default_price_tier:
                if not isinstance(default_price_tier, str):
                    errors.append("billing.default_price_tier は文字列で指定してください。")
                elif isinstance(tiers, dict) and default_price_tier not in tiers:
                    errors.append(
                        "billing.default_price_tier には tiers に定義されたキーを指定してください。"
                    )
            elif enabled:
                warnings.append("billing.default_price_tier が未設定です。デフォルトプランが決定されません。")

            mode = billing_config.get("mode")
            trial_period_days = billing_config.get("trial_period_days")
            if mode == "buy_once" and trial_period_days:
                warnings.append("buy_once モードでは trial_period_days は無視されます。")

            checkout_config = billing_config.get("checkout")
            if isinstance(checkout_config, dict):
                for url_field in ("success_url", "cancel_url"):
                    url_value = checkout_config.get(url_field)
                    if not url_value:
                        errors.append(f"billing.checkout.{url_field} を設定してください。")
                        continue
                    if not isinstance(url_value, str):
                        errors.append(f"billing.checkout.{url_field} は文字列である必要があります。")
                        continue
                    parsed = urlparse(url_value)
                    if parsed.scheme != "https":
                        errors.append(f"billing.checkout.{url_field} には https スキームのURLを指定してください。")
                    if not parsed.netloc:
                        errors.append(
                            f"billing.checkout.{url_field} に有効なホスト名が含まれていません。"
                        )
                    if parsed.hostname in {"localhost", "127.0.0.1"}:
                        warnings.append(
                            f"billing.checkout.{url_field} のホストがローカルアドレスです。本番環境では公開エンドポイントを指定してください。"
                        )
            elif enabled:
                errors.append("billing.enabled が true の場合は checkout 設定を定義してください。")

            webhook_config = billing_config.get("webhook")
            if (isinstance(webhook_config, dict)
                    and webhook_config.get("enabled")
                    and not webhook_config.get("endpoint_secret_env")):
                warnings.append(
                    "billing.webhook.enabled が true の場合は endpoint_secret_env を設定してください。"
                )

            if isinstance(billing_validated, dict):
                billing_validated["mode"] = mode or "subscription"

    def _validate_notification_section(
        self,
        original_config: Dict[str, Any],
        validated_config: Dict[str, Any],
        errors: List[str],
        warnings: List[str],
    ) -> None:
        """notification セクション（email / webhook 送信先）の検証"""
        notification_config = original_config.get("notification")
        notification_validated = validated_config.get("notification")
        if (isinstance(notification_config, dict)
                and isinstance(notification_validated, dict)
                and notification_config.get("enabled")):
                email_conf = notification_config.get("email", {})
                webhook_conf = notification_config.get("webhook", {})

                email_ready = False
                if isinstance(email_conf, dict):
                    email_validated = notification_validated.setdefault("email", {})
                    smtp_server = email_conf.get("smtp_server")
                    from_address = email_conf.get("from_address")
                    smtp_port = email_conf.get("smtp_port")
                    to_addresses = email_conf.get("to_addresses")
                    smtp_server_ok = False
                    smtp_port_ok = False

                    if smtp_server:
                        if not isinstance(smtp_server, str) or not smtp_server.strip():
                            errors.append("notification.email.smtp_server は空白以外の文字列で指定してください。")
                        elif smtp_port is None:
                            errors.append("notification.email.smtp_server を使用する場合は smtp_port を指定してください。")
                        else:
                            email_validated["smtp_server"] = smtp_server.strip()
                            smtp_server_ok = True
                        email_ready = True

                    if from_address:
                        if not isinstance(from_address, str) or not self._is_valid_email(from_address.strip()):
                            errors.append("notification.email.from_address は有効なメールアドレスである必要があります。")
                        else:
                            email_validated["from_address"] = from_address.strip()
                    elif smtp_server:
                        errors.append("notification.email.from_address は通知メール送信時に必須です。")

                    if isinstance(smtp_port, int):
                        email_validated["smtp_port"] = smtp_port
                        smtp_port_ok = True
                    elif smtp_port is not None:
                        errors.append("notification.email.smtp_port は整数で指定してください。")

                    normalized_to = self._normalize_email_list(
                        "notification.email.to_addresses", to_addresses, errors
                    )
                    if normalized_to:
                        email_validated["to_addresses"] = normalized_to
                        duplicates = self._find_duplicates(normalized_to)
                        if duplicates:
                            warnings.append(
                                "notification.email.to_addresses に重複があります: " + ", ".join(duplicates)
                            )
                        email_ready = True
                    elif smtp_server:
                        errors.append("notification.email.to_addresses には1件以上の有効なメールアドレスを指定してください。")

                    email_ready = email_ready and smtp_server_ok and smtp_port_ok and bool(email_validated.get("from_address")) and bool(email_validated.get("to_addresses"))

                webhook_ready = False
                if isinstance(webhook_conf, dict):
                    webhook_validated = notification_validated.setdefault("webhook", {})
                    url = webhook_conf.get("url")
                    method = webhook_conf.get("method")
                    if url:
                        if not isinstance(url, str) or not self._is_valid_url(url.strip()):
                            errors.append("notification.webhook.url は http(s):// 形式の有効なURLを指定してください。")
                        else:
                            webhook_validated["url"] = url.strip()
                            webhook_ready = True
                            if method:
                                normalized_method = method.upper()
                                allowed = {"GET", "POST", "PUT", "PATCH", "DELETE"}
                                if normalized_method not in allowed:
                                    errors.append(
                                        "notification.webhook.method は GET/POST/PUT/PATCH/DELETE のいずれかで指定してください。"
                                    )
                                else:
                                    webhook_validated["method"] = normalized_method
                            else:
                                webhook_validated["method"] = "POST"
                            if webhook_validated["url"].lower().startswith("http://"):
                                errors.append("notification.webhook.url は https:// で始まる必要があります。")
                            parsed_url = urlparse(webhook_validated["url"])
                            if parsed_url.hostname in {"localhost", "127.0.0.1"}:
                                warnings.append("notification.webhook.url のホストがローカルアドレスです。本番運用では外部到達可能なエンドポイントを設定してください。")
                    elif method:
                        warnings.append("notification.webhook.method が指定されていますが url が未設定です。")

                if not (email_ready or webhook_ready):
                    errors.append("notification.enabled が true の場合は email または webhook の送信先を設定してください。")

    def _validate_rate_limiting_section(
        self,
        original_config: Dict[str, Any],
        validated_config: Dict[str, Any],
        errors: List[str],
        warnings: List[str],
    ) -> None:
        """rate_limiting セクションの整合性検証"""
        rate_limit_config = original_config.get("rate_limiting")
        rate_limit_validated = validated_config.get("rate_limiting")
        if isinstance(rate_limit_config, dict) and isinstance(rate_limit_validated, dict) and rate_limit_config.get("enabled"):
            minute = rate_limit_config.get("requests_per_minute")
            hour = rate_limit_config.get("requests_per_hour")
            day = rate_limit_config.get("requests_per_day")
            if isinstance(minute, int) and isinstance(hour, int) and minute > hour:
                errors.append("requests_per_hour は requests_per_minute 以上である必要があります。")
            if isinstance(hour, int) and isinstance(day, int) and hour > day:
                errors.append("requests_per_day は requests_per_hour 以上である必要があります。")
            if isinstance(minute, int) and isinstance(hour, int) and minute * 60 > hour:
                warnings.append("requests_per_hour は requests_per_minute * 60 以上になるよう調整することを検討してください。")
            if isinstance(hour, int) and isinstance(day, int) and hour * 24 > day:
                warnings.append("requests_per_day は requests_per_hour * 24 以上になるよう調整することを検討してください。")

    def _normalize_ip_entries(
        self,
        field_name: str,
        values: Any,
        errors: List[str],
        warnings: List[str],
    ) -> Optional[List[str]]:
        """IPアドレスまたはCIDR表現の一覧を検証し正規化する"""

        if values is None:
            return None

        if not isinstance(values, list):
            errors.append(f"{field_name} は配列である必要があります。")
            return None

        normalized: List[str] = []
        for index, raw in enumerate(values):
            if not isinstance(raw, str):
                errors.append(f"{field_name}[{index}] は文字列である必要があります。")
                continue

            candidate = raw.strip()
            if not candidate:
                errors.append(f"{field_name}[{index}] は空文字列ではいけません。")
                continue

            try:
                network = ipaddress.ip_network(candidate, strict=False)
                normalized.append(str(network))
                continue
            except ValueError:
                pass

            try:
                address = ipaddress.ip_address(candidate)
                normalized.append(str(address))
            except ValueError:
                errors.append(f"{field_name}[{index}] は有効なIPアドレスまたはCIDRである必要があります。")

        duplicates = self._find_duplicates(normalized)
        if duplicates:
            warnings.append(
                f"{field_name} に重複があります: {', '.join(duplicates)}"
            )

        return normalized

    def _normalize_email_list(
        self,
        field_name: str,
        values: Any,
        errors: List[str],
    ) -> List[str]:
        """メールアドレス一覧の検証と正規化"""

        if values is None:
            return []

        if not isinstance(values, list):
            errors.append(f"{field_name} は配列である必要があります。")
            return []

        normalized: List[str] = []
        for index, raw in enumerate(values):
            if not isinstance(raw, str):
                errors.append(f"{field_name}[{index}] は文字列である必要があります。")
                continue

            candidate = raw.strip()
            if not candidate:
                errors.append(f"{field_name}[{index}] は空文字列ではいけません。")
                continue

            if not self._is_valid_email(candidate):
                errors.append(f"{field_name}[{index}] は有効なメールアドレスである必要があります。")
                continue

            normalized.append(candidate)

        return normalized

    def _is_valid_email(self, value: str) -> bool:
        """メールアドレス形式の簡易検証"""

        _, address = parseaddr(value)
        if not address:
            return False
        pattern = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
        return re.match(pattern, address) is not None

    def _is_valid_url(self, value: str) -> bool:
        """URL形式の簡易検証"""

        try:
            parsed = urlparse(value)
        except Exception:
            return False
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    def _find_duplicates(self, items: List[str]) -> List[str]:
        """リスト内の重複要素を検出"""

        seen = set()
        duplicates = set()
        for item in items:
            if item in seen:
                duplicates.add(item)
            else:
                seen.add(item)
        return sorted(duplicates)

    def _validate_secure_file_path(
        self,
        field_name: str,
        value: Any,
        errors: List[str],
        warnings: List[str],
        base_directory: Optional[Path] = None,
    ) -> Optional[str]:
        """設定で参照される機密ファイルパスを検証し正規化する"""

        if not isinstance(value, str):
            errors.append(f"{field_name} は文字列で指定してください。")
            return None

        candidate = Path(value).expanduser()
        if not candidate.is_absolute():
            errors.append(f"{field_name} には絶対パスを指定してください。")
            return None

        try:
            resolved = candidate.resolve()
        except OSError as exc:
            errors.append(f"{field_name} の解決に失敗しました: {exc}")
            return None

        if base_directory is None:
            base_directory = Path.cwd()

        if not _is_within_directory(base_directory, resolved):
            errors.append(f"{field_name} はアプリケーションディレクトリ外を指しています: {resolved}")
            return None

        if not resolved.exists():
            warnings.append(f"{field_name} '{resolved}' が存在しません。配置を確認してください。")
        elif not resolved.is_file():
            errors.append(f"{field_name} にはファイルを指定してください。")
            return None

        if resolved.suffix.lower() not in {".crt", ".pem", ".key", ".cer"}:
            warnings.append(f"{field_name} の拡張子が証明書/鍵ファイルとして一般的ではありません。内容を確認してください。")

        return str(resolved)

    def add_custom_rule(self, field_name: str, rules: Dict[str, Any]) -> None:
        """カスタム検証ルールを追加"""
        self.validation_rules[field_name] = rules
        logger.info(f"カスタム検証ルールを追加しました: {field_name}")

    def remove_rule(self, field_name: str) -> bool:
        """検証ルールを削除"""
        if field_name in self.validation_rules:
            del self.validation_rules[field_name]
            logger.info(f"検証ルールを削除しました: {field_name}")
            return True
        return False

    def get_validation_report(self, config_path: str) -> Dict[str, Any]:
        """検証レポートを取得"""
        validation_result = self.validate(config_path)

        return {
            "config_file": config_path,
            "validation_time": self._get_current_time(),
            "validation_result": validation_result,
            "summary": {
                "is_valid": validation_result["valid"],
                "error_count": len(validation_result["errors"]),
                "warning_count": len(validation_result["warnings"])
            }
        }

    def _get_current_time(self) -> str:
        """現在の時刻を UTC で取得"""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    def export_rules(self, filename: str) -> bool:
        """検証ルールをエクスポート"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.validation_rules, f, indent=2, ensure_ascii=False)
            logger.info(f"検証ルールをエクスポートしました: {filename}")
            return True
        except Exception as e:
            logger.error(f"検証ルールエクスポートエラー: {e}")
            return False
