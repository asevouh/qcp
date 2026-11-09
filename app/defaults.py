# -*- coding: utf-8 -*-
"""الإعدادات الافتراضية للتنسيق والهوية — قابلة للتعديل كلها من صفحة الإعدادات."""

CATEGORY_DEFINITIONS = {
    "analogy": "في بداية كل سؤال مما يأتي كلمتان ترتبطان بعلاقة معينة، يتبعهما أربعة خيارات، والمطلوب اختيار الخيار الذي تتشابه علاقته مع العلاقة الموجودة في السؤال.",
    "completion": "بعد كل سؤال مما يأتي أربعة خيارات تكمل فراغات الجملة، والمطلوب اختيار الخيار الذي يعطي للجملة معناها الصحيح.",
    "odd": "في كل سؤال مما يأتي أربع كلمات، والمطلوب اختيار الكلمة التي تختلف عن باقي الكلمات في المعنى.",
    "context": "في كل سؤال مما يأتي جملة تحتوي على أربع كلمات مكتوبة بخط عريض، والمطلوب اختيار الكلمة التي لا يتفق معناها مع المعنى العام للجملة.",
    "reading": "الأسئلة التالية تتعلق بالنص، والمطلوب قراءة النص بعناية واختيار الجواب الصحيح.",
}

CATEGORY_TITLES = {
    "analogy": "التناظر اللفظي",
    "completion": "إكمال الجمل",
    "odd": "المفردة الشاذة",
    "context": "الخطأ السياقي",
    "reading": "استيعاب المقروء",
}

DEFAULT_SETTINGS = {
    # الجهة والغلاف
    "organization_name": "ثانوية مجمع المعجل بحوطة سدير",
    "cover": {
        "right_text": "اختبار قدرات محوسب محاكي لطلاب الصف الأول والثاني ثانوي",
        "left_text": "أعدَّهُ الإرشاد الطلابي في ثانوية مجمع المعجل بحوطة سدير",
        "grade_label": "الدرجة النهائية",
        "quant_label": "كمي",
        "verbal_label": "لفظي",
        "number_label": "رقم الاختبار:",
        "count_label": "عدد الأسئلة:",
        "count_unit": "سؤال",
        "duration_label": "مدة الاختبار:",
        "duration_unit": "دقيقة",
        "big_suffix": ": كمي ولفظي",
        "notes_title": "ملحوظات",
        "notes": [
            "يجب اختيار إجابة واحدة فقط لكل سؤال.",
            "لا يوجد ورقة إجابة خارجية، يجب أن يكون الحل في أوراق الأسئلة هذه.",
            "يُسمح بالكتابة والشخبطة على أوراق الأسئلة، بشرط تحديد الإجابة النهائية بوضوحٍ تام.",
        ],
        "show_name_fields": True,
        "name_label": "الاسم:",
        "class_label": "الصف والشعبة:",
        "reminder_title": "تذكر",
        "reminder_text": "هذه الاختبارات المحاكية لا تُغني عن المذاكرة، هدفها قياس مستواك واستعدادك للاختبار الفعلي؛ المجهود كله عليك أنت، بالبحث عن المصادر والقراءة والتدرب.",
    },
    "end_text": "- انتهى الاختبار! ويمكنك فيما تبقى مراجعة حلّك فقط! -",
    "quant_section_title": "القسم الكمي",
    "verbal_section_title": "القسم اللفظي",
    "header_quant_label": "مصدر أسئلة الكمي:",
    "header_verbal_label": "مصدر أسئلة اللفظي:",
    "answer_key_title": "مفتاح الإجابة",
    "odd_stem_text": "أي الآتي مختلف؟",
    "geometry_caption": "(الرسم ليس على القياس)",
    "compare_label_1": "- القيمة الأولى:",
    "compare_label_2": "- القيمة الثانية:",
    "compare_options": ["القيمة الأولى أكبر", "القيمة الثانية أكبر", "القيمتان متساويتان", "المعطيات غير كافية"],
    "option_labels": ["أ)", "ب)", "جـ)", "د)"],
    "category_titles": CATEGORY_TITLES,
    "category_definitions": CATEGORY_DEFINITIONS,

    # الخطوط
    "font_family": "Calibri",
    "font_metrics_factor": 1.2207,  # (الصعود + النزول) / وحدات الخط لـ Calibri — يحسب تلقائيًا إن وجد ملف الخط
    "question_font_pt": 13,
    "option_font_pt": 13,
    "passage_font_pt": 13,
    "title_font_pt": 16,
    "category_title_pt": 13,
    "category_def_pt": 12,
    "compare_label_pt": 12,
    "caption_font_pt": 9,
    "end_text_pt": 13,
    "header_title_pt": 18,
    "header_source_pt": 10,
    "page_number_pt": 10,
    "line_spacing": 1.15,
    "number_bold": False,
    "analogy_stem_bold": True,

    # الصفحة والأعمدة (سم)
    "margin_top_cm": 2.9,
    "margin_bottom_cm": 2.0,
    "margin_right_cm": 1.5,
    "margin_left_cm": 1.5,
    "column_gap_cm": 1.2,
    "header_top_cm": 0.6,
    "header_height_cm": 1.35,
    "header_box_gap_cm": 0.35,
    "header_rule_gap_cm": 0.25,
    "header_border_pt": 1,
    "footer_bottom_cm": 0.5,
    "page_number_box_cm": 0.9,
    "page_numbers": True,
    "separator_width_pt": 0.75,
    "separator_color": "#404040",

    # المسافات (نقطة)
    "question_gap_pt": 10,
    "stem_options_gap_pt": 4,
    "compare_gap_pt": 4,
    "after_title_gap_pt": 6,
    "after_header_gap_pt": 6,
    "after_chart_gap_pt": 6,
    "after_passage_gap_pt": 8,
    "paragraph_gap_pt": 4,
    "section_gap_pt": 16,
    "end_text_gap_pt": 18,
    "option_label_width_cm": 0.9,
    "cell_padding_pt": 2,
    "box_padding_v_pt": 3,
    "box_padding_h_pt": 5,
    "border_width_pt": 0.75,

    # الرمادي
    "border_color": "#000000",
    "title_fill": "#E6E6E6",
    "correct_fill": "#D9D9D9",

    # الصور
    "geometry_width_cm": 4.5,
    "chart_width_cm": 7.5,

    # الأرقام والترقيم
    "digits": "hindi",            # hindi | western
    "percent_sign": "⁒",     # ⁒
    "decimal_style": "arabic",    # arabic (٫) | keep
    "numbering": "per_section",   # per_section | continuous
    "number_format": "{n}:",
    "frac_scale": 0.82,

    # التصدير
    "word_layout_mode": "match",  # match: نفس توزيع PDF | flow: تدفق Word التلقائي
    "word_safety_pt": 6,          # هامش أمان لكل عمود حتى لا يفيض Word
    "min_questions": 11,
    "max_questions": 13,
}

PRESETS = {
    "standard": {"name": "تنسيق قياسي", "values": {}},
    "compact": {"name": "تنسيق مضغوط", "values": {
        "question_font_pt": 12, "option_font_pt": 12, "passage_font_pt": 12, "category_def_pt": 11,
        "line_spacing": 1.05, "question_gap_pt": 7, "stem_options_gap_pt": 3, "paragraph_gap_pt": 3,
        "margin_right_cm": 1.3, "margin_left_cm": 1.3, "column_gap_cm": 1.0,
    }},
    "large": {"name": "تنسيق بخط أكبر", "values": {
        "question_font_pt": 14, "option_font_pt": 14, "passage_font_pt": 14, "category_def_pt": 13,
        "title_font_pt": 17, "line_spacing": 1.2, "question_gap_pt": 12,
    }},
}


def merged_settings(stored):
    """يدمج الإعدادات المخزنة مع الافتراضية (الإعدادات الجديدة تأخذ قيمها الافتراضية)."""
    import copy
    out = copy.deepcopy(DEFAULT_SETTINGS)
    for k, v in (stored or {}).items():
        if k in ("cover", "category_titles", "category_definitions") and isinstance(v, dict):
            out[k].update(v)
        else:
            out[k] = v
    return out
