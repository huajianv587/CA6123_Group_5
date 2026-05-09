"""Inject a deterministic demo shipment for the logistics-agent video.

Why this script exists:
    The default seed dataset never produces an active delay or a weather-
    disrupted location, so the logistics agent's full reasoning trace
    (Step 2 delay > 48h + Step 3 weather tool fires + Step 5 escalation)
    cannot be reproduced reliably for a recorded demo.

    This script injects ONE deterministic shipment whose tracking number,
    delay window, and last-event location are hard-coded so the demo
    always tells the same story:

        Order ID         : 999999999001
        Tracking Number  : SF9999000001
        ETA              : 72 hours in the past
        Last Location    : "Shenzhen Sorting Hub - Typhoon Mawar zone"
        Status           : in_transit

Usage:
    # 1. Make sure DATABASE_URL points at the same DB the app is using
    #    (defaults to .env; for SQLite the local dev DB is fine too).
    # 2. Run idempotently:
    python scripts/seed_demo_shipment.py

    # 3. In the UI, enter order ID  202404259001  to trigger the demo.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Allow running from repo root without installing as a package.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from shared import models  # noqa: E402
from shared.database import session_scope, init_db  # noqa: E402


DEMO_ORDER_ID = "202404259001"
DEMO_TRACKING_NUMBER = "SF9999000001"


def _ensure_demo_customer(db) -> models.Customer:
    cust = (
        db.query(models.Customer)
        .filter(models.Customer.email == "demo.delay@example.com")
        .one_or_none()
    )
    if cust:
        return cust
    cust = models.Customer(
        name="Demo 客户(物流延误演示)",
        phone="13800009999",
        email="demo.delay@example.com",
        member_level="vip",
    )
    db.add(cust)
    db.flush()
    return cust


def _delete_existing_demo(db) -> None:
    existing = (
        db.query(models.Order)
        .filter(models.Order.order_id == DEMO_ORDER_ID)
        .one_or_none()
    )
    if existing is not None:
        # Cascade: items + shipment(+events) + refunds are configured to
        # delete with the parent.
        db.delete(existing)
        db.flush()

    # Clean up any orphan shipments using the same tracking number.
    orphan = (
        db.query(models.Shipment)
        .filter(models.Shipment.tracking_number == DEMO_TRACKING_NUMBER)
        .one_or_none()
    )
    if orphan is not None:
        db.delete(orphan)
        db.flush()


def seed() -> None:
    init_db()
    now = datetime.utcnow()
    eta_overdue = now - timedelta(hours=72)  # 72h overdue → exceeds 48h threshold

    with session_scope() as db:
        _delete_existing_demo(db)
        customer = _ensure_demo_customer(db)

        order = models.Order(
            order_id=DEMO_ORDER_ID,
            customer_id=customer.id,
            status="shipped",
            payment_status="paid",
            total_amount=9999.0,
            shipping_fee=0.0,
            receive_address={
                "name": customer.name,
                "phone": customer.phone,
                "province": "广东省",
                "city": "深圳市",
                "district": "南山区",
                "detail": "科技园南区 1 号",
            },
            can_cancel=False,
            can_modify_address=False,
            created_at=now - timedelta(days=6),
            shipped_at=now - timedelta(days=5),
            received_at=None,
        )
        db.add(order)
        db.flush()

        db.add(
            models.OrderItem(
                order_id=order.id,
                product_name="iPhone 15 Pro Max (Demo Delayed Order)",
                sku="SKU-IP15PM-DEMO",
                unit_price=9999.0,
                quantity=1,
            )
        )

        shipment = models.Shipment(
            order_id=order.id,
            tracking_number=DEMO_TRACKING_NUMBER,
            carrier_code="SF",
            carrier_name="SF Express",
            status="in_transit",
            estimated_delivery=eta_overdue,
            signed_by=None,
        )
        db.add(shipment)
        db.flush()

        # Three events, last one ~30h ago → triggers "stale tracking" confidence
        # penalty AND the weather keyword in the location triggers the weather
        # tool deterministically. The delay vs. ETA is 72h (overdue).
        events = [
            (
                now - timedelta(hours=120),
                "picked",
                "快递员已揽收",
                "深圳发货仓",
            ),
            (
                now - timedelta(hours=80),
                "in_transit",
                "包裹已抵达广州转运中心,正在分拣",
                "广州转运中心",
            ),
            (
                now - timedelta(hours=30),
                "in_transit",
                "包裹滞留 - 受台风天气影响,后续派送时间待定 (Typhoon Mawar)",
                "Shenzhen Sorting Hub - Typhoon Mawar zone",
            ),
        ]
        for event_time, status, detail, location in events:
            db.add(
                models.ShipmentEvent(
                    shipment_id=shipment.id,
                    event_time=event_time,
                    status=status,
                    detail=detail,
                    location=location,
                )
            )

        db.commit()

    print(
        "[OK] Demo logistics shipment injected.\n"
        f"     Order ID         : {DEMO_ORDER_ID}\n"
        f"     Tracking Number  : {DEMO_TRACKING_NUMBER}\n"
        f"     ETA              : 72h overdue\n"
        f"     Last Location    : Shenzhen Sorting Hub - Typhoon Mawar zone\n"
        "\n"
        f"In the UI, enter order ID  {DEMO_ORDER_ID}  to trigger the demo."
    )


if __name__ == "__main__":
    seed()
