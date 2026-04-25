"""
退款Agent v2 — 集成 Agentic RAG
改造点：
  1. 资格判断前先 RAG 检索退款规则，用知识库内容增强判断逻辑
  2. 生成退款方案时，将 RAG 检索到的政策附加在回复中
  3. 用户问"退款规则/政策"时，直接从知识库回答，不走硬编码
  4. AgentResponse 携带 rag_used / rag_sources，便于可观测性追踪
"""
import re
from typing import Dict, Optional, Tuple, List
from datetime import datetime, timedelta
from enum import Enum
from .base_agent import BaseAgent, Message, AgentResponse, IntentType


class RefundReason(Enum):
    QUALITY_ISSUE = "quality_issue"
    WRONG_ITEM = "wrong_item"
    NOT_AS_DESCRIBED = "not_as_described"
    SEVEN_DAY_NO_REASON = "seven_day"
    DAMAGED = "damaged"
    LATE_DELIVERY = "late_delivery"
    OTHER = "other"


class RefundAgent(BaseAgent):

    # 意图：用户只是在问规则，不是申请退款
    _POLICY_QUERY_KEYWORDS = [
        "退款规则", "退款政策", "可以退吗", "支持退货吗",
        "怎么退款", "退款流程", "运费谁出", "几天能退",
        "无理由退货", "退款多久"
    ]

    def __init__(self, retriever=None):
        super().__init__("refund", "RefundAgent", retriever=retriever)
        self.mock_orders = self._init_mock_orders()
        self.refund_records: Dict[str, Dict] = {}

    def _init_mock_orders(self) -> Dict[str, Dict]:
        t = datetime.now()
        return {
            "202404160001": {
                "order_id": "202404160001", "status": "已发货",
                "product_name": "iPhone 15 Pro Max", "product_price": 9999.00,
                "quantity": 1, "total_amount": 9999.00, "shipping_fee": 0.0,
                "create_time": (t - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S"),
                "receive_time": None, "can_refund": True,
                "refund_deadline": (t + timedelta(days=4)).strftime("%Y-%m-%d"),
            },
            "202404100003": {
                "order_id": "202404100003", "status": "已完成",
                "product_name": "iPad Air 5", "product_price": 4799.00,
                "quantity": 1, "total_amount": 4799.00, "shipping_fee": 0.0,
                "create_time": (t - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S"),
                "receive_time": (t - timedelta(days=6)).strftime("%Y-%m-%d %H:%M:%S"),
                "can_refund": True,
                "refund_deadline": (t + timedelta(days=1)).strftime("%Y-%m-%d"),
            },
            "202404010004": {
                "order_id": "202404010004", "status": "已完成",
                "product_name": "MacBook Pro", "product_price": 14999.00,
                "quantity": 1, "total_amount": 14999.00, "shipping_fee": 0.0,
                "create_time": (t - timedelta(days=20)).strftime("%Y-%m-%d %H:%M:%S"),
                "receive_time": (t - timedelta(days=16)).strftime("%Y-%m-%d %H:%M:%S"),
                "can_refund": False,
                "refund_deadline": (t - timedelta(days=9)).strftime("%Y-%m-%d"),
            },
        }

    # ── 主处理入口 ────────────────────────────

    def process(self, message: Message) -> AgentResponse:
        content = message.content
        data = message.data
        self.log(f"处理退款请求: {content}")

        # ── 分支1：用户询问退款规则（不是申请退款）──
        if self._is_policy_query(content):
            return self._answer_policy_query(content)

        # ── 分支2：申请退款 ──────────────────────
        order_id = data.get("extracted_data", {}).get("order_id")
        if not order_id:
            for pat in [r"订单[号编号]?\s*(\d{10,20})", r"\b(\d{10,20})\b"]:
                m = re.search(pat, content)
                if m:
                    order_id = m.group(1)
                    break

        refund_reason = self._extract_refund_reason(content, data)

        if not order_id:
            return AgentResponse(
                success=False,
                message="申请退款需要提供订单号，请告知您要退款的订单号。",
                data={"action": "apply", "need_info": "order_id"},
            )

        if order_id not in self.mock_orders:
            return AgentResponse(
                success=False,
                message=f"未找到订单号 {order_id}，请确认是否正确。",
                data={"action": "apply", "order_id": order_id},
            )

        order = self.mock_orders[order_id]

        # ── RAG：检索与退款原因相关的规则 ──────
        rag_results = self.retrieve_knowledge(
            query=content,
            top_k=2,
            category_filter="refund",
        )
        rag_sources = [r.doc_id for r in rag_results]

        # 用 RAG 结果辅助判断（增强 _check_eligibility 的解释文本）
        can, reason = self._check_eligibility(order, refund_reason, rag_results)

        if not can:
            # 不可退时，附上 RAG 检索到的相关政策，帮用户理解原因
            policy_hint = self._extract_policy_hint(rag_results)
            msg = f"抱歉，订单 {order_id} 暂时无法申请退款。\n\n原因：{reason}"
            if policy_hint:
                msg += f"\n\n📖 相关退款政策\n{policy_hint}"
            return AgentResponse(
                success=False,
                message=msg,
                data={"order": order, "action": "apply", "can_refund": False},
                rag_used=bool(rag_results),
                rag_sources=rag_sources,
            )

        amount = self._calc_amount(order, refund_reason)
        plan = self._gen_plan(order, amount, refund_reason, rag_results)

        return AgentResponse(
            success=True,
            message=plan,
            data={
                "order": order,
                "action": "apply",
                "can_refund": True,
                "refund_amount": amount,
                "refund_reason": refund_reason.value if refund_reason else None,
            },
            rag_used=bool(rag_results),
            rag_sources=rag_sources,
        )

    # ── 策略查询分支 ──────────────────────────

    def _is_policy_query(self, content: str) -> bool:
        """判断用户是在询问规则，而不是申请退款。"""
        # 若内容中有订单号，更可能是在申请退款
        if re.search(r"\d{10,20}", content):
            return False
        return any(kw in content for kw in self._POLICY_QUERY_KEYWORDS)

    def _answer_policy_query(self, content: str) -> AgentResponse:
        """用 RAG 知识库回答退款规则咨询。"""
        results = self.retrieve_knowledge(
            query=content,
            top_k=3,
            category_filter="refund",
        )

        if not results:
            # RAG 无结果时的兜底回复
            return AgentResponse(
                success=True,
                message=(
                    "我们支持以下退款方式：\n"
                    "• 质量问题：随时可退，运费卖家承担\n"
                    "• 七天无理由：签收7天内，运费买家承担\n"
                    "• 发错货/描述不符：随时可退，运费卖家承担\n\n"
                    "如需申请退款，请提供订单号。"
                ),
                data={"action": "policy_query"},
                rag_used=False,
            )

        # 组装 RAG 回复
        parts = ["根据我们的退款政策：\n"]
        for r in results:
            parts.append(f"\n❓ {r.question}\n{r.answer}\n")

        parts.append("\n如需申请退款，请提供订单号，我来帮您处理。")

        return AgentResponse(
            success=True,
            message="".join(parts),
            data={"action": "policy_query"},
            rag_used=True,
            rag_sources=[r.doc_id for r in results],
        )

    # ── 原有逻辑（保持兼容，增加 rag_results 参数）────

    def _extract_refund_reason(self, content: str, data: Dict) -> Optional[RefundReason]:
        ext = data.get("extracted_data", {}).get("refund_reason", "")
        if ext == "质量问题":   return RefundReason.QUALITY_ISSUE
        if ext == "七天无理由": return RefundReason.SEVEN_DAY_NO_REASON
        if ext == "描述不符":   return RefundReason.NOT_AS_DESCRIBED
        c = content
        if any(kw in c for kw in ["质量", "坏", "破", "瑕疵", "故障"]):  return RefundReason.QUALITY_ISSUE
        if any(kw in c for kw in ["发错", "错发", "不是我要的"]):          return RefundReason.WRONG_ITEM
        if any(kw in c for kw in ["描述不符", "图文不符"]):                return RefundReason.NOT_AS_DESCRIBED
        if any(kw in c for kw in ["七天无理由", "不喜欢", "不合适"]):       return RefundReason.SEVEN_DAY_NO_REASON
        if any(kw in c for kw in ["破损", "碎了", "压坏"]):                return RefundReason.DAMAGED
        if any(kw in c for kw in ["没发货", "延迟", "等太久"]):             return RefundReason.LATE_DELIVERY
        return RefundReason.OTHER

    def _check_eligibility(
        self,
        order: Dict,
        reason: Optional[RefundReason],
        rag_results: list = None,
    ) -> Tuple[bool, str]:
        """
        资格判断逻辑保持不变。
        rag_results 参数预留，未来可用于动态规则覆盖。
        """
        if reason == RefundReason.QUALITY_ISSUE:
            return True, "质量问题支持退款"
        if order.get("receive_time"):
            days = (datetime.now() - datetime.strptime(
                order["receive_time"], "%Y-%m-%d %H:%M:%S"
            )).days
            if days > 7:
                return False, (
                    f"订单已签收 {days} 天，超过七天无理由退货期限。\n"
                    "如有质量问题仍可申请退款。"
                )
        if order["order_id"] in self.refund_records:
            return False, "该订单已有退款申请正在处理中。"
        return True, "符合退款条件"

    def _calc_amount(self, order: Dict, reason: Optional[RefundReason]) -> Dict:
        total = order["total_amount"]
        ship = order.get("shipping_fee", 0)
        seller_fault = reason in [
            RefundReason.QUALITY_ISSUE, RefundReason.WRONG_ITEM,
            RefundReason.NOT_AS_DESCRIBED, RefundReason.DAMAGED,
        ]
        ship_refund = ship if seller_fault else 0
        product_refund = total - ship
        return {
            "product_amount": product_refund,
            "shipping_fee": ship_refund,
            "total": product_refund + ship_refund,
            "original_total": total,
            "responsibility": "seller" if seller_fault else "buyer",
        }

    def _gen_plan(
        self,
        order: Dict,
        amount: Dict,
        reason: Optional[RefundReason],
        rag_results: list = None,
    ) -> str:
        """生成退款方案，可选附加 RAG 检索到的相关政策说明。"""
        reason_text = {
            RefundReason.QUALITY_ISSUE: "质量问题",
            RefundReason.WRONG_ITEM: "发错货",
            RefundReason.NOT_AS_DESCRIBED: "描述不符",
            RefundReason.SEVEN_DAY_NO_REASON: "七天无理由退货",
            RefundReason.DAMAGED: "商品破损",
            RefundReason.LATE_DELIVERY: "未按时发货",
            RefundReason.OTHER: "协商退款",
        }.get(reason, "协商退款")

        msg = (
            f"✅ 退款申请评估通过\n\n"
            f"📋 订单信息\n{'━'*20}\n"
            f"订单号：{order['order_id']}\n"
            f"商品：{order['product_name']}\n"
            f"订单金额：¥{order['total_amount']:.2f}\n\n"
            f"💰 退款金额明细\n{'━'*20}\n"
            f"商品金额：¥{amount['product_amount']:.2f}\n"
            f"运费：¥{amount['shipping_fee']:.2f}\n"
            f"{'━'*20}\n"
            f"退款总额：¥{amount['total']:.2f}\n\n"
            f"📝 退款原因：{reason_text}\n"
        )

        if amount["responsibility"] == "seller":
            msg += "💡 因卖家责任，运费全额退还\n"
        else:
            msg += "💡 七天无理由退货，运费由买家承担\n"

        msg += (
            "\n⏱️ 退款时效\n"
            "• 审核：1-3 个工作日\n"
            "• 到账：审核通过后 3-7 个工作日（原路退回）\n"
        )

        # ── RAG 增强：附上最相关的一条政策说明 ──
        policy_hint = self._extract_policy_hint(rag_results)
        if policy_hint:
            msg += f"\n📖 相关政策参考\n{policy_hint}\n"

        msg += "\n回复【确认退款】提交申请，回复【取消】放弃申请"
        return msg

    # ── 工具方法 ──────────────────────────────

    def _extract_policy_hint(self, rag_results: list) -> str:
        """从 RAG 结果中提取最相关的一条政策摘要。"""
        if not rag_results:
            return ""
        # 取相关度最高的一条，截取答案前 80 字
        top = rag_results[0]
        answer_snippet = top.answer[:80].rstrip("。，\n") + "..."
        return f"({top.question}：{answer_snippet})"
