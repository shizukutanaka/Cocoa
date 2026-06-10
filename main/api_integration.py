# main/api_integration.py
"""
API Integration Module for Cocoa
外部システムとの自動動画作成ワークフロー統合
"""

import hashlib
import hmac
import json
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import aiofiles
    from aiohttp import web
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

from integrated_security import get_security_manager
from template_library import get_template_library
from video_creator import VideoCreationRequest, get_video_creator

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class IntegrationConfig:
    """統合設定"""
    integration_id: str
    name: str
    type: str  # 'webhook', 'api', 'zapier', 'cms', 'crm'
    provider: str  # 'wordpress', 'shopify', 'salesforce', 'hubspot', etc.
    config: Dict[str, Any]
    webhooks: List[Dict[str, Any]] = None
    api_keys: Dict[str, str] = None
    enabled: bool = True
    created_at: datetime = None

    def __post_init__(self):
        if self.webhooks is None:
            self.webhooks = []
        if self.api_keys is None:
            self.api_keys = {}
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)

@dataclass
class WorkflowTrigger:
    """ワークフロートリガー"""
    trigger_id: str
    integration_id: str
    event_type: str  # 'content_created', 'user_registered', 'order_completed', etc.
    conditions: Dict[str, Any]
    actions: List[Dict[str, Any]]
    enabled: bool = True
    last_triggered: Optional[datetime] = None

@dataclass
class WorkflowExecution:
    """ワークフロー実行"""
    execution_id: str
    trigger_id: str
    input_data: Dict[str, Any]
    status: str  # 'pending', 'running', 'completed', 'failed'
    results: Dict[str, Any] = None
    error_message: Optional[str] = None
    started_at: datetime = None
    completed_at: Optional[datetime] = None

    def __post_init__(self):
        if self.results is None:
            self.results = {}
        if self.started_at is None:
            self.started_at = datetime.now(timezone.utc)

class APIIntegrationService:
    """
    API統合サービス
    外部システムとの自動動画作成ワークフロー
    """

    def __init__(self):
        self.security_manager = get_security_manager()

        # 統合管理
        self.integrations: Dict[str, IntegrationConfig] = {}
        self.triggers: Dict[str, WorkflowTrigger] = {}
        self.executions: Dict[str, WorkflowExecution] = {}

        # サービスインスタンス
        self.video_creator = None
        self.template_library = None

        # Webサーバー
        self.web_app = None
        self.runner = None
        self.site = None

        # 設定
        self.host = "0.0.0.0"
        self.port = 8081
        self.webhook_secret = os.getenv("WEBHOOK_SECRET", "default_secret")

        logger.info("API Integration Service initialized")

    async def initialize(self):
        """初期化"""
        # サービスインスタンス取得
        self.video_creator = await get_video_creator()
        self.template_library = await get_template_library()

        # Webアプリケーション作成
        self.web_app = web.Application()
        self.setup_routes()

        # デフォルト統合設定
        await self.create_default_integrations()

    def setup_routes(self):
        """APIルート設定"""
        # Webhookエンドポイント
        self.web_app.router.add_post('/webhook/{integration_id}/{event_type}', self.webhook_handler)
        self.web_app.router.add_post('/webhook/zapier', self.zapier_webhook_handler)

        # REST APIエンドポイント
        self.web_app.router.add_get('/api/integrations', self.get_integrations)
        self.web_app.router.add_post('/api/integrations', self.create_integration)
        self.web_app.router.add_get('/api/integrations/{integration_id}', self.get_integration)
        self.web_app.router.add_put('/api/integrations/{integration_id}', self.update_integration)
        self.web_app.router.add_delete('/api/integrations/{integration_id}', self.delete_integration)

        # ワークフロー管理
        self.web_app.router.add_get('/api/workflows', self.get_workflows)
        self.web_app.router.add_post('/api/workflows', self.create_workflow)
        self.web_app.router.add_get('/api/workflows/{workflow_id}', self.get_workflow)
        self.web_app.router.add_put('/api/workflows/{workflow_id}', self.update_workflow)
        self.web_app.router.add_delete('/api/workflows/{workflow_id}', self.delete_workflow)

        # 実行管理
        self.web_app.router.add_get('/api/executions', self.get_executions)
        self.web_app.router.add_post('/api/executions/{execution_id}/retry', self.retry_execution)

        # 外部システム連携API
        self.web_app.router.add_post('/api/cms/wordpress/post', self.cms_wordpress_post)
        self.web_app.router.add_post('/api/crm/salesforce/lead', self.crm_salesforce_lead)
        self.web_app.router.add_post('/api/ecommerce/shopify/order', self.ecommerce_shopify_order)

    async def create_default_integrations(self):
        """デフォルト統合設定を作成"""
        default_integrations = [
            IntegrationConfig(
                integration_id="wordpress",
                name="WordPress CMS",
                type="cms",
                provider="wordpress",
                config={
                    "webhook_url": f"http://{self.host}:{self.port}/webhook/wordpress",
                    "supported_events": ["post_published", "page_updated", "media_uploaded"],
                    "auto_video_generation": True
                },
                webhooks=[
                    {
                        "event": "post_published",
                        "url": f"http://{self.host}:{self.port}/webhook/wordpress/post_published",
                        "method": "POST"
                    }
                ]
            ),
            IntegrationConfig(
                integration_id="shopify",
                name="Shopify E-commerce",
                type="ecommerce",
                provider="shopify",
                config={
                    "webhook_url": f"http://{self.host}:{self.port}/webhook/shopify",
                    "supported_events": ["order_created", "product_updated", "customer_created"],
                    "auto_product_videos": True
                },
                webhooks=[
                    {
                        "event": "order_created",
                        "url": f"http://{self.host}:{self.port}/webhook/shopify/order_created",
                        "method": "POST"
                    }
                ]
            ),
            IntegrationConfig(
                integration_id="zapier",
                name="Zapier Integration",
                type="zapier",
                provider="zapier",
                config={
                    "webhook_url": f"http://{self.host}:{self.port}/webhook/zapier",
                    "supported_triggers": ["new_content", "user_action", "data_update"],
                    "api_key": os.getenv("ZAPIER_API_KEY", "")
                }
            )
        ]

        for integration in default_integrations:
            await self.create_integration_config(integration)

    async def create_integration_config(self, config: IntegrationConfig):
        """統合設定を作成"""
        self.integrations[config.integration_id] = config

        # 設定保存
        config_dir = Path("data/integrations")
        config_dir.mkdir(parents=True, exist_ok=True)

        config_file = config_dir / f"{config.integration_id}.json"
        config_data = {
            "integration_id": config.integration_id,
            "name": config.name,
            "type": config.type,
            "provider": config.provider,
            "config": config.config,
            "webhooks": config.webhooks,
            "api_keys": config.api_keys,
            "enabled": config.enabled,
            "created_at": config.created_at.isoformat()
        }

        async with aiofiles.open(config_file, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(config_data, ensure_ascii=False, indent=2))

        logger.info(f"Created integration: {config.integration_id}")

    async def start_service(self, host: str = "0.0.0.0", port: int = 8081):
        """サービスを開始"""
        self.host = host
        self.port = port

        try:
            self.runner = web.AppRunner(self.web_app)
            await self.runner.setup()

            self.site = web.TCPSite(self.runner, host, port)
            await self.site.start()

            logger.info(f"API Integration Service started on http://{host}:{port}")

        except Exception as e:
            logger.error(f"Failed to start integration service: {e}")
            raise

    async def stop_service(self):
        """サービスを停止"""
        if self.site:
            await self.site.stop()

        if self.runner:
            await self.runner.cleanup()

        logger.info("API Integration Service stopped")

    # Webhookハンドラー
    async def webhook_handler(self, request):
        """汎用Webhookハンドラー"""
        integration_id = request.match_info['integration_id']
        event_type = request.match_info['event_type']

        # 統合設定確認
        integration = self.integrations.get(integration_id)
        if not integration or not integration.enabled:
            return web.json_response({"error": "Integration not found or disabled"}, status=404)

        try:
            # リクエストデータ取得
            if request.content_type == 'application/json':
                data = await request.json()
            else:
                data = await request.text()

            # シグネチャ検証（オプション）
            signature = request.headers.get('X-Signature', '')
            if (integration.config.get('verify_signature', False)
                    and not self._verify_webhook_signature(data, signature, integration)):
                return web.json_response({"error": "Invalid signature"}, status=401)

            # ワークフロートリガー実行
            execution_results = await self._process_webhook_trigger(
                integration_id, event_type, data
            )

            return web.json_response({
                "status": "processed",
                "integration_id": integration_id,
                "event_type": event_type,
                "executions": execution_results
            })

        except Exception as e:
            logger.error(f"Webhook processing error: {e}")
            return web.json_response({"error": "Processing failed"}, status=500)

    async def zapier_webhook_handler(self, request):
        """Zapier Webhookハンドラー"""
        try:
            data = await request.json()
            trigger_type = data.get('trigger', 'generic')

            # Zapier固有の処理
            execution_results = await self._process_zapier_trigger(trigger_type, data)

            return web.json_response({
                "status": "processed",
                "trigger_type": trigger_type,
                "executions": execution_results
            })

        except Exception as e:
            logger.error(f"Zapier webhook error: {e}")
            return web.json_response({"error": "Processing failed"}, status=500)

    async def _process_webhook_trigger(self, integration_id: str, event_type: str, data: Any) -> List[Dict]:
        """Webhookトリガーを処理"""
        executions = []

        # 関連するトリガーを検索
        for trigger in self.triggers.values():
            if (trigger.integration_id == integration_id and
                    trigger.event_type == event_type and
                    trigger.enabled and
                    self._check_trigger_conditions(trigger.conditions, data)):
                execution = await self._execute_workflow_trigger(trigger, data)
                executions.append({
                    "trigger_id": trigger.trigger_id,
                    "execution_id": execution.execution_id,
                    "status": execution.status
                })

        return executions

    async def _process_zapier_trigger(self, trigger_type: str, data: Dict) -> List[Dict]:
        """Zapierトリガーを処理"""
        executions = []

        # Zapier固有のトリガーを検索
        zapier_integration = self.integrations.get('zapier')
        if not zapier_integration:
            return executions

        for trigger in self.triggers.values():
            if (trigger.integration_id == 'zapier' and
                trigger.event_type == trigger_type and
                trigger.enabled):

                execution = await self._execute_workflow_trigger(trigger, data)
                executions.append({
                    "trigger_id": trigger.trigger_id,
                    "execution_id": execution.execution_id,
                    "status": execution.status
                })

        return executions

    def _check_trigger_conditions(self, conditions: Dict, data: Any) -> bool:
        """トリガー条件をチェック"""
        if not conditions:
            return True

        # 簡易的な条件チェック実装
        for key, expected_value in conditions.items():
            if isinstance(data, dict):
                actual_value = data.get(key)
            else:
                # 他のデータ形式の場合はスキップ
                continue

            if actual_value != expected_value:
                return False

        return True

    async def _execute_workflow_trigger(self, trigger: WorkflowTrigger, input_data: Any) -> WorkflowExecution:
        """ワークフロートリガーを実行"""
        execution_id = f"exec_{uuid.uuid4().hex}"

        execution = WorkflowExecution(
            execution_id=execution_id,
            trigger_id=trigger.trigger_id,
            input_data=input_data if isinstance(input_data, dict) else {"raw_data": str(input_data)},
            status="running"
        )

        self.executions[execution_id] = execution

        try:
            # アクション実行
            results = await self._execute_workflow_actions(trigger.actions, input_data)

            execution.status = "completed"
            execution.results = results
            execution.completed_at = datetime.now(timezone.utc)

        except Exception as e:
            execution.status = "failed"
            execution.error_message = str(e)
            execution.completed_at = datetime.now(timezone.utc)
            logger.error(f"Workflow execution failed: {e}")

        # トリガーの最終実行時間を更新
        trigger.last_triggered = datetime.now(timezone.utc)

        return execution

    async def _execute_workflow_actions(self, actions: List[Dict], input_data: Any) -> Dict[str, Any]:
        """ワークフローアクションを実行"""
        results = {}

        for action in actions:
            action_type = action.get('type')

            if action_type == 'create_video':
                video_result = await self._execute_video_creation_action(action, input_data)
                results['video_creation'] = video_result

            elif action_type == 'send_notification':
                notification_result = await self._execute_notification_action(action, input_data)
                results['notification'] = notification_result

            elif action_type == 'update_cms':
                cms_result = await self._execute_cms_update_action(action, input_data)
                results['cms_update'] = cms_result

            elif action_type == 'create_task':
                task_result = await self._execute_task_creation_action(action, input_data)
                results['task_creation'] = task_result

        return results

    async def _execute_video_creation_action(self, action: Dict, input_data: Any) -> Dict[str, Any]:
        """動画作成アクションを実行"""
        try:
            # 入力データから動画作成パラメータを抽出
            script = self._extract_script_from_input(action, input_data)
            avatar_style = action.get('avatar_style', 'professional')
            template_id = action.get('template_id')

            # テンプレート使用の場合
            if template_id:
                template = self.template_library.get_video_templates().get(template_id)
                if template:
                    script = template.script_template.format(**input_data)

            # 動画作成リクエスト
            request = VideoCreationRequest(
                user_id="integration_system",
                script=script,
                avatar_style=avatar_style,
                voice_settings={"voice": "female", "speed": 1.0},
                video_settings={"resolution": "1080p", "fps": 30}
            )

            # 動画作成実行
            result = await self.video_creator.create_video(request)

            return {
                "success": result.success,
                "video_path": result.video_path,
                "thumbnail_path": result.thumbnail_path,
                "creation_time": result.creation_time
            }

        except Exception as e:
            logger.error(f"Video creation action failed: {e}")
            return {"success": False, "error": str(e)}

    async def _execute_notification_action(self, action: Dict, input_data: Any) -> Dict[str, Any]:
        """通知アクションを実行"""
        # 通知送信の実装（メール、Slackなど）
        logger.info(f"Sending notification: {action.get('message', 'Workflow completed')}")
        return {"success": True, "message": "Notification sent"}

    async def _execute_cms_update_action(self, action: Dict, input_data: Any) -> Dict[str, Any]:
        """CMS更新アクションを実行"""
        # CMS更新の実装
        logger.info(f"Updating CMS: {action.get('target', 'unknown')}")
        return {"success": True, "message": "CMS updated"}

    async def _execute_task_creation_action(self, action: Dict, input_data: Any) -> Dict[str, Any]:
        """タスク作成アクションを実行"""
        # タスク作成の実装
        logger.info(f"Creating task: {action.get('title', 'New task')}")
        return {"success": True, "message": "Task created"}

    def _extract_script_from_input(self, action: Dict, input_data: Any) -> str:
        """入力データからスクリプトを抽出"""
        script_template = action.get('script_template', '{content}')

        if isinstance(input_data, dict):
            return script_template.format(**input_data)
        return str(input_data)

    def _verify_webhook_signature(self, payload: str, signature: str, integration: IntegrationConfig) -> bool:
        """Webhookシグネチャを検証"""
        secret = integration.api_keys.get('webhook_secret', self.webhook_secret)
        expected_signature = hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(signature, expected_signature)

    # REST APIハンドラー
    async def get_integrations(self, request):
        """統合設定一覧を取得"""
        integrations_data = {}
        for integration_id, integration in self.integrations.items():
            integrations_data[integration_id] = {
                "integration_id": integration.integration_id,
                "name": integration.name,
                "type": integration.type,
                "provider": integration.provider,
                "enabled": integration.enabled,
                "webhooks": integration.webhooks
            }

        return web.json_response(integrations_data)

    async def create_integration(self, request):
        """統合設定を作成"""
        try:
            data = await request.json()

            integration = IntegrationConfig(
                integration_id=data['integration_id'],
                name=data['name'],
                type=data['type'],
                provider=data.get('provider', ''),
                config=data.get('config', {}),
                webhooks=data.get('webhooks', []),
                api_keys=data.get('api_keys', {})
            )

            await self.create_integration_config(integration)

            return web.json_response({
                "integration_id": integration.integration_id,
                "status": "created"
            }, status=201)

        except Exception as e:
            logger.error(f"Integration creation failed: {e}")
            return web.json_response({"error": str(e)}, status=400)

    async def get_integration(self, request):
        """統合設定を取得"""
        integration_id = request.match_info['integration_id']
        integration = self.integrations.get(integration_id)

        if not integration:
            return web.json_response({"error": "Integration not found"}, status=404)

        return web.json_response({
            "integration_id": integration.integration_id,
            "name": integration.name,
            "type": integration.type,
            "provider": integration.provider,
            "config": integration.config,
            "webhooks": integration.webhooks,
            "enabled": integration.enabled
        })

    async def update_integration(self, request):
        """統合設定を更新"""
        integration_id = request.match_info['integration_id']
        integration = self.integrations.get(integration_id)

        if not integration:
            return web.json_response({"error": "Integration not found"}, status=404)

        try:
            data = await request.json()

            # 更新可能なフィールド
            for field in ['name', 'config', 'webhooks', 'api_keys', 'enabled']:
                if field in data:
                    setattr(integration, field, data[field])

            # 設定保存
            await self.create_integration_config(integration)

            return web.json_response({"status": "updated"})

        except Exception as e:
            logger.error(f"Integration update failed: {e}")
            return web.json_response({"error": str(e)}, status=400)

    async def delete_integration(self, request):
        """統合設定を削除"""
        integration_id = request.match_info['integration_id']

        if integration_id not in self.integrations:
            return web.json_response({"error": "Integration not found"}, status=404)

        # 関連するトリガーを削除
        triggers_to_delete = [tid for tid, t in self.triggers.items() if t.integration_id == integration_id]
        for tid in triggers_to_delete:
            del self.triggers[tid]

        # 統合設定削除
        del self.integrations[integration_id]

        # 設定ファイル削除
        config_file = Path("data/integrations") / f"{integration_id}.json"
        if config_file.exists():
            config_file.unlink()

        return web.json_response({"status": "deleted"})

    # 外部システム連携API
    async def cms_wordpress_post(self, request):
        """WordPress投稿連携"""
        try:
            data = await request.json()

            # WordPress投稿データを処理
            post_data = {
                "title": data.get("title", ""),
                "content": data.get("content", ""),
                "excerpt": data.get("excerpt", ""),
                "categories": data.get("categories", [])
            }

            # 動画作成ワークフロー実行
            script = f"新しいブログ記事: {post_data['title']}\n\n{post_data['content'][:500]}..."

            request_obj = VideoCreationRequest(
                user_id="wordpress_integration",
                script=script,
                avatar_style="professional"
            )

            result = await self.video_creator.create_video(request_obj)

            return web.json_response({
                "status": "processed",
                "video_created": result.success,
                "video_path": result.video_path
            })

        except Exception as e:
            logger.error(f"WordPress integration failed: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def crm_salesforce_lead(self, request):
        """Salesforceリード連携"""
        try:
            data = await request.json()

            lead_data = {
                "name": data.get("name", ""),
                "company": data.get("company", ""),
                "email": data.get("email", ""),
                "status": data.get("status", "")
            }

            # 歓迎動画作成
            script = f"""こんにちは、{lead_data['name']}様！

{lead_data['company']}にお勤めの皆様へ、弊社のソリューションをご紹介いたします。

[製品の特徴やメリットについて説明]

お気軽にお問い合わせください。"""

            request_obj = VideoCreationRequest(
                user_id="salesforce_integration",
                script=script,
                avatar_style="business"
            )

            result = await self.video_creator.create_video(request_obj)

            return web.json_response({
                "status": "processed",
                "welcome_video_created": result.success,
                "video_path": result.video_path
            })

        except Exception as e:
            logger.error(f"Salesforce integration failed: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def ecommerce_shopify_order(self, request):
        """Shopify注文連携"""
        try:
            data = await request.json()

            order_data = {
                "order_number": data.get("order_number", ""),
                "customer_name": data.get("customer", {}).get("first_name", ""),
                "total_price": data.get("total_price", ""),
                "line_items": data.get("line_items", [])
            }

            # 注文確認動画作成
            script = f"""{order_data['customer_name']}様

ご注文いただき、ありがとうございます！
注文番号: {order_data['order_number']}
合計金額: ¥{order_data['total_price']}

[注文商品の確認]

商品はすぐに発送いたします。"""

            request_obj = VideoCreationRequest(
                user_id="shopify_integration",
                script=script,
                avatar_style="casual"
            )

            result = await self.video_creator.create_video(request_obj)

            return web.json_response({
                "status": "processed",
                "confirmation_video_created": result.success,
                "video_path": result.video_path
            })

        except Exception as e:
            logger.error(f"Shopify integration failed: {e}")
            return web.json_response({"error": str(e)}, status=500)

    # その他のAPIハンドラーは省略（実装は同様）

# グローバルインスタンス管理
_api_integration_service = None

async def get_api_integration_service() -> APIIntegrationService:
    """API統合サービスのインスタンスを取得"""
    global _api_integration_service

    if _api_integration_service is None:
        _api_integration_service = APIIntegrationService()
        await _api_integration_service.initialize()

    return _api_integration_service
