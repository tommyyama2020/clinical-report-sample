"""
generate_report.py
Cancer Genomic Clinical Report Generator
Usage: python generate_report.py report_data.json [--view clinician|patient] [--out report.pdf]
"""

import json
import sys
import argparse
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.lib import colors
from reportlab.lib.colors import HexColor

# ── Palette ──────────────────────────────────────────────────────────────────
C_TEXT       = HexColor("#1A1816")
C_TEXT2      = HexColor("#5A5650")
C_TEXT3      = HexColor("#9A9590")
C_BG         = HexColor("#F7F5F0")
C_SURFACE    = HexColor("#FFFFFF")
C_SURFACE2   = HexColor("#F0EDE6")
C_BORDER     = HexColor("#DEDAD4")
C_ACCENT     = HexColor("#1A3A2A")
C_ACCENT_MID = HexColor("#2D6B4A")
C_ACCENT_LT  = HexColor("#E6EFE9")
C_DANGER     = HexColor("#A32D2D")
C_DANGER_LT  = HexColor("#FCEBEB")
C_WARN       = HexColor("#854F0B")
C_WARN_LT    = HexColor("#FAEEDA")
C_INFO       = HexColor("#185FA5")
C_INFO_LT    = HexColor("#E6F1FB")
C_SUCCESS    = HexColor("#3B6D11")
C_SUCCESS_LT = HexColor("#EAF3DE")
C_GRAY       = HexColor("#888780")
C_GRAY_LT    = HexColor("#F1EFE8")
C_VUS_TEXT   = HexColor("#5F5E5A")

EV_COLORS = {
    "1":   (C_SUCCESS_LT, C_SUCCESS),
    "2A":  (C_INFO_LT,    C_INFO),
    "2B":  (C_INFO_LT,    C_INFO),
    "3":   (C_WARN_LT,    C_WARN),
    "R":   (C_DANGER_LT,  C_DANGER),
}

CLASS_COLORS = {
    "Pathogenic":        (C_DANGER_LT,  C_DANGER),
    "Likely pathogenic": (C_WARN_LT,    C_WARN),
    "VUS":               (C_GRAY_LT,    C_VUS_TEXT),
    "Benign":            (C_SUCCESS_LT, C_SUCCESS),
}

SIG_COLORS = {
    "SBS4":  C_WARN,
    "SBS2":  C_INFO,
    "SBS1":  C_GRAY,
    "SBS13": C_INFO,
}

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm
CONTENT_W = PAGE_W - 2 * MARGIN


# ── Style helpers ─────────────────────────────────────────────────────────────
def s(name, **kw):
    defaults = dict(fontName="Helvetica", fontSize=9, leading=13,
                    textColor=C_TEXT, spaceAfter=0, spaceBefore=0)
    defaults.update(kw)
    return ParagraphStyle(name, **defaults)

S_TITLE    = s("title",   fontName="Helvetica-Bold", fontSize=22, leading=26, spaceAfter=2)
S_SUBTITLE = s("sub",     fontSize=9, textColor=C_TEXT2)
S_SECTION  = s("sec",     fontName="Helvetica-Bold", fontSize=13, leading=17, spaceBefore=14, spaceAfter=6, textColor=C_ACCENT)
S_LABEL    = s("lbl",     fontSize=7.5, textColor=C_TEXT3, leading=10)
S_VALUE    = s("val",     fontName="Helvetica-Bold", fontSize=9, leading=12)
S_BODY     = s("body",    fontSize=9, leading=13, textColor=C_TEXT2)
S_SMALL    = s("sm",      fontSize=7.5, leading=10, textColor=C_TEXT3)
S_GENE     = s("gene",    fontName="Helvetica-Bold", fontSize=10, textColor=colors.white, alignment=TA_CENTER)
S_VAR      = s("var",     fontName="Courier-Bold", fontSize=9.5)
S_MONO     = s("mono",    fontName="Courier", fontSize=8.5, textColor=C_TEXT2)
S_PILL_TXT = s("pill",    fontSize=7.5, fontName="Helvetica-Bold", alignment=TA_CENTER)
S_PLAIN    = s("plain",   fontSize=9, leading=13, textColor=C_ACCENT, leftIndent=8)
S_WARN_TXT = s("warnbody",fontSize=8, textColor=C_DANGER, leading=11)
S_DISC     = s("disc",    fontSize=7.5, leading=11, textColor=C_TEXT3)
S_CENTER   = s("ctr",     alignment=TA_CENTER, fontSize=9, textColor=C_TEXT2)
S_RIGHT    = s("rt",      alignment=TA_RIGHT, fontSize=8, textColor=C_TEXT3)


def hr(color=C_BORDER, thickness=0.5, spaceB=4, spaceA=4):
    return HRFlowable(width="100%", thickness=thickness, color=color,
                      spaceAfter=spaceA, spaceBefore=spaceB)


def pill(text, bg, fg):
    """Inline colored pill as a 1-cell table."""
    st = ParagraphStyle("pt", fontName="Helvetica-Bold", fontSize=7.5,
                        textColor=fg, alignment=TA_CENTER, leading=9)
    t = Table([[Paragraph(text, st)]], colWidths=[None])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("ROUNDEDCORNERS", [4]),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
    ]))
    return t


def badge(text, bg, fg, w=38):
    st = ParagraphStyle("bt", fontName="Helvetica-Bold", fontSize=7,
                        textColor=fg, alignment=TA_CENTER, leading=9)
    t = Table([[Paragraph(text, st)]], colWidths=[w])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("ROUNDEDCORNERS", [3]),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING",   (0, 0), (-1, -1), 4),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
    ]))
    return t


def freq_bar_table(pct, width=60):
    """Mini frequency bar rendered as a 2-col table."""
    filled = max(2, int(width * pct / 100))
    empty  = width - filled
    inner = Table([["", ""]], colWidths=[filled, empty], rowHeights=[5])
    inner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), C_ACCENT_MID),
        ("BACKGROUND", (1, 0), (1, 0), C_SURFACE2),
        ("ROUNDEDCORNERS", [2]),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
    ]))
    return inner


# ── Report sections ───────────────────────────────────────────────────────────

def build_header(data):
    p, s_ = data["patient"], data["sample"]
    story = []
    story.append(Paragraph("Genomic Cancer Report", S_TITLE))
    story.append(Paragraph(
        f"Comprehensive somatic mutation analysis &nbsp;·&nbsp; {s_['panel']}", S_SUBTITLE))
    story.append(Spacer(1, 6))
    story.append(hr(C_TEXT, thickness=1.2, spaceB=0, spaceA=6))

    meta_rows = [
        [
            [Paragraph("PATIENT",           S_LABEL), Paragraph(f"{p['name']}, {p['age']}{p['sex']}", S_VALUE)],
            [Paragraph("SAMPLE ID",          S_LABEL), Paragraph(s_["sample_id"],           S_VALUE)],
            [Paragraph("TUMOR TYPE",         S_LABEL), Paragraph(s_["tumor_type"],           S_VALUE)],
        ],
        [
            [Paragraph("REPORT DATE",        S_LABEL), Paragraph(s_["report_date"],          S_VALUE)],
            [Paragraph("ORDERING PHYSICIAN", S_LABEL), Paragraph(s_["ordering_physician"],   S_VALUE)],
            [Paragraph("TUMOR PURITY",       S_LABEL), Paragraph(f"{s_['tumor_purity']}%",  S_VALUE)],
        ],
    ]

    col_w = CONTENT_W / 3
    for row in meta_rows:
        cells = [[Paragraph(item[0].text, S_LABEL), Paragraph(item[1].text, S_VALUE)] for item in row]
        # Flatten to 3-column single row
        flat_cells = []
        for lbl, val in [row[0], row[1], row[2]]:
            flat_cells.append(Table([[lbl], [val]], colWidths=[col_w - 4]))
        t = Table([flat_cells], colWidths=[col_w, col_w, col_w])
        t.setStyle(TableStyle([
            ("TOPPADDING",    (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(t)

    story.append(hr(spaceB=6, spaceA=2))
    return story


def build_summary(data):
    sm = data["summary"]
    story = [Paragraph("Summary", S_SECTION)]

    cards = [
        ("VARIANTS DETECTED", str(sm["total_variants"]),
         f"{sm['pathogenic_count']} pathogenic · {sm['vus_count']} VUS"),
        ("ACTIONABLE VARIANTS", str(sm["actionable_count"]),
         "FDA-approved therapies available"),
        ("TMB",
         f"{sm['tmb']} {sm['tmb_unit']}",
         sm["tmb_interpretation"]),
        ("MSI STATUS", sm["msi_status"], sm["msi_interpretation"]),
    ]

    cell_w = CONTENT_W / 4 - 3
    cells = []
    for label, value, sub in cards:
        inner = Table([
            [Paragraph(label, S_LABEL)],
            [Paragraph(value, ParagraphStyle("sv", fontName="Helvetica-Bold",
                                              fontSize=16, leading=20, textColor=C_TEXT))],
            [Paragraph(sub,   S_BODY)],
        ], colWidths=[cell_w - 8])
        inner.setStyle(TableStyle([
            ("TOPPADDING",    (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ]))
        box = Table([[inner]], colWidths=[cell_w])
        box.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), C_SURFACE),
            ("BOX",           (0, 0), (-1, -1), 0.5, C_BORDER),
            ("ROUNDEDCORNERS",[6]),
            ("TOPPADDING",    (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("LEFTPADDING",   (0, 0), (-1, -1), 12),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
        ]))
        cells.append(box)

    row_t = Table([cells], colWidths=[cell_w + 3] * 4, hAlign="LEFT")
    row_t.setStyle(TableStyle([
        ("LEFTPADDING",   (0, 0), (-1, -1), 2),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 2),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(row_t)
    story.append(Spacer(1, 10))
    return story


def build_variants(data, view):
    story = []
    sec_hdr_row = [
        Paragraph("Detected variants", S_SECTION),
        badge("COSMIC", HexColor("#EEEDFE"), HexColor("#3C3489")),
        badge("ClinVar", C_INFO_LT, C_INFO),
        badge("OncoKB/CIViC", C_SUCCESS_LT, C_SUCCESS, w=52),
    ]
    sec_t = Table([sec_hdr_row], colWidths=[CONTENT_W - 160, 48, 48, 58])
    sec_t.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "BOTTOM"),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
        ("LINEBELOW",     (0, 0), (-1, -1), 0.5, C_BORDER),
    ]))
    story.append(sec_t)
    story.append(Spacer(1, 4))

    for v in data["variants"]:
        story += build_variant_card(v, view)
        story.append(Spacer(1, 6))

    return story


def build_variant_card(v, view):
    blocks = []
    cls    = v["clinvar_classification"]
    cls_bg, cls_fg = CLASS_COLORS.get(cls, (C_GRAY_LT, C_VUS_TEXT))

    gene_cell = Table(
        [[Paragraph(v["gene"], S_GENE)]],
        colWidths=[40], rowHeights=[22]
    )
    gene_cell.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_ACCENT if cls != "VUS" else C_GRAY),
        ("ROUNDEDCORNERS",[5]),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 4),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
    ]))

    var_info = Table([
        [Paragraph(f"{v['hgvs_p']} ({v['hgvs_c']})",
                   ParagraphStyle("vh", fontName="Courier-Bold", fontSize=9.5, textColor=C_TEXT))],
        [Paragraph(f"{v['chromosome']}:{v['position']} · {v['exon']} · {v['variant_type']}", S_SMALL)],
    ], colWidths=[CONTENT_W - 130])
    var_info.setStyle(TableStyle([
        ("TOPPADDING",    (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
    ]))

    cls_pill = Table(
        [[Paragraph(cls, ParagraphStyle("cp", fontName="Helvetica-Bold",
                                         fontSize=8, textColor=cls_fg, alignment=TA_CENTER))]],
        colWidths=[72]
    )
    cls_pill.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), cls_bg),
        ("ROUNDEDCORNERS",[10]),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
    ]))

    header_row = Table(
        [[gene_cell, var_info, cls_pill]],
        colWidths=[48, CONTENT_W - 134, 80]
    )
    header_row.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    # ── Data grid ──
    col3 = CONTENT_W / 3

    def dc(label, value, sub=None):
        rows = [[Paragraph(label, S_LABEL)], [Paragraph(str(value), S_VALUE)]]
        if sub:
            rows.append([Paragraph(sub, S_SMALL)])
        t = Table(rows, colWidths=[col3 - 8])
        t.setStyle(TableStyle([
            ("TOPPADDING",    (0, 0), (-1, -1), 1),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ]))
        return t

    freq_pct = v["cosmic_frequency_pct"]
    freq_dc_rows = [
        [Paragraph("FREQUENCY IN TUMOR TYPE", S_LABEL)],
        [Paragraph(f"~{freq_pct}%", S_VALUE)],
        [freq_bar_table(freq_pct, width=int(col3 - 16))],
        [Paragraph(f"{v['cosmic_samples_positive']:,} / {v['cosmic_samples_total']:,} samples", S_SMALL)],
    ]
    freq_dc = Table(freq_dc_rows, colWidths=[col3 - 8])
    freq_dc.setStyle(TableStyle([
        ("TOPPADDING",    (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
    ]))

    grid_row1 = [
        dc("COSMIC ID", v["cosmic_id"],
           v["cosmic_id_legacy"] or ""),
        freq_dc,
        dc("ClinVar",
           v["clinvar_classification"],
           f"{v['clinvar_stars']}★ · {v['clinvar_submitters']} submitters"),
    ]

    grid1 = Table([grid_row1], colWidths=[col3, col3, col3])
    grid1.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    body_rows = [header_row, Spacer(1, 8), grid1]

    if view == "clinician":
        grid_row2 = [
            dc("VAF (TUMOR)", f"{v['vaf_pct']}%", f"coverage {v['coverage']:,}×"),
            dc("GENE ROLE", v["cosmic_gene_role"], f"Census Tier {v['cosmic_census_tier']}"),
            dc("CMC SCORE", f"{v['cosmic_cmc_score']:.2f}", "driver confidence"),
        ]
        grid2 = Table([grid_row2], colWidths=[col3, col3, col3])
        grid2.setStyle(TableStyle([
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
            ("TOPPADDING",    (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        body_rows.append(grid2)

    # Resistance flags
    for flag in v.get("resistance_flags", []):
        flag_t = Table(
            [[Paragraph(f"⚠  {flag}", S_WARN_TXT)]],
            colWidths=[CONTENT_W - 20]
        )
        flag_t.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), C_DANGER_LT),
            ("ROUNDEDCORNERS",[4]),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ]))
        body_rows += [Spacer(1, 4), flag_t]

    # Patient plain language
    if view == "patient" and v.get("patient_summary"):
        plain_t = Table(
            [[Paragraph(v["patient_summary"], S_PLAIN)]],
            colWidths=[CONTENT_W - 20]
        )
        plain_t.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), C_ACCENT_LT),
            ("LINEBEFORE",    (0, 0), (0, -1), 3, C_ACCENT_MID),
            ("ROUNDEDCORNERS",[3]),
            ("TOPPADDING",    (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING",   (0, 0), (-1, -1), 10),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
        ]))
        body_rows += [Spacer(1, 6), plain_t]

    # Treatments
    body_rows += [Spacer(1, 8),
                  hr(C_BORDER, spaceB=0, spaceA=4),
                  Paragraph("Treatment options", S_LABEL)]

    show_treatments = v.get("treatments", [])
    if view == "patient":
        show_treatments = [t for t in show_treatments if t["evidence_level"] in ("1", "2A")]

    for tx in show_treatments:
        ev = tx["evidence_level"]
        ev_bg, ev_fg = EV_COLORS.get(ev, (C_GRAY_LT, C_VUS_TEXT))
        ev_cell = Table(
            [[Paragraph(ev, ParagraphStyle("evp", fontName="Helvetica-Bold",
                                            fontSize=7.5, textColor=ev_fg, alignment=TA_CENTER))]],
            colWidths=[22], rowHeights=[14]
        )
        ev_cell.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), ev_bg),
            ("ROUNDEDCORNERS",[3]),
            ("TOPPADDING",    (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING",   (0, 0), (-1, -1), 3),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 3),
        ]))
        drug_info = Table([
            [Paragraph(tx["drug"],    ParagraphStyle("dn", fontName="Helvetica-Bold", fontSize=8.5, textColor=C_TEXT))],
            [Paragraph(tx["context"], ParagraphStyle("dc", fontSize=7.5, textColor=C_TEXT2, leading=10))],
        ], colWidths=[CONTENT_W - 90])
        drug_info.setStyle(TableStyle([
            ("TOPPADDING",    (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ]))
        status_p = Paragraph(tx["status"],
                             ParagraphStyle("st", fontSize=7.5, textColor=C_TEXT3, alignment=TA_RIGHT))
        tx_row = Table([[ev_cell, drug_info, status_p]],
                       colWidths=[26, CONTENT_W - 86, 56])
        tx_row.setStyle(TableStyle([
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
            ("LINEBELOW",     (0, 0), (-1, -1), 0.4, C_BORDER),
        ]))
        body_rows.append(tx_row)

    card_inner = Table(
        [[item] for item in body_rows],
        colWidths=[CONTENT_W - 24]
    )
    card_inner.setStyle(TableStyle([
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
    ]))

    card = Table([[card_inner]], colWidths=[CONTENT_W])
    card.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_SURFACE),
        ("BOX",           (0, 0), (-1, -1), 0.5, C_BORDER),
        ("ROUNDEDCORNERS",[8]),
        ("TOPPADDING",    (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("LEFTPADDING",   (0, 0), (-1, -1), 14),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 14),
    ]))

    return [KeepTogether(card)]


def build_signatures(data, view):
    if view == "patient":
        return []
    story = [Paragraph("Mutational signatures", S_SECTION)]

    sigs = data.get("mutational_signatures", [])
    col_w = CONTENT_W / 2 - 4

    rows_data = []
    for i in range(0, len(sigs), 2):
        pair = sigs[i:i+2]
        cells = []
        for sig in pair:
            color = SIG_COLORS.get(sig["signature"], C_GRAY)
            pct   = sig["contribution_pct"]
            filled = max(2, int((col_w - 20) * pct / 100))
            empty  = int(col_w - 20) - filled

            bar = Table([["", ""]], colWidths=[filled, empty], rowHeights=[6])
            bar.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (0, 0), color),
                ("BACKGROUND", (1, 0), (1, 0), C_SURFACE2),
                ("ROUNDEDCORNERS", [3]),
                ("TOPPADDING",    (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("LEFTPADDING",   (0, 0), (-1, -1), 0),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
            ]))

            inner = Table([
                [Paragraph(f"{sig['signature']} — {sig['name']}",
                           ParagraphStyle("sn", fontName="Helvetica-Bold", fontSize=8.5,
                                          textColor=C_TEXT))],
                [Paragraph(sig["aetiology"], S_SMALL)],
                [Spacer(1, 4)],
                [bar],
                [Paragraph(f"{pct}%",
                           ParagraphStyle("sp", fontName="Helvetica-Bold", fontSize=11,
                                          textColor=color))],
            ], colWidths=[col_w - 20])
            inner.setStyle(TableStyle([
                ("TOPPADDING",    (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ("LEFTPADDING",   (0, 0), (-1, -1), 0),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
            ]))

            box = Table([[inner]], colWidths=[col_w])
            box.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), C_SURFACE),
                ("BOX",           (0, 0), (-1, -1), 0.5, C_BORDER),
                ("ROUNDEDCORNERS",[8]),
                ("TOPPADDING",    (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LEFTPADDING",   (0, 0), (-1, -1), 12),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
            ]))
            cells.append(box)

        if len(cells) == 1:
            cells.append(Spacer(col_w, 1))

        row_t = Table([cells], colWidths=[col_w + 4, col_w + 4])
        row_t.setStyle(TableStyle([
            ("LEFTPADDING",   (0, 0), (-1, -1), 2),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 2),
            ("TOPPADDING",    (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        rows_data.append(row_t)

    story += rows_data

    note_txt = ("Dominant tobacco signature (SBS4) consistent with smoking history. "
                "APOBEC signatures (SBS2/13) suggest ongoing mutational processes "
                "— may influence immunotherapy response.")
    story.append(Spacer(1, 6))
    story.append(Paragraph(note_txt, S_BODY))
    return story


def build_evidence_legend(view):
    if view == "patient":
        return []
    story = [Paragraph("Evidence level guide  (OncoKB)", S_SECTION)]
    levels = [
        ("1",  "FDA-recognized biomarker in this tumor type"),
        ("2A", "Standard care biomarker in another tumor type"),
        ("3",  "Clinical evidence in this tumor type (early)"),
        ("R",  "Known resistance to therapy"),
    ]
    cells = []
    for code, desc in levels:
        bg, fg = EV_COLORS.get(code, (C_GRAY_LT, C_VUS_TEXT))
        ev_cell = Table(
            [[Paragraph(code, ParagraphStyle("elv", fontName="Helvetica-Bold",
                                              fontSize=8, textColor=fg, alignment=TA_CENTER))]],
            colWidths=[22], rowHeights=[14]
        )
        ev_cell.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), bg),
            ("ROUNDEDCORNERS",[3]),
            ("TOPPADDING",    (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING",   (0, 0), (-1, -1), 3),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 3),
        ]))
        desc_cell = Paragraph(desc, ParagraphStyle("ed", fontSize=8, textColor=C_TEXT2, leading=11))
        pair = Table([[ev_cell, desc_cell]], colWidths=[26, (CONTENT_W / 4) - 10])
        pair.setStyle(TableStyle([
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
            ("TOPPADDING",    (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        cells.append(pair)
    grid = Table([cells], colWidths=[(CONTENT_W / 4)] * 4)
    grid.setStyle(TableStyle([
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(grid)
    return story


def build_data_sources(data):
    ds = data.get("data_sources", {})
    story = [Spacer(1, 6), hr(spaceB=4, spaceA=4),
             Paragraph("Data sources", S_LABEL)]
    items = [f"<b>{k.replace('_',' ').title()}:</b> {v}" for k, v in ds.items()]
    story.append(Paragraph(" &nbsp;·&nbsp; ".join(items), S_SMALL))
    return story


def build_disclaimer():
    text = (
        "<b>Disclaimer:</b> This report is provided for informational and research purposes only. "
        "COSMIC data is used under commercial license and is not approved for clinical decision-making "
        "as a standalone resource. All treatment decisions must be made by a qualified oncologist in "
        "conjunction with full clinical context. Variant interpretations reflect current evidence as of "
        "report date and may change as new data emerge. ClinVar classifications represent community "
        "consensus and may differ from institutional interpretations. "
        "This sample report contains illustrative data only — no real patient data is included."
    )
    story = [Spacer(1, 8)]
    t = Table([[Paragraph(text, S_DISC)]], colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ("BOX",           (0, 0), (-1, -1), 0.5, C_BORDER),
        ("ROUNDEDCORNERS",[6]),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING",   (0, 0), (-1, -1), 12),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
    ]))
    story.append(t)
    return story


# ── Page template ─────────────────────────────────────────────────────────────

def make_footer(view, sample_id):
    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(C_TEXT3)
        label = f"CONFIDENTIAL — {view.upper()} VIEW  ·  Sample ID: {sample_id}  ·  Page {doc.page}"
        canvas.drawString(MARGIN, 12 * mm, label)
        canvas.drawRightString(PAGE_W - MARGIN, 12 * mm,
                               "For research use only · Not for clinical decision-making")
        canvas.restoreState()
    return footer


# ── Main ──────────────────────────────────────────────────────────────────────

def generate_report(json_path: str, view: str = "clinician", out_path: str = None):
    with open(json_path) as f:
        data = json.load(f)

    sample_id = data["sample"]["sample_id"]
    if out_path is None:
        out_path = f"cancer_report_{sample_id}_{view}.pdf"

    doc = SimpleDocTemplate(
        out_path,
        pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=16 * mm, bottomMargin=20 * mm,
        title=f"Genomic Cancer Report — {data['patient']['name']}",
        author=data["sample"]["ordering_physician"],
    )

    story = []
    story += build_header(data)
    story.append(Spacer(1, 8))
    story += build_summary(data)
    story += build_variants(data, view)
    story.append(Spacer(1, 8))
    story += build_signatures(data, view)
    story.append(Spacer(1, 8))
    story += build_evidence_legend(view)
    story += build_data_sources(data)
    story += build_disclaimer()

    footer_fn = make_footer(view, sample_id)
    doc.build(story, onFirstPage=footer_fn, onLaterPages=footer_fn)
    print(f"✓ Report written → {out_path}")
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate cancer genomic report PDF from JSON")
    parser.add_argument("json",  help="Path to report JSON file")
    parser.add_argument("--view", choices=["clinician", "patient"], default="clinician",
                        help="Report view: clinician (full) or patient (plain language). Default: clinician")
    parser.add_argument("--out",  default=None,
                        help="Output PDF path. Default: cancer_report_<id>_<view>.pdf")
    args = parser.parse_args()
    generate_report(args.json, args.view, args.out)
