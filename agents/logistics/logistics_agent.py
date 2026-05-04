import re

from agents.base_agent import AgentResponse, BaseAgent, Message


class LogisticsAgent(BaseAgent):
    def __init__(self, store=None, **kwargs):
        super().__init__("logistics", "LogisticsAgent", store=store, **kwargs)

    def process(self, message: Message) -> AgentResponse:
        data = message.data.get("extracted_data", {})
        tracking = data.get("tracking_number")
        if not tracking:
            match = re.search(r"\b([A-Z]{2}\d{9,13})\b", message.content, re.I)
            tracking = match.group(1).upper() if match else None
        if not tracking:
            return AgentResponse(False, "请提供快递单号，我可以查询物流轨迹和异常状态。", data={"need_info": "tracking_number"})
        return self._query(tracking, message.content)

    def _query(self, tracking: str, text: str) -> AgentResponse:
        if not self.store:
            return AgentResponse(False, "物流数据库未连接，请先配置 DATABASE_URL 并运行 seed_data.py。")
        shipment = self.store.get_shipment_by_tracking(tracking)
        if not shipment:
            return AgentResponse(False, f"未找到快递单号 {tracking} 的物流信息。", data={"tracking_number": tracking})
        msg = self._format(shipment)
        if "没收到" in text and shipment.status == "signed":
            msg += "\n\n异常提示：系统显示已签收但您未收到，请先确认家人/驿站代收；若仍未找到，建议转人工核查签收凭证。"
        elif any(k in text for k in ["不动", "没更新", "停滞"]):
            msg += "\n\n异常提示：物流超过 48 小时未更新时，可联系承运商核查；超过 5 个工作日可发起补发或退款调查。"
        return AgentResponse(True, msg, data={"tracking": self._payload(shipment), "action": "query"})

    def _format(self, shipment) -> str:
        lines = [
            "物流详情",
            f"快递单号：{shipment.tracking_number}",
            f"承运商：{shipment.carrier_name}",
            f"当前状态：{shipment.status}",
        ]
        if shipment.estimated_delivery:
            lines.append(f"预计送达：{shipment.estimated_delivery.date()}")
        lines.append("\n物流轨迹：")
        for event in sorted(shipment.events, key=lambda e: e.event_time, reverse=True):
            lines.append(f"- {event.event_time:%Y-%m-%d %H:%M} [{event.location}] {event.status}：{event.detail}")
        return "\n".join(lines)

    def _payload(self, shipment) -> dict:
        return {
            "tracking_number": shipment.tracking_number,
            "carrier_name": shipment.carrier_name,
            "status": shipment.status,
            "events": [
                {"time": e.event_time.isoformat(), "status": e.status, "detail": e.detail, "location": e.location}
                for e in sorted(shipment.events, key=lambda x: x.event_time, reverse=True)
            ],
        }
