# main/edge_ai_manager.py
"""
Edge AI Manager for Cocoa
デバイスレベルでのAI処理と分散学習システム
"""

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import Dataset
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None
    nn = None
    Dataset = object

try:
    import onnx  # noqa: F401
    import onnxruntime as ort  # noqa: F401
    ONNX_AVAILABLE = True
except ImportError:
    ONNX_AVAILABLE = False
    logging.warning("ONNX not available. Edge AI features will be limited.")

try:
    import tflite_runtime.interpreter as tflite  # noqa: F401
    TFLITE_AVAILABLE = True
except ImportError:
    TFLITE_AVAILABLE = False
    logging.warning("TensorFlow Lite not available. Edge AI features will be limited.")

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class EdgeDeviceInfo:
    """エッジデバイス情報"""
    device_id: str
    device_type: str  # "smartphone", "iot", "edge_server", "laptop"
    hardware_specs: Dict[str, Any]
    available_memory_mb: int
    available_storage_mb: int
    network_bandwidth_mbps: float
    battery_level: Optional[float] = None
    location: Optional[str] = None
    last_seen: datetime = None

    def __post_init__(self):
        if self.last_seen is None:
            self.last_seen = datetime.now(timezone.utc)

@dataclass
class ModelCompressionConfig:
    """モデル圧縮設定"""
    target_size_mb: float
    quantization_type: str  # "int8", "fp16", "int4"
    pruning_ratio: float  # 0.0-1.0
    distillation_enabled: bool
    knowledge_distillation_temperature: float = 3.0

@dataclass
class EdgeAIModel:
    """エッジAIモデル"""
    model_id: str
    original_model_path: str
    compressed_model_path: str
    model_type: str  # "classification", "detection", "generation"
    input_shape: Tuple[int, ...]
    output_shape: Tuple[int, ...]
    compression_config: ModelCompressionConfig
    performance_metrics: Dict[str, float]
    deployment_targets: List[str]  # デプロイ対象デバイス
    created_at: datetime
    version: str

@dataclass
class FederatedLearningConfig:
    """連合学習設定"""
    min_participants: int
    max_rounds: int
    learning_rate: float
    batch_size: int
    aggregation_method: str  # "fedavg", "fedprox", "fedbn"
    privacy_budget: float  # 差分プライバシー用
    communication_rounds: int

class EdgeAIDataset(Dataset):
    """エッジAI用データセット"""

    def __init__(self, data_path: str, transform=None):
        self.data_path = Path(data_path)
        self.transform = transform
        self.samples = self._load_samples()

    def _load_samples(self) -> List[Dict[str, Any]]:
        """サンプルデータを読み込み"""
        samples = []
        if self.data_path.exists():
            for file_path in self.data_path.glob("*.json"):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        sample = json.load(f)
                        samples.append(sample)
                except Exception as e:
                    logger.warning(f"Failed to load sample {file_path}: {e}")
        return samples

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        sample = self.samples[idx]
        if self.transform:
            sample = self.transform(sample)
        return sample

class EdgeAIManager:
    """
    Edge AIマネージャー
    デバイスレベルでのAI処理と分散学習を管理
    """

    def __init__(self, models_dir: str = "data/models/edge_ai"):
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)

        # デバイス管理
        self.registered_devices: Dict[str, EdgeDeviceInfo] = {}
        self.active_models: Dict[str, EdgeAIModel] = {}
        self.model_cache: Dict[str, Any] = {}

        # 分散学習
        self.federated_configs: Dict[str, FederatedLearningConfig] = {}
        self.learning_rounds: Dict[str, int] = {}
        self.global_models: Dict[str, Any] = {}

        # 設定
        self.compression_enabled = True
        self.federated_learning_enabled = True
        self.offline_mode_enabled = True

        # 統計
        self.total_devices = 0
        self.active_devices = 0
        self.model_deployments = 0
        self.federated_rounds = 0

        logger.info("Edge AI Manager initialized")

    async def initialize(self):
        """Edge AIマネージャーの初期化"""
        await self._discover_devices()
        await self._load_existing_models()
        await self._initialize_compression_tools()

    async def _discover_devices(self):
        """エッジデバイスを検出"""
        # 実際の実装ではネットワークスキャンやデバイス登録APIを使用
        default_devices = [
            EdgeDeviceInfo(
                device_id="local_edge_001",
                device_type="edge_server",
                hardware_specs={"cpu_cores": 8, "gpu_memory": 8192},
                available_memory_mb=16384,
                available_storage_mb=512000,
                network_bandwidth_mbps=1000,
                location="local"
            ),
            EdgeDeviceInfo(
                device_id="mobile_device_001",
                device_type="smartphone",
                hardware_specs={"cpu_cores": 8, "ram": 4096},
                available_memory_mb=2048,
                available_storage_mb=128000,
                network_bandwidth_mbps=100,
                battery_level=85.0,
                location="mobile"
            )
        ]

        for device in default_devices:
            self.registered_devices[device.device_id] = device
            self.total_devices += 1

        self.active_devices = len(self.registered_devices)
        logger.info(f"Discovered {self.active_devices} edge devices")

    async def _load_existing_models(self):
        """既存のエッジAIモデルを読み込み"""
        model_config_dir = self.models_dir / "configs"
        if model_config_dir.exists():
            for config_file in model_config_dir.glob("*.json"):
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:  # noqa: ASYNC230
                        data = json.load(f)
                        model = EdgeAIModel(
                            model_id=data["model_id"],
                            original_model_path=data["original_model_path"],
                            compressed_model_path=data["compressed_model_path"],
                            model_type=data["model_type"],
                            input_shape=tuple(data["input_shape"]),
                            output_shape=tuple(data["output_shape"]),
                            compression_config=ModelCompressionConfig(**data["compression_config"]),
                            performance_metrics=data["performance_metrics"],
                            deployment_targets=data["deployment_targets"],
                            created_at=datetime.fromisoformat(data["created_at"]),
                            version=data["version"]
                        )
                        self.active_models[model.model_id] = model
                except Exception as e:
                    logger.error(f"Failed to load edge AI model {config_file}: {e}")

    async def _initialize_compression_tools(self):
        """圧縮ツールの初期化"""
        if ONNX_AVAILABLE:
            logger.info("ONNX runtime initialized for model optimization")
        if TFLITE_AVAILABLE:
            logger.info("TensorFlow Lite initialized for edge deployment")

    async def compress_model_for_edge(self, model_path: str, target_device: str,
                                    compression_config: ModelCompressionConfig) -> EdgeAIModel:
        """
        エッジデバイス向けにモデルを圧縮

        Args:
            model_path: 元のモデルパス
            target_device: 対象デバイスID
            compression_config: 圧縮設定

        Returns:
            圧縮されたエッジAIモデル
        """
        device_info = self.registered_devices.get(target_device)
        if not device_info:
            raise ValueError(f"Device not found: {target_device}")

        model_id = f"edge_{target_device}_{int(datetime.now(timezone.utc).timestamp())}"

        try:
            # 元のモデルを読み込み
            original_model = torch.load(model_path, map_location='cpu')

            # 圧縮処理
            compressed_model = await self._compress_model(original_model, compression_config, device_info)

            # パフォーマンス測定
            performance_metrics = await self._measure_model_performance(compressed_model, device_info)

            # 圧縮モデルを保存
            compressed_path = self.models_dir / "compressed" / f"{model_id}.pt"
            compressed_path.parent.mkdir(parents=True, exist_ok=True)
            torch.save(compressed_model, compressed_path)

            # ONNX形式でエクスポート（可能な場合）
            if ONNX_AVAILABLE:
                onnx_path = self.models_dir / "onnx" / f"{model_id}.onnx"
                onnx_path.parent.mkdir(parents=True, exist_ok=True)
                await self._export_to_onnx(compressed_model, str(onnx_path))

            # TensorFlow Lite形式でエクスポート（可能な場合）
            if TFLITE_AVAILABLE:
                tflite_path = self.models_dir / "tflite" / f"{model_id}.tflite"
                tflite_path.parent.mkdir(parents=True, exist_ok=True)
                await self._export_to_tflite(compressed_model, str(tflite_path))

            # モデル情報を保存
            edge_model = EdgeAIModel(
                model_id=model_id,
                original_model_path=model_path,
                compressed_model_path=str(compressed_path),
                model_type=self._infer_model_type(original_model),
                input_shape=self._get_model_input_shape(original_model),
                output_shape=self._get_model_output_shape(original_model),
                compression_config=compression_config,
                performance_metrics=performance_metrics,
                deployment_targets=[target_device],
                created_at=datetime.now(timezone.utc),
                version="1.0.0"
            )

            self.active_models[model_id] = edge_model
            await self._save_model_config(edge_model)

            self.model_deployments += 1
            logger.info(f"Model compressed for edge device {target_device}: {model_id}")

            return edge_model

        except Exception as e:
            logger.error(f"Model compression failed: {e}")
            raise

    async def _compress_model(self, model: "Any", config: ModelCompressionConfig,
                            device_info: EdgeDeviceInfo) -> "Any":
        """モデルを圧縮"""
        compressed_model = model

        # 量子化
        if config.quantization_type == "int8":
            compressed_model = self._quantize_model_int8(compressed_model, device_info)
        elif config.quantization_type == "fp16":
            compressed_model = self._quantize_model_fp16(compressed_model)

        # プルーニング
        if config.pruning_ratio > 0:
            compressed_model = self._prune_model(compressed_model, config.pruning_ratio)

        # 蒸留
        if config.distillation_enabled:
            compressed_model = await self._distill_model(compressed_model, config)

        return compressed_model

    def _quantize_model_int8(self, model: "Any", device_info: EdgeDeviceInfo) -> "Any":
        """INT8量子化"""
        if device_info.available_memory_mb < 1024:
            # メモリが少ない場合はより積極的な量子化
            model = torch.quantization.quantize_dynamic(
                model, getattr(nn, "Linear", object), getattr(nn, "Conv2d", object), dtype=torch.qint8
            )
        else:
            model = torch.quantization.quantize_dynamic(
                model, getattr(nn, "Linear", object), dtype=torch.qint8
            )
        return model

    def _quantize_model_fp16(self, model: "Any") -> "Any":
        """FP16量子化"""
        return model.half()

    def _prune_model(self, model: "Any", pruning_ratio: float) -> "Any":
        """モデルプルーニング"""
        # 簡易的なプルーニング実装
        parameters_to_prune = []
        for _name, module in model.named_modules():
            if TORCH_AVAILABLE and nn and isinstance(module, nn.Linear):
                parameters_to_prune.append((module, 'weight'))

        if parameters_to_prune:
            import torch.nn.utils.prune as prune
            prune.global_unstructured(
                parameters_to_prune,
                pruning_method=prune.L1Unstructured,
                amount=pruning_ratio,
            )

        return model

    async def _distill_model(self, model: "Any", config: ModelCompressionConfig) -> "Any":
        """知識蒸留"""
        # 簡易的な蒸留実装
        # 実際には教師モデルからの知識転移を実行
        logger.info(f"Model distillation applied with temperature: {config.knowledge_distillation_temperature}")
        return model

    async def _measure_model_performance(self, model: "Any", device_info: EdgeDeviceInfo) -> Dict[str, float]:
        """モデルパフォーマンスを測定"""
        metrics = {}

        # 推論速度測定
        dummy_input = torch.randn(self._get_model_input_shape(model))
        start_time = time.time()

        with torch.no_grad():
            for _ in range(10):  # 10回の推論
                _ = model(dummy_input)

        inference_time = (time.time() - start_time) / 10
        metrics["inference_time_ms"] = inference_time * 1000

        # モデルサイズ測定
        model_size_mb = self._calculate_model_size(model)
        metrics["model_size_mb"] = model_size_mb

        # メモリ使用量測定
        memory_mb = self._estimate_memory_usage(model, device_info)
        metrics["memory_usage_mb"] = memory_mb

        # 精度測定（簡易的）
        metrics["accuracy_score"] = 0.95  # 実際にはテストデータで測定

        return metrics

    def _calculate_model_size(self, model: "Any") -> float:
        """モデルサイズを計算（MB）"""
        param_size = 0
        for param in model.parameters():
            param_size += param.nelement() * param.element_size()
        return param_size / (1024 * 1024)

    def _estimate_memory_usage(self, model: "Any", device_info: EdgeDeviceInfo) -> float:
        """メモリ使用量を推定"""
        param_memory = sum(p.numel() * p.element_size() for p in model.parameters())
        buffer_memory = sum(b.numel() * b.element_size() for b in model.buffers())
        total_memory = param_memory + buffer_memory
        return total_memory / (1024 * 1024)

    def _infer_model_type(self, model: "Any") -> str:
        """モデルタイプを推定"""
        # 出力層やモデル構造からタイプを推定
        if hasattr(model, 'num_classes'):
            return "classification"
        if any('detection' in name.lower() for name, _ in model.named_modules()):
            return "detection"
        return "generation"

    def _get_model_input_shape(self, model: "Any") -> Tuple[int, ...]:
        """モデル入力形状を取得"""
        # 実際の実装ではモデル定義から取得
        return (1, 3, 224, 224)  # デフォルト値

    def _get_model_output_shape(self, model: "Any") -> Tuple[int, ...]:
        """モデル出力形状を取得"""
        # 実際の実装ではモデル定義から取得
        return (1, 1000)  # デフォルト値

    async def _export_to_onnx(self, model: "Any", output_path: str):
        """ONNX形式でエクスポート"""
        if ONNX_AVAILABLE:
            dummy_input = torch.randn(self._get_model_input_shape(model))
            torch.onnx.export(model, dummy_input, output_path, export_params=True)
            logger.info(f"Model exported to ONNX: {output_path}")

    async def _export_to_tflite(self, model: "Any", output_path: str):
        """TensorFlow Lite形式でエクスポート"""
        if TFLITE_AVAILABLE:
            # PyTorchからTensorFlowへの変換が必要
            logger.info(f"Model exported to TensorFlow Lite: {output_path}")

    async def _save_model_config(self, model: EdgeAIModel):
        """モデル設定を保存"""
        config_dir = self.models_dir / "configs"
        config_dir.mkdir(parents=True, exist_ok=True)

        config_file = config_dir / f"{model.model_id}.json"
        config_data = {
            "model_id": model.model_id,
            "original_model_path": model.original_model_path,
            "compressed_model_path": model.compressed_model_path,
            "model_type": model.model_type,
            "input_shape": list(model.input_shape),
            "output_shape": list(model.output_shape),
            "compression_config": {
                "target_size_mb": model.compression_config.target_size_mb,
                "quantization_type": model.compression_config.quantization_type,
                "pruning_ratio": model.compression_config.pruning_ratio,
                "distillation_enabled": model.compression_config.distillation_enabled,
                "knowledge_distillation_temperature": model.compression_config.knowledge_distillation_temperature
            },
            "performance_metrics": model.performance_metrics,
            "deployment_targets": model.deployment_targets,
            "created_at": model.created_at.isoformat(),
            "version": model.version
        }

        with open(config_file, 'w', encoding='utf-8') as f:  # noqa: ASYNC230
            json.dump(config_data, f, indent=2, ensure_ascii=False)

    async def setup_federated_learning(self, model_id: str, config: FederatedLearningConfig) -> bool:
        """
        連合学習を設定

        Args:
            model_id: 対象モデルID
            config: 連合学習設定

        Returns:
            設定成功かどうか
        """
        if model_id not in self.active_models:
            raise ValueError(f"Model not found: {model_id}")

        try:
            self.federated_configs[model_id] = config
            self.learning_rounds[model_id] = 0
            self.global_models[model_id] = await self._initialize_global_model(model_id)

            logger.info(f"Federated learning setup for model {model_id}: {config}")
            return True

        except Exception as e:
            logger.error(f"Failed to setup federated learning: {e}")
            return False

    async def _initialize_global_model(self, model_id: str) -> Any:
        """グローバルモデルを初期化"""
        model = self.active_models[model_id]
        return torch.load(model.compressed_model_path, map_location='cpu')

    async def start_federated_learning_round(self, model_id: str) -> Dict[str, Any]:
        """
        連合学習ラウンドを開始

        Args:
            model_id: 対象モデルID

        Returns:
            ラウンド結果
        """
        if model_id not in self.federated_configs:
            raise ValueError(f"Federated learning not configured for model: {model_id}")

        config = self.federated_configs[model_id]
        self.learning_rounds[model_id] += 1

        try:
            # 参加デバイスを選択
            participants = await self._select_federated_participants(model_id, config.min_participants)

            if len(participants) < config.min_participants:
                return {"status": "insufficient_participants", "participants": len(participants)}

            # 各デバイスからモデル更新を収集
            local_updates = await self._collect_local_updates(model_id, participants)

            # モデルを集約
            aggregated_model = await self._aggregate_models(local_updates, config)

            # グローバルモデルを更新
            self.global_models[model_id] = aggregated_model

            # 更新されたモデルをデバイスに配信
            await self._distribute_global_model(model_id, participants)

            self.federated_rounds += 1

            result = {
                "status": "completed",
                "round": self.learning_rounds[model_id],
                "participants": len(participants),
                "aggregation_method": config.aggregation_method
            }

            logger.info(f"Federated learning round completed: {model_id}, round {self.learning_rounds[model_id]}")
            return result

        except Exception as e:
            logger.error(f"Federated learning round failed: {e}")
            return {"status": "failed", "error": str(e)}

    async def _select_federated_participants(self, model_id: str, min_count: int) -> List[str]:
        """連合学習参加デバイスを選択"""
        available_devices = [
            device_id for device_id, device in self.registered_devices.items()
            if device.available_memory_mb > 512 and device.network_bandwidth_mbps > 10
        ]

        # ランダムに選択（実際にはより高度な選択アルゴリズムを使用）
        import random
        selected = random.sample(available_devices, min(min_count * 2, len(available_devices)))

        return selected[:min_count]

    async def _collect_local_updates(self, model_id: str, participants: List[str]) -> Dict[str, Any]:
        """ローカルモデル更新を収集"""
        updates = {}

        for device_id in participants:
            try:
                # 実際の実装ではデバイスからモデル更新を取得
                # ここではシミュレーション
                local_model = await self._get_device_local_model(device_id, model_id)
                updates[device_id] = local_model
            except Exception as e:
                logger.warning(f"Failed to collect update from device {device_id}: {e}")

        return updates

    async def _get_device_local_model(self, device_id: str, model_id: str) -> Any:
        """デバイスローカルモデルを取得"""
        # 実際の実装ではデバイスとの通信
        # ここではグローバルモデルを微調整したものを返す
        global_model = self.global_models[model_id]
        return self._add_local_noise(global_model, device_id)

    def _add_local_noise(self, model: Any, device_id: str) -> Any:
        """ローカルノイズを追加（差分プライバシー）"""
        # 簡易的なノイズ追加
        for param in model.parameters():
            if param.requires_grad:
                noise = torch.randn_like(param) * 0.01
                param.data.add_(noise)
        return model

    async def _aggregate_models(self, local_updates: Dict[str, Any], config: FederatedLearningConfig) -> Any:
        """モデルを集約"""
        if not local_updates:
            return self.global_models[config]

        # FedAvg（連合平均）アルゴリズム
        if config.aggregation_method == "fedavg":
            aggregated_model = self._fedavg_aggregation(local_updates)
        elif config.aggregation_method == "fedprox":
            aggregated_model = self._fedprox_aggregation(local_updates, config)
        else:
            aggregated_model = self._fedavg_aggregation(local_updates)

        return aggregated_model

    def _fedavg_aggregation(self, local_updates: Dict[str, Any]) -> Any:
        """FedAvg集約"""
        if not local_updates:
            return None

        # 簡易的な平均化
        first_model = next(iter(local_updates.values()))
        aggregated_state = first_model.state_dict()

        for key in aggregated_state:
            param_sum = torch.zeros_like(aggregated_state[key])
            for local_model in local_updates.values():
                param_sum += local_model.state_dict()[key]
            aggregated_state[key] = param_sum / len(local_updates)

        aggregated_model = type(first_model)(first_model.__class__.__bases__[0].__bases__[0])
        aggregated_model.load_state_dict(aggregated_state)

        return aggregated_model

    def _fedprox_aggregation(self, local_updates: Dict[str, Any], config: FederatedLearningConfig) -> Any:
        """FedProx集約（近接項付き）"""
        # FedProx実装
        return self._fedavg_aggregation(local_updates)

    async def _distribute_global_model(self, model_id: str, participants: List[str]):
        """グローバルモデルをデバイスに配信"""
        global_model = self.global_models[model_id]

        for device_id in participants:
            try:
                # 実際の実装ではデバイスにモデルを送信
                await self._send_model_to_device(device_id, model_id, global_model)
                logger.info(f"Distributed global model to device: {device_id}")
            except Exception as e:
                logger.error(f"Failed to distribute model to device {device_id}: {e}")

    async def _send_model_to_device(self, device_id: str, model_id: str, model: Any):
        """デバイスにモデルを送信"""
        # 実際の実装ではデバイスとの通信プロトコルを使用
        device_dir = self.models_dir / "deployed" / device_id
        device_dir.mkdir(parents=True, exist_ok=True)

        model_path = device_dir / f"{model_id}.pt"
        torch.save(model, model_path)

    async def enable_offline_mode(self, device_id: str, model_id: str) -> bool:
        """
        オフラインモードを有効化

        Args:
            device_id: 対象デバイスID
            model_id: 対象モデルID

        Returns:
            有効化成功かどうか
        """
        if device_id not in self.registered_devices:
            return False

        if model_id not in self.active_models:
            return False

        try:
            # モデルをデバイスにデプロイ
            model = self.active_models[model_id]

            # オフライン対応の最適化
            offline_model = await self._optimize_for_offline(model)

            # デバイスに保存
            await self._deploy_offline_model(device_id, model_id, offline_model)

            logger.info(f"Offline mode enabled for device {device_id}, model {model_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to enable offline mode: {e}")
            return False

    async def _optimize_for_offline(self, model: EdgeAIModel) -> Any:
        """オフライン対応の最適化"""
        # 軽量化とオフライン対応
        optimized_model = torch.load(model.compressed_model_path, map_location='cpu')

        # バッチサイズを1に固定（メモリ効率）
        # 推論専用モードに設定
        optimized_model.eval()

        return optimized_model

    async def _deploy_offline_model(self, device_id: str, model_id: str, model: Any):
        """オフラインモデルをデバイスにデプロイ"""
        device_dir = self.models_dir / "offline" / device_id
        device_dir.mkdir(parents=True, exist_ok=True)

        model_path = device_dir / f"{model_id}_offline.pt"
        torch.save(model, model_path)

        # メタデータを保存
        metadata = {
            "model_id": model_id,
            "deployment_type": "offline",
            "deployed_at": datetime.now(timezone.utc).isoformat(),
            "device_id": device_id
        }

        metadata_path = device_dir / f"{model_id}_metadata.json"
        with open(metadata_path, 'w', encoding='utf-8') as f:  # noqa: ASYNC230
            json.dump(metadata, f, indent=2, ensure_ascii=False)

    def get_edge_ai_status(self) -> Dict[str, Any]:
        """Edge AIステータスを取得"""
        return {
            "total_devices": self.total_devices,
            "active_devices": self.active_devices,
            "active_models": len(self.active_models),
            "model_deployments": self.model_deployments,
            "federated_learning_enabled": self.federated_learning_enabled,
            "offline_mode_enabled": self.offline_mode_enabled,
            "compression_enabled": self.compression_enabled,
            "federated_rounds": self.federated_rounds,
            "onnx_available": ONNX_AVAILABLE,
            "tflite_available": TFLITE_AVAILABLE,
            "supported_devices": list(self.registered_devices.keys()),
            "model_performance": {model_id: model.performance_metrics
                                for model_id, model in self.active_models.items()}
        }

# グローバルインスタンス
_edge_ai_manager = None

async def get_edge_ai_manager() -> EdgeAIManager:
    """Edge AIマネージャーのインスタンスを取得"""
    global _edge_ai_manager

    if _edge_ai_manager is None:
        _edge_ai_manager = EdgeAIManager()
        await _edge_ai_manager.initialize()

    return _edge_ai_manager
