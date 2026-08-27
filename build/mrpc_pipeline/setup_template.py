#!/usr/bin/env python3
"""One-off: expand the 9-slide MRPC template to 11 slides by cloning two slides.

- Clone the annual-revenue slide -> insert a "Revenue by Month" slide before it.
- Clone the key-metrics slide   -> insert a "Card Billing" slide before it.

The clones inherit all styling (title box, logo, page number, tiles, chart slot);
the build script (build_mrpc_gen.py) fills their content. Run once to (re)generate
mrpc_template.pptx; safe to re-run from the 9-slide base.

    python3 setup_template.py <in_9slide.pptx> <out_template.pptx>
"""
import sys, copy
from pptx import Presentation
from pptx.oxml.ns import qn
from pptx.opc.constants import RELATIONSHIP_TYPE as RT

SHAPE_TAGS={qn('p:sp'),qn('p:pic'),qn('p:graphicFrame'),qn('p:grpSp'),qn('p:cxnSp')}

def clone_slide(prs, src_idx, dest_idx):
    src=prs.slides[src_idx]
    new=prs.slides.add_slide(src.slide_layout)
    for sh in list(new.shapes):            # drop placeholders add_slide created
        sh._element.getparent().remove(sh._element)
    tree=new.shapes._spTree
    for el in src.shapes._spTree:
        if el.tag in SHAPE_TAGS:
            tree.append(copy.deepcopy(el))
    # rewire image relationships (blips) to this slide's part
    for blip in tree.iter(qn('a:blip')):
        rId=blip.get(qn('r:embed'))
        if not rId: continue
        target=src.part.rels[rId].target_part
        blip.set(qn('r:embed'), new.part.relate_to(target, RT.IMAGE))
    # move the new sldId (appended last) to dest position
    lst=prs.slides._sldIdLst
    sid=list(lst)[-1]; lst.remove(sid); lst.insert(dest_idx, sid)
    return new

def title_of(s):
    for sh in s.shapes:
        if sh.has_text_frame and sh.text_frame.text.strip():
            return sh.text_frame.text.strip().split("\n")[0]
    return ""

def renumber(prs):
    # page-number box = the small text box at bottom-left (L~0.45, T~7.04) holding a number
    from pptx.util import Emu
    n=0
    for s in prs.slides:
        n+=1
        for sh in s.shapes:
            if sh.has_text_frame and sh.left is not None and sh.top is not None:
                if abs(Emu(sh.left).inches-0.45)<0.2 and abs(Emu(sh.top).inches-7.04)<0.2:
                    t=sh.text_frame.text.strip()
                    if t.isdigit():
                        sh.text_frame.paragraphs[0].runs[0].text=str(n)

def main(src, out):
    prs=Presentation(src)
    idx=lambda pred: next(i for i,s in enumerate(prs.slides) if pred(title_of(s)))
    rev=idx(lambda t: t.startswith("MRPC Revenue to"))
    clone_slide(prs, rev, rev+1)           # clone AFTER annual -> becomes Revenue-by-Month
    km=idx(lambda t: t.startswith("MRPC Key Metrics"))
    clone_slide(prs, km, km)               # Card Portfolio before Key Metrics
    renumber(prs)
    prs.save(out)
    print("template ->", len(prs.slides._sldIdLst), "slides")
    for i,s in enumerate(prs.slides): print(" ", i+1, repr(title_of(s)[:38]))

if __name__=="__main__":
    main(sys.argv[1], sys.argv[2])
