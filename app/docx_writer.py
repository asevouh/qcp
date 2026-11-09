# -*- coding: utf-8 -*-
"""
إنتاج ملف Word (DOCX) من نموذج المستند نفسه وخطة التوزيع نفسها المستخدمة في PDF.

- أقسام Word: قسم للغلاف (عمود واحد) ثم قسم الأسئلة بعمودين من اليمين إلى اليسار مع خط فاصل.
- وضع "match": تُدرج فواصل أعمدة صريحة حسب خطة محرك التخطيط → توزيع مطابق لملف PDF.
- وضع "flow": يترك Word يوزع المحتوى بنفسه مع خصائص "عدم الفصل" (للتعديل الحر).
- المعادلات المركبة صور PNG عالية الدقة بأبعاد المعاينة نفسها، مع حفظ مصدرها في وصف الصورة،
  وتُخفض عن السطر بمقدار عمقها لتجلس على خط القاعدة كما في PDF.
- النصوص والأرقام والخيارات تبقى نصًا قابلًا للتحرير.
"""
import base64
import io
import os
import re
import uuid
from xml.sax.saxutils import escape as _xesc

from docx import Document
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.opc.packuri import PackURI
from docx.opc.part import Part
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls, qn

NSD = nsdecls("w", "r", "wp", "a", "pic")
CM_TW = 566.929  # twips per cm
PT_TW = 20
PX_EMU = 9525  # EMU per CSS px (96 dpi)
CM_EMU = 360000

LATIN_RE = re.compile(r"[A-Za-z][A-Za-z0-9\-\.'/ ]*[A-Za-z0-9]|[A-Za-z]")
SYMBOL_FONT = "Exam Symbols"


def esc(t):
    return _xesc(str(t), {'"': "&quot;"})


def tw(cm):
    return int(round(cm * CM_TW))


def hp(pt):
    return int(round(pt * 2))


class DocxWriter:
    def __init__(self, settings, symbols_font_path=None):
        self.s = settings
        self.font = settings.get("font_family") or "Calibri"
        self.doc = Document()
        self.body = self.doc.element.body
        self.docpr_id = 100
        self.symbols_font_path = symbols_font_path
        self._used_symbols = False
        self._img_cache = {}
        self._setup_styles()

    # ------------------------------------------------------------ أساسيات
    def lh_pt(self, size):
        factor = float(self.s.get("font_metrics_factor") or 1.2207)
        mult = max(1.0, float(self.s.get("line_spacing") or 1.15))
        return round(size * factor * mult * 20) / 20

    def _setup_styles(self):
        st = self.doc.styles.element
        dd = st.find(qn("w:docDefaults"))
        f = esc(self.font)
        new_dd = parse_xml(
            '<w:docDefaults %s><w:rPrDefault><w:rPr><w:rFonts w:ascii="%s" w:eastAsia="%s" w:hAnsi="%s" w:cs="%s"/>'
            '<w:sz w:val="26"/><w:szCs w:val="26"/><w:lang w:val="ar-SA" w:eastAsia="en-US" w:bidi="ar-SA"/></w:rPr></w:rPrDefault>'
            '<w:pPrDefault><w:pPr><w:bidi/><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>'
            % (NSD, f, f, f, f))
        if dd is not None:
            st.replace(dd, new_dd)
        else:
            st.insert(0, new_dd)
        # النمط العادي بلا تنسيقات إضافية
        for s_el in st.findall(qn("w:style")):
            if s_el.get(qn("w:styleId")) == "Normal":
                for ch in list(s_el):
                    if ch.tag in (qn("w:pPr"), qn("w:rPr")):
                        s_el.remove(ch)
        # إعدادات المستند: وضع التوافق الحديث + تضمين الخطوط
        settings = self.doc.settings.element
        compat = settings.find(qn("w:compat"))
        if compat is None:
            compat = parse_xml('<w:compat %s/>' % NSD)
            settings.append(compat)
        for cs in compat.findall(qn("w:compatSetting")):
            if cs.get(qn("w:name")) == "compatibilityMode":
                compat.remove(cs)
        compat.append(parse_xml('<w:compatSetting %s w:name="compatibilityMode" w:uri="http://schemas.microsoft.com/office/word" w:val="15"/>' % NSD))
        zoom = settings.find(qn("w:zoom"))
        if zoom is not None and zoom.get(qn("w:percent")) is None:
            zoom.set(qn("w:percent"), "100")
        # لا تدقيق إملائي مزعج للنصوص العربية الخاصة
        for tag in ("hideSpellingErrors", "hideGrammaticalErrors"):
            self._settings_insert(tag)

    SETTINGS_ORDER = ["writeProtection", "view", "zoom", "removePersonalInformation", "removeDateAndTime", "doNotDisplayPageBoundaries",
                      "displayBackgroundShape", "printPostScriptOverText", "printFractionalCharacterWidth", "printFormsData",
                      "embedTrueTypeFonts", "embedSystemFonts", "saveSubsetFonts", "saveFormsData", "mirrorMargins", "alignBordersAndEdges",
                      "bordersDoNotSurroundHeader", "bordersDoNotSurroundFooter", "gutterAtTop", "hideSpellingErrors", "hideGrammaticalErrors"]

    def _settings_insert(self, local):
        """يضيف عنصرًا إلى settings.xml في موضعه الصحيح حسب ترتيب المخطط (Word صارم في الترتيب)."""
        settings = self.doc.settings.element
        if settings.find(qn("w:" + local)) is not None:
            return
        el = parse_xml('<w:%s %s/>' % (local, NSD))
        idx = self.SETTINGS_ORDER.index(local)
        for ch in settings:
            name = ch.tag.split("}")[-1]
            if name not in self.SETTINGS_ORDER[: idx + 1]:
                ch.addprevious(el)
                return
        settings.append(el)

    def _next_id(self):
        self.docpr_id += 1
        return self.docpr_id

    def rpr(self, size, bold=False, rtl=True, font=None, position=None, shd=None, color=None, lang=True):
        fnt = esc(font or self.font)
        x = '<w:rPr><w:rFonts w:ascii="%s" w:eastAsia="%s" w:hAnsi="%s" w:cs="%s"/>' % (fnt, fnt, fnt, fnt)
        if bold:
            x += "<w:b/><w:bCs/>"
        if color:
            x += '<w:color w:val="%s"/>' % color
        if position:
            x += '<w:position w:val="%d"/>' % position
        x += '<w:sz w:val="%d"/><w:szCs w:val="%d"/>' % (hp(size), hp(size))
        if shd:
            x += '<w:shd w:val="clear" w:color="auto" w:fill="%s"/>' % shd
        if rtl:
            x += "<w:rtl/>"
        x += "</w:rPr>"
        return x

    def text_runs(self, text, size, bold=False, shd=None):
        """يقسم النص إلى مقاطع: لاتيني (LTR) وعربي/محايد (RTL)، وعلامة ⁒ بخط الرموز المضمَّن."""
        out = []
        pos = 0
        pieces = []
        for m in LATIN_RE.finditer(text):
            if m.start() > pos:
                pieces.append((text[pos:m.start()], True))
            pieces.append((m.group(0), False))
            pos = m.end()
        if pos < len(text):
            pieces.append((text[pos:], True))
        for chunk, rtl in pieces:
            # فصل علامة النسبة المئوية العربية ⁒
            parts = re.split("(⁒)", chunk)
            for p in parts:
                if not p:
                    continue
                if p == "⁒":
                    self._used_symbols = True
                    out.append('<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r>' % (self.rpr(size, bold, rtl, font=SYMBOL_FONT, shd=shd), esc(p)))
                else:
                    out.append('<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r>' % (self.rpr(size, bold, rtl, shd=shd), esc(p)))
        return "".join(out)

    def image_run(self, blob, cx, cy, name, descr="", position=0):
        key = hash(blob)
        rid = self._img_cache.get(key)
        if rid is None:
            rid, _img = self.doc.part.get_or_add_image(io.BytesIO(blob))
            self._img_cache[key] = rid
        did = self._next_id()
        pos = '<w:position w:val="%d"/>' % position if position else ""
        return ('<w:r><w:rPr><w:noProof/>%s</w:rPr><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0">'
                '<wp:extent cx="%d" cy="%d"/><wp:effectExtent l="0" t="0" r="0" b="0"/>'
                '<wp:docPr id="%d" name="%s" descr="%s"/><wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect="1"/></wp:cNvGraphicFramePr>'
                '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic>'
                '<pic:nvPicPr><pic:cNvPr id="%d" name="%s"/><pic:cNvPicPr/></pic:nvPicPr>'
                '<pic:blipFill><a:blip r:embed="%s"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
                '<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="%d" cy="%d"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
                '</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r>'
                % (pos, cx, cy, did, esc(name), esc(descr), did, esc(name), rid, cx, cy))

    def runs_xml(self, runs, size, bold=False, shd=None):
        out = []
        for r in runs or []:
            t = r.get("t")
            if t == "text":
                if r.get("text"):
                    out.append(self.text_runs(r["text"], size, bold or r.get("bold"), shd))
            elif t == "br":
                out.append('<w:r>%s<w:br/></w:r>' % self.rpr(size))
            elif t == "math":
                img = self.math.get(r.get("mathId"))
                if img:
                    cx = int(round(img["width"] * PX_EMU))
                    cy = int(round(img["height"] * PX_EMU))
                    lower = -hp(img["descent"] * 0.75)
                    out.append(self.image_run(img["png"], cx, cy, "معادلة", r.get("latex", ""), lower))
                else:
                    out.append(self.text_runs(r.get("latex", ""), size, bold, shd))
        return "".join(out)

    def para(self, inner, size=13, align=None, before=0, after=0, line=None, rule="atLeast", keep_next=False,
             keep_lines=True, ind=None, bold_mark=False, shd=None, border=None):
        ppr = "<w:pPr>"
        if keep_next:
            ppr += "<w:keepNext/>"
        if keep_lines:
            ppr += "<w:keepLines/>"
        if border:
            ppr += border
        if shd:
            ppr += '<w:shd w:val="clear" w:color="auto" w:fill="%s"/>' % shd
        ppr += "<w:bidi/>"
        if line is None:
            line = self.lh_pt(size)
        if rule == "auto":
            ppr += '<w:spacing w:before="%d" w:after="%d" w:line="240" w:lineRule="auto"/>' % (round(before * 20), round(after * 20))
        else:
            ppr += '<w:spacing w:before="%d" w:after="%d" w:line="%d" w:lineRule="%s"/>' % (round(before * 20), round(after * 20), round(line * 20), rule)
        if ind:
            ppr += ind
        if align == "center":
            ppr += '<w:jc w:val="center"/>'
        elif align == "justify":
            ppr += '<w:jc w:val="both"/>'
        ppr += self.rpr(size, bold_mark) + "</w:pPr>"
        return "<w:p>%s%s</w:p>" % (ppr, inner)

    def spacer(self, pt, keep_next=True):
        if pt <= 0:
            return ""
        return ('<w:p><w:pPr>%s<w:bidi/><w:spacing w:before="0" w:after="0" w:line="%d" w:lineRule="exact"/>%s</w:pPr></w:p>'
                % ("<w:keepNext/>" if keep_next else "", round(pt * 20), self.rpr(1)))

    def column_break(self):
        return ('<w:p><w:pPr><w:bidi/><w:spacing w:before="0" w:after="0" w:line="20" w:lineRule="exact"/>%s</w:pPr>'
                '<w:r>%s<w:br w:type="column"/></w:r></w:p>' % (self.rpr(1), self.rpr(1)))

    def cell(self, inner, width_tw, borders=None, shd=None, valign=None, span=None, mar=None, vmerge=None):
        tcpr = '<w:tcPr><w:tcW w:w="%d" w:type="dxa"/>' % width_tw
        if span:
            tcpr += '<w:gridSpan w:val="%d"/>' % span
        if vmerge == "restart":
            tcpr += '<w:vMerge w:val="restart"/>'
        elif vmerge:
            tcpr += '<w:vMerge/>'
        if borders:
            tcpr += "<w:tcBorders>%s</w:tcBorders>" % borders
        if shd:
            tcpr += '<w:shd w:val="clear" w:color="auto" w:fill="%s"/>' % shd
        if mar:
            tcpr += "<w:tcMar>%s</w:tcMar>" % mar
        if valign:
            tcpr += '<w:vAlign w:val="%s"/>' % valign
        tcpr += "</w:tcPr>"
        if not inner:
            inner = self.para("", 2, line=2, rule="exact")
        return "<w:tc>%s%s</w:tc>" % (tcpr, inner)

    def table(self, grid, rows, width_tw=None, cell_mar=(0, 40, 0, 40), jc=None, borders_none=True, row_props=None):
        width_tw = width_tw or sum(grid)
        tblpr = '<w:tblPr><w:bidiVisual/><w:tblW w:w="%d" w:type="dxa"/>' % width_tw
        if jc:
            tblpr += '<w:jc w:val="%s"/>' % jc
        tblpr += '<w:tblInd w:w="0" w:type="dxa"/>'
        if borders_none:
            tblpr += ('<w:tblBorders><w:top w:val="nil"/><w:left w:val="nil"/><w:bottom w:val="nil"/><w:right w:val="nil"/>'
                      '<w:insideH w:val="nil"/><w:insideV w:val="nil"/></w:tblBorders>')
        tblpr += '<w:tblLayout w:type="fixed"/>'
        t, l, b, r = cell_mar
        tblpr += ('<w:tblCellMar><w:top w:w="%d" w:type="dxa"/><w:left w:w="%d" w:type="dxa"/><w:bottom w:w="%d" w:type="dxa"/>'
                  '<w:right w:w="%d" w:type="dxa"/></w:tblCellMar>' % (t, l, b, r))
        tblpr += '<w:tblLook w:val="0000" w:firstRow="0" w:lastRow="0" w:firstColumn="0" w:lastColumn="0" w:noHBand="1" w:noVBand="1"/></w:tblPr>'
        g = "<w:tblGrid>" + "".join('<w:gridCol w:w="%d"/>' % c for c in grid) + "</w:tblGrid>"
        body = ""
        for k, row in enumerate(rows):
            props = (row_props[k] if row_props else None) or {}
            trpr = "<w:trPr><w:cantSplit/>"
            if props.get("height"):
                trpr += '<w:trHeight w:val="%d" w:hRule="%s"/>' % props["height"]
            trpr += "</w:trPr>"
            body += "<w:tr>%s%s</w:tr>" % (trpr, "".join(row))
        return "<w:tbl>%s%s%s</w:tbl>" % (tblpr, g, body)

    def border_all(self, pt=0.75, color="000000"):
        sz = max(2, int(round(pt * 8)))
        return "".join('<w:%s w:val="single" w:sz="%d" w:space="0" w:color="%s"/>' % (side, sz, color) for side in ("top", "left", "bottom", "right"))

    def append(self, xml):
        if not xml:
            return
        el = parse_xml('<w:body %s>%s</w:body>' % (NSD, xml))
        sect = self.body.find(qn("w:sectPr"))
        for ch in list(el):
            if sect is not None:
                sect.addprevious(ch)
            else:
                self.body.append(ch)

    # ------------------------------------------------------------ الكتل
    def col_width_cm(self):
        s = self.s
        return (21.0 - float(s["margin_right_cm"]) - float(s["margin_left_cm"]) - float(s["column_gap_cm"])) / 2

    def keep(self, xml, keep_next_last=False):
        """يضيف keepNext لكل فقرات الكتلة عدا الأخيرة (وحدة لا تنقسم)."""
        el = parse_xml('<w:body %s>%s</w:body>' % (NSD, xml))
        paras = list(el.iter(qn("w:p")))
        for k, p in enumerate(paras):
            last = k == len(paras) - 1
            if last and not keep_next_last:
                continue
            ppr = p.find(qn("w:pPr"))
            if ppr is None:
                ppr = parse_xml('<w:pPr %s/>' % NSD)
                p.insert(0, ppr)
            if ppr.find(qn("w:keepNext")) is None:
                ppr.insert(0, parse_xml('<w:keepNext %s/>' % NSD))
        from lxml import etree
        return "".join(etree.tostring(ch, encoding="unicode") for ch in el)

    def block_xml(self, b):
        s = self.s
        colw = self.col_width_cm()
        colw_tw = tw(colw)
        t = b["type"]
        if t == "section_title":
            size = float(s["title_font_pt"])
            pad_v = float(s["box_padding_v_pt"]) * 20
            pad_h = float(s["box_padding_h_pt"]) * 20
            p = self.para(self.text_runs(b["text"], size, True), size, "center", keep_next=True)
            c = self.cell(p, colw_tw, self.border_all(float(s["border_width_pt"])), s["title_fill"].lstrip("#"), "center")
            return self.keep(self.table([colw_tw], [[c]], cell_mar=(pad_v, pad_h, pad_v, pad_h)), keep_next_last=True)
        if t == "category_header":
            pad_v = float(s["box_padding_v_pt"]) * 20
            pad_h = float(s["box_padding_h_pt"]) * 20
            st = float(s["category_title_pt"])
            sd = float(s["category_def_pt"])
            inner = self.para(self.text_runs(b["title"], st, True), st, "center", keep_next=True)
            if b.get("definition"):
                inner += self.para(self.text_runs(b["definition"], sd), sd, "center", before=1, keep_next=True)
            c = self.cell(inner, colw_tw, self.border_all(float(s["border_width_pt"])))
            return self.keep(self.table([colw_tw], [[c]], cell_mar=(pad_v, pad_h, pad_v, pad_h)), keep_next_last=True)
        if t == "question":
            return self.keep(self.question_xml(b, colw, colw_tw))
        if t == "chart":
            return self.image_para(b["media"], b["widthCm"], colw)
        if t == "passage":
            size = float(s["passage_font_pt"])
            return self.para(self.runs_xml(b["runs"], size), size, b.get("align") or "justify")
        if t == "end_text":
            size = float(s["end_text_pt"])
            return self.para(self.text_runs(b["text"], size, True), size, "center")
        return ""

    def image_para(self, media_id, width_cm, max_w_cm, align="center"):
        info = self.media.get(media_id)
        if not info or not os.path.exists(info.get("path", "")):
            return self.para(self.text_runs("[صورة مفقودة]", 11), 11, "center")
        w = min(float(width_cm), max_w_cm)
        h = w * info["h"] / max(1, info["w"])
        with open(info["path"], "rb") as f:
            blob = f.read()
        run = self.image_run(blob, int(w * CM_EMU), int(h * CM_EMU), "صورة", "")
        return self.para(run, 1, align, rule="auto")

    def question_xml(self, b, colw, colw_tw):
        s = self.s
        qsize = float(s["question_font_pt"])
        osize = float(s["option_font_pt"])
        gap_stem = float(s["stem_options_gap_pt"])
        out = []
        num = self.text_runs(b["numberLabel"] + " ", qsize, bool(s.get("number_bold")))
        stem_inner = num + self.runs_xml(b["stem"], qsize)
        fig = b.get("figure")
        cap_size = float(s["caption_font_pt"])
        if fig and fig.get("placement") == "side":
            fig_w = min(float(fig["widthCm"]), colw * 0.55)
            fig_col = tw(fig_w + 0.2)
            text_col = colw_tw - fig_col
            stem_p = self.para(stem_inner, qsize)
            fig_inner = self.image_para(fig["media"], fig_w, fig_w) + self.para(self.text_runs(fig["caption"], cap_size), cap_size, "center")
            c1 = self.cell(stem_p, text_col)
            c2 = self.cell(fig_inner, fig_col, mar='<w:right w:w="%d" w:type="dxa"/>' % tw(0.2))
            out.append(self.table([text_col, fig_col], [[c1, c2]], cell_mar=(0, 0, 0, 0)))
            out.append(self.spacer(gap_stem))
        else:
            if fig and fig.get("placement") == "above":
                out.append(self.image_para(fig["media"], fig["widthCm"], colw))
                out.append(self.para(self.text_runs(fig["caption"], cap_size), cap_size, "center"))
            out.append(self.para(stem_inner, qsize, after=gap_stem))
            if fig and fig.get("placement") != "above":
                out.append(self.image_para(fig["media"], fig["widthCm"], colw))
                out.append(self.para(self.text_runs(fig["caption"], cap_size), cap_size, "center", after=gap_stem))
        if b.get("compare"):
            cmpd = b["compare"]
            lab_size = float(s["compare_label_pt"])
            pad_v = float(s["box_padding_v_pt"]) * 20
            pad_h = float(s["box_padding_h_pt"]) * 20
            half = colw_tw // 2
            cells = []
            for lab, val in ((cmpd["label1"], cmpd["v1"]), (cmpd["label2"], cmpd["v2"])):
                inner = self.para(self.text_runs(self._disp(lab), lab_size), lab_size)
                inner += self.para(self.runs_xml(val, osize), osize, "center")
                cells.append(self.cell(inner, half, self.border_all(float(s["border_width_pt"])), valign="center"))
            out.append(self.table([half, colw_tw - half], [cells], cell_mar=(pad_v, pad_h, pad_v, pad_h)))
            out.append(self.spacer(float(s["compare_gap_pt"])))
        out.append(self.options_xml(b, colw_tw, osize))
        return "".join(out)

    def _disp(self, t):
        if (self.s.get("digits") or "hindi") == "hindi":
            return re.sub(r"[0-9]", lambda m: "٠١٢٣٤٥٦٧٨٩"[int(m.group(0))], t)
        return t

    def options_xml(self, b, colw_tw, size):
        s = self.s
        lab_tw = tw(float(s["option_label_width_cm"]))
        pad = float(s["cell_padding_pt"]) * 20
        fill = (s.get("correct_fill") or "#D9D9D9").lstrip("#")
        items = b["options"]["items"]

        def pair(it):
            shd = fill if it.get("correct") else None
            bold = bool(it.get("correct"))
            c1 = self.cell(self.para(self.text_runs(it["label"], size, bold), size), lab_tw, shd=shd)
            c2 = self.cell(self.para(self.runs_xml(it["runs"], size, bold), size), 0, shd=shd)
            return c1, c2

        if b["options"]["layout"] == "grid":
            txt_tw = (colw_tw - 2 * lab_tw) // 2
            grid = [lab_tw, txt_tw, lab_tw, colw_tw - 2 * lab_tw - txt_tw]
            rows = []
            for r in range(2):
                a1, a2 = pair(items[r * 2])
                b1, b2 = pair(items[r * 2 + 1])
                a2 = a2.replace('<w:tcW w:w="0"', '<w:tcW w:w="%d"' % grid[1], 1)
                b2 = b2.replace('<w:tcW w:w="0"', '<w:tcW w:w="%d"' % grid[3], 1)
                rows.append([a1, a2, b1, b2])
        else:
            grid = [lab_tw, colw_tw - lab_tw]
            rows = []
            for it in items:
                c1, c2 = pair(it)
                c2 = c2.replace('<w:tcW w:w="0"', '<w:tcW w:w="%d"' % grid[1], 1)
                rows.append([c1, c2])
        return self.table(grid, rows, cell_mar=(0, pad, 0, pad))

    # ------------------------------------------------------------ الترويسة والتذييل والغلاف
    def header_xml(self, info):
        s = self.s
        body_w = 21.0 - float(s["margin_right_cm"]) - float(s["margin_left_cm"])
        gap = float(s["header_box_gap_cm"])
        box_w = (body_w - 2 * gap) / 3
        h = float(s["header_height_cm"])
        src_size = float(s["header_source_pt"])
        title_size = float(s["header_title_pt"])
        bw = float(s.get("header_border_pt") or 1)

        def src_box(lab, val):
            inner = self.para(self.text_runs(self._disp(lab), src_size, True), src_size, "center", line=src_size * 1.25, rule="exact", keep_lines=False)
            inner += self.para(self.text_runs(self._disp(val or "—"), src_size, True), src_size, "center", line=src_size * 1.25, rule="exact", keep_lines=False)
            return self.cell(inner, tw(box_w), self.border_all(bw), valign="center")

        title_cell = self.cell(self.para(self.text_runs(self._disp(info.get("headerTitle", "")), title_size, True), title_size, "center", keep_lines=False),
                               tw(box_w), self.border_all(bw), valign="center")
        gap_cell = self.cell("", tw(gap))
        row = [src_box(s["header_quant_label"], info.get("quantSource")), gap_cell, title_cell, gap_cell,
               src_box(s["header_verbal_label"], info.get("verbalSource"))]
        grid = [tw(box_w), tw(gap), tw(box_w), tw(gap), tw(box_w)]
        tbl = self.table(grid, [row], cell_mar=(0, 40, 0, 40), row_props=[{"height": (tw(h), "exact")}])
        # خط أفقي أسفل الترويسة
        rule_gap = float(s["header_rule_gap_cm"]) * CM_TW / 20  # pt
        ext = max(0, float(s["margin_right_cm"]) - 0.4)
        ind = '<w:ind w:left="-%d" w:right="-%d"/>' % (tw(ext), tw(ext))
        border = '<w:pBdr><w:bottom w:val="single" w:sz="6" w:space="0" w:color="000000"/></w:pBdr>'
        rule = self.para("", 1, line=max(1, rule_gap), rule="exact", ind=ind, border=border, keep_lines=False)
        return tbl + rule

    def footer_xml(self):
        s = self.s
        if not s.get("page_numbers", True):
            return self.para("", 2, line=2, rule="exact")
        box = float(s["page_number_box_cm"])
        size = float(s["page_number_pt"])
        fld = ('<w:r>%s<w:fldChar w:fldCharType="begin"/></w:r><w:r>%s<w:instrText xml:space="preserve"> PAGE </w:instrText></w:r>'
               '<w:r>%s<w:fldChar w:fldCharType="separate"/></w:r><w:r>%s<w:t>١</w:t></w:r><w:r>%s<w:fldChar w:fldCharType="end"/></w:r>'
               % ((self.rpr(size),) * 5))
        p = self.para(fld, size, "center", keep_lines=False)
        c = self.cell(p, tw(box), self.border_all(0.75, "7F7F7F"), valign="center")
        return self.table([tw(box)], [[c]], jc="center", row_props=[{"height": (tw(box * 0.85), "exact")}])

    def cover_xml(self, plan):
        """الغلاف من خطة محرك التخطيط (layout.js → renderCover): المواضع والمسافات نفسها المستخدمة في PDF."""
        K = plan["K"]
        T = plan["top"]
        out = []
        PT_PER_CM = 72 / 2.54
        lh, size = plan["lineHpt"], plan["lineSizePt"]
        ex = dict(rule="exact", keep_lines=False)

        # ---- الجدول العلوي: 4 أعمدة × 4 صفوف، والخليتان الجانبيتان مدموجتان رأسيًا (كما في المرجع)
        tw_total = tw(K["tableW"])
        fr = [0.3445, 0.1552, 0.1555]
        grid = [tw(K["tableW"] * f) for f in fr]
        grid.append(tw_total - sum(grid))
        b = self.border_all(0.75)
        gsz, glh = K["gridPt"], plan["gridLineHpt"]
        ssz, slh = K["sidePt"], plan["sideLineHpt"]

        def gp(text):
            return self.para(self.text_runs(text, gsz), gsz, "center", line=glh, **ex)

        def side_cell(text, w, first):
            inner = self.para(self.text_runs(text, ssz, True), ssz, "center", line=slh, **ex) if first else ""
            return self.cell(inner, w, b, valign="center", vmerge="restart" if first else "continue")

        rows = [
            [side_cell(T["right"], grid[0], True), self.cell(gp(T["grade"]), grid[1] + grid[2], b, valign="center", span=2), side_cell(T["left"], grid[3], True)],
            [side_cell("", grid[0], False), self.cell(gp(T["quant"]), grid[1], b, valign="center"), self.cell(gp(T["verbal"]), grid[2], b, valign="center"), side_cell("", grid[3], False)],
            [side_cell("", grid[0], False), self.cell("", grid[1], b), self.cell("", grid[2], b), side_cell("", grid[3], False)],
            [side_cell("", grid[0], False), self.cell(gp(T["quantCount"]), grid[1], b, valign="center"), self.cell(gp(T["verbalCount"]), grid[2], b, valign="center"), side_cell("", grid[3], False)],
        ]
        rh = {"height": (tw(K["rowH"]), "exact")}
        out.append(self.table(grid, rows, jc="center", cell_mar=(0, 60, 0, 60), row_props=[rh] * 4))

        gap_pt = plan["gapCm"] * PT_PER_CM
        for g in plan["groups"]:
            kind = g["kind"]
            anchor = ""
            if kind == "remind":
                anchor = self.cover_reminder_shape(plan, g)
            sp = self.spacer(gap_pt, keep_next=False)
            if anchor:
                # الصندوق المستدير يُثبَّت بموضع مطلق في الصفحة؛ مرساته في فقرة المسافة التي تسبقه
                sp = sp.replace("</w:pPr></w:p>", "</w:pPr>%s</w:p>" % anchor, 1)
            out.append(sp)
            if kind == "info":
                n = len(g["lines"])
                for k, ln in enumerate(g["lines"]):
                    out.append(self.para(self.text_runs(ln["text"], size, ln.get("bold")), size, "center", line=lh,
                                         after=K["infoAfter"] if k < n - 1 else 0, **ex))
            elif kind == "big":
                bsz = K["bigPt"]
                w = tw(min(K["tableW"], g.get("bigWcm") or plan["bigWcm"]) + 0.15)
                p = self.para(self.text_runs(g["text"], bsz, True), bsz, "center", line=plan["bigLineHpt"], **ex)
                c = self.cell(p, w, self.border_all(1.0), valign="center")
                out.append(self.table([w], [[c]], jc="center", cell_mar=(tw(K["bigPadV"]), tw(K["bigPadH"]), tw(K["bigPadV"]), tw(K["bigPadH"]))))
            elif kind == "notes":
                notes = g.get("notes") or []
                if g.get("title"):
                    out.append(self.para(self.text_runs(g["title"], size, True), size, "center", line=lh,
                                         after=K["notesTitleAfter"] if notes else 0, **ex))
                ind = '<w:ind w:right="%d" w:left="%d" w:hanging="%d"/>' % (
                    tw(K["inner"] + K["textAt"]), tw(K["inner"]), tw(K["textAt"] - K["bulletAt"]))
                for k, n in enumerate(notes):
                    out.append(self.para(self.text_runs("•", size) + '<w:r>%s<w:tab/></w:r>' % self.rpr(size) + self.text_runs(n, size),
                                         size, line=lh, after=K["noteAfter"] if k < len(notes) - 1 else 0, ind=ind, **ex))
            elif kind == "names":
                labs = g.get("labels") or []
                dots = g.get("dots") or []
                ind = '<w:ind w:right="%d" w:left="%d"/>' % (tw(K["inner"]), tw(K["inner"]))
                for k, lab in enumerate(labs):
                    n = dots[k] if k < len(dots) else 60
                    out.append(self.para(self.text_runs(lab + " " + "." * n, size, True), size, line=lh,
                                         after=K["nameAfter"] if k < len(labs) - 1 else 0, ind=ind, **ex))
        return "".join(out)

    def cover_reminder_shape(self, plan, g):
        """صندوق التذكير: مستطيل بزوايا مستديرة (roundRect) فيه مربع نص، بالموضع والمقاس نفسيهما في PDF."""
        K = plan["K"]
        size, lh = plan["lineSizePt"], plan["lineHpt"]
        cx = int(round(K["remindW"] * CM_EMU))
        cy = int(round(g["boxHcm"] * CM_EMU))
        y = int(round(g["topCm"] * CM_EMU))
        ins = int(round((K["remindPadH"] + 1 / 72 * 2.54) * CM_EMU))
        inner = ""
        if g.get("title"):
            inner += self.para(self.text_runs(g["title"], size, True), size, "center", line=lh, after=K["remindTitleAfter"], rule="exact", keep_lines=False)
        inner += self.para(self.text_runs(g["text"], size), size, "center", line=lh, rule="exact", keep_lines=False)
        did = self._next_id()
        return (
            '<w:r><w:rPr><w:noProof/></w:rPr>'
            '<mc:AlternateContent xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
            'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">'
            '<mc:Choice Requires="wps"><w:drawing>'
            '<wp:anchor distT="0" distB="0" distL="114300" distR="114300" simplePos="0" relativeHeight="251659264" '
            'behindDoc="0" locked="0" layoutInCell="1" allowOverlap="1">'
            '<wp:simplePos x="0" y="0"/>'
            '<wp:positionH relativeFrom="page"><wp:align>center</wp:align></wp:positionH>'
            '<wp:positionV relativeFrom="page"><wp:posOffset>%d</wp:posOffset></wp:positionV>'
            '<wp:extent cx="%d" cy="%d"/><wp:effectExtent l="0" t="0" r="0" b="0"/><wp:wrapNone/>'
            '<wp:docPr id="%d" name="Reminder"/><wp:cNvGraphicFramePr/>'
            '<a:graphic><a:graphicData uri="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">'
            '<wps:wsp><wps:cNvSpPr/><wps:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="%d" cy="%d"/></a:xfrm>'
            '<a:prstGeom prst="roundRect"><a:avLst/></a:prstGeom><a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill>'
            '<a:ln w="12700"><a:solidFill><a:srgbClr val="000000"/></a:solidFill></a:ln></wps:spPr>'
            '<wps:txbx><w:txbxContent>%s</w:txbxContent></wps:txbx>'
            '<wps:bodyPr rot="0" vert="horz" wrap="square" lIns="%d" tIns="0" rIns="%d" bIns="0" anchor="ctr" anchorCtr="0">'
            '<a:noAutofit/></wps:bodyPr></wps:wsp></a:graphicData></a:graphic></wp:anchor></w:drawing></mc:Choice>'
            '</mc:AlternateContent></w:r>'
            % (y, cx, cy, did, cx, cy, inner, ins, ins))

    # ------------------------------------------------------------ تجميع المستند
    def sect_pr(self, kind, plan=None):
        if kind == "cover":
            K = (plan or {}).get("K") or {"top": 2.1, "tableW": 16.93}
            side = tw((21.0 - K["tableW"]) / 2)
            return ('<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="%d" w:right="%d" w:bottom="567" w:left="%d" w:header="0" w:footer="0" w:gutter="0"/>'
                    '<w:cols w:space="708"/><w:bidi/><w:docGrid w:linePitch="360"/></w:sectPr>' % (tw(K["top"]), side, side))
        return None

    def build(self, result, media, math_images, info, include_cover=True, mode="match"):
        """result: مخرجات محرك التخطيط (blocks + plan)."""
        self.media = media
        self.math = {}
        for m in math_images or []:
            data = m["dataUrl"].split(",", 1)[1]
            self.math[m["id"]] = {"png": base64.b64decode(data), "width": m["width"], "height": m["height"], "descent": m["descent"]}
        s = self.s
        blocks = {b["id"]: b for b in result["blocks"]}
        # إزالة الفقرة الفارغة الافتراضية
        for p in self.body.findall(qn("w:p")):
            self.body.remove(p)
        cover_plan = result.get("cover") if include_cover else None
        include_cover = bool(cover_plan)
        if include_cover:
            self.append(self.cover_xml(cover_plan))
            self.append('<w:p><w:pPr><w:bidi/><w:spacing w:after="0" w:line="20" w:lineRule="exact"/>%s%s</w:pPr></w:p>' % (self.rpr(1), self.sect_pr("cover", cover_plan)))
        plan = result["plan"]
        if mode == "flow":
            order = [ent for col in plan for ent in col]
            for k, ent in enumerate(order):
                b = blocks[ent["id"]]
                if k:
                    self.append(self.spacer(float(b.get("gapBefore") or 0)))
                self.append(self.block_xml(b))
        else:
            for ci, col in enumerate(plan):
                for k, ent in enumerate(col):
                    b = blocks[ent["id"]]
                    if k and ent.get("gap"):
                        self.append(self.spacer(float(ent["gap"])))
                    self.append(self.block_xml(b))
                if ci < len(plan) - 1:
                    self.append(self.column_break())
        # خصائص قسم الأسئلة
        sect = self.body.find(qn("w:sectPr"))
        for ch in list(sect):
            if ch.tag not in (qn("w:headerReference"), qn("w:footerReference")):
                sect.remove(ch)
        g = {
            "top": tw(float(s["margin_top_cm"])), "bottom": tw(float(s["margin_bottom_cm"])),
            "right": tw(float(s["margin_right_cm"])), "left": tw(float(s["margin_left_cm"])),
            "header": tw(float(s["header_top_cm"])), "footer": tw(float(s["footer_bottom_cm"])),
        }
        tail = parse_xml(
            '<w:sectPr %s><w:type w:val="nextPage"/><w:pgSz w:w="11906" w:h="16838"/>'
            '<w:pgMar w:top="%d" w:right="%d" w:bottom="%d" w:left="%d" w:header="%d" w:footer="%d" w:gutter="0"/>'
            '<w:pgNumType w:start="1"/><w:cols w:num="2" w:space="%d" w:sep="1"/><w:bidi/><w:docGrid w:linePitch="360"/></w:sectPr>'
            % (NSD, g["top"], g["right"], g["bottom"], g["left"], g["header"], g["footer"], tw(float(s["column_gap_cm"]))))
        for ch in list(tail):
            sect.append(ch)
        section = self.doc.sections[-1]
        section.header.is_linked_to_previous = False
        section.footer.is_linked_to_previous = False
        self._fill_part(section.header._element, self.header_xml(info))
        self._fill_part(section.footer._element, self.footer_xml())
        if include_cover:
            first = self.doc.sections[0]
            # الغلاف بلا ترويسة: نربط الغلاف بترويسة فارغة صريحة
            first.header.is_linked_to_previous = False
            first.footer.is_linked_to_previous = False
            self._fill_part(first.header._element, self.para("", 2, line=2, rule="exact"))
            self._fill_part(first.footer._element, self.para("", 2, line=2, rule="exact"))
        if self._used_symbols:
            self._embed_symbol_font()
        core = self.doc.core_properties
        core.title = info.get("examTitle") or ""
        core.author = "مُنشئ اختبارات القدرات"
        core.language = "ar-SA"
        return self.doc

    def _fill_part(self, el, xml):
        for ch in list(el):
            el.remove(ch)
        frag = parse_xml('<w:body %s>%s</w:body>' % (NSD, xml))
        for ch in list(frag):
            el.append(ch)
        # يجب أن ينتهي بفقرة
        if len(el) == 0 or el[-1].tag != qn("w:p"):
            el.append(parse_xml(self.para("", 1, line=1, rule="exact").replace("<w:p>", "<w:p %s>" % NSD, 1)))

    def _embed_symbol_font(self):
        """تضمين خط صغير يحوي علامة النسبة المئوية ⁒ حتى تظهر في أي جهاز."""
        if not self.symbols_font_path or not os.path.exists(self.symbols_font_path):
            return
        package = self.doc.part.package
        ft_part = None
        for rel in self.doc.part.rels.values():
            if rel.reltype == RT.FONT_TABLE:
                ft_part = rel.target_part
        if ft_part is None:
            return
        with open(self.symbols_font_path, "rb") as f:
            data = bytearray(f.read())
        guid = str(uuid.uuid4()).upper()
        key_hex = guid.replace("-", "")
        key = bytes.fromhex(key_hex)
        for i in range(32):
            data[i] ^= key[15 - (i % 16)]
        font_part = Part(PackURI("/word/fonts/font1.odttf"), "application/vnd.openxmlformats-officedocument.obfuscatedFont", bytes(data), package)
        rid = ft_part.relate_to(font_part, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/font")
        xml_font = ('<w:font %s w:name="%s"><w:panose1 w:val="020B0603030804020204"/><w:charset w:val="00"/><w:family w:val="swiss"/><w:pitch w:val="variable"/>'
                    '<w:embedRegular r:id="%s" w:fontKey="{%s}"/></w:font>' % (NSD, SYMBOL_FONT, rid, guid))
        if hasattr(ft_part, "_element"):
            ft_part._element.append(parse_xml(xml_font))
        else:
            from lxml import etree
            root = etree.fromstring(ft_part.blob)
            root.append(parse_xml(xml_font))
            ft_part._blob = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
        self._settings_insert("embedTrueTypeFonts")

    def save(self, path):
        self.doc.save(path)


# ---------------------------------------------------------------- مفتاح الإجابة
def build_answer_key_docx(settings, answer_key, sections, exam_title, path):
    w = DocxWriter(settings)
    for p in w.body.findall(qn("w:p")):
        w.body.remove(p)
    letters = {"a": "أ", "b": "ب", "c": "جـ", "d": "د"}
    w.append(w.para(w.text_runs("%s — %s" % (settings.get("answer_key_title") or "مفتاح الإجابة", exam_title or ""), 18, True), 18, "center", after=10))
    tables = []
    for idx, sec in enumerate(sections):
        if not sec:
            continue
        rows = [r for r in answer_key if r["sectionIndex"] == idx]
        title = settings["quant_section_title"] if sec["kind"] == "quant" else settings["verbal_section_title"]
        b = w.border_all(0.75)
        inner = w.para(w.text_runs(title, 14, True), 14, "center")
        inner += w.para(w.text_runs(w._disp(sec.get("source") or ""), 10), 10, "center", after=4)
        trs = [[w.cell(w.para(w.text_runs("رقم السؤال", 12, True), 12, "center"), tw(3.5), b, "E6E6E6"),
                w.cell(w.para(w.text_runs("الإجابة", 12, True), 12, "center"), tw(3.5), b, "E6E6E6")]]
        for r in rows:
            trs.append([w.cell(w.para(w.text_runs(w._disp(str(r["number"])), 12), 12, "center"), tw(3.5), b),
                        w.cell(w.para(w.text_runs(letters.get(r.get("answer"), "—"), 12, True), 12, "center"), tw(3.5), b)])
        inner += w.table([tw(3.5), tw(3.5)], trs, jc="center")
        inner += w.para("", 2, line=2, rule="exact")
        tables.append(w.cell(inner, tw(8.2)))
    if tables:
        w.append(w.table([tw(8.2)] * len(tables), [tables], jc="center", cell_mar=(0, 60, 0, 60)))
    sect = w.body.find(qn("w:sectPr"))
    for ch in list(sect):
        sect.remove(ch)
    for ch in parse_xml('<w:sectPr %s><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134" w:header="567" w:footer="567" w:gutter="0"/><w:cols w:space="708"/><w:bidi/></w:sectPr>' % NSD):
        sect.append(ch)
    w.doc.core_properties.title = "مفتاح الإجابة — " + (exam_title or "")
    w.doc.save(path)
