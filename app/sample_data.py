# -*- coding: utf-8 -*-
"""بيانات تجريبية شاملة تغطي جميع أنواع الأسئلة (تُستخدم في العرض التجريبي والاختبارات الآلية)."""
import io
import math

from PIL import Image, ImageDraw, ImageFont

GRAY = (90, 90, 90)


def _font(size, bold=False):
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    name = "ExamArabicFallback-Bold.ttf" if bold else "ExamArabicFallback-Regular.ttf"
    try:
        return ImageFont.truetype(os.path.join(here, "static", "fonts", name), size)
    except Exception:
        return ImageFont.load_default()


def _ar(t):
    """رسم نص عربي بسيط في الصور (أرقام هندية)."""
    return t


def make_chart_png():
    """رسم بياني بالأعمدة (تدرج رمادي) لتوزيع الفئات العمرية."""
    W, H = 900, 560
    im = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(im)
    left, right, top, bottom = 110, W - 40, 40, H - 110
    vals = [20, 56, 86, 98, 70, 72]
    labels = ["١٠-١٥", "١٦-٢٠", "٢١-٢٥", "٢٦-٣٠", "٣١-٣٥", "٣٦-٤٠"]
    vmax = 110
    f = _font(26)
    # خطوط الشبكة
    for v in range(0, vmax + 1, 10):
        y = bottom - (bottom - top) * v / vmax
        d.line([(left, y), (right, y)], fill=(215, 215, 215), width=2)
        txt = "".join("٠١٢٣٤٥٦٧٨٩"[int(c)] for c in str(v))
        tw = d.textlength(txt, font=f)
        d.text((left - 14 - tw, y - 16), txt, fill=(60, 60, 60), font=f)
    n = len(vals)
    slot = (right - left) / n
    for k, v in enumerate(vals):
        # من اليمين إلى اليسار
        x1 = right - slot * (k + 1) + slot * 0.22
        x2 = right - slot * k - slot * 0.22
        y = bottom - (bottom - top) * v / vmax
        d.rectangle([x1, y, x2, bottom], fill=(95, 95, 95))
        tw = d.textlength(labels[k], font=f)
        d.text(((x1 + x2) / 2 - tw / 2, bottom + 14), labels[k], fill=(40, 40, 40), font=f)
    d.line([(left, bottom), (right, bottom)], fill=(40, 40, 40), width=3)
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def make_triangle_png():
    W, H = 700, 560
    im = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(im)
    A, B, C = (120, 470), (600, 470), (420, 90)
    d.line([A, B, C, A], fill=(0, 0, 0), width=6, joint="curve")
    # الارتفاع
    D = (420, 470)
    d.line([C, D], fill=(0, 0, 0), width=4)
    d.rectangle([420, 445, 445, 470], outline=(0, 0, 0), width=3)
    f = _font(42, True)
    d.text((80, 470), "أ", font=f, fill=(0, 0, 0))
    d.text((612, 470), "ب", font=f, fill=(0, 0, 0))
    d.text((410, 30), "جـ", font=f, fill=(0, 0, 0))
    d.text((405, 480), "د", font=f, fill=(0, 0, 0))
    f2 = _font(36)
    d.text((440, 250), "٨ سم", font=f2, fill=(0, 0, 0))
    d.text((230, 480), "١٢ سم", font=f2, fill=(0, 0, 0))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def make_circles_png():
    W = H = 520
    im = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(im)
    c = (260, 260)
    for r, w in ((230, 6), (150, 6)):
        d.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], outline=(0, 0, 0), width=w)
    d.ellipse([c[0] - 12, c[1] - 12, c[0] + 12, c[1] + 12], fill=(0, 0, 0))
    d.line([(c[0] + 150, c[1]), (c[0] + 230, c[1])], fill=(80, 80, 80), width=5)
    f = _font(34)
    d.text((c[0] + 160, c[1] - 52), "٤ سم", font=f, fill=(0, 0, 0))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def make_numberline_png():
    W, H = 900, 200
    im = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(im)
    y = 120
    d.line([(40, y), (860, y)], fill=(0, 0, 0), width=5)
    xs = [60, 260, 460, 660, 840]
    names = ["", "ص", "ع", "ل", "س"]
    f = _font(40, True)
    for x, n in zip(xs, names):
        d.line([(x, y - 30), (x, y + 30)], fill=(0, 0, 0), width=5)
        if n:
            d.text((x - 12, y - 95), n, font=f, fill=(0, 0, 0))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def q(category, data, answer, **kw):
    out = {"type": "question", "category": category, "data": data, "answer": answer}
    out.update(kw)
    return out


def opts(*o, t="short"):
    return {"options_type": t, "options": list(o)}


def sample_quant(media):
    """media: dict name -> media_id"""
    items = [
        q("regular", {"stem": "قارن بين:", "options_type": "compare",
                      "compare": {"v1": "40% من 60", "v2": "60% من 40"}}, "c"),
        q("regular", dict(stem="هناك نقطتان: أ و جـ، قطع خالد نصف المسافة بين أ و جـ في دقيقة، وقطع ثلثي المتبقي في دقيقتين، وتبقى له 40 مترًا، ما المسافة بين النقطتين أ و جـ؟",
                          **opts("240", "200", "160", "80")), "a"),
        q("regular", dict(stem="ما النسبة المئوية للعدد <m>\\frac{1}{3}</m> ؟",
                          **opts("33%", "<m>33\\frac{1}{3}\\%</m>", "<m>\\frac{1}{3}\\%</m>", "33.3%")), "b"),
        q("regular", dict(stem="إذا كان <m>\\sqrt{20} \\times \\sqrt{5} = 2 \\times 5</m> ، فأوجد قيمة: <m>\\sqrt{5} + \\sqrt{20}</m>",
                          **opts("<m>5 + 2</m>", "<m>3\\sqrt{5}</m>", "<m>2\\sqrt{5}</m>", "<m>5\\sqrt{5}</m>")), "b"),
        q("regular", dict(stem="إذا كان <m>س^{2} + 2س + 1 = 0</m> ، فما قيمة <m>\\sqrt[3]{س^{3}}</m> ؟",
                          **opts("<m>-1</m>", "<m>1</m>", "<m>0</m>", "<m>2</m>")), "a"),
        {"type": "group", "group_kind": "chart", "data": {"title": "توزيع الفئات العمرية", "image": {"media_id": media["chart"], "width_cm": 7.6}},
         "children": [
             q("chart", dict(stem="بناءً على الرسم أعلاه، ما الفئة العمرية الأكثر عددًا؟", **opts("من ١٦ إلى ٢٠", "من ٢١ إلى ٢٥", "من ٢٦ إلى ٣٠", "من ٣١ إلى ٣٥")), "c"),
             q("chart", dict(stem="بناءً على الرسم نفسه، ما النسبة المئوية للفئة العمرية من 10 إلى 15 من المجموع <b>تقريبًا</b>؟", **opts("5%", "10%", "15%", "20%")), "a"),
         ]},
        q("geometry", dict(stem="في الشكل المجاور: المثلث أ ب جـ، فيه جـ د عمودي على أ ب، أوجد مساحة المثلث.",
                           image={"media_id": media["triangle"], "width_cm": 3.6}, image_placement="side",
                           **opts("٤٨ سم<m>^{2}</m>", "٩٦ سم<m>^{2}</m>", "٢٤ سم<m>^{2}</m>", "٦٤ سم<m>^{2}</m>")), "a"),
        q("regular", dict(stem="أيُّ العبارات الآتية صحيحة دائمًا لأي عددين صحيحين موجبين س، ص؟",
                          **opts("مجموع العددين أكبر من حاصل ضربهما", "حاصل ضرب العددين عدد زوجي",
                                 "مجموع العددين أكبر من أو يساوي ٢", "الفرق بين العددين عدد موجب", t="long")), "c"),
        q("regular", dict(stem="إذا كان <m>\\frac{س + ص}{12} = 3</m> و <m>س - ص = 6</m> ، فما قيمة س ؟",
                          **opts("21", "18", "15", "12")), "a"),
        q("regular", dict(stem="إذا كانت المسافة من س إلى ص = ١٢، والمسافات بين النقاط متساوية، قارن بين:", options_type="compare",
                          compare={"v1": "3", "v2": "<m>\\overline{س ل}</m>"}), "b"),
        q("regular", dict(stem="شخص يكتب على الكمبيوتر الأعداد من ٥ إلى ٢٠٠، كم مرة يضغط على أزرار الكمبيوتر؟ (اختر أدق وصف للطريقة الصحيحة في الحل)",
                          **opts("يحسب عدد الأعداد ذات الخانة الواحدة ثم ذات الخانتين ثم ذات الثلاث خانات ويجمع عدد الضغطات لكل مجموعة على حدة",
                                 "يضرب عدد الأعداد كلها في ثلاثة لأن أكبر عدد مكوَّن من ثلاث خانات",
                                 "يضرب عدد الأعداد كلها في اثنين لأن أغلب الأعداد مكوَّنة من خانتين",
                                 "يطرح أصغر عدد من أكبر عدد ثم يضيف واحدًا", t="long")), "a"),
        q("geometry", dict(stem="الشكل التالي: دائرتان متحدتا المركز، ما الفرق بين محيطي الدائرتين؟",
                           image={"media_id": media["circles"], "width_cm": 3.2}, image_placement="below",
                           **opts("<m>2ط</m>", "<m>4ط</m>", "<m>6ط</m>", "<m>8ط</m>")), "d"),
    ]
    return {"title": "قسم كمي تجريبي ١", "kind": "quant", "source": "أقسام دورة أ. محمود المنصف تدريب", "items": items}


def sample_verbal():
    long_paras = [
        "الإمام مالك بن أنس -رحمه الله- أتاه الله تعالى بسطة في العلم والجسم والخلق، وهي صفات نادرة. وقد اختار أن يكون درسه في مسجد رسول الله ﷺ، ذلك المسجد الذي تشد إليه الرحال، وأكبر حلقة علمية في ذلك التاريخ، وأختار أن يكون موضع جلوسه المكان الذي كان يجلس فيه عمر بن الخطاب رضي الله عنه.",
        "وقد ولد في أسرة اشتهرت بالرواية، ونشأ بين رواة محدثين، ولذلك اتجه، بعد أن حفظ القرآن الكريم، وتفصح بالعربية، إلى طلب علم الرواية والفقه. وبعد أن وعى ما أدركه من علم أهل عصره؛ اتجه عند نضجه إلى التدريس.",
        "إن تلك المكانة ما جاءته عفوًا، بل لها أسباب من نشأته، ومن جهوده، ومن شيوخه، ومن شخصه، مما أدى إلى فيض علمه الغزير، واستنباطه الفقهي السليم، وإدراك مصالح الناس والعلم بالقرآن والسنة، وتنقيح الرواية ونقدها بدراية عميقة مدركة.",
        "وكانت للمدينة أيضًا تلك المنزلة العلمية في العهد الأموي؛ إذ كانت مهد السنن والفتاوى المأثورة، حتى لقد كان الخليفة العادل عمر بن عبد العزيز -رحمه الله- يكتب إلى الأمصار يعلمهم السنن والفقه، ويكتب إلى أهل المدينة يسألهم عما مضى، ويعمل بما عندهم.",
    ]
    items = [
        q("analogy", {"pair": {"a": "حروف", "b": "كلمات"}, "options_type": "short",
                      "option_pairs": [{"a": "أغصان", "b": "أشجار"}, {"a": "قفز", "b": "وثب"}, {"a": "قاضي", "b": "العدل"}, {"a": "ذهب", "b": "معادن"}]}, "a"),
        q("analogy", {"pair": {"a": "الكف", "b": "المنع"}, "options_type": "short",
                      "option_pairs": [{"a": "اليد", "b": "القبض"}, {"a": "النور", "b": "الضياء"}, {"a": "القبض", "b": "البسط"}, {"a": "شتاء", "b": "خريف"}]}, "b"),
        q("analogy", {"pair": {"a": "سفر", "b": "مشقة"}, "options_type": "short",
                      "option_pairs": [{"a": "استقرار", "b": "راحة"}, {"a": "استيطان", "b": "خوف"}, {"a": "علم", "b": "ترحال"}, {"a": "سفر", "b": "تذكرة"}]}, "a"),
        q("completion", dict(stem="القرار هو الاختيار الذي تم التوصل إليه بعد ........ بين عدة اختيارات.",
                             **opts("المناقشة", "الجمع", "المراقبة", "المفاضلة")), "d"),
        q("completion", dict(stem="ليس العيب أن ........ ، ولكن العيب ألا تستطيع ........ .",
                             **opts("تسقط - النهوض", "تقع - الارتفاع", "تسرق - الهروب", "الثبور - البور")), "a"),
        q("odd", opts("ظرافة", "سفه", "طيش", "حماقة"), "a"),
        q("context", {"sentence": "إن للتعلم مرارة لن يذوقها إلا من ذاق مرارته.", "options_type": "short",
                      "selections": [{"start": 9, "end": 14, "text": "مرارة"}, {"start": 18, "end": 24, "text": "يذوقها"},
                                     {"start": 31, "end": 34, "text": "ذاق"}, {"start": 35, "end": 41, "text": "مرارته"}]}, "a"),
        q("context", {"sentence": "صديقك مرآة لك، تتراءى فيها فتكشف لك عن نفسه، وتصدقك عن محاسنك وعيوبك.", "options_type": "short",
                      "selections": []}, "b"),
        {"type": "group", "group_kind": "reading", "data": {"title": "الكريم واللئيم", "passage_type": "short",
                                                             "paragraphs": ["الكريم يلين عندما يُستَعطف، واللئيم يقسو عندما يُستلطف."]},
         "children": [
             q("reading", dict(stem="تؤكد العبارة على أن:", **opts("الاستلطاف يقسي الكريم", "القوة تلين الكريم", "القسوة تلين اللئيم", "الاستعطاف يقسي اللئيم", t="long")), "d"),
             q("reading", dict(stem="كم تضاد في النص؟", **opts("1", "2", "3", "4")), "b"),
         ]},
        {"type": "group", "group_kind": "reading", "data": {"title": "الإمام مالك", "passage_type": "long", "numbered": True,
                                                             "paragraphs": long_paras},
         "children": [
             q("reading", dict(stem="يفهم من سياق الفقرة (٤) أن كلمة \"قصبة\" تعني:", **opts("مدينة علمية", "مكان هجرة", "مركز اقتصادي", "عاصمة سياسية")), "d"),
             q("reading", dict(stem="أي الآتي يمكن استنتاجه من الفقرة (١)؟", **opts(
                 "الإمام مالك يبعث على الإعجاب والدهشة", "بُعد مقر تدريس الإمام مالك عن الشُّهرة",
                 "معظم المساجد ذات المدارس ينبغي السفر إليها", "عمق مساهمة الإمام مالك في تدبير شؤون الدولة", t="long")), "a"),
             q("reading", dict(stem="المعنى الأقرب للنص؟", **opts("لكي تُسعد عليك أن تتقن فن التجاهل", "قلب لا يبالي لا يعيش سعيدًا",
                                                                      "من لا يرضى بالقليل لا يرضى أبدًا", "إذا أسعدت نفسك أسعدت من حولك", t="long")), "c"),
         ]},
    ]
    return {"title": "قسم لفظي تجريبي ١", "kind": "verbal", "source": "أقسام العراب (ملف زيتونة)", "items": items}


def fix_context_offsets(section):
    """يحسب مواضع كلمات الخطأ السياقي من الجملة (لضمان صحة البيانات التجريبية)."""
    for it in section["items"]:
        if it.get("type") == "question" and it["category"] == "context":
            s = it["data"]["sentence"]
            words = [x["text"] for x in it["data"].get("selections", [])]
            if not words:
                words = {"صديقك مرآة لك، تتراءى فيها فتكشف لك عن نفسه، وتصدقك عن محاسنك وعيوبك.": ["مرآة", "نفسه", "وتصدقك", "وعيوبك"]}.get(s, [])
            sels, pos = [], 0
            for w in words:
                k = s.find(w, pos)
                if k < 0:
                    continue
                sels.append({"start": k, "end": k + len(w), "text": w})
                pos = k + len(w)
            it["data"]["selections"] = sels
    return section
