# -*- coding: utf-8 -*-
"""
بوابة الترخيص: لا يعمل البرنامج قبل أن يقرّ المستخدم بقراءة الترخيص وقبوله.

- نص الترخيص في ملف LICENSE.txt بجذر البرنامج.
- تُحسب بصمة النص (SHA-256 بعد توحيد نهايات الأسطر وحذف علامة BOM والمسافات في آخر الأسطر)،
  وتُقارن بالبصمة المعتمدة أدناه؛ فإن كان الملف مفقودًا أو معدَّلًا رفض البرنامج العمل.
- يُحفظ الإقرار في ملف license_acceptance.json داخل مجلد البيانات مع بصمة النص الذي قُبل،
  فإذا تغيّر نص الترخيص في إصدار لاحق طُلب الإقرار من جديد.

عند تحديث نص الترخيص رسميًا: شغّل  python app/license_gate.py  واستبدل LICENSE_SHA256 بالقيمة التي يطبعها.
"""
import datetime as _dt
import getpass
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LICENSE_PATH = os.path.join(ROOT, "LICENSE.txt")
LICENSE_VERSION = "1.1"
LICENSE_SHA256 = "caebab0e12e977aa91737edc34b5c5538b84e60ee979d8d5f76c92b06c69cb37"
ACCEPT_FILE = "license_acceptance.json"


def _normalize(raw):
    text = raw.decode("utf-8-sig")
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return "\n".join(l.rstrip() for l in lines).strip("\n")


def read_license():
    """يعيد (النص، البصمة) أو (None, None) إن لم يوجد الملف."""
    try:
        with open(LICENSE_PATH, "rb") as f:
            raw = f.read()
    except OSError:
        return None, None
    try:
        text = _normalize(raw)
    except UnicodeDecodeError:
        return None, None
    return text, hashlib.sha256(text.encode("utf-8")).hexdigest()


def _accept_path(data_dir):
    return os.path.join(data_dir, ACCEPT_FILE)


def status(data_dir):
    text, digest = read_license()
    if text is None:
        return {"state": "missing", "accepted": False}
    if digest != LICENSE_SHA256:
        return {"state": "tampered", "accepted": False}
    rec = None
    try:
        with open(_accept_path(data_dir), "r", encoding="utf-8") as f:
            rec = json.load(f)
    except (OSError, ValueError):
        rec = None
    accepted = bool(rec and rec.get("sha256") == digest and rec.get("acknowledged") is True)
    return {"state": "ok", "accepted": accepted, "version": LICENSE_VERSION,
            "accepted_at": rec.get("accepted_at") if accepted else None}


def is_accepted(data_dir):
    return status(data_dir).get("accepted", False)


def accept(data_dir, acknowledged):
    st = status(data_dir)
    if st["state"] != "ok":
        raise ValueError("ملف الترخيص مفقود أو معدَّل؛ لا يمكن قبوله. احصل على النسخة الأصلية من صانع البرنامج.")
    if acknowledged is not True:
        raise ValueError("يجب الإقرار بقراءة بنود الترخيص وقبولها أولًا.")
    _, digest = read_license()
    try:
        user = getpass.getuser()
    except Exception:  # noqa
        user = ""
    rec = {
        "license_version": LICENSE_VERSION, "sha256": digest, "acknowledged": True,
        "accepted_at": _dt.datetime.now().isoformat(timespec="seconds"), "os_user": user,
    }
    os.makedirs(data_dir, exist_ok=True)
    tmp = _accept_path(data_dir) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    os.replace(tmp, _accept_path(data_dir))
    return status(data_dir)


if __name__ == "__main__":
    print(read_license()[1])
