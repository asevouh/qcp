# -*- coding: utf-8 -*-
"""
اختبار شامل عبر الواجهة الحقيقية (Playwright) يحاكي سيناريو القبول في المواصفات:
قسم كمي ١١ سؤالًا (مقارنة + رسم هندسي + رسم بياني مشترك + معادلات) ← قسم لفظي ١٣ سؤالًا (كل التصنيفات + نص طويل)
← تبديل ترتيب سؤالين ← إنشاء اختبار ← معاينة ← تصدير Word وPDF ← إعادة فتح البرنامج والتحقق من بقاء البيانات.

التشغيل:  python tests/e2e_ui_test.py
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
APP = os.path.join(ROOT, "app")
sys.path.insert(0, APP)

def _free_port():
    import socket
    sk = socket.socket()
    sk.bind(("127.0.0.1", 0))
    p = sk.getsockname()[1]
    sk.close()
    return p


PORT = int(os.environ.get("E2E_PORT") or _free_port())
BASE = "http://127.0.0.1:%d/" % PORT


def set_port(p):
    global PORT, BASE
    PORT = p
    BASE = "http://127.0.0.1:%d/" % p
OUT = os.environ.get("E2E_OUT") or os.path.join(tempfile.gettempdir(), "qudurat_e2e")


def start_server(data_dir):
    p = subprocess.Popen([sys.executable, os.path.join(APP, "server.py"), "--port", str(PORT), "--data", data_dir, "--no-browser"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(120):
        try:
            # نتأكد أن الخادم الذي يجيب هو خادمنا (بيانات المجلد المؤقت نفسه)
            if os.path.abspath(api("/api/system")["data_dir"]) == os.path.abspath(data_dir):
                return p
        except Exception:
            pass
        time.sleep(0.25)
    p.terminate()
    raise RuntimeError("server did not start on port %d" % PORT)


def api(path):
    with urllib.request.urlopen(BASE + path.lstrip("/")) as r:
        return json.loads(r.read().decode("utf-8"))["data"]


def make_images(d):
    import sample_data as sd
    paths = {}
    for n, fn in (("chart", sd.make_chart_png), ("triangle", sd.make_triangle_png), ("circles", sd.make_circles_png)):
        p = os.path.join(d, n + ".png")
        with open(p, "wb") as f:
            f.write(fn())
        paths[n] = p
    return paths


class Runner:
    def __init__(self, page):
        self.pg = page
        self.errors = []
        page.on("pageerror", lambda e: self.errors.append(str(e)))
        page.on("console", lambda m: self.errors.append(m.text) if m.type == "error" else None)

    def wait_saved(self):
        pg = self.pg
        pg.wait_for_timeout(250)
        pg.wait_for_function("() => { const s=document.querySelector('.save-state'); return !s || !/pending|saving/.test(s.className); }", timeout=15000)

    def rich(self, idx, text, scope=".editor-pane"):
        areas = self.pg.locator(scope + " .rich-area")
        a = areas.nth(idx)
        a.click()
        self.pg.keyboard.press("End")
        self.pg.keyboard.type(text)

    def math_in_rich(self, idx, steps, scope=".editor-pane"):
        """steps: list of ('btn', label) | ('type', text) | ('tab',) | ('src', latex)"""
        rich = self.pg.locator(scope + " .rich").nth(idx)
        rich.locator(".rich-area").click()
        self.pg.keyboard.press("End")
        rich.locator("button", has_text="معادلة").click()
        dlg = self.pg.locator(".modal", has_text="إدراج معادلة")
        dlg.wait_for()
        for st in steps:
            if st[0] == "btn":
                dlg.locator(".palette button", has_text=st[1]).first.click()
            elif st[0] == "type":
                self.pg.keyboard.type(st[1])
            elif st[0] == "tab":
                self.pg.keyboard.press("Tab")
            elif st[0] == "src":
                dlg.locator("textarea").fill(st[1])
        dlg.locator("button", has_text="إدراج").click()
        dlg.wait_for(state="detached")

    def answer(self, k):
        self.pg.locator(".editor-pane .ans-pick").nth(k).click()

    def options(self, texts, start_idx=1):
        for i, t in enumerate(texts):
            self.rich(start_idx + i, t)

    def add(self, label):
        self.pg.locator(".add-bar button", has_text=label).click()
        self.pg.wait_for_timeout(500)
        self.wait_saved()

    def count_questions(self):
        sid = int(self.pg.evaluate("() => location.hash.split('/').pop()"))
        return api("/api/sections/%d" % sid)["question_count"]


def run():
    from playwright.sync_api import sync_playwright
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    data_dir = os.path.join(OUT, "data")
    imgs = make_images(OUT)
    srv = start_server(data_dir)
    report = {"steps": []}

    def step(name, ok=True, info=""):
        report["steps"].append({"step": name, "ok": ok, "info": info})
        print(("✔ " if ok else "✘ ") + name + (" — " + info if info else ""))

    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            ctx = b.new_context(viewport={"width": 1440, "height": 950}, accept_downloads=True)
            pg = ctx.new_page()
            R = Runner(pg)

            # ---------------------------------------------------------- الترخيص عند أول تشغيل
            pg.goto(BASE)
            pg.wait_for_selector(".lic-text")
            acc = pg.locator("button", has_text="أوافق — متابعة")
            blocked = acc.is_disabled() and pg.locator(".lic-ack input").is_disabled() and pg.locator(".shell").count() == 0
            pg.locator(".lic-text").evaluate("e => { e.scrollTop = e.scrollHeight; e.dispatchEvent(new Event('scroll')); }")
            pg.locator(".lic-ack input").check()
            acc.click()
            pg.wait_for_selector(".shell")
            step("أول تشغيل: لا يفتح البرنامج إلا بعد قراءة الترخيص حتى نهايته والإقرار بقبوله", blocked)

            # ---------------------------------------------------------- قسم كمي
            pg.goto(BASE + "#/sections/new")
            pg.wait_for_selector("text=إنشاء قسم جديد")
            pg.locator("input.input").first.fill("القسم الكمي — اختبار القبول")
            pg.locator(".choice", has_text="كمي").click()
            pg.locator("input[list=srcs3]").fill("أقسام دورة أ. محمود المنصف تدريب")
            pg.locator("button", has_text="إنشاء القسم والمتابعة").click()
            pg.wait_for_selector(".sec-top")
            step("إنشاء قسم كمي بعنوان ومصدر")

            # ١: سؤال اعتيادي بكسر
            R.add("سؤال اعتيادي")
            R.rich(0, "ما قيمة ")
            R.math_in_rich(0, [("btn", "كسر"), ("type", "3"), ("tab",), ("type", "4")])
            R.rich(0, " من 100 ؟")
            R.options(["75", "50", "25", "34"])
            R.answer(0)
            R.wait_saved()
            # ٢: مقارنة
            R.add("سؤال اعتيادي")
            R.rich(0, "قارن بين:")
            pg.locator(".editor-pane button", has_text="مقارنة بين قيمتين").click()
            R.rich(1, "40% من 60")
            R.rich(2, "60% من 40")
            R.answer(2)
            R.wait_saved()
            # ٣: جذر وأس ومتغير عربي
            R.add("سؤال اعتيادي")
            R.rich(0, "إذا كان ")
            R.math_in_rich(0, [("src", "س^{2} = 20")])
            R.rich(0, " ، فما قيمة ")
            R.math_in_rich(0, [("btn", "جذر"), ("type", "س^{2}")])
            R.rich(0, " ؟")
            R.math_in_rich(1, [("src", "2\\sqrt{5}")])
            R.math_in_rich(2, [("src", "\\sqrt[3]{20}")])
            R.math_in_rich(3, [("src", "4\\sqrt{5}")])
            R.math_in_rich(4, [("src", "10")])
            R.answer(0)
            R.wait_saved()
            # ٤: رسم هندسي
            R.add("سؤال رسم هندسي")
            R.rich(0, "في الشكل المجاور: المثلث أ ب جـ، أوجد مساحته.")
            pg.locator(".editor-pane .img-field input[type=file]").set_input_files(imgs["triangle"])
            pg.wait_for_selector(".editor-pane .img-field img")
            R.options(["48", "96", "24", "64"])
            R.answer(0)
            R.wait_saved()
            # ٥–٦: رسم بياني مشترك
            R.add("رسم بياني مع أسئلته")
            pg.locator(".editor-pane .img-field input[type=file]").set_input_files(imgs["chart"])
            pg.wait_for_selector(".editor-pane .img-field img")
            pg.locator(".editor-pane input.input").first.fill("توزيع الفئات العمرية")
            R.wait_saved()
            pg.locator(".qchildren .qrow").first.click()
            pg.wait_for_timeout(300)
            R.rich(0, "بناءً على الرسم أعلاه، ما الفئة العمرية الأكثر عددًا؟")
            R.options(["من 16 إلى 20", "من 21 إلى 25", "من 26 إلى 30", "من 31 إلى 35"])
            R.answer(2)
            R.wait_saved()
            pg.locator(".qchildren button", has_text="سؤال لهذه المجموعة").click()
            pg.wait_for_timeout(500)
            R.rich(0, "ما النسبة المئوية للفئة من 10 إلى 15 تقريبًا؟")
            R.options(["5%", "10%", "15%", "20%"])
            R.answer(0)
            R.wait_saved()
            # ٧: خيارات طويلة جدًا
            R.add("سؤال اعتيادي")
            R.rich(0, "أي العبارات الآتية صحيحة دائمًا؟")
            pg.locator(".editor-pane button", has_text="خيارات طويلة").click()
            R.options(["مجموع أي عددين صحيحين موجبين أكبر من حاصل ضربهما في جميع الحالات دون استثناء",
                       "حاصل ضرب أي عددين صحيحين متتاليين هو عدد زوجي دائمًا مهما كان العددان",
                       "الفرق بين أي عددين صحيحين موجبين هو عدد موجب دائمًا",
                       "ناتج قسمة أي عدد زوجي على ٢ هو عدد زوجي"])
            R.answer(1)
            R.wait_saved()
            # ٨–١١: أسئلة اعتيادية
            for k, (stem, ops) in enumerate([
                ("إذا كان ن عدد طبيعي، أوجد متوسط: ن ، ن + 2 ، ن + 10", ["ن + 4", "3ن + 12", "ن + 5", "ن + 3"]),
                ("كم عدد الأعداد الزوجية بين 1 و 100؟", ["49", "50", "51", "48"]),
                ("ما ناتج 64 − 16 ÷ (2 × 4) ؟", ["6", "62", "8", "56"]),
                ("سيارة تقطع 120 كم في ساعتين، كم تقطع في 5 ساعات؟", ["300", "240", "360", "250"]),
            ]):
                R.add("سؤال اعتيادي")
                R.rich(0, stem)
                R.options(ops)
                R.answer([0, 0, 1, 0][k])
                R.wait_saved()
            # تعديل معادلة موجودة بالنقر عليها
            pg.locator(".qitem.top").nth(0).locator(".qrow").first.click()
            pg.wait_for_timeout(400)
            pg.locator(".editor-pane .mchip").first.click()
            dlg = pg.locator(".modal", has_text="تعديل معادلة")
            dlg.wait_for()
            dlg.locator("textarea").fill("\\frac{3}{5}")
            dlg.locator("button", has_text="تحديث المعادلة").click()
            R.wait_saved()
            first_stem = api("/api/sections/%d" % int(pg.evaluate("() => location.hash.split('/').pop()")))["items"][0]["data"]["stem"]
            step("تعديل معادلة موجودة بالنقر عليها", "<m>\\frac{3}{5}</m>" in first_stem, first_stem)
            nq = R.count_questions()
            step("إضافة ١١ سؤالًا كميًا (كسر، مقارنة، جذر وأس، هندسي، رسم بياني مشترك، خيارات طويلة)", nq == 11, "العدد=%d" % nq)
            qid = int(pg.evaluate("() => location.hash.split('/').pop()"))
            sec = api("/api/sections/%d" % qid)
            drafts = [it for it in sec["items"] if it["type"] == "question" and it["status"] != "complete"]
            step("كل الأسئلة الكمية مكتملة ومحفوظة", not drafts, "مسودات=%d" % len(drafts))

            # ---------------------------------------------------------- قسم لفظي
            pg.goto(BASE + "#/sections/new")
            pg.wait_for_selector("text=إنشاء قسم جديد")
            pg.locator("input.input").first.fill("القسم اللفظي — اختبار القبول")
            pg.locator(".choice", has_text="لفظي").click()
            pg.locator("input[list=srcs3]").fill("أقسام العراب (ملف زيتونة)")
            pg.locator("button", has_text="إنشاء القسم والمتابعة").click()
            pg.wait_for_selector(".sec-top")
            # ١–٣ تناظر
            for a, bb, pairs, ans in [
                ("حروف", "كلمات", [("أغصان", "أشجار"), ("قفز", "وثب"), ("قاضي", "العدل"), ("ذهب", "معادن")], 0),
                ("الكف", "المنع", [("اليد", "القبض"), ("النور", "الضياء"), ("القبض", "البسط"), ("شتاء", "خريف")], 1),
                ("سفر", "مشقة", [("استقرار", "راحة"), ("استيطان", "خوف"), ("علم", "ترحال"), ("سفر", "تذكرة")], 0),
            ]:
                R.add("تناظر لفظي")
                ins = pg.locator(".editor-pane input.input")
                ins.nth(0).fill(a)
                ins.nth(1).fill(bb)
                for i, (x, y) in enumerate(pairs):
                    ins.nth(2 + 2 * i).fill(x)
                    ins.nth(3 + 2 * i).fill(y)
                R.answer(ans)
                R.wait_saved()
            # ٤–٥ إكمال جمل (فراغان)
            R.add("إكمال جمل")
            R.rich(0, "ليس العيب أن ")
            pg.locator(".editor-pane .rich").first.locator("button", has_text="إضافة فراغ").click()
            R.rich(0, " ، ولكن العيب ألا تستطيع ")
            pg.locator(".editor-pane .rich").first.locator("button", has_text="إضافة فراغ").click()
            R.rich(0, " .")
            R.options(["تسقط - النهوض", "تقع - الارتفاع", "تسرق - الهروب", "الثبور - البور"])
            R.answer(0)
            R.wait_saved()
            stem_saved = api("/api/sections/%d" % (qid + 1))["items"][-1]["data"]["stem"]
            step("زر «إضافة فراغ» يدرج ثماني نقاط في موضع المؤشر (فراغان)", stem_saved.count("........") == 2, stem_saved)
            R.add("إكمال جمل")
            R.rich(0, "القرار هو الاختيار الذي تم التوصل إليه بعد ")
            pg.locator(".editor-pane .rich").first.locator("button", has_text="إضافة فراغ").click()
            R.rich(0, " بين عدة اختيارات.")
            R.options(["المناقشة", "الجمع", "المراقبة", "المفاضلة"])
            R.answer(3)
            R.wait_saved()
            # ٦ مفردة شاذة
            R.add("مفردة شاذة")
            R.options(["ظرافة", "سفه", "طيش", "حماقة"], start_idx=0)
            R.answer(0)
            R.wait_saved()
            # ٧–٨ خطأ سياقي (مع كلمة مكررة)
            for sentence, words, ans in [
                ("إن للتعلم مرارة لن يذوقها إلا من ذاق مرارته.", ["مرارة", "يذوقها", "ذاق", "مرارته"], 0),
                ("العلم نور والجهل ظلام، والعلم يرفع أهله والجهل يرفع أهله.", ["نور", "ظلام", "يرفع", None], 3),
            ]:
                R.add("خطأ سياقي")
                ta = pg.locator(".editor-pane textarea").first
                ta.fill(sentence)
                pos = 0
                for w in words:
                    if w is None:
                        # الكلمة المكررة الثانية "يرفع"
                        k = sentence.rfind("يرفع")
                        start, end = k, k + len("يرفع")
                    else:
                        start = sentence.find(w, pos)
                        end = start + len(w)
                        pos = end
                    pg.evaluate("([s,e]) => { const t=document.querySelector('.editor-pane textarea'); t.focus(); t.setSelectionRange(s,e); }", [start, end])
                    pg.locator(".editor-pane button", has_text="إضافة الكلمة المحددة").click()
                R.answer(ans)
                R.wait_saved()
            ctx_items = [it for it in api("/api/sections/%d" % (qid + 1))["items"] if it.get("category") == "context"]
            sels = ctx_items[-1]["data"]["selections"]
            dup_ok = len(sels) == 4 and sels[2]["text"] == "يرفع" and sels[3]["text"] == "يرفع" and sels[2]["start"] != sels[3]["start"]
            step("الخطأ السياقي: تحديد ٤ كلمات بمواضعها (مع تكرار الكلمة نفسها)", dup_ok, json.dumps([(s["text"], s["start"]) for s in sels], ensure_ascii=False))
            # ٩–١٠ نص قصير
            R.add("نص استيعاب مع أسئلته")
            R.rich(0, "الكريم يلين عندما يُستَعطف، واللئيم يقسو عندما يُستلطف.")
            R.wait_saved()
            pg.locator(".qchildren .qrow").last.click()
            pg.wait_for_timeout(300)
            R.rich(0, "تؤكد العبارة على أن:")
            pg.locator(".editor-pane button", has_text="خيارات طويلة").click()
            R.options(["الاستلطاف يقسي الكريم", "القوة تلين الكريم", "القسوة تلين اللئيم", "الاستعطاف يقسي اللئيم"])
            R.answer(3)
            R.wait_saved()
            pg.locator(".qchildren").last.locator("button", has_text="سؤال لهذه المجموعة").click()
            pg.wait_for_timeout(500)
            R.rich(0, "كم تضاد في النص؟")
            R.options(["1", "2", "3", "4"])
            R.answer(1)
            R.wait_saved()
            # ١١–١٣ نص طويل متعدد الفقرات
            R.add("نص استيعاب مع أسئلته")
            pg.locator(".editor-pane button", has_text="نص طويل").click()
            paras = [
                "الإمام مالك بن أنس -رحمه الله- آتاه الله بسطة في العلم والجسم والخلق، وهي صفات نادرة، وقد اختار أن يكون درسه في مسجد رسول الله ﷺ، ذلك المسجد الذي تشد إليه الرحال.",
                "وقد ولد في أسرة اشتهرت بالرواية، ونشأ بين رواة محدثين، ولذلك اتجه بعد أن حفظ القرآن الكريم إلى طلب علم الرواية والفقه، ثم اتجه عند نضجه إلى التدريس.",
                "إن تلك المكانة ما جاءته عفوًا، بل لها أسباب من نشأته ومن جهوده ومن شيوخه ومن شخصه، مما أدى إلى فيض علمه الغزير واستنباطه الفقهي السليم.",
                "وكانت للمدينة أيضًا تلك المنزلة العلمية في العهد الأموي؛ إذ كانت مهد السنن والفتاوى المأثورة، حتى كان الخليفة عمر بن عبد العزيز يكتب إلى أهلها يسألهم.",
            ]
            R.rich(0, paras[0])
            for t in paras[1:]:
                pg.locator(".editor-pane button", has_text="إضافة فقرة").click()
                pg.wait_for_timeout(150)
                n = pg.locator(".editor-pane .para-card").count()
                R.rich(n - 1, t)
            R.wait_saved()
            pg.locator(".qchildren").last.locator(".qrow").first.click()
            pg.wait_for_timeout(300)
            R.rich(0, "يفهم من الفقرة (4) أن المدينة كانت:")
            R.options(["مدينة علمية", "مكان هجرة", "مركزًا اقتصاديًا", "عاصمة سياسية"])
            R.answer(0)
            R.wait_saved()
            for stem, ops, ans in [("أي الآتي يمكن استنتاجه من الفقرة (1)؟", ["مكانة الإمام العلمية", "بعد المسجد", "كثرة المساجد", "تدبير الدولة"], 0),
                                   ("سبب مكانة الإمام كما في الفقرة (3):", ["نشأته وجهوده وشيوخه", "ثراؤه", "منصبه", "سفره"], 0)]:
                pg.locator(".qchildren").last.locator("button", has_text="سؤال لهذه المجموعة").click()
                pg.wait_for_timeout(500)
                R.rich(0, stem)
                R.options(ops)
                R.answer(ans)
                R.wait_saved()
            nv = R.count_questions()
            step("إضافة ١٣ سؤالًا لفظيًا من كل التصنيفات مع نص طويل متعدد الفقرات", nv == 13, "العدد=%d" % nv)
            vid = qid + 1

            # ---------------------------------------------------------- تبديل ترتيب سؤالين
            before = [it["id"] for it in api("/api/sections/%d" % vid)["items"]]
            pg.locator(".qitem.top").nth(0).locator(".acts button[title='للأسفل']").click()
            pg.wait_for_timeout(700)
            after = [it["id"] for it in api("/api/sections/%d" % vid)["items"]]
            step("تبديل ترتيب سؤالين بزر التحريك دون إعادة إدخالهما", after[0] == before[1] and after[1] == before[0] and sorted(after) == sorted(before))
            # سحب وإفلات: نقل الأول إلى الموضع الثالث
            handle = pg.locator(".qitem.top").nth(0).locator(".handle")
            target = pg.locator(".qitem.top").nth(2)
            hb = handle.bounding_box()
            tb = target.bounding_box()
            pg.mouse.move(hb["x"] + hb["width"] / 2, hb["y"] + hb["height"] / 2)
            pg.mouse.down()
            for k in range(12):
                pg.mouse.move(hb["x"] + hb["width"] / 2, hb["y"] + (tb["y"] + tb["height"] * 0.8 - hb["y"]) * (k + 1) / 12)
                pg.wait_for_timeout(30)
            pg.mouse.up()
            pg.wait_for_timeout(900)
            after2 = [it["id"] for it in api("/api/sections/%d" % vid)["items"]]
            step("إعادة الترتيب بالسحب والإفلات تُحفظ بصورة دائمة", after2 != after and sorted(after2) == sorted(before), str(after2[:4]))

            # ---------------------------------------------------------- إنشاء الاختبار والتصدير
            pg.goto(BASE + "#/exams/new")
            pg.wait_for_selector("text=بيانات الاختبار")
            pg.locator("input[placeholder='مثال: الاختبار الخامس']").fill("اختبار القبول")
            pg.locator("input[placeholder='مثال: ٥']").fill("٥")
            pg.locator("select").nth(0).select_option(str(qid))
            pg.locator("select").nth(1).select_option(str(vid))
            pg.wait_for_timeout(300)
            total_txt = pg.locator(".badge", has_text="إجمالي الأسئلة").inner_text()
            step("اختيار القسمين يعرض العنوان والمصدر والعدد والإجمالي", "٢٤" in total_txt, total_txt)
            pg.locator("button", has_text="حفظ الاختبار").click()
            pg.wait_for_timeout(600)
            pg.locator("button", has_text="معاينة المستند").click()
            pg.wait_for_selector("iframe.pdf-frame", timeout=60000)
            step("معاينة المستند (PDF الفعلي داخل البرنامج)")
            pg.locator(".modal-head button", has_text="✕").click()
            # تعديل القسم ثم العودة إلى الاختبار
            exam_hash = pg.evaluate("() => location.hash")
            pg.locator("button", has_text="تعديل هذا القسم").first.click()
            pg.wait_for_selector(".sec-top")
            pg.locator("a", has_text="العودة إلى الاختبار").click()
            pg.wait_for_selector("text=بيانات الاختبار")
            pg.wait_for_timeout(500)
            step("تعديل القسم من صفحة الاختبار ثم العودة إليها", pg.evaluate("() => location.hash") == exam_hash and
                 pg.locator("input[placeholder='مثال: الاختبار الخامس']").input_value() == "اختبار القبول")
            files = {}
            for label, ext in (("تصدير Word", "docx"), ("تصدير PDF", "pdf")):
                with pg.expect_download(timeout=90000) as dl:
                    pg.locator("button", has_text=label).click()
                    # قد تظهر نافذة ملاحظات قبل التصدير
                    try:
                        pg.locator(".modal-foot button", has_text="متابعة رغم ذلك").click(timeout=1500)
                    except Exception:
                        pass
                d = dl.value
                path = os.path.join(OUT, "acceptance." + ext)
                d.save_as(path)
                files[ext] = path
                pg.wait_for_timeout(400)
            step("تصدير Word وPDF من الواجهة", all(os.path.getsize(f) > 10000 for f in files.values()), json.dumps({k: os.path.getsize(v) for k, v in files.items()}))
            report["files"] = files
            report["section_ids"] = [qid, vid]
            report["ui_errors"] = R.errors[:20]
            step("لا أخطاء JavaScript في الواجهة أثناء السيناريو", not R.errors, "; ".join(R.errors[:3]))
            pg.screenshot(path=os.path.join(OUT, "exam_page.png"))
            b.close()
    finally:
        srv.terminate()
        srv.wait(10)

    # ---------------------------------------------------------- إعادة التشغيل والتحقق من البقاء
    set_port(_free_port())
    srv = start_server(data_dir)
    try:
        secs = api("/api/sections")
        exams = api("/api/exams")
        ok = len(secs) == 2 and len(exams) == 1 and sum(s["question_count"] for s in secs) == 24
        step("بعد إغلاق البرنامج وإعادة فتحه: الأقسام والاختبار والأسئلة موجودة", ok, "أقسام=%d اختبارات=%d" % (len(secs), len(exams)))
    finally:
        srv.terminate()
        srv.wait(10)
    with open(os.path.join(OUT, "e2e_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    failed = [s for s in report["steps"] if not s["ok"]]
    print("\nالنتيجة: %d خطوة ناجحة، %d فاشلة" % (len(report["steps"]) - len(failed), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(run())
