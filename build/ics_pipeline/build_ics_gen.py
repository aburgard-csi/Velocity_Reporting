#!/usr/bin/env python3
"""Data-driven, client-agnostic ICS deck builder.

    python3 build_ics_gen.py <client_ics.json> <marine_ref.pptx> <out.pptx>

Builds the ICS data slides from the JSON in the brand style, appends the six
monthly-detail slides, and clones the static education/reference + Q&A slides
from the Marine reference deck. Mystery-shop slide included only when
mystery_shop.include is true.
"""
import sys, os, json, copy
from io import BytesIO
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn
from pptx.oxml import parse_xml
from pptx.opc.constants import RELATIONSHIP_TYPE as RT
import ics_charts_gen as CH
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import summit_slide

NAVY=RGBColor(0x00,0x27,0x4C); ORANGE=RGBColor(0xF4,0x7A,0x29); STEEL=RGBColor(0x9D,0xB8,0xCC)
LIGHT=RGBColor(0xEC,0xF0,0xF4); WHITE=RGBColor(0xFF,0xFF,0xFF); GREYT=RGBColor(0x5A,0x66,0x70)
NAVYX="00274C"
SHADOW=('<a:effectLst xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
        '<a:outerShdw blurRad="63500" dist="38100" dir="5400000" rotWithShape="0">'
        '<a:srgbClr val="000000"><a:alpha val="26000"/></a:srgbClr></a:outerShdw></a:effectLst>')
def shadow(sh):
    spPr=sh._element.spPr
    for e in spPr.findall(qn('a:effectLst')): spPr.remove(e)
    spPr.append(parse_xml(SHADOW))

def tb(s,l,t,w,h,txt,size,color,bold=False,align=PP_ALIGN.LEFT,anchor=MSO_ANCHOR.TOP,font="Montserrat"):
    b=s.shapes.add_textbox(Inches(l),Inches(t),Inches(w),Inches(h)); tf=b.text_frame; tf.word_wrap=True; tf.vertical_anchor=anchor
    for i,ln in enumerate(txt if isinstance(txt,list) else [txt]):
        p=tf.paragraphs[0] if i==0 else tf.add_paragraph(); p.alignment=align
        r=p.add_run(); r.text=ln; r.font.size=Pt(size); r.font.bold=bold; r.font.name=font; r.font.color.rgb=color
    return b

def callout(s,l,t,w,h,big,lab,sub=None,fill=NAVY,big_size=40):
    shp=s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,Inches(l),Inches(t),Inches(w),Inches(h))
    shp.fill.solid(); shp.fill.fore_color.rgb=fill; shp.line.fill.background()
    try: shp.adjustments[0]=0.06
    except Exception: pass
    tf=shp.text_frame; tf.word_wrap=True; tf.vertical_anchor=MSO_ANCHOR.MIDDLE
    tf.margin_left=Inches(0.15); tf.margin_right=Inches(0.15)
    def line(t,sz,b,c,al=PP_ALIGN.CENTER,first=False):
        p=tf.paragraphs[0] if first else tf.add_paragraph(); p.alignment=al
        r=p.add_run(); r.text=t; r.font.size=Pt(sz); r.font.bold=b; r.font.color.rgb=c
        r.font.name="Montserrat"
    line(big,big_size,True,WHITE,first=True); line(lab,16,False,WHITE)
    if sub: line(sub,15,False,WHITE)
    shadow(shp); return shp

def pill(s,txt):
    shp=s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,Inches(9.9),Inches(0.34),Inches(2.95),Inches(0.62))
    shp.fill.solid(); shp.fill.fore_color.rgb=ORANGE; shp.line.fill.background()
    tf=shp.text_frame; tf.word_wrap=True; tf.vertical_anchor=MSO_ANCHOR.MIDDLE; p=tf.paragraphs[0]; p.alignment=PP_ALIGN.CENTER
    r=p.add_run(); r.text=txt; r.font.size=Pt(15); r.font.bold=True; r.font.name="Montserrat"; r.font.color.rgb=WHITE
    shadow(shp)   # period pill carries the standard callout drop shadow (STYLE.md)

def pagenum(s,n): tb(s,0.45,7.0,0.7,0.34,str(n),16,NAVY,True)

def cap_pill(s,l,t,w,h,txt,fill,size=22):
    shp=s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,Inches(l),Inches(t),Inches(w),Inches(h))
    shp.fill.solid(); shp.fill.fore_color.rgb=fill; shp.line.fill.background()
    try: shp.adjustments[0]=0.5
    except Exception: pass
    tf=shp.text_frame; tf.vertical_anchor=MSO_ANCHOR.MIDDLE; p=tf.paragraphs[0]; p.alignment=PP_ALIGN.CENTER
    r=p.add_run(); r.text=txt; r.font.size=Pt(size); r.font.bold=True; r.font.name="Montserrat"; r.font.color.rgb=WHITE
    shadow(shp); return shp

LOGO=[None]
def logo(s):
    if LOGO[0] and os.path.exists(LOGO[0]):
        s.shapes.add_picture(LOGO[0],Inches(11.28),Inches(6.78),Inches(1.7))

def blank(prs):
    lay=prs.slide_layouts[6] if len(prs.slide_layouts)>6 else prs.slide_layouts[-1]
    s=prs.slides.add_slide(lay)
    for ph in list(s.placeholders):      # drop layout placeholders (no "Click to add title" prompts)
        ph._element.getparent().remove(ph._element)
    return s
def title(s,txt): tb(s,0.5,0.28,11.5,0.9,txt,26,NAVY,True,font="Montserrat",anchor=MSO_ANCHOR.MIDDLE)
def sub(s,txt,top=1.12): tb(s,0.5,top,12.3,0.6,txt,16,GREYT,False)
def notes(s,txt): s.notes_slide.notes_text_frame.text=txt

def _white_borders(cell,w=12700):
    tcPr=cell._tc.get_or_add_tcPr()
    for edge in ('a:lnB','a:lnT','a:lnR','a:lnL'):
        for e in tcPr.findall(qn(edge)): tcPr.remove(e)
        ln=parse_xml(f'<a:ln xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" w="{w}" cap="flat"><a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill></a:ln>')
        ln.tag=qn(edge); tcPr.insert(0,ln)

def std_table(s,rows,l,t,w,colw,highlight_last=True,fs=16,rowh=0.4):
    nr=len(rows); nc=len(rows[0])
    gf=s.shapes.add_table(nr,nc,Inches(l),Inches(t),Inches(w),Inches(rowh*nr)); tbl=gf.table
    tw=sum(colw)
    for i,cw in enumerate(colw): tbl.columns[i].width=Inches(w*cw/tw)
    for row in tbl.rows: row.height=Inches(rowh)
    tblPr=tbl._tbl.tblPr
    for a in list(tblPr):
        if a.tag==qn('a:tableStyleId'): tblPr.remove(a)
    tbl.first_row=False; tbl.horz_banding=False
    for ri,row in enumerate(rows):
        for ci,val in enumerate(row):
            c=tbl.cell(ri,ci); _white_borders(c)
            c.margin_left=Inches(0.1); c.margin_right=Inches(0.08); c.margin_top=Inches(0.01); c.margin_bottom=Inches(0.01)
            c.vertical_anchor=MSO_ANCHOR.MIDDLE; p=c.text_frame.paragraphs[0]; p.alignment=PP_ALIGN.LEFT if ci==0 else PP_ALIGN.CENTER
            r=p.add_run(); r.text=str(val); r.font.name="Montserrat"
            if ri==0:
                c.fill.solid(); c.fill.fore_color.rgb=NAVY; r.font.color.rgb=WHITE; r.font.bold=True; r.font.size=Pt(fs)
            elif highlight_last and ri==nr-1:
                c.fill.solid(); c.fill.fore_color.rgb=ORANGE; r.font.color.rgb=WHITE; r.font.bold=True; r.font.size=Pt(fs)
            else:
                c.fill.solid(); c.fill.fore_color.rgb=RGBColor(0xF2,0xF5,0xF8) if ri%2 else WHITE
                r.font.color.rgb=NAVY; r.font.size=Pt(fs); r.font.bold=(ci==0)

def restyle_newrel(prs):
    """Static education-slide fixes: standard grid + centering on '2026 New Releases',
    nudge the 'E-Learning Library Guide' image off the logo, enlarge the 'New in 2026'
    bullets."""
    _t=lambda s: next((sh.text_frame.text.strip().split("\n")[0] for sh in s.shapes if sh.has_text_frame and sh.text_frame.text.strip()),"")
    for s in prs.slides:
        ttl=_t(s)
        if ttl.startswith("2026 New Releases"):
            delta=0.0
            for sh in s.shapes:
                if not sh.has_table: continue
                sh.top=Inches(1.5); t=sh.table
                aw=sum(Emu(c.width).inches for c in t.columns); newL=(13.333-aw)/2
                delta=newL-Emu(sh.left).inches; sh.left=Inches(newL)
                for ri,row in enumerate(t.rows):
                    row.height=Inches(0.29)
                    hdr=t.cell(ri,0).text.strip().lower().startswith("quarter")
                    for ci in range(len(t.columns)):
                        c=t.cell(ri,ci); _white_borders(c); c.vertical_anchor=MSO_ANCHOR.MIDDLE
                        c.margin_top=Inches(0.01); c.margin_bottom=Inches(0.01)
                        for p in c.text_frame.paragraphs:
                            p.alignment=PP_ALIGN.CENTER
                            for r in p.runs:
                                r.font.name="Montserrat"; r.font.size=Pt(12 if hdr else 10.5)
                                r.font.color.rgb=WHITE if hdr else NAVY; r.font.bold=hdr
                        c.fill.solid()
                        c.fill.fore_color.rgb=NAVY if hdr else (RGBColor(0xF2,0xF5,0xF8) if ri%2 else WHITE)
            # shift the two column-header labels to stay centered over the table
            for sh in s.shapes:
                if sh.has_text_frame and sh.text_frame.text.strip() in ("Leadership Training","Front Line Referrals"):
                    sh.left=Inches(Emu(sh.left).inches+delta)
        elif ttl.startswith("E-Learning Library"):
            for sh in s.shapes:
                if sh.shape_type==13 and not (Emu(sh.left).inches>11 and Emu(sh.top).inches>6.5):  # content image, not logo
                    sh.left=Inches(Emu(sh.left).inches-0.5)
        elif ttl.startswith(("New in 2026","Reporting: VIP")):
            for sh in s.shapes:
                if sh.has_text_frame and sh.top is not None and 1.1<Emu(sh.top).inches<6.5 and sh.width and Emu(sh.width).inches>3:
                    for p in sh.text_frame.paragraphs:
                        for r in p.runs:
                            cur=r.font.size.pt if r.font.size else 14
                            r.font.size=Pt(cur+4)

def enforce_min_font(prs, minpt=16):
    """Bump any explicit run font size below minpt up to minpt across all slides.
    Skips the dense '2026 New Releases' reference table (can't fit at 16pt)."""
    _t=lambda s: next((sh.text_frame.text.strip().split("\n")[0] for sh in s.shapes if sh.has_text_frame and sh.text_frame.text.strip()),"")
    for s in prs.slides:
        skip=_t(s).startswith(("2026 New Releases","Program Results by Month Opened","Referred Accounts by Product"))
        for sh in s.shapes:
            if sh.has_text_frame:
                for p in sh.text_frame.paragraphs:
                    for r in p.runs:
                        if r.font.size is not None and r.font.size.pt<minpt: r.font.size=Pt(minpt)
            if sh.has_table and not skip:
                for row in sh.table.rows:
                    for c in row.cells:
                        for p in c.text_frame.paragraphs:
                            for r in p.runs:
                                if r.font.size is not None and r.font.size.pt<minpt: r.font.size=Pt(minpt)

# ---- clone (for static education slides) ----
SHAPE_TAGS={qn('p:sp'),qn('p:pic'),qn('p:graphicFrame'),qn('p:grpSp'),qn('p:cxnSp')}
def clone_from(dst, src_slide):
    new=dst.slides.add_slide(dst.slide_layouts[6])
    for sh in list(new.shapes): sh._element.getparent().remove(sh._element)
    tree=new.shapes._spTree
    for el in src_slide.shapes._spTree:
        if el.tag in SHAPE_TAGS: tree.append(copy.deepcopy(el))
    for blip in tree.iter(qn('a:blip')):
        rId=blip.get(qn('r:embed'))
        if not rId: continue
        # copy the image BLOB into a fresh part in the destination package (avoids
        # cross-package partname collisions like duplicate image8.png)
        src_part=src_slide.part.rels[rId].target_part
        _, new_rId=new.part.get_or_add_image_part(BytesIO(src_part.blob))
        blip.set(qn('r:embed'), new_rId)
    return new

def extract_logo(ref, path):
    for s in ref.slides:
        for sh in s.shapes:
            if sh.shape_type==13:
                try:
                    part=s.part.rels[sh._element.blipFill.blip.rEmbed].target_part
                    if "image2" in str(part.partname):
                        open(path,"wb").write(part.blob); return path
                except Exception: pass
    return None

# ============================ build ============================
def build(d, static_path, out):
    # Missing-input guard (Aaron 2026-07-24/25): ICS financials are QUARTERLY (workbook-
    # driven); referrals are monthly (VIP). A monthly refresh CARRIES FORWARD the latest
    # workbook's financial sections in the client JSON (source notes keep the workbook
    # period, so the carry-forward is auditable). A null section therefore means the data
    # sheet was never populated / mis-assembled — STOP; never render empty slides or 0%.
    _required=("referrals","performance","revenue","financial_summary","monthly_detail","benchmark")
    _missing=[k for k in _required if not d.get(k)]
    if _missing:
        _cid=(d.get("meta") or {}).get("client_id","?")
        raise SystemExit(
            f"ICS build STOPPED for client {_cid} — missing input section(s): {', '.join(_missing)}.\n"
            f"referrals = monthly from VIP; the financial sections come from the latest ICS workbook\n"
            f"(quarterly). For a monthly refresh, carry the prior quarter's financial sections\n"
            f"forward in the client JSON — the slide source notes name the workbook + period.\n"
            f"If no workbook has EVER landed for this client, wait for it — do NOT build a\n"
            f"partial deck (CLAUDE.md: never render a slide from null).")
    # static_path = ics_static.pptx (5 education slides + Q&A, native from Marine). Data
    # slides are built into this package and reordered to the front.
    m=d["meta"]; client=m["client_name"]; rm=m["report_month"]
    from datetime import datetime
    try:
        _dd=datetime.strptime(m.get("data_pull",""),"%Y-%m-%d"); data_date=f"{_dd.strftime('%B')} {_dd.day}, {_dd.year}"
    except Exception:
        data_date=rm
    wbm=m.get("workbook_month",rm)   # last completed month in the workbook (PTD as-of)
    A=os.path.join(os.path.dirname(out) or ".","_ics_assets"); os.makedirs(A,exist_ok=True)
    CH.render_all(d, A); a=lambda n: os.path.join(A,n)
    prs=Presentation(static_path)
    prs.slide_width=Inches(13.333); prs.slide_height=Inches(7.5)
    # the template may be a FULL populated demo deck (Union Financial) — keep only the
    # static education/reference + Q&A slides; everything else is rebuilt from data.
    STATIC_TITLES=("New in 2026","E-Learning Library Guide","2026 New Releases",
                   "Reporting: VIP","VIP Best Practices","Questions & Discussion")
    # Mark which template slides to keep, but DO NOT remove them yet.
    #
    # Dropping them here frees their slide partnames, and python-pptx then hands
    # those freed numbers to the data slides we are about to add. The retained
    # static slides sit at slide22-slide27, so the last six data slides landed on
    # partnames the statics still held: six parts each ended up referenced TWICE
    # in sldIdLst. The deck reported 28 slides but contained 22 — LibreOffice
    # refused to open it at all and PowerPoint recovered by reordering, which is
    # how the title slide vanished and Contact Us surfaced near the front.
    #
    # Deferring the removal until after the data slides exist keeps every
    # template partname in use, so the new slides allocate above them.
    _lst=prs.slides._sldIdLst
    _tpl_els=list(_lst)
    _static_els, _drop_els, _static_slides = [], [], []
    for _el,_sl in zip(_tpl_els, list(prs.slides)):
        _ft=next((sh.text_frame.text.strip().split("\n")[0] for sh in _sl.shapes
                  if sh.has_text_frame and sh.text_frame.text.strip()),"")
        if _ft.startswith(STATIC_TITLES):
            _static_els.append(_el); _static_slides.append(_sl)
        else:
            _drop_els.append(_el)
    n_static=len(_static_els)
    # logo comes from the slides we are keeping (the deck still holds the demo
    # slides at this point, so scanning everything could grab a chart image)
    LOGO[0]=extract_logo(type("_Ref",(),{"slides":_static_slides})(), a("logo.png"))
    restyle_newrel(prs)   # standard grid + logo-clearance on the static '2026 New Releases' table
    # replace the static Q&A slide's client reference (Marine FCU -> this client)
    for sl in prs.slides:
        for sh in sl.shapes:
            if sh.has_text_frame and "Marine" in sh.text_frame.text:
                for p in sh.text_frame.paragraphs:
                    if p.runs and "Marine" in "".join(r.text for r in p.runs):
                        p.runs[0].text=f"{client}  •  {rm}"
                        for r in p.runs[1:]: r.text=""

    # 1 cover
    # CANONICAL title layout (matches ARS/MRPC): centered lockup card, centered 40pt title,
    # orange centered client + review lines (STYLE.md, Aaron 2026-07-24)
    s=blank(prs)
    r=s.shapes.add_shape(MSO_SHAPE.RECTANGLE,0,0,prs.slide_width,prs.slide_height); r.fill.solid(); r.fill.fore_color.rgb=NAVY; r.line.fill.background()
    _tcard=s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,Inches(5.01),Inches(0.7),Inches(3.32),Inches(1.27))
    _tcard.fill.solid(); _tcard.fill.fore_color.rgb=WHITE; _tcard.line.fill.background()
    try: _tcard.adjustments[0]=0.25
    except Exception: pass
    if LOGO[0] and os.path.exists(LOGO[0]):
        s.shapes.add_picture(LOGO[0],Inches(5.17),Inches(0.86),Inches(3.0),Inches(0.95))
    tb(s,0.8,2.7,11.7,2.0,"Invitation Checking® System",40,WHITE,True,align=PP_ALIGN.CENTER,anchor=MSO_ANCHOR.MIDDLE,font="Montserrat")
    tb(s,0.8,5.0,11.7,1.2,[client,f"Executive Review  •  {rm}"],20,ORANGE,True,align=PP_ALIGN.CENTER,font="Montserrat")
    notes(s,"Title slide. No data.")

    # 2 divider — CANONICAL product-divider layout (STYLE.md, Aaron 2026-07-24):
    # white logo card top-left, centered 52pt title, orange centered benefits line
    s=blank(prs)
    r=s.shapes.add_shape(MSO_SHAPE.RECTANGLE,0,0,prs.slide_width,prs.slide_height); r.fill.solid(); r.fill.fore_color.rgb=NAVY; r.line.fill.background()
    _card=s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,Inches(0.55),Inches(0.5),Inches(2.22),Inches(0.92))
    _card.fill.solid(); _card.fill.fore_color.rgb=WHITE; _card.line.fill.background()
    try: _card.adjustments[0]=0.25
    except Exception: pass
    if LOGO[0] and os.path.exists(LOGO[0]):
        s.shapes.add_picture(LOGO[0],Inches(0.71),Inches(0.66),Inches(1.9),Inches(0.6))
    tb(s,0.7,2.25,11.9,2.4,"Invitation Checking® System",52,WHITE,True,align=PP_ALIGN.CENTER,anchor=MSO_ANCHOR.MIDDLE,font="Montserrat")
    tb(s,0.7,5.05,11.9,0.9,"Referrals · Account Performance · Revenue",22,ORANGE,True,align=PP_ALIGN.CENTER,font="Montserrat")
    notes(s,"Section divider. No data.")

    # Agenda (after the ICS section header)
    s=blank(prs); title(s,"Agenda")
    items=["The Power of Referrals","Referral Trend & Results by Branch",
           "Performance of ICS Accounts","ICS Revenue & Revenue Detail",
           "ICS Financial Summary","Comparisons",
           "E-Learning & VIP Resources","Questions & Discussion"]
    yy=1.55
    for i,it in enumerate(items,1):
        bd=s.shapes.add_shape(MSO_SHAPE.OVAL,Inches(1.6),Inches(yy),Inches(0.55),Inches(0.55))
        bd.fill.solid(); bd.fill.fore_color.rgb=ORANGE; bd.line.fill.background()   # all badges orange (Aaron)
        btf=bd.text_frame; btf.vertical_anchor=MSO_ANCHOR.MIDDLE; bp=btf.paragraphs[0]; bp.alignment=PP_ALIGN.CENTER
        br=bp.add_run(); br.text=str(i); br.font.size=Pt(16); br.font.bold=True; br.font.name="Montserrat"; br.font.color.rgb=WHITE
        tb(s,2.45,yy+0.02,9.5,0.5,it,20,NAVY,False,anchor=MSO_ANCHOR.MIDDLE)
        yy+=0.66
    logo(s); pagenum(s,3); notes(s,"Agenda. No data.")

    rf=d["referrals"]; base=f"Source — {m.get('vip_source','VIP ICS Referral Data')} and {m.get('workbook','ICS workbook')} for {client} ({m['client_id']}), pulled {m['data_pull']}."

    # 3 Power of Referrals
    s=blank(prs); title(s,"The Power of Referrals"); pill(s,f"PTD · {data_date}")
    sub(s,"Selection: checking referrals logged by branch staff — program-to-date and 2026 YTD.")
    total_ref=rf["program_to_date"]   # single source: the current program-to-date total shown in the callout
    callout(s,0.55,1.7,3.5,2.0,f"{total_ref:,}","Referrals Program-to-Date",big_size=44)
    pm=rf["previous_month"]
    tb(s,4.35,1.7,8.45,2.4,
       f"{client} team members have generated {total_ref:,} checking referrals since "
       f"program inception — {rf['year_to_date']:,} year-to-date in 2026. {pm['label']} was a program high at {pm['value']}.",
       28,NAVY,False,anchor=MSO_ANCHOR.MIDDLE,font="Calibri")   # 28pt fills the space (Aaron 2026-07-24)
    # Previous-month-vs-goal is keyed generically; the month-named key (june_/july_)
    # is a leftover that only exists while that month happens to be the previous
    # one, so reading it directly KeyErrors on every later pull.
    _vs_goal = rf.get('prev_month_vs_goal_pct',
                      rf.get(f"{pm['label'].lower()}_vs_goal_pct", 0))
    for i,(big,lab) in enumerate([(f"{rf['year_to_date']:,}","2026 Year-to-Date"),
                                   (f"{pm['value']}",f"Previous Month ({pm['label']})"),
                                   (f"{_vs_goal}%",f"{pm['label']} vs Goal")]):
        callout(s,0.55+i*4.1,4.15,3.8,1.5,big,lab)
    logo(s); pagenum(s,3)
    notes(s,base+f" Referrals PTD {rf['program_to_date']:,}, YTD {rf['year_to_date']:,}, {pm['label']} {pm['value']}, "
                f"monthly goal {rf['monthly_goal']:,} ({pm['label']} vs goal {_vs_goal}%). VIP, current thru {rf['month_to_date']['label']} (partial).")

    # 4 Referral Trend
    t=rf["trend"]; s=blank(prs); title(s,f"Referral Trend – Last {len(t['months'])} Months")
    pill(s,f"PTD · {data_date}")
    s.shapes.add_picture(a("ics_trend.png"),Inches(0.66),Inches(1.55),Inches(12.0))
    tb(s,1.2,6.72,9.8,0.5,
       f"Monthly checking referrals, {t['months'][0]} – {t['months'][-1]}; {t['months'][-2]} a program high at {t['referrals'][-2]}, {t['months'][-1]} partial. Goal {rf['monthly_goal']:,}/mo.",
       16,GREYT,False)
    logo(s); pagenum(s,4)
    notes(s,base+f" Monthly referrals vs the {rf['monthly_goal']:,}/mo goal. Bars navy, last complete month orange, partial month hatched. VIP.")

    # 5 Results by Branch
    s=blank(prs); title(s,"Results by Branch – Year to Date"); pill(s,f"YTD · {data_date}")
    bb=rf["by_branch"]; rows=[["Branch","Referrals YTD","Goal","% of Goal"]]
    shown=bb["branches"][:8]
    # A branch can carry a zero goal (non-retail units like 1734's "Operations").
    # Show a dash rather than dividing by zero — and never invent a percentage.
    for b in shown:
        pct=f"{round(b['referrals']/b['goal']*100)}%" if b.get("goal") else "—"
        rows.append([b["name"],f"{b['referrals']}",f"{b['goal']}",pct])
    tr=sum(b["referrals"] for b in shown); tg=sum(b["goal"] for b in shown)
    rows.append([f"Top {len(shown)} Total",f"{tr}",f"{tg}",
                 f"{round(tr/tg*100)}%" if tg else "—"])
    std_table(s,rows,3.0,1.45,7.3,[2.1,1.1,0.8,0.9],highlight_last=True,fs=16,rowh=0.5)
    sub(s,f"Selection: checking referrals by branch, year-to-date (top {len(shown)} branches).",top=6.72)
    logo(s); pagenum(s,5)
    notes(s,base+" Referrals by branch, YTD, vs each branch's YTD goal. Top branches by referrals. VIP; branch names reconciled to the Charts 'Goals' tab.")

    # 5a Referred Accounts by Product (workbook 'Referred Accounts by Product' tab, participating products only)
    rbp=d.get("referred_by_product")
    if rbp:
        prods=rbp["products"]; tot_ref=sum(p["referred"] for p in prods); tot_acc=sum(p["total"] for p in prods)
        s=blank(prs); title(s,"Referred Accounts by Product"); pill(s,f"PTD · {wbm}")
        sub(s,"Checking products participating in the Invitation Checking® System — accounts referred vs. total book.")
        s.shapes.add_picture(a("ics_refprod.png"),Inches(0.35),Inches(1.75),Inches(7.35))
        rows=[["Product","Total Accts","Referred","% of Ref."]]
        for p in sorted(prods,key=lambda x:-x["referred"]):
            pct=f"{p['referred']/tot_ref*100:.0f}%" if (tot_ref and p["referred"]>0) else "—"
            rows.append([p["name"],f"{p['total']:,}",f"{p['referred']:,}",pct])
        rows.append(["Total — participating",f"{tot_acc:,}",f"{tot_ref:,}","100%"])
        std_table(s,rows,7.9,1.85,5.05,[2.5,0.95,0.85,0.85],highlight_last=True,fs=13,rowh=0.5)
        logo(s); pagenum(s,6)
        notes(s,base+" Referred Accounts by Product — workbook 'Referred Accounts by Product' tab, filtered to Participates in ICS = Yes. Chart shows products with referrals; table lists all participating products.")

    # 5b Performance of Accounts — section intro (Cindy's layout, our style)
    s=blank(prs); title(s,"Performance of Accounts")
    intro_bullets=["Drilling into the data","Overall Profitability","Breakdown of Revenue",
                   "Breakdown by Month","Comparisons"]
    bx=s.shapes.add_textbox(Inches(0.75),Inches(2.05),Inches(6.0),Inches(4.5)); btf=bx.text_frame; btf.word_wrap=True
    for i,it in enumerate(intro_bullets):
        pp=btf.paragraphs[0] if i==0 else btf.add_paragraph(); pp.space_after=Pt(16)
        r1=pp.add_run(); r1.text="•  "; r1.font.size=Pt(22); r1.font.bold=True; r1.font.name="Calibri"; r1.font.color.rgb=ORANGE
        r2=pp.add_run(); r2.text=it; r2.font.size=Pt(22); r2.font.name="Calibri"; r2.font.color.rgb=NAVY
    s.shapes.add_picture(a("ics_perfintro.png"),Inches(6.55),Inches(1.75),Inches(5.85))
    logo(s); pagenum(s,6)
    notes(s,"Section intro to the ICS account-performance analysis (profitability, revenue breakdown, monthly detail, comparisons). Motif = monthly referrals (bars) + cumulative referrals (line), from the VIP referral trend. No figures on the slide face.")

    # --- ROI / Present Value recalculated per client (the workbook ROI is not used) ---
    # PV per account = annual profit × life; life = velocity avg 6.9 yrs for the program's
    # first 2 years, else the client's modeled life. PV total = PV/acct × accounts opened.
    # ROI = PV total ÷ (cost per acquired account × accounts opened).  (Aaron, 2026-07-13)
    import datetime as _dt
    VELOCITY_LIFE=6.9
    p=d["performance"]; _fs=d["financial_summary"]; n_acct=_fs["ics_accounts"]
    def _prog_years():
        ps=d["meta"].get("program_start")
        if not ps: return 99
        y,m=(int(x) for x in ps.split("-")[:2])
        yy,mm,dd=(int(x) for x in d["meta"]["data_pull"].split("-"))
        return (_dt.date(yy,mm,dd)-_dt.date(y,m,1)).days/365.25
    life_used=VELOCITY_LIFE if _prog_years()<2 else p.get("life_of_ics_account_years",VELOCITY_LIFE)
    pv_per_acct=p["annual_profit_per_account"]*life_used
    pv_total=pv_per_acct*n_acct
    total_cost=p["cost_per_account"]*n_acct
    roi_calc=pv_total/total_cost if total_cost else 0

    # 6 Performance of ICS Accounts (Cindy's ROI layout: 3 rectangular callouts + heading + bullets)
    AMBER=RGBColor(0xF5,0xA6,0x23)
    s=blank(prs); title(s,"Performance of ICS Accounts"); pill(s,f"PTD · {wbm}")
    tb(s,0.5,1.12,12.3,0.6,f"Return on Investment — {roi_calc:.2f} to 1",22,NAVY,True)
    modeled=p.get("life_of_ics_account_years",life_used)
    young=abs(life_used-VELOCITY_LIFE)<0.05   # first-2-years programs use the 6.9-yr velocity life
    if young:
        life_bullets=[f"Models indicate your average life of account is {modeled:g} years",
                      "National Average is 6.9 Years"]
        pv_bullets=["Using 6.9 Years to be conservative",
                    f"Acquisition Cost: ${p['cost_per_account']:,.0f}"]
    else:
        life_bullets=[f"{p.get('pct_added_life',0)*100:.0f}% longer than the {VELOCITY_LIFE:g}-year "
                      "average for all accounts","Modeled from ICS account survival"]
        pv_bullets=[f"Using the {life_used:g}-year modeled account life",
                    f"Acquisition Cost: ${p['cost_per_account']:,.0f}"]
    cols=[(AMBER, f"${p['annual_profit_per_account']:,.2f}",
           "Annual Profit Contribution per Account",
           [f"Accounts pay for themselves in ~{p['payback_months']} months"]),
          (ORANGE, f"{life_used:g} years",
           "Average Life of Accounts", life_bullets),
          (NAVY, f"${pv_per_acct:,.2f}",
           "Present Value per Account", pv_bullets)]
    BW,BT,BH,GAP=3.8,1.9,2.35,0.42
    x0=(13.333-(3*BW+2*GAP))/2                     # centered block, equal side margins
    for k,(fill,big,heading,bullets) in enumerate(cols):
        x=x0+k*(BW+GAP)
        box=s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,Inches(x),Inches(BT),Inches(BW),Inches(BH))
        box.fill.solid(); box.fill.fore_color.rgb=fill; box.line.fill.background()
        try: box.adjustments[0]=0.06                # rounded corners, matches deck callouts
        except Exception: pass
        tf=box.text_frame; tf.vertical_anchor=MSO_ANCHOR.MIDDLE; pp=tf.paragraphs[0]; pp.alignment=PP_ALIGN.CENTER
        r=pp.add_run(); r.text=big; r.font.size=Pt(36); r.font.bold=True; r.font.name="Montserrat"; r.font.color.rgb=WHITE
        shadow(box)
        tb(s,x,BT+BH+0.12,BW,0.6,heading,18,NAVY,True)
        bt=s.shapes.add_textbox(Inches(x),Inches(BT+BH+0.8),Inches(BW),Inches(1.7)); btf=bt.text_frame; btf.word_wrap=True
        for j,bl in enumerate(bullets):
            q=btf.paragraphs[0] if j==0 else btf.add_paragraph(); q.space_after=Pt(4)
            rr=q.add_run(); rr.text="•  "+bl; rr.font.size=Pt(17); rr.font.name="Calibri"; rr.font.color.rgb=NAVY
    logo(s); pagenum(s,6)
    notes(s,base+f" ROI recalculated (workbook ROI not used): PV/acct = annual profit ${p['annual_profit_per_account']:.2f} × {life_used:g} yr "
                f"(velocity life, program <2 yr) = ${pv_per_acct:,.2f}; PV total = ${pv_total:,.0f}; "
                f"ROI = PV total ÷ (${p['cost_per_account']:.0f} × {n_acct:,}) = {roi_calc:.2f} : 1.")

    # 6b Program Results by Month Opened — monthly-detail data table (revenue + amortized expense)
    md0=d["monthly_detail"]; mos=md0["months"]; nrm=len(mos)
    mo_open=[nrm-i for i in range(nrm)]; amort=p["cost_per_account"]/60.0
    _rr=lambda label,vals,fmt:[label]+[fmt(v) for v in vals]
    trows=[["Month Opened"]+mos,
           _rr("Accounts Opened",md0["accounts_opened"],lambda v:f"{v:,}"),
           _rr("Avg Balance / Acct",md0["avg_balance"],lambda v:f"${v:,.0f}"),
           _rr("Spread on Deposits",md0["spread"],lambda v:f"${v:,.0f}"),
           _rr("Interchange Income",md0["interchange"],lambda v:f"${v:,.0f}"),
           _rr("NSF / OD Fees",md0["nsf_od"],lambda v:f"${v:,.0f}"),
           _rr("Other Fees",md0["other_fees"],lambda v:f"${v:,.0f}"),
           _rr("Account Profit Contribution",md0["profit_contribution"],lambda v:f"${v:,.0f}"),
           _rr("Amortized Expense / Acct / Mo",[amort]*nrm,lambda v:f"${v:,.2f}"),
           _rr("Months Open",mo_open,lambda v:f"{v}")]
    s=blank(prs); title(s,"Program Results by Month Opened"); pill(s,f"PTD · {wbm}")
    sub(s,"ICS-originated checking accounts by opening-month cohort — revenue and amortized acquisition expense.")
    std_table(s,trows,0.35,1.7,12.63,[2.9]+[1]*nrm,highlight_last=False,fs=13,rowh=0.46)
    tb(s,0.4,6.55,12.55,0.4,f"Amortized expense: ${p['cost_per_account']:.0f} ÷ 60 months = ${amort:.2f} per account per month × time open.",14,GREYT,False)
    logo(s); pagenum(s,7)
    notes(s,base+f" Monthly Detail tab: revenue components, account profit contribution, amortized expense (${p['cost_per_account']:.0f} ÷ 60 = ${amort:.2f}/acct/mo). Cohort by opening month.")

    # 7 ICS Revenue
    s=blank(prs); title(s,"ICS Revenue"); pill(s,f"PTD · {wbm}")
    sub(s,"Selection: ICS-originated checking accounts; revenue program-to-date.")
    s.shapes.add_picture(a("ics_revpie.png"),Inches(0.5),Inches(1.55),Inches(12.3))
    logo(s); pagenum(s,7)
    notes(s,base+" PTD revenue by source: "+", ".join(f"{c['name']} ${c['amount']:,.0f}" for c in d['revenue']['components'])+f"; total ${d['revenue']['total']:,.0f}. Workbook 'Monthly Detail'.")

    # 8-13 monthly detail
    md=d["monthly_detail"]; icPTD=sum(md["interchange"]); nsPTD=sum(md["nsf_od"]); acc=md["cumulative_accounts"][-1]
    am=CH.acct_months(d)
    nsoPTD=sum(md["nsf_od"])+sum(md["other_fees"]); spPTD=sum(md["spread"])
    nso_nov=(md["nsf_od"][0]+md["other_fees"][0])
    SPREAD_DEF="Spread = 2.75% × avg month-end balance/account, summed monthly, net of interest paid."
    def mdslide(pg,ttl,subt,img,tiles,note,foot=None):
        s=blank(prs); title(s,ttl); sub(s,subt); s.shapes.add_picture(img,Inches(0.4),Inches(1.7),Inches(8.6))
        ty=1.9
        for big,lab in tiles: callout(s,9.3,ty,3.5,1.4,big,lab,big_size=26); ty+=1.6
        if foot: tb(s,0.5,6.5,12.3,0.5,foot,16,GREYT,False)
        logo(s); pagenum(s,pg); notes(s,note)
    IC_DEF="Interchange Income: Blended Rate × Debit Card Spend"
    mdslide(8,"Total Interchange Revenue",
            "Interchange revenue by cohort (opening month), program-to-date.",
            a("ics_ic_tot.png"),[(f"${icPTD:,.0f}","Interchange PTD"),(f"{acc:,}","ICS accounts")],
            base+" Interchange revenue by cohort. Workbook 'Monthly Detail' (revenue only).",foot=IC_DEF)
    mdslide(9,"Interchange Revenue per Account per Month",
            "Interchange revenue ÷ accounts opened ÷ months open, by cohort (e.g. Nov 25: $398.47 / 19 / 8 = $2.62).",
            a("ics_ic_pam.png"),[(f"${icPTD/am:.2f}","Blended / account / month"),(f"${icPTD/acc:.2f}","Per account, life-to-date")],
            base+" Interchange per account per month, cohort-normalized. Workbook 'Monthly Detail'.",foot=IC_DEF)
    mdslide(10,"Total NSF/OD & Other Fee Revenue",
            "NSF/OD fees plus other service charges by cohort (opening month), program-to-date. Revenue only — not item counts.",
            a("ics_nsf_tot.png"),[(f"${nsoPTD:,.0f}","NSF/OD & Other PTD"),(f"{acc:,}","ICS accounts")],
            base+" NSF/OD + other service charges by cohort. Workbook 'Monthly Detail' (revenue only).")
    mdslide(11,"NSF/OD & Other Fees per Account per Month",
            f"(NSF/OD + other charges) ÷ accounts opened ÷ months open, by cohort (e.g. Nov 25: ${nso_nov:,.2f} / 19 / 8 = ${nso_nov/19/8:.2f}).",
            a("ics_nsf_pam.png"),[(f"${nsoPTD/am:.2f}","Blended / account / month"),(f"${nsoPTD/acc:.2f}","Per account, life-to-date")],
            base+" NSF/OD + other charges per account per month, cohort-normalized. Workbook 'Monthly Detail'.")
    mdslide(12,"Total Spread Revenue",
            "Spread revenue by cohort (opening month), program-to-date.",
            a("ics_spread_tot.png"),[(f"${spPTD:,.0f}","Spread PTD"),(f"{acc:,}","ICS accounts")],
            base+" Spread revenue by cohort. Workbook 'Monthly Detail'.",foot=SPREAD_DEF)
    mdslide(13,"Spread Revenue per Account per Month",
            f"Spread revenue ÷ accounts opened ÷ months open, by cohort (e.g. Nov 25: ${md['spread'][0]:,.2f} / 19 / 8 = ${md['spread'][0]/19/8:.2f}).",
            a("ics_spread_pam.png"),[(f"${spPTD/am:.2f}","Blended / account / month"),(f"${spPTD/acc:.2f}","Per account, life-to-date")],
            base+" Spread per account per month, cohort-normalized. Workbook 'Monthly Detail'.",foot=SPREAD_DEF)
    mdslide(14,"Revenue Composition by Month",
            "Monthly revenue per referral by source: spread (net of interest), interchange, NSF/OD, other.",
            a("ics_comp.png"),[(f"${sum(md['profit_contribution']):,.0f}","Profit contribution PTD"),(f"{acc:,}","ICS accounts")],
            base+" Monthly revenue composition by cohort. Workbook 'Monthly Detail'.")
    tot_pam=(sum(md["spread"])+sum(md["interchange"])+sum(md["nsf_od"])+sum(md["other_fees"]))/am
    mdslide(15,"Revenue per Account per Month by Source",
            "Blended revenue per account per month by source, life-to-date (cohort revenue ÷ account-months).",
            a("ics_bucketcmp.png"),[(f"${tot_pam:,.2f}","All sources / acct / mo"),(f"{acc:,}","ICS accounts")],
            base+" Per-account-per-month revenue compared across sources (spread, interchange, NSF/OD, other), life-to-date. Workbook 'Monthly Detail'.")

    # 14 Financial Summary
    fs=d["financial_summary"]; s=blank(prs); title(s,"ICS Financial Summary"); pill(s,f"PTD · {wbm}")
    sub(s,"Selection: ICS-originated checking accounts; figures program-to-date.")
    BT0=1.85                                    # callout block sits lower to balance against the selection text (Aaron 2026-07-24)
    panel=s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,Inches(0.5),Inches(BT0),Inches(4.3),Inches(4.6))
    panel.fill.solid(); panel.fill.fore_color.rgb=LIGHT; panel.line.fill.background()
    try: panel.adjustments[0]=0.04
    except Exception: pass
    cpa=d["performance"]["cost_per_account"]; billed=cpa*fs["ics_accounts"]
    tb(s,0.75,BT0+0.1,3.8,0.4,"Program to Date",16,NAVY,True)
    yy=BT0+0.6
    for lab,val in [("Account Profit Contribution",f"${fs['account_profit_contribution']:,.0f}"),
                    ("Amortized Program Expense",f"${fs['total_program_expense']:,.0f}"),
                    ("Net Profit",f"${fs['net_profit']:,.0f}"),
                    (f"Billed Expense for {fs['ics_accounts']:,} Accounts",f"${billed:,.0f}")]:
        tb(s,0.75,yy,3.9,0.4,lab,14,GREYT,False); tb(s,0.75,yy+0.32,3.9,0.5,val,20,NAVY,True); yy+=0.98
    tb(s,0.5,6.5,12.6,0.5,f"Amortized expense: ${cpa:,.0f} ÷ 60 months = ${cpa/60:.2f} per account per month × time open.",16,GREYT,False)
    for i,(big,lab) in enumerate([(f"{fs['ics_accounts']:,}","ICS Accounts"),(f"${fs['average_balance']:,.0f}","Average Balance"),(f"{roi_calc:.2f} : 1","Return on Investment")]):
        callout(s,5.15,BT0+i*1.55,3.3,1.35,big,lab,big_size=24)
    callout(s,8.7,BT0,4.15,4.6,f"${pv_total/1e6:,.2f}M","Present Value",
            "of New ICS Accounts",fill=ORANGE,big_size=44)
    logo(s); pagenum(s,14)
    notes(s,base+f" Contribution ${fs['account_profit_contribution']:,.0f} − expense ${fs['total_program_expense']:,.0f} = net ${fs['net_profit']:,.0f}; "
                f"{fs['ics_accounts']:,} accounts, avg balance ${fs['average_balance']:,.0f}. Present Value = ${pv_total:,.0f} (annual profit × {life_used:g} yr × accounts); ROI {roi_calc:.2f}:1 (recalculated, workbook ROI not used).")

    # 15 Comparisons (modeled on the CSI/Velocity ICS Review template)
    bm=d["benchmark"]; s=blank(prs); title(s,"Comparisons")
    tb(s,1.3,1.4,3.9,0.5,"Velocity Clients' Average",18,NAVY,True,align=PP_ALIGN.CENTER)
    tb(s,8.15,1.4,3.9,0.5,f"{client} Data",18,NAVY,True,align=PP_ALIGN.CENTER)
    def cfmt(v,f):
        if f=="usd0": return f"${v:,.0f}"
        if f=="pct0": return f"{v:.0f}%"
        if f=="pct1": return f"{v:.1f}%"
        if f=="years": return f"{v:g} Years"
        return f"{v:g}"
    yy=2.15
    for mm in bm["metrics"]:
        cval=pv_per_acct if mm["label"].startswith("Lifetime Value") else mm["client"]   # recomputed PV
        cap_pill(s,1.3,yy,3.9,0.78,cfmt(mm["velocity_avg"],mm["fmt"]),ORANGE)
        tb(s,5.3,yy-0.05,2.75,0.9,mm["label"],17,NAVY,False,align=PP_ALIGN.CENTER,anchor=MSO_ANCHOR.MIDDLE)
        cap_pill(s,8.15,yy,3.9,0.78,cfmt(cval,mm["fmt"]),NAVY)
        yy+=1.06
    if bm.get("non_ics_close_rate_pct"):
        tb(s,1.3,yy+0.06,10.8,0.4,f"Note: your Non-ICS accounts' 12-month close rate = {bm['non_ics_close_rate_pct']:.1f}%.",14,GREYT,False)
    logo(s); pagenum(s,15)
    notes(s,base+f" {client} vs the Velocity ICS client average — openings/branch, lifetime value, 12-mo close rate (ICS {[x['client'] for x in bm['metrics'] if 'Close' in x['label']][0]:.2f}% vs Non-ICS {bm.get('non_ics_close_rate_pct',0):.2f}%), account life. Velocity averages are program-wide constants.")

    # optional mystery shop
    if d.get("mystery_shop",{}).get("include"):
        ms=d["mystery_shop"]; s=blank(prs); title(s,"Mystery Shop & Insights")
        for i,(big,lab,fill) in enumerate([(f"{ms['mystery_shops_ytd']}","Mystery Shops (YTD)",NAVY),
                                            (f"{ms['pass_rate_pct']}%","Pass Rate",ORANGE),
                                            (f"{ms['offered_referral_pct']}%","Offered a Referral",NAVY)]):
            callout(s,0.55+i*4.1,1.5,3.8,1.5,big,lab,fill=fill)
        logo(s); pagenum(s,16); notes(s,base+" Mystery shops YTD, pass rate, referral-offered rate. ICS Charts.")

    # Contact slide (built last so it lands at the very end, after Q&A)
    contacts=d.get("contacts",[])
    if contacts:
        s=blank(prs); title(s,"Contact Us")
        ncc=len(contacts); cw=5.6; gap=0.5; x0=(13.333-(ncc*cw+(ncc-1)*gap))/2
        for i,cc in enumerate(contacts):
            l=x0+i*(cw+gap)
            card=s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,Inches(l),Inches(1.95),Inches(cw),Inches(3.55))
            card.fill.solid(); card.fill.fore_color.rgb=NAVY; card.line.fill.background()
            try: card.adjustments[0]=0.05
            except Exception: pass
            shadow(card)
            tb(s,l+0.35,2.45,cw-0.7,0.7,cc["name"],26,WHITE,True,align=PP_ALIGN.CENTER)
            tb(s,l+0.35,3.25,cw-0.7,1.0,cc["role"],15,ORANGE,False,align=PP_ALIGN.CENTER)
            tb(s,l+0.35,4.5,cw-0.7,0.5,cc["phone"],17,WHITE,False,align=PP_ALIGN.CENTER)
            tb(s,l+0.35,5.02,cw-0.7,0.5,cc["email"],15,WHITE,False,align=PP_ALIGN.CENTER)
        logo(s); pagenum(s,99); notes(s,"Contact information.")

    # ---- reorder: data slides move to the front; static education + Q&A stay last;
    # the contact slide (last-built data slide) goes to the very end ----
    lst=prs.slides._sldIdLst
    # now that every data slide exists, discard the template's demo slides
    # (entry AND relationship, so no orphan parts are serialised)
    for _el in _drop_els:
        _rid=_el.get(qn('r:id'))
        if _el in list(lst):
            lst.remove(_el)
        if _rid:
            try: prs.part.drop_rel(_rid)
            except KeyError: pass
    ids=list(lst)
    static_ids=[e for e in ids if e in _static_els]
    data_ids=[e for e in ids if e not in _static_els]
    tail=[]
    if contacts and data_ids: tail=[data_ids.pop()]   # contact slide -> very end
    for sid in ids: lst.remove(sid)
    for sid in data_ids+static_ids+tail: lst.append(sid)
    # invariant: every slide referenced exactly once
    _seen=[e.get(qn('r:id')) for e in list(lst)]
    if len(_seen)!=len(set(_seen)):
        raise SystemExit("ERROR: duplicate slide references in sldIdLst")

    enforce_min_font(prs, 16)   # minimum 16pt across the deck
    summit_slide.insert_summit_after_title(prs)   # Executive Summit after the title (all decks)

    # renumber the content-slide page boxes sequentially (skip cover/divider/full-bleed)
    n=0
    for sl in prs.slides:
        n+=1
        for sh in sl.shapes:
            if sh.has_text_frame and sh.left is not None and sh.top is not None:
                if abs(Emu(sh.left).inches-0.45)<0.2 and abs(Emu(sh.top).inches-7.04)<0.2 and sh.text_frame.text.strip().isdigit():
                    sh.text_frame.paragraphs[0].runs[0].text=str(n)
    import fit_layout; fit_layout.fit(prs)   # clear number/logo, clamp off-slide (shared)
    prs.save(out); print("built",out,"->",len(prs.slides._sldIdLst),"slides")

if __name__=="__main__":
    build(json.load(open(sys.argv[1])), sys.argv[2], sys.argv[3])
