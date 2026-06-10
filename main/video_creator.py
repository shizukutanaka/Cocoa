# main/video_creator.py
"""
Video Creator Module for Cocoa
AIアバターを使用した動画自動生成システム
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
try:
    from moviepy.editor import AudioFileClip, CompositeVideoClip, TextClip
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False

from ai_avatar_generator import AvatarGenerationRequest, get_ai_avatar_generator
from integrated_security import get_security_manager

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class VideoCreationRequest:
    """動画作成リクエスト"""
    user_id: str
    script: str
    avatar_style: str = "professional"
    voice_settings: Dict[str, Union[str, int, float]] = None
    video_settings: Dict[str, Union[str, int, float]] = None
    background_music: Optional[str] = None
    output_format: str = "mp4"
    quality: str = "high"

    def __post_init__(self):
        if self.voice_settings is None:
            self.voice_settings = {"voice": "female", "speed": 1.0, "pitch": 0.0}
        if self.video_settings is None:
            self.video_settings = {"resolution": "1080p", "fps": 30, "duration": None}

@dataclass
class VideoCreationResult:
    """動画作成結果"""
    success: bool
    video_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    metadata: Dict = None
    error_message: Optional[str] = None
    creation_time: float = 0.0

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

class VoiceGenerator:
    """音声生成クラス"""

    def __init__(self):
        self.tts_engine = None  # TTSエンジン（pyttsx3や外部APIを使用）

    async def generate_voice(self, text: str, voice_settings: Dict) -> Tuple[str, float]:
        """
        テキストから音声を生成

        Args:
            text: 音声化するテキスト
            voice_settings: 音声設定

        Returns:
            (音声ファイルパス, 再生時間)
        """
        try:
            # 簡易的なTTS実装（実際にはpyttsx3や外部APIを使用）
            import pyttsx3

            if not self.tts_engine:
                self.tts_engine = pyttsx3.init()

            # 音声設定
            voices = self.tts_engine.getProperty('voices')
            if voice_settings.get('voice') == 'female' and len(voices) > 1:
                self.tts_engine.setProperty('voice', voices[1].id)
            elif voice_settings.get('voice') == 'male' and voices:
                self.tts_engine.setProperty('voice', voices[0].id)

            rate = self.tts_engine.getProperty('rate')
            self.tts_engine.setProperty('rate', int(rate * voice_settings.get('speed', 1.0)))

            # 音声ファイル生成
            audio_dir = Path("data/temp_audio")
            audio_dir.mkdir(parents=True, exist_ok=True)

            audio_filename = f"voice_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.wav"
            audio_path = audio_dir / audio_filename

            self.tts_engine.save_to_file(text, str(audio_path))
            self.tts_engine.runAndWait()

            # 再生時間を取得
            duration = self._get_audio_duration(str(audio_path))

            return str(audio_path), duration

        except Exception as e:
            logger.error(f"Voice generation failed: {e}")
            raise

    def _get_audio_duration(self, audio_path: str) -> float:
        """音声ファイルの再生時間を取得"""
        try:
            import wave
            with wave.open(audio_path, 'rb') as wav_file:
                frames = wav_file.getnframes()
                rate = wav_file.getframerate()
                return frames / float(rate)
        except (OSError, IOError, wave.Error) as e:
            # フォールバック: 文字数ベースの推定
            logger.warning(f"Failed to read audio duration from {audio_path}: {e}")
            return len(audio_path) * 0.1  # 簡易的な推定

class VideoCreator:
    """
    動画作成器
    AIアバターと音声を組み合わせて動画を生成
    """

    def __init__(self):
        self.security_manager = get_security_manager()
        self.avatar_generator = None
        self.voice_generator = VoiceGenerator()

        # 出力ディレクトリ
        self.output_dir = Path("data/videos")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 一時ファイルディレクトリ
        self.temp_dir = Path("data/temp_video")
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Video Creator initialized")

    async def initialize(self):
        """初期化"""
        if not self.avatar_generator:
            self.avatar_generator = await get_ai_avatar_generator()

    async def create_video(self, request: VideoCreationRequest) -> VideoCreationResult:
        """
        動画を作成

        Args:
            request: 動画作成リクエスト

        Returns:
            作成結果
        """
        start_time = asyncio.get_event_loop().time()

        try:
            # 初期化チェック
            if not self.avatar_generator:
                await self.initialize()

            # セキュリティチェック
            await self._validate_request(request)

            # スクリプトを文に分割
            sentences = self._split_script_into_sentences(request.script)

            # アバター画像生成
            avatar_paths = await self._generate_avatars_for_sentences(sentences, request)

            # 音声生成
            audio_path, total_duration = await self._generate_voice_for_script(request.script, request.voice_settings)

            # 動画合成
            video_path = await self._compose_video(
                avatar_paths, audio_path, sentences, request
            )

            # サムネイル生成
            thumbnail_path = await self._generate_thumbnail(video_path)

            # 後処理
            processed_result = VideoCreationResult(
                success=True,
                video_path=video_path,
                thumbnail_path=thumbnail_path,
                metadata={
                    "duration": total_duration,
                    "sentences_count": len(sentences),
                    "avatar_style": request.avatar_style,
                    "voice_settings": request.voice_settings,
                    "video_settings": request.video_settings,
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
            )

            # 作成時間を記録
            end_time = asyncio.get_event_loop().time()
            processed_result.creation_time = end_time - start_time

            # 監査ログ
            await self._log_video_creation(request, processed_result)

            # 一時ファイルクリーンアップ
            await self._cleanup_temp_files([audio_path] + list(avatar_paths.values()))

            return processed_result

        except Exception as e:
            logger.error(f"Video creation failed: {e}")
            end_time = asyncio.get_event_loop().time()

            # エラー時のクリーンアップ
            await self._cleanup_temp_files([])

            return VideoCreationResult(
                success=False,
                error_message=str(e),
                creation_time=end_time - start_time
            )

    async def _validate_request(self, request: VideoCreationRequest):
        """リクエストの妥当性を検証"""
        # ユーザー認証チェック
        if not await self.security_manager.validate_user_access(request.user_id, "video_creation"):
            raise ValueError("Unauthorized video creation request")

        # スクリプトチェック
        if not request.script or len(request.script.strip()) == 0:
            raise ValueError("Script cannot be empty")

        if len(request.script) > 10000:  # 10KB制限
            raise ValueError("Script too long (max 10000 characters)")

    def _split_script_into_sentences(self, script: str) -> List[str]:
        """スクリプトを文に分割"""
        import re

        # 文末の区切り文字で分割
        sentences = re.split(r'[。．！？\n]', script)
        sentences = [s.strip() for s in sentences if s.strip()]

        # 長すぎる文を分割
        max_length = 100
        final_sentences = []
        for sentence in sentences:
            if len(sentence) > max_length:
                # 単語単位で分割を試行
                words = sentence.split()
                current_chunk = ""
                for word in words:
                    if len(current_chunk + " " + word) > max_length:
                        if current_chunk:
                            final_sentences.append(current_chunk)
                        current_chunk = word
                    else:
                        current_chunk += " " + word if current_chunk else word
                if current_chunk:
                    final_sentences.append(current_chunk)
            else:
                final_sentences.append(sentence)

        return final_sentences

    async def _generate_avatars_for_sentences(self, sentences: List[str], request: VideoCreationRequest) -> Dict[str, str]:
        """各文に対応するアバターを生成"""
        avatar_paths = {}

        for i, sentence in enumerate(sentences):
            # アバター生成リクエスト作成
            avatar_request = AvatarGenerationRequest(
                user_id=request.user_id,
                prompt=f"{sentence}, speaking clearly",
                style=request.avatar_style,
                quality="high",
                customizations={
                    "expression": "speaking",
                    "context": f"sentence_{i+1}_of_{len(sentences)}"
                }
            )

            # アバター生成
            result = await self.avatar_generator.generate_avatar(avatar_request)

            if result.success:
                avatar_paths[sentence] = result.avatar_path
            else:
                logger.warning(f"Failed to generate avatar for sentence: {sentence}")
                # デフォルトのアバターを使用
                avatar_paths[sentence] = await self._get_default_avatar(request.avatar_style)

        return avatar_paths

    async def _generate_voice_for_script(self, script: str, voice_settings: Dict) -> Tuple[str, float]:
        """スクリプト全体の音声を生成"""
        return await self.voice_generator.generate_voice(script, voice_settings)

    async def _compose_video(self, avatar_paths: Dict[str, str], audio_path: str,
                           sentences: List[str], request: VideoCreationRequest) -> str:
        """動画を合成"""
        try:
            # 動画設定
            resolution = request.video_settings.get("resolution", "1080p")
            fps = request.video_settings.get("fps", 30)

            if resolution == "1080p":
                width, height = 1920, 1080
            elif resolution == "720p":
                width, height = 1280, 720
            else:
                width, height = 1920, 1080

            # 各文の表示時間を計算
            sentence_durations = self._calculate_sentence_durations(sentences, audio_path)

            # 動画クリップ作成
            video_clips = []
            current_time = 0

            for sentence, avatar_path in avatar_paths.items():
                duration = sentence_durations.get(sentence, 2.0)  # デフォルト2秒

                # アバター画像を動画クリップに変換
                avatar_clip = self._create_avatar_clip(avatar_path, duration, width, height)
                video_clips.append(avatar_clip.set_start(current_time))

                # 字幕追加
                subtitle_clip = self._create_subtitle_clip(sentence, current_time, duration, width, height)
                video_clips.append(subtitle_clip)

                current_time += duration

            # 音声クリップ
            audio_clip = AudioFileClip(audio_path)

            # 背景音楽追加（オプション）
            if request.background_music and Path(request.background_music).exists():
                bg_music = AudioFileClip(request.background_music).set_duration(audio_clip.duration)
                bg_music = bg_music.volumex(0.3)  # ボリュームを下げる
                audio_clip = CompositeVideoClip([audio_clip, bg_music])

            # 最終動画合成
            final_video = CompositeVideoClip(video_clips, size=(width, height))
            final_video = final_video.set_audio(audio_clip)
            final_video = final_video.set_duration(audio_clip.duration)

            # 出力ファイルパス
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            output_filename = f"avatar_video_{timestamp}.{request.output_format}"
            output_path = self.output_dir / output_filename

            # 動画書き出し
            final_video.write_videofile(
                str(output_path),
                fps=fps,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile=str(self.temp_dir / "temp_audio.m4a"),
                remove_temp=True,
                verbose=False,
                logger=None
            )

            return str(output_path)

        except Exception as e:
            logger.error(f"Video composition failed: {e}")
            raise

    def _calculate_sentence_durations(self, sentences: List[str], audio_path: str) -> Dict[str, float]:
        """各文の表示時間を計算"""
        try:
            # 音声の総時間を取得
            audio_duration = AudioFileClip(audio_path).duration

            # 文の長さに比例して時間を分配
            total_chars = sum(len(s) for s in sentences)
            durations = {}

            for sentence in sentences:
                # 文字数に基づく時間配分 + 最小時間保証
                char_ratio = len(sentence) / total_chars if total_chars > 0 else 1.0 / len(sentences)
                duration = max(audio_duration * char_ratio, 1.5)  # 最低1.5秒
                durations[sentence] = duration

            return durations

        except Exception as e:
            logger.warning(f"Duration calculation failed: {e}")
            # フォールバック: 等分
            default_duration = 2.0
            return dict.fromkeys(sentences, default_duration)

    def _create_avatar_clip(self, avatar_path: str, duration: float, width: int, height: int):
        """アバター画像から動画クリップを作成"""
        try:
            # 画像を読み込み
            avatar_image = Image.open(avatar_path)

            # アバターのサイズと位置を計算（画面中央、適切なサイズ）
            avatar_width = min(width // 2, 600)
            avatar_height = int(avatar_width * avatar_image.height / avatar_image.width)

            # リサイズ
            avatar_image = avatar_image.resize((avatar_width, avatar_height), Image.LANCZOS)

            # 位置を中央に
            x_pos = (width - avatar_width) // 2
            y_pos = (height - avatar_height) // 2

            # NumPy配列に変換
            avatar_array = np.array(avatar_image)

            # 動画クリップ作成（静止画を指定時間表示）
            from moviepy.video.VideoClip import ColorClip

            def make_frame(t):
                # 背景（黒）
                frame = np.zeros((height, width, 3), dtype=np.uint8)
                # アバターを配置
                frame[y_pos:y_pos+avatar_height, x_pos:x_pos+avatar_width] = avatar_array[:, :, :3]
                return frame

            clip = ColorClip(size=(width, height), color=(0,0,0), duration=duration)
            return clip.fl(make_frame)

        except Exception as e:
            logger.error(f"Avatar clip creation failed: {e}")
            # フォールバック: 黒いクリップ
            return ColorClip(size=(width, height), color=(0,0,0), duration=duration)

    def _create_subtitle_clip(self, text: str, start_time: float, duration: float,
                            width: int, height: int):
        """字幕クリップを作成"""
        try:
            # 字幕のスタイル設定
            fontsize = min(width // 40, 50)  # 画面サイズに応じたフォントサイズ

            # テキストクリップ作成
            txt_clip = TextClip(
                text,
                fontsize=fontsize,
                color='white',
                stroke_color='black',
                stroke_width=2,
                font='Arial-Bold'
            ).set_position(('center', height * 0.85)).set_duration(duration).set_start(start_time)

            return txt_clip

        except Exception as e:
            logger.warning(f"Subtitle creation failed: {e}")
            return TextClip("", fontsize=1, color='white').set_duration(duration).set_start(start_time)

    async def _generate_thumbnail(self, video_path: str) -> str:
        """動画のサムネイルを生成"""
        try:
            from moviepy.editor import VideoFileClip

            clip = VideoFileClip(video_path)
            thumbnail_time = min(1.0, clip.duration * 0.1)  # 動画の10%地点

            # サムネイル画像を取得
            thumbnail_image = clip.get_frame(thumbnail_time)

            # PIL画像に変換
            thumbnail_pil = Image.fromarray(thumbnail_image)

            # サムネイル保存
            thumbnail_path = video_path.replace('.mp4', '_thumb.jpg')
            thumbnail_pil.save(thumbnail_path, 'JPEG', quality=85)

            clip.close()

            return thumbnail_path

        except Exception as e:
            logger.warning(f"Thumbnail generation failed: {e}")
            return None

    async def _get_default_avatar(self, style: str) -> str:
        """デフォルトのアバター画像を取得"""
        # スタイルに応じたデフォルト画像を返す
        default_dir = Path("data/default_avatars")
        default_dir.mkdir(parents=True, exist_ok=True)

        default_path = default_dir / f"default_{style}.png"

        if default_path.exists():
            return str(default_path)

        # デフォルト画像が存在しない場合は新規作成
        try:
            request = AvatarGenerationRequest(
                user_id="system",
                prompt=f"default avatar in {style} style",
                style=style,
                quality="standard"
            )

            result = await self.avatar_generator.generate_avatar(request)
            if result.success:
                # デフォルトとして保存
                import shutil
                shutil.copy2(result.avatar_path, default_path)
                return str(default_path)

        except Exception as e:
            logger.error(f"Default avatar creation failed: {e}")

        # 最終フォールバック: 黒い画像
        fallback_image = Image.new('RGB', (512, 512), color='black')
        fallback_path = default_dir / "fallback.png"
        fallback_image.save(fallback_path)
        return str(fallback_path)

    async def _log_video_creation(self, request: VideoCreationRequest, result: VideoCreationResult):
        """動画作成操作を監査ログに記録"""
        await self.security_manager.log_security_event(
            event_type="video_creation",
            user_id=request.user_id,
            details={
                "success": result.success,
                "script_length": len(request.script),
                "avatar_style": request.avatar_style,
                "creation_time": result.creation_time,
                "error_message": result.error_message
            },
            ip_address="system"
        )

    async def _cleanup_temp_files(self, files_to_keep: List[str] = None):
        """一時ファイルをクリーンアップ"""
        try:
            if files_to_keep is None:
                files_to_keep = []

            keep_set = set(files_to_keep)

            # temp_audio内の古いファイルを削除
            audio_dir = Path("data/temp_audio")
            if audio_dir.exists():
                for file_path in audio_dir.glob("*"):
                    if str(file_path) not in keep_set:
                        try:
                            file_path.unlink()
                        except (OSError, PermissionError) as e:
                            logger.debug(f"Failed to remove temp audio file {file_path}: {e}")

            # temp_video内の古いファイルを削除
            for file_path in self.temp_dir.glob("*"):
                if str(file_path) not in keep_set:
                    try:
                        file_path.unlink()
                    except (OSError, PermissionError) as e:
                        logger.debug(f"Failed to remove temp video file {file_path}: {e}")

        except Exception as e:
            logger.warning(f"Temp file cleanup failed: {e}")

# グローバルインスタンス管理
_video_creator_instance = None

async def get_video_creator() -> VideoCreator:
    """動画作成器のインスタンスを取得"""
    global _video_creator_instance

    if _video_creator_instance is None:
        _video_creator_instance = VideoCreator()
        await _video_creator_instance.initialize()

    return _video_creator_instance
