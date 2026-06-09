# main/avatar_personality_tuner.py
"""
Avatar Personality Tuner Module for Cocoa
ユーザーの話し方・表情を分析して自然なアバター動作を最適化
"""

import logging
import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timezone
import statistics

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

from integrated_security import get_security_manager

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class PersonalityProfile:
    """パーソナリティプロファイル"""
    user_id: str
    speaking_style: Dict[str, Any] = None
    emotional_expression: Dict[str, Any] = None
    gesture_patterns: Dict[str, Any] = None
    facial_expressions: Dict[str, Any] = None
    voice_characteristics: Dict[str, Any] = None
    confidence_score: float = 0.0
    samples_analyzed: int = 0
    last_updated: datetime = None

    def __post_init__(self):
        if self.speaking_style is None:
            self.speaking_style = {}
        if self.emotional_expression is None:
            self.emotional_expression = {}
        if self.gesture_patterns is None:
            self.gesture_patterns = {}
        if self.facial_expressions is None:
            self.facial_expressions = {}
        if self.voice_characteristics is None:
            self.voice_characteristics = {}
        if self.last_updated is None:
            self.last_updated = datetime.now(timezone.utc)

@dataclass
class BehaviorSample:
    """行動サンプル"""
    sample_id: str
    user_id: str
    content_type: str  # 'speech', 'text', 'video', 'audio'
    content: str
    analysis_results: Dict[str, Any] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.analysis_results is None:
            self.analysis_results = {}
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)

@dataclass
class TunedAvatarConfig:
    """調整済みアバター設定"""
    user_id: str
    base_avatar_id: str
    personality_profile: PersonalityProfile
    optimized_settings: Dict[str, Any] = None
    performance_metrics: Dict[str, Any] = None
    created_at: datetime = None

    def __post_init__(self):
        if self.optimized_settings is None:
            self.optimized_settings = {}
        if self.performance_metrics is None:
            self.performance_metrics = {}
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)

class PersonalityAnalyzer:
    """
    パーソナリティ分析器
    ユーザーの話し方・表情・行動を分析
    """

    def __init__(self):
        # 感情分析の基本パラメータ
        self.emotion_keywords = {
            'happy': ['嬉しい', '楽しい', '素晴らしい', '最高', '笑', '喜'],
            'sad': ['悲しい', '辛い', '寂しい', '残念', '泣', '涙'],
            'angry': ['怒', 'イライラ', '腹立', '嫌', '憎', '激怒'],
            'surprised': ['驚', 'びっくり', '意外', '信じられない', 'すごい'],
            'fearful': ['怖い', '恐ろしい', '不安', '心配', '怯え'],
            'disgusted': ['嫌悪', '不快', '気持ち悪い', '吐き気'],
            'neutral': ['普通', 'まあまあ', '普通', '平凡']
        }

        # 話し方の特徴分析
        self.speech_patterns = {
            'formal': ['です', 'ます', 'ございます', 'いたします', 'させていただきます'],
            'casual': ['だよ', 'だね', 'じゃん', 'かも', 'かな', 'だぜ'],
            'enthusiastic': ['！', '！！', '!!!', 'すごく', 'とても', '大変'],
            'reserved': ['ちょっと', '少し', '多少', '控えめに', '慎重に'],
            'confident': ['確か', '間違いなく', '自信を持って', '断言', '確信'],
            'hesitant': ['かもしれない', 'かも', 'と思う', 'でしょうか', 'かな']
        }

    async def analyze_speech_content(self, text: str) -> Dict[str, Any]:
        """テキスト内容を分析"""
        analysis = {
            'emotion_scores': {},
            'speech_style_scores': {},
            'sentiment_score': 0.0,
            'complexity_score': 0.0,
            'confidence_score': 0.0,
            'keywords': []
        }

        # 感情分析
        total_emotion_score = 0
        for emotion, keywords in self.emotion_keywords.items():
            score = sum(1 for keyword in keywords if keyword in text)
            analysis['emotion_scores'][emotion] = score
            total_emotion_score += score

        # 感情強度正規化
        if total_emotion_score > 0:
            for emotion in analysis['emotion_scores']:
                analysis['emotion_scores'][emotion] /= total_emotion_score

        # 話し方スタイル分析
        for style, patterns in self.speech_patterns.items():
            score = sum(1 for pattern in patterns if pattern in text)
            analysis['speech_style_scores'][style] = score

        # 感情スコア計算（簡易版）
        positive_words = ['良い', '素晴らしい', '嬉しい', '楽しい', '好き', '満足']
        negative_words = ['悪い', '最悪', '悲しい', '辛い', '嫌い', '不満']

        positive_score = sum(1 for word in positive_words if word in text)
        negative_score = sum(1 for word in negative_words if word in text)

        analysis['sentiment_score'] = (positive_score - negative_score) / max(len(text.split()), 1)

        # 複雑さスコア（文長と語彙の多様性）
        sentences = text.split('。')
        avg_sentence_length = statistics.mean([len(s) for s in sentences]) if sentences else 0
        unique_words = len(set(text.split()))
        total_words = len(text.split())

        analysis['complexity_score'] = (avg_sentence_length * 0.3 + unique_words / max(total_words, 1) * 0.7)

        # 自信度スコア（断定表現の割合）
        confident_patterns = ['です', 'ます', 'である', 'だ', 'た', 'でした']
        confident_count = sum(1 for pattern in confident_patterns if pattern in text)
        analysis['confidence_score'] = confident_count / max(len(text.split()), 1)

        # キーワード抽出
        analysis['keywords'] = [word for word in text.split() if len(word) > 1][:10]

        return analysis

    async def analyze_audio_characteristics(self, audio_data: Optional[bytes] = None,
                                          audio_path: Optional[str] = None) -> Dict[str, Any]:
        """音声特性を分析"""
        analysis = {
            'pitch_range': {'min': 0, 'max': 0, 'average': 0},
            'speaking_rate': 0.0,  # words per minute
            'pause_patterns': [],
            'volume_variation': 0.0,
            'tone_stability': 0.0,
            'accent_detection': 'neutral'
        }

        # 簡易的な分析（実際には音声処理ライブラリを使用）
        if audio_path and Path(audio_path).exists():
            try:
                # 簡易推定: 平均話速150WPM
                analysis['speaking_rate'] = 150 * (1 + np.random.normal(0, 0.1))  # 簡易乱数

                # ピッチ範囲推定
                analysis['pitch_range'] = {
                    'min': 80 + np.random.normal(0, 10),
                    'max': 200 + np.random.normal(0, 20),
                    'average': 140 + np.random.normal(0, 15)
                }

                analysis['tone_stability'] = 0.7 + np.random.normal(0, 0.1)
                analysis['volume_variation'] = 0.6 + np.random.normal(0, 0.1)

            except Exception as e:
                logger.warning(f"Audio analysis failed: {e}")

        return analysis

    async def analyze_behavior_patterns(self, samples: List[BehaviorSample]) -> Dict[str, Any]:
        """行動パターンを分析"""
        if not samples:
            return {}

        analysis = {
            'consistency_score': 0.0,
            'adaptability_score': 0.0,
            'communication_style': {},
            'preferred_content_types': {},
            'temporal_patterns': {}
        }

        # 一貫性スコア計算
        if len(samples) > 1:
            # 感情の一貫性を分析
            emotions = []
            for sample in samples:
                if 'emotion' in sample.analysis_results:
                    emotions.append(sample.analysis_results['emotion'])

            if emotions:
                # 感情の標準偏差が小さいほど一貫性が高い
                try:
                    emotion_std = statistics.stdev(emotions) if len(emotions) > 1 else 0
                    analysis['consistency_score'] = max(0, 1.0 - emotion_std)
                except (ValueError, ZeroDivisionError) as e:
                    logger.warning(f"Failed to calculate emotion consistency: {e}")
                    analysis['consistency_score'] = 0.5

        # 適応性スコア（多様な感情表現）
        unique_emotions = len(set(sample.analysis_results.get('primary_emotion', 'neutral')
                                for sample in samples))
        analysis['adaptability_score'] = min(1.0, unique_emotions / 7.0)  # 7つの基本感情

        # コミュニケーションスタイル分析
        styles = {}
        for sample in samples:
            style = sample.analysis_results.get('communication_style', 'neutral')
            styles[style] = styles.get(style, 0) + 1

        analysis['communication_style'] = styles

        # コンテンツタイプ分析
        content_types = {}
        for sample in samples:
            content_types[sample.content_type] = content_types.get(sample.content_type, 0) + 1

        analysis['preferred_content_types'] = content_types

        return analysis

class AvatarPersonalityTuner:
    """
    アバターパーソナリティチューナー
    ユーザーの特性に合わせてアバターを最適化
    """

    def __init__(self):
        self.security_manager = get_security_manager()
        self.analyzer = PersonalityAnalyzer()

        # データベース
        self.db_path = Path("data/avatar_personality.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # プロファイルストレージ
        self.profiles: Dict[str, PersonalityProfile] = {}
        self.tuned_configs: Dict[str, TunedAvatarConfig] = {}

        logger.info("Avatar Personality Tuner initialized")

    async def initialize(self):
        """初期化"""
        # データベース初期化
        await self._init_database()

        # 保存されたプロファイルを読み込み
        await self._load_profiles()

    async def _init_database(self):
        """データベース初期化"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            # パーソナリティプロファイルテーブル
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS personality_profiles (
                    user_id TEXT PRIMARY KEY,
                    speaking_style TEXT NOT NULL,
                    emotional_expression TEXT NOT NULL,
                    gesture_patterns TEXT NOT NULL,
                    facial_expressions TEXT NOT NULL,
                    voice_characteristics TEXT NOT NULL,
                    confidence_score REAL DEFAULT 0.0,
                    samples_analyzed INTEGER DEFAULT 0,
                    last_updated TEXT
                )
            ''')

            # 行動サンプルテーブル
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS behavior_samples (
                    sample_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    analysis_results TEXT,
                    timestamp TEXT
                )
            ''')

            # 調整済みアバター設定テーブル
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tuned_avatar_configs (
                    user_id TEXT PRIMARY KEY,
                    base_avatar_id TEXT NOT NULL,
                    personality_profile TEXT NOT NULL,
                    optimized_settings TEXT NOT NULL,
                    performance_metrics TEXT,
                    created_at TEXT
                )
            ''')

            # インデックス作成
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_behavior_samples_user_id ON behavior_samples(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_behavior_samples_timestamp ON behavior_samples(timestamp)')

            conn.commit()

    async def _load_profiles(self):
        """プロファイルを読み込み"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM personality_profiles')
            rows = cursor.fetchall()

            for row in rows:
                profile = PersonalityProfile(
                    user_id=row[0],
                    speaking_style=json.loads(row[1]),
                    emotional_expression=json.loads(row[2]),
                    gesture_patterns=json.loads(row[3]),
                    facial_expressions=json.loads(row[4]),
                    voice_characteristics=json.loads(row[5]),
                    confidence_score=row[6],
                    samples_analyzed=row[7],
                    last_updated=datetime.fromisoformat(row[8])
                )
                self.profiles[row[0]] = profile

    async def add_behavior_sample(self, user_id: str, content_type: str,
                                content: str, additional_data: Optional[Dict] = None) -> str:
        """
        行動サンプルを追加

        Args:
            user_id: ユーザーID
            content_type: コンテンツタイプ
            content: コンテンツ内容
            additional_data: 追加データ

        Returns:
            サンプルID
        """
        sample_id = f"sample_{user_id}_{int(datetime.now(timezone.utc).timestamp() * 1000)}"

        # コンテンツ分析
        analysis_results = await self._analyze_content(content_type, content, additional_data)

        # サンプル作成
        sample = BehaviorSample(
            sample_id=sample_id,
            user_id=user_id,
            content_type=content_type,
            content=content,
            analysis_results=analysis_results
        )

        # データベース保存
        await self._save_behavior_sample(sample)

        # プロファイル更新
        await self._update_personality_profile(user_id, sample)

        return sample_id

    async def _analyze_content(self, content_type: str, content: str,
                             additional_data: Optional[Dict]) -> Dict[str, Any]:
        """コンテンツを分析"""
        analysis = {}

        if content_type in ['speech', 'text']:
            # テキスト分析
            text_analysis = await self.analyzer.analyze_speech_content(content)
            analysis.update(text_analysis)

            # 主要感情判定
            emotion_scores = analysis.get('emotion_scores', {})
            if emotion_scores:
                primary_emotion = max(emotion_scores.items(), key=lambda x: x[1])[0]
                analysis['primary_emotion'] = primary_emotion

            # コミュニケーションスタイル判定
            style_scores = analysis.get('speech_style_scores', {})
            if style_scores:
                primary_style = max(style_scores.items(), key=lambda x: x[1])[0]
                analysis['communication_style'] = primary_style

        elif content_type == 'audio':
            # 音声分析
            audio_analysis = await self.analyzer.analyze_audio_characteristics(
                audio_path=additional_data.get('audio_path') if additional_data else None
            )
            analysis.update(audio_analysis)

        elif content_type == 'video':
            # ビデオ分析（テキスト + 音声）
            if 'transcript' in additional_data:
                text_analysis = await self.analyzer.analyze_speech_content(additional_data['transcript'])
                analysis.update(text_analysis)

            if 'audio_path' in additional_data:
                audio_analysis = await self.analyzer.analyze_audio_characteristics(
                    audio_path=additional_data['audio_path']
                )
                analysis.update(audio_analysis)

        return analysis

    async def _save_behavior_sample(self, sample: BehaviorSample):
        """行動サンプルを保存"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO behavior_samples
                (sample_id, user_id, content_type, content, analysis_results, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                sample.sample_id,
                sample.user_id,
                sample.content_type,
                sample.content,
                json.dumps(sample.analysis_results, ensure_ascii=False),
                sample.timestamp.isoformat()
            ))

            conn.commit()

    async def _update_personality_profile(self, user_id: str, new_sample: BehaviorSample):
        """パーソナリティプロファイルを更新"""
        # 既存プロファイル取得または新規作成
        if user_id not in self.profiles:
            self.profiles[user_id] = PersonalityProfile(user_id=user_id)

        # 全てのサンプルを取得
        samples = await self._get_user_behavior_samples(user_id)
        samples.append(new_sample)

        # プロファイル更新
        updated_profile = await self._calculate_personality_profile(user_id, samples)

        # 保存
        self.profiles[user_id] = updated_profile
        await self._save_personality_profile(updated_profile)

    async def _get_user_behavior_samples(self, user_id: str) -> List[BehaviorSample]:
        """ユーザーの行動サンプルを取得"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT sample_id, user_id, content_type, content, analysis_results, timestamp
                FROM behavior_samples
                WHERE user_id = ?
                ORDER BY timestamp DESC
                LIMIT 100
            ''', (user_id,))

            samples = []
            for row in cursor.fetchall():
                samples.append(BehaviorSample(
                    sample_id=row[0],
                    user_id=row[1],
                    content_type=row[2],
                    content=row[3],
                    analysis_results=json.loads(row[4]) if row[4] else {},
                    timestamp=datetime.fromisoformat(row[5])
                ))

            return samples

    async def _calculate_personality_profile(self, user_id: str,
                                          samples: List[BehaviorSample]) -> PersonalityProfile:
        """パーソナリティプロファイルを計算"""
        profile = PersonalityProfile(user_id=user_id, samples_analyzed=len(samples))

        if not samples:
            return profile

        # 話し方の特徴を集計
        speaking_styles = {}
        emotional_expressions = {}
        gesture_patterns = {}
        facial_expressions = {}
        voice_characteristics = {}

        for sample in samples:
            analysis = sample.analysis_results

            # 話し方スタイル
            style = analysis.get('communication_style', 'neutral')
            speaking_styles[style] = speaking_styles.get(style, 0) + 1

            # 感情表現
            emotion = analysis.get('primary_emotion', 'neutral')
            emotional_expressions[emotion] = emotional_expressions.get(emotion, 0) + 1

            # ジェスチャーパターン（簡易）
            gesture_patterns['frequency'] = gesture_patterns.get('frequency', 0) + 1

            # 表情パターン
            confidence = analysis.get('confidence_score', 0.5)
            facial_expressions['confidence'] = facial_expressions.get('confidence', []) + [confidence]

            # 音声特性
            if 'speaking_rate' in analysis:
                voice_characteristics['speaking_rates'] = voice_characteristics.get('speaking_rates', []) + [analysis['speaking_rate']]

        # 平均値計算
        profile.speaking_style = speaking_styles
        profile.emotional_expression = emotional_expressions
        profile.gesture_patterns = gesture_patterns

        if facial_expressions.get('confidence'):
            profile.facial_expressions = {
                'average_confidence': statistics.mean(facial_expressions['confidence'])
            }

        if voice_characteristics.get('speaking_rates'):
            profile.voice_characteristics = {
                'average_speaking_rate': statistics.mean(voice_characteristics['speaking_rates'])
            }

        # 信頼度スコア計算
        profile.confidence_score = min(1.0, len(samples) / 10.0)  # 10サンプルで信頼度1.0
        profile.last_updated = datetime.now(timezone.utc)

        return profile

    async def _save_personality_profile(self, profile: PersonalityProfile):
        """パーソナリティプロファイルを保存"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                INSERT OR REPLACE INTO personality_profiles
                (user_id, speaking_style, emotional_expression, gesture_patterns,
                 facial_expressions, voice_characteristics, confidence_score,
                 samples_analyzed, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                profile.user_id,
                json.dumps(profile.speaking_style, ensure_ascii=False),
                json.dumps(profile.emotional_expression, ensure_ascii=False),
                json.dumps(profile.gesture_patterns, ensure_ascii=False),
                json.dumps(profile.facial_expressions, ensure_ascii=False),
                json.dumps(profile.voice_characteristics, ensure_ascii=False),
                profile.confidence_score,
                profile.samples_analyzed,
                profile.last_updated.isoformat()
            ))

            conn.commit()

    async def tune_avatar_for_user(self, user_id: str, base_avatar_id: str) -> TunedAvatarConfig:
        """
        ユーザーに合わせてアバターを調整

        Args:
            user_id: ユーザーID
            base_avatar_id: ベースアバターID

        Returns:
            調整済みアバター設定
        """
        # パーソナリティプロファイル取得
        profile = self.profiles.get(user_id)
        if not profile or profile.confidence_score < 0.3:
            # プロファイルが不十分な場合はデフォルト設定
            profile = PersonalityProfile(user_id=user_id)

        # 最適化設定を計算
        optimized_settings = await self._calculate_optimized_settings(profile)

        # アバター設定作成
        tuned_config = TunedAvatarConfig(
            user_id=user_id,
            base_avatar_id=base_avatar_id,
            personality_profile=profile,
            optimized_settings=optimized_settings
        )

        # 保存
        self.tuned_configs[user_id] = tuned_config
        await self._save_tuned_config(tuned_config)

        return tuned_config

    async def _calculate_optimized_settings(self, profile: PersonalityProfile) -> Dict[str, Any]:
        """最適化設定を計算"""
        settings = {
            'gesture_amplitude': 1.0,
            'facial_expression_intensity': 1.0,
            'speaking_rate_multiplier': 1.0,
            'emotional_responsiveness': 1.0,
            'confidence_display': 1.0
        }

        # パーソナリティに基づく調整

        # 話し方スタイルによる調整
        speaking_style = profile.speaking_style
        if speaking_style:
            max_style = max(speaking_style.items(), key=lambda x: x[1])[0]

            if max_style == 'enthusiastic':
                settings['gesture_amplitude'] = 1.3
                settings['facial_expression_intensity'] = 1.2
            elif max_style == 'reserved':
                settings['gesture_amplitude'] = 0.8
                settings['facial_expression_intensity'] = 0.9
            elif max_style == 'confident':
                settings['confidence_display'] = 1.2

        # 感情表現による調整
        emotional_expression = profile.emotional_expression
        if emotional_expression:
            max_emotion = max(emotional_expression.items(), key=lambda x: x[1])[0]

            if max_emotion == 'happy':
                settings['facial_expression_intensity'] = 1.1
                settings['emotional_responsiveness'] = 1.2
            elif max_emotion == 'sad':
                settings['facial_expression_intensity'] = 0.9
                settings['emotional_responsiveness'] = 1.1

        # 音声特性による調整
        voice_characteristics = profile.voice_characteristics
        if voice_characteristics and 'average_speaking_rate' in voice_characteristics:
            speaking_rate = voice_characteristics['average_speaking_rate']
            # 平均話速150WPMを基準に調整
            settings['speaking_rate_multiplier'] = speaking_rate / 150.0

        # 表情特性による調整
        facial_expressions = profile.facial_expressions
        if facial_expressions and 'average_confidence' in facial_expressions:
            confidence = facial_expressions['average_confidence']
            settings['confidence_display'] = confidence * 1.5  # 強調

        return settings

    async def _save_tuned_config(self, config: TunedAvatarConfig):
        """調整済み設定を保存"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                INSERT OR REPLACE INTO tuned_avatar_configs
                (user_id, base_avatar_id, personality_profile, optimized_settings,
                 performance_metrics, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                config.user_id,
                config.base_avatar_id,
                json.dumps({
                    'confidence_score': config.personality_profile.confidence_score,
                    'samples_analyzed': config.personality_profile.samples_analyzed
                }, ensure_ascii=False),
                json.dumps(config.optimized_settings, ensure_ascii=False),
                json.dumps(config.performance_metrics, ensure_ascii=False),
                config.created_at.isoformat()
            ))

            conn.commit()

    async def get_tuned_config(self, user_id: str) -> Optional[TunedAvatarConfig]:
        """調整済み設定を取得"""
        return self.tuned_configs.get(user_id)

    async def get_personality_profile(self, user_id: str) -> Optional[PersonalityProfile]:
        """パーソナリティプロファイルを取得"""
        return self.profiles.get(user_id)

    async def generate_personality_report(self, user_id: str) -> Dict[str, Any]:
        """パーソナリティレポートを生成"""
        profile = await self.get_personality_profile(user_id)
        tuned_config = await self.get_tuned_config(user_id)

        if not profile:
            return {"error": "No personality profile found"}

        report = {
            "user_id": user_id,
            "analysis_date": datetime.now(timezone.utc).isoformat(),
            "confidence_score": profile.confidence_score,
            "samples_analyzed": profile.samples_analyzed,
            "speaking_style": profile.speaking_style,
            "emotional_expression": profile.emotional_expression,
            "facial_expressions": profile.facial_expressions,
            "voice_characteristics": profile.voice_characteristics,
            "last_updated": profile.last_updated.isoformat()
        }

        if tuned_config:
            report["optimized_settings"] = tuned_config.optimized_settings
            report["performance_metrics"] = tuned_config.performance_metrics

        # インサイト生成
        insights = []
        if profile.confidence_score > 0.7:
            insights.append("パーソナリティ分析の信頼性が高いです。")
        else:
            insights.append("より多くのサンプルを追加することで分析精度が向上します。")

        speaking_style = profile.speaking_style
        if speaking_style:
            dominant_style = max(speaking_style.items(), key=lambda x: x[1])[0]
            insights.append(f"主な話し方スタイル: {dominant_style}")

        emotional_expression = profile.emotional_expression
        if emotional_expression:
            dominant_emotion = max(emotional_expression.items(), key=lambda x: x[1])[0]
            insights.append(f"主な感情表現: {dominant_emotion}")

        report["insights"] = insights

        return report

# グローバルインスタンス管理
_avatar_personality_tuner = None

async def get_avatar_personality_tuner() -> AvatarPersonalityTuner:
    """アバターパーソナリティチューナーのインスタンスを取得"""
    global _avatar_personality_tuner

    if _avatar_personality_tuner is None:
        _avatar_personality_tuner = AvatarPersonalityTuner()
        await _avatar_personality_tuner.initialize()

    return _avatar_personality_tuner
