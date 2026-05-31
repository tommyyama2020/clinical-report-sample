"""
generate_report.py
Cancer Genomic Clinical Report Generator
Usage:
  python generate_report.py report_data.json [--view clinician|patient] [--format pdf|html|both] [--out output]
"""

import json
import sys
import argparse
import html as html_mod
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


# ── HTML Generator ────────────────────────────────────────────────────────────

def _ev_colors_html(ev):
    m = {"1": ("#EAF3DE","#3B6D11"), "2A": ("#E6F1FB","#185FA5"),
         "2B": ("#E6F1FB","#185FA5"), "3": ("#FAEEDA","#854F0B"), "R": ("#FCEBEB","#A32D2D")}
    return m.get(ev, ("#F1EFE8","#5F5E5A"))

def _cls_colors_html(cls):
    m = {"Pathogenic": ("#FCEBEB","#A32D2D"), "Likely pathogenic": ("#FAEEDA","#854F0B"),
         "VUS": ("#F1EFE8","#5F5E5A"), "Benign": ("#EAF3DE","#3B6D11")}
    return m.get(cls, ("#F1EFE8","#5F5E5A"))

def _stars(n):
    return "★" * n + "☆" * (5 - n)

def _freq_bar(pct, color="#2D6B4A"):
    return (f'<div style="height:6px;background:#F0EDE6;border-radius:3px;margin:4px 0 2px">'
            f'<div style="width:{min(pct,100)}%;height:100%;background:{color};border-radius:3px"></div></div>')

def _pill(text, bg, fg, radius="20px"):
    return (f'<span style="display:inline-block;background:{bg};color:{fg};font-size:11px;'
            f'font-weight:600;padding:2px 9px;border-radius:{radius};white-space:nowrap">{text}</span>')

def _resistance_flag(text):
    return (f'<div style="background:#FCEBEB;border-radius:5px;padding:7px 12px;'
            f'margin:10px 0;font-size:12px;color:#A32D2D;font-weight:500">⚠ {text}</div>')

def _plain_box(text):
    return (f'<div style="background:#E6EFE9;border-left:3px solid #2D6B4A;border-radius:0 8px 8px 0;'
            f'padding:10px 14px;margin:10px 0;font-size:13px;line-height:1.6;color:#1A3A2A">'
            f'<strong>What this means for you:</strong> {html_mod.escape(text)}</div>')

def _sig_bar(pct, color):
    return (f'<div style="height:8px;background:#F0EDE6;border-radius:4px;margin:6px 0">'
            f'<div style="width:{pct}%;height:100%;background:{color};border-radius:4px"></div></div>')

def generate_html(json_path: str, view: str = "clinician", out_path: str = None) -> str:
    with open(json_path) as f:
        data = json.load(f)

    p   = data["patient"]
    s   = data["sample"]
    sm  = data["summary"]
    ds  = data.get("data_sources", {})

    sample_id = s["sample_id"]
    if out_path is None:
        out_path = f"cancer_report_{sample_id}_{view}.html"

    is_clinician = view == "clinician"

    # ── Variants HTML ──
    variants_html = ""
    for v in data["variants"]:
        cls           = v["clinvar_classification"]
        cls_bg, cls_fg = _cls_colors_html(cls)
        gene_bg       = "#1A3A2A" if cls != "VUS" else "#888780"
        freq_pct      = v["cosmic_frequency_pct"]

        # data grid
        grid_cells = f"""
        <div class="dc"><div class="dc-l">COSMIC ID</div>
          <div class="dc-v">{v['cosmic_id']}</div>
          <div class="dc-s">{v.get('cosmic_id_legacy') or ''}</div></div>
        <div class="dc"><div class="dc-l">FREQUENCY IN TUMOR TYPE</div>
          <div class="dc-v">~{freq_pct}%</div>
          {_freq_bar(freq_pct)}
          <div class="dc-s">{v['cosmic_samples_positive']:,} / {v['cosmic_samples_total']:,} samples</div></div>
        <div class="dc"><div class="dc-l">ClinVar</div>
          <div class="dc-v" style="color:{cls_fg}">{cls}</div>
          <div class="dc-s">{_stars(v['clinvar_stars'])} · {v['clinvar_submitters']} submitters</div></div>
        """
        if is_clinician:
            grid_cells += f"""
        <div class="dc"><div class="dc-l">VAF (TUMOR)</div>
          <div class="dc-v">{v['vaf_pct']}%</div>
          <div class="dc-s">coverage {v['coverage']:,}×</div></div>
        <div class="dc"><div class="dc-l">GENE ROLE</div>
          <div class="dc-v">{v['cosmic_gene_role']}</div>
          <div class="dc-s">Census Tier {v['cosmic_census_tier']}</div></div>
        <div class="dc"><div class="dc-l">CMC SCORE</div>
          <div class="dc-v">{v['cosmic_cmc_score']:.2f}</div>
          <div class="dc-s">driver confidence</div></div>
            """

        # resistance flags
        flags_html = "".join(_resistance_flag(f) for f in v.get("resistance_flags", []))

        # patient plain language
        plain_html = _plain_box(v["patient_summary"]) if not is_clinician and v.get("patient_summary") else ""

        # treatments
        treatments = v.get("treatments", [])
        if not is_clinician:
            treatments = [t for t in treatments if t["evidence_level"] in ("1", "2A")]
        tx_rows = ""
        for tx in treatments:
            ev = tx["evidence_level"]
            ev_bg, ev_fg = _ev_colors_html(ev)
            tx_rows += f"""
            <div class="tx-row">
              {_pill(ev, ev_bg, ev_fg, "4px")}
              <div style="flex:1">
                <div style="font-weight:600;font-size:13px">{html_mod.escape(tx['drug'])}</div>
                <div style="font-size:11px;color:#5A5650">{html_mod.escape(tx['context'])}</div>
              </div>
              <div style="font-size:11px;color:#9A9590;white-space:nowrap">{tx['status']}</div>
            </div>"""

        variants_html += f"""
        <div class="v-card">
          <div class="v-header">
            <span class="gene-badge" style="background:{gene_bg}">{v['gene']}</span>
            <div>
              <div style="font-family:monospace;font-weight:700;font-size:14px">{v['hgvs_p']} ({v['hgvs_c']})</div>
              <div style="font-size:11px;color:#9A9590">{v['chromosome']}:{v['position']} · {v['exon']} · {v['variant_type']}</div>
            </div>
            {_pill(cls, cls_bg, cls_fg)}
          </div>
          <div class="v-body">
            <div class="dc-grid">{grid_cells}</div>
            {flags_html}
            {plain_html}
            <div style="margin-top:12px;padding-top:12px;border-top:0.5px solid #DEDAD4">
              <div style="font-size:10px;letter-spacing:.06em;text-transform:uppercase;color:#9A9590;margin-bottom:8px">
                Treatment options
                <span style="background:#EAF3DE;color:#3B6D11;font-size:9px;padding:1px 6px;border-radius:3px;margin-left:6px;font-weight:600">OncoKB/CIViC</span>
              </div>
              {tx_rows}
            </div>
          </div>
        </div>"""

    # ── Signatures HTML ──
    sig_colors = {"SBS4": "#854F0B", "SBS2": "#185FA5", "SBS1": "#888780", "SBS13": "#185FA5"}
    sigs_html = ""
    if is_clinician:
        sig_cards = ""
        for sig in data.get("mutational_signatures", []):
            color = sig_colors.get(sig["signature"], "#888780")
            sig_cards += f"""
            <div class="sig-card">
              <div style="font-weight:600;font-size:13px;margin-bottom:3px">{sig['signature']} — {sig['name']}</div>
              <div style="font-size:11px;color:#5A5650;margin-bottom:8px">{html_mod.escape(sig['aetiology'])}</div>
              {_sig_bar(sig['contribution_pct'], color)}
              <div style="font-size:14px;font-weight:600;color:{color}">{sig['contribution_pct']}%</div>
            </div>"""
        sigs_html = f"""
        <div class="section">
          <div class="sec-hdr"><span class="sec-title">Mutational signatures</span>
            <span class="badge" style="background:#EEEDFE;color:#3C3489">COSMIC</span></div>
          <div class="sig-grid">{sig_cards}</div>
          <p style="font-size:12px;color:#5A5650;margin-top:10px">
            Dominant tobacco signature (SBS4) consistent with smoking history.
            APOBEC signatures (SBS2/13) suggest ongoing mutational processes — may influence immunotherapy response.
          </p>
        </div>"""

    # ── Patient summary section ──
    patient_section = ""
    if not is_clinician:
        patient_section = f"""
        <div class="section">
          <div class="sec-hdr"><span class="sec-title">What these results mean for you</span></div>
          <div style="display:flex;flex-direction:column;gap:12px">
            <div style="background:#E6EFE9;border-left:3px solid #2D6B4A;border-radius:0 8px 8px 0;padding:12px 16px;font-size:13px;line-height:1.6;color:#1A3A2A">
              <strong>3 actionable findings:</strong> Three of the four changes found in your tumour have treatments available or in clinical trials. Your doctor will review these with you.
            </div>
            <div style="background:#E6F1FB;border-left:3px solid #185FA5;border-radius:0 8px 8px 0;padding:12px 16px;font-size:13px;line-height:1.6;color:#185FA5">
              <strong>1 uncertain finding:</strong> One change (KEAP1) does not yet have enough evidence to say whether it matters. No immediate action is needed.
            </div>
            <div style="background:#F1EFE8;border-left:3px solid #888780;border-radius:0 8px 8px 0;padding:12px 16px;font-size:13px;line-height:1.6;color:#5A5650">
              <strong>Next steps:</strong> Your doctor, {html_mod.escape(s['ordering_physician'])}, will discuss these findings with you at your next appointment.
            </div>
          </div>
        </div>"""

    # ── Evidence legend ──
    legend_html = ""
    if is_clinician:
        levels = [("1","FDA-recognized biomarker in this tumor type"),
                  ("2A","Standard care biomarker in another tumor type"),
                  ("3","Clinical evidence in this tumor type (early)"),
                  ("R","Known resistance to therapy")]
        ev_items = ""
        for code, desc in levels:
            ev_bg, ev_fg = _ev_colors_html(code)
            ev_items += f'<div style="display:flex;gap:8px;align-items:flex-start">{_pill(code, ev_bg, ev_fg, "4px")}<span style="font-size:12px;color:#5A5650">{desc}</span></div>'
        legend_html = f"""
        <div class="section">
          <div class="sec-hdr"><span class="sec-title">Evidence level guide</span>
            <span class="badge" style="background:#EAF3DE;color:#3B6D11">OncoKB</span></div>
          <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px">{ev_items}</div>
        </div>"""

    # ── Data sources ──
    ds_items = " &nbsp;·&nbsp; ".join(
        f"<strong>{k.replace('_',' ').title()}:</strong> {html_mod.escape(v)}"
        for k, v in ds.items())

    # ── Full HTML ──
    view_label = "Clinician" if is_clinician else "Patient"
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Genomic Cancer Report — {html_mod.escape(p['name'])} ({view_label} view)</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>
  *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'DM Sans',sans-serif;background:#F7F5F0;color:#1A1816;font-size:15px;line-height:1.65}}
  .page{{max-width:860px;margin:0 auto;padding:2rem 1.5rem 4rem}}
  .report-title{{font-family:'DM Serif Display',serif;font-size:28px;font-weight:400;line-height:1.2}}
  .header-meta{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:1rem 2rem;margin-top:1.5rem;padding-top:1.5rem;border-top:.5px solid rgba(26,24,22,.1)}}
  .meta-label{{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#9A9590;margin-bottom:2px}}
  .meta-value{{font-weight:500;font-size:14px}}
  .summary-strip{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:2rem}}
  .sum-card{{background:#fff;border:.5px solid #DEDAD4;border-radius:10px;padding:14px 16px}}
  .sum-label{{font-size:10px;letter-spacing:.07em;text-transform:uppercase;color:#9A9590;margin-bottom:6px}}
  .sum-value{{font-size:22px;font-weight:500;line-height:1}}
  .sum-sub{{font-size:12px;color:#5A5650;margin-top:4px}}
  .section{{margin-bottom:2.5rem}}
  .sec-hdr{{display:flex;align-items:baseline;gap:10px;margin-bottom:1rem;padding-bottom:8px;border-bottom:.5px solid #DEDAD4}}
  .sec-title{{font-size:17px;font-weight:500}}
  .badge{{font-size:10px;padding:2px 7px;border-radius:4px;font-weight:600;letter-spacing:.04em}}
  .v-card{{background:#fff;border:.5px solid #DEDAD4;border-radius:12px;margin-bottom:12px;overflow:hidden}}
  .v-header{{display:flex;align-items:center;gap:12px;padding:14px 18px;border-bottom:.5px solid #DEDAD4}}
  .gene-badge{{font-size:13px;font-weight:600;color:#fff;padding:4px 12px;border-radius:6px;white-space:nowrap;min-width:70px;text-align:center}}
  .v-body{{padding:14px 18px}}
  .dc-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:10px}}
  .dc{{}}
  .dc-l{{font-size:10px;letter-spacing:.06em;text-transform:uppercase;color:#9A9590;margin-bottom:3px}}
  .dc-v{{font-size:13px;font-weight:600}}
  .dc-s{{font-size:11px;color:#5A5650}}
  .tx-row{{display:flex;align-items:flex-start;gap:10px;padding:8px 0;border-bottom:.5px solid #DEDAD4;font-size:13px}}
  .tx-row:last-child{{border-bottom:none}}
  .sig-grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
  .sig-card{{background:#fff;border:.5px solid #DEDAD4;border-radius:10px;padding:14px 16px}}
  .view-badge{{display:inline-block;background:#1A3A2A;color:#fff;font-size:11px;font-weight:500;padding:3px 10px;border-radius:5px;margin-bottom:1rem}}
  .disclaimer{{margin-top:2rem;padding:14px 18px;border:.5px solid #DEDAD4;border-radius:10px;font-size:11px;color:#9A9590;line-height:1.7}}
  .footer-note{{text-align:center;font-size:11px;color:#9A9590;margin-top:1rem;padding-top:1rem;border-top:.5px solid #DEDAD4}}
  @media print{{.view-badge{{display:none}}}}
</style>
</head>
<body>
<div class="page">

  <div style="border-bottom:1.5px solid #1A1816;padding-bottom:1.5rem;margin-bottom:2rem">
    <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:1rem">
      <div>
        <h1 class="report-title">Genomic Cancer Report</h1>
        <p style="color:#5A5650;font-size:13px;margin-top:4px">Comprehensive somatic mutation analysis · {html_mod.escape(s['panel'])}</p>
      </div>
      <span class="view-badge">{'🔬 Clinician view' if is_clinician else '👤 Patient view'}</span>
    </div>
    <div class="header-meta">
      <div><div class="meta-label">Patient</div><div class="meta-value">{html_mod.escape(p['name'])}, {p['age']}{p['sex']}</div></div>
      <div><div class="meta-label">Sample ID</div><div class="meta-value">{html_mod.escape(sample_id)}</div></div>
      <div><div class="meta-label">Tumor type</div><div class="meta-value">{html_mod.escape(s['tumor_type'])}</div></div>
      <div><div class="meta-label">Report date</div><div class="meta-value">{html_mod.escape(s['report_date'])}</div></div>
      <div><div class="meta-label">Ordering physician</div><div class="meta-value">{html_mod.escape(s['ordering_physician'])}</div></div>
      <div><div class="meta-label">Tumor purity</div><div class="meta-value">{s['tumor_purity']}%</div></div>
    </div>
  </div>

  <div class="summary-strip">
    <div class="sum-card"><div class="sum-label">Variants detected</div>
      <div class="sum-value">{sm['total_variants']}</div>
      <div class="sum-sub">{sm['pathogenic_count']} pathogenic · {sm['vus_count']} VUS</div></div>
    <div class="sum-card"><div class="sum-label">Actionable variants</div>
      <div class="sum-value" style="color:#2D6B4A">{sm['actionable_count']}</div>
      <div class="sum-sub">FDA-approved therapies available</div></div>
    <div class="sum-card"><div class="sum-label">TMB</div>
      <div class="sum-value">{sm['tmb']}</div>
      <div class="sum-sub">{sm['tmb_unit']} · {sm['tmb_interpretation']}</div></div>
    <div class="sum-card"><div class="sum-label">MSI status</div>
      <div class="sum-value">{sm['msi_status']}</div>
      <div class="sum-sub">{sm['msi_interpretation']}</div></div>
  </div>

  <div class="section">
    <div class="sec-hdr">
      <span class="sec-title">Detected variants</span>
      <span class="badge" style="background:#EEEDFE;color:#3C3489">COSMIC</span>
      <span class="badge" style="background:#E6F1FB;color:#185FA5">ClinVar</span>
      <span class="badge" style="background:#EAF3DE;color:#3B6D11">OncoKB/CIViC</span>
    </div>
    {variants_html}
  </div>

  {sigs_html}
  {patient_section}
  {legend_html}

  <div style="margin-top:1rem;padding-top:1rem;border-top:.5px solid #DEDAD4;font-size:11px;color:#9A9590">
    <strong style="color:#1A1816">Data sources:</strong> {ds_items}
  </div>

  <div class="disclaimer">
    <strong style="color:#1A1816">Disclaimer:</strong>
    This report is provided for informational and research purposes only.
    COSMIC data is used under commercial license and is not approved for clinical decision-making as a standalone resource.
    All treatment decisions must be made by a qualified oncologist in conjunction with full clinical context.
    Variant interpretations reflect current evidence as of report date and may change as new data emerge.
    This sample report contains illustrative data only — no real patient data is included.
  </div>

  <div class="footer-note">
    CONFIDENTIAL — {view_label.upper()} VIEW &nbsp;·&nbsp; {html_mod.escape(sample_id)} &nbsp;·&nbsp; For research use only
  </div>

</div>
</body>
</html>"""

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✓ HTML report written → {out_path}")
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate cancer genomic report from JSON")
    parser.add_argument("json",   help="Path to report JSON file")
    parser.add_argument("--view", choices=["clinician", "patient"], default="clinician",
                        help="Report view: clinician (full) or patient (plain language). Default: clinician")
    parser.add_argument("--format", choices=["pdf", "html", "both"], default="both",
                        help="Output format: pdf, html, or both. Default: both")
    parser.add_argument("--out",  default=None,
                        help="Output path (without extension). Default: cancer_report_<id>_<view>")
    args = parser.parse_args()

    folder = "report_clinician" if args.view == "clinician" else "report_patient"
    Path(folder).mkdir(parents=True, exist_ok=True)
    base = args.out or str(Path(folder) / f"cancer_report_{args.view}")

    if args.format in ("pdf", "both"):
        generate_report(args.json, args.view, base + ".pdf")
    if args.format in ("html", "both"):
        generate_html(args.json, args.view, base + ".html")
