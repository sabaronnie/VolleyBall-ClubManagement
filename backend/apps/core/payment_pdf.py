"""Minimal PDF statements for club fee reminders and receipts (ReportLab)."""

from __future__ import annotations

from io import BytesIO

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


def build_reminder_pdf_bytes(
    *,
    club_name: str,
    player_name: str,
    player_email: str,
    team_name: str | None,
    description: str,
    amount_due: str,
    amount_paid: str,
    remaining: str,
    currency: str,
    due_date: str,
) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    _, h = letter
    x, y = 50, h - 60
    c.setFont("Helvetica-Bold", 16)
    c.drawString(x, y, "Payment reminder")
    y -= 28
    c.setFont("Helvetica", 11)
    c.drawString(x, y, f"Club: {club_name}")
    y -= 18
    c.drawString(x, y, f"Player: {player_name}")
    y -= 16
    c.drawString(x, y, f"Email: {player_email}")
    y -= 16
    if team_name:
        c.drawString(x, y, f"Team: {team_name}")
        y -= 16
    y -= 8
    c.setFont("Helvetica-Bold", 11)
    c.drawString(x, y, "Fee details")
    y -= 20
    c.setFont("Helvetica", 10)
    for label, val in (
        ("Description", description),
        ("Amount due", f"{currency} {amount_due}"),
        ("Amount paid", f"{currency} {amount_paid}"),
        ("Remaining", f"{currency} {remaining}"),
        ("Due date", due_date),
    ):
        c.drawString(x, y, f"{label}: {val}")
        y -= 16
    y -= 16
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(
        x,
        y,
        "Please arrange payment according to your club's instructions. A PDF copy is attached to this email.",
    )
    c.showPage()
    c.save()
    return buf.getvalue()


def build_receipt_pdf_bytes(
    *,
    club_name: str,
    player_name: str,
    player_email: str,
    team_name: str | None,
    description: str,
    amount_due: str,
    amount_paid: str,
    remaining: str,
    currency: str,
    due_date: str,
    paid_at: str | None,
    ledger_lines: list[str],
) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    _, h = letter
    x, y = 50, h - 60
    c.setFont("Helvetica-Bold", 16)
    c.drawString(x, y, "Payment receipt")
    y -= 28
    c.setFont("Helvetica", 11)
    c.drawString(x, y, f"Club: {club_name}")
    y -= 18
    c.drawString(x, y, f"Player: {player_name}")
    y -= 16
    c.drawString(x, y, f"Email: {player_email}")
    y -= 16
    if team_name:
        c.drawString(x, y, f"Team: {team_name}")
        y -= 16
    y -= 8
    c.setFont("Helvetica-Bold", 11)
    c.drawString(x, y, "Summary")
    y -= 20
    c.setFont("Helvetica", 10)
    for label, val in (
        ("Description", description),
        ("Invoice total", f"{currency} {amount_due}"),
        ("Amount paid (cumulative)", f"{currency} {amount_paid}"),
        ("Balance remaining", f"{currency} {remaining}"),
        ("Due date", due_date),
    ):
        c.drawString(x, y, f"{label}: {val}")
        y -= 16
    if paid_at:
        c.drawString(x, y, f"Paid in full at: {paid_at}")
        y -= 16
    y -= 12
    c.setFont("Helvetica-Bold", 11)
    c.drawString(x, y, "Ledger (most recent first)")
    y -= 18
    c.setFont("Helvetica", 9)
    for line in ledger_lines[:30]:
        if y < 80:
            c.showPage()
            y = h - 60
            c.setFont("Helvetica", 9)
        c.drawString(x, y, line[:120])
        y -= 14
    c.showPage()
    c.save()
    return buf.getvalue()


def build_balance_summary_pdf_bytes(
    *,
    title: str,
    club_name: str,
    player_name: str,
    player_email: str,
    as_of_date: str,
    line_items: list[dict],
    total_remaining: str,
    total_currency: str,
    cleared_message: str | None = None,
) -> bytes:
    """
    Multi-line fee statement: description, due date, amounts, remaining; optional total row.
    If line_items is empty, show cleared_message instead of a table.
    Each line_item: description, team (optional), due_date, amount_due, amount_paid, remaining, currency
    """
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    _, h = letter
    x, y = 50, h - 55

    def new_page():
        nonlocal y
        c.showPage()
        y = h - 55
        c.setFont("Helvetica", 10)

    c.setFont("Helvetica-Bold", 16)
    c.drawString(x, y, title)
    y -= 26
    c.setFont("Helvetica", 11)
    c.drawString(x, y, f"Club: {club_name}")
    y -= 18
    c.drawString(x, y, f"Player / family: {player_name}")
    y -= 16
    c.drawString(x, y, f"Email: {player_email}")
    y -= 16
    c.drawString(x, y, f"As of: {as_of_date}")
    y -= 22

    if cleared_message:
        c.setFont("Helvetica", 10)
        for paragraph in cleared_message.split("\n\n"):
            for line in paragraph.split("\n"):
                if y < 72:
                    new_page()
                c.drawString(x, y, line[:100])
                y -= 14
            y -= 6
        c.setFont("Helvetica-Oblique", 9)
        if y < 72:
            new_page()
        c.drawString(
            x,
            y,
            "This PDF was generated automatically after a payment was recorded on your account.",
        )
        c.showPage()
        c.save()
        return buf.getvalue()

    c.setFont("Helvetica-Bold", 11)
    c.drawString(x, y, "Fee lines")
    y -= 18
    c.setFont("Helvetica-Bold", 9)
    headers = ("Description", "Due", "Due amt", "Paid", "Remaining")
    col_x = [x, x + 220, x + 290, x + 360, x + 430]
    for hx, label in zip(col_x, headers, strict=False):
        c.drawString(hx, y, label)
    y -= 14
    c.setFont("Helvetica", 9)
    for item in line_items:
        if y < 100:
            new_page()
            c.setFont("Helvetica-Bold", 9)
            for hx, label in zip(col_x, headers, strict=False):
                c.drawString(hx, y, label)
            y -= 14
            c.setFont("Helvetica", 9)
        desc = (item.get("description") or "")[:42]
        team = item.get("team")
        if team:
            desc = f"{desc} ({team[:18]})"
        c.drawString(col_x[0], y, desc[:48])
        c.drawString(col_x[1], y, (item.get("due_date") or "")[:12])
        cur = item.get("currency") or total_currency
        c.drawString(col_x[2], y, f"{cur} {item.get('amount_due', '')}"[:14])
        c.drawString(col_x[3], y, f"{cur} {item.get('amount_paid', '')}"[:14])
        c.drawString(col_x[4], y, f"{cur} {item.get('remaining', '')}"[:14])
        y -= 14

    y -= 10
    if y < 80:
        new_page()
    c.setFont("Helvetica-Bold", 11)
    c.drawString(x, y, f"Total remaining ({total_currency}): {total_remaining}")
    y -= 20
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(
        x,
        y,
        "Please arrange payment according to your club's instructions. A PDF copy is attached to this email.",
    )
    c.showPage()
    c.save()
    return buf.getvalue()
