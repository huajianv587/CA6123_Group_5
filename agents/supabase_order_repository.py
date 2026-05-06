"""
OrderAgent 专用：对接团队 schema 中的 orders + order_addresses（无外键 json 地址列）。

环境变量：
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY | SUPABASE_PUBLISHABLE_KEY | SUPABASE_ANON_KEY | SUPABASE_KEY
  SUPABASE_ORDERS_TABLE           默认 orders
  SUPABASE_ORDER_ADDRESSES_TABLE  默认 order_addresses
  SUPABASE_ORDER_TIME_COLUMN      默认 create_time
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


def _format_ts(val: Any) -> Optional[str]:
    if val is None:
        return None
    if isinstance(val, str):
        s = val.replace("T", " ")
        return s[:19] if len(s) >= 19 else s
    if hasattr(val, "strftime"):
        return val.strftime("%Y-%m-%d %H:%M:%S")
    return str(val)


def _as_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _status_to_code(status: str) -> str:
    """orders.status 为中文 CHECK 值，映射为 OrderAgent 内部 status_code。"""
    m = {
        "待发货": "pending_ship",
        "已发货": "shipped",
        "已完成": "completed",
        "已取消": "cancelled",
    }
    return m.get((status or "").strip(), "")


def _derive_modify_cancel(status_code: str, status_label: str) -> Tuple[bool, bool]:
    code = (status_code or "").lower()
    st = status_label or ""
    if code == "pending_ship" or "待发货" in st:
        return True, True
    if code in ("cancelled", "canceled", "completed") or "已取消" in st or "已完成" in st:
        return False, False
    if code == "shipped" or "已发货" in st:
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

    def _fetch_current_address_row(self, order_id: str) -> Optional[Dict[str, Any]]:
        r = (
            self._client.table(self._addresses)
            .select("*")
            .eq("order_id", order_id)
            .eq("is_current", True)
            .limit(1)
            .execute()
        )
        rows = r.data or []
        return rows[0] if rows else None

    def _merge_order_and_address(
        self, order: Dict[str, Any], address: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        oid = str(order.get("order_id", ""))
        status = str(order.get("status") or "")
        status_code = _status_to_code(status)

        if address:
            recv = {
                "name": str(address.get("name", "")),
                "phone": str(address.get("phone", "")),
                "province": str(address.get("province", "")),
                "city": str(address.get("city", "")),
                "district": str(address.get("district", "")),
                "detail": str(address.get("detail", "")),
            }
        else:
            recv = {
                "name": "",
                "phone": "",
                "province": "",
                "city": "",
                "district": "",
                "detail": "",
            }

        cm = order.get("can_modify_address")
        cc = order.get("can_cancel")
        if cm is None or cc is None:
            dm, dc = _derive_modify_cancel(status_code, status)
            if cm is None:
                cm = dm
            if cc is None:
                cc = dc

        create_time = _format_ts(order.get("create_time"))
        ship_time = _format_ts(order.get("ship_time"))

        return {
            "order_id": oid,
            "status": status,
            "status_code": status_code,
            "product_name": str(order.get("product_name") or ""),
            "product_price": _as_float(order.get("product_price")),
            "quantity": int(order.get("quantity") or 0) or 1,
            "total_amount": _as_float(order.get("total_amount")),
            "create_time": create_time or "",
            "ship_time": ship_time,
            "receive_address": recv,
            "can_modify_address": bool(cm),
            "can_cancel": bool(cc),
            "tracking_number": order.get("tracking_number"),
            "user_id": order.get("user_id"),
            "product_id": order.get("product_id"),
            "shipping_fee": _as_float(order.get("shipping_fee")),
        }

    def _address_map_for_orders(self, order_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        if not order_ids:
            return {}
        r = (
            self._client.table(self._addresses)
            .select("*")
            .in_("order_id", order_ids)
            .eq("is_current", True)
            .execute()
        )
        out: Dict[str, Dict[str, Any]] = {}
        for row in r.data or []:
            oid = row.get("order_id")
            if oid and oid not in out:
                out[str(oid)] = row
        return out

    def fetch_by_order_id(self, order_id: str) -> Optional[Dict[str, Any]]:
        if not order_id:
            return None
        q = (
            self._client.table(self._orders)
            .select("*")
            .eq("order_id", order_id)
            .limit(1)
            .execute()
        )
        rows = q.data or []
        if not rows:
            return None
        addr = self._fetch_current_address_row(order_id)
        return self._merge_order_and_address(rows[0], addr)

    def fetch_recent(self, limit: int = 2) -> List[Dict[str, Any]]:
        q = (
            self._client.table(self._orders)
            .select("*")
            .order(self._time_column, desc=True)
            .limit(limit)
            .execute()
        )
        orders = q.data or []
        ids = [str(o["order_id"]) for o in orders if o.get("order_id")]
        amap = self._address_map_for_orders(ids)
        return [self._merge_order_and_address(o, amap.get(str(o.get("order_id")))) for o in orders]

    def fetch_all(self, max_rows: int = 100) -> List[Dict[str, Any]]:
        q = (
            self._client.table(self._orders)
            .select("*")
            .order(self._time_column, desc=True)
            .limit(max_rows)
            .execute()
        )
        orders = q.data or []
        ids = [str(o["order_id"]) for o in orders if o.get("order_id")]
        amap = self._address_map_for_orders(ids)
        return [self._merge_order_and_address(o, amap.get(str(o.get("order_id")))) for o in orders]

    def update_cancelled(self, order_id: str) -> Tuple[bool, str]:
        """orders：状态改为已取消，并关闭改址/取消；写入 cancel_time。"""
        payload: Dict[str, Any] = {
            "status": "已取消",
            "can_cancel": False,
            "can_modify_address": False,
            "cancel_time": datetime.now(timezone.utc).isoformat(),
        }
        r = self._client.table(self._orders).update(payload).eq("order_id", order_id).execute()
        if r.data:
            return True, ""
        return False, "订单未更新（检查 order_id、RLS 与 orders 表结构）。"

    def update_receive_address(self, order_id: str, addr: Dict[str, str]) -> Tuple[bool, str]:
        """
        order_addresses：将旧当前地址 is_current=false，再插入新当前地址。
        addr 键：name, phone, province, city, district, detail
        """
        self._client.table(self._addresses).update({"is_current": False}).eq("order_id", order_id).eq(
            "is_current", True
        ).execute()

        ins: Dict[str, Any] = {
            "order_id": order_id,
            "name": addr.get("name") or "收件人",
            "phone": addr.get("phone") or "",
            "province": addr.get("province") or "",
            "city": addr.get("city") or "",
            "district": addr.get("district") or "",
            "detail": addr.get("detail") or "",
            "is_current": True,
        }
        try:
            self._client.table(self._addresses).insert(ins).execute()
            return True, ""
        except Exception as e:
            return False, str(e)
