# main/interactive_ai_agent.py
"""
Interactive AI Agent Module for Cocoa
会話可能なAIアバター機能を提供
"""

import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

from integrated_security import get_security_manager

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class ConversationContext:
    """会話コンテキスト"""
    user_id: str
    avatar_id: str
    session_id: str
    language: str = "ja"
    personality: Dict[str, Any] = field(default_factory=dict)
    knowledge_base: List[str] = field(default_factory=list)
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

@dataclass
class AgentResponse:
    """AIエージェントの応答"""
    response_text: str
    confidence_score: float
    response_time: float
    language: str
    emotion: str = "neutral"
    suggestions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

class PersonalityManager:
    """パーソナリティ管理"""

    def __init__(self):
        self.personality_templates = {
            "friendly": {
                "tone": "friendly",
                "verbosity": "moderate",
                "formality": "casual",
                "traits": ["helpful", "patient", "enthusiastic"]
            },
            "professional": {
                "tone": "professional",
                "verbosity": "concise",
                "formality": "formal",
                "traits": ["knowledgeable", "precise", "respectful"]
            },
            "creative": {
                "tone": "creative",
                "verbosity": "elaborate",
                "formality": "casual",
                "traits": ["imaginative", "inspiring", "artistic"]
            },
            "teacher": {
                "tone": "educational",
                "verbosity": "detailed",
                "formality": "moderate",
                "traits": ["patient", "explanatory", "encouraging"]
            }
        }

    def get_personality_prompt(self, personality_type: str) -> str:
        """パーソナリティに基づくプロンプトを取得"""
        template = self.personality_templates.get(personality_type, self.personality_templates["friendly"])

        prompt = f"You are an AI assistant with a {template['tone']} personality. "
        prompt += f"Be {template['verbosity']} in your responses and maintain {template['formality']} formality. "
        prompt += f"Key traits: {', '.join(template['traits'])}."

        return prompt

class KnowledgeBaseManager:
    """知識ベース管理"""

    def __init__(self):
        self.knowledge_dir = Path("data/knowledge_base")
        self.knowledge_dir.mkdir(parents=True, exist_ok=True)

    def add_knowledge(self, user_id: str, knowledge_items: List[str]) -> bool:
        """知識ベースに情報を追加"""
        try:
            kb_file = self.knowledge_dir / f"{user_id}_knowledge.json"

            if kb_file.exists():
                with open(kb_file, encoding='utf-8') as f:
                    existing_data = json.load(f)
                    existing_knowledge = existing_data.get('knowledge', [])
            else:
                existing_knowledge = []

            # 重複を避けて新しい知識を追加
            for item in knowledge_items:
                if item not in existing_knowledge:
                    existing_knowledge.append(item)

            # 保存
            with open(kb_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'user_id': user_id,
                    'knowledge': existing_knowledge,
                    'updated_at': datetime.now(timezone.utc).isoformat()
                }, f, ensure_ascii=False, indent=2)

            return True

        except Exception as e:
            logger.error(f"Failed to add knowledge: {e}")
            return False

    def get_knowledge_context(self, user_id: str, max_items: int = 10) -> str:
        """知識ベースからコンテキストを取得"""
        try:
            kb_file = self.knowledge_dir / f"{user_id}_knowledge.json"

            if not kb_file.exists():
                return ""

            with open(kb_file, encoding='utf-8') as f:
                data = json.load(f)
                knowledge_items = data.get('knowledge', [])

            # 最新の知識を優先的に取得
            recent_knowledge = knowledge_items[-max_items:] if len(knowledge_items) > max_items else knowledge_items

            if recent_knowledge:
                return f"Relevant knowledge: {'; '.join(recent_knowledge)}"
            return ""

        except Exception as e:
            logger.error(f"Failed to get knowledge context: {e}")
            return ""

class InteractiveAIAgent:
    """
    インタラクティブAIエージェント
    会話可能なAIアバター機能を提供
    """

    def __init__(self, model_name: str = "microsoft/DialoGPT-medium", use_openai: bool = False):
        """
        初期化

        Args:
            model_name: 使用する言語モデル名
            use_openai: OpenAI APIを使用するか
        """
        self.security_manager = get_security_manager()
        self.personality_manager = PersonalityManager()
        self.knowledge_manager = KnowledgeBaseManager()

        self.model_name = model_name
        self.use_openai = use_openai

        # OpenAI設定
        self.openai_api_key = os.getenv('OPENAI_API_KEY', '')
        if use_openai and self.openai_api_key:
            openai.api_key = self.openai_api_key

        # ローカルモデル設定
        self.tokenizer = None
        self.model = None
        self.chatbot = None

        # アクティブな会話コンテキスト
        self.active_conversations: Dict[str, ConversationContext] = {}

        # 応答キャッシュ
        self.response_cache: Dict[str, AgentResponse] = {}

        logger.info(f"Interactive AI Agent initialized with model: {model_name}")

    async def initialize_model(self):
        """言語モデルを初期化"""
        try:
            if self.use_openai:
                logger.info("Using OpenAI API for conversations")
                return True

            logger.info(f"Loading local model: {self.model_name}")

            # トークナイザーとモデルの読み込み
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = AutoModelForCausalLM.from_pretrained(self.model_name)

            # パイプラインの設定
            self.chatbot = pipeline(
                'text-generation',
                model=self.model,
                tokenizer=self.tokenizer,
                device=0 if torch.cuda.is_available() else -1
            )

            logger.info("Local model loaded successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize model: {e}")
            return False

    async def create_conversation(self,
                                user_id: str,
                                avatar_id: str,
                                personality: str = "friendly",
                                language: str = "ja") -> str:
        """
        新しい会話セッションを作成

        Args:
            user_id: ユーザーID
            avatar_id: アバターID
            personality: パーソナリティタイプ
            language: 言語設定

        Returns:
            セッションID
        """
        session_id = str(uuid.uuid4())

        context = ConversationContext(
            user_id=user_id,
            avatar_id=avatar_id,
            session_id=session_id,
            language=language,
            personality={"type": personality},
            conversation_history=[]
        )

        self.active_conversations[session_id] = context

        # セキュリティログ
        await self.security_manager.log_security_event(
            event_type="conversation_created",
            user_id=user_id,
            details={
                "session_id": session_id,
                "avatar_id": avatar_id,
                "personality": personality,
                "language": language
            }
        )

        logger.info(f"Conversation created: {session_id} for user {user_id}")
        return session_id

    async def generate_response(self,
                              session_id: str,
                              user_message: str,
                              max_length: int = 150) -> AgentResponse:
        """
        AI応答を生成

        Args:
            session_id: 会話セッションID
            user_message: ユーザーのメッセージ
            max_length: 応答の最大長

        Returns:
            AIエージェントの応答
        """
        start_time = asyncio.get_event_loop().time()

        try:
            # 会話コンテキストを取得
            if session_id not in self.active_conversations:
                raise ValueError(f"Session not found: {session_id}")

            context = self.active_conversations[session_id]

            # 知識ベースからコンテキストを取得
            knowledge_context = self.knowledge_manager.get_knowledge_context(context.user_id)

            # パーソナリティプロンプトを取得
            personality_prompt = self.personality_manager.get_personality_prompt(
                context.personality.get("type", "friendly")
            )

            # 完全なプロンプトを構築
            full_prompt = self._build_conversation_prompt(
                personality_prompt,
                knowledge_context,
                context.conversation_history,
                user_message,
                context.language
            )

            # AI応答を生成
            if self.use_openai:
                response_text = await self._generate_openai_response(full_prompt, max_length)
            else:
                response_text = await self._generate_local_response(full_prompt, max_length)

            # 応答を処理・検証
            processed_response = await self._process_response(response_text, context)

            # 会話履歴を更新
            context.conversation_history.append({
                "user": user_message,
                "agent": processed_response.response_text,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

            # 履歴が長くなりすぎないよう制限
            if len(context.conversation_history) > 50:
                context.conversation_history = context.conversation_history[-30:]

            # 応答時間を計算
            response_time = asyncio.get_event_loop().time() - start_time

            final_response = AgentResponse(
                response_text=processed_response.response_text,
                confidence_score=processed_response.confidence_score,
                response_time=response_time,
                language=context.language,
                emotion=processed_response.emotion,
                suggestions=processed_response.suggestions,
                metadata={
                    "session_id": session_id,
                    "model_used": "openai" if self.use_openai else "local",
                    "knowledge_items_used": len(knowledge_context.split(";")) if knowledge_context else 0
                }
            )

            # キャッシュに保存
            self.response_cache[session_id] = final_response

            # セキュリティログ
            await self.security_manager.log_security_event(
                event_type="ai_response_generated",
                user_id=context.user_id,
                details={
                    "session_id": session_id,
                    "response_length": len(final_response.response_text),
                    "confidence": final_response.confidence_score
                }
            )

            return final_response

        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            response_time = asyncio.get_event_loop().time() - start_time

            return AgentResponse(
                response_text="申し訳ありませんが、エラーが発生しました。もう一度お試しください。",
                confidence_score=0.0,
                response_time=response_time,
                language=context.language if session_id in self.active_conversations else "ja",
                emotion="apologetic"
            )

    def _build_conversation_prompt(self,
                                 personality_prompt: str,
                                 knowledge_context: str,
                                 conversation_history: List[Dict[str, str]],
                                 current_message: str,
                                 language: str) -> str:
        """会話プロンプトを構築"""
        prompt = f"{personality_prompt}\n\n"

        if knowledge_context:
            prompt += f"{knowledge_context}\n\n"

        # 会話履歴を追加（最新の3往復のみ）
        recent_history = conversation_history[-6:] if len(conversation_history) > 6 else conversation_history

        for exchange in recent_history:
            prompt += f"User: {exchange['user']}\n"
            prompt += f"Assistant: {exchange['agent']}\n"

        prompt += f"User: {current_message}\n"
        prompt += "Assistant:"

        return prompt

    async def _generate_openai_response(self, prompt: str, max_length: int) -> str:
        """OpenAI APIで応答を生成"""
        try:
            response = await openai.ChatCompletion.acreate(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful AI assistant."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_length,
                temperature=0.7
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise

    async def _generate_local_response(self, prompt: str, max_length: int) -> str:
        """ローカルモデルで応答を生成"""
        try:
            if not self.chatbot:
                raise RuntimeError("Local model not initialized")

            # トークン制限を考慮してプロンプトを調整
            inputs = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512)

            outputs = self.chatbot(
                inputs['input_ids'],
                max_length=inputs['input_ids'].shape[1] + max_length,
                temperature=0.7,
                do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id
            )

            generated_text = self.tokenizer.decode(outputs[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True)
            return generated_text.strip()

        except Exception as e:
            logger.error(f"Local model error: {e}")
            raise

    async def _process_response(self, response_text: str, context: ConversationContext) -> AgentResponse:
        """応答を処理・検証"""
        # 応答のクリーンアップ
        cleaned_response = self._clean_response(response_text)

        # 感情分析（簡易版）
        emotion = self._analyze_emotion(cleaned_response)

        # 信頼度スコアの計算（簡易版）
        confidence_score = self._calculate_confidence(cleaned_response, context)

        # 提案の生成（簡易版）
        suggestions = self._generate_suggestions(cleaned_response, context)

        return AgentResponse(
            response_text=cleaned_response,
            confidence_score=confidence_score,
            response_time=0.0,  # 実際の応答時間は呼び出し元で計算
            language=context.language,
            emotion=emotion,
            suggestions=suggestions
        )

    def _clean_response(self, response: str) -> str:
        """応答をクリーンアップ"""
        # 不要な文字や繰り返しの除去
        cleaned = response.strip()

        # 過度な繰り返しの除去
        import re
        return re.sub(r'(.)\1{3,}', r'\1\1', cleaned)

    def _analyze_emotion(self, response: str) -> str:
        """応答から感情を分析（簡易版）"""
        positive_words = ['ありがとう', '嬉しい', '素晴らしい', 'excellent', 'great', 'wonderful']
        negative_words = ['申し訳', '残念', '悪い', 'sorry', 'unfortunately']

        response_lower = response.lower()

        if any(word in response_lower for word in positive_words):
            return "positive"
        if any(word in response_lower for word in negative_words):
            return "negative"
        return "neutral"

    def _calculate_confidence(self, response: str, context: ConversationContext) -> float:
        """応答の信頼度を計算（簡易版）"""
        # 応答の長さによるスコアリング
        length_score = min(1.0, len(response) / 100)

        # 言語一致によるスコアリング
        language_score = 1.0 if context.language in response else 0.8

        # 会話の連続性によるスコアリング
        history_score = min(1.0, len(context.conversation_history) / 10)

        return (length_score + language_score + history_score) / 3

    def _generate_suggestions(self, response: str, context: ConversationContext) -> List[str]:
        """応答に基づく提案を生成（簡易版）"""
        suggestions = []

        if "質問" in response or "?" in response:
            suggestions.append("さらなる詳細を尋ねる")

        if len(context.conversation_history) > 5:
            suggestions.append("会話を続ける")
            suggestions.append("新しいトピックを提案する")

        return suggestions[:3]  # 最大3つの提案

    async def update_personality(self, session_id: str, personality_type: str) -> bool:
        """会話のパーソナリティを更新"""
        if session_id not in self.active_conversations:
            return False

        context = self.active_conversations[session_id]
        context.personality = {"type": personality_type}

        return True

    async def add_knowledge(self, session_id: str, knowledge_items: List[str]) -> bool:
        """会話に知識を追加"""
        if session_id not in self.active_conversations:
            return False

        context = self.active_conversations[session_id]
        return self.knowledge_manager.add_knowledge(context.user_id, knowledge_items)

    async def get_conversation_history(self, session_id: str) -> List[Dict[str, str]]:
        """会話履歴を取得"""
        if session_id not in self.active_conversations:
            return []

        return self.active_conversations[session_id].conversation_history

    async def end_conversation(self, session_id: str) -> bool:
        """会話セッションを終了"""
        if session_id not in self.active_conversations:
            return False

        context = self.active_conversations[session_id]

        # セキュリティログ
        await self.security_manager.log_security_event(
            event_type="conversation_ended",
            user_id=context.user_id,
            details={
                "session_id": session_id,
                "message_count": len(context.conversation_history)
            }
        )

        # セッションを削除
        del self.active_conversations[session_id]

        # キャッシュもクリーンアップ
        if session_id in self.response_cache:
            del self.response_cache[session_id]

        logger.info(f"Conversation ended: {session_id}")
        return True

    async def get_agent_stats(self) -> Dict[str, Any]:
        """エージェント統計情報を取得"""
        return {
            "active_conversations": len(self.active_conversations),
            "total_responses": len(self.response_cache),
            "supported_languages": ["ja", "en", "zh", "ko"],
            "available_personalities": list(self.personality_manager.personality_templates.keys()),
            "model_status": "ready" if (self.chatbot or self.use_openai) else "not_initialized"
        }

# グローバルインスタンス管理
_ai_agent_instance = None
_ai_agent_instance_lock = asyncio.Lock()

async def get_interactive_ai_agent() -> InteractiveAIAgent:
    """インタラクティブAIエージェントのインスタンスを取得"""
    global _ai_agent_instance

    if _ai_agent_instance is None:
        async with _ai_agent_instance_lock:
            if _ai_agent_instance is None:
                use_openai = bool(os.getenv('OPENAI_API_KEY'))
                _ai_agent_instance = InteractiveAIAgent(use_openai=use_openai)
                if not await _ai_agent_instance.initialize_model():
                    logger.warning("Failed to initialize AI model, using fallback mode")

    return _ai_agent_instance
