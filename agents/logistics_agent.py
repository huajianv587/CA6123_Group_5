"""
Logistics Agent - Logistics Inquiry + Simulated External Logistics API Call
"""
import re
import time
import random
from typing import Dict, Optional
from datetime import datetime, timedelta
from .base_agent import BaseAgent, Message, AgentResponse, IntentType


class LogisticsAgent(BaseAgent):

    def __init__(self):
        super().__init__("logistics", "LogisticsAgent")
        self.carriers = {"SF": "顺丰速运", "JD": "京东物流",
                         "YT": "圆通速递", "ZT": "中通快递", "YD": "韵达速递"}
        self.mock_tracking = self._init_mock_tracking()

    def _init_mock_tracking(self) -> Dict[str, Dict]:
        t = datetime.now()
        return {
            "SF1234567890": {
                "tracking_number": "SF1234567890", "carrier_code": "SF",
                "carrier_name": "顺丰速运", "status": "派送中",
                "estimated_delivery": (t + timedelta(days=1)).strftime("%Y-%m-%d"),
                "timeline": [
                    {"time": (t - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M"),
                     "status": "派送中", "detail": "快递员正在派送中",
                     "location": "北京市朝阳区"},
                ],
            }
        }

    def process(self, message: Message) -> AgentResponse:
        content = message.content
        data = message.data
        self.log(f"处理物流请求: {content}")

        tracking = data.get("extracted_data", {}).get("tracking_number")

        if not tracking:
            m = re.search(r"\b([A-Z]{2}\d{9,13})\b", content, re.IGNORECASE)
            if m:
                tracking = m.group(1)

        if tracking:
            return self._query_tracking(tracking)

        return AgentResponse(
            success=False,
            message="请提供快递单号，我可以帮您查询物流状态。",
            data={"error": "missing_tracking"}
        )

    def _query_tracking(self, number: str) -> AgentResponse:
        self.log(f"查询物流单号: {number}")
        time.sleep(0.2)

        result, api_error = self._call_external_api(number)

        if api_error:
            return AgentResponse(
                success=False,
                message=f"物流系统暂时不可用，请稍后再试（单号：{number}）",
                data={"error": "api_unavailable"}
            )

        if result:
            return AgentResponse(
                success=True,
                message=self._format_tracking(result),
                data={"tracking": result}
            )

        return AgentResponse(
            success=False,
            message=f"未找到单号 {number} 的物流信息",
            data={"error": "not_found"}
        )

    def _call_external_api(self, number: str) -> tuple[Optional[Dict], bool]:
        try:
            if random.random() < 0.3:
                raise ConnectionError("API失败")

            if random.random() > 0.5:
                t = datetime.now()
                return {
                    "tracking_number": number,
                    "carrier_name": "顺丰速运",
                    "status": "运输中",
                    "estimated_delivery": (t + timedelta(days=2)).strftime("%Y-%m-%d"),
                    "timeline": []
                }, False

            return None, False

        except Exception:
            return None, True

    def _format_tracking(self, t: Dict) -> str:
        return f"📦 单号：{t['tracking_number']}\n🚚 状态：{t['status']}\n📅 预计送达：{t.get('estimated_delivery','未知')}"



def run(input_data: dict) -> dict:
    agent = LogisticsAgent()

    message = Message(
        content=input_data.get("query", ""),
        data={
            "extracted_data": {
                "tracking_number": input_data.get("tracking_number")
            }
        }
    )

    result = agent.process(message)

    error_type = result.data.get("error") if result.data else None

    if result.success:
        type_ = "normal"
    elif error_type == "not_found":
        type_ = "not_found"
    else:
        type_ = "exception"

  
    need_human = error_type == "api_unavailable"

    return {
        "agent": "LogisticsAgent",
        "status": "success" if result.success else "fail",
        "type": type_,
        "answer": result.message,
        "data": result.data,
        "need_human": need_human,
        "error": error_type
    }
