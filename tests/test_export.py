# -*- coding: utf-8 -*-
"""
اختبارات التصدير الفعلي إلى Word وPDF عبر واجهة البرنامج البرمجية:
- إنتاج الملفات وصلاحيتها.
- عدم تقسيم أي سؤال، وعدم تجاوز الأعمدة، وأن كل انتقال إلى عمود جديد كان لضيق المساحة فعلًا.
- ترتيب الأسئلة في الملفين = ترتيبها في قاعدة البيانات.
- اتجاه RTL، والعمودان من اليمين، والترويسة تحمل المصدرين، والأرقام هندية، والمعادلات صور مع مصدرها.
- نسخة المعلم، ومفتاح الإجابة، ووضع التدفق، وأثر الإعدادات.
- حالة: نص استيعاب طويل يتوزع بين النصفين عند حدود الفقرات فقط.
"""
import io
import os
import re
import unittest
import zipfile

import helpers

SKIP = not helpers.playwright_available()
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
HINDI = "٠١٢٣٤٥٦٧٨٩"


def hindi(n):
    return "".join(HINDI[int(c)] for c in str(n))


def docx_xml(raw):
    z = zipfile.ZipFile(io.BytesIO(raw))
    return {n: z.read(n).decode("utf-8") for n in z.namelist() if n.endswith(".xml") or n.endswith(".rels")}, z


def para_texts(document_xml):
    from lxml import etree
    root = etree.fromstring(document_xml.encode("utf-8"))
    out = []
    for p in root.iter(W + "p"):
        out.append("".join(t.text or "" for t in p.iter(W + "t")))
    return out


@unittest.skipIf(SKIP, "Playwright غير مثبت")
class ExportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ids = helpers.demo()
        _, cls.srv = helpers.server()
        cls.db = cls.srv.DB()

    def export(self, variant="student", formats=("pdf", "docx"), exam_id=None):
        r = helpers.http("POST", "/api/exams/%d/export" % (exam_id or self.ids["exam"]), {"formats": list(formats), "variant": variant})
        self.assertTrue(r.get("ok"), r.get("error"))
        files = {k: helpers.download(u) for k, u in r["data"]["files"].items()}
        return r["data"], files

    def layout(self, sections, settings=None, exam=None):
        import exporter
        s = exporter.prepare_settings(settings or self.db.get_settings())
        payload, media = exporter.build_payload(self.db, sections, s, exam or {"title": "اختبار"}, "student", False, True)
        res = self.srv.STATE["worker"].submit("exam", payload, pdf=True, math=True)
        return res, s, media

    # ------------------------------------------------------------------
    def test_pdf_and_docx_produced(self):
        data, files = self.export()
        self.assertTrue(files["pdf"].startswith(b"%PDF"))
        self.assertGreater(len(files["docx"]), 20000)
        rep = data["report"]
        self.assertEqual(rep["overflow"], [])
        self.assertEqual(rep["warnings"], [])
        self.assertEqual(rep["mathErrors"], [])
        self.assertEqual(rep["brokenImages"], [])
        npages = len(re.findall(rb"/Type\s*/Page[^s]", files["pdf"]))
        self.assertEqual(npages, rep["pages"])

    def test_question_order_matches_database(self):
        data, files = self.export()
        content = self.db.exam_sections_content(self.ids["exam"])
        expected = helpers.flatten_qids(content["quant"]["items"]) + helpers.flatten_qids(content["verbal"]["items"])
        self.assertEqual(data["report"]["order"], expected)
        # ترتيب أرقام الأسئلة في Word (يبدأ الترقيم من ١ في كل قسم)
        xml, _ = docx_xml(files["docx"])
        nums = [m for t in para_texts(xml["word/document.xml"]) for m in re.findall(r"^([٠-٩]+):", t)]
        nq = len(helpers.flatten_qids(content["quant"]["items"]))
        nv = len(helpers.flatten_qids(content["verbal"]["items"]))
        self.assertEqual(nums, [hindi(i) for i in range(1, nq + 1)] + [hindi(i) for i in range(1, nv + 1)])

    def test_no_split_and_greedy_columns(self):
        """كل سؤال كتلة واحدة في عمود واحد؛ ولا ينتقل محتوى لعمود جديد إلا إذا لم يتسع فعلًا."""
        content = self.db.exam_sections_content(self.ids["exam"])
        res, s, _ = self.layout([content["quant"], content["verbal"]])
        lay = res["layout"]
        blocks = {b["id"]: b for b in lay["blocks"]}
        seen = []
        for col in lay["plan"]:
            for ent in col:
                seen.append(ent["id"])
        self.assertEqual(seen, [b["id"] for b in lay["blocks"]], "كل كتلة تظهر مرة واحدة وبالترتيب")
        self.assertEqual(lay["overflow"], [])
        # العنوان/التعريف لا يبقى وحيدًا في أسفل عمود
        for col in lay["plan"][:-1]:
            last = blocks[col[-1]["id"]]
            self.assertNotIn(last["type"], ("section_title", "category_header"), "عنوان منفصل عن محتواه في أسفل عمود")

    def check_greedy(self, lay):
        """يتحقق أن كل عمود لا يتجاوز سعته، وأن أول كتلة في العمود التالي لم تكن لتتسع في السابق.
        يعيد قائمة المسافات المتبقية عند كل انتقال مع ارتفاع الكتلة المنقولة."""
        cap = lay["colCapacityPt"]
        h = dict(zip([b["id"] for b in lay["blocks"]], lay["heights"]))
        blocks = {b["id"]: b for b in lay["blocks"]}
        moves = []
        for ci, col in enumerate(lay["plan"]):
            used = sum(e["gap"] + h[e["id"]] for e in col)
            self.assertLessEqual(used, cap + 0.5, "العمود %d تجاوز سعته" % ci)
            if ci + 1 < len(lay["plan"]):
                nxt = lay["plan"][ci + 1][0]["id"]
                b = blocks[nxt]
                need = (b.get("gapBefore") or 0) + h[nxt]
                if b.get("keepWithNext") or blocks[col[-1]["id"]].get("keepWithNext"):
                    continue
                self.assertGreater(used + need, cap, "الكتلة %s كانت تتسع في العمود السابق" % nxt)
                moves.append((cap - used, h[nxt], b["type"]))
        return moves

    def test_question_near_column_end_moves_whole(self):
        """حالة: سؤال يقع قرب نهاية النصف الأيمن ولا تتسع المساحة لخياراته — يجب أن ينتقل كاملًا إلى النصف التالي."""
        sid = self.db.create_section("حالة نهاية العمود", "quant", "اختبار")
        long_stem = "سؤال طويل نسبيًا لاختبار التوزيع " * 4
        for k in range(13):
            self.db.create_item(sid, {"type": "question", "category": "regular", "answer": "a",
                                      "data": {"stem": long_stem + str(k + 1), "options_type": "long" if k % 3 == 0 else "short",
                                               "options": [("خيار طويل لاختبار الالتفاف داخل الخلية " * 2 if k % 3 == 0 else "") + "١", "٢", "٣", "٤"]}})
        import db as dbm
        section = dbm.strip_section(self.db.get_section(sid, with_items=True))
        res, s, _ = self.layout([section])
        lay = res["layout"]
        self.assertEqual(lay["overflow"], [])
        moves = self.check_greedy(lay)
        self.assertTrue(moves)
        # يوجد انتقال كانت فيه المساحة المتبقية تكفي لنص السؤال (سطرين على الأقل) لكن ليس للسؤال كاملًا مع خياراته
        two_lines = 2 * 18.25
        self.assertTrue(any(rem >= two_lines and rem < need for rem, need, t in moves if t == "question"),
                        "لم تظهر حالة سؤال قرب نهاية العمود: %r" % moves)

    def test_demo_exam_columns_greedy(self):
        content = self.db.exam_sections_content(self.ids["exam"])
        res, _, _ = self.layout([content["quant"], content["verbal"]])
        self.check_greedy(res["layout"])

    def test_docx_rtl_columns_header_and_digits(self):
        data, files = self.export()
        xml, z = docx_xml(files["docx"])
        doc = xml["word/document.xml"]
        self.assertIn('<w:cols w:num="2"', doc)
        self.assertIn('w:sep="1"', doc)
        self.assertRegex(doc, r"<w:cols [^>]*/><w:bidi/>")
        self.assertIn("<w:bidiVisual/>", doc)
        self.assertNotIn('w:val="Cambria Math"', doc)
        # المصدران في الترويسة
        headers = " ".join(v for k, v in xml.items() if k.startswith("word/header"))
        content = self.db.exam_sections_content(self.ids["exam"])
        self.assertIn(content["quant"]["source"], headers)
        self.assertIn(content["verbal"]["source"], headers)
        # الخط Calibri
        self.assertIn('w:ascii="Calibri"', doc)
        self.assertIn('w:cs="Calibri"', doc)
        # المعادلات صور مع مصدرها في الوصف
        self.assertIn('descr="\\frac{1}{3}"', doc)
        self.assertGreater(len([n for n in z.namelist() if n.startswith("word/media/")]), 5)
        # فواصل الأعمدة = عدد الأعمدة - ١ (وضع مطابق لـ PDF)
        ncols = len(self.export_plan())
        self.assertEqual(doc.count('w:type="column"'), ncols - 1)
        # علامة النسبة المئوية ⁒ بخط مضمَّن
        self.assertIn("⁒", doc)
        self.assertTrue(any(n.startswith("word/fonts/") for n in z.namelist()))
        self.assertIn("embedTrueTypeFonts", xml["word/settings.xml"])
        # لا أرقام لاتينية في نصوص الأسئلة (الوضع الافتراضي هندي)
        texts = [t for t in para_texts(doc) if re.match(r"^[٠-٩]+:", t)]
        self.assertTrue(texts)
        for t in texts:
            self.assertIsNone(re.search(r"[0-9]", t), t)

    def export_plan(self):
        content = self.db.exam_sections_content(self.ids["exam"])
        res, _, _ = self.layout([content["quant"], content["verbal"]])
        return res["layout"]["plan"]

    def test_teacher_copy_marks_each_answer(self):
        _, files = self.export("teacher", ("docx",))
        xml, _ = docx_xml(files["docx"])
        fill = self.db.get_settings()["correct_fill"].lstrip("#")
        content = self.db.exam_sections_content(self.ids["exam"])
        n = len(helpers.flatten_qids(content["quant"]["items"])) + len(helpers.flatten_qids(content["verbal"]["items"]))
        # خليتان مظللتان لكل سؤال (الرمز والنص)
        self.assertEqual(xml["word/document.xml"].count('w:fill="%s"' % fill), 2 * n)

    def test_answer_key_matches(self):
        _, files = self.export("key", ("docx", "pdf"))
        xml, _ = docx_xml(files["docx"])
        texts = [t for t in para_texts(xml["word/document.xml"]) if t]
        letters = {"a": "أ", "b": "ب", "c": "جـ", "d": "د"}
        content = self.db.exam_sections_content(self.ids["exam"])
        expected = []
        for sec in (content["quant"], content["verbal"]):
            for it in sec["items"]:
                for q in (it.get("children") if it["type"] == "group" else [it]):
                    expected.append(letters[q["answer"]])
        got = [texts[k + 1] for k, t in enumerate(texts[:-1]) if re.fullmatch(r"[٠-٩]+", t)]
        self.assertEqual(got, expected)
        self.assertTrue(files["pdf"].startswith(b"%PDF"))

    def test_flow_mode_and_settings_effect(self):
        old = self.db.get_settings()
        try:
            self.db.save_settings({"word_layout_mode": "flow", "digits": "western", "numbering": "continuous", "end_text": "نهاية الاختبار التجريبية"})
            _, files = self.export("student", ("docx",))
            xml, _ = docx_xml(files["docx"])
            doc = xml["word/document.xml"]
            self.assertEqual(doc.count('w:type="column"'), 0)
            texts = para_texts(doc)
            nums = [m for t in texts for m in re.findall(r"^([0-9]+):", t)]
            self.assertEqual(nums, [str(i) for i in range(1, len(nums) + 1)])
            self.assertGreater(len(nums), 20)
            self.assertIn("نهاية الاختبار التجريبية", " ".join(texts))
        finally:
            self.db.save_settings({k: old[k] for k in ("word_layout_mode", "digits", "numbering", "end_text")})

    def test_long_passage_splits_only_at_paragraph_boundaries(self):
        sid = self.db.create_section("نص طويل", "verbal", "اختبار")
        paras = ["(%d) " % (k + 1) + ("هذه فقرة طويلة من نص القراءة لاختبار التوزيع بين نصفي الصفحة عند حدود الفقرات فقط. " * 4) for k in range(9)]
        self.db.create_item(sid, {"type": "group", "group_kind": "reading", "data": {"passage_type": "long", "numbered": False, "paragraphs": paras},
                                  "children": [{"type": "question", "category": "reading", "answer": "a",
                                                "data": {"stem": "سؤال عن النص", "options_type": "short", "options": ["١", "٢", "٣", "٤"]}}]})
        import db as dbm
        section = dbm.strip_section(self.db.get_section(sid, with_items=True))
        res, _, _ = self.layout([section])
        lay = res["layout"]
        blocks = {b["id"]: b for b in lay["blocks"]}
        cols_with_passage = [[blocks[e["id"]]["index"] for e in col if blocks[e["id"]]["type"] == "passage"] for col in lay["plan"]]
        cols_with_passage = [c for c in cols_with_passage if c]
        self.assertGreaterEqual(len(cols_with_passage), 2, "النص يجب أن يتوزع على أكثر من نصف")
        flat = [i for c in cols_with_passage for i in c]
        self.assertEqual(flat, list(range(9)), "الفقرات بترتيبها وكل فقرة كاملة في نصف واحد")
        self.assertEqual(lay["overflow"], [])
        # الأسئلة بعد النص
        order = [blocks[e["id"]]["type"] for col in lay["plan"] for e in col]
        self.assertLess(max(k for k, t in enumerate(order) if t == "passage"), order.index("question"))

    def test_preview_endpoint(self):
        r = helpers.http("POST", "/api/exams/%d/preview" % self.ids["exam"])
        self.assertTrue(r["ok"], r.get("error"))
        pdf = helpers.download(r["data"]["url"].split("?")[0])
        self.assertTrue(pdf.startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
