# -*- coding: utf-8 -*-
"""
اختبارات محرك المعادلات العربية: تُنفَّذ داخل المتصفح نفسه المستخدم في التصدير، وتفحص المواضع الهندسية الفعلية:
الأس على يسار الأساس، علامة الجذر معكوسة وخطها يمتد يسارًا، ترتيب أرقام العدد، البسط فوق المقام، عكس رموز العلاقات،
موضع علامة النسبة المئوية ⁒، والأرقام الهندية.
"""
import unittest

import helpers

SKIP = not helpers.playwright_available()


@unittest.skipIf(SKIP, "Playwright غير مثبت")
class MathTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        base, _ = helpers.server()
        cls.pw = sync_playwright().start()
        try:
            cls.browser = cls.pw.chromium.launch()
        except Exception:
            cls.browser = cls.pw.chromium.launch(channel="msedge")
        cls.page = cls.browser.new_page()
        cls.page.goto(base + "/static/shared/export.html")
        cls.page.wait_for_function("window.QExportReady === true")
        cls.page.evaluate("() => QExport.loadFonts()")

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def lay(self, latex, digits="hindi"):
        return self.page.evaluate(
            """([t, dg]) => { const b = QMath.layout(QMath.parse(t), {size: 20, family: QRender.fontStack({}), digits: dg, percent: '\\u2052', decimal: 'arabic', fracScale: 0.82});
                 return {w: b.w, a: b.a, d: b.d, items: b.items}; }""", [latex, digits])

    def texts(self, box):
        return [it for it in box["items"] if it["k"] == "t"]

    def find(self, box, s):
        for it in self.texts(box):
            if it["s"] == s:
                return it
        self.fail("لم يوجد النص %r في %r" % (s, [t["s"] for t in self.texts(box)]))

    # ------------------------------------------------------------------
    def test_multi_digit_number_order_kept_and_hindi(self):
        b = self.lay("1234")
        self.assertEqual([t["s"] for t in self.texts(b)], ["١٢٣٤"])
        b = self.lay("1234", "western")
        self.assertEqual([t["s"] for t in self.texts(b)], ["1234"])

    def test_decimal_separator(self):
        b = self.lay("3.25")
        self.assertEqual(self.texts(b)[0]["s"], "٣٫٢٥")

    def test_exponent_left_of_base(self):
        b = self.lay("س^{2}")
        base = self.find(b, "س")
        sup = self.find(b, "٢")
        self.assertLess(sup["x"], base["x"], "الأس يجب أن يكون على يسار الأساس")
        self.assertLess(sup["y"], base["y"], "الأس يجب أن يكون مرفوعًا")
        self.assertLess(sup["size"], base["size"])

    def test_rtl_sequence(self):
        b = self.lay("2س + 1")
        two = self.find(b, "٢")
        s = self.find(b, "س")
        plus = self.find(b, "+")
        one = self.find(b, "١")
        self.assertTrue(two["x"] > s["x"] > plus["x"] > one["x"], "الترتيب من اليمين إلى اليسار")

    def test_fraction_stacking(self):
        b = self.lay("\\frac{3}{4}")
        num = self.find(b, "٣")
        den = self.find(b, "٤")
        bar = [it for it in b["items"] if it["k"] == "r"][0]
        self.assertLess(num["y"], bar["y"])
        self.assertGreater(den["y"], bar["y"] + bar["h"])
        self.assertAlmostEqual(num["x"], den["x"], delta=2)

    def test_mirrored_radical(self):
        b = self.lay("\\sqrt{20}")
        body = self.find(b, "٢٠")
        paths = [it for it in b["items"] if it["k"] == "p"]
        bar = [it for it in b["items"] if it["k"] == "r"][0]
        xs = [c[1] for p in paths for c in p["cmds"] if c[0] in ("M", "L")]
        sign_left = min(xs)
        # العلامة على يمين ما تحت الجذر
        self.assertGreaterEqual(sign_left, body["x"] + 0.5)
        # الخط العلوي يبدأ من أعلى العلامة ويمتد يسارًا فوق العدد
        self.assertLessEqual(bar["x"], body["x"])
        self.assertGreaterEqual(bar["x"] + bar["w"], sign_left - 1)
        # الذيل الصغير في أقصى اليمين (بداية الجذر)
        tick_start = paths[0]["cmds"][0]
        self.assertAlmostEqual(tick_start[1], max(xs), delta=0.01)

    def test_nth_root_index_on_right(self):
        b = self.lay("\\sqrt[3]{27}")
        idx = self.find(b, "٣")
        body = self.find(b, "٢٧")
        self.assertGreater(idx["x"], body["x"])
        self.assertLess(idx["size"], body["size"])

    def test_relations_mirrored(self):
        b = self.lay("س < ص")
        self.assertIn(">", [t["s"] for t in self.texts(b)])
        b = self.lay("س \\le ص")
        self.assertIn("≥", [t["s"] for t in self.texts(b)])

    def test_percent_sign_left_of_number(self):
        b = self.lay("40\\%")
        num = self.find(b, "٤٠")
        pc = self.find(b, "⁒")
        self.assertLess(pc["x"], num["x"])

    def test_negative_sign_on_right(self):
        b = self.lay("-0.8")
        minus = self.find(b, "−")
        num = self.find(b, "٠٫٨")
        self.assertGreater(minus["x"], num["x"])

    def test_mixed_arabic_text(self):
        b = self.lay("40\\% من 60")
        self.assertGreater(self.find(b, "٤٠")["x"], self.find(b, "من")["x"])
        self.assertGreater(self.find(b, "من")["x"], self.find(b, "٦٠")["x"])

    def test_complex_expression_renders(self):
        for t in ["\\frac{\\sqrt{8} - \\sqrt{18}}{\\sqrt{2}}", "\\left(\\frac{1}{2}\\right)^{3}", "33\\frac{1}{3}\\%", "\\overline{أب}", "\\overarc{م ن}",
                  "س_{1} + س_{2}", "\\sqrt{\\frac{س}{4}}", "64 - 16 \\div (2 \\times 4)"]:
            r = self.page.evaluate("(t) => { const r = QMath.render(t, {size: 18, family: QRender.fontStack({}), digits: 'hindi'}); return {e: r.error || null, w: r.width, h: r.height}; }", t)
            self.assertIsNone(r["e"], t)
            self.assertGreater(r["w"], 5, t)

    def test_parse_errors_reported(self):
        for t in ["\\frac{1}", "\\sqrt{2", "{س"]:
            r = self.page.evaluate("(t) => QMath.validate(t)", t)
            self.assertTrue(r, t)

    def test_png_matches_svg_size(self):
        r = self.page.evaluate("""() => { const o = {size: 18, family: QRender.fontStack({}), digits: 'hindi'};
            const b = QMath.layout(QMath.parse('\\\\frac{1}{3}'), o); const s = QMath.toSVG(b, o); const p = QMath.toPNG(b, o, 4);
            return {sw: s.width, sh: s.height, pw: p.width, ph: p.height, sd: s.descent, pd: p.descent}; }""")
        self.assertEqual((r["sw"], r["sh"], r["sd"]), (r["pw"], r["ph"], r["pd"]))


if __name__ == "__main__":
    unittest.main()
