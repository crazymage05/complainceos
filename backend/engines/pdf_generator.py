"""
PDF generation for filing drafts.

Renders the populated_fields + advisor_notes from a generated draft into
a clean, printable PDF that a small-business owner can take to a CA or
upload to a government portal.
"""

from datetime import datetime
from io import BytesIO
from typing import Any, Dict

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)


# Brand palette — match the dashboard
GREEN = colors.HexColor("#22c55e")
GRAY_900 = colors.HexColor("#111827")
GRAY_600 = colors.HexColor("#4b5563")
GRAY_300 = colors.HexColor("#d1d5db")
GRAY_100 = colors.HexColor("#f3f4f6")
RED_500 = colors.HexColor("#ef4444")
AMBER_500 = colors.HexColor("#f59e0b")


def _styles():
    base = getSampleStyleSheet()
    out = {
        "title": ParagraphStyle(
            "Title", parent=base["Title"], fontSize=22, leading=26,
            textColor=GRAY_900, alignment=0, spaceAfter=4,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle", parent=base["Normal"], fontSize=10, leading=14,
            textColor=GRAY_600, spaceAfter=12,
        ),
        "h2": ParagraphStyle(
            "H2", parent=base["Heading2"], fontSize=12, leading=16,
            textColor=GRAY_900, spaceBefore=14, spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "Body", parent=base["BodyText"], fontSize=9.5, leading=13,
            textColor=GRAY_900, spaceAfter=4,
        ),
        "caption": ParagraphStyle(
            "Caption", parent=base["Normal"], fontSize=8, leading=11,
            textColor=GRAY_600,
        ),
        "footer": ParagraphStyle(
            "Footer", parent=base["Normal"], fontSize=7.5, leading=10,
            textColor=GRAY_600, alignment=1,
        ),
    }
    return out


def _format_value(v: Any) -> str:
    if v is None or v == "":
        return "—"
    if isinstance(v, (int, float)):
        if isinstance(v, float) and v.is_integer():
            v = int(v)
        try:
            return f"{v:,}"
        except Exception:
            return str(v)
    return str(v)


def _humanise_field(name: str) -> str:
    return name.replace("_", " ").title()


def generate_draft_pdf(draft: Dict[str, Any], business: Dict[str, Any]) -> bytes:
    """Render a draft dict into a PDF and return the bytes."""
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=f"ComplianceOS — {draft.get('template_name', 'Draft')}",
        author="ComplianceOS",
    )
    styles = _styles()
    story = []

    # ── Header band ───────────────────────────────────────────────────────────
    header_data = [[
        Paragraph(
            f"<b>ComplianceOS</b><br/>"
            f"<font size=8 color='#4b5563'>AI Compliance Agent</font>",
            styles["body"],
        ),
        Paragraph(
            f"<para alignment='right'><font size=7 color='#4b5563'>Generated</font><br/>"
            f"<font size=9>{datetime.utcnow().strftime('%d %b %Y')}</font></para>",
            styles["body"],
        ),
    ]]
    header_tbl = Table(header_data, colWidths=[120 * mm, 50 * mm])
    header_tbl.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), 1.5, GREEN),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(header_tbl)
    story.append(Spacer(1, 10))

    # ── Title ────────────────────────────────────────────────────────────────
    story.append(Paragraph(draft.get("template_name", "Filing Draft"), styles["title"]))
    sub = f"For <b>{business.get('name', 'your business')}</b>"
    if draft.get("authority_portal"):
        sub += f" — Submit at: <font color='#0369a1'>{draft.get('authority_portal')}</font>"
    story.append(Paragraph(sub, styles["subtitle"]))

    # ── Pre-filled fields ────────────────────────────────────────────────────
    story.append(Paragraph("Pre-Filled Fields", styles["h2"]))
    fields = draft.get("populated_fields", {}) or {}
    if fields:
        rows = [["Field", "Value"]]
        for k, v in fields.items():
            rows.append([_humanise_field(k), _format_value(v)])
        tbl = Table(rows, colWidths=[55 * mm, 115 * mm], repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), GRAY_100),
            ("TEXTCOLOR", (0, 0), (-1, 0), GRAY_900),
            ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9),
            ("FONT", (0, 1), (-1, -1), "Helvetica", 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GRAY_100]),
            ("GRID", (0, 0), (-1, -1), 0.4, GRAY_300),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(tbl)
    else:
        story.append(Paragraph("<i>No fields pre-populated for this filing.</i>", styles["body"]))

    # ── Advisor notes ────────────────────────────────────────────────────────
    notes = draft.get("advisor_notes") or {}
    if notes:
        risk = (notes.get("risk_level") or "medium").lower()
        risk_color = {
            "high": RED_500, "medium": AMBER_500, "low": GREEN,
        }.get(risk, AMBER_500)
        story.append(Paragraph("AI Compliance Advisor Notes", styles["h2"]))

        risk_para = Paragraph(
            f"<font color='{risk_color.hexval()}'><b>RISK: {risk.upper()}</b></font> — "
            f"{notes.get('risk_reason', '')}",
            styles["body"],
        )
        story.append(risk_para)
        story.append(Spacer(1, 6))

        sections = [
            ("Documents Required", notes.get("documents_required", [])),
            ("Common Mistakes to Avoid", notes.get("common_mistakes", [])),
            ("Filing Checklist", notes.get("filing_checklist", [])),
        ]
        bullet_style = ParagraphStyle(
            "Bullet", parent=styles["body"],
            leftIndent=12, bulletIndent=2, spaceAfter=2,
        )
        for heading, items in sections:
            if not items:
                continue
            story.append(Paragraph(f"<b>{heading}</b>", styles["body"]))
            for it in items:
                story.append(Paragraph(str(it), bullet_style, bulletText="•"))
            story.append(Spacer(1, 4))

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 16))
    story.append(Paragraph(
        "This draft is auto-generated by ComplianceOS and is intended as a "
        "starting point. Review every field with your CA or compliance officer "
        "before filing with the government.",
        styles["caption"],
    ))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        f"ComplianceOS · Multi-agent AI compliance officer · {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        styles["footer"],
    ))

    doc.build(story)
    return buf.getvalue()


def safe_filename(template_name: str, business_name: str) -> str:
    """Build a filesystem-safe filename for a draft PDF."""
    import re
    name = f"{business_name}_{template_name}".replace(" ", "_")
    name = re.sub(r"[^A-Za-z0-9_\-]", "", name)
    return f"{name[:80]}.pdf"
