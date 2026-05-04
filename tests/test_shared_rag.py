from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from agents import IntentType, Message
from agents.refund import RefundAgent
from knowledge import KnowledgeRetriever
from shared import models
from shared.database import Base
from shared.store import CustomerServiceStore


def _store():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    db = Session()
    return CustomerServiceStore(db), db


def _seed_refund_context(db):
    customer = models.Customer(name="VIP User", phone="13800000000", email="vip@example.com", member_level="vip")
    db.add(customer)
    db.flush()
    order = models.Order(
        order_id="202404259999",
        customer_id=customer.id,
        status="completed",
        payment_status="paid",
        total_amount=9999.0,
        shipping_fee=0.0,
        receive_address={"name": "VIP User", "phone": "13800000000", "province": "SG", "city": "Singapore", "district": "CBD", "detail": "Demo"},
        can_cancel=False,
        can_modify_address=False,
        created_at=datetime.utcnow() - timedelta(days=15),
        shipped_at=datetime.utcnow() - timedelta(days=12),
        received_at=datetime.utcnow() - timedelta(days=10),
    )
    db.add(order)
    db.flush()
    db.add(models.OrderItem(order_id=order.id, product_name="iPhone 15 Pro Max", sku="SKU-IP15PM", unit_price=9999.0, quantity=1))
    db.add(
        models.PolicyRule(
            rule_id="refund_vip_goodwill_review_v2",
            category="refund",
            title="VIP 客户协商退款复核规则",
            decision="escalate",
            reason_code="vip_goodwill_human_review",
            customer_levels=["vip"],
            product_categories=["electronics"],
            refund_reasons=["seven_day"],
            conditions={"max_days_after_receive": 15, "requires_human_review": True},
            answer="VIP 客户在普通规则边界外的协商退款进入人工复核。",
            keywords=["VIP", "退款", "人工复核", "电子产品"],
            source_doc_id="chrome_shared_service_sop_2026",
            rule_version="RAG-v2",
            priority=100,
            effective_from=datetime.utcnow() - timedelta(days=1),
            effective_to=datetime.utcnow() + timedelta(days=365),
        )
    )
    db.add(
        models.HistoricalCase(
            case_id="case_refund_vip_001",
            category="refund",
            title="VIP 高价值电子产品退款复核",
            issue_summary="VIP 用户购买高价值电子产品后提出协商退款。",
            resolution="系统检索历史服务记录和有效退款规则后升级人工复核。",
            customer_segment="vip",
            product_category="electronics",
            outcome="human_review_approved",
            keywords=["VIP", "高价值", "退款", "电子产品", "人工复核"],
        )
    )
    db.add(models.CustomerTag(customer_id=customer.id, tag="goodwill_candidate", risk_level="low", description="近期无恶意退款记录。"))
    db.commit()


def test_shared_rag_retrieves_policy_rules_and_cases():
    store, db = _store()
    try:
        _seed_refund_context(db)
        retriever = KnowledgeRetriever(store=store)
        results = retriever.retrieve("VIP 电子产品 退款 人工复核", category="refund", top_k=5)
        doc_ids = {item.doc_id for item in results}

        assert "refund_vip_goodwill_review_v2" in doc_ids
        assert "case_refund_vip_001" in doc_ids
    finally:
        db.close()


def test_refund_agent_uses_policy_rule_customer_level_and_product_category():
    store, db = _store()
    try:
        _seed_refund_context(db)
        agent = RefundAgent(store=store, retriever=KnowledgeRetriever(store=store))
        response = agent.receive_message(
            Message(
                sender="router",
                receiver="refund",
                intent=IntentType.REFUND,
                content="订单202404259999 我想七天无理由退款",
                data={"extracted_data": {"order_id": "202404259999", "refund_reason": "seven_day"}},
                session_id="test-session",
            )
        )

        assert response.success is True
        assert response.need_escalate is True
        assert response.data["refund_policy"]["rule_id"] == "refund_vip_goodwill_review_v2"
        assert response.data["product_category"] == "electronics"
        assert response.data["customer_tags"][0]["tag"] == "goodwill_candidate"
    finally:
        db.close()
