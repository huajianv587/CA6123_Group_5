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
PRODUCT_CATEGORY = {
    "iPhone 15 Pro Max": "electronics",
    "AirPods Pro 2": "electronics",
    "iPad Air 5": "electronics",
    "MacBook Pro": "electronics",
    "智能手表 S9": "electronics",
}


def clear(db):
    for model in [
        models.AgentEvent,
        models.MessageRecord,
        models.ChatSession,
        models.KnowledgeChunk,
        models.KnowledgeDocument,
        models.PolicyRule,
        models.HistoricalCase,
        models.CustomerTag,
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
            member_level="vip" if i == 1 else choice(levels),
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
        if i == 99:
            customer = customers[0]
            product_name, sku, price = ("iPhone 15 Pro Max", "SKU-IP15PM", 9999)
            qty = 1
            status = "completed"
            created = now - timedelta(days=15)
            shipped_at = now - timedelta(days=12)
            received_at = now - timedelta(days=10)
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
    docs.extend(
        [
            {
                "id": "chrome_refund_policy_2026",
                "category": "refund",
                "question": "Chrome lightweight refund policy digest v2",
                "answer": "轻量抓取/整理的退款规则摘要：卖家责任支持全额退款和运费承担；七天无理由需校验签收时间、商品类型和二次销售状态；虚拟、定制、鲜活类商品不支持无理由退款。",
                "keywords": ["Chrome", "退款规则", "七天", "卖家责任", "虚拟商品"],
            },
            {
                "id": "chrome_shared_service_sop_2026",
                "category": "safety",
                "question": "Chrome lightweight customer-service SOP digest v2",
                "answer": "共享客服 SOP 摘要：所有 agent 生成用户可见回复前应完成脱敏；涉及高金额、疑似欺诈、重复投诉、低置信度路由或丢件争议时转人工审核。",
                "keywords": ["Chrome", "共享库", "脱敏", "人工审核", "低置信度"],
            },
        ]
    )
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


def seed_policy_rules(db):
    now = datetime.utcnow()
    rules = [
        {
            "rule_id": "refund_quality_seller_fault_v2",
            "category": "refund",
            "title": "卖家责任退款规则",
            "decision": "approve",
            "reason_code": "seller_fault_full_refund",
            "customer_levels": [],
            "product_categories": [],
            "refund_reasons": ["quality_issue", "wrong_item", "not_as_described"],
            "conditions": {"seller_fault": True, "shipping_fee_owner": "seller"},
            "answer": "质量问题、错发漏发、描述不符属于卖家责任，支持退款或换货，商品金额和合理退货运费由商家承担。",
            "keywords": ["质量", "错发", "描述不符", "卖家责任", "运费"],
            "source_doc_id": "chrome_refund_policy_2026",
            "rule_version": "RAG-v2",
            "priority": 100,
        },
        {
            "rule_id": "refund_seven_day_electronics_v2",
            "category": "refund",
            "title": "电子产品七天无理由规则",
            "decision": "approve",
            "reason_code": "seven_day_buyer_shipping",
            "customer_levels": [],
            "product_categories": ["electronics", "general"],
            "refund_reasons": ["seven_day", "other"],
            "conditions": {"max_days_after_receive": 7, "shipping_fee_owner": "buyer", "requires_resellable": True},
            "answer": "签收后 7 天内且商品不影响二次销售时，支持七天无理由退货；非质量问题退货运费通常由买家承担。",
            "keywords": ["七天", "无理由", "电子产品", "二次销售"],
            "source_doc_id": "chrome_refund_policy_2026",
            "rule_version": "RAG-v2",
            "priority": 80,
        },
        {
            "rule_id": "refund_virtual_goods_deny_v2",
            "category": "refund",
            "title": "虚拟/定制商品无理由退款限制",
            "decision": "deny",
            "reason_code": "non_refundable_product_type",
            "customer_levels": [],
            "product_categories": ["digital_virtual", "customized", "fresh_food"],
            "refund_reasons": ["seven_day", "other"],
            "conditions": {"non_refundable": True},
            "answer": "数字虚拟商品、定制类商品、鲜活易腐类商品通常不支持七天无理由退款；如存在质量或履约问题需转人工核实。",
            "keywords": ["虚拟商品", "定制", "鲜活", "不支持无理由"],
            "source_doc_id": "chrome_refund_policy_2026",
            "rule_version": "RAG-v2",
            "priority": 120,
        },
        {
            "rule_id": "refund_vip_goodwill_review_v2",
            "category": "refund",
            "title": "VIP 客户协商退款复核规则",
            "decision": "escalate",
            "reason_code": "vip_goodwill_human_review",
            "customer_levels": ["vip", "gold"],
            "product_categories": ["electronics", "general"],
            "refund_reasons": ["other", "seven_day"],
            "conditions": {"max_days_after_receive": 15, "requires_human_review": True},
            "answer": "VIP/Gold 客户在普通规则边界内的协商退款可进入人工复核，结合历史服务记录、商品状态和金额决定是否特殊处理。",
            "keywords": ["VIP", "Gold", "协商退款", "人工复核", "历史记录"],
            "source_doc_id": "chrome_shared_service_sop_2026",
            "rule_version": "RAG-v2",
            "priority": 60,
        },
    ]
    for item in rules:
        db.add(
            models.PolicyRule(
                **item,
                enabled=True,
                effective_from=now - timedelta(days=30),
                effective_to=now + timedelta(days=365),
            )
        )


def seed_historical_cases(db):
    cases = [
        {
            "case_id": "case_refund_vip_001",
            "category": "refund",
            "title": "VIP 高价值电子产品退款复核",
            "issue_summary": "VIP 用户购买高价值电子产品后提出协商退款，订单金额较高且超过普通自动审批边界。",
            "resolution": "系统检索历史服务记录和有效退款规则后升级人工复核，人工确认商品未影响二次销售后批准退款。",
            "customer_segment": "vip",
            "product_category": "electronics",
            "outcome": "human_review_approved",
            "keywords": ["VIP", "高价值", "退款", "电子产品", "人工复核"],
        },
        {
            "case_id": "case_logistics_signed_missing_001",
            "category": "logistics",
            "title": "签收未收到争议处理",
            "issue_summary": "用户反馈物流显示已签收但本人未收到，多次追问处理进度。",
            "resolution": "先排查驿站、门卫、家人代收，再联系承运商核查签收凭证；超过 48 小时无结果时转人工处理补发或赔偿。",
            "customer_segment": "general",
            "product_category": "general",
            "outcome": "escalated_for_carrier_proof",
            "keywords": ["签收", "没收到", "丢件", "承运商", "人工"],
        },
        {
            "case_id": "case_complaint_repeated_001",
            "category": "complaint",
            "title": "重复投诉升级",
            "issue_summary": "同一订单出现多次投诉，用户提到 12315 和媒体曝光。",
            "resolution": "保留 trace_id 和完整会话记录，直接进入人工升级队列，由主管统一处理。",
            "customer_segment": "risk_watch",
            "product_category": "general",
            "outcome": "supervisor_queue",
            "keywords": ["重复投诉", "12315", "媒体", "trace", "主管"],
        },
    ]
    for item in cases:
        db.add(models.HistoricalCase(**item))


def seed_customer_tags(db, customers):
    for customer in customers[:4]:
        db.add(
            models.CustomerTag(
                customer_id=customer.id,
                tag="goodwill_candidate" if customer.member_level in {"vip", "gold"} else "standard_history",
                risk_level="low",
                description="模拟历史服务记录：近期无恶意退款记录，可作为协商退款参考。",
            )
        )
    for customer in customers[4:7]:
        db.add(
            models.CustomerTag(
                customer_id=customer.id,
                tag="repeat_complaint_watch",
                risk_level="medium",
                description="模拟历史服务记录：近 30 天出现多次投诉，需在客服流程中保留 trace 并视情况升级。",
            )
        )


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
        seed_policy_rules(db)
        seed_historical_cases(db)
        seed_customer_tags(db, customers)
    print("Seed data created: 20 customers, 100 orders, shipments, refunds, complaints, shared knowledge, policy rules, historical cases, customer tags.")


if __name__ == "__main__":
    main()
