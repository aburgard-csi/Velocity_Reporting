#!/usr/bin/env python3
"""Data-driven, client-agnostic MRPC deck builder.

Reads a per-client MRPC data sheet (JSON), renders every chart from it, clones
the neutral MRPC template, swaps charts + all client text + speaker notes, and
saves a finished MRPC Executive Review deck for ANY client.

    python3 build_mrpc_gen.py <client_mrpc.json> <template.pptx> <out.pptx>

Tier colours on the Enrollments slide: Gold = orange, Platinum = steel/gray,
Business = navy — in the chart bars AND the tier callouts, which match.
(An earlier revision had callouts inverted against the bars; the code below
is the truth and this line used to contradict it.)

The Business tier and its callout appear only when meta.has_business is true.
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import summit_slide
from pptx import Presentation
from pptx.util import Inches, Emu, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml.ns import qn
from pptx.oxml import parse_xml
import mrpc_charts_gen as CH

# Standard callout drop shadow (STYLE.md "Callouts") — defined once, in build/shapes.py.
from shapes import shadow as add_shadow
from brand import usd_compact as _usd   # one money format for every program

NAVY=RGBColor(0x00,0x27,0x4C); ORANGE=RGBColor(0xF4,0x7A,0x29)
STEEL=RGBColor(0x9D,0xB8,0xCC); WHITE=RGBColor(0xFF,0xFF,0xFF)

# ---- text helpers (preserve run formatting) --------------------------------
def set_lines(shape, lines):
    tf=shape.text_frame; paras=tf.paragraphs
    for i,ln in enumerate(lines):
        if i<len(paras):
            p=paras[i]
            if p.runs:
                p.runs[0].text=ln
                for r in p.runs[1:]: r._r.getparent().remove(r._r)
            else:
                p.add_run().text=ln
    for j in range(len(lines), len(paras)):
        for r in paras[j].runs: r.text=""

def set_text(shape, txt): set_lines(shape,[txt])

def set_fill(shape, rgb):
    shape.fill.solid(); shape.fill.fore_color.rgb=rgb

def set_notes(slide, txt):
    slide.notes_slide.notes_text_frame.text=txt

# ---- picture helpers -------------------------------------------------------
def partname(slide, sh):
    try: return str(slide.part.rels[sh._element.blipFill.blip.rEmbed].target_part.partname).split('/')[-1]
    except: return ''

def pics(slide, logo="image2"):
    out=[]
    for sh in slide.shapes:
        if sh.shape_type==13 and partname(slide,sh).rsplit('.',1)[0]!=logo:
            out.append(sh)
    return out

def swap(slide, sh, path):
    # Repoint the picture to a NEW image part (unique file content -> unique part),
    # rather than mutating a shared part's blob. Cloned slides may share the source
    # image part, so mutating in place would corrupt both — repointing is safe.
    image_part, rId = slide.part.get_or_add_image_part(path)
    sh._element.blipFill.blip.set(qn('r:embed'), rId)

def place_pic(sh, l, t, w, h):
    sh.left=Inches(l); sh.top=Inches(t); sh.width=Inches(w); sh.height=Inches(h)

def add_callout(slide, l, t, w, h, big, label, sub=None, fill=None):
    fill=fill or NAVY
    shp=slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(l),Inches(t),Inches(w),Inches(h))
    shp.fill.solid(); shp.fill.fore_color.rgb=fill; shp.line.fill.background()
    try: shp.adjustments[0]=0.06
    except Exception: pass
    tf=shp.text_frame; tf.word_wrap=True; tf.vertical_anchor=MSO_ANCHOR.MIDDLE
    tf.margin_left=Inches(0.25); tf.margin_right=Inches(0.2)
    def line(txt,size,bold,color,first=False):
        p=tf.paragraphs[0] if first else tf.add_paragraph()
        p.alignment=PP_ALIGN.LEFT; r=p.add_run(); r.text=txt
        r.font.size=Pt(size); r.font.bold=bold; r.font.color.rgb=color
        r.font.name="Montserrat" if (bold and size>=30) else "Calibri"
    line(big,40,True,WHITE,first=True)
    line(label,15,True,WHITE)
    if sub: line(sub,11,False,RGBColor(0xC9,0xD6,0xE3))
    add_shadow(shp)
    return shp

def date_pill(slide, text):
    """Orange reporting-date pill, top-right of a content slide (matches the
    template's 'As of' pill: 10.50, 0.34, 2.35x0.50, Calibri 12 bold white,
    centered, default rounding, drop shadow). Reuses an existing top-right pill
    if the template already carries one, else creates it."""
    for sh in slide.shapes:
        if sh.shape_type==1 and sh.top is not None and sh.left is not None \
           and abs(Emu(sh.top).inches-0.34)<0.2 and abs(Emu(sh.left).inches-10.5)<0.35:
            set_text(sh, text); add_shadow(sh); return sh
    shp=slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                               Inches(10.50),Inches(0.34),Inches(2.35),Inches(0.50))
    shp.fill.solid(); shp.fill.fore_color.rgb=ORANGE; shp.line.fill.background()
    tf=shp.text_frame; tf.word_wrap=True; tf.vertical_anchor=MSO_ANCHOR.MIDDLE
    tf.margin_left=Inches(0.1); tf.margin_right=Inches(0.1)
    tf.margin_top=Inches(0.05); tf.margin_bottom=Inches(0.05)
    p=tf.paragraphs[0]; p.alignment=PP_ALIGN.CENTER
    r=p.add_run(); r.text=text; r.font.size=Pt(12); r.font.bold=True
    r.font.name="Calibri"; r.font.color.rgb=WHITE
    add_shadow(shp)
    return shp

def renumber_pages(prs):
    n=0
    for s in prs.slides:
        n+=1
        for sh in s.shapes:
            if sh.has_text_frame and sh.left is not None and sh.top is not None:
                if abs(Emu(sh.left).inches-0.45)<0.2 and abs(Emu(sh.top).inches-7.04)<0.2:
                    t=sh.text_frame.text.strip()
                    if t.isdigit() and sh.text_frame.paragraphs[0].runs:
                        sh.text_frame.paragraphs[0].runs[0].text=str(n)

def txt_at(slide, top=None, left=None, contains=None, tol=0.15):
    """Find a text box by approximate top/left and/or substring. tol kept tight (0.15")
    so an overlay text box is not confused with the tile shape ~0.25" behind it."""
    for sh in slide.shapes:
        if not sh.has_text_frame: continue
        if contains and contains not in sh.text_frame.text: continue
        if top is not None and (sh.top is None or abs(Emu(sh.top).inches-top)>tol): continue
        if left is not None and (sh.left is None or abs(Emu(sh.left).inches-left)>tol): continue
        return sh
    return None

def autoshapes(slide):
    return [sh for sh in slide.shapes if sh.shape_type==1]

def add_contact_slide(prs, contact):
    """Contact Us slide at the very end (Aaron 2026-07-16; mirrors the ARS/ICS design).
    `contact` is the client's managing CSM, from rpe_env.csm_contact (Aaron, 2026-09-16).
    The MRPC shell CARRIES a Contact slide whose card is static text for one CSM; that card is
    rewritten in place rather than a second slide added."""
    from shapes import find_contact_slide, fill_contact_card
    shell = find_contact_slide(prs)
    if shell is not None:
        return fill_contact_card(shell, contact)
    blank=next((ly for ly in prs.slide_layouts if len(ly.placeholders)==0), prs.slide_layouts[-1])
    cs=prs.slides.add_slide(blank)
    for ph in list(cs.placeholders):               # no PowerPoint prompt boxes (Aaron 2026-07-24)
        ph._element.getparent().remove(ph._element)
    def ctb(x,y,w,h,txt,sz,col,bold,align=PP_ALIGN.CENTER):
        t=cs.shapes.add_textbox(Inches(x),Inches(y),Inches(w),Inches(h)); p=t.text_frame.paragraphs[0]
        p.alignment=align; r=p.add_run(); r.text=txt
        r.font.name="Montserrat"; r.font.size=Pt(sz); r.font.bold=bold; r.font.color.rgb=col
        return t
    ctb(0.5,0.28,12.33,0.9,"Contact Us",30,NAVY,True,align=PP_ALIGN.LEFT)
    from shapes import contact_card_lines, CONTACT_CARD_TOP, CONTACT_CARD_W as cw, CONTACT_CARD_H
    contacts=[contact]
    ncc=len(contacts); gap=0.5; x0=(13.333-(ncc*cw+(ncc-1)*gap))/2
    style={"name":(26,WHITE,True),"role":(15,ORANGE,False),"phone":(17,WHITE,False),"email":(15,WHITE,False)}
    for i,cc in enumerate(contacts):
        l=x0+i*(cw+gap)
        card=cs.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,Inches(l),Inches(CONTACT_CARD_TOP),Inches(cw),Inches(CONTACT_CARD_H))
        card.fill.solid(); card.fill.fore_color.rgb=NAVY; card.line.fill.background()
        try: card.adjustments[0]=0.05
        except Exception: pass
        add_shadow(card)
        for field,txt,top,hh in contact_card_lines(cc):
            ctb(l+0.35,top,cw-0.7,hh,txt,*style[field])
    logo=os.path.join(os.path.dirname(os.path.dirname(__file__)),"assets","logo.png")
    if os.path.exists(logo):
        try: cs.shapes.add_picture(logo,Inches(11.28),Inches(6.78),Inches(1.7))
        except Exception: pass
    pn=cs.shapes.add_textbox(Inches(0.45),Inches(7.04),Inches(0.7),Inches(0.32)); pp=pn.text_frame.paragraphs[0]
    rr=pp.add_run(); rr.text=str(len(prs.slides._sldIdLst)); rr.font.name="Calibri"; rr.font.size=Pt(11); rr.font.bold=True; rr.font.color.rgb=NAVY
    from shapes import contact_card_note
    cs.notes_slide.notes_text_frame.text=contact_card_note(contact)
    return cs

def complete_series(data):
    """Trim the monthly VIP series the slides COMPARE to their complete months, in place.

    Aaron, 2026-09-17: "Don't calculate YoY or comparisons on partial months, only use
    complete months." Slide 5 averages and peaks `performance_vs_goal`, slide 8 averages,
    totals and ranges `revenue.by_month`, and both charts colour the last bar as the
    latest month. Neither series has ended on a month in progress so far (the Sep 2026
    pulls end Jul 26 and May 26), but nothing held them to it. month_complete decides —
    a month that had not ended at the pull date, or one whose volume is below half its
    six-month median — and what it leaves out is returned for the notes, never dropped
    silently. The enrollments series keeps its own `partial_last` / `last_complete`
    handling, which VIP supplies.
    """
    import datetime
    import month_complete
    try:
        as_of = datetime.date.fromisoformat(str(data["meta"].get("data_pull") or "")[:10])
    except ValueError:
        as_of = None
    notes = {}
    for key, block, measure, value_key in (
            ("performance_vs_goal", data.get("performance_vs_goal"), "new checking accounts", "new_accounts"),
            ("revenue.by_month", (data.get("revenue") or {}).get("by_month"), "revenue", "revenue")):
        if not block or not block.get("months") or not block.get(value_key):
            continue
        months = block["months"]
        res = month_complete.assess(months, block[value_key], as_of, measure)
        if res["complete"] < len(months):
            n = len(months)
            for k, v in list(block.items()):
                if isinstance(v, list) and len(v) == n:
                    block[k] = v[:res["complete"]]
            notes[key] = month_complete.excluded_sentence(
                res, fmt=(lambda v: f"${v:,.0f}") if value_key == "revenue" else None)
    return notes


# ---- build -----------------------------------------------------------------
def build(data, template, out):
    m=data["meta"]; client=m["client_name"]; rm=m["report_month"]; hb=m["has_business"]
    _left_out=complete_series(data)
    # The Contact Us card is the client's managing CSM (Aaron, 2026-09-16) — resolved first,
    # so a client with no CSM on file stops before anything is rendered.
    import rpe_env
    contact=rpe_env.csm_contact(m["client_id"])
    assets=os.path.join(os.path.dirname(out) or ".","_mrpc_assets")
    CH.render_all(data, assets)
    A=lambda n: os.path.join(assets,n)

    prs=Presentation(template); S=list(prs.slides)

    # Slide 1 — title
    sub=txt_at(S[0], top=5.0)
    if sub: set_text(sub, f"{client} | Executive Review  •  {rm}")

    # Slide 3 — enrollments by month + tier callouts
    e=data["enrollments_by_month"]; lc=e["last_complete"]
    sh_sub=txt_at(S[2], top=1.12)
    if sh_sub:
        biz_txt=" and Business" if hb else ""
        set_text(sh_sub, f"Gold + Platinum (personal){biz_txt} enrollments by month, "
                         f"last {len(e['months'])} months ({e['months'][0]} – {e['months'][-1]})"
                         # Said only when it is so: VIP flags the running month, and a
                         # sheet pulled after the month closed has none (2026-09-17).
                         + (f"; {e['months'][-1]} is a partial month." if e.get("partial_last") else "."))
    swap(S[2], max(pics(S[2]), key=lambda p:p.width*p.height), A("mrpc_enroll.png"))
    boxes=sorted(autoshapes(S[2]), key=lambda sh: Emu(sh.top).inches)
    # boxes top->bottom: Gold, Platinum, Business
    # Tier palette (Aaron 2026-07-24): callouts MATCH the chart bars — Gold=orange,
    # Platinum=GRAY (steel), Business=NAVY. Platinum text goes navy for contrast.
    tiers=[("Gold", lc["gold"], ORANGE), ("Platinum", lc["platinum"], STEEL),
           ("Business", lc.get("business",0), NAVY)]
    for i,(name,val,color) in enumerate(tiers):
        if i>=len(boxes): break
        if name=="Business" and not hb:
            # remove the business callout entirely for consumer-only clients
            boxes[i]._element.getparent().remove(boxes[i]._element); continue
        set_fill(boxes[i], color)
        set_lines(boxes[i], [name, f"{val:,}", lc["label"]])
        if color==STEEL:                       # navy text on the gray Platinum card
            for _pa in boxes[i].text_frame.paragraphs:
                for _r in _pa.runs: _r.font.color.rgb=NAVY

    # Slide 4 — channel
    swap(S[3], max(pics(S[3]), key=lambda p:p.width*p.height), A("mrpc_channel.png"))

    # Slide 5 — performance vs goal
    p=data["performance_vs_goal"]
    # Resolved by CONTENT, not position. This looked for a box at top=6.7" with a
    # 0.15" tolerance; the caption sits at 6.40", so txt_at returned None, the
    # `if` fell through, and the caption was never swapped — silently. Every MRPC
    # deck ever shipped therefore carried the TEMPLATE's sentence, "averages ~55%
    # of goal, peaking at 72% in Feb 2026", identical for Austin, Ideal, Summit,
    # Capital and Marine alike. Geometry drifts; the words do not.
    sh_sub=txt_at(S[4], contains="New checking accounts")
    if sh_sub is None:
        raise SystemExit("slide 5: the enrollment-vs-goal caption was not found — "
                         "refusing to ship the template's sentence")
    # ...and the sentence is DERIVED. `penetration_summary` was read from the
    # client sheet with a '' default, and no sheet has ever carried that key, so
    # even a caption that swapped would have read "Enrollment penetration ."
    # `pct_of_goal` is the real per-month series and is always present.
    pog=p.get("pct_of_goal") or []
    months=p.get("months") or []
    if pog and months and len(pog)==len(months):
        i=max(range(len(pog)), key=lambda k: pog[k])
        pen=(f"averages {round(sum(pog)/len(pog))}% of goal, "
             f"peaking at {round(pog[i])}% in {months[i]}")
    else:
        raise SystemExit("slide 5: performance_vs_goal.pct_of_goal is missing or "
                         "does not line up with months — cannot state penetration")
    set_text(sh_sub, f"New checking accounts (bars) vs the {p['goal_pct']}% enrollment "
                     f"goal and actual enrollments. Enrollment penetration {pen}.")
    swap(S[4], max(pics(S[4]), key=lambda p2:p2.width*p2.height), A("mrpc_perf.png"))

    # Slide 6 — retention (left) + cancellations (right)
    ps=pics(S[5])
    left=min(ps, key=lambda p2:Emu(p2.left).inches); right=max(ps, key=lambda p2:Emu(p2.left).inches)
    swap(S[5], left,  A("mrpc_retention.png"))
    swap(S[5], right, A("mrpc_cancel.png"))

    rv=data["revenue"]
    ytd=next((a for a in rv["annual"] if "YTD" in a["year"]), None)

    # Slide 7 (S[6]) — Revenue by Year (annual). Yearly comes first, then the monthly slide.
    t=txt_at(S[6], top=0.28);  t and set_text(t, f"MRPC Revenue by Year to {client}")
    t=txt_at(S[6], top=1.88);  t and set_text(t, f"${rv['year_2025']:,}")
    t=txt_at(S[6], top=2.53);  t and set_text(t, f"2025 Revenue (~${rv.get('year_2025_monthly_avg',0):,}/mo)")
    t=txt_at(S[6], top=3.55);  t and set_text(t, f"${rv['life_of_program']:,}")
    t=txt_at(S[6], top=4.14);  t and set_text(t, "Life-of-Program Revenue")
    t=txt_at(S[6], top=4.95)
    if t:
        ytd_txt=f" {ytd['year']} is at ${ytd['amount']/1000:,.1f}K through {ytd.get('ytd_through','')}." if ytd else ""
        # "has grown" is tested against the annual series, not assumed. Capital
        # Bank 1502 peaked at $8.4K and has fallen for three years — their deck
        # still opened by telling them revenue had grown across the programme.
        _yrs=[a["amount"] for a in (rv.get("annual") or []) if "YTD" not in str(a.get("year",""))]
        _grew=len(_yrs) >= 2 and _yrs[-1] >= _yrs[-2]
        _lead=("Revenue has grown across the life of the program to"
               if _grew else "Life-of-program revenue reached")
        set_text(t, f"{_lead} "
                    f"${rv['year_2025']/1000:,.1f}K in 2025 — {_usd(rv['life_of_program'])} "
                    f"life-of-program.{ytd_txt}")
    _rp=max(pics(S[6]), key=lambda p2:p2.width*p2.height)
    place_pic(_rp, 0.4, 1.45, 7.55, 5.15)         # taller still (Aaron 2026-07-24); footnote sits below
    swap(S[6], _rp, A("mrpc_revenue.png"))
    t=txt_at(S[6], top=6.75)
    if t and ytd: set_text(t, f"* {ytd['year'].replace(' YTD','').strip()} is year-to-date through {ytd.get('ytd_through','')}.")

    # Slide 8 (S[7]) — Revenue by Month (after the yearly slide). Same cloned layout:
    # chart left, two tiles right (Avg Monthly, Trailing-12), narrative.
    bm=rv["by_month"]; bmv=bm["revenue"]; bm_avg=round(sum(bmv)/len(bmv)); bm_tot=round(sum(bmv))
    t=txt_at(S[7], top=0.28);  t and set_text(t, f"MRPC Revenue by Month to {client}")
    t=txt_at(S[7], top=1.88);  t and set_text(t, f"${bm_avg:,}")
    t=txt_at(S[7], top=2.53);  t and set_text(t, "Avg Monthly Revenue (12 mo)")
    t=txt_at(S[7], top=3.55);  t and set_text(t, f"${bm_tot:,}")
    t=txt_at(S[7], top=4.14);  t and set_text(t, "Trailing-12 Revenue")
    t=txt_at(S[7], top=4.95)
    # "has held around" is a claim of stability and is only made when the series
    # is actually stable. Capital Bank 1502 swings +/-15% around its mean and was
    # still told its revenue "held around" the average.
    _spread=(max(max(bmv)-bm_avg, bm_avg-min(bmv))/bm_avg*100) if bm_avg else 0
    # One decimal, matching the range beside it. At ,.0f a $669 average printed
    # as "$1K" next to a "$0.6K-$0.7K" range — an average outside its own range.
    _rev_txt=(f"Monthly MRPC revenue has held around ${bm_avg/1000:,.1f}K"
              if _spread <= 10 else
              f"Monthly MRPC revenue has averaged ${bm_avg/1000:,.1f}K")
    if t: set_text(t, f"{_rev_txt}, "
                      f"ranging ${min(bmv)/1000:,.1f}K–${max(bmv)/1000:,.1f}K over {bm['months'][0]} – {bm['months'][-1]}.")
    t=txt_at(S[7], top=6.75);  t and set_text(t, f"* Monthly revenue to {client}, {bm['months'][0]} – {bm['months'][-1]}.")
    _rp7=max(pics(S[7]), key=lambda p2:p2.width*p2.height)
    place_pic(_rp7, 0.4, 1.45, 7.55, 5.15)
    swap(S[7], _rp7, A("mrpc_revmonth.png"))

    # Slide 9 (S[8]) — Card Portfolio (NEW). Cloned from Key Metrics: 3 top tiles + big
    # box (right) + chart slot (left). Pie replaces the chart; tiles/box repurposed.
    b=data["card_billing"]; tot=b["total_accounts"]; mbill=b["monthly_billing"]
    plat=next((c for c in CH.card_types(b) if c["name"]=="Platinum"), None)
    plat_share=round(plat["accounts"]/tot*100,1) if plat else 0
    cross=round(b["multi_card_accounts"]/tot*100,1)
    avg_fee=mbill/tot
    t=txt_at(S[8], top=0.28);  t and set_text(t, "MRPC Card Portfolio")
    t=txt_at(S[8], top=1.91, left=0.8);  t and set_text(t, f"{tot:,}")
    t=txt_at(S[8], top=2.62, left=0.8);  t and set_text(t, "Total Cards Billed")
    t=txt_at(S[8], top=1.91, left=4.93); t and set_text(t, f"${mbill/1000:,.0f}K")
    t=txt_at(S[8], top=2.62, left=4.93); t and set_text(t, "Monthly Card Billing")
    t=txt_at(S[8], top=1.91, left=9.06); t and set_text(t, f"${avg_fee:,.2f}")
    t=txt_at(S[8], top=2.62, left=9.06); t and set_text(t, "Avg Fee per Account")
    t=txt_at(S[8], top=3.95); t and set_text(t, f"{plat_share:.0f}%")
    t=txt_at(S[8], top=4.95); t and set_text(t, "Platinum Share")
    # Which card leads, and at what price, are FOUND — both were hardcoded as
    # "Platinum ($14.95/mo)". The price is per client in card_billing.prices, and
    # the leader is whichever type holds the most accounts: a client whose Gold or
    # Business Platinum book overtook Platinum would have been told otherwise.
    _types=sorted(CH.card_types(b), key=lambda c: c["accounts"], reverse=True)
    _lead=_types[0] if _types else None
    _price=(b.get("prices") or {}).get(_lead["name"]) if _lead else None
    _lead_txt=(f"{_lead['name']} (${_price:,.2f}/mo) is the most-held card"
               if _lead and _price else
               f"{_lead['name']} is the most-held card" if _lead else
               "Card mix is shown at right")
    t=txt_at(S[8], top=5.5);  t and set_text(t, f"{_lead_txt}; "
                                                f"{cross:.1f}% of accounts hold more than one card.")
    for sh in list(autoshapes(S[8])):              # billing pie is NOT in a callout — free the space
        try: fh=str(sh.fill.fore_color.rgb).upper()
        except Exception: fh=""
        if fh in ("ECF0F4","F2F5F8"): sh._element.getparent().remove(sh._element)
    cardpic=max(pics(S[8]), key=lambda p2:p2.width*p2.height)
    place_pic(cardpic, 0.3, 3.42, 6.5, 2.82)       # below the tiles (3.3) and clear of the Platinum card (6.95)
    swap(S[8], cardpic, A("mrpc_cardpie.png"))

    # Slide 10 (S[9]) — Key Metrics. Active Enrollments is the LARGE callout; PTD upper-
    # right. Card billing has moved to its own slide; the freed lower-left now carries a
    # cross-sale callout.
    k=data["key_metrics"]
    t=txt_at(S[9], top=1.91, left=0.8);  t and set_text(t, f"${k['avg_monthly_revenue']:,}")
    t=txt_at(S[9], top=1.91, left=4.93); t and set_text(t, f"{k['enrollments_trailing_12']:,}")
    t=txt_at(S[9], top=1.91, left=9.06); t and set_text(t, f"{k['ptd_total']:,}")
    t=txt_at(S[9], top=2.62, left=9.06); t and set_text(t, "Enrollments, Program-to-Date")
    t=txt_at(S[9], top=3.95); t and set_text(t, f"{k['active_enrollments']:,}")
    t=txt_at(S[9], top=4.95); t and set_text(t, "Active Enrollments")
    t=txt_at(S[9], top=5.5);  t and set_text(t, "Members currently active in the MRPC program.")
    # remove the old billing chart (+ its light backdrop) and add the cross-sale callout
    for pic in list(pics(S[9])): pic._element.getparent().remove(pic._element)
    for sh in list(autoshapes(S[9])):
        try: fh=str(sh.fill.fore_color.rgb).upper()
        except Exception: fh=""
        if fh=="ECF0F4": sh._element.getparent().remove(sh._element)   # billing backdrop
    # Tier Mix (Program to Date) — dynamic rows (some clients have 3 tiers, some more);
    # font scales to fill the callout (Aaron 2026-07-24). Cross-sale rides as the footer line.
    _ct=CH.card_types(data["card_billing"]); _tt=sum(c["accounts"] for c in _ct) or 1
    _rows=[f"{c['name']} — {c['accounts']:,} ({c['accounts']/_tt*100:.0f}%)" for c in _ct]
    _n=len(_rows)
    # refresh: remove any baked Tier Mix content from the template first (idempotent)
    from pptx.util import Emu as _E
    for _sh in list(S[9].shapes):
        _tx=_sh.text_frame.text if _sh.has_text_frame else ""
        _isnavycard=(_sh.shape_type==1 and _sh.left is not None and abs(_E(_sh.left).inches-0.7)<0.05
                     and _sh.top is not None and abs(_E(_sh.top).inches-3.65)<0.05)
        if ("Tier Mix (Program to Date)" in _tx) or ("Cross-sale:" in _tx) or _isnavycard or ("— " in _tx and "%" in _tx and _sh.left is not None and _E(_sh.left).inches<6.5 and _sh.top is not None and _E(_sh.top).inches>4.0):
            _sh._element.getparent().remove(_sh._element)
    # navy card drawn manually: label (top) / tier rows (middle, dynamic size) / cross-sale (bottom)
    from pptx.util import Inches as _I, Pt as _P
    from pptx.dml.color import RGBColor as _RC
    from pptx.enum.shapes import MSO_SHAPE as _MS
    from pptx.enum.text import PP_ALIGN as _AL
    _NV=_RC(0x00,0x27,0x4C); _WH=_RC(0xFF,0xFF,0xFF); _OR=_RC(0xF4,0x7A,0x29)
    _card=S[9].shapes.add_shape(_MS.ROUNDED_RECTANGLE,_I(0.7),_I(3.65),_I(6.0),_I(2.65))
    _card.fill.solid(); _card.fill.fore_color.rgb=_NV; _card.line.fill.background()
    try: _card.adjustments[0]=0.05
    except Exception: pass
    add_shadow(_card)
    def _wtb(x,y,w,h,txt,sz,col,bold,align=_AL.LEFT):
        b=S[9].shapes.add_textbox(_I(x),_I(y),_I(w),_I(h)); tf=b.text_frame; tf.word_wrap=True
        pa=tf.paragraphs[0]; pa.alignment=align; r=pa.add_run(); r.text=txt
        r.font.size=_P(sz); r.font.bold=bold; r.font.name="Montserrat"; r.font.color.rgb=col
        return b,tf
    _wtb(1.0,3.78,5.4,0.4,"Tier Mix (Program to Date)",14,_OR,True)
    _avail=1.45
    _fs=int(min(18, max(11, (_avail/_n)*72*0.62)))   # dynamic: fill the rows area, floor 11pt
    _b,_tf=_wtb(1.0,4.22,5.4,_avail,_rows[0],_fs,_WH,True)
    for _r in _rows[1:]:
        _pa=_tf.add_paragraph(); _rn=_pa.add_run(); _rn.text=_r
        _rn.font.size=_P(_fs); _rn.font.bold=True; _rn.font.name="Montserrat"; _rn.font.color.rgb=_WH
    _wtb(1.0,5.82,5.4,0.4,f"Cross-sale: {cross:.1f}% of accounts hold more than one card.",11,_RC(0xCF,0xDB,0xE8),False)

    # Slide 11 (S[10]) — closing
    sub=txt_at(S[10], top=5.1)
    if sub: set_text(sub, f"{client}  •  {rm}")

    # ---- date callout: orange "As of {rm}" pill, top-right of every content slide ----
    # (STYLE.md: reporting month = generation month). Reuses the template pill on the
    # Card Portfolio / Key Metrics slides; creates a matching one on the others.
    for _i in (2, 3, 4, 5, 6, 7, 8, 9):
        date_pill(S[_i], f"As of {rm}")

    # ---- speaker notes ----
    src=m.get("source","VIP MyRewards Premium Cards dashboards")
    pull=m.get("data_pull","")
    base=f"Source — {src} for {client} ({m['client_id']}), pulled {pull}."
    set_notes(S[0], "Title slide. No data.")
    set_notes(S[1], "Section divider (MyRewards Premium Cards®). No data.")
    set_notes(S[2], base+f" Enrollments by month, tiers {'Gold/Platinum/Business' if hb else 'Gold/Platinum'}; "
                        f"callout = {lc['label']} (last complete month)"
                        + (f"; {e['months'][-1]} partial. " if e.get("partial_last") else ". ")
                        +
                        f"{'Monthly tier split apportioned from the last-complete-month ratio pending exact VIP tiers. ' if e.get('tier_split_approx') else ''}"
                        f"Selection: enrollments by month, last {len(e['months'])} months.")
    set_notes(S[3], base+f" Enrollments by channel, program-to-date: "
                        + " / ".join(f"{kk} {vv}%" for kk,vv in data['channel']['pct'].items())+".")
    set_notes(S[4], base+f" Enrollment performance vs the {p['goal_pct']}% goal, "
                        f"{len(p['months'])} months ({p['months'][0]} – {p['months'][-1]}). Bars navy, last month orange. "
                        f"{'New-checking bars seeded/derived pending exact VIP values. ' if p.get('new_checking_approx') else ''}"
                        "Selection: new checking accounts vs. goal and actual enrollments."
                        + (" " + _left_out["performance_vs_goal"] if _left_out.get("performance_vs_goal") else ""))
    set_notes(S[5], base+" Retention by enrollment-cohort month + cancellations by reason. Bars navy, last cohort orange. "
                        f"{'Still-active line seeded/approx pending exact VIP values. ' if data['retention'].get('still_active_approx') else ''}"
                        "Selection: enrolled members by cohort month, with count still active now.")
    set_notes(S[6], base+f" Revenue by year 2016–{ytd['year'] if ytd else ''}; 2025 ${rv['year_2025']:,}, "
                        f"life-of-program ${rv['life_of_program']:,}"+(f", {ytd['year']} ${ytd['amount']:,}" if ytd else "")+
                        ". Full annual series pulled from VIP; sums to life-of-program.")
    set_notes(S[7], base+f" Revenue by month (VIP MRPC Revenue by Month), {bm['months'][0]} – {bm['months'][-1]}; "
                        f"avg ${bm_avg:,}/mo, trailing-12 ${bm_tot:,}. Bars navy, last month orange."
                        + (" " + _left_out["revenue.by_month"] if _left_out.get("revenue.by_month") else ""))
    set_notes(S[8], base+f" Card portfolio by type: Platinum ($14.95/mo), Gold ($9.95/mo), Business Platinum "
                        f"($19.95/mo), and Multiple Cards (accounts with >1 card). Total {tot:,} cards, "
                        f"monthly billing ${mbill:,.2f}, cross-sale {cross:.1f}%. Fee tiers above the three base "
                        "prices are multi-card accounts.")
    set_notes(S[9], base+f" Key metrics: avg monthly revenue ${k['avg_monthly_revenue']:,}; trailing-12 "
                        f"{k['enrollments_trailing_12']:,}; active {k['active_enrollments']:,}; PTD "
                        f"{k['ptd_total']:,}{' (VERIFY)' if k.get('ptd_total_verify') else ''}; cross-sale {cross:.1f}%.")
    set_notes(S[10], "Discussion slide. No data.")

    # ---- callout polish: clear baked-in tile text, then a UNIFORM shadow on every callout ----
    def _fill_hex(sh):
        try: return str(sh.fill.fore_color.rgb).upper()
        except Exception: return ""
    for si in (6, 7):                                                        # revenue slides: numbers live in overlay boxes
        for sh in autoshapes(S[si]):
            if Emu(sh.top).inches < 1.0: continue
            if _fill_hex(sh) == "ECF0F4": continue
            if sh.has_text_frame and sh.text_frame.text.strip():
                for pp in sh.text_frame.paragraphs:
                    for r in pp.runs: r.text = ""
    # universal drop shadow: every solid-filled callout/tile/pill on every slide
    # (skip white logo boxes and the light ECF0F4 backdrop panels)
    for _s in prs.slides:
        for sh in _s.shapes:
            if sh.shape_type != 1: continue
            if _fill_hex(sh) in ("FFFFFF", "ECF0F4", ""): continue
            try:
                if sh.fill.type is not None and sh.fill.fore_color is not None and sh.fill.fore_color.type is not None:
                    add_shadow(sh)
            except Exception: pass
    # ---- spacing: on full-width-chart slides, keep the bottom caption clear of the page number
    # + logo, and shrink the chart so it doesn't crowd the caption (STYLE.md) ----
    for _s in prs.slides:
        _fc = [sh for sh in _s.shapes if sh.shape_type == 13 and sh.width is not None and Emu(sh.width).inches > 10]
        if not _fc: continue
        _ch = _fc[0]
        _caps = [sh for sh in _s.shapes if sh.has_text_frame and sh.top is not None and sh.left is not None
                 and sh.width is not None and Emu(sh.top).inches > 5.8 and Emu(sh.left).inches < 3
                 and Emu(sh.width).inches > 4 and not sh.text_frame.text.strip().isdigit()]
        for sh in _caps:
            _l = Emu(sh.left).inches
            if Emu(sh.top).inches > 6.45: sh.top = Inches(6.4)               # lift a 2-line caption above the page number
            if _l + Emu(sh.width).inches > 11.05: sh.width = Inches(11.05 - _l)  # clear the logo
        if _caps:
            _capt = min(Emu(sh.top).inches for sh in _caps)
            if Emu(_ch.top).inches + Emu(_ch.height).inches > _capt - 0.1:
                _ch.height = Inches(max(3.5, (_capt - 0.2) - Emu(_ch.top).inches))


    add_contact_slide(prs, contact)   # Contact Us at the very end: the managing CSM
    summit_slide.insert_summit_after_title(prs)   # Executive Summit after the title (all decks)
    renumber_pages(prs)
    restyle_fonts(prs)   # size floor only; names/skips handled by build/restyle_fonts.py post-processor
    # Per-title geometry contract, before fit_layout — the same call ARS makes.
    # No title in this deck carries a rule yet, so today this is a no-op; it is
    # wired now so the next layout fix lands in the contract instead of in one
    # deck (CLAUDE.md rule 2).
    import slide_geometry; slide_geometry.apply(prs)
    import fit_layout; fit_layout.fit(prs)   # clear number/logo, clamp off-slide (shared)
    prs.save(out)
    print("built", out, "->", len(prs.slides._sldIdLst), "slides")

def restyle_fonts(prs, minpt=10):
    """Legibility floor only — bump any explicit run size below minpt up to minpt.
    The MRPC template carries a deliberate 10-15 pt hierarchy (footnotes 11, tier
    sublabels 10, KPI labels 13-14, panel headings 15, date pill 12); flooring at 16
    would flatten that and collide the bottom captions with the page number, so the
    floor is set at 10 and the template's sizes are preserved. Font *names* are set by
    role afterward by the shared build/restyle_fonts.py post-processor (headings +
    callouts = Montserrat; subheadings, body, tables = Calibri)."""
    def _fix(tf):
        for p in tf.paragraphs:
            for r in p.runs:
                if r.font.size is not None and r.font.size.pt < minpt: r.font.size = Pt(minpt)
    for s in prs.slides:
        if any(sh.has_text_frame and ("Executive Summit" in sh.text_frame.text
               or "About the Summit" in sh.text_frame.text) for sh in s.shapes):
            continue
        for sh in s.shapes:
            if sh.has_text_frame: _fix(sh.text_frame)

if __name__ == "__main__":
    # See build_ics_gen: a literal path still works; a bare `1075` or
    # `1075_mrpc.json` resolves under RPE_DATA_ROOT/Inputs/VIP Data/ first,
    # then the repo's data/ folder.
    from rpe_env import resolve_client_json
    build(json.load(open(resolve_client_json(sys.argv[1], "mrpc"), encoding="utf-8")),
          sys.argv[2], sys.argv[3])
