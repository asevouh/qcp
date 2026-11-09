# -*- coding: utf-8 -*-
"""
طبقة البيانات (SQLite): الأقسام، الأسئلة والمجموعات المرتبة، الصور، الاختبارات، الإعدادات.
- كل الكتابات داخل معاملات (transactions) لضمان سلامة البيانات.
- ترتيب الأسئلة محفوظ في عمود position لكل (قسم، أب).
"""
import copy
import datetime as _dt
import hashlib
import html
import json
import os
import re
import sqlite3
import threading
import uuid

from defaults import DEFAULT_SETTINGS, PRESETS, merged_settings

SCHEMA_VERSION = 1

QUANT_CATS = ("regular", "chart", "geometry")
VERBAL_CATS = ("analogy", "completion", "odd", "context", "reading")
ANSWERS = ("a", "b", "c", "d")

_lock = threading.RLock()


class ValidationError(Exception):
    pass


class NotFound(Exception):
    pass


def now():
    return _dt.datetime.now().isoformat(timespec="seconds")


# ------------------------------------------------------------------ النص الغني
_TAG_RE = re.compile(r"<(/?)(b|strong|br|m)\s*/?>", re.I)


def sanitize_rich(s):
    """يسمح فقط بـ <b> و <br> و <m>…</m>؛ أي وسم آخر يحوّل إلى نص آمن."""
    if s is None:
        return ""
    s = str(s)
    out = []
    i = 0
    bold = 0
    while i < len(s):
        if s.startswith("<m>", i) or s.lower().startswith("<m>", i):
            j = s.lower().find("</m>", i + 3)
            if j < 0:
                out.append(html.escape(s[i:], quote=False))
                break
            latex = html.unescape(s[i + 3:j])
            out.append("<m>" + html.escape(latex, quote=False) + "</m>")
            i = j + 4
            continue
        m = _TAG_RE.match(s, i)
        if m and m.group(2).lower() != "m":
            tag = m.group(2).lower()
            if tag == "br":
                out.append("<br>")
            elif m.group(1):
                if bold > 0:
                    out.append("</b>")
                    bold -= 1
            else:
                out.append("<b>")
                bold += 1
            i = m.end()
            continue
        if s[i] == "<":
            out.append("&lt;")
        elif s[i] == ">":
            out.append("&gt;")
        elif s[i] == "&":
            m2 = re.match(r"&(amp|lt|gt|quot|#39|nbsp);", s[i:])
            if m2:
                out.append(m2.group(0))
                i += len(m2.group(0))
                continue
            out.append("&amp;")
        else:
            out.append(s[i])
        i += 1
    out.append("</b>" * bold)
    return "".join(out)


def rich_plain(s):
    s = re.sub(r"<m>(.*?)</m>", r" \1 ", s or "", flags=re.S)
    s = re.sub(r"<br\s*/?>", " ", s)
    s = re.sub(r"</?b>", "", s)
    return html.unescape(s).strip()


def rich_empty(s):
    return not rich_plain(s)


# ------------------------------------------------------------------ الاتصال
class Database:
    def __init__(self, path):
        self.path = path
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.media_dir = os.path.join(os.path.dirname(os.path.abspath(path)), "media")
        os.makedirs(self.media_dir, exist_ok=True)
        self._local = threading.local()
        self.init_schema()

    def conn(self):
        c = getattr(self._local, "conn", None)
        if c is None:
            c = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
            c.row_factory = sqlite3.Row
            c.execute("PRAGMA foreign_keys = ON")
            c.execute("PRAGMA journal_mode = WAL")
            c.execute("PRAGMA synchronous = FULL")
            self._local.conn = c
        return c

    def close(self):
        c = getattr(self._local, "conn", None)
        if c is not None:
            c.close()
            self._local.conn = None

    def tx(self):
        return _Tx(self)

    def init_schema(self):
        with self.tx() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE IF NOT EXISTS sections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                kind TEXT NOT NULL CHECK (kind IN ('quant','verbal')),
                source TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','complete','review')),
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                section_id INTEGER NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
                parent_id INTEGER REFERENCES items(id) ON DELETE CASCADE,
                position INTEGER NOT NULL,
                type TEXT NOT NULL CHECK (type IN ('question','group')),
                category TEXT,
                group_kind TEXT CHECK (group_kind IS NULL OR group_kind IN ('chart','reading')),
                data TEXT NOT NULL DEFAULT '{}',
                answer TEXT CHECK (answer IS NULL OR answer IN ('a','b','c','d')),
                status TEXT NOT NULL DEFAULT 'draft',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_items_section ON items(section_id, parent_id, position);
            CREATE TABLE IF NOT EXISTS media (
                id TEXT PRIMARY KEY,
                sha256 TEXT NOT NULL,
                filename TEXT NOT NULL DEFAULT '',
                mime TEXT NOT NULL,
                ext TEXT NOT NULL,
                width INTEGER NOT NULL,
                height INTEGER NOT NULL,
                size INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_media_sha ON media(sha256);
            CREATE TABLE IF NOT EXISTS exams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                number TEXT NOT NULL DEFAULT '',
                header_title TEXT NOT NULL DEFAULT '',
                quant_section_id INTEGER REFERENCES sections(id) ON DELETE SET NULL,
                verbal_section_id INTEGER REFERENCES sections(id) ON DELETE SET NULL,
                duration INTEGER,
                options TEXT NOT NULL DEFAULT '{}',
                frozen INTEGER NOT NULL DEFAULT 0,
                snapshot TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_export_at TEXT
            );
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS exports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exam_id INTEGER,
                kind TEXT NOT NULL,
                variant TEXT NOT NULL,
                filename TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)
            c.execute("INSERT OR IGNORE INTO meta(key, value) VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),))

    # -------------------------------------------------------------- الإعدادات
    def get_settings(self):
        row = self.conn().execute("SELECT value FROM settings WHERE key='global'").fetchone()
        stored = json.loads(row["value"]) if row else {}
        return merged_settings(stored)

    def save_settings(self, values):
        if not isinstance(values, dict):
            raise ValidationError("صيغة الإعدادات غير صحيحة")
        clean = {}
        for k, v in values.items():
            if k not in DEFAULT_SETTINGS:
                continue
            dv = DEFAULT_SETTINGS[k]
            if isinstance(dv, bool):
                clean[k] = bool(v)
            elif isinstance(dv, (int, float)) and not isinstance(dv, bool):
                try:
                    num = float(v)
                except (TypeError, ValueError):
                    raise ValidationError("قيمة غير رقمية للإعداد: %s" % k)
                if num < 0 or num > 1000:
                    raise ValidationError("قيمة خارج النطاق للإعداد: %s" % k)
                clean[k] = num
            elif isinstance(dv, dict):
                if not isinstance(v, dict):
                    raise ValidationError("صيغة غير صحيحة للإعداد: %s" % k)
                sub = copy.deepcopy(dv)
                for kk, vv in v.items():
                    if kk in dv:
                        sub[kk] = vv if not isinstance(dv[kk], str) else str(vv)
                clean[k] = sub
            elif isinstance(dv, list):
                if not isinstance(v, list):
                    raise ValidationError("صيغة غير صحيحة للإعداد: %s" % k)
                clean[k] = [str(x) for x in v]
            else:
                clean[k] = "" if v is None else str(v)
        # تحقق منطقي
        merged = merged_settings(clean)
        if merged["min_questions"] > merged["max_questions"]:
            raise ValidationError("الحد الأدنى لعدد الأسئلة أكبر من الحد الأعلى")
        if len(merged.get("compare_options", [])) != 4 or len(merged.get("option_labels", [])) != 4:
            raise ValidationError("يجب أن تكون خيارات المقارنة ورموز الخيارات أربعة")
        with self.tx() as c:
            c.execute("INSERT INTO settings(key, value) VALUES ('global', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                      (json.dumps(clean, ensure_ascii=False),))
        return self.get_settings()

    def apply_preset(self, name):
        if name not in PRESETS:
            raise ValidationError("قالب غير معروف")
        cur = self.conn().execute("SELECT value FROM settings WHERE key='global'").fetchone()
        stored = json.loads(cur["value"]) if cur else {}
        # إعادة قيم القالب القياسي ثم تطبيق القالب المختار (للخطوط والمسافات فقط)
        keys = set()
        for p in PRESETS.values():
            keys.update(p["values"].keys())
        for k in keys:
            stored.pop(k, None)
        stored.update(PRESETS[name]["values"])
        with self.tx() as c:
            c.execute("INSERT INTO settings(key, value) VALUES ('global', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                      (json.dumps(stored, ensure_ascii=False),))
        return self.get_settings()

    def reset_settings(self, group=None):
        with self.tx() as c:
            c.execute("DELETE FROM settings WHERE key='global'")
        return self.get_settings()

    # -------------------------------------------------------------- الأقسام
    def _section_row(self, r, counts=None):
        d = dict(r)
        if counts is not None:
            d.update(counts)
        return d

    def section_counts(self, section_id):
        c = self.conn()
        q = c.execute("SELECT COUNT(*) AS n, SUM(CASE WHEN status='complete' THEN 1 ELSE 0 END) AS ok FROM items WHERE section_id=? AND type='question'",
                      (section_id,)).fetchone()
        g = c.execute("SELECT COUNT(*) AS n FROM items WHERE section_id=? AND type='group'", (section_id,)).fetchone()
        return {"question_count": q["n"] or 0, "complete_count": q["ok"] or 0, "group_count": g["n"] or 0}

    def list_sections(self, query="", kind=None, sort="updated", status=None):
        sql = "SELECT * FROM sections WHERE 1=1"
        args = []
        if query:
            sql += " AND (title LIKE ? OR source LIKE ? OR notes LIKE ?)"
            args += ["%" + query + "%"] * 3
        if kind in ("quant", "verbal"):
            sql += " AND kind=?"
            args.append(kind)
        if status in ("draft", "complete", "review"):
            sql += " AND status=?"
            args.append(status)
        order = {
            "updated": "updated_at DESC, id DESC",
            "created": "created_at DESC, id DESC",
            "created_asc": "created_at ASC, id ASC",
            "kind": "kind ASC, updated_at DESC",
            "title": "title ASC",
        }.get(sort, "updated_at DESC, id DESC")
        rows = self.conn().execute(sql + " ORDER BY " + order, args).fetchall()
        return [self._section_row(r, self.section_counts(r["id"])) for r in rows]

    def get_section(self, section_id, with_items=False):
        r = self.conn().execute("SELECT * FROM sections WHERE id=?", (section_id,)).fetchone()
        if not r:
            raise NotFound("القسم غير موجود")
        d = self._section_row(r, self.section_counts(section_id))
        if with_items:
            d["items"] = self.get_tree(section_id)
        return d

    def create_section(self, title, kind, source, notes=""):
        title = (title or "").strip()
        source = (source or "").strip()
        if not title:
            raise ValidationError("عنوان القسم مطلوب")
        if kind not in ("quant", "verbal"):
            raise ValidationError("نوع القسم يجب أن يكون كميًا أو لفظيًا")
        if not source:
            raise ValidationError("مصدر القسم مطلوب")
        t = now()
        with self.tx() as c:
            cur = c.execute("INSERT INTO sections(title, kind, source, notes, created_at, updated_at) VALUES (?,?,?,?,?,?)",
                            (title, kind, source, notes or "", t, t))
            return cur.lastrowid

    def update_section(self, section_id, fields):
        sec = self.get_section(section_id)
        upd = {}
        if "title" in fields:
            v = (fields["title"] or "").strip()
            if not v:
                raise ValidationError("عنوان القسم مطلوب")
            upd["title"] = v
        if "source" in fields:
            v = (fields["source"] or "").strip()
            if not v:
                raise ValidationError("مصدر القسم مطلوب")
            upd["source"] = v
        if "notes" in fields:
            upd["notes"] = str(fields["notes"] or "")
        if "status" in fields:
            st = fields["status"]
            if st not in ("draft", "complete", "review"):
                raise ValidationError("حالة غير صحيحة")
            if st == "complete":
                problems = self.section_problems(section_id)
                if problems:
                    raise ValidationError("لا يمكن اعتماد القسم مكتملًا: " + "؛ ".join(problems[:4]))
            upd["status"] = st
        if "kind" in fields and fields["kind"] != sec["kind"]:
            raise ValidationError("لا يمكن تغيير نوع القسم بعد إنشائه (أنشئ قسمًا جديدًا أو انسخه)")
        if not upd:
            return sec
        upd["updated_at"] = now()
        with self.tx() as c:
            c.execute("UPDATE sections SET " + ", ".join(k + "=?" for k in upd) + " WHERE id=?", list(upd.values()) + [section_id])
        return self.get_section(section_id)

    def section_problems(self, section_id):
        sec = self.get_section(section_id)
        s = self.get_settings()
        problems = []
        n = sec["question_count"]
        if n < s["min_questions"] or n > s["max_questions"]:
            problems.append("عدد الأسئلة %d خارج النطاق المطلوب (%d–%d)" % (n, s["min_questions"], s["max_questions"]))
        rows = self.conn().execute("SELECT id, position, parent_id, status FROM items WHERE section_id=? AND type='question'", (section_id,)).fetchall()
        drafts = [r for r in rows if r["status"] != "complete"]
        if drafts:
            problems.append("يوجد %d سؤال غير مكتمل (مسودة)" % len(drafts))
        empty_groups = self.conn().execute(
            "SELECT g.id FROM items g WHERE g.section_id=? AND g.type='group' AND NOT EXISTS (SELECT 1 FROM items q WHERE q.parent_id=g.id)",
            (section_id,)).fetchall()
        if empty_groups:
            problems.append("توجد مجموعة بلا أسئلة")
        return problems

    def delete_section(self, section_id):
        self.get_section(section_id)
        with self.tx() as c:
            c.execute("DELETE FROM sections WHERE id=?", (section_id,))

    def duplicate_section(self, section_id, title=None):
        sec = self.get_section(section_id, with_items=True)
        new_id = self.create_section(title or (sec["title"] + " (نسخة)"), sec["kind"], sec["source"], sec.get("notes", ""))
        with self.tx() as c:
            self._insert_tree(new_id, strip_items(sec["items"]), None, c, sec["kind"])
        return new_id

    def _insert_tree(self, section_id, items, parent_id, c, kind=None, parent_group_kind=None):
        """يدرج شجرة عناصر داخل معاملة قائمة (c). تُعاد حساب حالة كل سؤال من بياناته."""
        t = now()
        if kind is None:
            kind = c.execute("SELECT kind FROM sections WHERE id=?", (section_id,)).fetchone()["kind"]
        for pos, it in enumerate(items):
            typ = it.get("type")
            if typ == "group":
                status = "complete"
            else:
                status = "complete" if not question_issues(it, kind, parent_group_kind) else "draft"
            cur = c.execute(
                "INSERT INTO items(section_id, parent_id, position, type, category, group_kind, data, answer, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (section_id, parent_id, pos, typ, it.get("category"), it.get("group_kind"),
                 json.dumps(it.get("data") or {}, ensure_ascii=False), it.get("answer") if it.get("answer") in ANSWERS else None, status, t, t))
            if typ == "group":
                self._insert_tree(section_id, it.get("children") or [], cur.lastrowid, c, kind, it.get("group_kind"))
        c.execute("UPDATE sections SET updated_at=? WHERE id=?", (t, section_id))

    def import_section_items(self, section_id, items):
        """إدراج عناصر (منظفة) في قسم موجود — يُستخدم للبيانات التجريبية والاستيراد."""
        sec = self.get_section(section_id)
        clean = []
        for it in items:
            if it.get("type") == "group":
                g = normalize_item(it, sec["kind"])
                g["children"] = [normalize_item(ch, sec["kind"], g["group_kind"]) for ch in it.get("children") or []]
                clean.append(g)
            else:
                clean.append(normalize_item(it, sec["kind"]))
        with self.tx() as c:
            start = c.execute("SELECT COUNT(*) AS n FROM items WHERE section_id=? AND parent_id IS NULL", (section_id,)).fetchone()["n"]
            self._insert_tree(section_id, clean, None, c, sec["kind"])
            if start:
                # الإدراج بدأ من الموضع ٠؛ نعيد ترقيم العناصر الجديدة لتأتي بعد الموجودة
                rows = c.execute("SELECT id FROM items WHERE section_id=? AND parent_id IS NULL ORDER BY created_at, id", (section_id,)).fetchall()
                self._renumber(c, section_id, None, [r["id"] for r in rows])

    # -------------------------------------------------------------- العناصر (الأسئلة والمجموعات)
    def _item_dict(self, r):
        d = dict(r)
        d["data"] = json.loads(d["data"] or "{}")
        return d

    def get_tree(self, section_id):
        rows = self.conn().execute("SELECT * FROM items WHERE section_id=? ORDER BY position ASC, id ASC", (section_id,)).fetchall()
        items = [self._item_dict(r) for r in rows]
        top = [i for i in items if i["parent_id"] is None]
        by_parent = {}
        for i in items:
            if i["parent_id"] is not None:
                by_parent.setdefault(i["parent_id"], []).append(i)
        for t in top:
            if t["type"] == "group":
                t["children"] = sorted(by_parent.get(t["id"], []), key=lambda x: (x["position"], x["id"]))
        top.sort(key=lambda x: (x["position"], x["id"]))
        sec = self.conn().execute("SELECT kind FROM sections WHERE id=?", (section_id,)).fetchone()
        kind = sec["kind"] if sec else None
        for t in top:
            self._annotate(t, kind, None)
            for ch in t.get("children", []):
                self._annotate(ch, kind, t)
        return top

    def _annotate(self, item, kind, parent):
        if item["type"] == "question":
            item["issues"] = question_issues(item, kind, parent["group_kind"] if parent else None)
        else:
            item["issues"] = group_issues(item)

    def get_item(self, item_id):
        r = self.conn().execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
        if not r:
            raise NotFound("العنصر غير موجود")
        d = self._item_dict(r)
        if d["type"] == "group":
            d["children"] = [self._item_dict(x) for x in self.conn().execute(
                "SELECT * FROM items WHERE parent_id=? ORDER BY position, id", (item_id,)).fetchall()]
        return d

    def _siblings(self, c, section_id, parent_id):
        if parent_id is None:
            return c.execute("SELECT id FROM items WHERE section_id=? AND parent_id IS NULL ORDER BY position, id", (section_id,)).fetchall()
        return c.execute("SELECT id FROM items WHERE parent_id=? ORDER BY position, id", (parent_id,)).fetchall()

    def _renumber(self, c, section_id, parent_id, order_ids):
        for pos, iid in enumerate(order_ids):
            c.execute("UPDATE items SET position=? WHERE id=?", (pos, iid))

    def create_item(self, section_id, payload, parent_id=None, position=None):
        sec = self.get_section(section_id)
        kind = sec["kind"]
        typ = payload.get("type", "question")
        parent = None
        if parent_id is not None:
            parent = self.get_item(parent_id)
            if parent["section_id"] != section_id or parent["type"] != "group":
                raise ValidationError("المجموعة غير صحيحة")
            if typ != "question":
                raise ValidationError("لا يمكن وضع مجموعة داخل مجموعة")
        clean = normalize_item(payload, kind, parent["group_kind"] if parent else None)
        t = now()
        with self.tx() as c:
            sib = [r["id"] for r in self._siblings(c, section_id, parent_id)]
            if position is None or position > len(sib) or position < 0:
                position = len(sib)
            status = "complete" if not clean["_issues"] else "draft"
            cur = c.execute(
                "INSERT INTO items(section_id, parent_id, position, type, category, group_kind, data, answer, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (section_id, parent_id, position, clean["type"], clean.get("category"), clean.get("group_kind"),
                 json.dumps(clean["data"], ensure_ascii=False), clean.get("answer"), status, t, t))
            new_id = cur.lastrowid
            sib.insert(position, new_id)
            self._renumber(c, section_id, parent_id, sib)
            # أسئلة ابتدائية للمجموعة
            if clean["type"] == "group" and payload.get("children"):
                for k, ch in enumerate(payload["children"]):
                    cc = normalize_item(ch, kind, clean["group_kind"])
                    c.execute(
                        "INSERT INTO items(section_id, parent_id, position, type, category, group_kind, data, answer, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        (section_id, new_id, k, "question", cc.get("category"), None, json.dumps(cc["data"], ensure_ascii=False),
                         cc.get("answer"), "complete" if not cc["_issues"] else "draft", t, t))
            c.execute("UPDATE sections SET updated_at=? WHERE id=?", (t, section_id))
        return new_id

    def update_item(self, item_id, payload):
        cur_item = self.get_item(item_id)
        sec = self.get_section(cur_item["section_id"])
        parent = self.get_item(cur_item["parent_id"]) if cur_item["parent_id"] else None
        merged = {"type": cur_item["type"], "category": cur_item.get("category"), "group_kind": cur_item.get("group_kind"),
                  "data": cur_item["data"], "answer": cur_item.get("answer")}
        for k in ("category", "data", "answer"):
            if k in payload:
                merged[k] = payload[k]
        if cur_item["type"] == "group" and "group_kind" in payload and payload["group_kind"] != cur_item["group_kind"]:
            raise ValidationError("لا يمكن تغيير نوع المجموعة")
        clean = normalize_item(merged, sec["kind"], parent["group_kind"] if parent else None)
        status = "complete" if not clean["_issues"] else "draft"
        t = now()
        with self.tx() as c:
            c.execute("UPDATE items SET category=?, data=?, answer=?, status=?, updated_at=? WHERE id=?",
                      (clean.get("category"), json.dumps(clean["data"], ensure_ascii=False), clean.get("answer"), status, t, item_id))
            c.execute("UPDATE sections SET updated_at=? WHERE id=?", (t, cur_item["section_id"]))
        out = self.get_item(item_id)
        out["issues"] = clean["_issues"]
        return out

    def delete_item(self, item_id):
        it = self.get_item(item_id)
        with self.tx() as c:
            c.execute("DELETE FROM items WHERE id=?", (item_id,))
            sib = [r["id"] for r in self._siblings(c, it["section_id"], it["parent_id"])]
            self._renumber(c, it["section_id"], it["parent_id"], sib)
            c.execute("UPDATE sections SET updated_at=? WHERE id=?", (now(), it["section_id"]))

    def duplicate_item(self, item_id):
        it = self.get_item(item_id)
        t = now()
        with self.tx() as c:
            sib = [r["id"] for r in self._siblings(c, it["section_id"], it["parent_id"])]
            pos = sib.index(item_id) + 1
            cur = c.execute(
                "INSERT INTO items(section_id, parent_id, position, type, category, group_kind, data, answer, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (it["section_id"], it["parent_id"], pos, it["type"], it.get("category"), it.get("group_kind"),
                 json.dumps(it["data"], ensure_ascii=False), it.get("answer"), it["status"], t, t))
            new_id = cur.lastrowid
            sib.insert(pos, new_id)
            self._renumber(c, it["section_id"], it["parent_id"], sib)
            for k, ch in enumerate(it.get("children", [])):
                c.execute(
                    "INSERT INTO items(section_id, parent_id, position, type, category, group_kind, data, answer, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (it["section_id"], new_id, k, "question", ch.get("category"), None, json.dumps(ch["data"], ensure_ascii=False),
                     ch.get("answer"), ch["status"], t, t))
            c.execute("UPDATE sections SET updated_at=? WHERE id=?", (t, it["section_id"]))
        return new_id

    def wrap_in_group(self, item_id, group_kind):
        """يحوّل سؤالًا منفردًا إلى أول سؤال في مجموعة جديدة (رسم بياني أو نص استيعاب) في الموضع نفسه."""
        it = self.get_item(item_id)
        if it["type"] != "question" or it["parent_id"] is not None:
            raise ValidationError("يمكن تحويل سؤال منفرد فقط")
        sec = self.get_section(it["section_id"])
        if group_kind == "chart" and sec["kind"] != "quant":
            raise ValidationError("الرسوم البيانية للقسم الكمي فقط")
        if group_kind == "reading" and sec["kind"] != "verbal":
            raise ValidationError("نصوص الاستيعاب للقسم اللفظي فقط")
        gdata = {"title": "", "image": None} if group_kind == "chart" else {"title": "", "passage_type": "short", "paragraphs": [""], "numbered": True}
        g = normalize_item({"type": "group", "group_kind": group_kind, "data": gdata}, sec["kind"])
        qd = dict(it["data"])
        if not qd.get("options") and qd.get("option_pairs"):
            qd["options"] = ["%s : %s" % (p.get("a", ""), p.get("b", "")) for p in qd["option_pairs"]]
        if "stem" not in qd:
            qd["stem"] = qd.get("sentence", "")
        q = normalize_item({"type": "question", "category": "chart" if group_kind == "chart" else "reading", "data": qd, "answer": it.get("answer")}, sec["kind"], group_kind)
        t = now()
        with self.tx() as c:
            sib = [r["id"] for r in self._siblings(c, it["section_id"], None)]
            pos = sib.index(item_id)
            cur = c.execute(
                "INSERT INTO items(section_id, parent_id, position, type, category, group_kind, data, answer, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (it["section_id"], None, pos, "group", None, group_kind, json.dumps(g["data"], ensure_ascii=False), None, "complete", t, t))
            gid = cur.lastrowid
            c.execute("UPDATE items SET parent_id=?, position=0, category=?, data=?, status=?, updated_at=? WHERE id=?",
                      (gid, q["category"], json.dumps(q["data"], ensure_ascii=False), "complete" if not q["_issues"] else "draft", t, item_id))
            sib[pos] = gid
            self._renumber(c, it["section_id"], None, sib)
            c.execute("UPDATE sections SET updated_at=? WHERE id=?", (t, it["section_id"]))
        return gid

    def reorder(self, section_id, order):
        """order: [{"id": X, "children": [ids]} ...] — يجب أن يحوي كل العناصر دون إضافة أو حذف."""
        self.get_section(section_id)
        c0 = self.conn()
        rows = c0.execute("SELECT id, parent_id, type FROM items WHERE section_id=?", (section_id,)).fetchall()
        top_ids = sorted(r["id"] for r in rows if r["parent_id"] is None)
        children = {}
        for r in rows:
            if r["parent_id"] is not None:
                children.setdefault(r["parent_id"], []).append(r["id"])
        new_top = [int(e["id"]) for e in order]
        if sorted(new_top) != top_ids:
            raise ValidationError("قائمة الترتيب لا تطابق عناصر القسم (أعد تحميل الصفحة)")
        for e in order:
            if "children" in e and e["children"] is not None:
                if sorted(int(x) for x in e["children"]) != sorted(children.get(int(e["id"]), [])):
                    raise ValidationError("ترتيب أسئلة المجموعة لا يطابق أسئلتها")
        with self.tx() as c:
            self._renumber(c, section_id, None, new_top)
            for e in order:
                if e.get("children") is not None:
                    self._renumber(c, section_id, int(e["id"]), [int(x) for x in e["children"]])
            c.execute("UPDATE sections SET updated_at=? WHERE id=?", (now(), section_id))
        return self.get_tree(section_id)

    def move_item(self, item_id, direction):
        it = self.get_item(item_id)
        with self.tx() as c:
            sib = [r["id"] for r in self._siblings(c, it["section_id"], it["parent_id"])]
            k = sib.index(item_id)
            j = k + (-1 if direction == "up" else 1)
            if 0 <= j < len(sib):
                sib[k], sib[j] = sib[j], sib[k]
                self._renumber(c, it["section_id"], it["parent_id"], sib)
                c.execute("UPDATE sections SET updated_at=? WHERE id=?", (now(), it["section_id"]))
        return self.get_tree(it["section_id"])

    # -------------------------------------------------------------- الصور
    def save_media(self, blob, filename=""):
        from PIL import Image
        import io
        if not blob:
            raise ValidationError("الملف فارغ")
        if len(blob) > 25 * 1024 * 1024:
            raise ValidationError("حجم الصورة كبير جدًا (الحد ٢٥ ميجابايت)")
        try:
            im = Image.open(io.BytesIO(blob))
            im.load()
        except Exception:
            raise ValidationError("الملف ليس صورة صالحة (المدعوم: PNG وJPG وGIF وBMP وWEBP)")
        fmt = (im.format or "").upper()
        # نحفظ PNG أو JPEG فقط (المدعومان في Word والمتصفح)؛ غيرها يحوّل إلى PNG
        if fmt == "JPEG":
            ext, mime, data = "jpg", "image/jpeg", blob
        elif fmt == "PNG":
            ext, mime, data = "png", "image/png", blob
        else:
            if im.mode not in ("RGB", "RGBA", "L", "LA"):
                im = im.convert("RGBA")
            buf = io.BytesIO()
            im.save(buf, "PNG")
            ext, mime, data = "png", "image/png", buf.getvalue()
        sha = hashlib.sha256(data).hexdigest()
        existing = self.conn().execute("SELECT * FROM media WHERE sha256=?", (sha,)).fetchone()
        if existing and os.path.exists(self.media_path(existing["id"], existing["ext"])):
            return dict(existing)
        mid = uuid.uuid4().hex
        path = self.media_path(mid, ext)
        tmp = path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        with self.tx() as c:
            c.execute("INSERT INTO media(id, sha256, filename, mime, ext, width, height, size, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                      (mid, sha, filename or "", mime, ext, im.width, im.height, len(data), now()))
        return dict(self.conn().execute("SELECT * FROM media WHERE id=?", (mid,)).fetchone())

    def media_path(self, mid, ext):
        return os.path.join(self.media_dir, "%s.%s" % (mid, ext))

    def get_media(self, mid):
        if not re.fullmatch(r"[0-9a-f]{32}", str(mid or "")):
            raise NotFound("صورة غير موجودة")
        r = self.conn().execute("SELECT * FROM media WHERE id=?", (mid,)).fetchone()
        if not r:
            raise NotFound("صورة غير موجودة")
        return dict(r)

    def media_map(self, ids):
        out = {}
        for mid in ids:
            try:
                m = self.get_media(mid)
            except NotFound:
                continue
            out[mid] = {"w": m["width"], "h": m["height"], "url": "/media/" + mid, "path": self.media_path(mid, m["ext"]), "mime": m["mime"]}
        return out

    # -------------------------------------------------------------- الاختبارات
    def _exam_dict(self, r):
        d = dict(r)
        d["options"] = json.loads(d["options"] or "{}")
        d["frozen"] = bool(d["frozen"])
        snap = d.pop("snapshot", None)
        d["has_snapshot"] = bool(snap)
        for key in ("quant", "verbal"):
            sid = d[key + "_section_id"]
            info = None
            if d["frozen"] and snap:
                s = json.loads(snap).get(key)
                if s:
                    info = {"id": s.get("id"), "title": s["title"], "source": s["source"], "question_count": count_questions(s["items"]), "frozen": True}
            elif sid:
                try:
                    s = self.get_section(sid)
                    info = {"id": s["id"], "title": s["title"], "source": s["source"], "question_count": s["question_count"], "status": s["status"]}
                except NotFound:
                    info = None
            d[key + "_section"] = info
        return d

    def list_exams(self, query=""):
        sql = "SELECT * FROM exams"
        args = []
        if query:
            sql += " WHERE title LIKE ? OR number LIKE ?"
            args = ["%" + query + "%"] * 2
        rows = self.conn().execute(sql + " ORDER BY updated_at DESC, id DESC", args).fetchall()
        return [self._exam_dict(r) for r in rows]

    def get_exam(self, exam_id):
        r = self.conn().execute("SELECT * FROM exams WHERE id=?", (exam_id,)).fetchone()
        if not r:
            raise NotFound("الاختبار غير موجود")
        return self._exam_dict(r)

    def _validate_exam_fields(self, f):
        title = (f.get("title") or "").strip()
        if not title:
            raise ValidationError("عنوان الاختبار مطلوب")
        q = f.get("quant_section_id")
        v = f.get("verbal_section_id")
        if q:
            s = self.get_section(int(q))
            if s["kind"] != "quant":
                raise ValidationError("القسم المختار في خانة الكمي ليس قسمًا كميًا")
        if v:
            s = self.get_section(int(v))
            if s["kind"] != "verbal":
                raise ValidationError("القسم المختار في خانة اللفظي ليس قسمًا لفظيًا")
        dur = f.get("duration")
        if dur not in (None, ""):
            try:
                dur = int(dur)
            except (TypeError, ValueError):
                raise ValidationError("مدة الاختبار يجب أن تكون رقمًا")
            if dur <= 0 or dur > 600:
                raise ValidationError("مدة الاختبار غير منطقية")
        else:
            dur = None
        opts = f.get("options") or {}
        if not isinstance(opts, dict):
            raise ValidationError("خيارات الاختبار غير صحيحة")
        return {
            "title": title, "number": str(f.get("number") or "").strip(), "header_title": str(f.get("header_title") or "").strip(),
            "quant_section_id": int(q) if q else None, "verbal_section_id": int(v) if v else None,
            "duration": dur, "options": json.dumps(opts, ensure_ascii=False),
        }

    def create_exam(self, fields):
        f = self._validate_exam_fields(fields)
        t = now()
        with self.tx() as c:
            cur = c.execute("INSERT INTO exams(title, number, header_title, quant_section_id, verbal_section_id, duration, options, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                            (f["title"], f["number"], f["header_title"], f["quant_section_id"], f["verbal_section_id"], f["duration"], f["options"], t, t))
            return cur.lastrowid

    def update_exam(self, exam_id, fields):
        ex = self.get_exam(exam_id)
        base = {"title": ex["title"], "number": ex["number"], "header_title": ex["header_title"],
                "quant_section_id": ex["quant_section_id"], "verbal_section_id": ex["verbal_section_id"],
                "duration": ex["duration"], "options": ex["options"]}
        base.update({k: v for k, v in fields.items() if k in base})
        if ex["frozen"] and (base["quant_section_id"] != ex["quant_section_id"] or base["verbal_section_id"] != ex["verbal_section_id"]):
            raise ValidationError("الاختبار معتمد (مثبَّت)؛ ألغِ الاعتماد قبل تغيير الأقسام")
        f = self._validate_exam_fields(base)
        with self.tx() as c:
            c.execute("UPDATE exams SET title=?, number=?, header_title=?, quant_section_id=?, verbal_section_id=?, duration=?, options=?, updated_at=? WHERE id=?",
                      (f["title"], f["number"], f["header_title"], f["quant_section_id"], f["verbal_section_id"], f["duration"], f["options"], now(), exam_id))
        return self.get_exam(exam_id)

    def delete_exam(self, exam_id):
        self.get_exam(exam_id)
        with self.tx() as c:
            c.execute("DELETE FROM exams WHERE id=?", (exam_id,))

    def duplicate_exam(self, exam_id):
        ex = self.get_exam(exam_id)
        return self.create_exam({"title": ex["title"] + " (نسخة)", "number": ex["number"], "header_title": ex["header_title"],
                                 "quant_section_id": ex["quant_section_id"], "verbal_section_id": ex["verbal_section_id"],
                                 "duration": ex["duration"], "options": ex["options"]})

    def exam_problems(self, exam_id):
        ex = self.get_exam(exam_id)
        s = self.get_settings()
        problems = []
        if not ex["quant_section_id"] and not (ex["frozen"] and ex["quant_section"]):
            problems.append("لم يُختر القسم الكمي")
        if not ex["verbal_section_id"] and not (ex["frozen"] and ex["verbal_section"]):
            problems.append("لم يُختر القسم اللفظي")
        for key, label in (("quant", "الكمي"), ("verbal", "اللفظي")):
            info = ex.get(key + "_section")
            if info:
                n = info["question_count"]
                if n < s["min_questions"] or n > s["max_questions"]:
                    problems.append("عدد أسئلة القسم %s (%d) خارج النطاق المطلوب %d–%d" % (label, n, s["min_questions"], s["max_questions"]))
        if not ex["frozen"]:
            for key, label in (("quant", "الكمي"), ("verbal", "اللفظي")):
                sid = ex[key + "_section_id"]
                if sid:
                    drafts = self.conn().execute("SELECT COUNT(*) AS n FROM items WHERE section_id=? AND type='question' AND status!='complete'", (sid,)).fetchone()["n"]
                    if drafts:
                        problems.append("في القسم %s %d سؤال غير مكتمل" % (label, drafts))
        return problems

    def freeze_exam(self, exam_id):
        ex = self.get_exam(exam_id)
        if ex["frozen"]:
            return ex
        problems = self.exam_problems(exam_id)
        if problems:
            raise ValidationError("لا يمكن اعتماد الاختبار: " + "؛ ".join(problems))
        snap = {}
        for key in ("quant", "verbal"):
            sec = self.get_section(ex[key + "_section_id"], with_items=True)
            snap[key] = strip_section(sec)
        with self.tx() as c:
            c.execute("UPDATE exams SET frozen=1, snapshot=?, updated_at=? WHERE id=?", (json.dumps(snap, ensure_ascii=False), now(), exam_id))
        return self.get_exam(exam_id)

    def unfreeze_exam(self, exam_id):
        self.get_exam(exam_id)
        with self.tx() as c:
            c.execute("UPDATE exams SET frozen=0, snapshot=NULL, updated_at=? WHERE id=?", (now(), exam_id))
        return self.get_exam(exam_id)

    def exam_sections_content(self, exam_id):
        """محتوى القسمين للتصدير: من النسخة المثبتة إن كان الاختبار معتمدًا، وإلا من الأقسام الحالية."""
        r = self.conn().execute("SELECT * FROM exams WHERE id=?", (exam_id,)).fetchone()
        if not r:
            raise NotFound("الاختبار غير موجود")
        out = {}
        if r["frozen"] and r["snapshot"]:
            snap = json.loads(r["snapshot"])
            out = {"quant": snap.get("quant"), "verbal": snap.get("verbal")}
        else:
            for key in ("quant", "verbal"):
                sid = r[key + "_section_id"]
                out[key] = strip_section(self.get_section(sid, with_items=True)) if sid else None
        return out

    def mark_exported(self, exam_id, kind, variant, filename):
        with self.tx() as c:
            c.execute("INSERT INTO exports(exam_id, kind, variant, filename, created_at) VALUES (?,?,?,?,?)", (exam_id, kind, variant, filename, now()))
            if exam_id:
                c.execute("UPDATE exams SET last_export_at=? WHERE id=?", (now(), exam_id))

    def list_sources(self):
        rows = self.conn().execute("SELECT DISTINCT source FROM sections WHERE source != '' ORDER BY source").fetchall()
        return [r["source"] for r in rows]

    def stats(self):
        c = self.conn()
        return {
            "sections": c.execute("SELECT COUNT(*) AS n FROM sections").fetchone()["n"],
            "quant_sections": c.execute("SELECT COUNT(*) AS n FROM sections WHERE kind='quant'").fetchone()["n"],
            "verbal_sections": c.execute("SELECT COUNT(*) AS n FROM sections WHERE kind='verbal'").fetchone()["n"],
            "questions": c.execute("SELECT COUNT(*) AS n FROM items WHERE type='question'").fetchone()["n"],
            "exams": c.execute("SELECT COUNT(*) AS n FROM exams").fetchone()["n"],
            "media": c.execute("SELECT COUNT(*) AS n FROM media").fetchone()["n"],
        }

    # -------------------------------------------------------------- النسخ الاحتياطي (JSON)
    def export_all(self):
        c = self.conn()
        sections = []
        for r in c.execute("SELECT * FROM sections ORDER BY id").fetchall():
            d = dict(r)
            d["items"] = strip_items(self.get_tree(r["id"]))
            sections.append(d)
        exams = []
        for r in c.execute("SELECT * FROM exams ORDER BY id").fetchall():
            d = dict(r)
            d["options"] = json.loads(d["options"] or "{}")
            d["snapshot"] = json.loads(d["snapshot"]) if d["snapshot"] else None
            exams.append(d)
        media = [dict(r) for r in c.execute("SELECT * FROM media ORDER BY created_at").fetchall()]
        row = c.execute("SELECT value FROM settings WHERE key='global'").fetchone()
        return {
            "format": "qudurat-exam-builder", "version": SCHEMA_VERSION, "exported_at": now(),
            "settings": json.loads(row["value"]) if row else {},
            "sections": sections, "exams": exams, "media": media,
        }

    def import_all(self, data, media_blobs, mode="merge"):
        """mode: merge (إضافة بجانب الموجود) | replace (استبدال كل البيانات)."""
        if not isinstance(data, dict) or data.get("format") != "qudurat-exam-builder":
            raise ValidationError("الملف ليس نسخة احتياطية من هذا البرنامج")
        # الصور أولًا
        media_id_map = {}
        for m in data.get("media", []):
            blob = media_blobs.get(m["id"])
            if blob is None:
                continue
            saved = self.save_media(blob, m.get("filename", ""))
            media_id_map[m["id"]] = saved["id"]
        t = now()
        with self.tx() as c:
            if mode == "replace":
                c.execute("DELETE FROM exams")
                c.execute("DELETE FROM items")
                c.execute("DELETE FROM sections")
                if data.get("settings") is not None:
                    c.execute("INSERT INTO settings(key, value) VALUES ('global', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                              (json.dumps(data["settings"], ensure_ascii=False),))
            sec_map = {}
            for s in data.get("sections", []):
                if s.get("kind") not in ("quant", "verbal"):
                    raise ValidationError("نوع قسم غير صحيح في النسخة الاحتياطية")
                cur = c.execute("INSERT INTO sections(title, kind, source, status, notes, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                                (s["title"], s["kind"], s.get("source", ""), s.get("status", "draft") if s.get("status") in ("draft", "complete", "review") else "draft",
                                 s.get("notes", ""), s.get("created_at") or t, s.get("updated_at") or t))
                sec_map[s.get("id")] = cur.lastrowid
                items = remap_media(copy.deepcopy(s.get("items", [])), media_id_map)
                self._insert_tree(cur.lastrowid, items, None, c, s["kind"])
            for e in data.get("exams", []):
                snap = e.get("snapshot")
                if snap:
                    for key in ("quant", "verbal"):
                        if snap.get(key):
                            snap[key]["items"] = remap_media(snap[key]["items"], media_id_map)
                c.execute("INSERT INTO exams(title, number, header_title, quant_section_id, verbal_section_id, duration, options, frozen, snapshot, created_at, updated_at, last_export_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                          (e["title"], e.get("number", ""), e.get("header_title", ""), sec_map.get(e.get("quant_section_id")), sec_map.get(e.get("verbal_section_id")),
                           e.get("duration"), json.dumps(e.get("options") or {}, ensure_ascii=False), 1 if e.get("frozen") and snap else 0,
                           json.dumps(snap, ensure_ascii=False) if snap else None, e.get("created_at") or t, e.get("updated_at") or t, e.get("last_export_at")))
        return {"sections": len(data.get("sections", [])), "exams": len(data.get("exams", [])), "media": len(media_id_map)}

    def export_section(self, section_id):
        sec = self.get_section(section_id, with_items=True)
        ids = collect_media_ids(sec["items"])
        media = [self.get_media(m) for m in ids if self._media_exists(m)]
        return {"format": "qudurat-exam-builder", "version": SCHEMA_VERSION, "exported_at": now(), "settings": None,
                "sections": [dict(strip_section(sec), id=sec["id"], status=sec["status"], notes=sec.get("notes", ""))], "exams": [], "media": media}

    def _media_exists(self, mid):
        try:
            self.get_media(mid)
            return True
        except NotFound:
            return False


class _Tx:
    def __init__(self, db):
        self.db = db

    def __enter__(self):
        _lock.acquire()
        self.c = self.db.conn()
        self.c.execute("BEGIN IMMEDIATE")
        return self.c

    def __exit__(self, et, ev, tb):
        try:
            if et is None:
                self.c.execute("COMMIT")
            else:
                self.c.execute("ROLLBACK")
        finally:
            _lock.release()
        return False


# ------------------------------------------------------------------ أدوات البنية
def count_questions(items):
    n = 0
    for it in items or []:
        if it["type"] == "question":
            n += 1
        else:
            n += len(it.get("children") or [])
    return n


def strip_items(items):
    out = []
    for it in items:
        d = {"id": it["id"], "type": it["type"], "category": it.get("category"), "group_kind": it.get("group_kind"),
             "data": it["data"], "answer": it.get("answer"), "status": it.get("status", "draft")}
        if it["type"] == "group":
            d["children"] = strip_items(it.get("children") or [])
        out.append(d)
    return out


def strip_section(sec):
    return {"id": sec["id"], "title": sec["title"], "kind": sec["kind"], "source": sec["source"], "items": strip_items(sec.get("items") or [])}


def collect_media_ids(items):
    ids = []
    for it in items or []:
        img = (it.get("data") or {}).get("image") or {}
        if img.get("media_id"):
            ids.append(img["media_id"])
        ids += collect_media_ids(it.get("children") or [])
    seen = set()
    return [x for x in ids if not (x in seen or seen.add(x))]


def remap_media(items, mapping):
    for it in items or []:
        img = (it.get("data") or {}).get("image")
        if img and img.get("media_id") in mapping:
            img["media_id"] = mapping[img["media_id"]]
        remap_media(it.get("children") or [], mapping)
    return items


# ------------------------------------------------------------------ تنظيف بيانات الأسئلة والتحقق منها
def _s(v, maxlen=20000):
    v = "" if v is None else str(v)
    return v[:maxlen]


def normalize_item(payload, section_kind, group_kind=None):
    typ = payload.get("type", "question")
    if typ not in ("question", "group"):
        raise ValidationError("نوع عنصر غير صحيح")
    data = payload.get("data") or {}
    if not isinstance(data, dict):
        raise ValidationError("بيانات السؤال غير صحيحة")
    if typ == "group":
        gk = payload.get("group_kind")
        if gk not in ("chart", "reading"):
            raise ValidationError("نوع المجموعة غير صحيح")
        if gk == "chart" and section_kind != "quant":
            raise ValidationError("مجموعات الرسوم البيانية للقسم الكمي فقط")
        if gk == "reading" and section_kind != "verbal":
            raise ValidationError("نصوص الاستيعاب للقسم اللفظي فقط")
        d = {"title": _s(data.get("title"), 300)}
        if gk == "chart":
            d["image"] = _image(data.get("image"))
        else:
            d["passage_type"] = "long" if data.get("passage_type") == "long" else "short"
            paras = data.get("paragraphs") or []
            if not isinstance(paras, list):
                raise ValidationError("فقرات النص غير صحيحة")
            d["paragraphs"] = [sanitize_rich(p) for p in paras][:100]
            d["numbered"] = bool(data.get("numbered", True))
            if data.get("align") in ("center", "justify", "right"):
                d["align"] = data["align"]
        clean = {"type": "group", "group_kind": gk, "category": None, "data": d, "answer": None}
        clean["_issues"] = group_issues(clean)
        return clean

    cat = payload.get("category")
    if section_kind == "quant":
        allowed = ("chart",) if group_kind == "chart" else ("regular", "geometry")
    else:
        allowed = ("reading",) if group_kind == "reading" else ("analogy", "completion", "odd", "context")
    if cat not in allowed:
        if group_kind == "chart":
            cat = "chart"
        elif group_kind == "reading":
            cat = "reading"
        else:
            raise ValidationError("تصنيف السؤال غير مناسب لهذا القسم")
    otype = data.get("options_type", "short")
    if otype not in ("short", "long", "compare"):
        otype = "short"
    if otype == "compare" and section_kind != "quant":
        otype = "short"
    d = {"options_type": otype}
    if cat == "analogy":
        pair = data.get("pair") or {}
        d["pair"] = {"a": _s(pair.get("a"), 500).strip(), "b": _s(pair.get("b"), 500).strip()}
        pairs = data.get("option_pairs") or []
        d["option_pairs"] = []
        for k in range(4):
            p = pairs[k] if k < len(pairs) and isinstance(pairs[k], dict) else {}
            d["option_pairs"].append({"a": _s(p.get("a"), 500).strip(), "b": _s(p.get("b"), 500).strip()})
    elif cat == "context":
        sentence = _s(data.get("sentence"), 5000)
        d["sentence"] = sentence
        sels = []
        for sel in (data.get("selections") or [])[:4]:
            try:
                st, en = int(sel.get("start")), int(sel.get("end"))
            except (TypeError, ValueError, AttributeError):
                continue
            if 0 <= st < en <= len(sentence):
                sels.append({"start": st, "end": en, "text": sentence[st:en]})
        sels.sort(key=lambda x: x["start"])
        # منع التداخل
        clean_sels = []
        for sel in sels:
            if clean_sels and sel["start"] < clean_sels[-1]["end"]:
                continue
            clean_sels.append(sel)
        d["selections"] = clean_sels
    else:
        if cat != "odd":
            d["stem"] = sanitize_rich(data.get("stem"))
        if otype == "compare":
            cmp_ = data.get("compare") or {}
            d["compare"] = {"v1": sanitize_rich(cmp_.get("v1")), "v2": sanitize_rich(cmp_.get("v2"))}
        else:
            opts = data.get("options") or []
            d["options"] = [sanitize_rich(opts[k]) if k < len(opts) else "" for k in range(4)]
    if cat == "geometry":
        d["image"] = _image(data.get("image"))
        d["image_placement"] = data.get("image_placement") if data.get("image_placement") in ("below", "side", "above") else "below"
    if data.get("note"):
        d["note"] = _s(data.get("note"), 2000)
    ans = payload.get("answer")
    ans = ans if ans in ANSWERS else None
    clean = {"type": "question", "category": cat, "group_kind": None, "data": d, "answer": ans}
    clean["_issues"] = question_issues(clean, section_kind, group_kind)
    return clean


def _image(img):
    if not isinstance(img, dict) or not img.get("media_id"):
        return None
    mid = str(img.get("media_id"))
    if not re.fullmatch(r"[0-9a-f]{32}", mid):
        return None
    try:
        w = float(img.get("width_cm")) if img.get("width_cm") not in (None, "") else None
    except (TypeError, ValueError):
        w = None
    if w is not None:
        w = max(1.0, min(w, 20.0))
    return {"media_id": mid, "width_cm": w}


def question_issues(item, section_kind, group_kind):
    d = item.get("data") or {}
    cat = item.get("category")
    issues = []
    otype = d.get("options_type", "short")
    if cat == "analogy":
        p = d.get("pair") or {}
        if not p.get("a") or not p.get("b"):
            issues.append("طرفا السؤال غير مكتملين")
        pairs = d.get("option_pairs") or []
        if len(pairs) < 4 or any(not x.get("a") or not x.get("b") for x in pairs[:4]):
            issues.append("الخيارات الأربعة غير مكتملة (كل خيار طرفان)")
    elif cat == "context":
        if not (d.get("sentence") or "").strip():
            issues.append("الجملة فارغة")
        if len(d.get("selections") or []) != 4:
            issues.append("يجب تحديد أربع كلمات من الجملة (المحدد: %d)" % len(d.get("selections") or []))
    elif cat == "odd":
        if len([o for o in (d.get("options") or []) if not rich_empty(o)]) < 4:
            issues.append("الخيارات الأربعة غير مكتملة")
    else:
        if otype == "compare":
            c = d.get("compare") or {}
            if rich_empty(c.get("v1")) or rich_empty(c.get("v2")):
                issues.append("قيمتا المقارنة غير مكتملتين")
        else:
            if rich_empty(d.get("stem")):
                issues.append("نص السؤال فارغ")
            if len([o for o in (d.get("options") or []) if not rich_empty(o)]) < 4:
                issues.append("الخيارات الأربعة غير مكتملة")
        if cat == "completion" and "...." not in (d.get("stem") or "") and "…" not in (d.get("stem") or ""):
            issues.append("لا يوجد فراغ في جملة الإكمال")
    if cat == "geometry" and not (d.get("image") or {}).get("media_id"):
        issues.append("لم تُرفق صورة الرسم الهندسي")
    if item.get("answer") not in ANSWERS:
        issues.append("لم تُحدد الإجابة الصحيحة")
    return issues


def group_issues(item):
    d = item.get("data") or {}
    issues = []
    if item.get("group_kind") == "chart":
        if not (d.get("image") or {}).get("media_id"):
            issues.append("لم يُرفع الرسم البياني")
    elif item.get("group_kind") == "reading":
        if not [p for p in d.get("paragraphs") or [] if not rich_empty(p)]:
            issues.append("نص القراءة فارغ")
    return issues
