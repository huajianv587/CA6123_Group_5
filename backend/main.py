from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from backend.schemas import ChatRequest, ChatResponse, ResolveRequest
from orchestration import CustomerServiceOrchestrator
from quality_safety.evaluation import evaluate_quality_safety
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
    return [
        {
            "id": item.id,
            "session_id": item.session_id,
            "content": item.content,
            "emotion_level": item.emotion_level,
            "emotion_score": item.emotion_score,
            "escalation_reason": item.escalation_reason,
            "status": item.status,
            "created_at": item.created_at.isoformat(),
        }
        for item in store.list_escalations()
    ]


@app.post("/api/admin/escalations/{complaint_id}/resolve")
def resolve_escalation(complaint_id: int, payload: ResolveRequest, db: Session = Depends(get_db)):
    store = CustomerServiceStore(db)
    complaint = store.resolve_escalation(complaint_id)
    if not complaint:
        raise HTTPException(status_code=404, detail="escalation_not_found")
    db.commit()
    return {"id": complaint.id, "status": complaint.status, "note": payload.note}
