from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Optional


def _format_ts(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        normalized = value.replace("T", " ")
        return normalized[:19] if len(normalized) >= 19 else normalized
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _status_to_code(status: str) -> str:
    mapping = {
        "待发货": "pending_ship",
        "已发货": "shipped",
        "已完成": "completed",
        "已取消": "cancelled",
    }
    return mapping.get((status or "").strip(), "")


def _derive_order_flags(status_code: str, status_label: str) -> tuple[bool, bool]:
    code = (status_code or "").lower()
    label = status_label or ""
    if code == "pending_ship" or "待发货" in label:
        return True, True
    if code in {"cancelled", "canceled", "completed"} or "已取消" in label or "已完成" in label:
        return False, False
    if code == "shipped" or "已发货" in label:
        return False, False
    return False, False


class SupabaseOrderRepository:
    def __init__(self, url: str, key: str, orders_table: str, addresses_table: str, time_column: str):
        from supabase import create_client

        self._client = create_client(url, key)
        self._orders = orders_table
        self._addresses = addresses_table
        self._time_column = time_column

    @classmethod
    def from_env(cls) -> Optional["SupabaseOrderRepository"]:
        url = (os.environ.get("SUPABASE_URL") or "").strip()
        key = (
            (os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
            or (os.environ.get("SUPABASE_PUBLISHABLE_KEY") or "").strip()
            or (os.environ.get("SUPABASE_ANON_KEY") or "").strip()
            or (os.environ.get("SUPABASE_KEY") or "").strip()
        )
        if not url or not key:
            return None
        orders_table = (os.environ.get("SUPABASE_ORDERS_TABLE") or "orders").strip()
        addresses_table = (os.environ.get("SUPABASE_ORDER_ADDRESSES_TABLE") or "order_addresses").strip()
        time_column = (os.environ.get("SUPABASE_ORDER_TIME_COLUMN") or "create_time").strip()
        try:
            return cls(url, key, orders_table, addresses_table, time_column)
        except ImportError:
            return None

    def _fetch_current_address_row(self, order_id: str) -> Optional[dict[str, Any]]:
        response = (
            self._client.table(self._addresses)
            .select("*")
            .eq("order_id", order_id)
            .eq("is_current", True)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        return rows[0] if rows else None

    def _address_map_for_orders(self, order_ids: list[str]) -> dict[str, dict[str, Any]]:
        if not order_ids:
            return {}
        response = (
            self._client.table(self._addresses)
            .select("*")
            .in_("order_id", order_ids)
            .eq("is_current", True)
            .execute()
        )
        output: dict[str, dict[str, Any]] = {}
        for row in response.data or []:
            order_id = row.get("order_id")
            if order_id and str(order_id) not in output:
                output[str(order_id)] = row
        return output

    def _merge_order_and_address(self, order: dict[str, Any], address: Optional[dict[str, Any]]) -> dict[str, Any]:
        status = str(order.get("status") or "")
        status_code = _status_to_code(status)
        if address:
            receive_address = {
                "name": str(address.get("name", "")),
                "phone": str(address.get("phone", "")),
                "province": str(address.get("province", "")),
                "city": str(address.get("city", "")),
                "district": str(address.get("district", "")),
                "detail": str(address.get("detail", "")),
            }
        else:
            receive_address = {"name": "", "phone": "", "province": "", "city": "", "district": "", "detail": ""}

        can_modify = order.get("can_modify_address")
        can_cancel = order.get("can_cancel")
        if can_modify is None or can_cancel is None:
            derived_modify, derived_cancel = _derive_order_flags(status_code, status)
            can_modify = derived_modify if can_modify is None else can_modify
            can_cancel = derived_cancel if can_cancel is None else can_cancel

        return {
            "order_id": str(order.get("order_id", "")),
            "status": status,
            "status_code": status_code,
            "product_name": str(order.get("product_name") or ""),
            "product_price": _as_float(order.get("product_price")),
            "quantity": int(order.get("quantity") or 0) or 1,
            "total_amount": _as_float(order.get("total_amount")),
            "create_time": _format_ts(order.get("create_time")) or "",
            "ship_time": _format_ts(order.get("ship_time")),
            "receive_address": receive_address,
            "can_modify_address": bool(can_modify),
            "can_cancel": bool(can_cancel),
            "tracking_number": order.get("tracking_number"),
            "user_id": order.get("user_id"),
            "product_id": order.get("product_id"),
            "shipping_fee": _as_float(order.get("shipping_fee")),
        }

    def fetch_by_order_id(self, order_id: str) -> Optional[dict[str, Any]]:
        if not order_id:
            return None
        response = self._client.table(self._orders).select("*").eq("order_id", order_id).limit(1).execute()
        rows = response.data or []
        if not rows:
            return None
        address = self._fetch_current_address_row(order_id)
        return self._merge_order_and_address(rows[0], address)

    def fetch_recent(self, limit: int = 2) -> list[dict[str, Any]]:
        response = (
            self._client.table(self._orders)
            .select("*")
            .order(self._time_column, desc=True)
            .limit(limit)
            .execute()
        )
        orders = response.data or []
        ids = [str(order["order_id"]) for order in orders if order.get("order_id")]
        address_map = self._address_map_for_orders(ids)
        return [self._merge_order_and_address(order, address_map.get(str(order.get("order_id")))) for order in orders]

    def fetch_all(self, max_rows: int = 100) -> list[dict[str, Any]]:
        response = (
            self._client.table(self._orders)
            .select("*")
            .order(self._time_column, desc=True)
            .limit(max_rows)
            .execute()
        )
        orders = response.data or []
        ids = [str(order["order_id"]) for order in orders if order.get("order_id")]
        address_map = self._address_map_for_orders(ids)
        return [self._merge_order_and_address(order, address_map.get(str(order.get("order_id")))) for order in orders]

    def update_cancelled(self, order_id: str) -> tuple[bool, str]:
        payload: dict[str, Any] = {
            "status": "已取消",
            "can_cancel": False,
            "can_modify_address": False,
            "cancel_time": datetime.now(timezone.utc).isoformat(),
        }
        response = self._client.table(self._orders).update(payload).eq("order_id", order_id).execute()
        if response.data:
            return True, ""
        return False, "订单未更新，请检查 order_id、RLS 与 orders 表结构。"

    def update_receive_address(self, order_id: str, address: dict[str, str]) -> tuple[bool, str]:
        self._client.table(self._addresses).update({"is_current": False}).eq("order_id", order_id).eq("is_current", True).execute()
        payload: dict[str, Any] = {
            "order_id": order_id,
            "name": address.get("name") or "收件人",
            "phone": address.get("phone") or "",
            "province": address.get("province") or "",
            "city": address.get("city") or "",
            "district": address.get("district") or "",
            "detail": address.get("detail") or "",
            "is_current": True,
        }
        try:
            self._client.table(self._addresses).insert(payload).execute()
            return True, ""
        except Exception as exc:
            return False, str(exc)
