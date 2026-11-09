# -*- coding: utf-8 -*-
"""
إعداد نسخة نظيفة من البرنامج للمشاركة والنشر.

الخطوات:
  ١) ينسخ البرنامج كله إلى «مجلد عمل» بجوار مجلد البرنامج (لا يُمس المجلد الأصلي إطلاقًا).
  ٢) يحذف من النسخة فقط: البيانات والنسخ الاحتياطية والملفات المُصدَّرة وإقرار الترخيص وكل أثر للمستخدم،
     والملفات المؤقتة والمنشأة تلقائيًا، وأدوات الصيانة هذه نفسها.
  ٣) يتحقق من سلامة النسخة: وجود الملفات الأساسية، وسلامة ملف الترخيص، وخلوّها من مسارات الجهاز واسم المستخدم.
  ٤) يضغطها في ملف ZIP جاهز للتوزيع، ثم يتحقق من سلامة الملف المضغوط.

الاستعمال:  python tools/make_release.py        (أو انقر مرتين على tools/make_release_windows.bat)
يعمل بمكتبة Python القياسية وحدها.
"""
import sys
sys.dont_write_bytecode = True  # التحقق يقرأ وحدة الترخيص من النسخة؛ يجب ألا يُنشئ ذلك __pycache__ داخلها

import datetime as _dt
import fnmatch
import getpass
import os
import re
import shutil
import stat
import sys
import zipfile

TOOLS = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(TOOLS)                       # جذر البرنامج
PACKAGE_NAME = "QuduratExamBuilder"
WORK = os.path.join(os.path.dirname(SRC), "مجلد عمل")   # بجوار مجلد البرنامج
COPY = os.path.join(WORK, PACKAGE_NAME)

# لا يُنسخ أصلًا (ضخم أو خاص بهذا الجهاز)
SKIP_ON_COPY = {".venv", "venv", "env", ".git", "مجلد عمل"}

# يُحذف من النسخة (مسارات نسبية من جذر النسخة)
REMOVE_PATHS = [
    "data",              # قاعدة البيانات، الصور، الملفات المُصدَّرة، النسخ الاحتياطية، إقرار الترخيص، الخطوط المضافة
    "tools",             # أدوات الصيانة (هذا السكربت) لا توزَّع
    "test_report.html",  # تقرير اختبارات فيه مسار الجهاز واسم المستخدم؛ يُنشأ من جديد عند تشغيل الاختبارات
    ".claude", ".vscode", ".idea",
]
# أنماط أسماء تُحذف أينما وُجدت
REMOVE_PATTERNS = ["__pycache__", "*.pyc", "*.pyo", "*.tmp", "*.log", "*.bak", "~$*", ".~lock.*",
                   "Thumbs.db", "desktop.ini", ".DS_Store", "*.db-wal", "*.db-shm", ".pytest_cache"]

REQUIRED = ["LICENSE.txt", "README.txt", "requirements.txt", "setup_windows.bat", "start_windows.bat",
            "app/server.py", "app/license_gate.py", "app/static/index.html", "دليل_التشغيل.html"]

TEXT_EXT = {".py", ".js", ".html", ".css", ".txt", ".json", ".bat", ".command", ".sh", ".md"}
EXEC_EXT = {".sh", ".command"}


def say(msg):
    print(msg, flush=True)


def fail(msg):
    say("\n[FAILED] " + msg)
    say("No release package was created.")
    sys.exit(1)


def _force_remove(func, path, _exc):
    """حذف الملفات المحمية من الكتابة على Windows."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except OSError:
        pass


def inside(path, root):
    path, root = os.path.realpath(path), os.path.realpath(root)
    return os.path.commonpath([path, root]) == root and path != root


def remove(path):
    # حماية: لا حذف إلا داخل مجلد العمل
    if not inside(path, WORK):
        fail("Refused to delete outside the work folder: " + path)
    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path, onerror=_force_remove)
    elif os.path.lexists(path):
        try:
            os.remove(path)
        except PermissionError:
            os.chmod(path, stat.S_IWRITE)
            os.remove(path)


def read_version():
    try:
        with open(os.path.join(SRC, "app", "server.py"), encoding="utf-8") as f:
            m = re.search(r'^VERSION\s*=\s*"([^"]+)"', f.read(), re.M)
            return m.group(1) if m else "0"
    except OSError:
        return "0"


def step_copy():
    say("[1/4] Copying the program to the work folder...")
    say("      from: " + SRC)
    say("      to:   " + COPY)
    os.makedirs(WORK, exist_ok=True)
    if os.path.exists(COPY):
        remove(COPY)
    shutil.copytree(SRC, COPY, ignore=lambda d, names: [n for n in names if n in SKIP_ON_COPY])


def step_clean():
    say("[2/4] Removing user data, backups, generated files and usage traces from the copy...")
    removed = []
    for rel in REMOVE_PATHS:
        p = os.path.join(COPY, rel)
        if os.path.lexists(p):
            remove(p)
            removed.append(rel)
    for dirpath, dirnames, filenames in os.walk(COPY, topdown=True):
        for name in list(dirnames) + list(filenames):
            if any(fnmatch.fnmatch(name, pat) for pat in REMOVE_PATTERNS):
                p = os.path.join(dirpath, name)
                remove(p)
                removed.append(os.path.relpath(p, COPY))
                if name in dirnames:
                    dirnames.remove(name)
    for r in removed:
        say("      removed: " + r.replace(os.sep, "/"))
    if not removed:
        say("      nothing to remove.")


def step_verify():
    say("[3/4] Verifying the copy...")
    missing = [r for r in REQUIRED if not os.path.exists(os.path.join(COPY, r))]
    if missing:
        fail("Required files are missing from the copy: " + ", ".join(missing))
    # الترخيص سليم ومطابق للبصمة المعتمدة
    sys.path.insert(0, os.path.join(COPY, "app"))
    try:
        import license_gate  # noqa: E402  (من النسخة نفسها)
        _, digest = license_gate.read_license()
        if digest != license_gate.LICENSE_SHA256:
            fail("LICENSE.txt in the copy is modified or does not match the approved fingerprint.")
    finally:
        sys.path.pop(0)
        sys.modules.pop("license_gate", None)
    # احتياط: إن أنشأ أي مكوّن ملفات مؤقتة أثناء التحقق تُحذف قبل الفحص النهائي
    for dirpath, dirnames, _f in os.walk(COPY):
        for d in list(dirnames):
            if d == "__pycache__":
                remove(os.path.join(dirpath, d))
                dirnames.remove(d)
    # لا بقايا ممنوعة
    for dirpath, dirnames, filenames in os.walk(COPY):
        rel = os.path.relpath(dirpath, COPY)
        top = rel.split(os.sep)[0]
        if top in REMOVE_PATHS or top in SKIP_ON_COPY:
            fail("A forbidden folder is still in the copy: " + rel)
        for n in dirnames + filenames:
            if any(fnmatch.fnmatch(n, pat) for pat in REMOVE_PATTERNS):
                fail("A forbidden file is still in the copy: " + os.path.join(rel, n))
    # لا مسارات من هذا الجهاز ولا اسم المستخدم داخل الملفات النصية
    needles = {os.path.expanduser("~"), os.path.expanduser("~").replace("\\", "/"), SRC, SRC.replace("\\", "/")}
    try:
        user = getpass.getuser()
        if user and len(user) >= 3:
            needles.add("\\Users\\" + user)
            needles.add("/Users/" + user)
    except Exception:  # noqa
        pass
    needles = {n.lower() for n in needles if n}
    for dirpath, _d, filenames in os.walk(COPY):
        for n in filenames:
            ext = os.path.splitext(n)[1].lower()
            p = os.path.join(dirpath, n)
            if ext == ".docx":
                # خصائص ملفات Word (المؤلف، آخر من عدّل…) قد تحمل اسم المستخدم
                try:
                    with zipfile.ZipFile(p) as dz:
                        content = " ".join(dz.read(m).decode("utf-8", "ignore") for m in dz.namelist() if m.startswith("docProps/")).lower()
                except (OSError, zipfile.BadZipFile):
                    continue
            elif ext in TEXT_EXT:
                try:
                    with open(p, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read().lower()
                except OSError:
                    continue
            else:
                continue
            for nd in needles:
                if nd in content:
                    fail("File %s contains a path or user name from this computer (%s)." % (os.path.relpath(p, COPY), nd))
    say("      required files present, license intact, no user data or local paths found.")


def step_zip(version):
    stamp = _dt.date.today().strftime("%Y%m%d")
    zpath = os.path.join(WORK, "%s-v%s-%s.zip" % (PACKAGE_NAME, version, stamp))
    say("[4/4] Creating the ZIP package...")
    if os.path.exists(zpath):
        remove(zpath)
    count = 0
    with zipfile.ZipFile(zpath, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for dirpath, dirnames, filenames in os.walk(COPY):
            dirnames.sort()
            for n in sorted(filenames):
                full = os.path.join(dirpath, n)
                arc = PACKAGE_NAME + "/" + os.path.relpath(full, COPY).replace(os.sep, "/")
                info = zipfile.ZipInfo.from_file(full, arc)
                info.compress_type = zipfile.ZIP_DEFLATED
                mode = 0o755 if os.path.splitext(n)[1].lower() in EXEC_EXT else 0o644
                info.external_attr = (stat.S_IFREG | mode) << 16
                with open(full, "rb") as f:
                    z.writestr(info, f.read(), compresslevel=9)
                count += 1
    with zipfile.ZipFile(zpath) as z:
        bad = z.testzip()
        if bad:
            fail("The ZIP file is corrupt at: " + bad)
        names = z.namelist()
    if PACKAGE_NAME + "/LICENSE.txt" not in names:
        fail("LICENSE.txt is missing from the ZIP file.")
    size = os.path.getsize(zpath) / (1024 * 1024)
    return zpath, count, size


def open_folder():
    """يفتح مجلد العمل في مستكشف الملفات (تظهر فيه الأسماء العربية بوضوح، بخلاف نافذة cmd)."""
    if os.environ.get("RELEASE_NO_OPEN") == "1":
        return
    try:
        if sys.platform.startswith("win"):
            os.startfile(WORK)  # noqa
            say("      the work folder has been opened in File Explorer.")
    except OSError:
        pass


def main():
    if not os.path.exists(os.path.join(SRC, "app", "server.py")):
        fail("The program was not found in: " + SRC)
    version = read_version()
    say("Qudurat Exam Builder - release packaging, version %s\n" % version)
    step_copy()
    step_clean()
    step_verify()
    zpath, count, size = step_zip(version)
    say("\n[OK] Release package is ready.")
    say("      clean copy:  " + COPY)
    say("      ZIP package: " + zpath)
    say("      files: %d - size: %.1f MB" % (count, size))
    say("      the original program folder was not changed.")
    open_folder()


if __name__ == "__main__":
    main()
