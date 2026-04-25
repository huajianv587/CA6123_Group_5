"""
投诉Agent - 情绪识别 + 安抚话术 + 自动升级人工
"""
import random
from typing import Dict, List, Optional
from datetime import datetime
from .base_agent import BaseAgent, Message, AgentResponse, IntentType


class ComplaintAgent(BaseAgent):

    def __init__(self):
        super().__init__("complaint", "ComplaintAgent")
        self.emotion_lexicon = {
            "angry":       {"kws": ["气", "怒", "火", "炸", "死", "滚", "垃圾", "坑", "骗", "差", "烂",
                                    "混蛋", "可恶", "恶心", "受够了", "忍无可忍", "火大"], "w": 2.0},
            "urgent":      {"kws": ["急", "快", "马上", "立刻", "必须", "赶紧", "刻不容缓"], "w": 1.5},
            "disappointed":{"kws": ["失望", "后悔", "不该", "上当", "受骗", "心寒", "无语", "无奈"], "w": 1.5},
            "threatening": {"kws": ["曝光", "媒体", "12315", "投诉", "告", "法院", "律师", "工商局",
                                    "消协", "消费者协会", "电视台", "记者", "微博", "朋友圈", "抖音"], "w": 2.5},
            "escalation":  {"kws": ["经理", "主管", "领导", "负责人", "老板", "人工", "真人", "活人",
                                    "不要机器人", "找人工", "转人工"], "w": 1.8},
        }
        self.comfort_phrases = {
            "low":    ["理解您的感受，我们会尽快为您处理。",
                       "非常抱歉给您带来不便，让我来帮您解决。"],
            "medium": ["真的非常抱歉让您有这样的体验，我完全理解您的心情。",
                       "您的不满我们非常重视，请给我一次机会帮您解决。"],
            "high":   ["非常抱歉让您如此生气，这确实是我们服务的失误。",
                       "我能感受到您的愤怒，请相信我们一定会妥善处理。"],
        }
        self.solution_templates = {
            "delivery_delay": {"triggers": ["没到", "慢", "等太久", "延迟"],
                               "response": "关于配送延迟，我会立即联系物流核实，2小时内给您回复，如确认延误可申请补偿。"},
            "quality_issue":  {"triggers": ["质量", "坏", "破", "瑕疵"],
                               "response": "质量问题我们承担全责。您可以选择：①全额退款  ②换货  ③补偿优惠券，请告知偏好。"},
            "service_issue":  {"triggers": ["态度", "客服", "不理", "不回复"],
                               "response": "对于客服服务问题我会记录反馈给服务主管，并亲自跟进您的问题直到解决。"},
            "wrong_item":     {"triggers": ["发错", "不对", "少发", "漏发"],
                               "response": "发错货是我们的失误，我们会立即安排补发，错误商品您可以选择退回或保留。"},
        }
        self.complaint_records: List[Dict] = []

    def process(self, message: Message) -> AgentResponse:
        content = message.content
        data = message.data
        self.log(f"处理投诉/情绪问题: {content}")
        router_emotion = data.get("emotion_level", {})
        detailed = self._analyze_emotion(content)
        final_emotion = self._merge(router_emotion, detailed)
        need_escalate, reason = self._check_escalation(final_emotion, data, message.session_id)
        if need_escalate:
            return self._do_escalation(content, final_emotion, reason, message.session_id)
        return AgentResponse(
            success=True,
            message=self._comfort_response(content, final_emotion, message.session_id),
            data={"emotion_analysis": final_emotion, "action": "comfort"},
        )

    def _analyze_emotion(self, content: str) -> Dict:
        scores = {k: 0.0 for k in self.emotion_lexicon}
        for etype, cfg in self.emotion_lexicon.items():
            for kw in cfg["kws"]:
                scores[etype] += content.count(kw) * cfg["w"]
        total = sum(scores.values())
        level = "high" if total >= 8 else "medium" if total >= 3 else "low"
        demands = [stype for stype, tcfg in self.solution_templates.items()
                   if any(t in content for t in tcfg["triggers"])]
        return {"level": level, "total_score": total, "scores": scores,
                "dominant": max(scores, key=scores.get) if total > 0 else None,
                "demands": demands}

    def _merge(self, router: Dict, detailed: Dict) -> Dict:
        prio = {"high": 3, "medium": 2, "low": 1}
        rl, dl = router.get("level", "low"), detailed["level"]
        final_level = dl if prio.get(dl, 0) >= prio.get(rl, 0) else rl
        return {**detailed, "level": final_level}

    def _check_escalation(self, emotion: Dict, data: Dict, session_id: str) -> tuple:
        reasons = []
        if emotion["total_score"] >= 8:
            reasons.append(f"情绪激烈（分数：{emotion['total_score']:.1f}）")
        if emotion["scores"].get("threatening", 0) >= 2:
            reasons.append("用户提及投诉/曝光/法律途径")
        if emotion["scores"].get("escalation", 0) >= 1:
            reasons.append("用户明确要求转人工")
        count = sum(1 for r in self.complaint_records if r.get("session_id") == session_id)
        if count >= 3:
            reasons.append(f"重复投诉（{count}次）")
        return bool(reasons), "；".join(reasons)

    def _do_escalation(self, content: str, emotion: Dict, reason: str, session_id: str) -> AgentResponse:
        self.complaint_records.append({
            "session_id": session_id, "content": content,
            "emotion": emotion, "escalate_reason": reason,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "escalated",
        })
        msg = (f"🚨 正在为您转接人工客服\n\n"
               f"非常抱歉让您有如此不愉快的体验。\n\n"
               f"📋 已为您记录：\n{'━'*20}\n"
               f"• 情绪等级：{emotion['level'].upper()}\n"
               f"• 升级原因：{reason}\n"
               f"• 优先级别：紧急\n\n"
               f"👤 人工客服信息：\n{'━'*20}\n"
               f"• 当前排队：3 人\n"
               f"• 预计等待：2-3 分钟\n"
               f"• 服务专员：高级客服经理\n\n"
               f"⏱️ 在等待期间请保持电话畅通，我们会优先处理您的问题。")
        return AgentResponse(success=True, message=msg,
                             data={"emotion_analysis": emotion, "action": "escalate"},
                             need_escalate=True, escalate_reason=reason)

    def _comfort_response(self, content: str, emotion: Dict, session_id: str) -> str:
        level = emotion["level"]
        comfort = random.choice(self.comfort_phrases[level])
        solution = ""
        for d in emotion.get("demands", []):
            if d in self.solution_templates:
                solution = self.solution_templates[d]["response"]
                break
        resp = comfort + "\n\n"
        if solution:
            resp += solution + "\n\n"
        tips = {"high": "💡 如处理不满意，随时可要求转接人工客服。",
                "medium": "💡 我会持续跟进，确保问题妥善解决。",
                "low": "💡 还有其他我可以帮您的吗？"}
        resp += tips.get(level, "")
        self.complaint_records.append({
            "session_id": session_id, "content": content,
            "emotion": emotion, "status": "handled",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
        return resp
