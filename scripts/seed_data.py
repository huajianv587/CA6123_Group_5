from datetime import datetime, timedelta
import sys
from pathlib import Path
from random import choice, randint, random, seed

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from knowledge.faq_store import FAQ_DOCUMENTS
from shared import models
from shared.database import init_db, session_scope


PRODUCTS = [
    ("iPhone 15 Pro Max", "SKU-IP15PM", 9999),
    ("AirPods Pro 2", "SKU-APP2", 1899),
    ("iPad Air 5", "SKU-IPAD5", 4799),
    ("MacBook Pro", "SKU-MBP", 14999),
    ("智能手表 S9", "SKU-WATCH9", 2999),
]
CARRIERS = [("SF", "顺丰速运"), ("JD", "京东物流"), ("YT", "圆通速递"), ("ZT", "中通快递")]
STATUSES = ["pending_ship", "shipped", "signed", "completed", "cancelled"]


def clear(db):
    for model in [
        models.AgentEvent,
        models.MessageRecord,
        models.ChatSession,
        models.KnowledgeChunk,
        models.KnowledgeDocument,
        models.Complaint,
        models.RefundRequest,
        models.ShipmentEvent,
        models.Shipment,
        models.OrderItem,
        models.Order,
        models.Customer,
    ]:
        db.query(model).delete()


def seed_customers(db):
    customers = []
    levels = ["standard", "silver", "gold", "vip"]
    for i in range(1, 21):
        customer = models.Customer(
            name=f"用户{i:02d}",
            phone=f"1380000{i:04d}",
            email=f"user{i:02d}@example.com",
            member_level=choice(levels),
        )
        db.add(customer)
        customers.append(customer)
    db.flush()
    return customers


def seed_orders(db, customers):
    orders = []
    now = datetime.utcnow()
    for i in range(1, 101):
        customer = choice(customers)
        product_name, sku, price = choice(PRODUCTS)
        qty = randint(1, 2)
        status = choice(STATUSES)
        created = now - timedelta(days=randint(0, 30), hours=randint(0, 23))
        shipped_at = created + timedelta(days=1) if status in {"shipped", "signed", "completed"} else None
        received_at = shipped_at + timedelta(days=randint(1, 4)) if status in {"signed", "completed"} else None
        order = models.Order(
            order_id=f"20240425{i:04d}",
            customer_id=customer.id,
            status=status,
            payment_status="paid" if status != "cancelled" else "refunded",
            total_amount=float(price * qty),
            shipping_fee=0 if price > 99 else 12,
            receive_address={
                "name": customer.name,
                "phone": customer.phone,
                "province": choice(["广东省", "北京市", "上海市", "浙江省"]),
                "city": choice(["深圳市", "北京市", "上海市", "杭州市"]),
                "district": choice(["南山区", "朝阳区", "浦东新区", "西湖区"]),
                "detail": f"科技园 {randint(1, 99)} 号",
            },
            can_cancel=status == "pending_ship",
            can_modify_address=status == "pending_ship",
            created_at=created,
            shipped_at=shipped_at,
            received_at=received_at,
        )
        db.add(order)
        db.flush()
        db.add(models.OrderItem(order_id=order.id, product_name=product_name, sku=sku, unit_price=float(price), quantity=qty))
        orders.append(order)
    db.flush()
    return orders


def seed_shipments(db, orders):
    now = datetime.utcnow()
    shippable = [order for order in orders if order.status in {"shipped", "signed", "completed"}]
    for idx, order in enumerate(shippable[:100], start=1):
        code, name = CARRIERS[(idx - 1) % len(CARRIERS)]
        status = "signed" if order.status in {"signed", "completed"} else "in_transit"
        shipment = models.Shipment(
            order_id=order.id,
            tracking_number=f"{code}{1000000000 + idx}",
            carrier_code=code,
            carrier_name=name,
            status=status,
            estimated_delivery=now + timedelta(days=randint(1, 3)),
            signed_by=order.receive_address["name"] if status == "signed" else None,
        )
        db.add(shipment)
        db.flush()
        events = [
            ("picked", "快递员已揽收", "发货仓"),
            ("in_transit", "包裹正在转运中", "转运中心"),
            (status, "包裹已签收" if status == "signed" else "包裹正在派送", order.receive_address["city"]),
        ]
        for offset, (event_status, detail, location) in enumerate(events):
            db.add(models.ShipmentEvent(shipment_id=shipment.id, event_time=now - timedelta(hours=(len(events) - offset) * 6), status=event_status, detail=detail, location=location))


def seed_refunds_complaints(db, orders):
    refundable = [order for order in orders if order.status in {"signed", "completed", "shipped"}]
    for order in refundable[:30]:
        if random() < 0.5:
            db.add(models.RefundRequest(order_id=order.id, reason=choice(["quality_issue", "seven_day", "not_as_described"]), amount=order.total_amount, status=choice(["pending", "approved", "rejected"])))
    for i in range(30):
        level = choice(["low", "medium", "high"])
        db.add(models.Complaint(session_id=f"seed-{i:03d}", user_id=None, content=choice(["物流太慢了", "我要投诉服务态度", "商品质量有问题", "我要找经理"]), emotion_level=level, emotion_score={"low": 1, "medium": 3.5, "high": 8}[level], escalation_reason="演示数据" if level == "high" else None, status="open" if level == "high" else "handled"))


def seed_knowledge(db):
    docs = list(FAQ_DOCUMENTS)
    base_len = len(docs)
    categories = ["refund", "logistics", "order", "complaint", "safety"]
    for i in range(base_len + 1, 51):
        category = choice(categories)
        docs.append({
            "id": f"{category}_{i:03d}",
            "category": category,
            "question": f"{category} 常见问题 {i}",
            "answer": f"这是 {category} 场景的演示知识文档，用于测试 RAG 检索、引用来源和客服回答生成。",
            "keywords": [category, "演示", "规则"],
        })
    for doc in docs:
        db.add(models.KnowledgeDocument(doc_id=doc["id"], category=doc["category"], title=doc["question"], content=doc["answer"], keywords=doc["keywords"]))


def main():
    seed(42)
    init_db()
    with session_scope() as db:
        clear(db)
        customers = seed_customers(db)
        orders = seed_orders(db, customers)
        seed_shipments(db, orders)
        seed_refunds_complaints(db, orders)
        seed_knowledge(db)
    print("Seed data created: 20 customers, 100 orders, shipments, refunds, complaints, 50 knowledge documents.")


if __name__ == "__main__":
    main()
