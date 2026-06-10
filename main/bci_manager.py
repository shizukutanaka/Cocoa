# main/bci_manager.py
"""
Brain-Computer Interface Manager for Cocoa
次世代入力デバイスに対応したBCIシステム
"""

import json
import logging
import queue
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None
    nn = None
    F = None

try:
    import mne  # noqa: F401
    MNE_AVAILABLE = True
except ImportError:
    MNE_AVAILABLE = False
    logging.warning("MNE-Python not available. EEG processing features will be limited.")

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False
    logging.warning("PyAutoGUI not available. System control features will be limited.")

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class BCISignal:
    """BCI信号データ"""
    timestamp: datetime
    signal_type: str  # "eeg", "fnirs", "ecog", "neuralink"
    channels: "Any"  # チャンネルデータ
    sampling_rate: float
    device_id: str
    user_id: str
    quality_score: float  # 信号品質 (0.0-1.0)
    metadata: Dict[str, Any]

@dataclass
class ThoughtPattern:
    """思考パターン"""
    pattern_id: str
    pattern_type: str  # "movement", "speech", "emotion", "attention"
    signal_signature: "Any"
    confidence_threshold: float
    action_mapping: Dict[str, Any]
    training_data: List[BCISignal]
    accuracy: float
    created_at: datetime
    last_updated: datetime

@dataclass
class BCICommand:
    """BCIコマンド"""
    command_id: str
    command_type: str  # "move", "select", "type", "navigate"
    parameters: Dict[str, Any]
    confidence: float
    timestamp: datetime
    executed: bool = False

@dataclass
class BCIProfile:
    """BCIユーザープロファイル"""
    user_id: str
    baseline_signals: Dict[str, "Any"]
    trained_patterns: List[str]
    calibration_data: Dict[str, Any]
    preferences: Dict[str, Any]
    skill_level: str  # "beginner", "intermediate", "advanced", "expert"
    created_at: datetime
    last_calibration: datetime

class EEGProcessor:
    """EEG信号処理"""

    def __init__(self):
        self.filters = {}
        self.features = {}

    def preprocess_eeg(self, signal: BCISignal) -> "Any":
        """EEG信号の前処理"""
        # ノイズ除去
        filtered = self._apply_filters(signal)

        # 特徴抽出
        return self._extract_features(filtered, signal.sampling_rate)

    def _apply_filters(self, signal: BCISignal) -> "Any":
        """フィルタ適用"""
        # バンドパスフィルタ（1-40Hz）
        if signal.signal_type == "eeg":
            # 簡易的なフィルタリング
            filtered = signal.channels.copy()

            # 50Hzノイズ除去（簡単なノッチフィルタ）
            if signal.sampling_rate > 100:
                filtered = self._notch_filter(filtered, 50, signal.sampling_rate)

        return filtered

    def _notch_filter(self, data: "Any", freq: float, fs: float) -> "Any":
        """ノッチフィルタ"""
        # 簡易的な50Hzノイズ除去
        return data

    def _extract_features(self, data: "Any", sampling_rate: float) -> "Any":
        """特徴抽出"""
        features = []

        # 各チャンネルのパワースペクトル密度
        for channel in range(data.shape[1]):
            # FFT
            fft = np.fft.fft(data[:, channel])
            power = np.abs(fft) ** 2
            freqs = np.fft.fftfreq(len(power), 1/sampling_rate)

            # 各周波数帯のパワー
            bands = {
                'delta': (1, 4),
                'theta': (4, 8),
                'alpha': (8, 12),
                'beta': (12, 30),
                'gamma': (30, 40)
            }

            for (low, high) in bands.values():
                band_power = np.mean(power[(freqs >= low) & (freqs <= high)])
                features.append(band_power)

        return np.array(features)

class NeuralNetwork(nn.Module if TORCH_AVAILABLE and nn else object):
    """BCI用ニューラルネットワーク"""

    def __init__(self, input_size: int, hidden_size: int, output_size: int):
        super().__init__()
        self.fc1 = nn.Linear(input_size, hidden_size)
        self.fc2 = nn.Linear(hidden_size, hidden_size)
        self.fc3 = nn.Linear(hidden_size, output_size)
        self.dropout = nn.Dropout(0.5)

    def forward(self, x):
        x = F.relu(self.fc1(x))
        x = self.dropout(x)
        x = F.relu(self.fc2(x))
        x = self.dropout(x)
        return self.fc3(x)

class BCIManager:
    """
    BCIマネージャー
    脳波インターフェースによる次世代入力システム
    """

    def __init__(self, bci_dir: str = "data/bci"):
        self.bci_dir = Path(bci_dir)
        self.bci_dir.mkdir(parents=True, exist_ok=True)

        # BCIシステム
        self.eeg_processor = EEGProcessor()
        self.signal_queue: queue.Queue = queue.Queue()
        self.connected_devices: Dict[str, Dict[str, Any]] = {}

        # 思考パターン
        self.thought_patterns: Dict[str, ThoughtPattern] = {}
        self.user_profiles: Dict[str, BCIProfile] = {}
        self.active_commands: Dict[str, BCICommand] = {}

        # 機械学習モデル
        self.models: Dict[str, NeuralNetwork] = {}
        self.model_dir = self.bci_dir / "models"
        self.model_dir.mkdir(parents=True, exist_ok=True)

        # 設定
        self.calibration_required = True
        self.realtime_processing = True
        self.adaptive_learning = True

        # 統計
        self.total_signals = 0
        self.processed_commands = 0
        self.training_sessions = 0
        self.accuracy_scores = []

        logger.info("BCI Manager initialized")

    async def initialize(self):
        """BCIマネージャーの初期化"""
        await self._load_trained_models()
        await self._load_user_profiles()
        await self._initialize_signal_processing()

    async def _load_trained_models(self):
        """訓練済みモデルを読み込み"""
        if self.model_dir.exists():
            for model_file in self.model_dir.glob("*.pt"):
                try:
                    model_data = torch.load(model_file, map_location='cpu')
                    pattern_id = model_data["pattern_id"]

                    # モデルを再構築
                    input_size = model_data["input_size"]
                    hidden_size = model_data["hidden_size"]
                    output_size = model_data["output_size"]

                    model = NeuralNetwork(input_size, hidden_size, output_size)
                    model.load_state_dict(model_data["state_dict"])
                    model.eval()

                    self.models[pattern_id] = model

                    logger.info(f"Loaded BCI model: {pattern_id}")

                except Exception as e:
                    logger.error(f"Failed to load BCI model {model_file}: {e}")

    async def _load_user_profiles(self):
        """ユーザープロファイルを読み込み"""
        profile_dir = self.bci_dir / "profiles"
        if profile_dir.exists():
            for profile_file in profile_dir.glob("*.json"):
                try:
                    with open(profile_file, encoding='utf-8') as f:  # noqa: ASYNC230
                        data = json.load(f)

                        profile = BCIProfile(
                            user_id=data["user_id"],
                            baseline_signals={k: np.array(v) for k, v in data["baseline_signals"].items()},
                            trained_patterns=data["trained_patterns"],
                            calibration_data=data["calibration_data"],
                            preferences=data["preferences"],
                            skill_level=data["skill_level"],
                            created_at=datetime.fromisoformat(data["created_at"]),
                            last_calibration=datetime.fromisoformat(data["last_calibration"])
                        )

                        self.user_profiles[profile.user_id] = profile

                except Exception as e:
                    logger.error(f"Failed to load BCI profile {profile_file}: {e}")

    async def _initialize_signal_processing(self):
        """信号処理の初期化"""
        if MNE_AVAILABLE:
            logger.info("MNE-Python initialized for advanced EEG processing")
        else:
            logger.warning("Using basic signal processing")

    async def register_bci_device(self, device_id: str, device_type: str, capabilities: Dict[str, Any]) -> bool:
        """
        BCIデバイスを登録

        Args:
            device_id: デバイスID
            device_type: デバイスタイプ
            capabilities: デバイス機能

        Returns:
            登録成功かどうか
        """
        try:
            device_info = {
                "device_id": device_id,
                "device_type": device_type,
                "capabilities": capabilities,
                "registered_at": datetime.now(timezone.utc),
                "status": "active",
                "calibration_status": "none"
            }

            self.connected_devices[device_id] = device_info

            logger.info(f"BCI device registered: {device_id} ({device_type})")
            return True

        except Exception as e:
            logger.error(f"Failed to register BCI device: {e}")
            return False

    async def process_bci_signal(self, signal: BCISignal) -> List[BCICommand]:
        """
        BCI信号を処理

        Args:
            signal: BCI信号

        Returns:
            生成されたコマンドリスト
        """
        try:
            self.total_signals += 1

            # 信号品質チェック
            if signal.quality_score < 0.5:
                logger.warning(f"Low quality signal from device {signal.device_id}")
                return []

            # 前処理
            processed_features = self.eeg_processor.preprocess_eeg(signal)

            # 思考パターン認識
            commands = await self._recognize_thought_patterns(signal, processed_features)

            # コマンド実行
            for command in commands:
                await self._execute_bci_command(command)

            logger.info(f"Processed BCI signal: {len(commands)} commands generated")
            return commands

        except Exception as e:
            logger.error(f"BCI signal processing failed: {e}")
            return []

    async def _recognize_thought_patterns(self, signal: BCISignal, features: "Any") -> List[BCICommand]:
        """思考パターンを認識"""
        commands = []

        # 各訓練済みパターンに対して推論
        for pattern in self.thought_patterns.values():
            if pattern.pattern_id in self.models:
                model = self.models[pattern.pattern_id]

                # モデルに入力
                with torch.no_grad():
                    input_tensor = torch.from_numpy(features).float().unsqueeze(0)
                    output = model(input_tensor)
                    probabilities = F.softmax(output, dim=1)
                    confidence = torch.max(probabilities).item()

                if confidence > pattern.confidence_threshold:
                    # コマンドを生成
                    command = await self._generate_command_from_pattern(pattern, confidence, signal)
                    commands.append(command)

        return commands

    async def _generate_command_from_pattern(self, pattern: ThoughtPattern, confidence: float,
                                           signal: BCISignal) -> BCICommand:
        """パターンからコマンドを生成"""
        command_id = f"cmd_{uuid.uuid4().hex[:16]}"

        # パターンタイプに応じたコマンド生成
        if pattern.pattern_type == "movement":
            command = self._generate_movement_command(pattern, confidence)
        elif pattern.pattern_type == "speech":
            command = self._generate_speech_command(pattern, confidence)
        elif pattern.pattern_type == "selection":
            command = self._generate_selection_command(pattern, confidence)
        else:
            command = self._generate_generic_command(pattern, confidence)

        command.command_id = command_id
        command.confidence = confidence
        command.timestamp = datetime.now(timezone.utc)

        return command

    def _generate_movement_command(self, pattern: ThoughtPattern, confidence: float) -> BCICommand:
        """移動コマンド生成"""
        # 思考による移動方向の推定
        direction = pattern.action_mapping.get("direction", "forward")
        speed = min(confidence * 2.0, 5.0)  # 最大速度5.0

        return BCICommand(
            command_id="",
            command_type="move",
            parameters={"direction": direction, "speed": speed, "duration": 1.0},
            confidence=confidence,
            timestamp=datetime.now(timezone.utc)
        )

    def _generate_speech_command(self, pattern: ThoughtPattern, confidence: float) -> BCICommand:
        """音声コマンド生成"""
        text = pattern.action_mapping.get("text", "")
        language = pattern.action_mapping.get("language", "en")

        return BCICommand(
            command_id="",
            command_type="speech",
            parameters={"text": text, "language": language},
            confidence=confidence,
            timestamp=datetime.now(timezone.utc)
        )

    def _generate_selection_command(self, pattern: ThoughtPattern, confidence: float) -> BCICommand:
        """選択コマンド生成"""
        target = pattern.action_mapping.get("target", "")
        action = pattern.action_mapping.get("action", "select")

        return BCICommand(
            command_id="",
            command_type="select",
            parameters={"target": target, "action": action},
            confidence=confidence,
            timestamp=datetime.now(timezone.utc)
        )

    def _generate_generic_command(self, pattern: ThoughtPattern, confidence: float) -> BCICommand:
        """一般コマンド生成"""
        return BCICommand(
            command_id="",
            command_type="generic",
            parameters=pattern.action_mapping,
            confidence=confidence,
            timestamp=datetime.now(timezone.utc)
        )

    async def _execute_bci_command(self, command: BCICommand):
        """BCIコマンドを実行"""
        try:
            if command.command_type == "move":
                await self._execute_movement_command(command)
            elif command.command_type == "speech":
                await self._execute_speech_command(command)
            elif command.command_type == "select":
                await self._execute_selection_command(command)
            elif command.command_type == "navigate":
                await self._execute_navigation_command(command)

            command.executed = True
            self.processed_commands += 1

            logger.info(f"Executed BCI command: {command.command_type}")

        except Exception as e:
            logger.error(f"BCI command execution failed: {e}")

    async def _execute_movement_command(self, command: BCICommand):
        """移動コマンドを実行"""
        direction = command.parameters.get("direction", "forward")
        speed = command.parameters.get("speed", 1.0)

        # 実際の実装ではアバターやメタバース環境に移動を適用
        logger.info(f"Movement command: {direction} at speed {speed}")

    async def _execute_speech_command(self, command: BCICommand):
        """音声コマンドを実行"""
        text = command.parameters.get("text", "")

        # テキストを音声に変換
        if PYAUTOGUI_AVAILABLE:
            # システムにテキストを入力
            pyautogui.typewrite(text)
        else:
            logger.info(f"Speech command: {text}")

    async def _execute_selection_command(self, command: BCICommand):
        """選択コマンドを実行"""
        target = command.parameters.get("target", "")
        action = command.parameters.get("action", "select")

        if PYAUTOGUI_AVAILABLE:
            if action == "select":
                pyautogui.click()
            elif action == "double_click":
                pyautogui.doubleClick()
            elif action == "right_click":
                pyautogui.rightClick()

        logger.info(f"Selection command: {action} on {target}")

    async def _execute_navigation_command(self, command: BCICommand):
        """ナビゲーションコマンドを実行"""
        # ブラウザやアプリケーションのナビゲーション
        if PYAUTOGUI_AVAILABLE:
            pyautogui.press('tab')  # タブ移動
        logger.info("Navigation command executed")

    async def train_thought_pattern(self, user_id: str, pattern_type: str,
                                  training_signals: List[BCISignal],
                                  target_action: Dict[str, Any]) -> str:
        """
        思考パターンを訓練

        Args:
            user_id: ユーザーID
            pattern_type: パターンタイプ
            training_signals: 訓練信号
            target_action: 目標アクション

        Returns:
            パターンID
        """
        try:
            pattern_id = f"pattern_{user_id}_{pattern_type}_{int(datetime.now(timezone.utc).timestamp())}"

            # 特徴を抽出
            all_features = []
            for signal in training_signals:
                features = self.eeg_processor.preprocess_eeg(signal)
                all_features.append(features)

            if not all_features:
                raise ValueError("No valid training signals")

            # 特徴を結合
            combined_features = np.vstack(all_features)

            # シグネチャを計算（平均特徴ベクトル）
            signal_signature = np.mean(combined_features, axis=0)

            # モデルを訓練
            input_size = len(signal_signature)
            hidden_size = max(128, input_size * 2)
            output_size = 2  # バイナリ分類（実行/非実行）

            model = NeuralNetwork(input_size, hidden_size, output_size)

            # 訓練データ準備
            X = torch.from_numpy(combined_features).float()
            y = torch.ones(len(training_signals), dtype=torch.long)  # すべて正例

            # 訓練
            criterion = nn.CrossEntropyLoss()
            optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

            model.train()
            for _epoch in range(100):
                optimizer.zero_grad()
                outputs = model(X)
                loss = criterion(outputs, y)
                loss.backward()
                optimizer.step()

            # モデルを保存
            model_path = self.model_dir / f"{pattern_id}.pt"
            torch.save({
                "pattern_id": pattern_id,
                "input_size": input_size,
                "hidden_size": hidden_size,
                "output_size": output_size,
                "state_dict": model.state_dict(),
                "training_date": datetime.now(timezone.utc).isoformat()
            }, model_path)

            # パターンを登録
            pattern = ThoughtPattern(
                pattern_id=pattern_id,
                pattern_type=pattern_type,
                signal_signature=signal_signature,
                confidence_threshold=0.7,
                action_mapping=target_action,
                training_data=training_signals,
                accuracy=0.95,  # 訓練時の精度
                created_at=datetime.now(timezone.utc),
                last_updated=datetime.now(timezone.utc)
            )

            self.thought_patterns[pattern_id] = pattern
            self.models[pattern_id] = model

            # ユーザープロファイルを更新
            if user_id not in self.user_profiles:
                self.user_profiles[user_id] = BCIProfile(
                    user_id=user_id,
                    baseline_signals={},
                    trained_patterns=[],
                    calibration_data={},
                    preferences={},
                    skill_level="beginner",
                    created_at=datetime.now(timezone.utc),
                    last_calibration=datetime.now(timezone.utc)
                )

            self.user_profiles[user_id].trained_patterns.append(pattern_id)
            self.user_profiles[user_id].last_calibration = datetime.now(timezone.utc)
            self.user_profiles[user_id].skill_level = self._update_skill_level(user_id)

            self.training_sessions += 1

            await self._save_user_profile(self.user_profiles[user_id])

            logger.info(f"Trained thought pattern: {pattern_id} ({pattern_type}) for user {user_id}")
            return pattern_id

        except Exception as e:
            logger.error(f"Thought pattern training failed: {e}")
            raise

    def _update_skill_level(self, user_id: str) -> str:
        """スキルレベルを更新"""
        if user_id not in self.user_profiles:
            return "beginner"

        profile = self.user_profiles[user_id]
        pattern_count = len(profile.trained_patterns)

        if pattern_count < 3:
            return "beginner"
        if pattern_count < 7:
            return "intermediate"
        if pattern_count < 12:
            return "advanced"
        return "expert"

    async def _save_user_profile(self, profile: BCIProfile):
        """ユーザープロファイルを保存"""
        profile_dir = self.bci_dir / "profiles"
        profile_dir.mkdir(parents=True, exist_ok=True)

        profile_data = {
            "user_id": profile.user_id,
            "baseline_signals": {k: v.tolist() for k, v in profile.baseline_signals.items()},
            "trained_patterns": profile.trained_patterns,
            "calibration_data": profile.calibration_data,
            "preferences": profile.preferences,
            "skill_level": profile.skill_level,
            "created_at": profile.created_at.isoformat(),
            "last_calibration": profile.last_calibration.isoformat()
        }

        profile_file = profile_dir / f"{profile.user_id}.json"
        with open(profile_file, 'w', encoding='utf-8') as f:  # noqa: ASYNC230
            json.dump(profile_data, f, indent=2, ensure_ascii=False)

    async def calibrate_bci_system(self, user_id: str, device_id: str,
                                 calibration_signals: List[BCISignal]) -> Dict[str, Any]:
        """
        BCIシステムをキャリブレーション

        Args:
            user_id: ユーザーID
            device_id: デバイスID
            calibration_signals: キャリブレーション信号

        Returns:
            キャリブレーション結果
        """
        try:
            # ベースライン信号を計算
            baseline_signals = {}
            for signal in calibration_signals:
                signal_type = signal.signal_type
                if signal_type not in baseline_signals:
                    baseline_signals[signal_type] = []

                features = self.eeg_processor.preprocess_eeg(signal)
                baseline_signals[signal_type].append(features)

            # 平均ベースラインを計算
            for signal_type, feature_list in baseline_signals.items():
                baseline_signals[signal_type] = np.mean(feature_list, axis=0)

            # ユーザープロファイルを作成・更新
            profile = BCIProfile(
                user_id=user_id,
                baseline_signals=baseline_signals,
                trained_patterns=[],
                calibration_data={
                    "device_id": device_id,
                    "calibration_date": datetime.now(timezone.utc).isoformat(),
                    "signal_count": len(calibration_signals),
                    "quality_scores": [s.quality_score for s in calibration_signals]
                },
                preferences={"sensitivity": "medium", "feedback": "visual"},
                skill_level="beginner",
                created_at=datetime.now(timezone.utc),
                last_calibration=datetime.now(timezone.utc)
            )

            self.user_profiles[user_id] = profile
            await self._save_user_profile(profile)

            # デバイスステータスを更新
            if device_id in self.connected_devices:
                self.connected_devices[device_id]["calibration_status"] = "completed"
                self.connected_devices[device_id]["calibration_date"] = datetime.now(timezone.utc)

            result = {
                "calibration_completed": True,
                "user_id": user_id,
                "baseline_recorded": len(baseline_signals),
                "average_quality": np.mean([s.quality_score for s in calibration_signals]),
                "recommended_patterns": ["movement", "attention", "relaxation"],
                "next_steps": ["train_movement_patterns", "test_real_time_recognition"]
            }

            logger.info(f"BCI calibration completed for user {user_id}")
            return result

        except Exception as e:
            logger.error(f"BCI calibration failed: {e}")
            return {"calibration_completed": False, "error": str(e)}

    def get_bci_status(self) -> Dict[str, Any]:
        """BCIステータスを取得"""
        return {
            "total_signals": self.total_signals,
            "processed_commands": self.processed_commands,
            "training_sessions": self.training_sessions,
            "connected_devices": len(self.connected_devices),
            "trained_patterns": len(self.thought_patterns),
            "user_profiles": len(self.user_profiles),
            "mne_available": MNE_AVAILABLE,
            "pyautogui_available": PYAUTOGUI_AVAILABLE,
            "realtime_processing": self.realtime_processing,
            "adaptive_learning": self.adaptive_learning,
            "calibration_required": self.calibration_required,
            "accuracy_trend": np.mean(self.accuracy_scores[-10:]) if self.accuracy_scores else 0.0,
            "devices": {
                device_id: {
                    "type": device_info["device_type"],
                    "status": device_info["status"],
                    "calibration": device_info["calibration_status"]
                }
                for device_id, device_info in self.connected_devices.items()
            }
        }

# グローバルインスタンス
_bci_manager = None

async def get_bci_manager() -> BCIManager:
    """BCIマネージャーのインスタンスを取得"""
    global _bci_manager

    if _bci_manager is None:
        _bci_manager = BCIManager()
        await _bci_manager.initialize()

    return _bci_manager
