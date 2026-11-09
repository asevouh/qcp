# -*- coding: utf-8 -*-
"""
مُنشئ اختبارات القدرات المحاكية — الخادم المحلي.
يعمل على جهاز المستخدم فقط (127.0.0.1) ويفتح الواجهة في المتصفح.
"""
import argparse
import datetime as _dt
import io
import json
import os
import re
import shutil
import socket
import sqlite3
import sys
import threading
import time
import uuid
import webbrowser
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from flask import Flask, Response, abort, jsonify, request, send_file, send_from_directory  # noqa: E402

import db as dbm  # noqa: E402
import exporter  # noqa: E402
import fonts  # noqa: E402
import license_gate  # noqa: E402
from defaults import PRESETS  # noqa: E402

VERSION = "1.0.0"
ROOT = os.path.dirname(HERE)

app = Flask(__name__, static_folder=os.path.join(HERE, "static"), static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = 300 * 1024 * 1024
app.json.ensure_ascii = False

STATE = {"db": None, "worker": None, "data_dir": None, "port": None}


def DB():
    return STATE["db"]


def ok(data=None, **kw):
    out = {"ok": True}
    if data is not None:
        out["data"] = data
    out.update(kw)
    return jsonify(out)


@app.errorhandler(dbm.ValidationError)
def _val(e):
    return jsonify({"ok": False, "error": str(e)}), 400


@app.errorhandler(dbm.NotFound)
def _nf(e):
    return jsonify({"ok": False, "error": str(e)}), 404


@app.errorhandler(exporter.ExportError)
def _exp(e):
    return jsonify({"ok": False, "error": "تعذر التصدير: " + str(e)}), 500


@app.errorhandler(Exception)
def _any(e):
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        return e
    app.logger.exception(e)
    return jsonify({"ok": False, "error": "حدث خطأ غير متوقع: %s" % e}), 500


@app.after_request
def _no_cache(resp):
    if request.path.startswith("/api/") or request.path.endswith(".js") or request.path.endswith(".css") or request.path in ("/", "/fonts.css"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


def body():
    return request.get_json(force=True, silent=True) or {}


# ------------------------------------------------------------------ الترخيص
# لا تعمل واجهات البرنامج قبل الإقرار بقراءة الترخيص وقبوله (ولا تعمل أبدًا إن كان ملف الترخيص مفقودًا أو معدَّلًا).
LICENSE_OPEN = {"/api/license", "/api/license/accept", "/api/system", "/api/shutdown"}


@app.before_request
def _license_gate():
    if request.path.startswith("/api/") and request.path not in LICENSE_OPEN:
        if not license_gate.is_accepted(STATE["data_dir"]):
            return jsonify({"ok": False, "error": "يجب قبول ترخيص البرنامج قبل استخدامه.", "license_required": True}), 403


@app.route("/api/license")
def license_info():
    text, _ = license_gate.read_license()
    st = license_gate.status(STATE["data_dir"])
    st["text"] = text if st["state"] == "ok" else None
    return ok(st)


@app.route("/api/license/accept", methods=["POST"])
def license_accept():
    try:
        return ok(license_gate.accept(STATE["data_dir"], body().get("acknowledged")))
    except ValueError as e:
        raise dbm.ValidationError(str(e))


@app.route("/license.txt")
def license_file():
    text, _ = license_gate.read_license()
    if text is None:
        abort(404)
    return Response(text, mimetype="text/plain; charset=utf-8")


# ------------------------------------------------------------------ الصفحات والملفات
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/fonts.css")
def fonts_css():
    fam = DB().get_settings().get("font_family") or "Calibri"
    return Response(fonts.fonts_css(fam), mimetype="text/css")


@app.route("/sysfont/<style>")
def sysfont(style):
    fam = DB().get_settings().get("font_family") or "Calibri"
    info = fonts.find_font(fam)
    path = info["files"].get(style)
    if not path or not os.path.exists(path):
        abort(404)
    return send_file(path, mimetype="font/ttf")


@app.route("/media/<mid>")
def media(mid):
    m = DB().get_media(mid)
    path = DB().media_path(m["id"], m["ext"])
    if not os.path.exists(path):
        abort(404)
    resp = send_file(path, mimetype=m["mime"])
    resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return resp


@app.route("/exports/<path:sub>")
def exports(sub):
    base = os.path.join(STATE["data_dir"], "exports")
    full = os.path.abspath(os.path.join(base, sub))
    if not full.startswith(os.path.abspath(base) + os.sep) or not os.path.exists(full):
        abort(404)
    inline = request.args.get("inline") == "1"
    mt = "application/pdf" if full.endswith(".pdf") else None
    return send_file(full, mimetype=mt, as_attachment=not inline, download_name=os.path.basename(full))


# ------------------------------------------------------------------ النظام
@app.route("/api/system")
def system():
    s = DB().get_settings()
    w = STATE["worker"]
    return ok({
        "version": VERSION, "stats": DB().stats(), "font": fonts.status(s.get("font_family") or "Calibri"),
        "browser": w.browser_name if w else None, "data_dir": STATE["data_dir"],
    })


@app.route("/api/shutdown", methods=["POST"])
def shutdown():
    def later():
        time.sleep(0.6)
        os._exit(0)
    threading.Thread(target=later, daemon=True).start()
    return ok()


# ------------------------------------------------------------------ الإعدادات
@app.route("/api/settings", methods=["GET", "PUT"])
def settings():
    if request.method == "PUT":
        return ok(DB().save_settings(body()))
    return ok(DB().get_settings())


@app.route("/api/settings/preset", methods=["POST"])
def preset():
    return ok(DB().apply_preset(body().get("name")))


@app.route("/api/settings/reset", methods=["POST"])
def reset_settings():
    return ok(DB().reset_settings())


@app.route("/api/presets")
def presets():
    return ok({k: v["name"] for k, v in PRESETS.items()})


# ------------------------------------------------------------------ الأقسام
@app.route("/api/sources")
def sources():
    return ok(DB().list_sources())


@app.route("/api/sections", methods=["GET", "POST"])
def sections():
    if request.method == "POST":
        b = body()
        sid = DB().create_section(b.get("title"), b.get("kind"), b.get("source"), b.get("notes", ""))
        return ok(DB().get_section(sid, with_items=True))
    a = request.args
    return ok(DB().list_sections(a.get("q", ""), a.get("kind"), a.get("sort", "updated"), a.get("status")))


@app.route("/api/sections/<int:sid>", methods=["GET", "PUT", "DELETE"])
def section(sid):
    if request.method == "PUT":
        DB().update_section(sid, body())
        return ok(DB().get_section(sid, with_items=True))
    if request.method == "DELETE":
        used = [e for e in DB().list_exams() if (e["quant_section_id"] == sid or e["verbal_section_id"] == sid)]
        DB().delete_section(sid)
        return ok({"affected_exams": [e["title"] for e in used]})
    return ok(DB().get_section(sid, with_items=True))


@app.route("/api/sections/<int:sid>/duplicate", methods=["POST"])
def section_dup(sid):
    nid = DB().duplicate_section(sid, body().get("title"))
    return ok(DB().get_section(nid))


@app.route("/api/sections/<int:sid>/problems")
def section_problems(sid):
    return ok(DB().section_problems(sid))


@app.route("/api/sections/<int:sid>/items", methods=["POST"])
def section_items(sid):
    b = body()
    item = b.get("item") or {}
    iid = DB().create_item(sid, item, b.get("parent_id"), b.get("position"))
    return ok({"id": iid, "items": DB().get_tree(sid)})


@app.route("/api/sections/<int:sid>/reorder", methods=["POST"])
def section_reorder(sid):
    return ok(DB().reorder(sid, body().get("order") or []))


@app.route("/api/items/<int:iid>", methods=["GET", "PUT", "DELETE"])
def item(iid):
    if request.method == "PUT":
        return ok(DB().update_item(iid, body()))
    if request.method == "DELETE":
        it = DB().get_item(iid)
        DB().delete_item(iid)
        return ok({"items": DB().get_tree(it["section_id"])})
    return ok(DB().get_item(iid))


@app.route("/api/items/<int:iid>/duplicate", methods=["POST"])
def item_dup(iid):
    it = DB().get_item(iid)
    nid = DB().duplicate_item(iid)
    return ok({"id": nid, "items": DB().get_tree(it["section_id"])})


@app.route("/api/items/<int:iid>/move", methods=["POST"])
def item_move(iid):
    return ok(DB().move_item(iid, body().get("direction")))


@app.route("/api/items/<int:iid>/wrap", methods=["POST"])
def item_wrap(iid):
    it = DB().get_item(iid)
    gid = DB().wrap_in_group(iid, body().get("group_kind"))
    return ok({"group_id": gid, "items": DB().get_tree(it["section_id"])})


@app.route("/api/media", methods=["POST"])
def upload_media():
    f = request.files.get("file")
    if not f:
        raise dbm.ValidationError("لم يُرسل ملف")
    m = DB().save_media(f.read(), f.filename or "")
    return ok({"id": m["id"], "width": m["width"], "height": m["height"], "url": "/media/" + m["id"]})


@app.route("/api/media/<mid>")
def media_info(mid):
    m = DB().get_media(mid)
    return ok({"id": m["id"], "width": m["width"], "height": m["height"], "url": "/media/" + m["id"]})


# ------------------------------------------------------------------ الاختبارات
@app.route("/api/exams", methods=["GET", "POST"])
def exams():
    if request.method == "POST":
        eid = DB().create_exam(body())
        return ok(DB().get_exam(eid))
    return ok(DB().list_exams(request.args.get("q", "")))


@app.route("/api/exams/<int:eid>", methods=["GET", "PUT", "DELETE"])
def exam(eid):
    if request.method == "PUT":
        return ok(DB().update_exam(eid, body()))
    if request.method == "DELETE":
        DB().delete_exam(eid)
        return ok()
    return ok(DB().get_exam(eid))


@app.route("/api/exams/<int:eid>/duplicate", methods=["POST"])
def exam_dup(eid):
    return ok(DB().get_exam(DB().duplicate_exam(eid)))


@app.route("/api/exams/<int:eid>/problems")
def exam_problems(eid):
    return ok(DB().exam_problems(eid))


@app.route("/api/exams/<int:eid>/freeze", methods=["POST"])
def exam_freeze(eid):
    return ok(DB().freeze_exam(eid))


@app.route("/api/exams/<int:eid>/unfreeze", methods=["POST"])
def exam_unfreeze(eid):
    return ok(DB().unfreeze_exam(eid))


def safe_name(s):
    s = re.sub(r'[\\/:*?"<>|\r\n\t]+', " ", s or "").strip()
    return re.sub(r"\s+", " ", s)[:120] or "اختبار"


def exam_export_info(ex):
    opts = ex.get("options") or {}
    return {
        "title": ex["title"], "number": ex["number"], "header_title": ex.get("header_title") or ex["title"],
        "duration": ex.get("duration"), "big_title": opts.get("big_title") or None,
    }


def ordered_sections(ex, content):
    order = (ex.get("options") or {}).get("section_order", "quant_first")
    secs = [content.get("quant"), content.get("verbal")]
    if order == "verbal_first":
        secs.reverse()
    return secs


@app.route("/api/exams/<int:eid>/export", methods=["POST"])
def exam_export(eid):
    b = body()
    ex = DB().get_exam(eid)
    content = DB().exam_sections_content(eid)
    secs = ordered_sections(ex, content)
    if not any(secs):
        raise dbm.ValidationError("اختر القسمين قبل التصدير")
    formats = [f for f in (b.get("formats") or ["pdf", "docx"]) if f in ("pdf", "docx")]
    variant = b.get("variant", "student")
    opts = ex.get("options") or {}
    out_dir = os.path.join(STATE["data_dir"], "exports", "exam-%d" % eid)
    base = safe_name(ex["title"])
    info = exam_export_info(ex)
    if variant == "key":
        files, key = exporter.export_answer_key(STATE["worker"], DB(), secs, info, out_dir, base + " - مفتاح الإجابة", formats)
        report = {"answerKey": key}
    else:
        suffix = " - نسخة المعلم" if variant == "teacher" else ""
        files, report, _layout = exporter.export_exam(STATE["worker"], DB(), secs, info, out_dir, base + suffix, formats,
                                                      variant="teacher" if variant == "teacher" else "student",
                                                      include_cover=opts.get("include_cover", True))
        report.pop("plan", None)
    for k, p in files.items():
        DB().mark_exported(eid, k, variant, os.path.basename(p))
    urls = {k: "/exports/exam-%d/%s" % (eid, os.path.basename(p)) for k, p in files.items()}
    return ok({"files": urls, "report": report, "folder": out_dir})


def _preview(secs, info, include_cover):
    pid = uuid.uuid4().hex[:12]
    out_dir = os.path.join(STATE["data_dir"], "exports", "preview")
    files, report, _layout = exporter.export_exam(STATE["worker"], DB(), secs, info, out_dir, "preview-" + pid, ("pdf",),
                                                  include_cover=include_cover)
    report.pop("plan", None)
    return {"url": "/exports/preview/preview-%s.pdf?inline=1" % pid, "report": report}


@app.route("/api/exams/<int:eid>/preview", methods=["POST"])
def exam_preview(eid):
    ex = DB().get_exam(eid)
    content = DB().exam_sections_content(eid)
    secs = ordered_sections(ex, content)
    if not any(secs):
        raise dbm.ValidationError("اختر قسمًا واحدًا على الأقل للمعاينة")
    return ok(_preview(secs, exam_export_info(ex), (ex.get("options") or {}).get("include_cover", True)))


@app.route("/api/sections/<int:sid>/preview", methods=["POST"])
def section_preview(sid):
    sec = dbm.strip_section(DB().get_section(sid, with_items=True))
    return ok(_preview([sec], {"title": sec["title"], "header_title": sec["title"], "duration": None}, False))


# ------------------------------------------------------------------ النسخ الاحتياطي
def make_backup_zip(data, media_rows):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("data.json", json.dumps(data, ensure_ascii=False, indent=1))
        for m in media_rows:
            p = DB().media_path(m["id"], m["ext"])
            if os.path.exists(p):
                z.write(p, "media/%s.%s" % (m["id"], m["ext"]))
        z.writestr("README.txt", "نسخة احتياطية من برنامج مُنشئ اختبارات القدرات. استعدها من صفحة النسخ الاحتياطي في البرنامج.\n")
    buf.seek(0)
    return buf


@app.route("/api/backup")
def backup():
    data = DB().export_all()
    buf = make_backup_zip(data, data["media"])
    name = "نسخة-احتياطية-%s.zip" % _dt.datetime.now().strftime("%Y-%m-%d-%H%M")
    return send_file(buf, mimetype="application/zip", as_attachment=True, download_name=name)


@app.route("/api/sections/<int:sid>/export-file")
def section_export_file(sid):
    data = DB().export_section(sid)
    buf = make_backup_zip(data, data["media"])
    name = "قسم-%s.zip" % safe_name(data["sections"][0]["title"])
    return send_file(buf, mimetype="application/zip", as_attachment=True, download_name=name)


def read_backup_upload(f):
    raw = f.read()
    if not raw:
        raise dbm.ValidationError("الملف فارغ")
    if raw[:2] == b"PK":
        try:
            z = zipfile.ZipFile(io.BytesIO(raw))
        except zipfile.BadZipFile:
            raise dbm.ValidationError("ملف مضغوط تالف")
        if "data.json" not in z.namelist():
            raise dbm.ValidationError("الملف لا يحتوي على data.json")
        data = json.loads(z.read("data.json").decode("utf-8"))
        blobs = {}
        for n in z.namelist():
            m = re.fullmatch(r"media/([0-9a-f]{32})\.\w+", n)
            if m:
                blobs[m.group(1)] = z.read(n)
        return data, blobs
    try:
        return json.loads(raw.decode("utf-8")), {}
    except Exception:
        raise dbm.ValidationError("صيغة الملف غير مدعومة (المطلوب: ملف zip أو json من هذا البرنامج)")


@app.route("/api/restore", methods=["POST"])
def restore():
    f = request.files.get("file")
    if not f:
        raise dbm.ValidationError("لم يُرسل ملف")
    mode = request.form.get("mode", "merge")
    if mode not in ("merge", "replace"):
        raise dbm.ValidationError("طريقة استعادة غير معروفة")
    data, blobs = read_backup_upload(f)
    auto_backup("before-restore")
    res = DB().import_all(data, blobs, mode)
    return ok(res)


@app.route("/api/backups")
def backups_list():
    d = os.path.join(STATE["data_dir"], "backups")
    out = []
    if os.path.isdir(d):
        for n in sorted(os.listdir(d), reverse=True):
            if n.endswith(".db"):
                out.append({"name": n, "size": os.path.getsize(os.path.join(d, n))})
    return ok(out)


@app.route("/api/backups/<name>")
def backups_get(name):
    if not re.fullmatch(r"[\w\-.]+\.db", name):
        abort(404)
    p = os.path.join(STATE["data_dir"], "backups", name)
    if not os.path.exists(p):
        abort(404)
    return send_file(p, as_attachment=True, download_name=name)


@app.route("/api/demo", methods=["POST"])
def demo():
    ids = create_demo(DB())
    return ok(ids)


def create_demo(database):
    import sample_data as sd
    media = {}
    for n, fn in (("chart", sd.make_chart_png), ("triangle", sd.make_triangle_png), ("circles", sd.make_circles_png)):
        media[n] = database.save_media(fn(), n + ".png")["id"]
    q = sd.sample_quant(media)
    v = sd.fix_context_offsets(sd.sample_verbal())
    qid = database.create_section(q["title"], "quant", q["source"])
    database.import_section_items(qid, q["items"])
    vid = database.create_section(v["title"], "verbal", v["source"])
    database.import_section_items(vid, v["items"])
    eid = database.create_exam({"title": "الاختبار التجريبي", "number": "١", "quant_section_id": qid, "verbal_section_id": vid, "duration": 26})
    return {"quant": qid, "verbal": vid, "exam": eid}


def auto_backup(tag="auto", keep=15):
    d = os.path.join(STATE["data_dir"], "backups")
    os.makedirs(d, exist_ok=True)
    src = DB().path
    if not os.path.exists(src):
        return None
    name = "%s-%s.db" % (tag, _dt.datetime.now().strftime("%Y%m%d-%H%M%S"))
    dst = os.path.join(d, name)
    try:
        s = sqlite3.connect(src)
        t = sqlite3.connect(dst)
        with t:
            s.backup(t)
        s.close()
        t.close()
    except Exception:
        return None
    files = sorted([n for n in os.listdir(d) if n.startswith(tag + "-") and n.endswith(".db")])
    for old in files[:-keep]:
        try:
            os.remove(os.path.join(d, old))
        except OSError:
            pass
    return dst


def clean_previews():
    d = os.path.join(STATE["data_dir"], "exports", "preview")
    if os.path.isdir(d):
        now = time.time()
        for n in os.listdir(d):
            p = os.path.join(d, n)
            try:
                if now - os.path.getmtime(p) > 3600:
                    os.remove(p)
            except OSError:
                pass


# ------------------------------------------------------------------ التشغيل
def free_port(start):
    for p in range(start, start + 30):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    raise RuntimeError("لا يوجد منفذ متاح")


def init_app(data_dir, port):
    os.makedirs(data_dir, exist_ok=True)
    STATE["data_dir"] = data_dir
    STATE["db"] = dbm.Database(os.path.join(data_dir, "exams.db"))
    STATE["port"] = port
    STATE["worker"] = exporter.RenderWorker("http://127.0.0.1:%d" % port)
    return app


def serve(port, threads=8):
    import logging
    logging.getLogger("waitress.queue").setLevel(logging.ERROR)
    try:
        from waitress import serve as wserve
        wserve(app, host="127.0.0.1", port=port, threads=threads, ident="qudurat")
    except ImportError:
        app.run(host="127.0.0.1", port=port, threaded=True, use_reloader=False)


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="مُنشئ اختبارات القدرات المحاكية")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--data", default=os.path.join(ROOT, "data"))
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--demo", action="store_true", help="إنشاء بيانات تجريبية إن كانت قاعدة البيانات فارغة")
    args = ap.parse_args()
    port = free_port(args.port)
    init_app(os.path.abspath(args.data), port)
    auto_backup("auto")
    clean_previews()
    if args.demo and DB().stats()["sections"] == 0:
        create_demo(DB())
    STATE["worker"].start()
    url = "http://127.0.0.1:%d/" % port
    print("=" * 60)
    print(" مُنشئ اختبارات القدرات يعمل الآن على: %s" % url)
    print(" Qudurat Exam Builder is running at: %s" % url)
    print(" البيانات محفوظة في: %s" % STATE["data_dir"])
    print(" لإيقاف البرنامج: أغلق هذه النافذة أو اضغط زر الإيقاف في الواجهة.")
    print("=" * 60)
    if not args.no_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    serve(port)


if __name__ == "__main__":
    main()
