# -*- coding: utf-8 -*-
"""
يشغّل كل الاختبارات الآلية (البيانات + المعادلات + التصدير + سيناريو الواجهة الكامل)
ويكتب تقريرًا عربيًا: test_report.html في مجلد البرنامج.

التشغيل:  python tests/run_all.py        (أو run_tests_windows.bat)
          python tests/run_all.py --no-ui (بدون اختبار الواجهة الطويل)
"""
import datetime
import html
import io
import json
import os
import platform
import subprocess
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

AR = {
    "test_section_requires_title_kind_source": "إنشاء القسم يتطلب عنوانًا ونوعًا (كمي/لفظي) ومصدرًا، والمصدر محفوظ على مستوى القسم",
    "test_order_insert_middle_delete_renumber": "الإدراج بين سؤالين، والحذف مع إعادة الترقيم، والتحريك، وإعادة الترتيب — والترتيب محفوظ دائمًا بعد إعادة فتح قاعدة البيانات",
    "test_reorder_rejects_incomplete_list": "رفض أي ترتيب ناقص يمكن أن يُسقط سؤالًا",
    "test_answer_follows_question_when_moved": "نقل السؤال لا يغيّر إجابته الصحيحة",
    "test_group_shared_content_survives_question_delete": "حذف سؤال من مجموعة لا يحذف النص/الرسم المشترك، وترتيب الفقرات يُحفظ كما أُدخل",
    "test_group_kind_restricted_to_section_kind": "الرسوم البيانية للكمي فقط ونصوص الاستيعاب للفظي فقط",
    "test_draft_when_options_incomplete": "السؤال بخيارات ناقصة يُحفظ مسودة ولا يُعد مكتملًا إلا بأربعة خيارات وإجابة",
    "test_compare_question_needs_values_not_options": "سؤال المقارنة يحتاج القيمتين فقط والخيارات ثابتة",
    "test_rich_text_sanitized_and_preserved": "حفظ النص الغني (عريض/معادلات) وتعطيل أي وسوم ضارة",
    "test_text_never_rewritten": "لا تُغيَّر نصوص الأسئلة والخيارات المخزنة (الأرقام والنسب كما كُتبت)",
    "test_context_selections_positions_and_repeated_words": "الخطأ السياقي: حفظ المواضع لا النص فقط، وترتيب الخيارات حسب ظهورها، مع كلمة مكررة",
    "test_context_overlapping_selection_dropped": "منع التحديدات المتداخلة في الخطأ السياقي",
    "test_analogy_parts_order_kept": "التناظر: ترتيب الطرفين ثابت والطرف قد يكون عبارة",
    "test_wrap_question_into_chart_group": "تحويل سؤال إلى مجموعة رسم بياني في الموضع نفسه",
    "test_exam_kind_validation_and_freeze_snapshot": "منع اختيار قسمين من نوع خاطئ، والاعتماد يثبّت نسخة لا تتأثر بتعديل القسم الأصلي",
    "test_question_count_range_problem": "التحقق من عدد الأسئلة (١١–١٣) قبل اعتماد القسم مكتملًا",
    "test_backup_roundtrip_with_media_and_order": "النسخ الاحتياطي ثم الاستعادة يحفظان الأسئلة والترتيب والإجابات والصور والاختبارات",
    "test_media_dedup_and_invalid": "رفض الملفات غير الصالحة كصور، وعدم تكرار الصورة نفسها",
    "test_settings_validation": "التحقق من الإعدادات قبل الحفظ والقوالب الجاهزة لا تمس النصوص",
    "test_duplicate_section_independent": "نسخ قسم ينتج نسخة مستقلة",
    "test_multi_digit_number_order_kept_and_hindi": "الأعداد متعددة الخانات بترتيبها الصحيح وبالأرقام الهندية (أو اللاتينية حسب الإعداد)",
    "test_decimal_separator": "الفاصلة العشرية العربية ٫",
    "test_exponent_left_of_base": "الأس مرفوع وعلى يسار الأساس",
    "test_rtl_sequence": "ترتيب عناصر المعادلة من اليمين إلى اليسار",
    "test_fraction_stacking": "الكسر: البسط فوق خط الكسر والمقام تحته في المنتصف",
    "test_mirrored_radical": "علامة الجذر معكوسة: تبدأ من اليمين وخطها العلوي يمتد يسارًا فوق العدد",
    "test_nth_root_index_on_right": "دليل الجذر النوني في الجهة اليمنى",
    "test_relations_mirrored": "عكس رموز العلاقات (< ≤) كما في الكتابة العربية",
    "test_percent_sign_left_of_number": "علامة النسبة ⁒ على يسار العدد",
    "test_negative_sign_on_right": "إشارة السالب على يمين العدد",
    "test_mixed_arabic_text": "معادلة تمزج النص العربي بالأرقام (٤٠⁒ من ٦٠)",
    "test_complex_expression_renders": "معادلات مركبة: كسر بجذور، قوس ممتد بأس، عدد كسري بنسبة، قطعة وقوس، أدلة سفلية، جذر كسر",
    "test_parse_errors_reported": "اكتشاف الأخطاء في صيغة المعادلة وإظهارها",
    "test_png_matches_svg_size": "صورة المعادلة في Word بأبعاد المعاينة/PDF نفسها",
    "test_pdf_and_docx_produced": "إنتاج PDF وWord صالحين، دون تجاوز أعمدة أو صور مفقودة أو أخطاء معادلات",
    "test_question_order_matches_database": "ترتيب الأسئلة في الملفين مطابق لترتيبها في البرنامج، والترقيم من ١ في كل قسم",
    "test_no_split_and_greedy_columns": "كل كتلة تظهر مرة واحدة بالترتيب، ولا عنوان تصنيف منفصل في أسفل عمود",
    "test_question_near_column_end_moves_whole": "حالة سؤال قرب نهاية النصف الأيمن لا تتسع خياراته: ينتقل كاملًا للنصف التالي",
    "test_demo_exam_columns_greedy": "استغلال المساحة: لا ينتقل محتوى إلى عمود جديد إلا إذا لم يتسع فعلًا",
    "test_docx_rtl_columns_header_and_digits": "Word: عمودان من اليمين مع خط فاصل، جداول RTL، المصدران في الترويسة، خط Calibri، معادلات بمصدرها، ⁒ بخط مضمَّن، أرقام هندية",
    "test_teacher_copy_marks_each_answer": "نسخة المعلم تظلل الإجابة الصحيحة لكل سؤال",
    "test_answer_key_matches": "مفتاح الإجابة يطابق الإجابات بترتيب الأسئلة",
    "test_flow_mode_and_settings_effect": "أثر الإعدادات فعليًا: أرقام لاتينية، ترقيم متصل، عبارة نهاية، ووضع التدفق في Word",
    "test_long_passage_splits_only_at_paragraph_boundaries": "النص الطويل يتوزع بين النصفين عند حدود الفقرات فقط، والأسئلة بعده",
    "test_preview_endpoint": "معاينة الاختبار تنتج PDF فعليًا",
}


class Collector(unittest.TextTestResult):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.records = []
        self._t = {}

    def startTest(self, test):
        self._t[test.id()] = time.time()
        super().startTest(test)

    def _rec(self, test, status, detail=""):
        name = test.id().split(".")[-1]
        self.records.append({"id": test.id(), "name": name, "module": test.id().split(".")[0], "status": status,
                             "desc": AR.get(name, (test.shortDescription() or name)), "detail": detail,
                             "secs": round(time.time() - self._t.get(test.id(), time.time()), 2)})

    def addSuccess(self, test):
        super().addSuccess(test)
        self._rec(test, "ok")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._rec(test, "fail", self._exc_info_to_string(err, test)[-1500:])

    def addError(self, test, err):
        super().addError(test, err)
        self._rec(test, "error", self._exc_info_to_string(err, test)[-1500:])

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._rec(test, "skip", reason)


def main():
    no_ui = "--no-ui" in sys.argv
    suite = unittest.defaultTestLoader.discover(HERE, pattern="test_*.py")
    stream = io.StringIO()
    runner = unittest.TextTestRunner(stream=sys.stdout, verbosity=2, resultclass=Collector)
    t0 = time.time()
    res = runner.run(suite)
    unit_secs = round(time.time() - t0, 1)
    e2e = None
    if not no_ui:
        print("\n=== سيناريو القبول عبر الواجهة ===")
        import tempfile
        out_dir = os.path.join(tempfile.gettempdir(), "qudurat_test_runs")
        env = dict(os.environ, E2E_OUT=os.path.abspath(os.path.join(out_dir, "e2e")))
        p = subprocess.run([sys.executable, os.path.join(HERE, "e2e_ui_test.py")], env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
        print(p.stdout[-4000:])
        rep_path = os.path.join(env["E2E_OUT"], "e2e_report.json")
        if os.path.exists(rep_path):
            with open(rep_path, encoding="utf-8") as f:
                e2e = json.load(f)
        else:
            e2e = {"steps": [{"step": "تشغيل سيناريو الواجهة", "ok": False, "info": (p.stdout + p.stderr)[-1500:]}]}
    write_report(res.records, unit_secs, e2e)
    failed = [r for r in res.records if r["status"] in ("fail", "error")] + [s for s in (e2e or {}).get("steps", []) if not s["ok"]]
    print("\nالتقرير: %s" % os.path.join(ROOT, "test_report.html"))
    print("النتيجة النهائية: %s" % ("نجحت كل الاختبارات" if not failed else "يوجد %d اختبار فاشل" % len(failed)))
    return 1 if failed else 0


def write_report(records, unit_secs, e2e):
    esc = html.escape
    ok = sum(1 for r in records if r["status"] == "ok")
    bad = sum(1 for r in records if r["status"] in ("fail", "error"))
    skip = sum(1 for r in records if r["status"] == "skip")
    groups = {"test_db": "طبقة البيانات والحفظ", "test_math": "محرك المعادلات العربية (داخل المتصفح نفسه المستخدم في التصدير)", "test_export": "التصدير إلى Word وPDF ومحرك التوزيع", "test_license": "ترخيص البرنامج والإقرار عند أول تشغيل"}
    rows = ""
    for mod, title in groups.items():
        rs = [r for r in records if r["module"] == mod]
        if not rs:
            continue
        rows += "<tr><th colspan=3>%s (%d)</th></tr>" % (esc(title), len(rs))
        for r in rs:
            mark = {"ok": "✔", "fail": "✘", "error": "✘", "skip": "—"}[r["status"]]
            cls = {"ok": "ok", "fail": "bad", "error": "bad", "skip": "skip"}[r["status"]]
            det = ("<pre>%s</pre>" % esc(r["detail"])) if r["detail"] and r["status"] != "ok" else ""
            rows += "<tr class='%s'><td class=m>%s</td><td>%s%s</td><td class=s>%s ث</td></tr>" % (cls, mark, esc(r["desc"]), det, r["secs"])
    e2e_rows = ""
    if e2e:
        for s in e2e.get("steps", []):
            e2e_rows += "<tr class='%s'><td class=m>%s</td><td>%s<div class=i>%s</div></td></tr>" % (
                "ok" if s["ok"] else "bad", "✔" if s["ok"] else "✘", esc(s["step"]), esc(s.get("info") or ""))
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    doc = """<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><title>تقرير الاختبارات الآلية</title>
<style>body{font-family:Calibri,'Segoe UI',Tahoma,sans-serif;background:#f5f6f8;color:#1d2730;margin:0;line-height:1.7}
main{max-width:980px;margin:0 auto;padding:20px 16px 50px}h1{margin:0 0 6px}.sum{display:flex;gap:12px;flex-wrap:wrap;margin:14px 0}
.c{background:#fff;border:1px solid #e1e5ea;border-radius:12px;padding:12px 18px}.c b{font-size:26px;display:block}
table{width:100%%;border-collapse:collapse;background:#fff;border:1px solid #e1e5ea;border-radius:12px;overflow:hidden;margin:12px 0}
th{background:#eef2f4;text-align:right;padding:8px 12px}td{padding:7px 12px;border-top:1px solid #edf0f2;vertical-align:top}
td.m{width:28px;text-align:center;font-weight:700}td.s{width:70px;color:#66727e;font-size:13px;white-space:nowrap}
tr.ok td.m{color:#2e7d32}tr.bad td{background:#fdecea}tr.bad td.m{color:#b42318}tr.skip td{color:#888}.i{color:#66727e;font-size:13px;direction:ltr;text-align:right;unicode-bidi:plaintext}
pre{white-space:pre-wrap;direction:ltr;text-align:left;font-size:12px;background:#fff7f6;padding:6px}</style></head><body><main>
<h1>تقرير الاختبارات الآلية</h1><div>مُنشئ اختبارات القدرات — %s — %s / Python %s</div>
<div class="sum"><div class="c"><b>%d</b>اختبار ناجح</div><div class="c"><b>%d</b>فاشل</div><div class="c"><b>%d</b>متخطى</div><div class="c"><b>%s ث</b>المدة</div>
<div class="c"><b>%s</b>خطوات سيناريو القبول الناجحة</div></div>
<h2>الاختبارات الوحدوية والتكاملية</h2><table>%s</table>
<h2>سيناريو القبول عبر الواجهة الحقيقية (معايير القبول في المواصفات)</h2><table>%s</table>
</main></body></html>""" % (now, esc(platform.platform()), platform.python_version(), ok, bad, skip, unit_secs,
                            ("%d/%d" % (sum(1 for s in e2e["steps"] if s["ok"]), len(e2e["steps"]))) if e2e else "لم يُشغّل",
                            rows, e2e_rows or "<tr><td>لم يُشغَّل (--no-ui)</td></tr>")
    with open(os.path.join(ROOT, "test_report.html"), "w", encoding="utf-8") as f:
        f.write(doc)


if __name__ == "__main__":
    sys.exit(main())
