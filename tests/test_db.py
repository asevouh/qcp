# -*- coding: utf-8 -*-
"""اختبارات طبقة البيانات: الأقسام، الترتيب، المجموعات، التحقق، الاعتماد، النسخ الاحتياطي."""
import os
import tempfile
import unittest

import helpers  # noqa: F401  (يضبط مسار التطبيق)
import db as dbm
import sample_data as sd


def q(cat, stem="سؤال", opts=("١", "٢", "٣", "٤"), ans="a", otype="short"):
    return {"type": "question", "category": cat, "data": {"stem": stem, "options_type": otype, "options": list(opts)}, "answer": ans}


class DBTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.db = dbm.Database(os.path.join(self.dir, "t.db"))

    def tearDown(self):
        self.db.close()

    def ids(self, sid):
        return [it["id"] for it in self.db.get_tree(sid)]

    # ------------------------------------------------------------------
    def test_section_requires_title_kind_source(self):
        with self.assertRaises(dbm.ValidationError):
            self.db.create_section("", "quant", "مصدر")
        with self.assertRaises(dbm.ValidationError):
            self.db.create_section("قسم", "other", "مصدر")
        with self.assertRaises(dbm.ValidationError):
            self.db.create_section("قسم", "quant", "")
        sid = self.db.create_section("قسم", "quant", "مصدر المنصف")
        s = self.db.get_section(sid)
        self.assertEqual(s["source"], "مصدر المنصف")
        self.assertEqual(s["status"], "draft")

    def test_order_insert_middle_delete_renumber(self):
        sid = self.db.create_section("قسم", "quant", "م")
        a = self.db.create_item(sid, q("regular", "أ"))
        b = self.db.create_item(sid, q("regular", "ب"))
        c = self.db.create_item(sid, q("regular", "ج"))
        self.assertEqual(self.ids(sid), [a, b, c])
        x = self.db.create_item(sid, q("regular", "إدراج"), position=1)
        self.assertEqual(self.ids(sid), [a, x, b, c])
        self.db.delete_item(x)
        self.assertEqual(self.ids(sid), [a, b, c])
        positions = [it["position"] for it in self.db.get_tree(sid)]
        self.assertEqual(positions, [0, 1, 2])
        self.db.move_item(c, "up")
        self.assertEqual(self.ids(sid), [a, c, b])
        tree = self.db.reorder(sid, [{"id": b}, {"id": a}, {"id": c}])
        self.assertEqual([t["id"] for t in tree], [b, a, c])
        # الترتيب محفوظ بعد إعادة الاتصال
        db2 = dbm.Database(os.path.join(self.dir, "t.db"))
        self.assertEqual([t["id"] for t in db2.get_tree(sid)], [b, a, c])

    def test_reorder_rejects_incomplete_list(self):
        sid = self.db.create_section("قسم", "quant", "م")
        a = self.db.create_item(sid, q("regular"))
        self.db.create_item(sid, q("regular"))
        with self.assertRaises(dbm.ValidationError):
            self.db.reorder(sid, [{"id": a}])

    def test_answer_follows_question_when_moved(self):
        sid = self.db.create_section("قسم", "quant", "م")
        a = self.db.create_item(sid, q("regular", ans="d"))
        b = self.db.create_item(sid, q("regular", ans="b"))
        self.db.move_item(a, "down")
        tree = self.db.get_tree(sid)
        self.assertEqual([(t["id"], t["answer"]) for t in tree], [(b, "b"), (a, "d")])

    def test_group_shared_content_survives_question_delete(self):
        sid = self.db.create_section("قسم", "verbal", "م")
        g = self.db.create_item(sid, {"type": "group", "group_kind": "reading", "data": {"passage_type": "long", "paragraphs": ["فقرة ١", "فقرة ٢"]},
                                      "children": [q("reading"), q("reading")]})
        tree = self.db.get_tree(sid)
        kids = [c["id"] for c in tree[0]["children"]]
        self.db.delete_item(kids[0])
        tree = self.db.get_tree(sid)
        self.assertEqual(len(tree), 1)
        self.assertEqual(tree[0]["data"]["paragraphs"], ["فقرة ١", "فقرة ٢"])
        self.assertEqual([c["id"] for c in tree[0]["children"]], [kids[1]])
        # إعادة ترتيب الفقرات محفوظة كما أُدخلت
        self.db.update_item(g, {"data": {"passage_type": "long", "paragraphs": ["فقرة ٢", "فقرة ١"]}})
        self.assertEqual(self.db.get_item(g)["data"]["paragraphs"], ["فقرة ٢", "فقرة ١"])

    def test_group_kind_restricted_to_section_kind(self):
        sid = self.db.create_section("قسم", "verbal", "م")
        with self.assertRaises(dbm.ValidationError):
            self.db.create_item(sid, {"type": "group", "group_kind": "chart", "data": {}})

    def test_draft_when_options_incomplete(self):
        sid = self.db.create_section("قسم", "quant", "م")
        iid = self.db.create_item(sid, q("regular", opts=("١", "٢", "", "")))
        it = [t for t in self.db.get_tree(sid) if t["id"] == iid][0]
        self.assertEqual(it["status"], "draft")
        self.assertTrue(any("الخيارات" in x for x in it["issues"]))
        res = self.db.update_item(iid, {"data": {"stem": "سؤال", "options_type": "short", "options": ["١", "٢", "٣", "٤"]}, "answer": "a"})
        self.assertEqual(res["status"], "complete")

    def test_compare_question_needs_values_not_options(self):
        sid = self.db.create_section("قسم", "quant", "م")
        iid = self.db.create_item(sid, {"type": "question", "category": "regular", "answer": "c",
                                        "data": {"stem": "قارن بين:", "options_type": "compare", "compare": {"v1": "٤٠٪ من ٦٠", "v2": "٦٠٪ من ٤٠"}}})
        it = self.db.get_item(iid)
        self.assertEqual(it["status"], "complete")
        self.assertNotIn("options", it["data"])

    def test_rich_text_sanitized_and_preserved(self):
        sid = self.db.create_section("قسم", "quant", "م")
        stem = 'ما قيمة <m>\\frac{3}{4}</m> <b>تقريبًا</b>؟ <script>alert(1)</script>'
        iid = self.db.create_item(sid, q("regular", stem=stem))
        saved = self.db.get_item(iid)["data"]["stem"]
        self.assertIn("<m>\\frac{3}{4}</m>", saved)
        self.assertIn("<b>تقريبًا</b>", saved)
        self.assertNotIn("<script>", saved)
        self.assertIn("&lt;script&gt;", saved)

    def test_text_never_rewritten(self):
        sid = self.db.create_section("قسم", "quant", "م")
        stem = "إذا كان س + 2ص = 22 ، س = 2 ، قارن بين:"
        iid = self.db.create_item(sid, q("regular", stem=stem, opts=("40%", "3.5", "1/2", "س")))
        d = self.db.get_item(iid)["data"]
        self.assertEqual(d["stem"], stem)
        self.assertEqual(d["options"], ["40%", "3.5", "1/2", "س"])

    def test_context_selections_positions_and_repeated_words(self):
        sid = self.db.create_section("قسم", "verbal", "م")
        s = "العلم يرفع أهله والجهل يرفع أهله والمال لا يرفع"
        k1 = s.find("يرفع")
        k2 = s.find("يرفع", k1 + 1)
        k3 = s.rfind("يرفع")
        sels = [{"start": k3, "end": k3 + 4}, {"start": 0, "end": 5}, {"start": k1, "end": k1 + 4}, {"start": k2, "end": k2 + 4}]
        iid = self.db.create_item(sid, {"type": "question", "category": "context", "answer": "b", "data": {"sentence": s, "selections": sels}})
        d = self.db.get_item(iid)["data"]
        self.assertEqual([x["start"] for x in d["selections"]], sorted([0, k1, k2, k3]))
        self.assertEqual([x["text"] for x in d["selections"]], ["العلم", "يرفع", "يرفع", "يرفع"])
        self.assertEqual(self.db.get_item(iid)["status"], "complete")

    def test_context_overlapping_selection_dropped(self):
        sid = self.db.create_section("قسم", "verbal", "م")
        s = "كلمة أولى ثانية"
        iid = self.db.create_item(sid, {"type": "question", "category": "context", "answer": "a",
                                        "data": {"sentence": s, "selections": [{"start": 0, "end": 9}, {"start": 5, "end": 9}]}})
        self.assertEqual(len(self.db.get_item(iid)["data"]["selections"]), 1)

    def test_analogy_parts_order_kept(self):
        sid = self.db.create_section("قسم", "verbal", "م")
        iid = self.db.create_item(sid, {"type": "question", "category": "analogy", "answer": "a",
                                        "data": {"pair": {"a": "ازدحام", "b": "طريق مزدحم جدًا"},
                                                 "option_pairs": [{"a": "أ%d" % i, "b": "ب%d" % i} for i in range(4)]}})
        d = self.db.get_item(iid)["data"]
        self.assertEqual(d["pair"], {"a": "ازدحام", "b": "طريق مزدحم جدًا"})
        self.assertEqual(d["option_pairs"][2], {"a": "أ2", "b": "ب2"})

    def test_wrap_question_into_chart_group(self):
        sid = self.db.create_section("قسم", "quant", "م")
        a = self.db.create_item(sid, q("regular", "أول"))
        b = self.db.create_item(sid, q("regular", "ثانٍ"))
        gid = self.db.wrap_in_group(b, "chart")
        tree = self.db.get_tree(sid)
        self.assertEqual([t["id"] for t in tree], [a, gid])
        self.assertEqual(tree[1]["children"][0]["id"], b)
        self.assertEqual(tree[1]["children"][0]["category"], "chart")

    def test_exam_kind_validation_and_freeze_snapshot(self):
        m = {n: self.db.save_media(f(), n)["id"] for n, f in (("chart", sd.make_chart_png), ("triangle", sd.make_triangle_png), ("circles", sd.make_circles_png))}
        qs = self.db.create_section("كمي", "quant", "مصدر كمي")
        self.db.import_section_items(qs, sd.sample_quant(m)["items"])
        vs = self.db.create_section("لفظي", "verbal", "مصدر لفظي")
        self.db.import_section_items(vs, sd.fix_context_offsets(sd.sample_verbal())["items"])
        with self.assertRaises(dbm.ValidationError):
            self.db.create_exam({"title": "خطأ", "quant_section_id": vs, "verbal_section_id": qs})
        eid = self.db.create_exam({"title": "اختبار", "quant_section_id": qs, "verbal_section_id": vs, "duration": 26})
        self.assertEqual(self.db.exam_problems(eid), [])
        self.db.freeze_exam(eid)
        first = self.db.get_tree(qs)[0]
        self.db.update_item(first["id"], {"data": dict(first["data"], stem="نص معدّل بعد الاعتماد")})
        snap = self.db.exam_sections_content(eid)
        self.assertNotEqual(snap["quant"]["items"][0]["data"].get("stem"), "نص معدّل بعد الاعتماد")
        self.db.unfreeze_exam(eid)
        live = self.db.exam_sections_content(eid)
        self.assertEqual(live["quant"]["items"][0]["data"].get("stem"), "نص معدّل بعد الاعتماد")

    def test_question_count_range_problem(self):
        sid = self.db.create_section("قسم", "quant", "م")
        for _ in range(3):
            self.db.create_item(sid, q("regular"))
        probs = self.db.section_problems(sid)
        self.assertTrue(any("خارج النطاق" in p for p in probs))
        with self.assertRaises(dbm.ValidationError):
            self.db.update_section(sid, {"status": "complete"})

    def test_backup_roundtrip_with_media_and_order(self):
        m = {n: self.db.save_media(f(), n)["id"] for n, f in (("chart", sd.make_chart_png), ("triangle", sd.make_triangle_png), ("circles", sd.make_circles_png))}
        qs = self.db.create_section("كمي", "quant", "مصدر كمي")
        self.db.import_section_items(qs, sd.sample_quant(m)["items"])
        eid = self.db.create_exam({"title": "اختبار", "quant_section_id": qs})
        data = self.db.export_all()
        blobs = {}
        for row in data["media"]:
            with open(self.db.media_path(row["id"], row["ext"]), "rb") as f:
                blobs[row["id"]] = f.read()
        other = dbm.Database(os.path.join(tempfile.mkdtemp(), "o.db"))
        res = other.import_all(data, blobs, "replace")
        self.assertEqual(res["sections"], 1)
        src = self.db.get_tree(qs)
        dst = other.get_tree(other.list_sections()[0]["id"])
        strip = lambda items: [(i["type"], i.get("category"), i["answer"], (i["data"].get("stem") or ""), [(c.get("answer"), c["data"].get("stem")) for c in i.get("children", [])]) for i in items]
        self.assertEqual(strip(src), strip(dst))
        # الصور منقولة ومتاحة
        img_items = [i for i in dst if (i["data"].get("image") or {}).get("media_id")]
        for i in img_items:
            mid = i["data"]["image"]["media_id"]
            row = other.get_media(mid)
            self.assertTrue(os.path.exists(other.media_path(mid, row["ext"])))
        self.assertEqual(len(other.list_exams()), 1)
        self.assertEqual(other.list_exams()[0]["quant_section"]["question_count"], 13)

    def test_media_dedup_and_invalid(self):
        b = sd.make_chart_png()
        m1 = self.db.save_media(b, "a.png")
        m2 = self.db.save_media(b, "b.png")
        self.assertEqual(m1["id"], m2["id"])
        with self.assertRaises(dbm.ValidationError):
            self.db.save_media(b"not an image", "x.png")

    def test_settings_validation(self):
        with self.assertRaises(dbm.ValidationError):
            self.db.save_settings({"question_font_pt": "abc"})
        with self.assertRaises(dbm.ValidationError):
            self.db.save_settings({"min_questions": 15, "max_questions": 11})
        s = self.db.save_settings({"end_text": "- انتهى -", "question_font_pt": 14})
        self.assertEqual(s["end_text"], "- انتهى -")
        self.assertEqual(s["question_font_pt"], 14)
        self.assertEqual(s["font_family"], "Calibri")
        s = self.db.apply_preset("compact")
        self.assertEqual(s["question_font_pt"], 12)
        self.assertEqual(s["end_text"], "- انتهى -")

    def test_duplicate_section_independent(self):
        sid = self.db.create_section("قسم", "quant", "م")
        a = self.db.create_item(sid, q("regular", "أصل"))
        nid = self.db.duplicate_section(sid)
        copy_first = self.db.get_tree(nid)[0]
        self.db.update_item(copy_first["id"], {"data": dict(copy_first["data"], stem="تعديل النسخة")})
        self.assertEqual(self.db.get_item(a)["data"]["stem"], "أصل")


if __name__ == "__main__":
    unittest.main()
