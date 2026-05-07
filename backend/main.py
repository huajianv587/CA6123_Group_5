from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from backend.schemas import ChatRequest, ChatResponse, ResolveRequest
from orchestration import CustomerServiceOrchestrator
from quality_safety.evaluation import evaluate_quality_safety
from shared.config import get_settings
from shared.database import get_db, init_db
from shared.store import CustomerServiceStore


app = FastAPI(title="Customer Service Agentic RAG API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()


def get_store(db: Session = Depends(get_db)) -> CustomerServiceStore:
    return CustomerServiceStore(db)


def _iso(value):
    return value.isoformat() if value else None


def _database_status() -> dict:
    url = get_settings().database_url
    if "supabase.co" in url:
        label = "Supabase Postgres"
    elif url.startswith("sqlite"):
        label = "Local SQLite"
    elif url.startswith("postgres"):
        label = "Postgres"
    else:
        label = "Configured database"
    return {
        "label": label,
        "server_managed": True,
        "frontend_direct_supabase": False,
        "auto_create_tables": True,
    }


def _order_payload(order) -> dict:
    shipment = order.shipment
    events = sorted(shipment.events, key=lambda item: item.event_time, reverse=True) if shipment else []
    return {
        "id": order.id,
        "order_id": order.order_id,
        "status": order.status,
        "payment_status": order.payment_status,
        "total_amount": order.total_amount,
        "shipping_fee": order.shipping_fee,
        "created_at": _iso(order.created_at),
        "shipped_at": _iso(order.shipped_at),
        "received_at": _iso(order.received_at),
        "customer": {
            "id": order.customer.id,
            "name": order.customer.name,
            "member_level": order.customer.member_level,
        }
        if order.customer
        else None,
        "items": [
            {
                "product_name": item.product_name,
                "sku": item.sku,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
            }
            for item in order.items
        ],
        "shipment": {
            "tracking_number": shipment.tracking_number,
            "carrier_name": shipment.carrier_name,
            "status": shipment.status,
            "estimated_delivery": _iso(shipment.estimated_delivery),
            "events": [
                {
                    "time": _iso(event.event_time),
                    "status": event.status,
                    "detail": event.detail,
                    "location": event.location,
                }
                for event in events
            ],
        }
        if shipment
        else None,
        "refund_count": len(order.refunds),
    }


def _refund_payload(refund) -> dict:
    order = refund.order
    return {
        "id": refund.id,
        "reason": refund.reason,
        "amount": refund.amount,
        "status": refund.status,
        "review_result": refund.review_result,
        "created_at": _iso(refund.created_at),
        "resolved_at": _iso(refund.resolved_at),
        "order": {
            "order_id": order.order_id,
            "status": order.status,
            "total_amount": order.total_amount,
            "customer": {
                "name": order.customer.name,
                "member_level": order.customer.member_level,
            }
            if order and order.customer
            else None,
        }
        if order
        else None,
    }


def _session_payload(session) -> dict:
    messages = sorted(session.messages, key=lambda item: item.created_at)
    last_message = messages[-1] if messages else None
    last_agent_message = next((msg for msg in reversed(messages) if msg.role == "assistant"), None)
    return {
        "id": session.id,
        "status": session.status,
        "user_id": session.user_id,
        "escalated": session.escalated,
        "message_count": len(messages),
        "last_message": last_message.content if last_message else "",
        "last_intent": last_agent_message.intent if last_agent_message else None,
        "last_agent": last_agent_message.agent if last_agent_message else None,
        "created_at": _iso(session.created_at),
        "updated_at": _iso(session.updated_at),
    }


def _escalation_payload(item) -> dict:
    return {
        "id": item.id,
        "session_id": item.session_id,
        "content": item.content,
        "emotion_level": item.emotion_level,
        "emotion_score": item.emotion_score,
        "escalation_reason": item.escalation_reason,
        "status": item.status,
        "created_at": _iso(item.created_at),
    }


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, db: Session = Depends(get_db)):
    store = CustomerServiceStore(db)
    orchestrator = CustomerServiceOrchestrator(store=store)
    result = orchestrator.process_message(payload.message, payload.session_id, payload.user_id)
    db.commit()
    return result


@app.get("/api/sessions/{session_id}")
def session_messages(session_id: str, store: CustomerServiceStore = Depends(get_store)):
    messages = store.get_session_messages(session_id)
    return {
        "session_id": session_id,
        "messages": [
            {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "agent": msg.agent,
                "intent": msg.intent,
                "rag_sources": msg.rag_sources,
                "metadata": msg.metadata_json,
                "created_at": msg.created_at.isoformat(),
            }
            for msg in messages
        ],
    }


@app.get("/api/orders/{order_id}")
def order_detail(order_id: str, store: CustomerServiceStore = Depends(get_store)):
    order = store.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="order_not_found")
    return {
        "order_id": order.order_id,
        "status": order.status,
        "payment_status": order.payment_status,
        "total_amount": order.total_amount,
        "shipping_fee": order.shipping_fee,
        "receive_address": order.receive_address,
        "customer": {"id": order.customer.id, "name": order.customer.name, "member_level": order.customer.member_level},
        "items": [{"product_name": item.product_name, "sku": item.sku, "quantity": item.quantity, "unit_price": item.unit_price} for item in order.items],
        "shipment": {
            "tracking_number": order.shipment.tracking_number,
            "carrier_name": order.shipment.carrier_name,
            "status": order.shipment.status,
            "events": [{"time": e.event_time.isoformat(), "status": e.status, "detail": e.detail, "location": e.location} for e in order.shipment.events],
        }
        if order.shipment
        else None,
        "refunds": [{"id": r.id, "reason": r.reason, "amount": r.amount, "status": r.status} for r in order.refunds],
    }


@app.get("/api/admin/metrics")
def metrics(store: CustomerServiceStore = Depends(get_store)):
    return store.metrics()


@app.get("/api/admin/dashboard")
def dashboard(store: CustomerServiceStore = Depends(get_store)):
    metrics_data = store.metrics()
    safety_data = evaluate_quality_safety()
    recent_sessions = store.list_session_summaries(limit=6)
    recent_orders = [_order_payload(item) for item in store.list_orders(limit=6)]
    recent_refunds = [_refund_payload(item) for item in store.list_refunds(limit=6)]
    escalations_data = [_escalation_payload(item) for item in store.list_escalations(limit=6)]
    agent_calls = metrics_data.get("agent_calls", {})
    agent_status = [
        {
            "agent": agent,
            "calls": agent_calls.get(agent, 0),
            "status": "active" if agent_calls.get(agent, 0) else "ready",
        }
        for agent in ["router", "order", "logistics", "refund", "complaint", "quality_safety"]
    ]
    return {
        "metrics": metrics_data,
        "safety": safety_data,
        "database": _database_status(),
        "agent_status": agent_status,
        "recent_sessions": recent_sessions,
        "recent_orders": recent_orders,
        "recent_refunds": recent_refunds,
        "open_escalations": escalations_data,
    }


@app.get("/api/admin/orders")
def admin_orders(
    limit: int = Query(default=25, ge=1, le=100),
    status: Optional[str] = None,
    store: CustomerServiceStore = Depends(get_store),
):
    return [_order_payload(item) for item in store.list_orders(limit=limit, status=status)]


@app.get("/api/admin/refunds")
def admin_refunds(
    limit: int = Query(default=25, ge=1, le=100),
    status: Optional[str] = None,
    store: CustomerServiceStore = Depends(get_store),
):
    return [_refund_payload(item) for item in store.list_refunds(limit=limit, status=status)]


@app.get("/api/admin/sessions")
def admin_sessions(limit: int = Query(default=20, ge=1, le=100), store: CustomerServiceStore = Depends(get_store)):
    return store.list_session_summaries(limit=limit)


@app.get("/api/admin/evaluation/safety")
def safety_evaluation():
    return evaluate_quality_safety()


@app.get("/api/admin/shared-knowledge")
def shared_knowledge(store: CustomerServiceStore = Depends(get_store)):
    rules = store.list_active_policy_rules()
    cases = store.list_historical_cases(limit=20)
    return {
        "version": "RAG-v2",
        "policy_rules": [
            {
                "rule_id": rule.rule_id,
                "category": rule.category,
                "title": rule.title,
                "decision": rule.decision,
                "reason_code": rule.reason_code,
                "rule_version": rule.rule_version,
                "effective_from": rule.effective_from.isoformat(),
                "effective_to": rule.effective_to.isoformat() if rule.effective_to else None,
                "source_doc_id": rule.source_doc_id,
            }
            for rule in rules
        ],
        "historical_cases": [
            {
                "case_id": case.case_id,
                "category": case.category,
                "title": case.title,
                "outcome": case.outcome,
                "customer_segment": case.customer_segment,
                "product_category": case.product_category,
            }
            for case in cases
        ],
    }


@app.get("/api/admin/escalations")
def escalations(store: CustomerServiceStore = Depends(get_store)):
    return [_escalation_payload(item) for item in store.list_escalations()]


@app.post("/api/admin/escalations/{complaint_id}/resolve")
def resolve_escalation(complaint_id: int, payload: ResolveRequest, db: Session = Depends(get_db)):
    store = CustomerServiceStore(db)
    complaint = store.resolve_escalation(complaint_id)
    if not complaint:
        raise HTTPException(status_code=404, detail="escalation_not_found")
    db.commit()
    return {"id": complaint.id, "status": complaint.status, "note": payload.note}
