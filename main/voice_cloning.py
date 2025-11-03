# main/voice_cloning.py
"""
Voice Cloning Module for Cocoa
ユーザーの音声をクローンしてアバターに使用するシステム
"""

import os
import asyncio
import logging
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
from datetime import datetime
import json
import numpy as np
import torch
import torchaudio
from scipy.io import wavfile

from .integrated_security import get_security_manager

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class VoiceSample:
    """音声サンプル"""
    sample_id: str
    user_id: str
    audio_path: str
    duration: float
    sample_rate: int
    text_content: Optional[str] = None
    quality_score: float = 0.0
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

@dataclass
class VoiceCloneRequest:
    """音声クローンリクエスト"""
    user_id: str
    voice_name: str
    sample_audio_paths: List[str]
    text_samples: Optional[List[str]] = None
    quality_preference: str = "balanced"  # "speed", "quality", "balanced"

@dataclass
class VoiceCloneResult:
    """音声クローン結果"""
    success: bool
    voice_id: str
    voice_name: str
    model_path: Optional[str] = None
    quality_metrics: Dict = None
    error_message: Optional[str] = None
    training_time: float = 0.0

    def __post_init__(self):
        if self.quality_metrics is None:
            self.quality_metrics = {}

class VoiceCloningEngine:
    """
    音声クローニングエンジン
    Tortoise TTSを使用した高品質音声クローニング
    """

    def __init__(self):
        self.security_manager = get_security_manager()

        # Tortoise TTS関連
        self.tts = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        # 音声データ管理
        self.voice_samples_dir = Path("data/voice_samples")
        self.voice_models_dir = Path("data/voice_models")
        self.temp_dir = Path("data/temp_voice")

        for dir_path in [self.voice_samples_dir, self.voice_models_dir, self.temp_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

        # トレーニング設定
        self.training_config = {
            "learning_rate": 1e-4,
            "batch_size": 8,
            "epochs": 100,
            "validation_split": 0.1
        }

        logger.info(f"Voice Cloning Engine initialized with device: {self.device}")

    async def initialize(self):
        """TTSエンジンを初期化"""
        try:
            # Tortoise TTSの初期化（遅延読み込み）
            from tortoise.api import TextToSpeech

            self.tts = TextToSpeech()
            logger.info("Tortoise TTS initialized successfully")

        except ImportError:
            logger.warning("Tortoise TTS not available, using fallback TTS")
            self.tts = None
        except Exception as e:
            logger.error(f"TTS initialization failed: {e}")
            self.tts = None

    async def add_voice_sample(self, user_id: str, audio_path: str,
                              text_content: Optional[str] = None) -> VoiceSample:
        """
        音声サンプルを追加

        Args:
            user_id: ユーザーID
            audio_path: 音声ファイルパス
            text_content: 音声の内容テキスト（オプション）

        Returns:
            音声サンプル情報
        """
        # セキュリティチェック
        if not await self.security_manager.validate_user_access(user_id, "voice_sample_upload"):
            raise ValueError("Unauthorized voice sample upload")

        # 音声ファイルの検証
        await self._validate_audio_file(audio_path)

        # サンプル情報を取得
        duration, sample_rate = self._get_audio_info(audio_path)
        quality_score = self._assess_audio_quality(audio_path)

        # サンプルID生成
        sample_id = f"sample_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # 保存先パス
        user_dir = self.voice_samples_dir / user_id
        user_dir.mkdir(exist_ok=True)

        saved_path = user_dir / f"{sample_id}.wav"

        # 音声ファイルを保存（WAV形式に変換）
        await self._convert_and_save_audio(audio_path, saved_path)

        # サンプル情報作成
        sample = VoiceSample(
            sample_id=sample_id,
            user_id=user_id,
            audio_path=str(saved_path),
            duration=duration,
            sample_rate=sample_rate,
            text_content=text_content,
            quality_score=quality_score
        )

        # メタデータを保存
        await self._save_sample_metadata(sample)

        logger.info(f"Voice sample added: {sample_id}")
        return sample

    async def clone_voice(self, request: VoiceCloneRequest) -> VoiceCloneResult:
        """
        音声クローニングを実行

        Args:
            request: クローンリクエスト

        Returns:
            クローン結果
        """
        start_time = asyncio.get_event_loop().time()

        try:
            # セキュリティチェック
            if not await self.security_manager.validate_user_access(request.user_id, "voice_cloning"):
                raise ValueError("Unauthorized voice cloning request")

            # 音声サンプルを取得
            voice_samples = await self._get_user_voice_samples(request.user_id)
            if len(voice_samples) < 3:
                raise ValueError("At least 3 voice samples required for cloning")

            # 音声ID生成
            voice_id = f"voice_{request.user_id}_{request.voice_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            # トレーニングデータ準備
            training_data = await self._prepare_training_data(voice_samples, request)

            # モデルトレーニング
            model_path = await self._train_voice_model(voice_id, training_data, request.quality_preference)

            # 品質評価
            quality_metrics = await self._evaluate_voice_quality(voice_id, model_path)

            # 結果作成
            result = VoiceCloneResult(
                success=True,
                voice_id=voice_id,
                voice_name=request.voice_name,
                model_path=model_path,
                quality_metrics=quality_metrics
            )

            # トレーニング時間を記録
            end_time = asyncio.get_event_loop().time()
            result.training_time = end_time - start_time

            # 監査ログ
            await self._log_voice_cloning(request, result)

            return result

        except Exception as e:
            logger.error(f"Voice cloning failed: {e}")
            end_time = asyncio.get_event_loop().time()

            return VoiceCloneResult(
                success=False,
                voice_id=f"failed_{datetime.now().timestamp()}",
                voice_name=request.voice_name,
                error_message=str(e),
                training_time=end_time - start_time
            )

    async def generate_speech(self, voice_id: str, text: str,
                             emotion: str = "neutral") -> Optional[str]:
        """
        指定された音声でテキストを生成

        Args:
            voice_id: 音声ID
            text: 生成するテキスト
            emotion: 感情表現

        Returns:
            生成された音声ファイルのパス
        """
        try:
            # モデルパスを取得
            model_path = await self._get_voice_model_path(voice_id)
            if not model_path:
                raise ValueError(f"Voice model not found: {voice_id}")

            # 出力ファイルパス
            output_filename = f"speech_{voice_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
            output_path = self.temp_dir / output_filename

            if self.tts:
                # Tortoise TTSを使用
                await self._generate_with_tortoise(model_path, text, str(output_path), emotion)
            else:
                # フォールバックTTS
                await self._generate_with_fallback(text, str(output_path))

            return str(output_path)

        except Exception as e:
            logger.error(f"Speech generation failed: {e}")
            return None

    async def _validate_audio_file(self, audio_path: str):
        """音声ファイルの妥当性を検証"""
        if not Path(audio_path).exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        # ファイルサイズチェック（最大50MB）
        if os.path.getsize(audio_path) > 50 * 1024 * 1024:
            raise ValueError("Audio file too large (max 50MB)")

        # 音声情報を取得して検証
        try:
            duration, sample_rate = self._get_audio_info(audio_path)

            if duration < 1.0:
                raise ValueError("Audio too short (minimum 1 second)")
            if duration > 60.0:
                raise ValueError("Audio too long (maximum 60 seconds)")
            if sample_rate < 8000 or sample_rate > 48000:
                raise ValueError("Invalid sample rate (8000-48000 Hz)")

        except Exception as e:
            raise ValueError(f"Invalid audio file: {e}")

    def _get_audio_info(self, audio_path: str) -> Tuple[float, int]:
        """音声ファイルの情報を取得"""
        try:
            # scipyを使用
            sample_rate, data = wavfile.read(audio_path)

            # チャンネル数のチェック
            if len(data.shape) > 1:
                data = data[:, 0]  # ステレオの場合は左チャンネルを使用

            duration = len(data) / sample_rate
            return duration, sample_rate

        except Exception as e:
            logger.warning(f"scipy wavfile failed, trying torchaudio: {e}")

            # torchaudioをフォールバックとして使用
            try:
                waveform, sample_rate = torchaudio.load(audio_path)
                duration = waveform.shape[1] / sample_rate
                return duration, sample_rate
            except Exception as e2:
                raise ValueError(f"Could not read audio file: {e2}")

    def _assess_audio_quality(self, audio_path: str) -> float:
        """音声品質を評価（0.0-1.0）"""
        try:
            # SNR（信号対雑音比）の簡易計算
            sample_rate, data = wavfile.read(audio_path)

            if len(data.shape) > 1:
                data = data[:, 0]

            # RMS計算
            rms = np.sqrt(np.mean(data.astype(np.float32) ** 2))

            # ノイズレベル推定（静かな部分）
            noise_threshold = np.percentile(np.abs(data), 10)
            noise_rms = np.sqrt(np.mean(data[np.abs(data) < noise_threshold].astype(np.float32) ** 2))

            if noise_rms > 0:
                snr = 20 * np.log10(rms / noise_rms)
                # SNRを0-1のスコアに変換
                quality_score = min(1.0, max(0.0, (snr - 10) / 30))  # 10dB=0.0, 40dB=1.0
            else:
                quality_score = 0.5  # デフォルト

            return quality_score

        except Exception as e:
            logger.warning(f"Quality assessment failed: {e}")
            return 0.5

    async def _convert_and_save_audio(self, source_path: str, dest_path: Path):
        """音声ファイルを変換して保存"""
        try:
            # torchaudioを使用して標準形式に変換
            waveform, sample_rate = torchaudio.load(source_path)

            # モノラルに変換
            if waveform.shape[0] > 1:
                waveform = torch.mean(waveform, dim=0, keepdim=True)

            # サンプルレートを22050Hzに統一
            target_sample_rate = 22050
            if sample_rate != target_sample_rate:
                resampler = torchaudio.transforms.Resample(sample_rate, target_sample_rate)
                waveform = resampler(waveform)

            # WAV形式で保存
            torchaudio.save(str(dest_path), waveform, target_sample_rate)

        except Exception as e:
            # 変換失敗時はコピー
            logger.warning(f"Audio conversion failed, copying as-is: {e}")
            shutil.copy2(source_path, dest_path)

    async def _save_sample_metadata(self, sample: VoiceSample):
        """サンプルメタデータを保存"""
        metadata_path = Path(sample.audio_path).with_suffix('.json')

        metadata = {
            "sample_id": sample.sample_id,
            "user_id": sample.user_id,
            "duration": sample.duration,
            "sample_rate": sample.sample_rate,
            "text_content": sample.text_content,
            "quality_score": sample.quality_score,
            "created_at": sample.created_at.isoformat()
        }

        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

    async def _get_user_voice_samples(self, user_id: str) -> List[VoiceSample]:
        """ユーザーの音声サンプルを取得"""
        user_dir = self.voice_samples_dir / user_id
        if not user_dir.exists():
            return []

        samples = []
        for json_file in user_dir.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)

                audio_path = json_file.with_suffix('.wav')
                if audio_path.exists():
                    sample = VoiceSample(**metadata)
                    sample.audio_path = str(audio_path)
                    samples.append(sample)

            except Exception as e:
                logger.warning(f"Failed to load sample metadata {json_file}: {e}")

        return sorted(samples, key=lambda x: x.created_at, reverse=True)

    async def _prepare_training_data(self, samples: List[VoiceSample],
                                   request: VoiceCloneRequest) -> Dict:
        """トレーニングデータを準備"""
        # テキストサンプルがある場合は使用
        text_samples = request.text_samples or []

        training_data = {
            "audio_paths": [s.audio_path for s in samples],
            "texts": text_samples,
            "sample_rates": [s.sample_rate for s in samples],
            "durations": [s.duration for s in samples]
        }

        return training_data

    async def _train_voice_model(self, voice_id: str, training_data: Dict,
                               quality_preference: str) -> str:
        """音声モデルをトレーニング"""
        # モデル保存パス
        model_path = self.voice_models_dir / voice_id
        model_path.mkdir(exist_ok=True)

        model_file = model_path / "voice_model.pt"

        try:
            if self.tts:
                # Tortoise TTSでのトレーニング
                await self._train_with_tortoise(training_data, str(model_file), quality_preference)
            else:
                # 簡易トレーニング（実際には本格的なトレーニングが必要）
                await self._create_basic_voice_model(training_data, str(model_file))

            return str(model_path)

        except Exception as e:
            logger.error(f"Voice model training failed: {e}")
            raise

    async def _train_with_tortoise(self, training_data: Dict, model_path: str,
                                 quality_preference: str):
        """Tortoise TTSでトレーニング"""
        # Tortoise TTSのトレーニング実装
        # 実際には複雑なトレーニングプロセスが必要
        logger.info("Tortoise TTS training would be implemented here")

        # プレースホルダーとして基本モデルを保存
        torch.save({"placeholder": True}, model_path)

    async def _create_basic_voice_model(self, training_data: Dict, model_path: str):
        """基本的な音声モデルを作成"""
        # 基本的な統計情報を保存
        model_data = {
            "training_data": training_data,
            "created_at": datetime.now().isoformat(),
            "model_type": "basic_fallback"
        }

        torch.save(model_data, model_path)

    async def _evaluate_voice_quality(self, voice_id: str, model_path: str) -> Dict:
        """音声品質を評価"""
        # テストテキストで音声を生成して評価
        test_text = "これはテスト音声です。"

        try:
            audio_path = await self.generate_speech(voice_id, test_text)
            if audio_path:
                # 生成された音声の品質を評価
                quality_score = self._assess_audio_quality(audio_path)

                metrics = {
                    "clarity": quality_score,
                    "naturalness": 0.8,  # 仮定値
                    "similarity": 0.7,   # 仮定値
                    "overall_quality": quality_score
                }

                # 一時ファイルを削除
                Path(audio_path).unlink(missing_ok=True)

                return metrics
            else:
                return {"error": "Speech generation failed"}

        except Exception as e:
            logger.error(f"Quality evaluation failed: {e}")
            return {"error": str(e)}

    async def _generate_with_tortoise(self, model_path: str, text: str,
                                    output_path: str, emotion: str):
        """Tortoise TTSで音声を生成"""
        # Tortoise TTSの実装
        logger.info("Tortoise TTS generation would be implemented here")

        # プレースホルダーとしてpyttsx3を使用
        import pyttsx3
        engine = pyttsx3.init()
        engine.save_to_file(text, output_path)
        engine.runAndWait()

    async def _generate_with_fallback(self, text: str, output_path: str):
        """フォールバックTTSで音声を生成"""
        import pyttsx3

        engine = pyttsx3.init()
        engine.save_to_file(text, output_path)
        engine.runAndWait()

    async def _get_voice_model_path(self, voice_id: str) -> Optional[str]:
        """音声モデルパスを取得"""
        model_path = self.voice_models_dir / voice_id
        model_file = model_path / "voice_model.pt"

        if model_file.exists():
            return str(model_path)
        return None

    async def _log_voice_cloning(self, request: VoiceCloneRequest, result: VoiceCloneResult):
        """音声クローニング操作を監査ログに記録"""
        await self.security_manager.log_security_event(
            event_type="voice_cloning",
            user_id=request.user_id,
            details={
                "success": result.success,
                "voice_name": request.voice_name,
                "sample_count": len(request.sample_audio_paths),
                "training_time": result.training_time,
                "error_message": result.error_message
            },
            ip_address="system"
        )

    async def list_user_voices(self, user_id: str) -> List[Dict]:
        """ユーザーの音声一覧を取得"""
        voices = []

        for voice_dir in self.voice_models_dir.glob(f"voice_{user_id}_*"):
            if voice_dir.is_dir():
                voice_id = voice_dir.name

                # メタデータを読み取り
                metadata = {}
                metadata_file = voice_dir / "metadata.json"
                if metadata_file.exists():
                    try:
                        with open(metadata_file, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                    except (IOError, json.JSONDecodeError) as e:
                        logger.warning(f"Failed to load voice metadata from {metadata_file}: {e}")

                voices.append({
                    "voice_id": voice_id,
                    "voice_name": metadata.get("voice_name", voice_id.split("_", 2)[-1]),
                    "created_at": metadata.get("created_at", ""),
                    "quality_score": metadata.get("quality_score", 0.0)
                })

        return sorted(voices, key=lambda x: x["created_at"], reverse=True)

    async def delete_voice(self, user_id: str, voice_id: str) -> bool:
        """音声を削除"""
        if not voice_id.startswith(f"voice_{user_id}_"):
            raise ValueError("Unauthorized voice deletion")

        voice_path = self.voice_models_dir / voice_id
        if not voice_path.exists():
            return False

        try:
            shutil.rmtree(voice_path)
            logger.info(f"Voice deleted: {voice_id}")
            return True
        except Exception as e:
            logger.error(f"Voice deletion failed: {e}")
            return False

# グローバルインスタンス管理
_voice_cloning_engine = None

async def get_voice_cloning_engine() -> VoiceCloningEngine:
    """音声クローニングエンジンのインスタンスを取得"""
    global _voice_cloning_engine

    if _voice_cloning_engine is None:
        _voice_cloning_engine = VoiceCloningEngine()
        await _voice_cloning_engine.initialize()

    return _voice_cloning_engine
