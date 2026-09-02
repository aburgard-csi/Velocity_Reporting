"""Shared layout-fit pass (all programs) — run by every builder right before
prs.save(), AFTER slide_geometry.apply() and BEFORE the final numbering pass.

0. Full-bleed slides (dividers, covers) lose their slide number; empty layout
   placeholders ("Click to add title") are stripped everywhere.
1. Slide numbers -> Calibri 10 pt bold navy (STYLE.md "Slide numbers").
2. Caption breathing room: a text box starting below 5.5" is moved so its
   ESTIMATED glyph lines (0.105"/char, 0.26"/line) finish above the number band
   at 7.00"; any chart it now touches is shortened to clear it.
3. Pictures are scaled down onto the slide (right edge 13.30") and clear of the
   number/logo zones.
4. Bottom footnotes wider than 4" are narrowed sideways off the number (left) and
   logo (right); narrower ones are lifted above the zone.
Skips the Executive Summit slide. validate_deck.geometry_findings FAILs anything
this pass leaves behind."""
import math
from pptx.util import Emu, Inches, Pt
from pptx.dml.color import RGBColor

def _in(v): return Emu(v).inches if v is not None else None
def _b4(sh):
    l,t,w,h=_in(sh.left),_in(sh.top),_in(sh.width),_in(sh.height)
    return None if None in (l,t,w,h) else (l,t,l+w,t+h)
def _is_num(sh):
    if not (sh.has_text_frame and sh.text_frame.text.strip().isdigit()): return False
    b=_b4(sh); return bool(b) and b[1]>6.5 and b[0]<1.7 and (b[2]-b[0])<1.4
def _is_logo(sh):
    if sh.shape_type!=13: return False
    b=_b4(sh); return bool(b) and (b[2]-b[0])<3.15 and (b[3]-b[1])<1.2
def _is_summit(s):
    t=" ".join(sh.text_frame.text for sh in s.shapes if sh.has_text_frame)
    return "Executive Summit" in t or "About the Summit" in t
def _ov(a,b,pad=0.05):
    return (min(a[2],b[2])-max(a[0],b[0]))>pad and (min(a[3],b[3])-max(a[1],b[1]))>pad

def fit(prs):
    for s in prs.slides:
        if _is_summit(s): continue
        # dividers/covers (full-bleed background) carry NO slide number (STYLE.md)
        _fullbleed=any(sh.shape_type==1 and (_in(sh.width) or 0)>12.5 and (_in(sh.height) or 0)>6.5
                       for sh in s.shapes)
        if _fullbleed:
            for sh in list(s.shapes):
                if _is_num(sh): sh._element.getparent().remove(sh._element)
        # strip empty layout placeholders (PowerPoint 'click to add' prompt boxes)
        try:
            for ph in list(s.placeholders):
                if not (ph.has_text_frame and ph.text_frame.text.strip()):
                    ph._element.getparent().remove(ph._element)
        except Exception:
            pass
        # 1. slide numbers 10pt
        for sh in s.shapes:
            if _is_num(sh):
                for pa in sh.text_frame.paragraphs:
                    for r in pa.runs:
                        r.font.name="Calibri"; r.font.size=Pt(10); r.font.bold=True
                        r.font.color.rgb=RGBColor(0x00,0x27,0x4C)
        numB=[_b4(sh) for sh in s.shapes if _is_num(sh)]
        logoB=[_b4(sh) for sh in s.shapes if _is_logo(sh)]
        zones=[z for z in numB+logoB if z]
        numR=max((z[2] for z in numB if z), default=None)
        logoL=min((z[0] for z in logoB if z), default=None)
        # 2. caption breathing room (text only)
        for sh in list(s.shapes):
            if _is_num(sh) or _is_logo(sh): continue
            if not (sh.has_text_frame and sh.text_frame.text.strip()): continue
            b=_b4(sh)
            if not b or b[1]<5.5: continue
            txt=sh.text_frame.text.strip(); wdt=max(0.5,b[2]-b[0])
            lines=max(1,math.ceil(len(txt)*0.105/wdt))
            need_top=round(7.00-0.08-0.26*lines,2)
            if b[1]>need_top:
                nt=max(4.5,need_top)
                sh.top=Inches(nt); sh.height=Inches(round(0.10+0.26*lines,2))
                nb=(b[0],nt,b[2],nt+0.10+0.26*lines)
                for ch in s.shapes:
                    if ch.shape_type==13 and not _is_logo(ch):
                        cb=_b4(ch)
                        if cb and _ov(nb,cb,pad=0.02) and (cb[2]-cb[0])>3.0:
                            ch.height=Inches(round(max(1.0,nt-0.06-cb[1]),2))
        # 3. clamp pictures onto the slide / clear of number+logo band
        for sh in list(s.shapes):
            if sh.shape_type!=13 or _is_logo(sh): continue
            b=_b4(sh)
            if not b: continue
            l,t=b[0],b[1]; w=b[2]-b[0]; h=b[3]-b[1]; r=b[2]; bot=b[3]
            tgt=7.4
            for z in zones:
                if _ov(b,z): tgt=min(tgt,z[1]-0.10)
            sc=1.0
            if bot>tgt and h>0: sc=min(sc,(tgt-t)/h)
            if r>13.35 and w>0: sc=min(sc,(13.3-l)/w)
            if 0<sc<1:
                sh.width=Inches(round(w*sc,2)); sh.height=Inches(round(h*sc,2))
        # 4. wide bottom footnotes: clear number (left) / logo (right) sideways
        for sh in list(s.shapes):
            if _is_num(sh) or _is_logo(sh): continue
            if not (sh.has_text_frame and sh.text_frame.text.strip()): continue
            b=_b4(sh)
            if not b: continue
            hits=[z for z in zones if _ov(b,z)]
            if not hits: continue
            l,t,r,bot=b; w=r-l; h=bot-t
            if w>4:
                nl,nr=l,r
                if numR and l<numR+0.25: nl=numR+0.30
                if logoL and r>logoL-0.10: nr=logoL-0.15
                if (nr-nl)>=2.0:
                    sh.left=Inches(round(nl,2)); sh.width=Inches(round(nr-nl,2))
                    b=(nl,t,nr,bot)
                rem=[z for z in zones if _ov(b,z)]
                if rem:
                    zt=min(z[1] for z in rem); sh.top=Inches(round(max(0.2,zt-0.05-h),2))
            else:
                zt=min(z[1] for z in hits); sh.top=Inches(round(max(0.2,zt-0.05-h),2))
    return prs

if __name__=="__main__":
    import sys
    from pptx import Presentation
    for p in sys.argv[1:]:
        prs=Presentation(p); fit(prs); prs.save(p); print("fit_layout ->",p)
