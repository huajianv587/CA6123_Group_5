from __future__ import annotations

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

        product_category = self._product_category(order)
        customer_level = getattr(order.customer, "member_level", "standard") if order.customer else "standard"
        customer_tags = self._customer_tags(order)
        policy_decision = self._policy_decision(order, reason, product_category, customer_level, customer_tags)

        rag_query = (
            f"{text} 退款原因:{self._reason_label(reason)} 商品类型:{product_category} "
            f"客户等级:{customer_level} 客户标签:{','.join(tag['tag'] for tag in customer_tags)}"
        )
        rag_results = self.retrieve_knowledge(rag_query, top_k=3, category_filter="refund")
        rag_sources = [r.doc_id for r in rag_results]
        can_refund, reason_text = policy_decision["can_refund"], policy_decision["reason_text"]
        if not can_refund:
            return AgentResponse(
                False,
                f"订单 {order_id} 暂不符合退款条件。\n原因：{reason_text}",
                data={
                    "refund_policy": policy_decision,
                    "customer_tags": customer_tags,
                    "product_category": product_category,
                },
                rag_used=bool(rag_results),
                rag_sources=rag_sources,
            )

        amount = self._amount(order, reason)
        refund = self.store.create_refund(order, reason, amount, status="pending")
        historical_cases = self._historical_cases("refund")
        msg = (
            f"退款申请已创建\n"
            f"退款编号：{refund.id}\n"
            f"订单号：{order.order_id}\n"
            f"退款原因：{self._reason_label(reason)}\n"
            f"客户等级：{customer_level}\n"
            f"商品类型：{product_category}\n"
            f"预计退款：¥{amount:.2f}\n"
            f"规则判定：{policy_decision['reason_text']}\n"
            f"审核时效：1-3 个工作日；到账时效：审核通过后 3-7 个工作日。"
        )
        if rag_results:
            msg += "\n\n参考政策：\n" + self.format_rag_context(rag_results, max_chars=360)
        if historical_cases:
            msg += "\n\n相似历史案例：\n" + "\n".join(f"- {case['title']}：{case['outcome']}" for case in historical_cases[:2])
        return AgentResponse(
            True,
            msg,
            data={
                "refund_id": refund.id,
                "amount": amount,
                "action": "apply",
                "refund_policy": policy_decision,
                "customer_tags": customer_tags,
                "product_category": product_category,
                "historical_cases": historical_cases,
            },
            need_escalate=policy_decision["need_escalate"],
            escalate_reason=policy_decision["escalate_reason"],
            rag_used=bool(rag_results),
            rag_sources=rag_sources,
        )

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
        if any(k in text for k in ["碎了", "压坏", "损坏"]):
            return "damaged"
        if any(k in text for k in ["没发货", "延迟", "等太久"]):
            return "late_delivery"
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
        if reason in {"quality_issue", "wrong_item", "not_as_described", "damaged"}:
            return True, "卖家责任场景支持退款。"
        if order.received_at:
            days = (datetime.utcnow() - order.received_at).days
            if days > 7:
                return False, f"签收已超过 7 天，无理由退款窗口已关闭；如存在质量问题仍可申请。"
        return True, "符合退款条件。"

    def _policy_decision(
        self,
        order,
        reason: str,
        product_category: str,
        customer_level: str,
        customer_tags: list[dict],
    ) -> dict:
        if order.status in {"cancelled", "refunded"}:
            return self._decision(False, "订单已取消或已退款。", rule=None)
        rules = self.store.list_active_policy_rules("refund") if self.store and hasattr(self.store, "list_active_policy_rules") else []
        matched = [rule for rule in rules if self._rule_matches(rule, order, reason, product_category, customer_level)]
        if not matched:
            can_refund, reason_text = self._eligibility(order, reason)
            return self._decision(can_refund, reason_text, rule=None)

        rule = matched[0]
        if rule.decision == "deny":
            return self._decision(False, rule.answer, rule=rule)
        if rule.decision == "escalate":
            return self._decision(
                True,
                rule.answer,
                rule=rule,
                need_escalate=True,
                escalate_reason="refund_policy_requires_human_review",
                customer_tags=customer_tags,
            )
        return self._decision(True, rule.answer, rule=rule, customer_tags=customer_tags)

    def _rule_matches(self, rule, order, reason: str, product_category: str, customer_level: str) -> bool:
        if rule.refund_reasons and reason not in rule.refund_reasons:
            return False
        if rule.product_categories and product_category not in rule.product_categories:
            return False
        if rule.customer_levels and customer_level not in rule.customer_levels:
            return False
        conditions = rule.conditions or {}
        max_days = conditions.get("max_days_after_receive")
        if max_days is not None and order.received_at:
            days = (datetime.utcnow() - order.received_at).days
            if days > int(max_days):
                return False
        return True

    def _decision(
        self,
        can_refund: bool,
        reason_text: str,
        rule=None,
        need_escalate: bool = False,
        escalate_reason: str = "",
        customer_tags: list[dict] | None = None,
    ) -> dict:
        return {
            "can_refund": can_refund,
            "reason_text": reason_text,
            "need_escalate": need_escalate,
            "escalate_reason": escalate_reason,
            "rule_id": getattr(rule, "rule_id", None),
            "rule_version": getattr(rule, "rule_version", None),
            "decision": getattr(rule, "decision", "fallback"),
            "source_doc_id": getattr(rule, "source_doc_id", None),
            "customer_tags": customer_tags or [],
        }

    def _product_category(self, order) -> str:
        names = " ".join(item.product_name for item in order.items)
        skus = " ".join(item.sku for item in order.items)
        text = f"{names} {skus}".lower()
        if any(word in text for word in ["iphone", "airpods", "ipad", "macbook", "watch", "智能手表"]):
            return "electronics"
        if any(word in text for word in ["virtual", "digital", "card", "会员", "激活码"]):
            return "digital_virtual"
        if any(word in text for word in ["custom", "定制"]):
            return "customized"
        if any(word in text for word in ["fresh", "生鲜", "鲜活"]):
            return "fresh_food"
        return "general"

    def _customer_tags(self, order) -> list[dict]:
        if not self.store or not hasattr(self.store, "get_customer_tags"):
            return []
        return [
            {"tag": item.tag, "risk_level": item.risk_level, "description": item.description}
            for item in self.store.get_customer_tags(order.customer_id)
        ]

    def _historical_cases(self, category: str) -> list[dict]:
        if not self.store or not hasattr(self.store, "list_historical_cases"):
            return []
        return [
            {
                "case_id": item.case_id,
                "title": item.title,
                "outcome": item.outcome,
                "resolution": item.resolution,
            }
            for item in self.store.list_historical_cases(category=category, limit=3)
        ]

    def _amount(self, order, reason: str) -> float:
        seller_fault = reason in {"quality_issue", "wrong_item", "not_as_described", "damaged", "late_delivery"}
        return float(order.total_amount if seller_fault else order.total_amount - order.shipping_fee)

    def _reason_label(self, reason: str) -> str:
        return {
            "quality_issue": "质量问题",
            "seven_day": "七天无理由",
            "wrong_item": "错发/少发",
            "not_as_described": "描述不符",
            "damaged": "商品破损",
            "late_delivery": "未按时发货",
            "other": "协商退款",
        }.get(reason, reason)
