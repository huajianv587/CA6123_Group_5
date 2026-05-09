import logging
import re
from datetime import datetime, timedelta
from typing import Optional

from agents.base_agent import AgentResponse, BaseAgent, IntentType, Message

logger = logging.getLogger("logistics_agent")


# ─────────────────────────────────────────────────────────────────────────────
# Autonomous Logistics Intelligence Agent
# ─────────────────────────────────────────────────────────────────────────────

class LogisticsAgent(BaseAgent):
    """Autonomous logistics reasoning agent.

    Beyond simple shipment lookup, this agent performs:
    - Multi-step delivery risk reasoning
    - Dynamic tool selection (shipment DB / carrier API / weather service)
    - Confidence scoring for uncertain data
    - Risk-based human escalation
    - Structured observability traces
    """

    # ── Risk / escalation thresholds ──────────────────────────────────────────
    DELAY_THRESHOLD_HOURS = 48
    HIGH_RISK_THRESHOLD = 0.75
    LOW_CONFIDENCE_THRESHOLD = 0.70

    def __init__(self, store=None, **kwargs):
        super().__init__("logistics", "LogisticsAgent", store=store, **kwargs)
        self.carriers = {
            "SF": "SF Express",
            "JD": "JD Logistics",
            "YT": "YTO Express",
            "ZT": "ZTO Express",
            "YD": "Yunda Express",
        }

    # ── Entry point ───────────────────────────────────────────────────────────

    def process(self, message: Message) -> AgentResponse:
        data = message.data.get("extracted_data", {})
        tracking = data.get("tracking_number")
        if not tracking:
            match = re.search(r"\b([A-Z]{2}\d{9,13})\b", message.content, re.I)
            tracking = match.group(1).upper() if match else None

        if not tracking:
            return AgentResponse(
                False,
                "Please provide a tracking number so I can look up the shipment, assess delivery risk, and recommend next steps.",
                data={"need_info": "tracking_number"},
            )

        return self._run_reasoning_pipeline(tracking, message)

    # ── Autonomous reasoning pipeline ─────────────────────────────────────────

    def _run_reasoning_pipeline(self, tracking: str, message: Message) -> AgentResponse:
        """Five-step autonomous reasoning loop:
        1. Perceive  – retrieve shipment context
        2. Analyse   – compute delay severity & anomaly type
        3. Enrich    – dynamic tool selection (weather, carrier)
        4. Evaluate  – risk score + confidence score
        5. Decide    – generate mitigation plan & escalation decision
        """
        reasoning_trace: list[str] = []
        tools_invoked: list[str] = []

        # ── Step 1: Perceive ──────────────────────────────────────────────────
        reasoning_trace.append("Step 1 [Perceive] Retrieving shipment context.")
        shipment, source = self._fetch_shipment(tracking)
        tools_invoked.append(source)

        if shipment is None:
            return AgentResponse(
                False,
                f"No shipment information found for tracking number {tracking}. Escalating to human operator for manual verification.",
                data={"tracking_number": tracking, "reasoning_trace": reasoning_trace},
                need_escalate=True,
                escalate_reason="shipment_not_found",
            )

        reasoning_trace.append(
            f"Step 1 [Perceive] Shipment {tracking} retrieved via {source}. "
            f"Status: {shipment.get('status', 'unknown')}."
        )

        # ── Step 2: Analyse – delay & anomaly detection ───────────────────────
        reasoning_trace.append("Step 2 [Analyse] Evaluating delay severity and anomaly type.")
        delay_hours = self._compute_delay_hours(shipment)
        anomaly = self._detect_anomaly(shipment, message.content, delay_hours)

        if delay_hours > self.DELAY_THRESHOLD_HOURS:
            reasoning_trace.append(
                f"Step 2 [Analyse] Delay EXCEEDS threshold: {delay_hours:.1f} h > {self.DELAY_THRESHOLD_HOURS} h."
            )
        if anomaly:
            reasoning_trace.append(f"Step 2 [Analyse] Anomaly detected: {anomaly}.")

        # ── Step 3: Enrich – dynamic tool selection ───────────────────────────
        reasoning_trace.append("Step 3 [Tool Selection] Selecting external enrichment tools.")
        weather_risk, weather_detail = self._invoke_weather_service(shipment)
        tools_invoked.append("weather_service")

        if weather_risk:
            reasoning_trace.append(f"Step 3 [Tool Selection] Weather disruption detected: {weather_detail}.")
        else:
            reasoning_trace.append("Step 3 [Tool Selection] No weather disruption detected.")

        carrier_reachable = self._invoke_carrier_api(tracking)
        tools_invoked.append("carrier_api")
        if not carrier_reachable:
            reasoning_trace.append("Step 3 [Tool Selection] Carrier API unreachable – reliability reduced.")

        # ── Step 4: Evaluate – risk + confidence ──────────────────────────────
        reasoning_trace.append("Step 4 [Evaluate] Computing risk score and confidence score.")
        risk_score = self._compute_risk(delay_hours, anomaly, weather_risk, shipment)
        confidence_score = self._compute_confidence(shipment, carrier_reachable)

        reasoning_trace.append(
            f"Step 4 [Evaluate] Risk score: {risk_score:.2f} | Confidence score: {confidence_score:.2f}."
        )

        # ── Step 5: Decide – mitigation + escalation ──────────────────────────
        reasoning_trace.append("Step 5 [Decide] Generating mitigation strategy and escalation decision.")
        mitigation = self._plan_mitigation(delay_hours, anomaly, weather_risk, risk_score)
        escalation_required = (
            risk_score >= self.HIGH_RISK_THRESHOLD
            or confidence_score < self.LOW_CONFIDENCE_THRESHOLD
        )

        if escalation_required:
            escalation_reason = (
                f"risk_score={risk_score:.2f} >= {self.HIGH_RISK_THRESHOLD}"
                if risk_score >= self.HIGH_RISK_THRESHOLD
                else f"confidence_score={confidence_score:.2f} < {self.LOW_CONFIDENCE_THRESHOLD}"
            )
            reasoning_trace.append(
                f"Step 5 [Decide] Human escalation REQUIRED — {escalation_reason}."
            )
        else:
            reasoning_trace.append("Step 5 [Decide] Autonomous resolution is sufficient.")

        # ── Observability logging ─────────────────────────────────────────────
        obs_record = {
            "tracking_number": tracking,
            "intent": "logistics_query",
            "tools_invoked": tools_invoked,
            "delay_hours": round(delay_hours, 1),
            "anomaly": anomaly,
            "weather_risk": weather_risk,
            "risk_score": round(risk_score, 2),
            "confidence_score": round(confidence_score, 2),
            "mitigation": mitigation,
            "human_escalation": escalation_required,
            "reasoning_trace": reasoning_trace,
        }
        logger.info("[OBSERVABILITY] %s", obs_record)

        # ── Build response ────────────────────────────────────────────────────
        response_message = self._build_response_message(
            shipment=shipment,
            source=source,
            delay_hours=delay_hours,
            anomaly=anomaly,
            weather_risk=weather_risk,
            weather_detail=weather_detail,
            risk_score=risk_score,
            confidence_score=confidence_score,
            mitigation=mitigation,
            escalation_required=escalation_required,
            reasoning_trace=reasoning_trace,
        )

        return AgentResponse(
            success=True,
            message=response_message,
            data={
                "tracking": shipment,
                "risk_score": round(risk_score, 2),
                "confidence_score": round(confidence_score, 2),
                "reasoning_trace": reasoning_trace,
                "tools_invoked": tools_invoked,
                "mitigation": mitigation,
                "escalation_required": escalation_required,
                "observability": obs_record,
            },
            need_escalate=escalation_required,
            escalate_reason=(
                f"High risk ({risk_score:.2f}) or low confidence ({confidence_score:.2f})"
                if escalation_required else ""
            ),
        )

    # ── Tool 1: Shipment fetch (DB → external fallback) ───────────────────────

    def _fetch_shipment(self, tracking: str) -> tuple[Optional[dict], str]:
        if self.store:
            shipment = self.store.get_shipment_by_tracking(tracking)
            if shipment:
                return self._payload(shipment), "shipment_database"

        # External API fallback
        result = self._call_external_api(tracking)
        if result:
            return result, "carrier_api_external"
        return None, "not_found"

    # ── Tool 2: Weather service (mock / pluggable) ────────────────────────────

    def _invoke_weather_service(self, shipment: dict) -> tuple[bool, str]:
        """Mock weather disruption service.

        Replace the body with a real API call (e.g. OpenWeatherMap) if available.
        The reasoning layer treats this identically regardless of data source.
        """
        status = shipment.get("status", "")
        events = shipment.get("events", [])
        last_location = events[0].get("location", "") if events else ""

        # Heuristic simulation: treat known high-risk keywords as weather signal
        weather_keywords = ["heavy rain", "typhoon", "snowstorm", "flood", "storm", "blizzard"]
        for kw in weather_keywords:
            if kw.lower() in last_location.lower():
                return True, f"Severe weather condition detected near {last_location}"

        # Simulate stochastic disruption for stuck/delayed shipments (demo-friendly)
        if status in ("stuck", "Delayed", "In Transit") and shipment.get("delay_hours", 0) > 24:
            import random
            random.seed(hash(shipment.get("tracking_number", "")) % 1000)
            if random.random() < 0.35:
                return True, "Regional weather disruption likely along current route"

        return False, ""

    # ── Tool 3: Carrier API reachability probe ────────────────────────────────

    def _invoke_carrier_api(self, tracking: str) -> bool:
        """Returns True when carrier data can be confirmed externally.

        Replace with a real ping/API call; currently returns True for known
        carrier prefixes and False for unrecognised ones.
        """
        code = tracking[:2].upper()
        return code in self.carriers

    # ── Risk scoring ──────────────────────────────────────────────────────────

    def _compute_risk(
        self,
        delay_hours: float,
        anomaly: Optional[str],
        weather_risk: bool,
        shipment: dict,
    ) -> float:
        risk = 0.10  # base

        if delay_hours > 24:
            risk += 0.25
        if delay_hours > self.DELAY_THRESHOLD_HOURS:
            risk += 0.25

        if shipment.get("status") in ("stuck", "Delayed"):
            risk += 0.20

        if weather_risk:
            risk += 0.15

        if anomaly == "signed_not_received":
            risk += 0.30  # potential fraud / misdelivery
        elif anomaly == "stagnant":
            risk += 0.15

        return min(risk, 1.0)

    # ── Confidence scoring ────────────────────────────────────────────────────

    def _compute_confidence(self, shipment: dict, carrier_reachable: bool) -> float:
        confidence = 0.95

        events = shipment.get("events", [])
        if not events:
            confidence -= 0.30  # no tracking events → high uncertainty

        if shipment.get("status") in ("unknown", ""):
            confidence -= 0.20

        if not carrier_reachable:
            confidence -= 0.20

        # Penalise stale last-event
        if events:
            try:
                last_time_str = events[0].get("time", "")
                last_time = datetime.fromisoformat(last_time_str.replace("Z", "+00:00"))
                hours_since = (datetime.utcnow() - last_time.replace(tzinfo=None)).total_seconds() / 3600
                if hours_since > 72:
                    confidence -= 0.15
            except (ValueError, TypeError):
                confidence -= 0.10

        return max(confidence, 0.0)

    # ── Delay computation ─────────────────────────────────────────────────────

    def _compute_delay_hours(self, shipment: dict) -> float:
        estimated = shipment.get("estimated_delivery")
        if not estimated:
            return 0.0
        try:
            if isinstance(estimated, str):
                eta = datetime.fromisoformat(estimated)
            else:
                eta = datetime.combine(estimated, datetime.min.time())
            delta = datetime.utcnow() - eta
            return max(delta.total_seconds() / 3600, 0.0)
        except (ValueError, TypeError):
            return 0.0

    # ── Anomaly detection ─────────────────────────────────────────────────────

    def _detect_anomaly(self, shipment: dict, text: str, delay_hours: float) -> Optional[str]:
        if "not received" in text.lower() and shipment.get("status") == "signed":
            return "signed_not_received"
        if any(k in text.lower() for k in ["not moving", "no update", "stagnant", "stuck"]) or delay_hours > self.DELAY_THRESHOLD_HOURS:
            return "stagnant"
        return None

    # ── Mitigation planner ────────────────────────────────────────────────────

    def _plan_mitigation(
        self,
        delay_hours: float,
        anomaly: Optional[str],
        weather_risk: bool,
        risk_score: float,
    ) -> str:
        if anomaly == "signed_not_received":
            return "Initiate misdelivery investigation; request proof-of-delivery from carrier; consider reshipping."
        if weather_risk and delay_hours > self.DELAY_THRESHOLD_HOURS:
            return "Reroute via alternate transit hub; estimated recovery time 12–24 hours; notify customer proactively."
        if delay_hours > self.DELAY_THRESHOLD_HOURS:
            return "Contact carrier for priority handling; if unresolved within 2 business days, escalate to refund assessment."
        if risk_score >= self.HIGH_RISK_THRESHOLD:
            return "Flag case for human review; provide customer with interim compensation options."
        return "Continue monitoring; auto-notify customer if next update exceeds 24 hours."

    # ── Response builder ──────────────────────────────────────────────────────

    def _build_response_message(
        self,
        shipment: dict,
        source: str,
        delay_hours: float,
        anomaly: Optional[str],
        weather_risk: bool,
        weather_detail: str,
        risk_score: float,
        confidence_score: float,
        mitigation: str,
        escalation_required: bool,
        reasoning_trace: list[str],
    ) -> str:
        source_label = "(source: internal database)" if source == "shipment_database" else "(source: external carrier API)"
        lines = [
            f"── Shipment Details {source_label} ──",
            f"Tracking Number : {shipment.get('tracking_number', 'N/A')}",
            f"Carrier         : {shipment.get('carrier_name', 'N/A')}",
            f"Current Status  : {shipment.get('status', 'N/A')}",
        ]
        if shipment.get("estimated_delivery"):
            lines.append(f"Est. Delivery   : {shipment['estimated_delivery']}")

        events = shipment.get("events", [])
        if events:
            lines.append("\nTracking History:")
            for event in events:
                t = event.get("time", "")[:16].replace("T", " ")
                lines.append(f"  - {t} [{event.get('location', '')}] {event.get('status', '')}: {event.get('detail', '')}")

        # ── Agent reasoning summary ───────────────────────────────────────────
        lines.append("\n── Agent Reasoning Summary ──")
        risk_label = "🔴 High" if risk_score >= 0.75 else ("🟡 Medium" if risk_score >= 0.4 else "🟢 Low")
        conf_label = "⚠️ Low" if confidence_score < 0.7 else "✅ Normal"
        lines.append(f"Delivery Risk Score : {risk_score:.2f}  [{risk_label}]")
        lines.append(f"Data Confidence     : {confidence_score:.2f}  [{conf_label}]")

        if weather_risk:
            lines.append(f"Weather Disruption  : ⚠️  {weather_detail}")
        if anomaly:
            anomaly_label = {
                "signed_not_received": "Signed as delivered but customer has not received the parcel (possible misdelivery or fraud)",
                "stagnant": "Shipment has had no tracking updates for an extended period",
            }.get(anomaly, anomaly)
            lines.append(f"Anomaly Detected    : {anomaly_label}")

        lines.append(f"\nRecommended Action: {mitigation}")

        if escalation_required:
            lines.append(
                "\n⚠️  Human escalation triggered: this case has a high risk score or low data confidence. "
                "Transferring to a human operator for review."
            )

        return "\n".join(lines)

    # ── Payload helpers ───────────────────────────────────────────────────────

    def _payload(self, shipment) -> dict:
        """Convert ORM shipment object to plain dict."""
        return {
            "tracking_number": shipment.tracking_number,
            "carrier_name": shipment.carrier_name,
            "status": shipment.status,
            "estimated_delivery": (
                shipment.estimated_delivery.isoformat()
                if shipment.estimated_delivery else None
            ),
            "events": [
                {
                    "time": e.event_time.isoformat(),
                    "status": e.status,
                    "detail": e.detail,
                    "location": e.location,
                }
                for e in sorted(shipment.events, key=lambda x: x.event_time, reverse=True)
            ],
        }

    def _call_external_api(self, tracking: str) -> Optional[dict]:
        """Simulated external carrier API. Replace with real HTTP call in production."""
        code = tracking[:2].upper()
        carrier = self.carriers.get(code)
        if not carrier:
            return None

        now = datetime.utcnow()
        return {
            "tracking_number": tracking.upper(),
            "carrier_name": carrier,
            "status": "In Transit",
            "estimated_delivery": (now + timedelta(days=2)).isoformat(),
            "events": [
                {
                    "time": (now - timedelta(hours=6)).isoformat(),
                    "status": "Picked Up",
                    "detail": "Parcel collected by carrier at origin facility",
                    "location": "Origin Warehouse",
                },
                {
                    "time": (now - timedelta(hours=2)).isoformat(),
                    "status": "In Transit",
                    "detail": "Parcel being processed at sorting hub",
                    "location": "Sorting Hub",
                },
            ],
        }


# ── Module-level run() for direct invocation / integration tests ──────────────

def run(input_data: dict) -> dict:
    agent = LogisticsAgent()
    message = Message(
        sender="router",
        receiver="logistics",
        intent=IntentType.LOGISTICS,
        content=input_data.get("query", ""),
        data={"extracted_data": {"tracking_number": input_data.get("tracking_number")}},
    )
    result = agent.process(message)
    return {
        "agent": "LogisticsAgent",
        "status": "success" if result.success else "fail",
        "answer": result.message,
        "data": result.data,
        "need_human": result.need_escalate,
        "escalate_reason": result.escalate_reason,
    }
