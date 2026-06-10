"""Stripe billing integration for Otedama.

提供機能:
- Checkoutセッション生成 (買い切り / サブスクリプション)
- Stripe Webhook処理でのライセンス状態更新
- 簡易ストレージを用いたサブスクリプション状態保持
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import stripe
    STRIPE_AVAILABLE = True
except ImportError:
    stripe = None
    STRIPE_AVAILABLE = False

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR.parent / "config" / "config.json"
DEFAULT_STORAGE_PATH = BASE_DIR.parent / "data" / "billing_accounts.json"
DEFAULT_EVENT_LOG_PATH = BASE_DIR.parent / "data" / "billing_events.json"
logger = logging.getLogger(__name__)


class BillingError(RuntimeError):
    """Billing処理における例外."""


@dataclass(frozen=True)
class PriceTier:
    key: str
    price_id: str
    description: str


@dataclass(frozen=True)
class BillingConfig:
    enabled: bool
    mode: str
    currency: str
    default_price_tier: str
    trial_period_days: Optional[int]
    tiers: Dict[str, PriceTier]
    success_url: str
    cancel_url: str
    webhook_enabled: bool
    webhook_secret_env: Optional[str]

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> BillingConfig:
        billing_raw = (config_dict or {}).get("billing") or {}
        enabled = bool(billing_raw.get("enabled", False))
        mode = billing_raw.get("mode", "subscription")
        currency = billing_raw.get("currency", "jpy")
        default_price_tier = billing_raw.get("default_price_tier") or ""
        trial_period_days = billing_raw.get("trial_period_days")
        tiers_raw = billing_raw.get("tiers") or {}
        success_url = billing_raw.get("checkout", {}).get("success_url") or ""
        cancel_url = billing_raw.get("checkout", {}).get("cancel_url") or ""
        webhook_raw = billing_raw.get("webhook") or {}
        webhook_enabled = bool(webhook_raw.get("enabled", False))
        webhook_secret_env = webhook_raw.get("endpoint_secret_env")

        tiers: Dict[str, PriceTier] = {}
        for key, tier_data in tiers_raw.items():
            if not isinstance(tier_data, dict):
                continue
            price_id = tier_data.get("price_id")
            description = tier_data.get("description", "")
            if price_id:
                tiers[key] = PriceTier(key=key, price_id=price_id, description=description)

        return cls(
            enabled=enabled,
            mode=mode,
            currency=currency,
            default_price_tier=default_price_tier,
            trial_period_days=trial_period_days,
            tiers=tiers,
            success_url=success_url,
            cancel_url=cancel_url,
            webhook_enabled=webhook_enabled,
            webhook_secret_env=webhook_secret_env,
        )

    @classmethod
    def load(cls, path: Path = CONFIG_PATH) -> BillingConfig:
        with path.open(encoding="utf-8") as handle:
            config_dict = json.load(handle)
        return cls.from_dict(config_dict)

    def resolve_price(self, tier_key: Optional[str] = None) -> PriceTier:
        key = tier_key or self.default_price_tier
        if not key:
            raise BillingError("billing.default_price_tier が未設定です")
        if key not in self.tiers:
            raise BillingError(f"未定義の課金ティアが指定されました: {key}")
        return self.tiers[key]

    @property
    def webhook_secret(self) -> Optional[str]:
        if not self.webhook_enabled or not self.webhook_secret_env:
            return None
        return os.getenv(self.webhook_secret_env)


class BillingStorage:
    """JSONファイルベースの簡易ストレージ.

    Stripe側のサブスクリプション状態とユーザーIDの対応を保持します。
    """

    def __init__(self, storage_path: Path = DEFAULT_STORAGE_PATH):
        self._path = storage_path
        self._lock = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._write({})

    def _read(self) -> Dict[str, Any]:
        try:
            with self._path.open(encoding="utf-8") as handle:
                payload = json.load(handle)
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError as exc:
            # Empty or corrupt file — treat as empty storage rather than crashing
            if self._path.stat().st_size == 0:
                return {}
            raise BillingError(f"ストレージファイルの読み込みに失敗しました: {exc}") from exc

        if not isinstance(payload, dict):
            return {}
        return payload

    def _write(self, payload: Dict[str, Any]) -> None:
        tmp_path = self._path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        tmp_path.replace(self._path)

    def upsert_subscription(self, record_key: str, payload: Dict[str, Any]) -> None:
        with self._lock:
            data = self._read()
            data[record_key] = payload
            self._write(data)

    def get_by_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            data = self._read()
            for record in data.values():
                if record.get("user_id") == user_id:
                    return record
        return None

    def get_by_customer(self, customer_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            data = self._read()
            return data.get(customer_id)

    def all_records(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return dict(self._read())


class BillingEventLog:
    """Stripe Webhookイベントの処理状況を記録するシンプルなログ."""

    def __init__(
        self,
        path: Path = DEFAULT_EVENT_LOG_PATH,
        *,
        retention_days: int = 30,
        max_events: int = 5000,
    ) -> None:
        self._path = path
        self._retention_days = max(0, retention_days)
        self._max_events = max(1, max_events)
        self._lock = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._write({})

    def has(self, event_id: str) -> bool:
        if not event_id:
            return False
        with self._lock:
            data = self._read()
            return event_id in data

    def record(self, event_id: str, event_type: str) -> None:
        if not event_id:
            return
        with self._lock:
            data = self._read()
            data[event_id] = {
                "event_type": event_type,
                "processed_at": datetime.now(timezone.utc).isoformat(),
            }
            self._prune(data)
            self._write(data)

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _read(self) -> Dict[str, Any]:
        try:
            with self._path.open(encoding="utf-8") as handle:
                payload = json.load(handle)
            if not isinstance(payload, dict):
                return {}
            return payload
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError as exc:
            if self._path.stat().st_size == 0:
                return {}
            raise BillingError(f"イベントログの読み込みに失敗しました: {exc}") from exc

    def _write(self, payload: Dict[str, Any]) -> None:
        tmp_path = self._path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        tmp_path.replace(self._path)

    def _prune(self, data: Dict[str, Any]) -> None:
        if not data:
            return

        now = datetime.now(timezone.utc)
        threshold = now - timedelta(days=self._retention_days) if self._retention_days else None

        if threshold:
            expired = []
            for key, value in data.items():
                processed_at = self._parse_ts(value.get("processed_at"))
                if processed_at and processed_at < threshold:
                    expired.append(key)
            for key in expired:
                data.pop(key, None)

        if len(data) > self._max_events:
            ordered = sorted(
                (
                    (key, self._parse_ts(value.get("processed_at")) or now)
                    for key, value in data.items()
                ),
                key=lambda item: item[1],
            )
            for key, _ in ordered[: len(data) - self._max_events]:
                data.pop(key, None)

    @staticmethod
    def _parse_ts(raw: Optional[str]) -> Optional[datetime]:
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw.replace("Z", ""))
        except ValueError:
            return None


class StripeBillingService:
    """Stripe API を用いた課金処理ラッパー."""

    def __init__(self, config: Optional[BillingConfig] = None, storage: Optional[BillingStorage] = None, event_log: Optional[BillingEventLog] = None, *, config_path: Path = CONFIG_PATH) -> None:
        self._config = config or BillingConfig.load(config_path)
        if not self._config.enabled:
            raise BillingError("billing.enabled が false のため Stripe サービスを初期化できません")

        if not STRIPE_AVAILABLE:
            raise BillingError("stripe ライブラリがインストールされていません: pip install stripe")
        api_key = os.getenv("STRIPE_API_KEY")
        if not api_key:
            raise BillingError("環境変数 STRIPE_API_KEY が設定されていません")
        stripe.api_key = api_key

        # レート制限設定
        self._rate_limit_calls = 100  # 1分あたりの最大API呼び出し数
        self._rate_limit_window = 60  # レート制限ウィンドウ（秒）
        self._api_calls = []  # API呼び出しタイムスタンプ記録
        self._lock = threading.Lock()

        self._storage = storage or BillingStorage()
        self._event_log = event_log or BillingEventLog()

    def list_price_tiers(self) -> Dict[str, PriceTier]:
        """利用可能な課金ティアを返却します."""
        return dict(self._config.tiers)

    @property
    def config(self) -> BillingConfig:
        return self._config

    def create_checkout_session(
        self,
        *,
        user_id: str,
        tier_key: Optional[str] = None,
        customer_id: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        price_tier = self._config.resolve_price(tier_key)
        session_kwargs: Dict[str, Any] = {
            "success_url": self._config.success_url,
            "cancel_url": self._config.cancel_url,
            "metadata": {"user_id": user_id, "tier": price_tier.key},
        }
        if metadata:
            session_kwargs["metadata"].update(metadata)
        if customer_id:
            session_kwargs["customer"] = customer_id

        mode = self._config.mode
        if mode == "subscription":
            session_kwargs["line_items"] = [
                {
                    "price": price_tier.price_id,
                    "quantity": 1,
                }
            ]
            session_kwargs["mode"] = "subscription"
            subscription_data: Dict[str, Any] = {
                "metadata": {
                    "user_id": user_id,
                    "tier": price_tier.key,
                }
            }
            if self._config.trial_period_days:
                subscription_data["trial_period_days"] = self._config.trial_period_days
            session_kwargs["subscription_data"] = subscription_data
        elif mode == "buy_once":
            session_kwargs["line_items"] = [self._build_buy_once_line_item(price_tier)]
            session_kwargs["mode"] = "payment"
        else:
            raise BillingError(f"未対応の billing.mode です: {mode}")

        return session_kwargs

    def _check_rate_limit(self) -> None:
        """レート制限チェック"""
        now = time.time()
        with self._lock:
            # 古いタイムスタンプを削除
            cutoff = now - self._rate_limit_window
            self._api_calls = [call_time for call_time in self._api_calls if call_time > cutoff]

            if len(self._api_calls) >= self._rate_limit_calls:
                raise BillingError(f"レート制限を超えました。1分間に{self._rate_limit_calls}回以内に抑えてください")

            self._api_calls.append(now)

    def create_billing_portal_session(
        self,
        *,
        customer_id: str,
        return_url: str,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """顧客向けのBilling Portalセッションを作成します."""

        if not customer_id:
            raise BillingError("customer_id が指定されていません")
        if not return_url:
            raise BillingError("return_url が指定されていません")

        # リトライ機能付きAPI呼び出しを使用
        session = self._api_call_with_retry(stripe.billing_portal.Session.create, customer=customer_id, return_url=return_url)

        existing = self._storage.get_by_customer(customer_id) or {}
        record = {
            **existing,
            "customer_id": customer_id,
            "user_id": user_id or existing.get("user_id"),
            "mode": self._config.mode,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "last_event": "billing_portal.session.created",
        }
        self._storage.upsert_subscription(customer_id, record)

        return {
            "id": session.get("id"),
            "url": session.get("url"),
        }

    def _api_call_with_retry(self, api_func, *args, max_retries: int = 3, **kwargs) -> Any:
        """リトライ機能付きAPI呼び出し"""
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                # レート制限チェック
                self._check_rate_limit()
                return api_func(*args, **kwargs)
            except stripe.error.RateLimitError as e:
                last_error = e
                if attempt < max_retries:
                    wait_time = min(2 ** attempt, 10)  # 指数バックオフ（最大10秒）
                    logger.warning(f"レート制限エラー、再試行まで{wait_time}秒待機: {e}")
                    time.sleep(wait_time)
                    continue
            except (stripe.error.APIConnectionError, stripe.error.APIError) as e:
                last_error = e
                if attempt < max_retries:
                    wait_time = min(2 ** attempt, 5)  # 指数バックオフ（最大5秒）
                    logger.warning(f"APIエラー、再試行まで{wait_time}秒待機: {e}")
                    time.sleep(wait_time)
                    continue
            except Exception as e:
                # その他のエラーは即座に失敗
                raise BillingError(f"API呼び出しエラー: {e}") from e

        # 全てのリトライが失敗した場合
        raise BillingError(f"API呼び出しが{max_retries}回失敗しました: {last_error}") from last_error

    def _build_buy_once_line_item(self, price_tier: PriceTier) -> Dict[str, Any]:
        """買い切りモード用に3ヶ月分の料金を計算してLineItemを組み立てる."""

        try:
            base_price = stripe.Price.retrieve(price_tier.price_id)
        except stripe.error.StripeError as exc:  # type: ignore[attr-defined]
            raise BillingError(f"Stripe価格の取得に失敗しました: {exc}") from exc

        unit_amount = base_price.get("unit_amount")
        currency = base_price.get("currency")
        product_id = base_price.get("product")

        if unit_amount is None:
            raise BillingError("Stripe価格に unit_amount が含まれていません")
        if not product_id:
            raise BillingError("Stripe価格に product が含まれていません")

        if currency and currency.lower() != self._config.currency.lower():
            raise BillingError(
                "Stripe価格の通貨と config.billing.currency が一致していません"
            )

        amount_three_months = int(unit_amount) * 3
        if amount_three_months <= 0:
            raise BillingError("計算された買い切り金額が不正です")

        return {
            "price_data": {
                "currency": self._config.currency,
                "product": product_id,
                "unit_amount": amount_three_months,
            },
            "quantity": 1,
        }

    def handle_webhook(self, payload: bytes, signature: str) -> Dict[str, Any]:
        secret = self._config.webhook_secret
        if self._config.webhook_enabled and not secret:
            raise BillingError(
                "Stripe webhook シークレットが設定されていません (.env に STRIPE_WEBHOOK_SECRET を設定してください)"
            )

        event = self._construct_event(payload, signature, secret)
        event_type = event.get("type")
        event_id = event.get("id")
        data_object = event.get("data", {}).get("object", {})

        if event_id and self._event_log.has(event_id):
            logger.info("Stripeイベント %s は既に処理済みのためスキップします", event_id)
            return {
                "processed": False,
                "reason": "Duplicate event",
                "event_type": event_type,
                "event_id": event_id,
            }

        handler_name = self._WEBHOOK_HANDLERS.get(event_type)
        if handler_name is not None:
            result = getattr(self, handler_name)(data_object, event_type)
        else:
            logger.info("Unhandled Stripe event received: %s", event_type)
            result = {"processed": False, "reason": "Unhandled event", "event_type": event_type}

        if event_id:
            self._event_log.record(event_id, event_type or "unknown")
        return result

    # Stripe イベントタイプ -> ハンドラメソッド名のディスパッチテーブル
    _WEBHOOK_HANDLERS = {
        "customer.subscription.created": "_handle_subscription_update",
        "customer.subscription.updated": "_handle_subscription_update",
        "customer.subscription.deleted": "_handle_subscription_update",
        "customer.subscription.trial_will_end": "_handle_trial_will_end",
        "checkout.session.completed": "_handle_checkout_completed",
        "invoice.payment_succeeded": "_handle_invoice_payment",
        "invoice.payment_failed": "_handle_invoice_payment_failed",
        "invoice.payment_action_required": "_handle_invoice_payment_action_required",
    }

    # ------------------------------------------------------------------
    # Stripe back-office operations
    # ------------------------------------------------------------------
    def get_or_create_customer(
        self,
        *,
        user_id: str,
        email: Optional[str] = None,
        name: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        """ユーザーIDからStripe顧客IDを返却。存在しない場合は作成します."""

        if not user_id:
            raise BillingError("user_id が指定されていません")

        existing = self._storage.get_by_user(user_id)
        if existing and existing.get("customer_id"):
            return existing["customer_id"]

        metadata_payload = {"user_id": user_id}
        if metadata:
            metadata_payload.update(metadata)

        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata=metadata_payload,
            )
        except stripe.error.StripeError as exc:  # type: ignore[attr-defined]
            raise BillingError(f"Stripe顧客の作成に失敗しました: {exc}") from exc

        customer_id = customer.get("id")
        if not customer_id:
            raise BillingError("Stripe顧客IDを取得できませんでした")

        record = {
            "customer_id": customer_id,
            "user_id": user_id,
            "mode": self._config.mode,
            "status": "customer_created",
            "updated_at": datetime.now(timezone.utc).isoformat() + "Z",
            "last_event": "customer.created",
        }
        self._storage.upsert_subscription(customer_id, record)
        return customer_id

    def refresh_subscription_from_stripe(self, customer_id: str) -> Dict[str, Any]:
        """Stripeから最新サブスクリプション情報を取得し、ローカルストレージへ反映します."""

        if not customer_id:
            raise BillingError("customer_id が指定されていません")

        try:
            response = stripe.Subscription.list(
                customer=customer_id,
                status="all",
                limit=1,
                expand=["data.items.data.price"],
            )
        except stripe.error.StripeError as exc:  # type: ignore[attr-defined]
            raise BillingError(f"Stripeサブスクリプションの取得に失敗しました: {exc}") from exc

        subscription = (response or {}).get("data", [])
        if not subscription:
            record = {
                "customer_id": customer_id,
                "status": "not_found",
                "mode": self._config.mode,
                "updated_at": datetime.now(timezone.utc).isoformat() + "Z",
                "last_event": "sync.subscription.missing",
            }
            self._storage.upsert_subscription(customer_id, record)
            return record

        sub = subscription[0]
        record = self._build_subscription_record(sub, "sync.subscription")
        self._storage.upsert_subscription(customer_id, record)
        return record

    def cancel_subscription(
        self,
        customer_id: str,
        *,
        subscription_id: Optional[str] = None,
        at_period_end: bool = True,
    ) -> Dict[str, Any]:
        """指定したサブスクリプションをキャンセルします (デフォルトで期末キャンセル)."""

        if not customer_id:
            raise BillingError("customer_id が指定されていません")

        existing = self._storage.get_by_customer(customer_id) or {}
        sub_id = subscription_id or existing.get("subscription_id")
        if not sub_id:
            raise BillingError("キャンセル対象の subscription_id が見つかりません")

        try:
            updated = stripe.Subscription.modify(
                sub_id,
                cancel_at_period_end=at_period_end,
            )
        except stripe.error.StripeError as exc:  # type: ignore[attr-defined]
            raise BillingError(f"Stripeサブスクリプションのキャンセルに失敗しました: {exc}") from exc

        record = self._build_subscription_record(
            updated,
            "subscription.cancel.requested" if at_period_end else "subscription.cancel.immediate",
        )
        self._storage.upsert_subscription(customer_id, record)
        return record

    def change_subscription_tier(
        self,
        customer_id: str,
        target_tier_key: str,
        *,
        subscription_id: Optional[str] = None,
        invoice_now: bool = False,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """サブスクリプションを別ティアへ変更します."""

        if not customer_id:
            raise BillingError("customer_id が指定されていません")
        if not target_tier_key:
            raise BillingError("target_tier_key が指定されていません")

        price_tier = self._config.resolve_price(target_tier_key)

        existing = self._storage.get_by_customer(customer_id) or {}
        sub_id = subscription_id or existing.get("subscription_id")
        if not sub_id:
            raise BillingError("変更対象の subscription_id が見つかりません")

        try:
            current_subscription = stripe.Subscription.retrieve(
                sub_id,
                expand=["items.data.price"],
            )
        except stripe.error.StripeError as exc:  # type: ignore[attr-defined]
            raise BillingError(f"Stripeサブスクリプションの取得に失敗しました: {exc}") from exc

        items = (current_subscription.get("items") or {}).get("data", [])
        if not items:
            raise BillingError("既存サブスクリプションにアイテムが存在しません")
        primary_item = items[0]
        subscription_item_id = primary_item.get("id")
        if not subscription_item_id:
            raise BillingError("subscription_item_id を取得できませんでした")

        metadata_payload = (current_subscription.get("metadata") or {}).copy()
        metadata_payload["tier"] = price_tier.key
        if existing.get("user_id") and "user_id" not in metadata_payload:
            metadata_payload["user_id"] = existing.get("user_id")
        if metadata:
            metadata_payload.update(metadata)

        proration_behavior = "always_invoice" if invoice_now else "create_prorations"

        try:
            updated = stripe.Subscription.modify(
                sub_id,
                items=[{"id": subscription_item_id, "price": price_tier.price_id}],
                proration_behavior=proration_behavior,
                metadata=metadata_payload,
                cancel_at_period_end=False,
            )
        except stripe.error.StripeError as exc:  # type: ignore[attr-defined]
            raise BillingError(f"Stripeサブスクリプションの更新に失敗しました: {exc}") from exc

        record = self._build_subscription_record(updated, "subscription.change_tier")
        self._storage.upsert_subscription(customer_id, record)
        return record

    def generate_subscription_report(self) -> Dict[str, Any]:
        """現在の課金口座状態を集計して返します."""

        records = self._storage.all_records()
        status_counter: Counter[str] = Counter()
        tier_counter: Counter[str] = Counter()
        total_revenue_cents = 0
        outstanding_cents = 0
        action_required: List[str] = []
        past_due: List[str] = []
        trial_will_end: List[str] = []

        for customer_id, record in records.items():
            status = record.get("status") or "unknown"
            status_counter[status] += 1

            tier_key = record.get("tier_key") or self._resolve_tier_key_from_price(record.get("tier_price_id"))
            if tier_key:
                tier_counter[tier_key] += 1

            amount_paid = record.get("amount_paid")
            if isinstance(amount_paid, int):
                total_revenue_cents += max(0, amount_paid)

            amount_due = record.get("amount_due")
            if isinstance(amount_due, int):
                outstanding_cents += max(0, amount_due)

            if status in {"past_due", "unpaid"}:
                past_due.append(customer_id)
            if status in {"action_required", "requires_payment_method"}:
                action_required.append(customer_id)
            if record.get("last_event") == "customer.subscription.trial_will_end":
                trial_will_end.append(customer_id)

        report = {
            "generated_at": datetime.now(timezone.utc).isoformat() + "Z",
            "currency": self._config.currency,
            "counts": {
                "customers": len(records),
                "active": status_counter.get("active", 0),
                "trialing": status_counter.get("trialing", 0),
                "past_due": status_counter.get("past_due", 0),
                "canceled": status_counter.get("canceled", 0),
            },
            "status_breakdown": dict(status_counter),
            "tier_breakdown": dict(tier_counter),
            "revenue_cents": {
                "collected_total": total_revenue_cents,
                "outstanding_total": outstanding_cents,
            },
            "alerts": {
                "past_due_customers": past_due,
                "action_required_customers": action_required,
                "trial_will_end_customers": trial_will_end,
            },
        }
        return report

    def _construct_event(
        self,
        payload: bytes,
        signature: str,
        secret: Optional[str],
    ) -> Dict[str, Any]:
        if secret:
            return stripe.Webhook.construct_event(payload=payload, sig_header=signature, secret=secret)
        # シークレットが無効（Webhook未使用）の場合は直接JSONとして扱う
        return json.loads(payload.decode("utf-8"))

    def _handle_subscription_update(self, subscription: Dict[str, Any], event_type: str) -> Dict[str, Any]:
        record = self._build_subscription_record(subscription, event_type)
        customer_id = record.get("customer_id")
        if customer_id:
            self._storage.upsert_subscription(customer_id, record)
        return {"processed": True, "event_type": event_type, "customer_id": customer_id}

    def _handle_trial_will_end(self, subscription: Dict[str, Any], event_type: str) -> Dict[str, Any]:
        record = self._build_subscription_record(subscription, event_type)
        record["status"] = "trialing"
        record["next_action"] = "trial_will_end"
        customer_id = record.get("customer_id")
        if customer_id:
            self._storage.upsert_subscription(customer_id, record)
        return {"processed": True, "event_type": event_type, "customer_id": customer_id}

    def _handle_invoice_payment_failed(self, invoice: Dict[str, Any], event_type: str) -> Dict[str, Any]:
        customer_id = invoice.get("customer")
        existing = self._storage.get_by_customer(customer_id) or {}
        record = {
            **existing,
            "customer_id": customer_id,
            "status": "past_due",
            "mode": self._config.mode,
            "amount_due": invoice.get("amount_due"),
            "attempt_count": invoice.get("attempt_count"),
            "updated_at": datetime.now(timezone.utc).isoformat() + "Z",
            "last_event": event_type,
        }
        if customer_id:
            self._storage.upsert_subscription(customer_id, record)
        return {"processed": True, "event_type": event_type, "customer_id": customer_id}

    def _handle_invoice_payment_action_required(self, invoice: Dict[str, Any], event_type: str) -> Dict[str, Any]:
        customer_id = invoice.get("customer")
        existing = self._storage.get_by_customer(customer_id) or {}
        record = {
            **existing,
            "customer_id": customer_id,
            "status": "action_required",
            "mode": self._config.mode,
            "amount_due": invoice.get("amount_due") or existing.get("amount_due"),
            "updated_at": datetime.now(timezone.utc).isoformat() + "Z",
            "last_event": event_type,
        }
        if customer_id:
            self._storage.upsert_subscription(customer_id, record)
        return {"processed": True, "event_type": event_type, "customer_id": customer_id}

    def _handle_checkout_completed(self, session_obj: Dict[str, Any], event_type: str) -> Dict[str, Any]:
        mode = session_obj.get("mode")
        customer_id = session_obj.get("customer")
        subscription_id = session_obj.get("subscription")
        metadata = session_obj.get("metadata", {})
        user_id = metadata.get("user_id")
        tier_key = metadata.get("tier")

        record = {
            "customer_id": customer_id,
            "subscription_id": subscription_id,
            "status": "completed",
            "tier_key": tier_key,
            "tier_price_id": session_obj.get("display_items", [{}])[0].get("plan", {}).get("id")
            if mode == "subscription"
            else session_obj.get("line_items", [{}])[0].get("price", {}).get("id"),
            "user_id": user_id,
            "mode": mode,
            "updated_at": datetime.now(timezone.utc).isoformat() + "Z",
            "last_event": event_type,
            "subscription_item_id": None,
        }
        if customer_id:
            self._storage.upsert_subscription(customer_id, record)
        return {"processed": True, "event_type": event_type, "customer_id": customer_id}

    def _handle_invoice_payment(self, invoice: Dict[str, Any], event_type: str) -> Dict[str, Any]:
        customer_id = invoice.get("customer")
        subscription_id = invoice.get("subscription")
        lines = invoice.get("lines", {}).get("data", [])
        tier_price_id: Optional[str] = None
        if lines:
            tier_price_id = lines[0].get("price", {}).get("id")
        metadata = invoice.get("metadata", {})
        user_id = metadata.get("user_id")
        tier_key = metadata.get("tier")
        amount_paid = invoice.get("amount_paid")

        existing = self._storage.get_by_customer(customer_id) or {}
        record = {
            **existing,
            "customer_id": customer_id,
            "subscription_id": subscription_id,
            "status": "active",
            "tier_price_id": tier_price_id or existing.get("tier_price_id"),
            "tier_key": tier_key or existing.get("tier_key"),
            "user_id": user_id or existing.get("user_id"),
            "mode": self._config.mode,
            "amount_paid": amount_paid,
            "updated_at": datetime.now(timezone.utc).isoformat() + "Z",
            "last_event": event_type,
        }
        if customer_id:
            self._storage.upsert_subscription(customer_id, record)
        return {"processed": True, "event_type": event_type, "customer_id": customer_id}

    def get_subscription_status(self, user_id: str) -> Optional[Dict[str, Any]]:
        """ユーザーIDに紐づく最新のサブスクリプション状態を返します."""
        return self._storage.get_by_user(user_id)


__all__ = [
    "BillingError",
    "BillingConfig",
    "BillingStorage",
    "PriceTier",
    "StripeBillingService",
]
