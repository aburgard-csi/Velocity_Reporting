"""Per-slide geometry contract (by TITLE, not slide number).

Promoted from ars_pipeline/ to build/ so ICS and MRPC can adopt the same
contract. CLAUDE.md rule 2 says layout defects are fixed in the geometry
contract, never by hand-editing a deck — but only ARS had a contract to fix,
which is why ICS and MRPC layout fixes kept landing as one-off per-deck commits.
Applied by ALL THREE builders before fit_layout, and runnable standalone:
    python3 slide_geometry.py <deck.pptx>

Rules are keyed on the slide TITLE, so a deck simply skips the ones it has no
slide for. Every title with a rule today is an ARS title, which is why calling
apply() on an ICS or MRPC deck currently changes nothing — verified, not assumed.
That is the point: the seam is wired into all three builders now, so the NEXT
ICS or MRPC layout fix has somewhere to go. Before this, only ARS had a contract,
and ICS/MRPC layout defects kept landing as one-off per-deck commits (8970e17
ICS Financial Summary labels wrapping onto their values; ba3a300; 11d16df) —
exactly what CLAUDE.md rule 2 forbids.

Adding an ICS or MRPC rule: match on its title in apply() alongside the ARS
blocks. Do NOT start a second module — one contract, or the rule that says
"fix the contract, never the deck" has two places to be fixed.

Titles carrying a rule today (all ARS, Aaron 2026-07-24), in the order apply() tests them:
  Overall Debit Swipes / NSF/OD Activity ... chart taller, never wider than the tile rail
  12-Month Eligible Take Rate ............ chart and caption centered on the slide
  Product Mix ............................ source line bottom-center
  Reg E Opt-In (not Vintage) ............. donut <= 2.85" ending 4.45", legend rows from 4.60",
                                           caption at 5.85"
  Reg E Opt-In by Account Vintage /
  First-Year Closure / ARS Response Movement  chart top >= 1.75" (below the 2-line subtitle)
  Transaction Increase ................... caption (1.45, 6.02, 8.4 x 0.95); chart <= 4.1" tall,
                                           centered between subtitle and caption
  Who Responds ........................... caption starts below the chart bottom
  Program Reach .......................... chart (1.2, 1.8, 8.3 x 4.58)
  Account Growth / Account Retention ..... chart (1.0, 1.75, 8.4 x 4.38)
STYLE.md "Per-slide geometry contract" is the human-readable copy of this list."""
from pptx.util import Emu, Inches
from pptx.enum.shapes import MSO_SHAPE_TYPE
def _in(v): return Emu(v).inches if v is not None else None
def _title(sl):
    for sh in sl.shapes:
        if sh.has_text_frame and sh.text_frame.text.strip():
            return sh.text_frame.text.strip().split("\n")[0]
    return ""
def _pics(sl,minw=3.0):
    return [sh for sh in sl.shapes if sh.shape_type==MSO_SHAPE_TYPE.PICTURE
            and (_in(sh.width) or 0)>minw]
def apply(prs):
    for sl in prs.slides:
        t=_title(sl)
        if t.startswith(("Overall Debit Swipes","NSF/OD Activity")):
            # taller charts but NEVER wider than the tile rail; height from the image's
            # NATIVE aspect so nothing stretches (Aaron 2026-07-24: "taller, not wider")
            rail=[_in(sh.left) for sh in sl.shapes if sh.shape_type==1
                  and (_in(sh.left) or 0)>8 and (_in(sh.width) or 9)<4.5]
            tileL=min(rail) if rail else 9.6
            for sh in _pics(sl):
                try:
                    iw,ih=sh.image.size; asp=iw/ih
                except Exception:
                    w=_in(sh.width); h=_in(sh.height); asp=(w/h) if w and h else 1.73
                nw=round(tileL-0.25-0.6,2); nh=round(nw/asp,2)
                if nh>5.35: nh=5.35; nw=round(nh*asp,2)
                sh.left=Inches(0.6); sh.top=Inches(1.6)
                sh.width=Inches(nw); sh.height=Inches(nh)
        if t.startswith("12-Month Eligible Take Rate"):
            # chart + caption centered on the slide (Aaron 2026-07-24)
            from pptx.enum.text import PP_ALIGN as _PAL
            for sh in _pics(sl):
                w=_in(sh.width)
                if w: sh.left=Inches(round((13.333-w)/2,2))
            for sh in sl.shapes:
                if sh.has_text_frame and sh.text_frame.text.strip().startswith("Take rate by branch"):
                    sh.left=Inches(2.32); sh.width=Inches(8.7)
                    for pa in sh.text_frame.paragraphs: pa.alignment=_PAL.CENTER
        if t.startswith("Product Mix"):
            # source line bottom-center (Aaron 2026-07-24)
            from pptx.enum.text import PP_ALIGN as _PAL2
            for sh in sl.shapes:
                if sh.has_text_frame and sh.text_frame.text.strip().lower().startswith("source:"):
                    sh.left=Inches(0.5); sh.top=Inches(7.02); sh.width=Inches(12.33); sh.height=Inches(0.32)
                    for pa in sh.text_frame.paragraphs: pa.alignment=_PAL2.CENTER
        if t.startswith("Reg E Opt-In") and "Vintage" not in t:
            # left column stacks: donut (<=2.85, ends 4.45) -> legend rows -> caption (Aaron 2026-07-24)
            for sh in _pics(sl,minw=2.5):
                w=_in(sh.width); h=_in(sh.height)
                if w and h and abs(w-h)<0.2 and w>2.4:      # the square donut
                    sc=2.45/w
                    sh.width=Inches(2.45); sh.height=Inches(round(h*sc,2))
            rows=[sh for sh in sl.shapes if sh.has_text_frame and sh.text_frame.text.strip() in
                  ("Opted In","Opted Out","No Election (default)")]
            rows.sort(key=lambda x:_in(x.top) or 9)
            for j,sh in enumerate(rows):
                dy=(_in(sh.top) or 0)
                sh.top=Inches(round(4.22+j*0.36,2))
            chips=[sh for sh in sl.shapes if sh.shape_type==1 and (_in(sh.width) or 9)<0.5
                   and (_in(sh.left) or 9)<2.0 and 4.2<(_in(sh.top) or 0)<6.6]
            chips.sort(key=lambda x:_in(x.top) or 9)
            for j,sh in enumerate(chips[:3]):
                sh.top=Inches(round(4.24+j*0.36,2))
            for sh in sl.shapes:
                if sh.has_text_frame and (_in(sh.left) or 9)<1.5 and sh.text_frame.text.strip()[:1].isdigit():
                    pass
            for sh in sl.shapes:
                tx=sh.text_frame.text.strip() if sh.has_text_frame else ""
                if tx and (_in(sh.left) or 9)<1.6 and (_in(sh.top) or 0)>5.0 and len(tx)>40:
                    # The sentence needs FOUR lines at 16pt in this 3.75" column
                    # since the wording changed to "elected to extend their
                    # overdraft access to the debit card" (Aaron, 2026-09-10), and
                    # 1.10" holds three — the gate failed the build rather than
                    # letting it wrap into the page number. The donut gives up
                    # 0.40" and the legend moves up with it; nothing is shrunk
                    # below the 16pt floor.
                    sh.top=Inches(5.35); sh.height=Inches(1.60)
            # RIGHT COLUMN: the branch chart runs the height of the left stack
            # (Aaron, 2026-09-10). The template box was 3.40" tall ending at 5.35,
            # which left ~1.4" of empty slide under the caption while the chart
            # itself was squeezed — twelve bars and a rate line in half the space
            # the donut column uses. Taller box, caption follows it down. The
            # renderer's DIM must match this aspect or the PNG stretches
            # (CLAUDE.md rule 2): 7.60 x 4.50 -> charts_gen DIM 1520 x 900.
            for sh in _pics(sl, minw=6.0):
                sh.left=Inches(4.40); sh.top=Inches(1.60)
                sh.width=Inches(7.60); sh.height=Inches(4.50)
            for sh in sl.shapes:
                if sh.has_text_frame and (_in(sh.left) or 0)>4.0                    and sh.text_frame.text.strip().lower().startswith("opt-in rate by branch"):
                    sh.left=Inches(4.68); sh.top=Inches(6.22); sh.width=Inches(7.2)
        if t.startswith(("Reg E Opt-In by Account Vintage","First-Year Closure")) or ("ARS Response" in t and "Movement" in t):
            # chart starts below the 2-line selection subtitle (bottom 1.57)
            for sh in _pics(sl):
                tp=_in(sh.top)
                if tp is not None and tp<1.72:
                    bot=tp+(_in(sh.height) or 0)
                    sh.top=Inches(1.75); sh.height=Inches(round(max(1.0,bot-1.75),2))
        if t.startswith("Transaction Increase"):
            # caption needs 3 lines at 16pt: box (1.45, 6.10, 9.7 x 0.85) ends 0.10" above the number
            for sh in sl.shapes:
                if sh.has_text_frame and sh.text_frame.text.strip().startswith("Responders don"):
                    sh.left=Inches(1.45); sh.top=Inches(6.02); sh.width=Inches(8.4); sh.height=Inches(0.95)   # stops before the right-rail tiles (10.0")
            for sh in _pics(sl):
                tp=_in(sh.top); h=_in(sh.height)
                if tp is None or not h: continue
                if h>4.1: h=4.1; sh.height=Inches(4.1)
                sh.top=Inches(round(1.68+(6.02-0.06-1.68-h)/2,2))   # centered between subtitle and caption
        if t.startswith("Who Responds"):
            ch=_pics(sl); cb=max(((_in(x.top) or 0)+(_in(x.height) or 0)) for x in ch) if ch else 6.3
            for sh in sl.shapes:
                if sh.has_text_frame and sh.text_frame.text.strip().startswith("Responders carry"):
                    sh.top=Inches(round(cb+0.08,2))
        if t.startswith("Program Reach"):
            for sh in _pics(sl):
                sh.left=Inches(1.2); sh.top=Inches(1.8); sh.width=Inches(8.3); sh.height=Inches(4.58)
        if t.startswith(("Account Growth","Account Retention")):
            for sh in _pics(sl):
                sh.left=Inches(1.0); sh.top=Inches(1.75); sh.width=Inches(8.4); sh.height=Inches(4.38)
    return prs
if __name__=="__main__":
    import sys
    from pptx import Presentation
    for p in sys.argv[1:]:
        prs=Presentation(p); apply(prs); prs.save(p); print("slide_geometry ->",p)
