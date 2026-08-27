import zipfile, re, sys
from lxml import etree
IN=sys.argv[1]; OUT=sys.argv[2]
zin=zipfile.ZipFile(IN)
names=zin.namelist()
NS_R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
NS_CT='http://schemas.openxmlformats.org/package/2006/content-types'
def rels_targets(rels_xml, base='ppt'):
    root=etree.fromstring(rels_xml); out={}
    for rel in root:
        rid=rel.get('Id'); tgt=rel.get('Target'); mode=rel.get('TargetMode')
        out[rid]=(tgt,mode)
    return out
# 1) live slides from presentation sldIdLst + presentation rels
pres=etree.fromstring(zin.read('ppt/presentation.xml'))
ns={'p':'http://schemas.openxmlformats.org/presentationml/2006/main','r':NS_R}
live_rids=[e.get('{%s}id'%NS_R) for e in pres.findall('.//p:sldIdLst/p:sldId',ns)]
pres_rels=rels_targets(zin.read('ppt/_rels/presentation.xml.rels'))
def norm(t):  # relative to ppt/
    t=t.lstrip('/'); 
    return t if t.startswith('ppt/') else 'ppt/'+t
live_slides=set(norm(pres_rels[r][0]) for r in live_rids)
all_slides=set(n for n in names if re.fullmatch(r'ppt/slides/slide\d+\.xml',n))
dead_slides=all_slides-live_slides
# 2) media referenced by everything EXCEPT dead-slide rels
keep_media=set()
for n in names:
    if not n.endswith('.rels'): continue
    owner=n.replace('_rels/','').replace('.rels','')  # part this rels belongs to
    if owner in dead_slides: continue
    for tgt,mode in rels_targets(zin.read(n)).values():
        if mode=='External': continue
        p=tgt.replace('../','')
        if 'media/' in p: keep_media.add('ppt/'+p if not p.startswith('ppt/') else p)
all_media=set(n for n in names if n.startswith('ppt/media/'))
dead_media=all_media-keep_media
# 3) parts to drop
drop=set(dead_slides)|dead_media
for s in dead_slides:
    r=s.replace('slides/','slides/_rels/')+'.rels'
    if r in names: drop.add(r)
# 4) fix [Content_Types].xml (remove overrides for dead slides)
ct=etree.fromstring(zin.read('[Content_Types].xml'))
for ov in list(ct):
    pn=ov.get('PartName')
    if pn and pn.lstrip('/') in dead_slides: ct.remove(ov)
ct_xml=etree.tostring(ct,xml_declaration=True,encoding='UTF-8',standalone=True)
# 5) fix presentation rels (drop dead-slide rels)
pr=etree.fromstring(zin.read('ppt/_rels/presentation.xml.rels'))
for rel in list(pr):
    tgt=rel.get('Target')
    if tgt and norm(tgt) in dead_slides: pr.remove(rel)
pr_xml=etree.tostring(pr,xml_declaration=True,encoding='UTF-8',standalone=True)
# 6) write
zout=zipfile.ZipFile(OUT,'w',zipfile.ZIP_DEFLATED)
for item in zin.infolist():
    n=item.filename
    if n in drop: continue
    if n=='[Content_Types].xml': zout.writestr(item, ct_xml); continue
    if n=='ppt/_rels/presentation.xml.rels': zout.writestr(item, pr_xml); continue
    zout.writestr(item, zin.read(n))
zout.close()
print(f'dropped {len(dead_slides)} dead slides, {len(dead_media)} media. Out slides now:', len(all_slides)-len(dead_slides))
