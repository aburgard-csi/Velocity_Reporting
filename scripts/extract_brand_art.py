"""Extract the decorative art of the CSI brand template into build/assets/csi_brand/.

The brand template ("Updated Brand Presentation Sept. 2026.potx") draws its title, divider and closing slides with
a few plain shapes and two logo pictures. The builders draw those slides themselves (build/cover_divider.py), so
the art is lifted out of the template once and checked in; the build never reads the .potx.

The template paints with THEME colours (accent2..accent5, bg1). The shells' own theme is the stock Office one, where
those names mean other colours, so every theme colour is replaced here by the literal it has in the template's theme.

    python scripts/extract_brand_art.py "<path to the .potx>"

Writes: title_band.xml, title_wedge.xml, divider_wedge.xml, divider_fill.xml (the gradient fill of the divider
background), closing_fill.xml, csi_logo_dark.png (title slide, on white), csi_logo_white.png (white lettering,
coloured mark: the closing slide) and csi_logo_mono.png (all white: the divider, where the mark sits on the orange wedge
and would vanish; the template gets this with a bi-level picture effect, which not every viewer honours).
Each .xml is one <p:sp> (or one <a:gradFill>) with literal colours; brand_art.py loads them.
"""
import copy
import os
import re
import sys
import zipfile

from lxml import etree

NS = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main",
      "p": "http://schemas.openxmlformats.org/presentationml/2006/main"}
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "build", "assets", "csi_brand")


def theme_colours(z):
    """name -> hex for the template's own theme (the one its master points at)."""
    rel = z.read("ppt/slideMasters/_rels/slideMaster1.xml.rels").decode()
    theme = "ppt/theme/" + re.search(r'theme/(theme\d+\.xml)', rel).group(1)
    root = etree.fromstring(z.read(theme))
    cs = root.find(".//a:clrScheme", NS)
    out = {}
    for el in cs:
        name = etree.QName(el).localname
        c = el[0]
        out[name] = (c.get("val") if etree.QName(c).localname == "srgbClr" else c.get("lastClr")).upper()
    # the names slides use: bg1 -> lt1, tx1 -> dk1, bg2 -> lt2, tx2 -> dk2
    out.update(bg1=out["lt1"], tx1=out["dk1"], bg2=out["lt2"], tx2=out["dk2"])
    return out


def literal(el, colours):
    """Replace every <a:schemeClr val=x> under `el` with <a:srgbClr val=hex>, keeping its children (lumMod ...)."""
    for sc in el.iter("{%s}schemeClr" % NS["a"]):
        sc.tag = "{%s}srgbClr" % NS["a"]
        sc.set("val", colours[sc.get("val")])
    return el


def shape(root, name):
    for sp in root.findall(".//p:sp", NS):
        if sp.find(".//p:cNvPr", NS).get("name") == name:
            return sp
    raise SystemExit(f"shape {name!r} not found")


def strip_ids(sp, new_name):
    nv = sp.find(".//p:cNvPr", NS)
    nv.set("name", new_name)
    nv.set("id", "0")                                   # brand_art assigns a free id on insert
    for ext in nv.findall("a:extLst", NS):               # the template's creation id: a copy per slide would repeat it
        nv.remove(ext)
    for pr in sp.findall(".//p:nvPr", NS):
        pr.attrib.pop("userDrawn", None)
    return sp


def write(name, el):
    data = etree.tostring(el, xml_declaration=False, encoding="unicode")
    with open(os.path.join(OUT, name), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(data + "\n")
    print("wrote", name, len(data), "chars")


def main(argv):
    if len(argv) != 1:
        raise SystemExit(__doc__)
    z = zipfile.ZipFile(argv[0])
    col = theme_colours(z)
    print("theme colours:", {k: col[k] for k in ("accent2", "accent3", "accent4", "accent5", "bg1")})
    os.makedirs(OUT, exist_ok=True)
    lay = lambda n: etree.fromstring(z.read(f"ppt/slideLayouts/slideLayout{n}.xml"))
    t, d, c = lay(1), lay(11), lay(17)
    write("title_band.xml", literal(strip_ids(copy.deepcopy(shape(t, "Freeform 17")), "csi:band"), col))
    write("title_wedge.xml", literal(strip_ids(copy.deepcopy(shape(t, "Freeform 13")), "csi:wedge"), col))
    write("divider_wedge.xml", literal(strip_ids(copy.deepcopy(shape(d, "Freeform 21")), "csi:wedge"), col))
    write("divider_fill.xml", literal(copy.deepcopy(shape(d, "Freeform 27").find("p:spPr/a:gradFill", NS)), col))
    write("closing_fill.xml", literal(copy.deepcopy(c.find("p:cSld/p:bg/p:bgPr/a:gradFill", NS)), col))
    for img, out in (("image1.png", "csi_logo_dark.png"), ("image3.png", "csi_logo_white.png")):
        with open(os.path.join(OUT, out), "wb") as fh:
            fh.write(z.read("ppt/media/" + img))
        print("wrote", out)
    mono(z.read("ppt/media/image3.png"), os.path.join(OUT, "csi_logo_mono.png"))
    print("wrote csi_logo_mono.png")


def mono(png_bytes, path):
    """Every visible pixel white, transparency kept."""
    import io
    from PIL import Image
    im = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    alpha = im.getchannel("A")
    out = Image.new("RGBA", im.size, (255, 255, 255, 0))
    out.putalpha(alpha)
    out.paste((255, 255, 255, 255), mask=alpha)
    out.save(path)


if __name__ == "__main__":
    main(sys.argv[1:])
