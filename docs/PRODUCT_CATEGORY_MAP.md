# Cocoa プロダクト カテゴリー分類と改善トラッキング

**版**: 1.0 / **作成日**: 2026-06-08
**目的**: プロダクト全体（main/ 75 モジュール + services/ + scripts/）を機能カテゴリーに
徹底分割し、各カテゴリーの改善状況・残課題・テスト可能性を一元管理する。

## 環境制約（テスト可能性の前提）

本コンテナには重量級/ネイティブ依存が未インストール。以下は import 不可のため
ユニットテスト対象外（修正は可能だが検証不可）:

- **依存ブロック (38)**: torch, numpy, cv2, PIL, aiohttp, fastapi, flask, stripe, web3,
  openai, websockets, qrcode, sqlalchemy, prometheus_client, sentence_transformers, tkinter, PyQt5
- **ネイティブクラッシュ (7)**: cryptography の native binding が pyo3 panic
  （`advanced_security_2025`, `config_encryptor`, `enhanced_encryption`,
  `integrated_security`, `logging_manager`, `notification_system`, `preset_manager`）
- **相対 import 不整合 (8)**: `main/` に `__init__.py` が無いのに `from .x import` を使用
  （`avatar_agent`, `avatar_performance_monitor`, `metaverse_integration`,
  `multi_avatar_manager`, `social_media_optimizer`, `template_library`,
  `video_analytics`, `vr_ar_avatar_system`）。プロジェクト規約は「絶対 import + main/ を
  sys.path に追加」。ただし大半が `integrated_security`（crypto crash）にも依存するため、
  相対→絶対の修正後もこの環境では import 不可。

## カテゴリー分類（14カテゴリー）

凡例: ✅ テスト済 / 🟡 未テスト・改善余地あり / ⛔ 依存ブロック / 💥 crypto crash / 🔗 相対import

### 1. Avatar Core / Parameters（アバター・パラメータ）
| モジュール | 状態 | 備考 |
|---|---|---|
| avatar_parameters | ✅ | estimate_joint_range 等 |
| avatar_parameter_sets | ✅ | プリセット定義 |
| parameters | 🟡 | 10万パラメータ生成（純データ） |
| parameters_batch_validator | ✅ | test_batch_validator |
| parameter_optimizer | ⛔ numpy | |
| joint_range_report | ✅ | |
| avatar_parameter_editor | ⛔ PyQt5 | GUI |

### 2. Preset Management（プリセット管理）
| モジュール | 状態 | 備考 |
|---|---|---|
| preset_schema | ✅ | |
| preset_diff_core | ✅ | test_preset_diff |
| preset_change_history | ✅ | test_preset_history (REQ-PH) |
| preset_history_diff_and_rollback | ✅ | |
| preset_history_alert | 🟡 → 本リビジョンで対応 | Slack 異常検知。純ロジック未分離で未テスト |
| validate_and_repair_presets | ✅ | |
| template_filters | ✅ | |
| preset_manager | 💥 crypto | |
| preset_history_dashboard | ⛔ flask | |
| template_library | 🔗+💥 | |
| avatar_preset_linker_gui | ⛔ tkinter | |

### 3. VRChat Integration（VRChat連携）
| モジュール | 状態 | 備考 |
|---|---|---|
| vrchat_performance_analyzer | ✅ (53 tests) | 全22次元ランク・クロスPF・VRAM |
| vrchat_parameter_budget | ✅ | test_vrchat_budget |
| vrchat_sdk_integration | ⛔ PIL | |

### 4. AI / Generation（AI生成）
| モジュール | 状態 |
|---|---|
| ai_avatar_generator | ⛔ torch |
| ai_avatar_gui | ⛔ tkinter |
| rag_avatar_generator | ⛔ sentence_transformers |
| photo_to_avatar_generator | ⛔ numpy |
| voice_cloning | ⛔ numpy |
| emotional_intelligence | ⛔ numpy |
| interactive_ai_agent | ⛔ openai |
| interactive_avatar | ⛔ websockets |
| avatar_agent | 🔗+💥 |
| avatar_personality_tuner | ⛔ numpy |

### 5. Media / Video（メディア）
| モジュール | 状態 |
|---|---|
| video_creator | ⛔ PIL |
| avatar_video_creator | ⛔ cv2 |
| video_analytics | 🔗+💥 |
| virtual_backgrounds | ⛔ PIL |
| social_media_optimizer | 🔗+💥 |

### 6. Monitoring / Observability（監視）
| モジュール | 状態 |
|---|---|
| performance_monitor | ✅ |
| performance_analyzer | ⛔ psutil |
| avatar_performance_monitor | 🔗+💥 |
| health_monitor | ✅ |
| prometheus_monitor | ⛔ prometheus_client |
| grafana_integration | ✅ |

### 7. Infrastructure / Caching（基盤）
| モジュール | 状態 |
|---|---|
| cache_manager | ✅ |
| redis_cache_manager | ✅ |
| database_manager | ⛔ sqlalchemy |
| dependency_injection | ✅ |
| async_base | ✅ |

### 8. Security（セキュリティ）
| モジュール | 状態 |
|---|---|
| integrated_security | 💥 crypto |
| advanced_security_2025 | 💥 crypto |
| enhanced_encryption | 💥 crypto |
| config_encryptor | 💥 crypto |
| secret_manager | ✅ |
| two_factor_auth | ⛔ qrcode |
| blockchain_audit | ⛔ web3 |

### 9. Resilience / Ops（回復性・運用）
| モジュール | 状態 |
|---|---|
| disaster_recovery | ✅ |
| enhanced_disaster_recovery | ✅ |
| notification_system | 💥 crypto |
| logging_config | ✅ |
| logging_manager | 💥 crypto |

### 10. Config（設定）
| モジュール | 状態 |
|---|---|
| config | ✅ |
| config_validator | ✅ |
| services/shared/config | ✅ |

### 11. i18n（国際化）
| モジュール | 状態 |
|---|---|
| i18n | ✅ |
| i18n_manager | ⛔ aiohttp |
| template_filters | ✅ |

### 12. Emerging Tech / Metaverse（先端技術）
| モジュール | 状態 |
|---|---|
| metaverse_integration | 🔗 |
| nft_avatar_manager | ⛔ web3 |
| ar_cloud_manager | ⛔ numpy |
| edge_ai_manager | ⛔ torch |
| global_edge_manager | ✅ |
| vr_ar_avatar_system | 🔗+💥 |
| bci_manager | ⛔ numpy |

### 13. Commerce / API（課金・API）
| モジュール | 状態 |
|---|---|
| billing_service | ⛔ stripe |
| api_server | ⛔ fastapi |
| api_integration | ⛔ aiohttp |

### 14. Multi-avatar / Orchestration（統合）
| モジュール | 状態 |
|---|---|
| multi_avatar_manager | 🔗+💥 |
| main | 🟡 エントリポイント |

## 横断課題（cross-cutting）

| ID | 課題 | 対応 |
|---|---|---|
| X-01 | `main/` に `__init__.py` 無しで相対 import を使うトップレベルモジュール（28ファイル, モジュールレベル `from .X import`） | ✅ 対応済: 全て絶対 import に統一（`from .X` → `from X`）。`main/integrations/` は正規パッケージ（`__init__.py` 有）のため相対 import を維持。`dependency_injection.ConfigService` の関数内相対 import（fallback 無し・インスタンス化でクラッシュ）も修正しテスト追加。py_compile + ruff E9 で検証（多くは crypto/heavy-dep で import 自体は本環境で不可だが、相対 import 欠陥は除去） |
| X-02 | naive `datetime` の散在 | 本ループで主要モジュールを UTC 化済（performance_monitor, health_monitor, disaster_recovery 系, global_edge_manager, grafana_integration, scripts 群）。残: preset_history_alert |
| X-03 | テスト不能な heavy-dep 群 | 依存をインストールするか、純ロジックを dep から分離する設計（DI）を推奨 |

## 本カテゴリー分割作業での対応対象

テスト可能かつ未対応の純 Python モジュール:
- **preset_history_alert**（カテゴリー2）: 純異常検知ロジックを分離してテスト可能化（本リビジョンで実施）
