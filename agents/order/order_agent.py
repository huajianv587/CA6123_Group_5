import re
from typing import Any, Optional

from agents.base_agent import AgentResponse, BaseAgent, Message
from agents.order.supabase_order_repository import SupabaseOrderRepository


class OrderAgent(BaseAgent):
    def __init__(self, store=None, order_repository=None, **kwargs):
        super().__init__("order", "OrderAgent", store=store, **kwargs)
        self._repo = order_repository if order_repository is not None else (None if store else SupabaseOrderRepository.from_env())
        self._pending_address_by_session: dict[str, str] = {}

    def process(self, message: Message) -> AgentResponse:
        if self._repo and not self.store:
            return self._process_supabase(message)

        data = message.data.get("extracted_data", {})
        order_id = data.get("order_id")
        text = message.content
        if any(k in text for k in ["取消", "不要了"]):
            return self._cancel(order_id)
        if any(k in text for k in ["改地址", "修改地址", "换地址"]):
            return self._address_change(order_id)
        if any(k in text for k in ["全部", "所有", "最近"]):
            return self._list_recent(message.data.get("user_id"))
        return self._query(order_id, message.data.get("user_id"))

    def _query(self, order_id: Optional[str], user_id: Optional[int]) -> AgentResponse:
        if not self.store:
            return AgentResponse(False, "订单数据库未连接，请先配置 DATABASE_URL 并运行 seed_data.py。")
        if not order_id:
            return self._list_recent(user_id)
        order = self.store.get_order(order_id)
        if not order:
            return AgentResponse(False, f"未找到订单 {order_id}，请确认订单号是否正确。", data={"order_id": order_id})
        return AgentResponse(True, self._format_order(order), data={"order": self._order_payload(order), "action": "query"})

    def _list_recent(self, user_id: Optional[int]) -> AgentResponse:
        orders = self.store.list_recent_orders(user_id=user_id, limit=5) if self.store else []
        if not orders:
            return AgentResponse(False, "暂未查到订单。")
        lines = ["为您找到最近订单："]
        for order in orders:
            first = order.items[0].product_name if order.items else "商品"
            lines.append(f"- {order.order_id} | {order.status} | {first} | ¥{order.total_amount:.2f}")
        return AgentResponse(True, "\n".join(lines), data={"orders": [self._order_payload(o) for o in orders], "action": "list_recent"})

    def _cancel(self, order_id: Optional[str]) -> AgentResponse:
        if not self.store:
            return AgentResponse(False, "订单数据库未连接。")
        if not order_id:
            return AgentResponse(False, "取消订单需要提供订单号。", data={"need_info": "order_id"})
        order = self.store.get_order(order_id)
        if not order:
            return AgentResponse(False, f"未找到订单 {order_id}。")
        if not order.can_cancel:
            return AgentResponse(False, f"订单 {order_id} 当前状态为 {order.status}，不可取消。", data={"order": self._order_payload(order)})
        self.store.cancel_order(order)
        return AgentResponse(True, f"订单 {order_id} 已取消，退款将按原支付路径退回。", data={"order": self._order_payload(order), "action": "cancel"})

    def _address_change(self, order_id: Optional[str]) -> AgentResponse:
        if not self.store:
            return AgentResponse(False, "订单数据库未连接。")
        if not order_id:
            return AgentResponse(False, "修改地址需要提供订单号。", data={"need_info": "order_id"})
        order = self.store.get_order(order_id)
        if not order:
            return AgentResponse(False, f"未找到订单 {order_id}。")
        if not order.can_modify_address:
            return AgentResponse(False, f"订单 {order_id} 当前状态为 {order.status}，无法直接修改地址。")
        return AgentResponse(True, f"订单 {order_id} 仍可修改地址。请提供新的省市区、详细地址、姓名和电话。", data={"action": "change_address", "need_info": "new_address"})

    def _format_order(self, order) -> str:
        items = "、".join(f"{item.product_name} x{item.quantity}" for item in order.items)
        address = order.receive_address or {}
        tracking = order.shipment.tracking_number if order.shipment else "暂无"
        return (
            f"订单详情\n"
            f"订单号：{order.order_id}\n"
            f"状态：{order.status}\n"
            f"商品：{items}\n"
            f"金额：¥{order.total_amount:.2f}\n"
            f"收货地址：{address.get('province','')}{address.get('city','')}{address.get('district','')}{address.get('detail','')}\n"
            f"物流单号：{tracking}"
        )

    def _order_payload(self, order) -> dict:
        return {
            "order_id": order.order_id,
            "status": order.status,
            "total_amount": order.total_amount,
            "can_cancel": order.can_cancel,
            "can_modify_address": order.can_modify_address,
            "items": [{"product_name": i.product_name, "quantity": i.quantity, "unit_price": i.unit_price} for i in order.items],
            "shipment": {"tracking_number": order.shipment.tracking_number, "status": order.shipment.status} if order.shipment else None,
            "refunds": [{"id": r.id, "status": r.status, "amount": r.amount, "reason": r.reason} for r in order.refunds],
        }

    def _process_supabase(self, message: Message) -> AgentResponse:
        data: dict[str, Any] = message.data.get("extracted_data") or {}
        order_id = data.get("order_id")
        text = message.content
        session_id = message.session_id or ""

        has_address_keyword = any(k in text for k in ["改地址", "换地址", "修改地址"])
        if session_id and session_id in self._pending_address_by_session:
            pending_order_id = self._pending_address_by_session[session_id]
            parsed = self._parse_new_address(text, data)
            if parsed and not has_address_keyword:
                order = self._repo.fetch_by_order_id(pending_order_id)
                if order and order.get("can_modify_address"):
                    return self._apply_repo_address_update(pending_order_id, order, parsed, session_id)

        if has_address_keyword:
            return self._repo_address_change(order_id, text, data, session_id)
        if any(k in text for k in ["取消", "不要了"]):
            if session_id:
                self._pending_address_by_session.pop(session_id, None)
            return self._repo_cancel(order_id, text)
        if any(k in text for k in ["全部", "所有", "最近", "列表"]):
            return self._repo_list_orders()
        return self._repo_query(order_id, text)

    def _repo_query(self, order_id: Optional[str], text: str) -> AgentResponse:
        order_id = order_id or self._extract_order_id(text)
        if order_id:
            order = self._repo.fetch_by_order_id(order_id)
            if order:
                return AgentResponse(True, self._format_repo_order(order), data={"order": self._repo_order_payload(order), "action": "query"})
            return AgentResponse(False, f"未找到订单号 {order_id} 的信息，请确认订单号是否正确。", data={"action": "query", "order_id": order_id})

        recent = self._repo.fetch_recent(2)
        if not recent:
            return AgentResponse(True, "未指定订单号；数据库中暂无订单记录。", data={"orders": [], "action": "list_recent"})
        lines = ["未指定订单号，为您查询最近的订单："]
        lines.extend(self._format_repo_order_brief(order) for order in recent)
        lines.append("如需查询特定订单，请提供订单号。")
        return AgentResponse(True, "\n\n".join(lines), data={"orders": [self._repo_order_payload(o) for o in recent], "action": "list_recent"})

    def _repo_address_change(
        self,
        order_id: Optional[str],
        text: str,
        extracted: dict[str, Any],
        session_id: str,
    ) -> AgentResponse:
        order_id = order_id or self._extract_order_id(text)
        if not order_id:
            return AgentResponse(False, "修改地址需要提供订单号，请提供您要修改的订单号。", data={"action": "change_address", "need_info": "order_id"})
        order = self._repo.fetch_by_order_id(order_id)
        if not order:
            return AgentResponse(False, f"未找到订单号 {order_id}，请确认是否正确。", data={"action": "change_address", "order_id": order_id})
        if not order["can_modify_address"]:
            if session_id:
                self._pending_address_by_session.pop(session_id, None)
            return AgentResponse(False, f"抱歉，订单 {order_id} 当前状态为【{order['status']}】，已无法修改地址。", data={"order": order, "action": "change_address", "can_modify": False})

        parsed = self._parse_new_address(text, extracted)
        if parsed:
            return self._apply_repo_address_update(order_id, order, parsed, session_id)

        if session_id:
            self._pending_address_by_session[session_id] = order_id
        return AgentResponse(
            True,
            f"订单 {order_id} 可以修改地址。\n\n当前地址：{self._format_address(order['receive_address'])}\n\n请发送完整新地址：省 + 市 + 区/县 + 详细门牌 + 收货人姓名 + 手机号。",
            data={"order": order, "action": "change_address", "need_info": "new_address"},
        )

    def _apply_repo_address_update(
        self,
        order_id: str,
        order: dict[str, Any],
        new_address: dict[str, str],
        session_id: str,
    ) -> AgentResponse:
        if session_id:
            self._pending_address_by_session.pop(session_id, None)
        ok, error = self._repo.update_receive_address(order_id, new_address)
        if not ok:
            return AgentResponse(False, f"地址未能保存到数据库：{error}", data={"order": order, "action": "change_address", "new_address": new_address})
        updated = self._repo.fetch_by_order_id(order_id) or {**order, "receive_address": new_address}
        return AgentResponse(
            True,
            f"订单 {order_id} 收货地址已更新。\n\n新地址：{self._format_address(updated['receive_address'])}",
            data={"order": updated, "action": "change_address_done", "new_address": new_address},
        )

    def _repo_cancel(self, order_id: Optional[str], text: str) -> AgentResponse:
        order_id = order_id or self._extract_order_id(text)
        if not order_id:
            return AgentResponse(False, "取消订单需要提供订单号，请提供您要取消的订单号。", data={"action": "cancel", "need_info": "order_id"})
        order = self._repo.fetch_by_order_id(order_id)
        if not order:
            return AgentResponse(False, f"未找到订单号 {order_id}，请确认是否正确。", data={"action": "cancel", "order_id": order_id})
        if not order["can_cancel"]:
            return AgentResponse(False, f"抱歉，订单 {order_id} 当前状态为【{order['status']}】，已无法取消。", data={"order": order, "action": "cancel", "can_cancel": False})
        ok, error = self._repo.update_cancelled(order_id)
        if not ok:
            return AgentResponse(False, f"无法在数据库中完成取消：{error}", data={"order": order, "action": "cancel"})
        updated = self._repo.fetch_by_order_id(order_id) or {**order, "status": "已取消", "can_cancel": False, "can_modify_address": False}
        return AgentResponse(
            True,
            f"订单 {order_id} 已成功取消。\n\n商品：{updated['product_name']} x{updated['quantity']}\n金额：¥{updated['total_amount']:.2f}\n\n退款将在 3-7 个工作日内原路退回您的支付账户。",
            data={"order": updated, "action": "cancel"},
        )

    def _repo_list_orders(self) -> AgentResponse:
        orders = self._repo.fetch_all(100)
        lines = [f"您共有 {len(orders)} 个订单："]
        lines.extend(self._format_repo_order_brief(order) for order in orders)
        return AgentResponse(True, "\n\n".join(lines), data={"orders": [self._repo_order_payload(o) for o in orders], "action": "list_all"})

    @staticmethod
    def _extract_order_id(text: str) -> Optional[str]:
        match = re.search(r"订单[号编号]?\s*(\d{10,20})", text) or re.search(r"\b(\d{10,20})\b", text)
        return match.group(1) if match else None

    @staticmethod
    def _strip_address_noise(text: str) -> str:
        clean = text
        for keyword in ["改地址", "换地址", "修改地址", "新地址", "收货地址", "改为", "换成", "详细地址", "地址改成"]:
            clean = clean.replace(keyword, " ")
        clean = re.sub(r"订单[号编号]?\s*\d{10,20}", "", clean)
        return clean.strip()

    def _parse_new_address(self, text: str, extracted: dict[str, Any]) -> Optional[dict[str, str]]:
        work = self._strip_address_noise(text)
        phone_match = re.search(r"(1[3-9]\d{9})", work)
        phone = phone_match.group(1) if phone_match else str(extracted.get("phone") or "")
        if not phone:
            return None

        work_without_phone = work.replace(phone, " ").strip()
        name = ""
        name_match = re.search(r"(?:收货人|收件人|姓名|联系人)[:：\s]*([\u4e00-\u9fa5·．.\s]{2,12})", text)
        if name_match:
            name = re.sub(r"\s+", "", name_match.group(1)).strip("·．.")
        if not name:
            inline_name = re.search(r"([\u4e00-\u9fa5]{2,4})\s*(?:手机|电话)?\s*" + re.escape(phone), text)
            if inline_name:
                name = inline_name.group(1)

        geo = re.search(
            r"(?P<province>[\u4e00-\u9fa5]+?(?:省|自治区))?\s*"
            r"(?P<city>[\u4e00-\u9fa5]+?市)\s*"
            r"(?P<district>[\u4e00-\u9fa5]+?(?:区|县))\s*"
            r"(?P<detail>.+?)(?=1[3-9]\d{9}|$)",
            work_without_phone,
        )
        if not geo:
            return None
        detail = re.sub(r"[，,;；\s]+$", "", geo.group("detail").strip())
        if len(detail) < 4:
            return None
        return {
            "name": name or "收件人",
            "phone": phone,
            "province": (geo.group("province") or "").strip(),
            "city": geo.group("city").strip(),
            "district": geo.group("district").strip(),
            "detail": detail,
        }

    def _format_repo_order(self, order: dict[str, Any]) -> str:
        info = (
            f"订单详情\n"
            f"订单号：{order['order_id']}\n"
            f"状态：{order['status']}\n"
            f"下单时间：{order['create_time']}\n"
            f"商品：{order['product_name']} x{order['quantity']}\n"
            f"金额：¥{order['total_amount']:.2f}\n"
            f"收货地址：{self._format_address(order['receive_address'])}"
        )
        if order.get("tracking_number"):
            info += f"\n物流单号：{order['tracking_number']}"
        actions = []
        if order.get("can_modify_address"):
            actions.append("可修改地址")
        if order.get("can_cancel"):
            actions.append("可取消订单")
        if actions:
            info += "\n可用操作：" + " | ".join(actions)
        return info

    def _format_repo_order_brief(self, order: dict[str, Any]) -> str:
        return f"{order['order_id']} | {order['status']} | {order['product_name']} x{order['quantity']} | ¥{order['total_amount']:.2f}"

    def _format_address(self, address: dict[str, Any]) -> str:
        return (
            f"{address.get('province', '')}{address.get('city', '')}"
            f"{address.get('district', '')}{address.get('detail', '')}"
            f" ({address.get('name', '')} {address.get('phone', '')})"
        ).strip()

    def _repo_order_payload(self, order: dict[str, Any]) -> dict:
        return {
            "order_id": order["order_id"],
            "status": order["status"],
            "total_amount": order["total_amount"],
            "can_cancel": order["can_cancel"],
            "can_modify_address": order["can_modify_address"],
            "items": [
                {
                    "product_name": order.get("product_name", ""),
                    "quantity": order.get("quantity", 1),
                    "unit_price": order.get("product_price", order.get("total_amount", 0)),
                }
            ],
            "shipment": {"tracking_number": order.get("tracking_number"), "status": order.get("status")} if order.get("tracking_number") else None,
            "receive_address": order.get("receive_address", {}),
            "source": "supabase",
        }
