"""
RAG-Enhanced Avatar Generator for Cocoa
Retrieval-Augmented Generationを活用した高度なアバター生成システム
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timezone
import json

from sentence_transformers import SentenceTransformer
import chromadb

from integrated_security import get_security_manager

logger = logging.getLogger(__name__)

class AvatarRAGSystem:
    """
    RAGを活用したアバター生成システム
    ユーザーの好みや過去の選択を学習して、より良い提案を提供
    """

    def __init__(self, embedding_model: str = "all-MiniLM-L6-v2"):
        self.security_manager = get_security_manager()
        self.embedding_model = SentenceTransformer(embedding_model)
        self.vector_store = None
        self.chroma_client = None
        self.collection = None

        # 知識ベースの初期化
        self.avatar_knowledge_base = self._build_avatar_knowledge_base()

        # キャッシュディレクトリ
        self.cache_dir = Path("data/rag_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Avatar RAG System initialized")

    def _build_avatar_knowledge_base(self) -> Dict[str, List[str]]:
        """アバター生成に関する知識ベースを構築"""
        return {
            "styles": [
                "リアルなポートレート写真風",
                "アニメスタイルのキャラクター",
                "カートゥーン調のイラスト",
                "プロフェッショナルなビジネスポートレート",
                "カジュアルな日常スタイル",
                "ファンタジーキャラクター風",
                "サイバーパンク風の未来的スタイル",
                "ミニマリストなシンプルデザイン"
            ],
            "features": [
                "長い髪の女性キャラクター",
                "短い髪の男性キャラクター",
                "大きな瞳の可愛らしい顔",
                "シャープなフェイスライン",
                "優しい表情のポートレート",
                "自信たっぷりの強い視線",
                "柔らかい照明の優しい雰囲気",
                "ドラマチックな影の演出"
            ],
            "customizations": [
                "髪の色を変更",
                "瞳の色を調整",
                "表情を柔らかく",
                "服装をビジネススーツに",
                "背景をぼかして",
                "照明を暖色系に",
                "アクセサリーを追加",
                "メイクをナチュラルに"
            ],
            "trends": [
                "メタバース対応の高品質アバター",
                "NFTアートスタイルのデジタルアバター",
                "VR/AR対応のインタラクティブアバター",
                "ソーシャルメディア向けのプロフィール画像",
                "ゲームキャラクター風の個性派アバター",
                "プロフェッショナルなビジネスアバター",
                "クリエイター向けの個性派スタイル",
                "ミニマリストで洗練されたデザイン"
            ]
        }

    async def initialize_vector_store(self):
        """ベクターストアを初期化"""
        try:
            # ChromaDBクライアントの初期化
            self.chroma_client = chromadb.PersistentClient(path=str(self.cache_dir / "chroma_db"))

            # コレクションの作成または取得
            self.collection = self.chroma_client.get_or_create_collection(
                name="avatar_knowledge",
                metadata={"description": "Avatar generation knowledge base"}
            )

            # 知識ベースをベクターストアに追加
            await self._populate_knowledge_base()

            logger.info("RAG vector store initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize RAG vector store: {e}")
            raise

    async def _populate_knowledge_base(self):
        """知識ベースをベクターストアに追加"""
        if not self.collection:
            await self.initialize_vector_store()

        # 既存のデータがあるかチェック
        existing_count = self.collection.count()

        if existing_count == 0:
            # 知識ベースからドキュメントを作成
            documents = []
            metadatas = []
            ids = []

            for category, items in self.avatar_knowledge_base.items():
                for i, item in enumerate(items):
                    doc_id = f"{category}_{i}"
                    documents.append(item)
                    metadatas.append({"category": category, "type": "knowledge_base"})
                    ids.append(doc_id)

            # ドキュメントをコレクションに追加
            self.collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )

            logger.info(f"Added {len(documents)} knowledge base entries to vector store")

    async def enhance_prompt_with_rag(
        self,
        user_id: str,
        base_prompt: str,
        user_preferences: Optional[Dict] = None,
        context: Optional[str] = None
    ) -> str:
        """
        RAGを活用してプロンプトを強化

        Args:
            user_id: ユーザーID
            base_prompt: 基本プロンプト
            user_preferences: ユーザーの好みデータ
            context: 追加のコンテキスト

        Returns:
            強化されたプロンプト
        """
        try:
            # セキュリティチェック
            if not await self.security_manager.validate_user_access(user_id, "avatar_generation"):
                raise ValueError("Unauthorized access to RAG system")

            # クエリ構築
            query = f"{base_prompt}"
            if context:
                query += f" {context}"
            if user_preferences:
                query += f" ユーザーの好み: {json.dumps(user_preferences, ensure_ascii=False)}"

            # 類似ドキュメントを検索
            similar_docs = self.collection.query(
                query_texts=[query],
                n_results=5,
                where={"type": "knowledge_base"}
            )

            # 関連情報を抽出してプロンプトに統合
            enhanced_prompt = await self._build_enhanced_prompt(
                base_prompt, similar_docs, user_preferences
            )

            # ログ記録
            await self._log_rag_usage(user_id, query, enhanced_prompt)

            return enhanced_prompt

        except Exception as e:
            logger.error(f"RAG prompt enhancement failed: {e}")
            # エラー時は基本プロンプトを返す
            return base_prompt

    async def _build_enhanced_prompt(
        self,
        base_prompt: str,
        similar_docs: Dict,
        user_preferences: Optional[Dict]
    ) -> str:
        """類似ドキュメントから強化されたプロンプトを構築"""

        # 基本プロンプトにトレンド情報を追加
        enhanced_prompt = base_prompt

        # 類似ドキュメントから関連情報を抽出
        if similar_docs and "documents" in similar_docs:
            documents = similar_docs["documents"][0]  # 最初のクエリの結果

            # カテゴリ別の情報を追加
            categories_added = set()

            for doc in documents:
                # スタイル関連の情報
                if any(keyword in doc for keyword in ["スタイル", "リアル", "アニメ", "カートゥーン"]) and "styles" not in categories_added:
                    enhanced_prompt += ", 高品質なアバタースタイル"
                    categories_added.add("styles")

                # 特徴関連の情報
                elif any(keyword in doc for keyword in ["髪", "瞳", "表情", "顔"]) and "features" not in categories_added:
                    enhanced_prompt += ", 詳細なフェイシャル特徴"
                    categories_added.add("features")

                # カスタマイズ関連の情報
                elif any(keyword in doc for keyword in ["カスタマイズ", "変更", "調整"]) and "customizations" not in categories_added:
                    enhanced_prompt += ", 柔軟なカスタマイズオプション"
                    categories_added.add("customizations")

                # トレンド関連の情報
                elif any(keyword in doc for keyword in ["トレンド", "メタバース", "NFT"]) and "trends" not in categories_added:
                    enhanced_prompt += ", 最新のメタバース対応デザイン"
                    categories_added.add("trends")

        # ユーザーの好みを追加
        if user_preferences:
            preferred_style = user_preferences.get("preferred_style")
            if preferred_style:
                enhanced_prompt += f", {preferred_style}スタイルを優先"

        # 2025年のトレンドを追加
        enhanced_prompt += ", 2025年最新トレンド対応, AI生成の高品質アバター"

        return enhanced_prompt

    async def learn_user_preferences(
        self,
        user_id: str,
        avatar_metadata: Dict,
        feedback: Optional[Dict] = None
    ):
        """ユーザーの好みを学習して知識ベースを更新"""

        try:
            # フィードバックデータから学習
            if feedback:
                preference_data = {
                    "user_id": user_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "avatar_style": avatar_metadata.get("style"),
                    "customizations": avatar_metadata.get("customizations"),
                    "feedback_score": feedback.get("score", 0),
                    "feedback_comment": feedback.get("comment", ""),
                    "type": "user_preference"
                }

                # ベクターストアに追加
                doc_id = f"user_pref_{user_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

                self.collection.add(
                    documents=[json.dumps(preference_data, ensure_ascii=False)],
                    metadatas=[{"type": "user_preference", "user_id": user_id}],
                    ids=[doc_id]
                )

                logger.info(f"Learned user preference for user {user_id}")

        except Exception as e:
            logger.error(f"Failed to learn user preferences: {e}")

    async def get_avatar_suggestions(
        self,
        user_id: str,
        current_context: str,
        count: int = 5
    ) -> List[str]:
        """ユーザーに合わせたアバター生成の提案"""

        try:
            # ユーザーの過去の好みを検索
            user_preferences = self.collection.query(
                query_texts=[f"user {user_id} avatar preferences"],
                n_results=10,
                where={"user_id": user_id}
            )

            # コンテキストに基づいた提案を生成
            suggestions = []

            if user_preferences and "documents" in user_preferences:
                # 過去の好みから提案を生成
                suggestions = await self._generate_suggestions_from_preferences(
                    user_preferences, current_context, count
                )
            else:
                # デフォルトの提案
                suggestions = self._get_default_suggestions(current_context, count)

            return suggestions

        except Exception as e:
            logger.error(f"Failed to get avatar suggestions: {e}")
            return self._get_default_suggestions(current_context, count)

    async def _generate_suggestions_from_preferences(
        self,
        preferences: Dict,
        context: str,
        count: int
    ) -> List[str]:
        """ユーザーの好みから提案を生成"""

        suggestions = []

        # コンテキストをベクター検索
        context_query = f"アバター生成の提案: {context}"
        similar_docs = self.collection.query(
            query_texts=[context_query],
            n_results=count * 2,
            where={"type": "knowledge_base"}
        )

        if similar_docs and "documents" in similar_docs:
            documents = similar_docs["documents"][0]

            for doc in documents[:count]:
                # 提案フォーマットを作成
                suggestion = f"提案: {doc} - {context}を反映したスタイル"
                suggestions.append(suggestion)

        return suggestions

    def _get_default_suggestions(self, context: str, count: int) -> List[str]:
        """デフォルトの提案を生成"""

        default_suggestions = [
            f"プロフェッショナルな{context}スタイルのアバター",
            f"クリエイティブな{context}を表現したデザイン",
            f"モダンで洗練された{context}アバター",
            f"親しみやすい{context}スタイル",
            f"個性派の{context}キャラクター"
        ]

        return default_suggestions[:count]

    async def _log_rag_usage(self, user_id: str, query: str, enhanced_prompt: str):
        """RAG使用をログ記録"""

        await self.security_manager.log_security_event(
            event_type="rag_prompt_enhancement",
            user_id=user_id,
            details={
                "original_query": query,
                "enhanced_prompt_length": len(enhanced_prompt),
                "enhancement_successful": True
            },
            ip_address="system"
        )

# グローバルインスタンス
_rag_system = None

async def get_rag_system() -> AvatarRAGSystem:
    """RAGシステムのインスタンスを取得"""

    global _rag_system

    if _rag_system is None:
        _rag_system = AvatarRAGSystem()
        await _rag_system.initialize_vector_store()

    return _rag_system
