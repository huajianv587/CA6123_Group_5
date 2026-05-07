from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.main as backend_main
from shared.database import Base
from shared import models


def _build_test_sessionmaker():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def _seed_order(db):
    customer = models.Customer(
        name="Test User",
        phone="13800000000",
        email="test@example.com",
        member_level="vip",
    )
    db.add(customer)
    db.flush()

    order = models.Order(
        order_id="202404250001",
        customer_id=customer.id,
        status="completed",
        payment_status="paid",
        total_amount=199.0,
        shipping_fee=0.0,
        receive_address={
            "name": "Test User",
            "phone": "13800000000",
            "province": "SG",
            "city": "Singapore",
            "district": "CBD",
            "detail": "Demo",
        },
        can_cancel=False,
        can_modify_address=False,
        created_at=datetime.utcnow() - timedelta(days=2),
        shipped_at=datetime.utcnow() - timedelta(days=1),
        received_at=datetime.utcnow() - timedelta(hours=12),
    )
    db.add(order)
    db.flush()
    db.add(
        models.OrderItem(
            order_id=order.id,
            product_name="Demo Product",
            sku="SKU-DEMO",
            unit_price=199.0,
            quantity=1,
        )
    )

    shipment = models.Shipment(
        order_id=order.id,
        tracking_number="SF1000000001",
        carrier_code="SF",
        carrier_name="SF Express",
        status="in_transit",
        estimated_delivery=datetime.utcnow() + timedelta(days=1),
    )
    db.add(shipment)
    db.flush()
    db.add(
        models.ShipmentEvent(
            shipment_id=shipment.id,
            event_time=datetime.utcnow(),
            status="in_transit",
            detail="Package is moving",
            location="Transit Hub",
        )
    )
    db.commit()


def _client_with_seeded_db():
    SessionTesting = _build_test_sessionmaker()
    with SessionTesting() as db:
        _seed_order(db)

    def override_get_db():
        db = SessionTesting()
        try:
            yield db
        finally:
            db.close()

    backend_main.app.dependency_overrides[backend_main.get_db] = override_get_db
    return TestClient(backend_main.app)


def test_api_chat_routes_all_m1_intents_and_trace_fields():
    client = _client_with_seeded_db()
    cases = [
        ("order", "order", "\u6211\u60f3\u67e5\u8ba2\u5355202404250001"),
        ("logistics", "logistics", "SF1000000001 \u5230\u54ea\u4e86"),
        ("refund", "refund", "\u8ba2\u5355202404250001 \u6211\u8981\u9000\u6b3e\uff0c\u8d28\u91cf\u6709\u95ee\u9898"),
        ("complaint", "complaint", "\u6211\u8981\u6295\u8bc9\uff0c\u4f60\u4eec\u670d\u52a1\u592a\u5dee\u4e86\uff0c\u6211\u8981\u627e\u7ecf\u7406"),
        ("unknown", "router", "\u4f60\u597d"),
        ("logistics", "logistics", "\u8ba2\u5355202404250001 \u7684\u7269\u6d41\u5230\u54ea\u91cc\u4e86"),
    ]

    try:
        for expected_intent, expected_agent, text in cases:
            response = client.post("/api/chat", json={"message": text})
            payload = response.json()

            assert response.status_code == 200
            assert payload["intent"] == expected_intent
            assert payload["agent"] == expected_agent
            assert isinstance(payload["routing_trace"], list)
            assert isinstance(payload["candidate_intents"], list)
            assert "router_confidence" in payload
            assert "routing" in payload["data"]
    finally:
        backend_main.app.dependency_overrides.clear()


def test_api_chat_numeric_refund_policy_query_returns_policy_answer():
    client = _client_with_seeded_db()

    try:
        response = client.post(
            "/api/chat",
            json={"message": "\u0037\u5929\u65e0\u7406\u7531\u9000\u6b3e\u89c4\u5219\u662f\u4ec0\u4e48\uff1f"},
        )
        payload = response.json()

        assert response.status_code == 200
        assert payload["success"] is True
        assert payload["intent"] == "refund"
        assert payload["agent"] == "refund"
        assert payload["data"]["action"] == "policy_query"
    finally:
        backend_main.app.dependency_overrides.clear()


def test_admin_read_models_power_dashboard_pages():
    client = _client_with_seeded_db()

    try:
        chat = client.post(
            "/api/chat",
            json={"message": "\u8ba2\u5355202404250001 \u6211\u8981\u9000\u6b3e\uff0c\u8d28\u91cf\u6709\u95ee\u9898"},
        )
        assert chat.status_code == 200

        dashboard = client.get("/api/admin/dashboard")
        orders = client.get("/api/admin/orders?limit=10")
        refunds = client.get("/api/admin/refunds?limit=10")
        sessions = client.get("/api/admin/sessions?limit=10")

        assert dashboard.status_code == 200
        assert dashboard.json()["database"]["server_managed"] is True
        assert "agent_status" in dashboard.json()
        assert orders.status_code == 200
        assert orders.json()[0]["order_id"] == "202404250001"
        assert refunds.status_code == 200
        assert refunds.json()[0]["order"]["order_id"] == "202404250001"
        assert sessions.status_code == 200
        assert sessions.json()[0]["message_count"] >= 2
    finally:
        backend_main.app.dependency_overrides.clear()


def test_api_chat_context_followup_routes_to_logistics():
    client = _client_with_seeded_db()

    try:
        first = client.post("/api/chat", json={"message": "\u6211\u60f3\u67e5\u8ba2\u5355202404250001"}).json()
        second = client.post(
            "/api/chat",
            json={"session_id": first["session_id"], "message": "\u90a3\u7269\u6d41\u5230\u54ea\u91cc\u4e86"},
        ).json()

        assert second["intent"] == "logistics"
        assert second["agent"] == "logistics"
        assert second["data"]["routing"]["context_used"] is True
        trace_agents = [step["agent"] for step in second["routing_trace"]]
        assert trace_agents[:4] == ["router", "order", "orchestrator", "logistics"]
        assert "quality_safety" in trace_agents
        assert second["trace_id"]
        assert "safety_report" in second
    finally:
        backend_main.app.dependency_overrides.clear()
