# main/emotional_intelligence.py
"""
Emotional Intelligence Module for Avatar System
ユーザーの感情を認識してアバターの対応を適応させる機能を提供
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

try:
    from transformers import pipeline
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

try:
    import face_recognition
    FACE_RECOGNITION_AVAILABLE = True
except ImportError:
    FACE_RECOGNITION_AVAILABLE = False

from integrated_security import get_security_manager

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class EmotionAnalysisRequest:
    """感情分析リクエスト"""
    user_id: str
    input_type: str  # "text", "image", "voice", "combined"
    input_data: Any
    context: Optional[str] = None
    previous_emotions: Optional[List[str]] = None

    def __post_init__(self):
        if self.previous_emotions is None:
            self.previous_emotions = []

@dataclass
class EmotionAnalysisResult:
    """感情分析結果"""
    success: bool
    primary_emotion: str
    emotion_scores: Dict[str, float]
    confidence: float
    adaptation_suggestions: List[str]
    context_aware_responses: Dict[str, str]
    processing_metadata: Dict = None
    error_message: Optional[str] = None

    def __post_init__(self):
        if self.processing_metadata is None:
            self.processing_metadata = {}

class EmotionRecognition:
    """感情認識機能"""

    def __init__(self):
        self.text_classifier = None
        self.face_emotion_detector = None
        self.voice_emotion_analyzer = None

    async def initialize(self):
        """感情認識モデルを初期化"""
        try:
            # テキスト感情分析モデル（実際はより高度なモデルを使用）
            self.text_classifier = pipeline(
                "text-classification",
                model="j-hartmann/emotion-english-distilroberta-base",
                return_all_scores=True
            )

            logger.info("Emotion recognition models initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize emotion recognition models: {e}")
            return False

    async def analyze_text_emotion(self, text: str) -> Dict[str, float]:
        """テキストから感情を分析"""
        try:
            if not self.text_classifier:
                await self.initialize()

            results = self.text_classifier(text)

            # 結果を辞書形式に変換
            emotion_scores = {}
            for result in results[0]:
                emotion_scores[result['label']] = result['score']

            return emotion_scores

        except Exception as e:
            logger.error(f"Text emotion analysis failed: {e}")
            return {}

    async def analyze_image_emotion(self, image_path: str) -> Dict[str, float]:
        """画像から感情を分析（顔認識ベース）"""
        try:
            # 実際の実装ではより高度な顔感情認識モデルを使用
            # ここでは簡易的な実装

            # 画像を読み込み
            image = face_recognition.load_image_file(image_path)
            face_locations = face_recognition.face_locations(image)

            if not face_locations:
                return {}

            # 顔の表情特徴を簡易的に分析（実際は深層学習モデルを使用）
            emotion_scores = {
                "joy": 0.5,
                "sadness": 0.2,
                "anger": 0.1,
                "fear": 0.1,
                "surprise": 0.1,
                "disgust": 0.0
            }

            return emotion_scores

        except Exception as e:
            logger.error(f"Image emotion analysis failed: {e}")
            return {}

    async def analyze_voice_emotion(self, audio_data: bytes) -> Dict[str, float]:
        """音声から感情を分析"""
        try:
            # 実際の実装では音声感情認識モデルを使用
            # ここでは簡易的な実装

            emotion_scores = {
                "joy": 0.6,
                "sadness": 0.1,
                "anger": 0.1,
                "fear": 0.1,
                "surprise": 0.1,
                "disgust": 0.0
            }

            return emotion_scores

        except Exception as e:
            logger.error(f"Voice emotion analysis failed: {e}")
            return {}

class EmotionalIntelligence:
    """
    感情認識と適応応答システム
    ユーザーの感情を認識してアバターの対応を適応させる
    """

    def __init__(self, models_dir: str = "data/models/emotional_intelligence"):
        """
        初期化

        Args:
            models_dir: モデル保存ディレクトリ
        """
        self.security_manager = get_security_manager()
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)

        # 感情認識器
        self.emotion_recognition = EmotionRecognition()

        # 感情ベースの応答パターン
        self.emotion_response_patterns = {
            "joy": {
                "tone": "enthusiastic",
                "expressions": ["happy", "excited", "cheerful"],
                "responses": [
                    "それは素晴らしいですね！とても嬉しそうです。",
                    "その笑顔を見ると私も幸せになります！",
                    "素晴らしい気分ですね！おめでとうございます。"
                ]
            },
            "sadness": {
                "tone": "empathetic",
                "expressions": ["concerned", "caring", "supportive"],
                "responses": [
                    "何かお手伝いできることはありますか？",
                    "辛い気持ち、よくわかります。一緒に乗り越えましょう。",
                    "今はつらい時期かもしれませんが、必ず良くなります。"
                ]
            },
            "anger": {
                "tone": "calm",
                "expressions": ["patient", "understanding", "composed"],
                "responses": [
                    "落ち着いて話しましょう。何かご不満な点がありますか？",
                    "お気持ち、よくわかります。まずは深呼吸しましょう。",
                    "何かお力になれることがあればお知らせください。"
                ]
            },
            "fear": {
                "tone": "reassuring",
                "expressions": ["calming", "protective", "gentle"],
                "responses": [
                    "大丈夫ですよ。一緒に解決しましょう。",
                    "心配しないでください。私がサポートします。",
                    "まずは落ち着いて、状況を整理しましょう。"
                ]
            },
            "surprise": {
                "tone": "excited",
                "expressions": ["surprised", "intrigued", "curious"],
                "responses": [
                    "わあ、驚きました！それはすごいですね。",
                    "予想外でした！興味深いお話ですね。",
                    "びっくりするような出来事があったんですね。"
                ]
            },
            "neutral": {
                "tone": "friendly",
                "expressions": ["neutral", "attentive", "engaging"],
                "responses": [
                    "お話、興味深く聞いています。",
                    "それでは詳しく教えていただけますか？",
                    "とても参考になります。ありがとうございます。"
                ]
            }
        }

        logger.info(f"Emotional Intelligence system initialized with models dir: {models_dir}")

    async def initialize_models(self):
        """感情認識モデルを初期化"""
        try:
            await self.emotion_recognition.initialize()

            logger.info("Emotional Intelligence models initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize emotional intelligence models: {e}")
            return False

    async def analyze_emotion(self, request: EmotionAnalysisRequest) -> EmotionAnalysisResult:
        """
        感情を分析して適応応答を生成

        Args:
            request: 分析リクエスト

        Returns:
            分析結果と適応応答
        """
        start_time = asyncio.get_event_loop().time()

        try:
            # セキュリティチェック
            await self._validate_request(request)

            # 入力タイプに応じて感情を分析
            emotion_scores = {}

            if request.input_type == "text":
                emotion_scores = await self.emotion_recognition.analyze_text_emotion(request.input_data)
            elif request.input_type == "image":
                emotion_scores = await self.emotion_recognition.analyze_image_emotion(request.input_data)
            elif request.input_type == "voice":
                emotion_scores = await self.emotion_recognition.analyze_voice_emotion(request.input_data)
            elif request.input_type == "combined":
                # 複数の入力タイプを統合して分析
                emotion_scores = await self._analyze_combined_emotion(request.input_data)

            if not emotion_scores:
                raise ValueError("Failed to analyze emotions from input")

            # 主要な感情を決定
            primary_emotion = max(emotion_scores, key=emotion_scores.get)

            # 信頼度を計算
            max_score = emotion_scores[primary_emotion]
            confidence = max_score

            # 適応応答を生成
            adaptation_suggestions = await self._generate_adaptation_suggestions(
                primary_emotion, emotion_scores, request
            )

            # 文脈を考慮した応答を生成
            context_aware_responses = await self._generate_context_responses(
                primary_emotion, request.context, request.previous_emotions
            )

            # 処理時間を計算
            processing_time = asyncio.get_event_loop().time() - start_time

            result = EmotionAnalysisResult(
                success=True,
                primary_emotion=primary_emotion,
                emotion_scores=emotion_scores,
                confidence=confidence,
                adaptation_suggestions=adaptation_suggestions,
                context_aware_responses=context_aware_responses,
                processing_metadata={
                    "input_type": request.input_type,
                    "primary_emotion": primary_emotion,
                    "confidence": confidence,
                    "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
                    "processing_time": processing_time
                }
            )

            # セキュリティログ
            await self.security_manager.log_security_event(
                event_type="emotion_analysis_performed",
                user_id=request.user_id,
                details={
                    "input_type": request.input_type,
                    "primary_emotion": primary_emotion,
                    "confidence": confidence,
                    "processing_time": processing_time
                }
            )

            return result

        except Exception as e:
            logger.error(f"Emotion analysis failed: {e}")
            processing_time = asyncio.get_event_loop().time() - start_time

            return EmotionAnalysisResult(
                success=False,
                primary_emotion="neutral",
                emotion_scores={},
                confidence=0.0,
                adaptation_suggestions=[],
                context_aware_responses={},
                processing_metadata={"processing_time": processing_time},
                error_message=str(e)
            )

    async def _validate_request(self, request: EmotionAnalysisRequest):
        """リクエストの妥当性を検証"""
        # ユーザー認証チェック
        if not await self.security_manager.validate_user_access(request.user_id, "emotion_analysis"):
            raise ValueError("Unauthorized emotion analysis request")

        # 入力データの検証
        if request.input_type == "text" and not request.input_data.strip():
            raise ValueError("Text input cannot be empty")

        if request.input_type == "image" and not Path(request.input_data).exists():
            raise FileNotFoundError(f"Image file not found: {request.input_data}")

        if request.input_type == "voice" and not request.input_data:
            raise ValueError("Voice data cannot be empty")

    async def _analyze_combined_emotion(self, input_data: Dict) -> Dict[str, float]:
        """複数の入力タイプを統合して感情を分析"""
        try:
            combined_scores = {}

            # 各入力タイプのスコアを統合
            for input_type, data in input_data.items():
                if input_type == "text":
                    scores = await self.emotion_recognition.analyze_text_emotion(data)
                elif input_type == "image":
                    scores = await self.emotion_recognition.analyze_image_emotion(data)
                elif input_type == "voice":
                    scores = await self.emotion_recognition.analyze_voice_emotion(data)
                else:
                    continue

                # スコアを統合（重み付け平均）
                weight = 0.4 if input_type == "text" else 0.3
                for emotion, score in scores.items():
                    combined_scores[emotion] = combined_scores.get(emotion, 0) + score * weight

            return combined_scores

        except Exception as e:
            logger.error(f"Combined emotion analysis failed: {e}")
            return {}

    async def _generate_adaptation_suggestions(self, primary_emotion: str, emotion_scores: Dict, request: EmotionAnalysisRequest) -> List[str]:
        """感情に基づく適応提案を生成"""
        suggestions = []

        # 感情パターンに基づく提案
        if primary_emotion == "joy":
            suggestions.extend([
                "明るく楽しいトーンで応答する",
                "ポジティブな表情を強調する",
                "励ましの言葉を交える"
            ])
        elif primary_emotion == "sadness":
            suggestions.extend([
                "共感を示す表現を使う",
                "落ち着いたトーンで話す",
                "サポートを提案する"
            ])
        elif primary_emotion == "anger":
            suggestions.extend([
                "冷静で忍耐強い態度を保つ",
                "問題解決を提案する",
                "感情を刺激しないよう注意する"
            ])
        elif primary_emotion == "fear":
            suggestions.extend([
                "安心させる言葉を使う",
                "穏やかな表情を保つ",
                "具体的な解決策を提案する"
            ])
        elif primary_emotion == "surprise":
            suggestions.extend([
                "興味を示す表現を使う",
                "好奇心を刺激する",
                "会話を活発に進める"
            ])

        # 感情の強さに基づく追加提案
        max_score = max(emotion_scores.values())
        if max_score > 0.8:
            suggestions.append("感情の強さが非常に高いため、特別な注意を払う")
        elif max_score < 0.3:
            suggestions.append("感情の強さが低いため、自然な対応を心がける")

        return suggestions

    async def _generate_context_responses(self, primary_emotion: str, context: Optional[str], previous_emotions: List[str]) -> Dict[str, str]:
        """文脈を考慮した応答を生成"""
        responses = {}

        # 感情パターンから応答を生成
        emotion_pattern = self.emotion_response_patterns.get(primary_emotion, self.emotion_response_patterns["neutral"])

        # 基本応答
        responses["immediate"] = np.random.choice(emotion_pattern["responses"])

        # 文脈を考慮した応答
        if context:
            if "質問" in context:
                responses["contextual"] = f"ご質問についてお答えします。{responses['immediate']}"
            elif "相談" in context:
                responses["contextual"] = f"ご相談の件ですね。{responses['immediate']}"
            else:
                responses["contextual"] = responses["immediate"]

        # 感情の連続性を考慮した応答
        if previous_emotions and len(previous_emotions) > 0:
            prev_emotion = previous_emotions[-1]
            if prev_emotion != primary_emotion:
                responses["transition"] = f"感情が{prev_emotion}から{primary_emotion}に変わりましたね。{responses.get('immediate', '')}"

        return responses

    async def get_emotion_patterns(self) -> Dict[str, Any]:
        """感情パターンの情報を取得"""
        return {
            "supported_emotions": list(self.emotion_response_patterns.keys()),
            "response_patterns": self.emotion_response_patterns,
            "analysis_capabilities": [
                "テキスト感情分析",
                "画像表情認識",
                "音声感情分析",
                "複合感情分析",
                "文脈適応応答生成"
            ]
        }

    async def adapt_avatar_behavior(self, emotion_result: EmotionAnalysisResult, avatar_id: str) -> Dict[str, Any]:
        """感情分析結果に基づいてアバターの挙動を適応"""
        try:
            adaptation = {
                "tone": self.emotion_response_patterns[emotion_result.primary_emotion]["tone"],
                "expression": np.random.choice(
                    self.emotion_response_patterns[emotion_result.primary_emotion]["expressions"]
                ),
                "response_style": "empathetic" if emotion_result.primary_emotion in ["sadness", "fear"] else "engaging",
                "engagement_level": "high" if emotion_result.confidence > 0.7 else "normal",
                "adaptation_timestamp": datetime.now(timezone.utc).isoformat()
            }

            return adaptation

        except Exception as e:
            logger.error(f"Avatar behavior adaptation failed: {e}")
            return {}

# グローバルインスタンス管理
_emotional_intelligence_instance = None

async def get_emotional_intelligence() -> EmotionalIntelligence:
    """感情認識システムのインスタンスを取得"""
    global _emotional_intelligence_instance

    if _emotional_intelligence_instance is None:
        _emotional_intelligence_instance = EmotionalIntelligence()
        await _emotional_intelligence_instance.initialize_models()

    return _emotional_intelligence_instance
