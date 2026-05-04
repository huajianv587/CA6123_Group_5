"""
智能客服系统 - 中央协调器
v2: 统一创建 KnowledgeRetriever，注入到各 Agent
"""
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

import uuid
from typing import Dict, Optional, List
from datetime import datetime

from agents import (
    RouterAgent, OrderAgent, LogisticsAgent,
    RefundAgent, ComplaintAgent,
    Message, AgentResponse, IntentType,
)
from knowledge import KnowledgeRetriever


class CustomerServiceOrchestrator:
    """
    中央协调器 v2

    RAG 改造说明：
      - 启动时创建唯一的 KnowledgeRetriever 实例（共享，避免重复建索引）
      - 将 retriever 注入到所有支持 RAG 的 Agent
      - 统计信息新增 rag_usage 计数
    """

    def __init__(self, build_index_on_start: bool = False):
        """
        Args:
            build_index_on_start: 是否在启动时预热向量索引。
                True  → 启动稍慢，首次查询快。
                False → 启动快，首次 RAG 查询时懒加载（默认）。
        """
        # ── 创建共享检索器 ──────────────────────
        self.retriever = KnowledgeRetriever(score_threshold=0.60)
        if build_index_on_start:
            print("🔍 预热向量索引...")
            self.retriever.build_index()
            print("✅ 向量索引构建完成")

        # ── 初始化各 Agent（按需注入 retriever）──
        self.router = RouterAgent()
        self.order_agent = OrderAgent()
        self.logistics_agent = LogisticsAgent()
        self.refund_agent = RefundAgent(retriever=self.retriever)         # 退款规则 RAG
        self.complaint_agent = ComplaintAgent()                           # 暂不注入

        self.agents = {
            "router": self.router,
            "order": self.order_agent,
            "logistics": self.logistics_agent,
            "refund": self.refund_agent,
            "complaint": self.complaint_agent,
        }

        self.sessions: Dict[str, Dict] = {}
        self.stats = {
            "total_requests": 0,
            "escalation_count": 0,
            "intent_distribution": {i.value: 0 for i in IntentType},
            # ── RAG 新增统计 ──
            "rag_hits": 0,        # 成功使用 RAG 的次数
            "rag_sources": {},    # 各 doc_id 被召回次数
        }

    # ── 主处理流程（与原版完全相同，新增 RAG 统计）──

    def process_message(self, user_input: str, session_id: str = None) -> Dict:
        if not session_id or session_id not in self.sessions:
            session_id = self._create_session()
        session = self.sessions[session_id]
        session["messages"].append({
            "role": "user",
            "content": user_input,
            "timestamp": datetime.now().isoformat(),
        })
        self.stats["total_requests"] += 1

        print(f"\n{'='*60}")
        print(f"📝 用户输入: {user_input}")
        print(f"🆔 会话ID: {session_id}")
        print(f"{'='*60}\n")

        # Step 1: 意图路由
        router_msg = Message(
            sender="user", receiver="router",
            intent=IntentType.UNKNOWN,
            content=user_input, session_id=session_id,
        )
        router_resp = self.router.receive_message(router_msg)
        intent = router_resp.data.get("intent", "unknown")

        print(
            f"🤖 [RouterAgent] 意图={intent}  "
            f"置信度={router_resp.data.get('confidence', 0):.2f}  "
            f"情绪={router_resp.data.get('emotion_level', {}).get('level', 'low')}  "
            f"→ {router_resp.next_agent}\n"
        )

        if intent in self.stats["intent_distribution"]:
            self.stats["intent_distribution"][intent] += 1

        # Step 2: 业务处理
        target_id = router_resp.next_agent
        target = self.agents.get(target_id)
        if not target:
            return self._error(session_id, "找不到对应处理 Agent")

        biz_msg = Message(
            sender="router", receiver=target_id,
            intent=IntentType(intent),
            content=user_input,
            data=router_resp.data,
            session_id=session_id,
        )
        biz_resp = target.receive_message(biz_msg)

        rag_flag = "✅" if biz_resp.rag_used else "—"
        print(
            f"🤖 [{target.name}] 成功={biz_resp.success}  "
            f"升级人工={biz_resp.need_escalate}  "
            f"RAG={rag_flag} {biz_resp.rag_sources}\n"
        )

        # ── RAG 统计 ──────────────────────────
        if biz_resp.rag_used:
            self.stats["rag_hits"] += 1
            for src in biz_resp.rag_sources:
                self.stats["rag_sources"][src] = (
                    self.stats["rag_sources"].get(src, 0) + 1
                )

        if biz_resp.need_escalate:
            self.stats["escalation_count"] += 1
            session["status"] = "escalated"

        session["messages"].append({
            "role": "assistant",
            "content": biz_resp.message,
            "agent": target_id,
            "rag_used": biz_resp.rag_used,
            "rag_sources": biz_resp.rag_sources,
            "timestamp": datetime.now().isoformat(),
        })

        return {
            "success": True,
            "session_id": session_id,
            "response": biz_resp.message,
            "intent": intent,
            "agent": target_id,
            "need_escalate": biz_resp.need_escalate,
            "escalate_reason": biz_resp.escalate_reason,
            "data": biz_resp.data,
            # ── RAG 新增返回字段 ──
            "rag_used": biz_resp.rag_used,
            "rag_sources": biz_resp.rag_sources,
        }

    # ── 会话管理 ──────────────────────────────

    def _create_session(self) -> str:
        sid = str(uuid.uuid4())[:8]
        self.sessions[sid] = {
            "session_id": sid,
            "created_at": datetime.now().isoformat(),
            "status": "active",
            "messages": [],
            "context": {},
        }
        print(f"✨ 创建新会话: {sid}")
        return sid

    def _error(self, session_id: str, msg: str) -> Dict:
        return {
            "success": False,
            "session_id": session_id,
            "response": f"抱歉，系统出现错误：{msg}",
            "intent": "error",
            "agent": None,
            "need_escalate": True,
            "escalate_reason": "系统错误",
            "data": {},
            "rag_used": False,
            "rag_sources": [],
        }

    # ── 统计 ──────────────────────────────────

    def get_stats(self) -> Dict:
        total = self.stats["total_requests"]
        rag_rate = (self.stats["rag_hits"] / total * 100) if total else 0
        return {
            **self.stats,
            "total_sessions": len(self.sessions),
            "active_sessions": sum(
                1 for s in self.sessions.values() if s["status"] == "active"
            ),
            "escalated_sessions": sum(
                1 for s in self.sessions.values() if s["status"] == "escalated"
            ),
            "rag_hit_rate": f"{rag_rate:.1f}%",
            "retriever_stats": self.retriever.get_stats(),
        }


# ── 单例 ───────────────────────────────────────

_orchestrator: Optional[CustomerServiceOrchestrator] = None

def get_orchestrator(build_index_on_start: bool = False) -> CustomerServiceOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = CustomerServiceOrchestrator(
            build_index_on_start=build_index_on_start
        )
    return _orchestrator
