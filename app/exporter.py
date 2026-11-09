# -*- coding: utf-8 -*-
"""
محرك التصدير: يشغّل متصفح Chromium (بدون واجهة) لتنفيذ محرك التخطيط نفسه المستخدم في المعاينة،
ثم ينتج PDF مباشرة من الصفحات المخططة، ويعيد خطة التوزيع وصور المعادلات لبناء ملف Word.

المتصفح يعمل في خيط مستقل ثابت (Playwright لا يقبل الاستخدام من خيوط متعددة).
"""
import base64
import json
import os
import queue
import threading
import time
import traceback

import fonts
from docx_writer import DocxWriter, build_answer_key_docx

HERE = os.path.dirname(os.path.abspath(__file__))
SYMBOLS_FONT = os.path.join(HERE, "static", "fonts", "ExamSymbols-Regular.ttf")


class ExportError(Exception):
    pass


class RenderWorker:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")
        self.q = queue.Queue()
        self.thread = None
        self.browser_name = None
        self.browser_error = None
        self._started = threading.Event()

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.thread = threading.Thread(target=self._loop, name="render-worker", daemon=True)
        self.thread.start()

    def _launch(self, pw):
        errors = []
        attempts = [("chromium", {}), ("msedge", {"channel": "msedge"}), ("chrome", {"channel": "chrome"})]
        for name, kw in attempts:
            try:
                b = pw.chromium.launch(headless=True, **kw)
                self.browser_name = name
                return b
            except Exception as e:  # noqa
                errors.append("%s: %s" % (name, str(e).splitlines()[0] if str(e) else e))
        raise ExportError("تعذر تشغيل المتصفح اللازم للتصدير. شغّل ملف الإعداد مرة أخرى (setup) أو ثبّت Microsoft Edge أو Google Chrome.\n" + "\n".join(errors))

    def _loop(self):
        try:
            from playwright.sync_api import sync_playwright
        except Exception as e:
            self.browser_error = "مكتبة Playwright غير مثبتة: %s" % e
            self._started.set()
            while True:
                job = self.q.get()
                job["error"] = self.browser_error
                job["done"].set()
        with sync_playwright() as pw:
            browser = None
            self._started.set()
            while True:
                job = self.q.get()
                if job is None:
                    break
                try:
                    if browser is None or not browser.is_connected():
                        browser = self._launch(pw)
                    job["result"] = self._run_job(browser, job)
                except Exception as e:  # noqa
                    job["error"] = str(e)
                    job["trace"] = traceback.format_exc()
                    try:
                        if browser is not None and not browser.is_connected():
                            browser = None
                    except Exception:
                        browser = None
                finally:
                    job["done"].set()
            if browser:
                browser.close()

    def _run_job(self, browser, job):
        ctx = browser.new_context(viewport={"width": 1000, "height": 1400}, device_scale_factor=1)
        page = ctx.new_page()
        logs = []
        page.on("console", lambda m: logs.append(m.text))
        page.on("pageerror", lambda e: logs.append("ERROR: %s" % e))
        try:
            page.goto(self.base_url + "/static/shared/export.html", wait_until="load", timeout=60000)
            page.wait_for_function("window.QExportReady === true", timeout=30000)
            font_status = page.evaluate("() => QExport.loadFonts()")
            page.emulate_media(media="print")
            out = {"fonts": font_status, "logs": logs}
            if job["kind"] == "exam":
                res = page.evaluate("(d) => QExport.runExam(d)", job["payload"])
                out["layout"] = res
                if job.get("math"):
                    out["math_images"] = page.evaluate("(s) => QExport.mathImages(s)", job.get("math_scale", 6))
            elif job["kind"] == "key":
                out["layout"] = page.evaluate("(d) => QExport.runKey(d)", job["payload"])
            if job.get("pdf"):
                out["pdf"] = page.pdf(prefer_css_page_size=True, print_background=True, margin={"top": "0", "right": "0", "bottom": "0", "left": "0"})
            if job.get("png_pages"):
                pages = page.query_selector_all("#doc .page")
                shots = []
                for p in pages[: job.get("png_pages")]:
                    shots.append(p.screenshot(type="png"))
                out["png"] = shots
            return out
        finally:
            ctx.close()

    def submit(self, kind, payload, pdf=True, math=False, png_pages=0, timeout=180):
        self.start()
        self._started.wait(60)
        job = {"kind": kind, "payload": payload, "pdf": pdf, "math": math, "png_pages": png_pages, "done": threading.Event()}
        self.q.put(job)
        if not job["done"].wait(timeout):
            raise ExportError("انتهت مهلة التصدير")
        if job.get("error"):
            raise ExportError(job["error"])
        return job["result"]


def prepare_settings(settings):
    """يضبط مقياس الخط الفعلي (من ملف الخط إن وُجد) حتى تتطابق ارتفاعات الأسطر مع Word."""
    s = dict(settings)
    info = fonts.find_font(s.get("font_family") or "Calibri")
    s["font_metrics_factor"] = info["factor"]
    return s


def build_payload(db, sections, settings, exam_info, variant="student", include_cover=True, include_end=True):
    from db import collect_media_ids
    ids = []
    for sec in sections:
        if sec:
            ids += collect_media_ids(sec["items"])
    media = db.media_map(ids)
    payload = {
        "settings": settings, "sections": sections, "exam": exam_info, "variant": variant,
        "media": {k: {"w": v["w"], "h": v["h"], "url": v["url"]} for k, v in media.items()},
        "includeCover": include_cover, "includeEndText": include_end,
    }
    return payload, media


def export_exam(worker, db, sections, exam_info, out_dir, basename, formats=("pdf", "docx"), variant="student",
                include_cover=True, include_end=True, settings=None):
    """ينتج الملفات المطلوبة ويعيد مسارها مع تقرير التحقق."""
    settings = prepare_settings(settings or db.get_settings())
    payload, media = build_payload(db, sections, settings, exam_info, variant, include_cover, include_end)
    want_docx = "docx" in formats
    res = worker.submit("exam", payload, pdf=("pdf" in formats), math=want_docx)
    layout = res["layout"]
    os.makedirs(out_dir, exist_ok=True)
    files = {}
    if "pdf" in formats:
        p = os.path.join(out_dir, basename + ".pdf")
        _atomic_write(p, res["pdf"])
        files["pdf"] = p
    if want_docx:
        w = DocxWriter(settings, SYMBOLS_FONT)
        w.build(layout, media, res.get("math_images") or [], layout["info"], include_cover=include_cover,
                mode=settings.get("word_layout_mode") or "match")
        p = os.path.join(out_dir, basename + ".docx")
        tmp = p + ".tmp"
        w.save(tmp)
        os.replace(tmp, p)
        files["docx"] = p
    report = {
        "pages": layout.get("pageCount"),
        "warnings": layout.get("warnings"),
        "overflow": layout.get("overflow"),
        "brokenImages": layout.get("brokenImages"),
        "fonts": res.get("fonts"),
        "primaryFontLoaded": any(f["family"] == "QPrimary" and f["status"] == "loaded" for f in res.get("fonts") or []),
        "mathErrors": [b for b in _math_errors(layout.get("blocks") or [])],
        "browser": worker.browser_name,
        "order": [b.get("qid") for b in layout.get("blocks") or [] if b.get("type") == "question"],
        "plan": layout.get("plan"),
        "logs": [l for l in res.get("logs") or [] if "ERROR" in l][:20],
    }
    return files, report, layout


def export_answer_key(worker, db, sections, exam_info, out_dir, basename, formats=("pdf", "docx"), settings=None):
    settings = prepare_settings(settings or db.get_settings())
    payload, _media = build_payload(db, sections, settings, exam_info, "student", False, False)
    files = {}
    res = worker.submit("key", payload, pdf=("pdf" in formats))
    os.makedirs(out_dir, exist_ok=True)
    if "pdf" in formats:
        p = os.path.join(out_dir, basename + ".pdf")
        _atomic_write(p, res["pdf"])
        files["pdf"] = p
    if "docx" in formats:
        p = os.path.join(out_dir, basename + ".docx")
        build_answer_key_docx(settings, res["layout"]["answerKey"], sections, exam_info.get("title"), p + ".tmp")
        os.replace(p + ".tmp", p)
        files["docx"] = p
    return files, res["layout"]["answerKey"]


def _math_errors(blocks):
    out = []

    def scan(runs, where):
        for r in runs or []:
            if r.get("t") == "math" and r.get("error"):
                out.append({"where": where, "latex": r.get("latex"), "error": r.get("error")})
    for b in blocks:
        if b.get("type") == "question":
            w = b.get("numberLabel", "")
            scan(b.get("stem"), w)
            for it in (b.get("options") or {}).get("items", []):
                scan(it.get("runs"), w)
            if b.get("compare"):
                scan(b["compare"].get("v1"), w)
                scan(b["compare"].get("v2"), w)
        elif b.get("type") == "passage":
            scan(b.get("runs"), "نص القراءة")
    return out


def _atomic_write(path, data):
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
