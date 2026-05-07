from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from shared import models


class CustomerServiceStore:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create_session(self, session_id: str, user_id: Optional[int] = None) -> models.ChatSession:
        session = self.db.get(models.ChatSession, session_id)
        if session is None:
            session = models.ChatSession(id=session_id, user_id=user_id, status="active")
            self.db.add(session)
            self.db.flush()
        elif user_id and not session.user_id:
            session.user_id = user_id
        session.updated_at = datetime.utcnow()
        return session

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        agent: Optional[str] = None,
        intent: Optional[str] = None,
        rag_sources: Optional[list] = None,
        metadata: Optional[dict] = None,
    ) -> models.MessageRecord:
        record = models.MessageRecord(
            session_id=session_id,
            role=role,
            content=content,
            agent=agent,
            intent=intent,
            rag_sources=rag_sources or [],
            metadata_json=metadata or {},
        )
        self.db.add(record)
        self.db.flush()
        return record

    def get_session_messages(self, session_id: str) -> list[models.MessageRecord]:
        stmt = select(models.MessageRecord).where(models.MessageRecord.session_id == session_id).order_by(models.MessageRecord.created_at)
        return list(self.db.scalars(stmt))

    def get_order(self, order_id: str) -> Optional[models.Order]:
        stmt = (
            select(models.Order)
            .options(
                selectinload(models.Order.items),
                selectinload(models.Order.shipment).selectinload(models.Shipment.events),
                selectinload(models.Order.refunds),
                selectinload(models.Order.customer),
            )
            .where(models.Order.order_id == order_id)
        )
        return self.db.scalars(stmt).first()

    def list_recent_orders(self, user_id: Optional[int] = None, limit: int = 5) -> list[models.Order]:
        stmt = select(models.Order).options(selectinload(models.Order.items), selectinload(models.Order.shipment)).order_by(models.Order.created_at.desc()).limit(limit)
        if user_id:
            stmt = stmt.where(models.Order.customer_id == user_id)
        return list(self.db.scalars(stmt))

    def cancel_order(self, order: models.Order) -> None:
        order.status = "cancelled"
        order.can_cancel = False
        order.can_modify_address = False

    def get_shipment_by_tracking(self, tracking_number: str) -> Optional[models.Shipment]:
        stmt = (
            select(models.Shipment)
            .options(selectinload(models.Shipment.events), selectinload(models.Shipment.order).selectinload(models.Order.items))
            .where(models.Shipment.tracking_number == tracking_number)
        )
        return self.db.scalars(stmt).first()

    def create_refund(self, order: models.Order, reason: str, amount: float, status: str = "pending") -> models.RefundRequest:
        refund = models.RefundRequest(order_id=order.id, reason=reason, amount=amount, status=status)
        self.db.add(refund)
        self.db.flush()
        return refund

    def has_open_refund(self, order: models.Order) -> bool:
        return any(r.status in {"pending", "approved", "processing"} for r in order.refunds)

    def create_complaint(
        self,
        session_id: str,
        content: str,
        emotion_level: str,
        emotion_score: float,
        escalation_reason: Optional[str],
        user_id: Optional[int] = None,
        status: str = "open",
    ) -> models.Complaint:
        complaint = models.Complaint(
            session_id=session_id,
            user_id=user_id,
            content=content,
            emotion_level=emotion_level,
            emotion_score=emotion_score,
            escalation_reason=escalation_reason,
            status=status,
        )
        self.db.add(complaint)
        self.db.flush()
        return complaint

    def list_escalations(self) -> list[models.Complaint]:
        stmt = select(models.Complaint).where(models.Complaint.status == "open").order_by(models.Complaint.created_at.desc())
        return list(self.db.scalars(stmt))

    def resolve_escalation(self, complaint_id: int) -> Optional[models.Complaint]:
        complaint = self.db.get(models.Complaint, complaint_id)
        if complaint:
            complaint.status = "resolved"
            complaint.resolved_at = datetime.utcnow()
        return complaint

    def add_agent_event(self, agent: str, success: bool, duration_ms: float, session_id: Optional[str] = None, intent: Optional[str] = None, error: Optional[str] = None, metadata: Optional[dict] = None) -> None:
        self.db.add(models.AgentEvent(agent=agent, success=success, duration_ms=duration_ms, session_id=session_id, intent=intent, error=error, metadata_json=metadata or {}))

    def list_active_policy_rules(self, category: Optional[str] = None, at: Optional[datetime] = None) -> list[models.PolicyRule]:
        at = at or datetime.utcnow()
        stmt = select(models.PolicyRule).where(
            models.PolicyRule.enabled.is_(True),
            models.PolicyRule.effective_from <= at,
        )
        if category:
            stmt = stmt.where(models.PolicyRule.category == category)
        rules = list(self.db.scalars(stmt.order_by(models.PolicyRule.priority.desc(), models.PolicyRule.id.asc())))
        return [rule for rule in rules if rule.effective_to is None or rule.effective_to >= at]

    def list_historical_cases(self, category: Optional[str] = None, limit: int = 5) -> list[models.HistoricalCase]:
        stmt = select(models.HistoricalCase)
        if category:
            stmt = stmt.where(models.HistoricalCase.category == category)
        stmt = stmt.order_by(models.HistoricalCase.created_at.desc()).limit(limit)
        return list(self.db.scalars(stmt))

    def get_customer_tags(self, customer_id: int) -> list[models.CustomerTag]:
        stmt = select(models.CustomerTag).where(models.CustomerTag.customer_id == customer_id).order_by(models.CustomerTag.created_at.desc())
        return list(self.db.scalars(stmt))

    def metrics(self) -> dict:
        total_messages = self.db.scalar(select(func.count(models.MessageRecord.id))) or 0
        total_sessions = self.db.scalar(select(func.count(models.ChatSession.id))) or 0
        escalations = self.db.scalar(select(func.count(models.Complaint.id)).where(models.Complaint.status == "open")) or 0
        rag_hits = self.db.scalar(select(func.count(models.MessageRecord.id)).where(models.MessageRecord.rag_sources != [])) or 0
        intent_rows = self.db.execute(
            select(models.MessageRecord.intent, func.count(models.MessageRecord.id))
            .where(models.MessageRecord.intent.is_not(None))
            .group_by(models.MessageRecord.intent)
        ).all()
        agent_rows = self.db.execute(
            select(models.AgentEvent.agent, func.count(models.AgentEvent.id))
            .group_by(models.AgentEvent.agent)
        ).all()
        policy_rules = self.db.scalar(select(func.count(models.PolicyRule.id))) or 0
        historical_cases = self.db.scalar(select(func.count(models.HistoricalCase.id))) or 0
        customer_tags = self.db.scalar(select(func.count(models.CustomerTag.id))) or 0
        return {
            "total_messages": total_messages,
            "total_sessions": total_sessions,
            "open_escalations": escalations,
            "rag_hit_rate": round((rag_hits / total_messages * 100), 1) if total_messages else 0,
            "intent_distribution": {intent: count for intent, count in intent_rows if intent},
            "agent_calls": {agent: count for agent, count in agent_rows},
            "shared_knowledge": {
                "policy_rules": policy_rules,
                "historical_cases": historical_cases,
                "customer_tags": customer_tags,
            },
        }
