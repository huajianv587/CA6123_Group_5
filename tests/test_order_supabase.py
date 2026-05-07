from agents import IntentType, Message
from agents.order import OrderAgent


class FakeOrderRepository:
    def __init__(self):
        self.order = {
            "order_id": "202404250123",
            "status": "待发货",
            "product_name": "iPhone 15 Pro Max",
            "product_price": 9999.0,
            "quantity": 1,
            "total_amount": 9999.0,
            "create_time": "2026-05-01 10:00:00",
            "ship_time": None,
            "receive_address": {
                "name": "张三",
                "phone": "13812345678",
                "province": "广东省",
                "city": "深圳市",
                "district": "南山区",
                "detail": "科技园1号",
            },
            "can_modify_address": True,
            "can_cancel": True,
            "tracking_number": None,
            "shipping_fee": 0.0,
        }

    def fetch_by_order_id(self, order_id):
        return dict(self.order) if order_id == self.order["order_id"] else None

    def fetch_recent(self, limit=2):
        return [dict(self.order)]

    def fetch_all(self, max_rows=100):
        return [dict(self.order)]

    def update_cancelled(self, order_id):
        self.order["status"] = "已取消"
        self.order["can_cancel"] = False
        self.order["can_modify_address"] = False
        return True, ""

    def update_receive_address(self, order_id, address):
        self.order["receive_address"] = dict(address)
        return True, ""


def _message(text, extracted=None, session_id="s1"):
    return Message(
        sender="router",
        receiver="order",
        intent=IntentType.ORDER,
        content=text,
        data={"extracted_data": extracted or {}},
        session_id=session_id,
    )


def test_order_agent_uses_supabase_repository_for_query_and_cancel():
    repo = FakeOrderRepository()
    agent = OrderAgent(order_repository=repo)

    query = agent.receive_message(_message("查订单202404250123"))
    assert query.success is True
    assert query.data["order"]["source"] == "supabase"

    cancel = agent.receive_message(_message("取消订单202404250123"))
    assert cancel.success is True
    assert cancel.data["order"]["status"] == "已取消"


def test_order_agent_updates_supabase_address_after_followup():
    repo = FakeOrderRepository()
    agent = OrderAgent(order_repository=repo)

    first = agent.receive_message(_message("订单202404250123 改地址"))
    assert first.data["need_info"] == "new_address"

    second = agent.receive_message(_message("广东省深圳市福田区中心路88号 收货人李四 13912345678"))
    assert second.success is True
    assert second.data["new_address"]["district"] == "福田区"
