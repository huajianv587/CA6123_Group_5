from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
IMAGE_DIR = ROOT / "docs" / "images"
ANIMATION_DIR = ROOT / "docs" / "animations"

NAVY = "#071723"
NAVY_2 = "#0d2533"
PANEL = "#112b3a"
PANEL_2 = "#17364a"
TEXT = "#f8fafc"
MUTED = "#b9c7d5"
LINE = "#4a6b80"
EMERALD = "#28c986"
BLUE = "#4ea5ff"
AMBER = "#f1a72c"
RED = "#ff5b66"
PURPLE = "#a78bfa"
LIGHT_BG = "#f4f7fb"
LIGHT_PANEL = "#ffffff"
LIGHT_TEXT = "#0f172a"
LIGHT_MUTED = "#5b6b80"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf"),
    ]
    for item in candidates:
        if item.exists():
            return ImageFont.truetype(str(item), size)
    return ImageFont.load_default()


def text_size(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.ImageFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=fnt)
    return box[2] - box[0], box[3] - box[1]


def wrap_text(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.ImageFont, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if text_size(draw, candidate, fnt)[0] <= width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_wrapped(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    fnt: ImageFont.ImageFont,
    fill: str,
    width: int,
    line_gap: int = 8,
) -> int:
    x, y = xy
    for line in wrap_text(draw, text, fnt, width):
        draw.text((x, y), line, font=fnt, fill=fill)
        y += text_size(draw, line, fnt)[1] + line_gap
    return y


def vertical_gradient(size: tuple[int, int], top: str, bottom: str) -> Image.Image:
    width, height = size
    img = Image.new("RGB", size, top)
    draw = ImageDraw.Draw(img)
    top_rgb = tuple(int(top[i : i + 2], 16) for i in (1, 3, 5))
    bottom_rgb = tuple(int(bottom[i : i + 2], 16) for i in (1, 3, 5))
    for y in range(height):
        ratio = y / max(height - 1, 1)
        rgb = tuple(round(top_rgb[i] * (1 - ratio) + bottom_rgb[i] * ratio) for i in range(3))
        draw.line([(0, y), (width, y)], fill=rgb)
    return img


def glow(draw: ImageDraw.ImageDraw, center: tuple[int, int], radius: int, color: str) -> None:
    x, y = center
    for i in range(10, 0, -1):
        alpha_radius = radius + i * 16
        fill = color
        draw.ellipse((x - alpha_radius, y - alpha_radius, x + alpha_radius, y + alpha_radius), outline=fill, width=1)


def rounded_card(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    title: str,
    subtitle: str,
    accent: str,
    title_size: int = 34,
    body_size: int = 25,
) -> None:
    x1, y1, x2, y2 = box
    draw.rounded_rectangle(box, radius=22, fill=PANEL, outline="#426176", width=3)
    draw.rounded_rectangle((x1, y1, x1 + 12, y2), radius=8, fill=accent)
    draw.text((x1 + 34, y1 + 28), title, font=font(title_size, True), fill=TEXT)
    draw_wrapped(draw, (x1 + 34, y1 + 80), subtitle, font(body_size), MUTED, x2 - x1 - 70, line_gap=6)


def generate_figure_4() -> None:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    width, height = 2200, 1238
    img = vertical_gradient((width, height), NAVY, "#153a4d")
    draw = ImageDraw.Draw(img)

    glow(draw, (1040, 680), 360, "#194f54")
    glow(draw, (1750, 420), 260, "#12394d")

    draw.text((110, 96), "Figure 4", font=font(28, True), fill="#9cf2c4")
    draw.text((110, 145), "Data And Knowledge Map", font=font(72, True), fill=TEXT)
    draw_wrapped(
        draw,
        (110, 238),
        "Structured service decisions combine customer messages, operational records, enterprise knowledge, and governance evidence.",
        font(31),
        MUTED,
        1450,
        line_gap=8,
    )

    column_titles = [
        ("Operational Signals", 125, EMERALD),
        ("Business Records", 755, BLUE),
        ("Knowledge And Governance", 1385, AMBER),
    ]
    for label, x, color in column_titles:
        draw.text((x, 338), label, font=font(31, True), fill=color)
        draw.line((x, 385, x + 500, 385), fill=color, width=4)

    card_w = 520
    card_h = 142
    rows = [425, 602, 779]
    columns = [125, 755, 1385]
    cards = [
        (columns[0], rows[0], "Customer Messages", "Sessions, multi-turn requests", EMERALD),
        (columns[0], rows[1], "Complaints", "Severity, risk, staff review", RED),
        (columns[0], rows[2], "Evaluation Records", "Safety and quality outcomes", PURPLE),
        (columns[1], rows[0], "Orders", "Payment, items, amount, status", BLUE),
        (columns[1], rows[1], "Shipments", "Tracking number and delivery trail", BLUE),
        (columns[1], rows[2], "Refund Cases", "Reason, amount, status, priority", AMBER),
        (columns[2], rows[0], "Policy Rules", "Refund and service rules", AMBER),
        (columns[2], rows[1], "Historical Cases", "Exception precedents", EMERALD),
        (columns[2], rows[2], "Customer Tags", "VIP, category, risk hints", PURPLE),
    ]

    hub = (420, 1012, 1780, 1168)
    hub_anchor_y = hub[1] - 50
    for x, y, _, _, accent in cards:
        start = (x + card_w // 2, y + card_h + 4)
        end = (min(max(start[0], hub[0] + 80), hub[2] - 80), hub[1])
        draw.line((start[0], start[1], start[0], hub_anchor_y), fill=accent, width=3)
        draw.line((start[0], hub_anchor_y, end[0], hub_anchor_y), fill=accent, width=3)
        draw.line((end[0], hub_anchor_y, end[0], end[1]), fill=accent, width=3)

    for x, y, title, subtitle, accent in cards:
        rounded_card(draw, (x, y, x + card_w, y + card_h), title, subtitle, accent, title_size=31, body_size=24)

    draw.rounded_rectangle(hub, radius=28, fill="#0f3140", outline="#7ae7b0", width=4)
    draw.text((hub[0] + 46, hub[1] + 30), "Service Decision Context", font=font(41, True), fill=TEXT)
    draw_wrapped(
        draw,
        (hub[0] + 46, hub[1] + 88),
        "Routes requests, recommends responses, creates cases, escalates risk, and reports outcomes.",
        font(27),
        MUTED,
        hub[2] - hub[0] - 92,
        line_gap=7,
    )

    img.save(IMAGE_DIR / "figure-4-data-and-knowledge-map.png", quality=95)


def draw_sidebar(draw: ImageDraw.ImageDraw, active: str) -> None:
    draw.rectangle((0, 0, 210, 560), fill="#0b1721")
    draw.rounded_rectangle((20, 22, 58, 60), radius=10, fill="#0c8f62")
    draw.text((72, 22), "ServiceOps AI", font=font(18, True), fill=TEXT)
    draw.text((72, 45), "Agent workspace", font=font(11), fill="#a9c7d8")
    items = ["Operations", "Agent Console", "Customer Orders", "Refund Cases", "Knowledge Base", "Quality Monitor", "Escalation Queue"]
    y = 92
    for item in items:
        selected = item == active
        if selected:
            draw.rounded_rectangle((16, y - 8, 196, y + 28), radius=8, fill="#1b2c3a")
        draw.text((36, y), item, font=font(13, selected), fill=TEXT if selected else "#dce8f2")
        y += 46
    draw.ellipse((22, 498, 50, 526), fill="#e6eef7")
    draw.text((62, 496), "Demo Agent", font=font(13, True), fill=TEXT)
    draw.text((62, 516), "Support Operator", font=font(10), fill="#9fb5c5")


def draw_ui_frame(title: str, active: str, mode: str) -> Image.Image:
    img = Image.new("RGB", (1000, 560), LIGHT_BG)
    draw = ImageDraw.Draw(img)
    draw_sidebar(draw, active)
    draw.text((245, 34), title, font=font(28, True), fill=LIGHT_TEXT)
    draw.text((246, 72), "Enterprise customer service operations workspace", font=font(14), fill=LIGHT_MUTED)
    draw.rounded_rectangle((890, 34, 970, 64), radius=8, fill="#047857")
    draw.text((910, 40), "Refresh", font=font(12, True), fill="#ffffff")

    if mode == "landing":
        img = vertical_gradient((1000, 560), "#071723", "#153a4d")
        draw = ImageDraw.Draw(img)
        draw.text((50, 45), "ServiceOps AI", font=font(20, True), fill=TEXT)
        draw.text((50, 72), "Customer service operations platform", font=font(12), fill="#b7c9d7")
        draw.text((50, 150), "Unify requests, orders,\nrefunds, and complaints", font=font(52, True), fill=TEXT, spacing=6)
        draw_wrapped(draw, (54, 315), "Enterprise-side workspace for support teams to process customer messages with order context, refund rules, escalation queues, and service quality monitoring.", font(18), "#e2edf5", 640, 8)
        draw.rounded_rectangle((55, 430, 240, 470), radius=10, fill="#07865e")
        draw.text((78, 440), "Open agent workspace", font=font(14, True), fill="#ffffff")
        for i, (label, value) in enumerate([("Orders", "100"), ("Messages", "12"), ("Refunds", "17"), ("Escalations", "9")]):
            x = 690 + (i % 2) * 140
            y = 210 + (i // 2) * 120
            draw.rounded_rectangle((x, y, x + 120, y + 88), radius=10, fill="#102737", outline="#426176")
            draw.text((x + 16, y + 14), label, font=font(12, True), fill=MUTED)
            draw.text((x + 16, y + 42), value, font=font(34, True), fill=TEXT)
        return img

    if mode == "dashboard":
        kpis = [("Total orders", "100"), ("Customer messages", "12"), ("Pending refunds", "3"), ("Escalation tickets", "9")]
        for i, (label, value) in enumerate(kpis):
            x = 245 + i * 180
            draw.rounded_rectangle((x, 110, x + 160, 190), radius=8, fill=LIGHT_PANEL, outline="#d5dee8")
            draw.text((x + 16, 126), label, font=font(11, True), fill=LIGHT_MUTED)
            draw.text((x + 16, 150), value, font=font(25, True), fill=LIGHT_TEXT)
        panels = [("Recent Order Context", ["202404250028 Preparing", "202404250067 Delivered", "202404250038 In transit"]), ("Latest Customer Requests", ["Refund request", "Delivery follow-up", "Complaint review"]), ("High-Risk Escalations", ["High priority", "Staff review required", "Legal-risk keywords"])]
        for i, (heading, rows) in enumerate(panels):
            x = 245 + i * 240
            draw.rounded_rectangle((x, 220, x + 218, 505), radius=8, fill=LIGHT_PANEL, outline="#d5dee8")
            draw.text((x + 14, 238), heading, font=font(13, True), fill=LIGHT_TEXT)
            y = 282
            for row in rows:
                draw.text((x + 14, y), row, font=font(13, True), fill=LIGHT_TEXT)
                draw.line((x + 14, y + 28, x + 204, y + 28), fill="#e5edf5")
                y += 54

    elif mode == "console":
        draw.rounded_rectangle((245, 115, 565, 492), radius=10, fill=LIGHT_PANEL, outline="#d5dee8")
        draw.text((265, 135), "Incoming customer message", font=font(14, True), fill=LIGHT_TEXT)
        draw.rounded_rectangle((265, 180, 520, 230), radius=14, fill="#e9f3ff")
        draw_wrapped(draw, (285, 190), "Customer says the parcel has not arrived and asks for help.", font(13), LIGHT_TEXT, 210, 4)
        draw.rounded_rectangle((310, 275, 540, 335), radius=14, fill="#dcfce7")
        draw_wrapped(draw, (330, 285), "Suggested handling: verify shipment status and provide next action.", font(13), LIGHT_TEXT, 190, 4)
        draw.rounded_rectangle((600, 115, 940, 492), radius=10, fill=LIGHT_PANEL, outline="#d5dee8")
        for i, label in enumerate(["Intent: logistics", "Order context found", "Policy context checked", "Escalation: not required"]):
            y = 150 + i * 72
            draw.rounded_rectangle((625, y, 910, y + 42), radius=8, fill="#f0fdf4", outline="#a7f3d0")
            draw.text((645, y + 11), label, font=font(13, True), fill="#065f46")

    elif mode == "orders":
        headers = ["Order ID", "Customer", "Status", "Amount", "Delivery"]
        rows = [
            ["202404250028", "Customer 4", "Preparing", "S$2998", "Pending"],
            ["202404250067", "Customer 12", "Delivered", "S$5998", "Completed"],
            ["202404250038", "Customer 7", "In transit", "S$4799", "On route"],
            ["202404250087", "Customer 15", "Completed", "S$5998", "Closed"],
        ]
        draw.rounded_rectangle((245, 120, 945, 485), radius=10, fill=LIGHT_PANEL, outline="#d5dee8")
        x_positions = [265, 405, 535, 660, 790]
        for x, header in zip(x_positions, headers):
            draw.text((x, 145), header, font=font(13, True), fill=LIGHT_MUTED)
        for r, row in enumerate(rows):
            y = 192 + r * 62
            draw.line((265, y - 16, 920, y - 16), fill="#e5edf5")
            for x, value in zip(x_positions, row):
                draw.text((x, y), value, font=font(13, True if x == 265 else False), fill=LIGHT_TEXT)

    elif mode == "refunds":
        cards = [("Quality issue", "Pending review", "S$299.00"), ("Seven-day return", "Approved", "S$89.00"), ("Wrong item", "Pending review", "S$168.00")]
        for i, (reason, status, amount) in enumerate(cards):
            y = 135 + i * 105
            draw.rounded_rectangle((250, y, 930, y + 78), radius=10, fill=LIGHT_PANEL, outline="#d5dee8")
            draw.text((275, y + 18), reason, font=font(16, True), fill=LIGHT_TEXT)
            draw.text((275, y + 45), "Refund case requires policy and order context", font=font(12), fill=LIGHT_MUTED)
            draw.text((690, y + 18), amount, font=font(16, True), fill=LIGHT_TEXT)
            draw.rounded_rectangle((805, y + 18, 910, y + 46), radius=14, fill="#fef3c7" if "Pending" in status else "#dcfce7")
            draw.text((820, y + 24), status, font=font(11, True), fill="#92400e" if "Pending" in status else "#166534")

    elif mode == "tickets":
        for i, label in enumerate(["High priority complaint", "Lost parcel dispute", "High-value refund review", "Legal-risk service wording"]):
            y = 132 + i * 78
            draw.rounded_rectangle((250, y, 930, y + 56), radius=10, fill=LIGHT_PANEL, outline="#d5dee8")
            draw.text((275, y + 17), label, font=font(15, True), fill=LIGHT_TEXT)
            draw.rounded_rectangle((760, y + 14, 905, y + 42), radius=14, fill="#fee2e2")
            draw.text((780, y + 20), "Staff review", font=font(11, True), fill="#991b1b")
    return img


def generate_operations_gif() -> None:
    ANIMATION_DIR.mkdir(parents=True, exist_ok=True)
    frames = [
        draw_ui_frame("Landing", "Operations", "landing"),
        draw_ui_frame("Operations Overview", "Operations", "dashboard"),
        draw_ui_frame("Agent Console", "Agent Console", "console"),
        draw_ui_frame("Customer Orders", "Customer Orders", "orders"),
        draw_ui_frame("Refund Cases", "Refund Cases", "refunds"),
        draw_ui_frame("Escalation Queue", "Escalation Queue", "tickets"),
    ]
    frames[0].save(
        ANIMATION_DIR / "operations-workspace-demo.gif",
        save_all=True,
        append_images=frames[1:],
        duration=1050,
        loop=0,
        optimize=True,
    )


def draw_workflow_frame(active: int) -> Image.Image:
    img = vertical_gradient((1000, 560), NAVY, "#133d4d")
    draw = ImageDraw.Draw(img)
    draw.text((52, 44), "ServiceOps Closed Loop", font=font(34, True), fill=TEXT)
    draw.text((54, 88), "From customer request to auditable operational record", font=font(16), fill=MUTED)
    steps = [
        ("Request Intake", "Customer message enters the agent workspace."),
        ("Safety Check", "PII and risky instructions are filtered first."),
        ("Intent Routing", "The request is classified into a service route."),
        ("Context Retrieval", "Orders, shipments, policies, and cases are retrieved."),
        ("Recommendation", "The operator receives handling guidance."),
        ("Persistence", "Messages, events, refunds, and tickets are stored."),
    ]
    y = 205
    start_x = 80
    gap = 150
    for i, (title, _) in enumerate(steps):
        x = start_x + i * gap
        color = EMERALD if i == active else "#2b5063"
        draw.line((x + 38, y + 38, x + gap - 16, y + 38), fill="#35596b", width=4)
        draw.ellipse((x, y, x + 76, y + 76), fill=color, outline="#93ffd0" if i == active else "#547487", width=3)
        draw.text((x + 27, y + 22), str(i + 1), font=font(22, True), fill=TEXT)
        draw_wrapped(draw, (x - 16, y + 96), title, font(13, True), TEXT, 110, 3)
    title, body = steps[active]
    draw.rounded_rectangle((150, 390, 850, 500), radius=24, fill=PANEL, outline="#79e6b0", width=3)
    draw.text((190, 418), title, font=font(25, True), fill=TEXT)
    draw_wrapped(draw, (190, 456), body, font(17), MUTED, 610, 6)
    progress_width = 700
    draw.rounded_rectangle((150, 520, 850, 534), radius=8, fill="#234655")
    draw.rounded_rectangle((150, 520, 150 + round(progress_width * ((active + 1) / len(steps))), 534), radius=8, fill=EMERALD)
    return img


def generate_workflow_gif() -> None:
    ANIMATION_DIR.mkdir(parents=True, exist_ok=True)
    frames = [draw_workflow_frame(i) for i in range(6)]
    frames[0].save(
        ANIMATION_DIR / "serviceops-closed-loop.gif",
        save_all=True,
        append_images=frames[1:],
        duration=1050,
        loop=0,
        optimize=True,
    )


def main() -> None:
    generate_figure_4()
    generate_operations_gif()
    generate_workflow_gif()
    print(f"Wrote {IMAGE_DIR / 'figure-4-data-and-knowledge-map.png'}")
    print(f"Wrote {ANIMATION_DIR / 'operations-workspace-demo.gif'}")
    print(f"Wrote {ANIMATION_DIR / 'serviceops-closed-loop.gif'}")


if __name__ == "__main__":
    main()
