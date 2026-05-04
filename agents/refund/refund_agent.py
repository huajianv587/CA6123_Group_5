from datetime import datetime
from typing import Optional

from agents.base_agent import AgentResponse, BaseAgent, Message


class RefundAgent(BaseAgent):
    def __init__(self, store=None, **kwargs):
        super().__init__("refund", "RefundAgent", store=store, **kwargs)

    def process(self, message: Message) -> AgentResponse:
        text = message.content
        if self._is_policy_query(text):
            return self._policy(text)
        data = message.data.get("extracted_data", {})
        order_id = data.get("order_id")
        reason = data.get("refund_reason") or self._reason(text)
        if not order_id:
            return AgentResponse(False, "申请退款需要提供订单号。", data={"need_info": "order_id"})
        if not self.store:
            return AgentResponse(False, "退款数据库未连接，请先配置 DATABASE_URL 并运行 seed_data.py。")
        order = self.store.get_order(order_id)
        if not order:
            return AgentResponse(False, f"未找到订单 {order_id}。")
        if self.store.has_open_refund(order):
            return AgentResponse(False, f"订单 {order_id} 已有退款申请正在处理，请勿重复提交。")

        can_refund, reason_text = self._eligibility(order, reason)
        rag_results = self.retrieve_knowledge(text, top_k=2, category_filter="refund")
        rag_sources = [r.doc_id for r in rag_results]
        if not can_refund:
            return AgentResponse(False, f"订单 {order_id} 暂不符合退款条件。\n原因：{reason_text}", rag_used=bool(rag_results), rag_sources=rag_sources)

        amount = self._amount(order, reason)
        refund = self.store.create_refund(order, reason, amount, status="pending")
        msg = (
            f"退款申请已创建\n"
            f"退款编号：{refund.id}\n"
            f"订单号：{order.order_id}\n"
            f"退款原因：{self._reason_label(reason)}\n"
            f"预计退款：¥{amount:.2f}\n"
            f"审核时效：1-3 个工作日；到账时效：审核通过后 3-7 个工作日。"
        )
        if rag_results:
            msg += "\n\n参考政策：\n" + self.format_rag_context(rag_results, max_chars=360)
        return AgentResponse(True, msg, data={"refund_id": refund.id, "amount": amount, "action": "apply"}, rag_used=bool(rag_results), rag_sources=rag_sources)

    def _policy(self, text: str) -> AgentResponse:
        results = self.retrieve_knowledge(text, top_k=3, category_filter="refund")
        if results:
            return AgentResponse(True, "根据退款政策：\n" + self.format_rag_context(results), data={"action": "policy_query"}, rag_used=True, rag_sources=[r.doc_id for r in results])
        return AgentResponse(True, "支持质量问题、错发漏发、描述不符、七天无理由等退款场景。申请退款时请提供订单号和退款原因。", data={"action": "policy_query"})

    def _is_policy_query(self, text: str) -> bool:
        return not any(ch.isdigit() for ch in text) and any(k in text for k in ["规则", "政策", "能退吗", "怎么退款", "多久到账", "运费"])

    def _reason(self, text: str) -> str:
        if any(k in text for k in ["质量", "坏", "故障", "破损"]):
            return "quality_issue"
        if any(k in text for k in ["七天", "无理由", "不想要", "不喜欢"]):
            return "seven_day"
        if any(k in text for k in ["错发", "少发", "不是我要"]):
            return "wrong_item"
        if any(k in text for k in ["描述不符", "货不对板"]):
            return "not_as_described"
        return "other"

    def _eligibility(self, order, reason: str) -> tuple[bool, str]:
        if order.status in {"cancelled", "refunded"}:
            return False, "订单已取消或已退款。"
        if reason in {"quality_issue", "wrong_item", "not_as_described"}:
            return True, "卖家责任场景支持退款。"
        if order.received_at:
            days = (datetime.utcnow() - order.received_at).days
            if days > 7:
                return False, f"签收已超过 7 天，无理由退款窗口已关闭；如存在质量问题仍可申请。"
        return True, "符合退款条件。"

    def _amount(self, order, reason: str) -> float:
        seller_fault = reason in {"quality_issue", "wrong_item", "not_as_described"}
        return float(order.total_amount if seller_fault else order.total_amount - order.shipping_fee)

    def _reason_label(self, reason: str) -> str:
        return {
            "quality_issue": "质量问题",
            "seven_day": "七天无理由",
            "wrong_item": "错发/少发",
            "not_as_described": "描述不符",
            "other": "协商退款",
        }.get(reason, reason)
