"""
Downloadable PDF report: a summary table of every candidate (AI score +
human decision) followed by one detail page per candidate with the full
XAI breakdown. This is the auditable paper trail HR downloads.
"""
import io
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak,
)

BRAND = colors.HexColor("#1B2A41")   # deep ink navy
ACCENT = colors.HexColor("#C98A3E")  # warm amber accent
GOOD = colors.HexColor("#2E7D5B")
BAD = colors.HexColor("#B3452C")


def _status_color(status: str):
    return {
        "approved": GOOD, "rejected": BAD, "edited": ACCENT, "pending": colors.grey,
    }.get(status, colors.grey)


def build_report(session: dict, candidates: list) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        topMargin=0.6 * inch, bottomMargin=0.6 * inch,
        leftMargin=0.6 * inch, rightMargin=0.6 * inch,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleStyle", parent=styles["Title"], textColor=BRAND, fontSize=20,
    )
    h2_style = ParagraphStyle(
        "H2Style", parent=styles["Heading2"], textColor=BRAND, spaceBefore=10,
    )
    body_style = ParagraphStyle("BodyStyle", parent=styles["BodyText"], leading=14)
    small_style = ParagraphStyle("SmallStyle", parent=styles["BodyText"], fontSize=8, textColor=colors.grey)

    story = []
    story.append(Paragraph("SCREEN — AI Resume Screening Report", title_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        f"Target role: <b>{session['target_category']}</b> &nbsp;|&nbsp; "
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", small_style,
    ))
    story.append(Spacer(1, 14))

    # Summary table
    table_data = [["#", "Candidate", "AI Score", "AI Suggestion", "Human Decision"]]
    for i, c in enumerate(candidates, start=1):
        pct = f"{c['match_probability'] * 100:.0f}%"
        suggestion = "Shortlist" if c["match_probability"] >= 0.6 else (
            "Review" if c["match_probability"] >= 0.35 else "Not a fit"
        )
        table_data.append([
            str(i), c["candidate_name"], pct, suggestion, c["hitl_status"].capitalize(),
        ])

    tbl = Table(table_data, colWidths=[0.3 * inch, 2.1 * inch, 0.9 * inch, 1.3 * inch, 1.4 * inch])
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), BRAND),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F1EA")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D8D2C4")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]
    for i, c in enumerate(candidates, start=1):
        style_cmds.append(("TEXTCOLOR", (4, i), (4, i), _status_color(c["hitl_status"])))
    tbl.setStyle(TableStyle(style_cmds))
    story.append(tbl)
    story.append(PageBreak())

    # Detail pages
    for c in candidates:
        story.append(Paragraph(c["candidate_name"], title_style))
        story.append(Paragraph(
            f"Target role: {c['target_category']} &nbsp;|&nbsp; "
            f"Match score: <b>{c['match_probability'] * 100:.0f}%</b> &nbsp;|&nbsp; "
            f"Human decision: <b>{c['hitl_status'].capitalize()}</b>", body_style,
        ))
        story.append(Spacer(1, 8))

        story.append(Paragraph("AI Explanation", h2_style))
        story.append(Paragraph(c.get("ai_explanation", ""), body_style))
        story.append(Spacer(1, 8))

        story.append(Paragraph("Why this score (Explainable AI)", h2_style))
        xai_data = [["Signal", "Value", "Contribution", "Impact"]]
        for row in c.get("xai_breakdown", []):
            xai_data.append([
                row["label"], str(row["value"]), str(row["contribution"]),
                f"{row['impact_pct']}%",
            ])
        xai_tbl = Table(xai_data, colWidths=[2.4 * inch, 1.2 * inch, 1.4 * inch, 1.0 * inch])
        xai_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E9E2D0")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D8D2C4")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(xai_tbl)
        story.append(Spacer(1, 8))

        matched = ", ".join(c.get("matched_skills", [])) or "None detected"
        missing = ", ".join(c.get("missing_skills", [])) or "None"
        story.append(Paragraph("Skills", h2_style))
        story.append(Paragraph(f"<b>Matched:</b> {matched}", body_style))
        story.append(Paragraph(f"<b>Missing:</b> {missing}", body_style))

        if c.get("hitl_note"):
            story.append(Spacer(1, 8))
            story.append(Paragraph("Recruiter Note", h2_style))
            story.append(Paragraph(c["hitl_note"], body_style))

        story.append(PageBreak())

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
