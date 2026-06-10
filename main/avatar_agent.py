# main/avatar_agent.py
"""
Avatar Agent Module for Cocoa
Webサイトやキオスクに埋め込み可能なリアルタイムアバター代理機能
"""

import asyncio
import json
import logging
import random
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Optional web-server stack (only required when running the embeddable agent server).
try:
    import aiohttp
    from aiohttp import web
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

try:
    import jinja2
    JINJA2_AVAILABLE = True
except ImportError:
    JINJA2_AVAILABLE = False

try:
    import aiofiles
    AIOFILES_AVAILABLE = True
except ImportError:
    AIOFILES_AVAILABLE = False

from integrated_security import get_security_manager
from interactive_avatar import InteractiveAvatar, create_interactive_avatar


@dataclass
class AgentSession:
    """エージェントとの対話セッション"""
    session_id: str
    agent_id: str
    client_id: str
    start_time: datetime
    last_activity: datetime
    message_count: int = 0

@dataclass
class AgenticTask:
    """自律的タスク"""
    task_id: str
    task_type: str
    priority: int
    context: Dict[str, Any]
    trigger_conditions: Dict[str, Any]
    action_sequence: List[str]
    status: str = "pending"
    created_at: datetime = None
    completed_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)

@dataclass
class EnvironmentContext:
    """環境コンテキスト"""
    user_activity: str
    time_of_day: str
    location: str
    emotional_state: str
    recent_actions: List[str]
    system_status: Dict[str, Any]
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)
@dataclass
class AgentConfiguration:
    """アバターエージェント設定"""
    agent_id: str
    avatar_id: str
    style: str
    name: str
    description: str
    personality: Dict[str, Any]
    capabilities: List[str]
    embedding_options: Dict[str, Any]
    security_settings: Dict[str, Any]
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)

class AgenticAIManager:
    """
    Agentic AIマネージャー
    自律的にタスクを実行し、環境に適応するAI
    """

    def __init__(self):
        self.security_manager = get_security_manager()

        # タスク管理
        self.active_tasks: Dict[str, AgenticTask] = {}
        self.completed_tasks: deque = deque(maxlen=1000)
        self.task_history: Dict[str, List] = defaultdict(list)

        # 環境監視
        self.environment_history: deque = deque(maxlen=100)
        self.context_window: int = 50

        # 学習データ
        self.behavior_patterns: Dict[str, Any] = {}
        self.success_rates: Dict[str, float] = defaultdict(float)

        # 設定
        self.autonomous_mode: bool = True
        self.learning_enabled: bool = True
        self.adaptation_rate: float = 0.7

        # 予測モデル
        self.action_predictor: Dict[str, Any] = {}

        logger.info("Agentic AI Manager initialized")

    async def initialize(self):
        """初期化"""
        # デフォルトタスクテンプレートの読み込み
        await self._load_default_task_templates()

        # 環境監視開始
        await self._start_environment_monitoring()

        # 予測モデルの初期化
        await self._initialize_prediction_model()

    async def _load_default_task_templates(self):
        """デフォルトタスクテンプレートの読み込み"""
        self.task_templates = {
            "user_engagement": AgenticTask(
                task_id="user_engagement",
                task_type="engagement",
                priority=5,
                context={"trigger": "user_idle"},
                trigger_conditions={"idle_time": 30, "last_interaction": "chat"},
                action_sequence=["initiate_conversation", "suggest_help", "offer_assistance"]
            ),
            "security_check": AgenticTask(
                task_id="security_check",
                task_type="security",
                priority=9,
                context={"trigger": "suspicious_activity"},
                trigger_conditions={"failed_attempts": 3, "unusual_patterns": True},
                action_sequence=["log_security_event", "increase_monitoring", "alert_admin"]
            ),
            "performance_optimization": AgenticTask(
                task_id="performance_optimization",
                task_type="optimization",
                priority=6,
                context={"trigger": "high_load"},
                trigger_conditions={"cpu_usage": 80, "memory_usage": 75},
                action_sequence=["analyze_performance", "optimize_resources", "adjust_settings"]
            ),
            "context_awareness": AgenticTask(
                task_id="context_awareness",
                task_type="awareness",
                priority=4,
                context={"trigger": "context_change"},
                trigger_conditions={"time_change": True, "activity_change": True},
                action_sequence=["analyze_context", "adapt_behavior", "update_responses"]
            )
        }

    async def _start_environment_monitoring(self):
        """環境監視の開始"""
        # 環境監視タスクを定期的に実行
        while self.autonomous_mode:
            try:
                # 環境コンテキストの取得
                context = await self._get_environment_context()
                self.environment_history.append(context)

                # タスクトリガーのチェック
                await self._check_task_triggers(context)

                # 予測的行動の実行
                await self._execute_predictive_actions(context)

                # 待機
                await asyncio.sleep(5)  # 5秒間隔で監視

            except Exception as e:
                logger.error(f"Environment monitoring error: {e}")
                await asyncio.sleep(10)

    async def _get_environment_context(self) -> EnvironmentContext:
        """環境コンテキストを取得"""
        # 実際の実装では各種センサーやシステム情報を収集
        return EnvironmentContext(
            user_activity=self._detect_user_activity(),
            time_of_day=self._get_time_of_day(),
            location=self._get_location(),
            emotional_state=self._detect_emotional_state(),
            recent_actions=list(self.task_history.keys())[-10:],
            system_status={
                "cpu_usage": random.uniform(20, 80),
                "memory_usage": random.uniform(30, 70),
                "active_sessions": len(self.active_sessions) if hasattr(self, 'active_sessions') else 0
            }
        )

    def _detect_user_activity(self) -> str:
        """ユーザーの活動を検知"""
        # 簡易的な活動検知
        activities = ["browsing", "chatting", "idle", "working", "researching"]
        return random.choice(activities)

    def _get_time_of_day(self) -> str:
        """時間帯を取得"""
        hour = datetime.now(timezone.utc).hour
        if 6 <= hour < 12:
            return "morning"
        if 12 <= hour < 18:
            return "afternoon"
        if 18 <= hour < 22:
            return "evening"
        return "night"

    def _get_location(self) -> str:
        """場所を取得"""
        # 実際にはGPSやネットワーク情報から
        return "office"

    def _detect_emotional_state(self) -> str:
        """感情状態を検知"""
        # 実際には感情分析APIやセンサーから
        emotions = ["neutral", "positive", "negative", "excited", "confused"]
        return random.choice(emotions)

    async def _check_task_triggers(self, context: EnvironmentContext):
        """タスクトリガーをチェック"""
        for template in self.task_templates.values():
            if await self._should_trigger_task(template, context):
                await self._execute_agentic_task(template, context)

    async def _should_trigger_task(self, task: AgenticTask, context: EnvironmentContext) -> bool:
        """タスクを実行すべきか判断"""
        # トリガー条件の評価
        for condition, threshold in task.trigger_conditions.items():
            current_value = context.system_status.get(condition, 0)
            if isinstance(threshold, (int, float)):
                if current_value < threshold:
                    return False
            elif isinstance(threshold, bool):
                if not current_value:
                    return False
            elif isinstance(threshold, str) and context.user_activity != threshold:
                return False

        # 優先度に基づく実行判断
        if task.priority < 5:
            return random.random() < 0.8  # 高優先タスクは80%の確率で実行
        return random.random() < 0.3  # 低優先タスクは30%の確率で実行

    async def _execute_agentic_task(self, task_template: AgenticTask, context: EnvironmentContext):
        """自律的タスクを実行"""
        task = AgenticTask(
            task_id=f"{task_template.task_id}_{int(time.time())}",
            task_type=task_template.task_type,
            priority=task_template.priority,
            context=task_template.context,
            trigger_conditions=task_template.trigger_conditions,
            action_sequence=task_template.action_sequence.copy()
        )

        self.active_tasks[task.task_id] = task
        logger.info(f"Executing agentic task: {task.task_id} ({task.task_type})")

        try:
            # アクションシーケンスの実行
            for action in task.action_sequence:
                await self._execute_action(action, task, context)
                await asyncio.sleep(1)  # アクション間隔

            # タスク完了
            task.status = "completed"
            task.completed_at = datetime.now(timezone.utc)
            self.completed_tasks.append(task)

            # 履歴記録
            self.task_history[task.task_type].append({
                "task_id": task.task_id,
                "success": True,
                "duration": (task.completed_at - task.created_at).total_seconds()
            })

            # 成功率更新
            self._update_success_rate(task.task_type, True)

            logger.info(f"Task completed successfully: {task.task_id}")

        except Exception as e:
            logger.error(f"Task execution failed: {task.task_id} - {e}")
            task.status = "failed"
            task.completed_at = datetime.now(timezone.utc)
            self.task_history[task.task_type].append({
                "task_id": task.task_id,
                "success": False,
                "error": str(e)
            })
            self._update_success_rate(task.task_type, False)

        finally:
            # アクティブタスクから削除
            if task.task_id in self.active_tasks:
                del self.active_tasks[task.task_id]

    async def _execute_action(self, action: str, task: AgenticTask, context: EnvironmentContext):
        """個別アクションを実行"""
        logger.info(f"Executing action: {action}")

        # アクションに応じた処理
        if action == "initiate_conversation":
            await self._initiate_conversation(task, context)
        elif action == "suggest_help":
            await self._suggest_help(task, context)
        elif action == "log_security_event":
            await self._log_security_event(task, context)
        elif action == "analyze_performance":
            await self._analyze_performance(task, context)
        elif action == "analyze_context":
            await self._analyze_context(task, context)
        elif action == "adapt_behavior":
            await self._adapt_behavior(task, context)

    async def _initiate_conversation(self, task: AgenticTask, context: EnvironmentContext):
        """会話を開始"""
        # 実際にはWebSocketやAPI経由でメッセージを送信
        message = f"こんにちは！ {context.time_of_day}の時間帯ですね。何かお手伝いできることはありますか？"
        logger.info(f"Initiating conversation: {message}")
        # ここで実際のメッセージ送信処理を実装

    async def _suggest_help(self, task: AgenticTask, context: EnvironmentContext):
        """ヘルプを提案"""
        suggestions = [
            "ドキュメントの閲覧をお手伝いします",
            "設定の確認をサポートします",
            "パフォーマンスの最適化を提案します"
        ]
        suggestion = random.choice(suggestions)
        logger.info(f"Suggesting help: {suggestion}")
        # 実際のヘルプ提案処理

    async def _log_security_event(self, task: AgenticTask, context: EnvironmentContext):
        """セキュリティイベントを記録"""
        logger.warning(f"Security event detected: {context.system_status}")
        # セキュリティログへの記録
        await self.security_manager.log_event(
            event_type="agentic_ai_security_check",
            details=f"Agentic task triggered: {task.task_id}",
            severity="medium"
        )

    async def _analyze_performance(self, task: AgenticTask, context: EnvironmentContext):
        """パフォーマンスを分析"""
        logger.info(f"Analyzing performance: {context.system_status}")
        # パフォーマンス分析処理

    async def _analyze_context(self, task: AgenticTask, context: EnvironmentContext):
        """コンテキストを分析"""
        logger.info(f"Analyzing context: {context.user_activity}, {context.time_of_day}")
        # コンテキスト分析処理

    async def _adapt_behavior(self, task: AgenticTask, context: EnvironmentContext):
        """行動を適応"""
        # 環境に応じた行動適応
        if context.time_of_day == "night":
            logger.info("Adapting behavior for night time - reducing activity")
        elif context.user_activity == "working":
            logger.info("Adapting behavior for work mode - increasing assistance")

    async def _execute_predictive_actions(self, context: EnvironmentContext):
        """予測的行動を実行"""
        # ユーザーの次の行動を予測して準備
        predictions = await self._predict_user_actions(context)
        for prediction in predictions:
            await self._prepare_for_prediction(prediction, context)

    async def _predict_user_actions(self, context: EnvironmentContext) -> List[str]:
        """ユーザーの行動を予測"""
        # 簡易的な予測モデル
        predictions = []

        if context.time_of_day == "morning" and context.user_activity == "browsing":
            predictions.append("document_access")
        elif context.emotional_state == "confused":
            predictions.append("help_request")
        elif context.system_status.get("cpu_usage", 0) > 70:
            predictions.append("performance_complaint")

        return predictions[:3]  # 最大3つまで

    async def _prepare_for_prediction(self, prediction: str, context: EnvironmentContext):
        """予測に対する準備"""
        logger.info(f"Preparing for predicted action: {prediction}")
        # 予測に基づく準備処理

    async def _initialize_prediction_model(self):
        """予測モデルの初期化"""
        # 機械学習モデルやルールベースの予測システムを初期化
        self.action_predictor = {
            "morning": ["document_access", "status_check"],
            "afternoon": ["help_request", "feature_usage"],
            "evening": ["summary_request", "backup_check"],
            "night": ["maintenance", "log_review"]
        }

    def _update_success_rate(self, task_type: str, success: bool):
        """成功率を更新"""
        current_rate = self.success_rates[task_type]
        if success:
            self.success_rates[task_type] = current_rate * 0.9 + 0.1
        else:
            self.success_rates[task_type] = current_rate * 0.9 + 0.0

    def get_agentic_status(self) -> Dict[str, Any]:
        """Agentic AIのステータスを取得"""
        return {
            "autonomous_mode": self.autonomous_mode,
            "learning_enabled": self.learning_enabled,
            "active_tasks": len(self.active_tasks),
            "completed_tasks_today": len([t for t in self.completed_tasks if t.created_at.date() == datetime.now(timezone.utc).date()]),
            "success_rates": dict(self.success_rates),
            "environment_context": self.environment_history[-1] if self.environment_history else None
        }

    async def enable_autonomous_mode(self):
        """自律モードを有効化"""
        self.autonomous_mode = True
        logger.info("Autonomous mode enabled")

    async def disable_autonomous_mode(self):
        """自律モードを無効化"""
        self.autonomous_mode = False
        logger.info("Autonomous mode disabled")

# グローバルインスタンス
_agentic_ai_manager = None

async def get_agentic_ai_manager() -> AgenticAIManager:
    """Agentic AIマネージャーのインスタンスを取得"""
    global _agentic_ai_manager

    if _agentic_ai_manager is None:
        _agentic_ai_manager = AgenticAIManager()
        await _agentic_ai_manager.initialize()

    return _agentic_ai_manager
class AvatarAgentService:
    """
    アバターエージェントサービス
    Web埋め込み可能なリアルタイムアバター代理
    Agentic AI機能を統合
    """

    def __init__(self):
        self.security_manager = get_security_manager()

        # エージェント管理
        self.agents: Dict[str, AgentConfiguration] = {}
        self.active_sessions: Dict[str, AgentSession] = {}
        self.agent_instances: Dict[str, InteractiveAvatar] = {}

        # Agentic AI統合
        self.agentic_ai_manager: Optional[AgenticAIManager] = None

        # Webサーバー
        self.web_app = None
        self.runner = None
        self.site = None

        # テンプレート
        self.template_dir = Path("main/templates")
        self.static_dir = Path("main/static")

        # 設定
        self.host = "0.0.0.0"
        self.port = 8080
        self.max_sessions_per_agent = 10

        logger.info("Avatar Agent Service with Agentic AI initialized")

    async def initialize(self):
        """初期化"""
        # ディレクトリ作成
        for dir_path in [self.template_dir, self.static_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

        # Agentic AIマネージャーの初期化
        self.agentic_ai_manager = await get_agentic_ai_manager()

        # Webアプリケーション作成
        self.web_app = web.Application()
        self.setup_routes()

        # デフォルトエージェント作成
        await self.create_default_agents()

        # Jinja2テンプレート環境
        self.template_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(self.template_dir)),
            autoescape=True
        )

    def setup_routes(self):
        """Webルート設定"""
        self.web_app.router.add_get('/', self.index_page)
        self.web_app.router.add_get('/agent/{agent_id}', self.agent_page)
        self.web_app.router.add_get('/embed/{agent_id}', self.embed_widget)
        self.web_app.router.add_get('/api/agents', self.get_agents_api)
        self.web_app.router.add_get('/api/agent/{agent_id}/status', self.get_agent_status)
        self.web_app.router.add_post('/api/agent/{agent_id}/message', self.send_message)
        self.web_app.router.add_get('/ws/agent/{agent_id}', self.websocket_handler)

        # Agentic AI API
        self.web_app.router.add_get('/api/agentic/status', self.get_agentic_status)
        self.web_app.router.add_post('/api/agentic/enable', self.enable_agentic_ai)
        self.web_app.router.add_post('/api/agentic/disable', self.disable_agentic_ai)
        self.web_app.router.add_get('/api/agentic/tasks', self.get_agentic_tasks)

        self.web_app.router.add_static('/static/', path=str(self.static_dir), name='static')

    async def create_default_agents(self):
        """デフォルトエージェント作成"""
        default_agents = [
            AgentConfiguration(
                agent_id="customer_support",
                avatar_id="support_bot",
                style="professional",
                name="カスタマーサポート",
                description="製品やサービスに関する質問にお答えします",
                personality={
                    "tone": "helpful",
                    "expertise": ["products", "services", "troubleshooting"],
                    "response_style": "clear_and_concise"
                },
                capabilities=["text_chat", "faq_lookup", "ticket_creation"],
                embedding_options={
                    "size": "medium",
                    "position": "bottom_right",
                    "theme": "corporate"
                },
                security_settings={
                    "max_sessions": 50,
                    "rate_limit": 10,  # messages per minute
                    "content_filter": True
                }
            ),
            AgentConfiguration(
                agent_id="sales_assistant",
                avatar_id="sales_bot",
                style="friendly",
                name="営業アシスタント",
                description="製品のご紹介やお見積もりのお手伝いをいたします",
                personality={
                    "tone": "enthusiastic",
                    "expertise": ["products", "pricing", "features"],
                    "response_style": "persuasive_and_helpful"
                },
                capabilities=["text_chat", "product_demo", "quote_generation"],
                embedding_options={
                    "size": "large",
                    "position": "center",
                    "theme": "sales"
                },
                security_settings={
                    "max_sessions": 30,
                    "rate_limit": 15,
                    "content_filter": True
                }
            ),
            AgentConfiguration(
                agent_id="educational_guide",
                avatar_id="teacher_bot",
                style="wise",
                name="学習ガイド",
                description="学習内容についてわかりやすく説明します",
                personality={
                    "tone": "patient",
                    "expertise": ["education", "tutorials", "explanations"],
                    "response_style": "educational_and_encouraging"
                },
                capabilities=["text_chat", "interactive_lessons", "progress_tracking"],
                embedding_options={
                    "size": "medium",
                    "position": "bottom_left",
                    "theme": "educational"
                },
                security_settings={
                    "max_sessions": 100,
                    "rate_limit": 20,
                    "content_filter": True
                }
            )
        ]

        for agent_config in default_agents:
            await self.create_agent(agent_config)

    async def create_agent(self, config: AgentConfiguration) -> bool:
        """
        アバターエージェントを作成

        Args:
            config: エージェント設定

        Returns:
            作成成功かどうか
        """
        try:
            # 設定検証
            if not await self._validate_agent_config(config):
                return False

            # エージェント登録
            self.agents[config.agent_id] = config

            # インタラクティブアバター作成
            avatar = await create_interactive_avatar(config.avatar_id, config.style)
            self.agent_instances[config.agent_id] = avatar

            # エージェントサーバー起動
            await avatar.start_server(host="localhost", port=self._get_agent_port(config.agent_id))

            # 設定保存
            await self._save_agent_config(config)

            logger.info(f"Created avatar agent: {config.agent_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to create agent {config.agent_id}: {e}")
            return False

    async def _validate_agent_config(self, config: AgentConfiguration) -> bool:
        """エージェント設定の検証"""
        # 必須フィールドチェック
        required_fields = ['agent_id', 'avatar_id', 'style', 'name', 'description']
        for field in required_fields:
            if not getattr(config, field, None):
                logger.error(f"Missing required field: {field}")
                return False

        # 重複IDチェック
        if config.agent_id in self.agents:
            logger.error(f"Agent ID already exists: {config.agent_id}")
            return False

        # セキュリティ設定チェック
        if config.security_settings.get('max_sessions', 0) > 1000:
            logger.error("Max sessions too high")
            return False

        return True

    def _get_agent_port(self, agent_id: str) -> int:
        """エージェント用のポート番号を取得"""
        # シンプルなハッシュベースのポート割り当て
        port_base = 9000
        port_offset = hash(agent_id) % 1000
        return port_base + port_offset

    async def _save_agent_config(self, config: AgentConfiguration):
        """エージェント設定を保存"""
        config_dir = Path("data/agent_configs")
        config_dir.mkdir(parents=True, exist_ok=True)

        config_file = config_dir / f"{config.agent_id}.json"
        config_data = {
            "agent_id": config.agent_id,
            "avatar_id": config.avatar_id,
            "style": config.style,
            "name": config.name,
            "description": config.description,
            "personality": config.personality,
            "capabilities": config.capabilities,
            "embedding_options": config.embedding_options,
            "security_settings": config.security_settings,
            "created_at": config.created_at.isoformat()
        }

        async with aiofiles.open(config_file, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(config_data, ensure_ascii=False, indent=2))

    async def start_service(self, host: str = "0.0.0.0", port: int = 8080):
        """サービスを開始"""
        self.host = host
        self.port = port

        try:
            self.runner = web.AppRunner(self.web_app)
            await self.runner.setup()

            self.site = web.TCPSite(self.runner, host, port)
            await self.site.start()

            logger.info(f"Avatar Agent Service started on http://{host}:{port}")

            # テンプレートファイル作成
            await self._create_template_files()

        except Exception as e:
            logger.error(f"Failed to start service: {e}")
            raise

    async def stop_service(self):
        """サービスを停止"""
        # すべてのエージェントを停止
        for agent in self.agent_instances.values():
            await agent.stop_server()

        # Webサーバー停止
        if self.site:
            await self.site.stop()

        if self.runner:
            await self.runner.cleanup()

        logger.info("Avatar Agent Service stopped")

    async def _create_template_files(self):
        """テンプレートファイルを作成"""
        # HTMLテンプレート
        index_template = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cocoa Avatar Agents</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .agent-card { border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px; }
        .agent-card h3 { margin-top: 0; }
        .embed-code { background: #f5f5f5; padding: 10px; border-radius: 3px; font-family: monospace; }
    </style>
</head>
<body>
    <h1>Cocoa アバターエージェント</h1>
    <p>利用可能なアバターエージェント:</p>

    {% for agent_id, agent in agents.items() %}
    <div class="agent-card">
        <h3>{{ agent.name }}</h3>
        <p>{{ agent.description }}</p>
        <p><strong>スタイル:</strong> {{ agent.style }}</p>
        <p><strong>機能:</strong> {{ agent.capabilities|join(', ') }}</p>

        <h4>埋め込みコード:</h4>
        <div class="embed-code">
&lt;iframe src="http://{{ host }}:{{ port }}/embed/{{ agent_id }}"
        width="400" height="600" frameborder="0"&gt;&lt;/iframe&gt;
        </div>

        <p><a href="/agent/{{ agent_id }}" target="_blank">テストページを開く</a></p>
    </div>
    {% endfor %}
</body>
</html>
        """

        embed_template = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ agent.name }} - Avatar Agent</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background: {{ theme.background or '#f0f0f0' }};
        }
        .chat-container {
            max-width: 100%;
            height: 100vh;
            display: flex;
            flex-direction: column;
        }
        .avatar-area {
            flex: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            background: {{ theme.avatar_bg or '#ffffff' }};
            border-radius: 10px;
            margin-bottom: 20px;
        }
        .avatar-image {
            max-width: 200px;
            max-height: 200px;
            border-radius: 50%;
        }
        .chat-messages {
            flex: 1;
            overflow-y: auto;
            padding: 10px;
            background: white;
            border-radius: 10px;
            margin-bottom: 10px;
        }
        .message {
            margin: 10px 0;
            padding: 10px;
            border-radius: 10px;
        }
        .message.user { background: #007bff; color: white; margin-left: 50px; }
        .message.agent { background: #e9ecef; margin-right: 50px; }
        .input-area {
            display: flex;
            gap: 10px;
        }
        #message-input {
            flex: 1;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
        }
        button {
            padding: 10px 20px;
            background: {{ theme.button_bg or '#007bff' }};
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
        }
        button:hover { opacity: 0.8; }
        .status { text-align: center; color: #666; font-size: 0.9em; }
    </style>
</head>
<body>
    <div class="chat-container">
        <div class="avatar-area">
            <div id="avatar-display">
                <img src="/static/avatar-placeholder.png" alt="{{ agent.name }}" class="avatar-image">
                <div class="status" id="status">接続中...</div>
            </div>
        </div>

        <div class="chat-messages" id="messages"></div>

        <div class="input-area">
            <input type="text" id="message-input" placeholder="メッセージを入力...">
            <button onclick="sendMessage()">送信</button>
        </div>
    </div>

    <script>
        let ws;
        const agentId = '{{ agent_id }}';

        function initWebSocket() {
            ws = new WebSocket(`ws://localhost:{{ port + 1000 }}/ws/agent/${agentId}`);

            ws.onopen = function(event) {
                document.getElementById('status').textContent = '接続完了';
                addMessage('system', '{{ agent.name }}がオンラインになりました。');
            };

            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                if (data.type === 'response') {
                    addMessage('agent', data.content);
                }
            };

            ws.onclose = function(event) {
                document.getElementById('status').textContent = '切断されました';
                addMessage('system', '接続が切断されました。');
            };

            ws.onerror = function(error) {
                console.error('WebSocket error:', error);
                document.getElementById('status').textContent = 'エラー発生';
            };
        }

        function addMessage(sender, content) {
            const messages = document.getElementById('messages');
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${sender}`;
            messageDiv.textContent = content;
            messages.appendChild(messageDiv);
            messages.scrollTop = messages.scrollHeight;
        }

        function sendMessage() {
            const input = document.getElementById('message-input');
            const message = input.value.trim();

            if (message && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({
                    type: 'text',
                    content: message,
                    timestamp: new Date().toISOString()
                }));

                addMessage('user', message);
                input.value = '';
            }
        }

        // Enterキーでの送信
        document.getElementById('message-input').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });

        // 初期化
        initWebSocket();
    </script>
</body>
</html>
        """

        # テンプレートファイル保存
        async with aiofiles.open(self.template_dir / "index.html", 'w', encoding='utf-8') as f:
            await f.write(index_template)

        async with aiofiles.open(self.template_dir / "embed.html", 'w', encoding='utf-8') as f:
            await f.write(embed_template)

    # Webハンドラー
    async def index_page(self, request):
        """インデックスページ"""
        template = self.template_env.get_template("index.html")
        html = template.render(
            agents=self.agents,
            host=self.host,
            port=self.port
        )
        return web.Response(text=html, content_type='text/html')

    async def agent_page(self, request):
        """エージェント個別ページ"""
        agent_id = request.match_info['agent_id']
        agent = self.agents.get(agent_id)

        if not agent:
            return web.Response(text="Agent not found", status=404)

        # 埋め込みページを直接表示
        return await self.embed_widget(request)

    async def embed_widget(self, request):
        """埋め込みウィジェット"""
        agent_id = request.match_info['agent_id']
        agent = self.agents.get(agent_id)

        if not agent:
            return web.Response(text="Agent not found", status=404)

        template = self.template_env.get_template("embed.html")
        html = template.render(
            agent=agent,
            agent_id=agent_id,
            port=self.port + 1000,  # WebSocketポート
            theme=agent.embedding_options
        )
        return web.Response(text=html, content_type='text/html')

    async def get_agents_api(self, request):
        """エージェント一覧API"""
        agents_data = {}
        for agent_id, agent in self.agents.items():
            agents_data[agent_id] = {
                "agent_id": agent.agent_id,
                "name": agent.name,
                "description": agent.description,
                "style": agent.style,
                "capabilities": agent.capabilities,
                "embedding_options": agent.embedding_options
            }

        return web.json_response(agents_data)

    async def get_agent_status(self, request):
        """エージェントステータス取得"""
        agent_id = request.match_info['agent_id']
        agent = self.agent_instances.get(agent_id)

        if not agent:
            return web.json_response({"error": "Agent not found"}, status=404)

        status = agent.get_status()
        active_sessions = len([s for s in self.active_sessions.values() if s.agent_id == agent_id])

        return web.json_response({
            "agent_id": agent_id,
            "status": status,
            "active_sessions": active_sessions,
            "max_sessions": self.agents[agent_id].security_settings.get('max_sessions', 10)
        })

    async def send_message(self, request):
        """メッセージ送信API"""
        agent_id = request.match_info['agent_id']
        agent = self.agent_instances.get(agent_id)

        if not agent:
            return web.json_response({"error": "Agent not found"}, status=404)

        try:
            data = await request.json()
            message = data.get('message', '')
            user_id = data.get('user_id', 'api_user')

            # セッション作成または取得
            session_id = f"{agent_id}_{user_id}"
            if session_id not in self.active_sessions:
                self.active_sessions[session_id] = AgentSession(
                    session_id=session_id,
                    agent_id=agent_id,
                    client_id=user_id,
                    start_time=datetime.now(timezone.utc),
                    last_activity=datetime.now(timezone.utc)
                )

            session = self.active_sessions[session_id]
            session.message_count += 1
            session.last_activity = datetime.now(timezone.utc)

            # メッセージ処理（ここでは簡易的な応答）
            response = f"こんにちは！ {message} についてお答えします。"

            return web.json_response({
                "response": response,
                "session_id": session_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

        except Exception as e:
            logger.error(f"Message processing error: {e}")
            return web.json_response({"error": "Processing failed"}, status=500)

    async def websocket_handler(self, request):
        """WebSocketハンドラー"""
        agent_id = request.match_info['agent_id']
        agent = self.agent_instances.get(agent_id)

        if not agent:
            return web.Response(text="Agent not found", status=404)

        # インタラクティブアバターのWebSocketにリダイレクト
        # 実際の実装ではここでWebSocketプロキシを行う
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        # 簡易的なエコー実装
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(msg.data)
                response = {
                    "type": "response",
                    "content": f"エージェント {agent_id} からの応答: {data.get('content', '')}",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                await ws.send_str(json.dumps(response, ensure_ascii=False))
            elif msg.type == aiohttp.WSMsgType.ERROR:
                logger.error(f'WebSocket error {ws.exception()}')

        return ws

    # Agentic AI ハンドラー
    async def get_agentic_status(self, request):
        """Agentic AI ステータス取得"""
        if not self.agentic_ai_manager:
            return web.json_response({"error": "Agentic AI not initialized"}, status=500)

        status = self.agentic_ai_manager.get_agentic_status()
        return web.json_response(status)

    async def enable_agentic_ai(self, request):
        """Agentic AI を有効化"""
        if not self.agentic_ai_manager:
            return web.json_response({"error": "Agentic AI not initialized"}, status=500)

        try:
            await self.agentic_ai_manager.enable_autonomous_mode()
            return web.json_response({"status": "enabled"})
        except Exception as e:
            logger.error(f"Failed to enable Agentic AI: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def disable_agentic_ai(self, request):
        """Agentic AI を無効化"""
        if not self.agentic_ai_manager:
            return web.json_response({"error": "Agentic AI not initialized"}, status=500)

        try:
            await self.agentic_ai_manager.disable_autonomous_mode()
            return web.json_response({"status": "disabled"})
        except Exception as e:
            logger.error(f"Failed to disable Agentic AI: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def get_agentic_tasks(self, request):
        """Agentic AI タスク一覧取得"""
        if not self.agentic_ai_manager:
            return web.json_response({"error": "Agentic AI not initialized"}, status=500)

        tasks = {
            "active": [task.__dict__ for task in self.agentic_ai_manager.active_tasks.values()],
            "completed": [task.__dict__ for task in list(self.agentic_ai_manager.completed_tasks)[-10:]]
        }

        return web.json_response(tasks)

# グローバルインスタンス管理
_avatar_agent_service = None

async def get_avatar_agent_service() -> AvatarAgentService:
    """アバターエージェントサービスのインスタンスを取得"""
    global _avatar_agent_service

    if _avatar_agent_service is None:
        _avatar_agent_service = AvatarAgentService()
        await _avatar_agent_service.initialize()

    return _avatar_agent_service
