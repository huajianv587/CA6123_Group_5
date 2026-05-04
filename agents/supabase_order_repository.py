"""
从 Supabase 读取订单（及可选取消更新）。

环境变量（至少需要 URL + Key）：
  SUPABASE_URL                 Project URL，如 https://<ref>.supabase.co
  SUPABASE_SERVICE_ROLE_KEY    服务端脚本优先（绕过 RLS，勿暴露给前端）
  SUPABASE_PUBLISHABLE_KEY     控制台「Publishable key」（sb_publishable_...）
  SUPABASE_ANON_KEY            传统 JWT anon key（eyJ...）；与 publishable 二选一即可
  SUPABASE_KEY                 上述任一 key 的兜底变量名
  SUPABASE_ORDERS_TABLE       表名，默认 orders
  SUPABASE_ORDER_TIME_COLUMN  用于排序的下单时间列，默认 create_time（常见备选 created_at）
  SUPABASE_ORDER_ADDRESS_MODE   写收货地址：json（默认，更新 receive_address jsonb）或 flat（更新拆列）

表行 → OrderAgent 内部字典的约定见 SupabaseOrderRepository._row_to_order 文档字符串。
"""
from __future__ import annotations

import json
import os
from datetime import datetime
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


def _parse_address_blob(raw: Any) -> Optional[Dict[str, str]]:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            d = json.loads(raw)
            return d if isinstance(d, dict) else None
        except json.JSONDecodeError:
            return None
    return None


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
    """PostgREST 读订单；列名可与下述约定不一致时在 _row_to_order 中扩展映射。"""

    def __init__(self, url: str, key: str, table: str, time_column: str):
        from supabase import create_client

        self._client = create_client(url, key)
        self._table = table
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
        table = (os.environ.get("SUPABASE_ORDERS_TABLE") or "orders").strip()
        time_column = (os.environ.get("SUPABASE_ORDER_TIME_COLUMN") or "create_time").strip()
        try:
            return cls(url, key, table, time_column)
        except ImportError:
            return None

    def _row_to_order(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """
        将一行映射为 OrderAgent 使用的结构。

        期望列（可缺省，缺省则用合理默认）：
          order_id（或 id 作为订单号）, status, status_code,
          product_name, product_price, quantity, total_amount,
          create_time 或 created_at, ship_time,
          receive_address（json/jsonb）或
            recipient_name + phone + province + city + district + detail（或 detail_address）
          tracking_number, can_modify_address, can_cancel（布尔，可缺省则由状态推导）
        """
        oid_raw = row.get("order_id")
        if oid_raw is not None:
            oid = str(oid_raw)
        elif row.get("id") is not None:
            oid = str(row["id"])
        else:
            oid = ""

        status = str(row.get("status") or "")
        status_code = str(row.get("status_code") or "")

        addr = _parse_address_blob(row.get("receive_address"))
        if not addr:
            addr = {
                "name": str(row.get("recipient_name") or row.get("receiver_name") or ""),
                "phone": str(row.get("phone") or row.get("recipient_phone") or ""),
                "province": str(row.get("province") or ""),
                "city": str(row.get("city") or ""),
                "district": str(row.get("district") or ""),
                "detail": str(
                    row.get("detail")
                    or row.get("detail_address")
                    or row.get("address_detail")
                    or ""
                ),
            }

        cm = row.get("can_modify_address")
        cc = row.get("can_cancel")
        if cm is None or cc is None:
            dm, dc = _derive_modify_cancel(status_code, status)
            if cm is None:
                cm = dm
            if cc is None:
                cc = dc

        create_time = _format_ts(
            row.get("create_time") if "create_time" in row else row.get("created_at")
        )
        ship_time = _format_ts(row.get("ship_time"))

        return {
            "order_id": oid,
            "status": status,
            "status_code": status_code,
            "product_name": str(row.get("product_name") or ""),
            "product_price": _as_float(row.get("product_price")),
            "quantity": int(row.get("quantity") or 0) or 1,
            "total_amount": _as_float(row.get("total_amount")),
            "create_time": create_time or "",
            "ship_time": ship_time,
            "receive_address": addr,
            "can_modify_address": bool(cm),
            "can_cancel": bool(cc),
            "tracking_number": row.get("tracking_number"),
        }

    def fetch_by_order_id(self, order_id: str) -> Optional[Dict[str, Any]]:
        if not order_id:
            return None
        q = (
            self._client.table(self._table)
            .select("*")
            .eq("order_id", order_id)
            .limit(1)
            .execute()
        )
        rows = q.data or []
        if not rows:
            q2 = (
                self._client.table(self._table)
                .select("*")
                .eq("id", order_id)
                .limit(1)
                .execute()
            )
            rows = q2.data or []
        if not rows:
            return None
        return self._row_to_order(rows[0])

    def fetch_recent(self, limit: int = 2) -> List[Dict[str, Any]]:
        q = (
            self._client.table(self._table)
            .select("*")
            .order(self._time_column, desc=True)
            .limit(limit)
            .execute()
        )
        return [self._row_to_order(r) for r in (q.data or [])]

    def fetch_all(self, max_rows: int = 100) -> List[Dict[str, Any]]:
        q = (
            self._client.table(self._table)
            .select("*")
            .order(self._time_column, desc=True)
            .limit(max_rows)
            .execute()
        )
        return [self._row_to_order(r) for r in (q.data or [])]

    def update_cancelled(self, order_id: str) -> Tuple[bool, str]:
        """将订单标为已取消（需表上存在对应列；RLS 需允许 update）。"""
        payload = {
            "status": "已取消",
            "status_code": "cancelled",
            "can_cancel": False,
            "can_modify_address": False,
        }
        cancel_col = (os.environ.get("SUPABASE_ORDER_CANCEL_TIME_COLUMN") or "").strip()
        if cancel_col:
            payload[cancel_col] = datetime.now().isoformat()

        r = self._client.table(self._table).update(payload).eq("order_id", order_id).execute()
        if r.data:
            return True, ""
        r2 = self._client.table(self._table).update(payload).eq("id", order_id).execute()
        if r2.data:
            return True, ""
        return False, "数据库未更新到任何行（检查 order_id / id 列、RLS 与列名）。"

    def update_receive_address(self, order_id: str, addr: Dict[str, str]) -> Tuple[bool, str]:
        """
        更新收货地址。addr 键：name, phone, province, city, district, detail。
        SUPABASE_ORDER_ADDRESS_MODE=json：写入 receive_address；
        flat：写入 recipient_name, phone, province, city, district, detail。
        """
        mode = (os.environ.get("SUPABASE_ORDER_ADDRESS_MODE") or "json").strip().lower()
        if mode == "flat":
            payload: Dict[str, Any] = {
                "recipient_name": addr.get("name", ""),
                "phone": addr.get("phone", ""),
                "province": addr.get("province", ""),
                "city": addr.get("city", ""),
                "district": addr.get("district", ""),
                "detail": addr.get("detail", ""),
            }
        else:
            payload = {"receive_address": addr}

        r = self._client.table(self._table).update(payload).eq("order_id", order_id).execute()
        if r.data:
            return True, ""
        r2 = self._client.table(self._table).update(payload).eq("id", order_id).execute()
        if r2.data:
            return True, ""
        return False, "地址未写入数据库（列名/RLS/order_id 是否与表一致？可尝试 SUPABASE_ORDER_ADDRESS_MODE=flat）。"
