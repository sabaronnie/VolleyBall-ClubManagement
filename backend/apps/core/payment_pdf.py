"""PDF builders for fee statements, receipts, and team standings (ReportLab)."""

from __future__ import annotations

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


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


def build_team_standings_pdf_bytes(
    *,
    team_name: str,
    club_name: str,
    record_label: str,
    matches_played: int,
    wins: int,
    losses: int,
    points_for: int,
    points_against: int,
    point_differential: int,
    note: str,
    generated_at_label: str,
    matches: list[dict],
) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=0.55 * inch,
        rightMargin=0.55 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
    )
    styles = getSampleStyleSheet()
    page_width = letter[0] - doc.leftMargin - doc.rightMargin
    card_padding = 14
    card_inner_width = page_width - (card_padding * 2)

    title_style = ParagraphStyle(
        "StandingsTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=26,
        textColor=colors.white,
        spaceAfter=6,
    )
    subtitle_style = ParagraphStyle(
        "StandingsSubtitle",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#D7E7FF"),
    )
    section_style = ParagraphStyle(
        "StandingsSection",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#12315C"),
        spaceAfter=8,
    )
    match_title_style = ParagraphStyle(
        "MatchTitle",
        parent=styles["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#10213F"),
        spaceAfter=3,
    )
    score_style = ParagraphStyle(
        "MatchScore",
        parent=styles["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=10.8,
        leading=13,
        textColor=colors.HexColor("#10213F"),
        alignment=2,
    )
    body_style = ParagraphStyle(
        "StandingsBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#425466"),
    )
    metric_label_style = ParagraphStyle(
        "MetricLabel",
        parent=body_style,
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#66778A"),
        alignment=1,
    )
    metric_value_style = ParagraphStyle(
        "MetricValue",
        parent=body_style,
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=19,
        textColor=colors.HexColor("#0F2748"),
        alignment=1,
    )
    metric_note_style = ParagraphStyle(
        "MetricNote",
        parent=body_style,
        fontSize=8.3,
        leading=10,
        textColor=colors.HexColor("#66778A"),
        alignment=1,
    )
    badge_style = ParagraphStyle(
        "Badge",
        parent=body_style,
        fontName="Helvetica-Bold",
        fontSize=8.2,
        leading=10,
        textColor=colors.white,
        alignment=1,
    )
    small_stat_label_style = ParagraphStyle(
        "SmallStatLabel",
        parent=body_style,
        fontName="Helvetica-Bold",
        fontSize=7.7,
        leading=9.5,
        textColor=colors.HexColor("#6D7B8B"),
        alignment=1,
    )
    small_stat_value_style = ParagraphStyle(
        "SmallStatValue",
        parent=body_style,
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=14,
        textColor=colors.HexColor("#10213F"),
        alignment=1,
    )

    def paragraph(text: str, style: ParagraphStyle) -> Paragraph:
        return Paragraph(escape(text), style)

    def signed(value: int) -> str:
        return f"+{value}" if value > 0 else str(value)

    def metric_card(label: str, value: str, note_text: str) -> Table:
        card = Table(
            [[paragraph(label, metric_label_style)], [paragraph(value, metric_value_style)], [paragraph(note_text, metric_note_style)]],
            colWidths=[page_width / 3 - 8],
        )
        card.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F5F9FF")),
                    ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#D8E6F5")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ]
            )
        )
        return card

    def label_value(label: str, value: str) -> Paragraph:
        safe_label = escape(label)
        safe_value = escape(value or "—")
        return Paragraph(f"<b>{safe_label}</b><br/>{safe_value}", body_style)

    def stat_pill(label: str, value: str, width: float) -> Table:
        pill = Table(
            [[paragraph(label, small_stat_label_style)], [paragraph(value, small_stat_value_style)]],
            colWidths=[width],
        )
        pill.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                    ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#E1E8F0")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        return pill

    story = []

    header = Table(
        [
            [paragraph("Team Standings Report", title_style)],
            [paragraph(f"{team_name} | {club_name}", subtitle_style)],
            [paragraph(f"Generated {generated_at_label}", subtitle_style)],
        ],
        colWidths=[page_width],
    )
    header.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#12315C")),
                ("BOX", (0, 0), (-1, -1), 0, colors.white),
                ("LEFTPADDING", (0, 0), (-1, -1), 18),
                ("RIGHTPADDING", (0, 0), (-1, -1), 18),
                ("TOPPADDING", (0, 0), (-1, -1), 18),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 16),
            ]
        )
    )
    story.append(header)
    story.append(Spacer(1, 14))
    story.append(paragraph("Overall Snapshot", section_style))

    summary_cards = Table(
        [
            [
                metric_card("Record", record_label, "wins-losses"),
                metric_card("Matches Played", str(matches_played), "completed matches"),
                metric_card("Point Differential", signed(point_differential), "overall spread"),
            ],
            [
                metric_card("Wins", str(wins), "match victories"),
                metric_card("Losses", str(losses), "match defeats"),
                metric_card("Scoring", f"{points_for} For / {points_against} Against", "team totals"),
            ],
        ],
        colWidths=[page_width / 3, page_width / 3, page_width / 3],
        hAlign="LEFT",
    )
    summary_cards.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(summary_cards)
    story.append(Spacer(1, 10))
    story.append(paragraph(note or "Completed matches only.", body_style))
    story.append(Spacer(1, 16))

    if not matches:
        story.append(paragraph("Completed Match Breakdown", section_style))
        empty_state = Table([[paragraph("No completed matches have been recorded for this team yet.", body_style)]], colWidths=[page_width])
        empty_state.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                    ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#E1E8F0")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 14),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                    ("TOPPADDING", (0, 0), (-1, -1), 14),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
                ]
            )
        )
        story.append(empty_state)
    else:
        badge_colors = {
            "win": colors.HexColor("#1F8F55"),
            "loss": colors.HexColor("#C2410C"),
            "draw": colors.HexColor("#64748B"),
        }
        match_cards = []
        for index, match in enumerate(matches, start=1):
            result_key = match.get("result") or "draw"
            badge_width = 126
            badge = Table(
                [[paragraph((match.get("result_label") or "Completed").upper(), badge_style)]],
                colWidths=[badge_width],
            )
            badge.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), badge_colors.get(result_key, colors.HexColor("#64748B"))),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                        ("TOPPADDING", (0, 0), (-1, -1), 5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ]
                )
            )
            badge_row = Table(
                [["", badge]],
                colWidths=[card_inner_width - badge_width, badge_width],
            )
            badge_row.setStyle(
                TableStyle(
                    [
                        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                        ("TOPPADDING", (0, 0), (-1, -1), 0),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ]
                )
            )
            score_width = 190
            header_table = Table(
                [
                    [
                        paragraph(
                            f"Match {index}: {match.get('scheduled_date_label', 'Date TBD')}",
                            match_title_style,
                        ),
                        paragraph(match.get("final_score_label") or "Score unavailable", score_style),
                    ],
                    [
                        paragraph(
                            f"{match.get('team_name', team_name)} vs {match.get('opponent', 'Opponent')}",
                            body_style,
                        ),
                        "",
                    ],
                ],
                colWidths=[card_inner_width - score_width, score_width],
            )
            header_table.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                        ("TOPPADDING", (0, 0), (-1, -1), 0),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )
            details_table = Table(
                [
                    [
                        label_value("Match Type", match.get("match_type_label") or "—"),
                        label_value("Venue", match.get("location") or "TBD"),
                    ],
                    [
                        label_value(
                            "Time",
                            match.get("time_window_label") or match.get("scheduled_date_label") or "—",
                        ),
                        label_value("Duration", match.get("duration_label") or "—"),
                    ],
                ],
                colWidths=[card_inner_width / 2, card_inner_width / 2],
            )
            details_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#E1E8F0")),
                        ("INNERGRID", (0, 0), (-1, -1), 1, colors.HexColor("#E1E8F0")),
                        ("LEFTPADDING", (0, 0), (-1, -1), 10),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                        ("TOPPADDING", (0, 0), (-1, -1), 8),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ]
                )
            )
            team_stats = match.get("team_stats") or {}
            stat_col_width = card_inner_width / 3
            stat_grid = Table(
                [
                    [
                        stat_pill("Points", str(team_stats.get("points_scored", 0)), stat_col_width - 8),
                        stat_pill("Aces", str(team_stats.get("aces", 0)), stat_col_width - 8),
                        stat_pill("Blocks", str(team_stats.get("blocks", 0)), stat_col_width - 8),
                    ],
                    [
                        stat_pill("Assists", str(team_stats.get("assists", 0)), stat_col_width - 8),
                        stat_pill("Digs", str(team_stats.get("digs", 0)), stat_col_width - 8),
                        stat_pill("Errors", str(team_stats.get("errors", 0)), stat_col_width - 8),
                    ],
                    [
                        stat_pill("Points For", str(match.get("points_for", 0)), stat_col_width - 8),
                        stat_pill("Points Against", str(match.get("points_against", 0)), stat_col_width - 8),
                        stat_pill("Point Diff", signed(int(match.get("point_differential", 0))), stat_col_width - 8),
                    ],
                ],
                colWidths=[stat_col_width, stat_col_width, stat_col_width],
            )
            stat_grid.setStyle(
                TableStyle(
                    [
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                        ("TOPPADDING", (0, 0), (-1, -1), 0),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ]
                )
            )
            card = Table([[badge_row], [header_table], [details_table], [stat_grid]], colWidths=[page_width])
            card.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FBFDFF")),
                        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#D8E6F5")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), card_padding),
                        ("RIGHTPADDING", (0, 0), (-1, -1), card_padding),
                        ("TOPPADDING", (0, 0), (-1, -1), card_padding),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), card_padding),
                        ("TOPPADDING", (0, 0), (-1, 0), 12),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
                        ("TOPPADDING", (0, 1), (-1, 1), 0),
                        ("BOTTOMPADDING", (0, 1), (-1, 1), 8),
                        ("TOPPADDING", (0, 2), (-1, 2), 0),
                        ("BOTTOMPADDING", (0, 2), (-1, 2), 10),
                        ("TOPPADDING", (0, 3), (-1, 3), 0),
                    ]
                )
            )
            match_cards.append(card)

        story.append(
            KeepTogether(
                [
                    paragraph("Completed Match Breakdown", section_style),
                    Spacer(1, 8),
                    match_cards[0],
                ]
            )
        )
        for card in match_cards[1:]:
            story.append(Spacer(1, 12))
            story.append(KeepTogether([card]))

    doc.build(story)
    return buf.getvalue()
