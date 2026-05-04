from typing import Optional

from agents.base_agent import AgentResponse, BaseAgent, Message


class OrderAgent(BaseAgent):
    def __init__(self, store=None, **kwargs):
        super().__init__("order", "OrderAgent", store=store, **kwargs)

    def process(self, message: Message) -> AgentResponse:
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
