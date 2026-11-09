# -*- coding: utf-8 -*-
"""اكتشاف خط المستند (Calibri افتراضيًا) على الجهاز، وقراءة مقاييسه، وإنشاء ملف fonts.css."""
import glob
import os
import platform
import subprocess
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
BUNDLED = os.path.join(HERE, "static", "fonts")

# أسماء ملفات شائعة لخطوط معروفة (يُبحث أيضًا بالاسم الداخلي عند الحاجة)
KNOWN_FILES = {
    "calibri": {"regular": ["calibri.ttf", "Calibri.ttf"], "bold": ["calibrib.ttf", "Calibri Bold.ttf", "calibri-bold.ttf"]},
    "arial": {"regular": ["arial.ttf", "Arial.ttf"], "bold": ["arialbd.ttf", "Arial Bold.ttf"]},
    "times new roman": {"regular": ["times.ttf", "Times New Roman.ttf"], "bold": ["timesbd.ttf", "Times New Roman Bold.ttf"]},
    "tahoma": {"regular": ["tahoma.ttf", "Tahoma.ttf"], "bold": ["tahomabd.ttf", "Tahoma Bold.ttf"]},
    "sakkal majalla": {"regular": ["majalla.ttf"], "bold": ["majallab.ttf"]},
    "traditional arabic": {"regular": ["trado.ttf"], "bold": ["tradbdo.ttf"]},
    "simplified arabic": {"regular": ["simpo.ttf"], "bold": ["simpbdo.ttf"]},
    "segoe ui": {"regular": ["segoeui.ttf"], "bold": ["segoeuib.ttf"]},
}
# مقاييس معروفة (الصعود+النزول)/وحدات الخط، تُستخدم إن لم يوجد ملف الخط
KNOWN_FACTORS = {"calibri": 1.2207, "arial": 1.1499, "times new roman": 1.1499, "tahoma": 1.2075}

_cache = {}
_lock = threading.Lock()


def font_dirs():
    dirs = []
    sysname = platform.system()
    if sysname == "Windows":
        windir = os.environ.get("WINDIR", r"C:\Windows")
        dirs.append(os.path.join(windir, "Fonts"))
        local = os.environ.get("LOCALAPPDATA")
        if local:
            dirs.append(os.path.join(local, "Microsoft", "Windows", "Fonts"))
    elif sysname == "Darwin":
        dirs += ["/Library/Fonts", os.path.expanduser("~/Library/Fonts"), "/System/Library/Fonts", "/System/Library/Fonts/Supplemental"]
        for app in ("Microsoft Word.app", "Microsoft PowerPoint.app", "Microsoft Excel.app", "Microsoft Outlook.app"):
            dirs.append("/Applications/%s/Contents/Resources/DFonts" % app)
    else:
        dirs += ["/usr/share/fonts", "/usr/local/share/fonts", os.path.expanduser("~/.fonts"), os.path.expanduser("~/.local/share/fonts")]
    # مجلد اختياري داخل البرنامج: يمكن للمستخدم وضع ملفات الخط فيه
    dirs.append(os.path.join(os.path.dirname(HERE), "data", "fonts"))
    return [d for d in dirs if os.path.isdir(d)]


def _scan_by_name(family):
    """يبحث في مجلدات الخطوط عن ملف اسمه الداخلي يطابق العائلة (أبطأ؛ يستخدم عند عدم المعرفة المسبقة)."""
    try:
        from fontTools.ttLib import TTFont
    except Exception:
        return {}
    fam = family.lower()
    found = {}
    for d in font_dirs():
        for path in glob.glob(os.path.join(d, "**", "*.tt[fc]"), recursive=True) + glob.glob(os.path.join(d, "**", "*.otf"), recursive=True):
            try:
                t = TTFont(path, lazy=True, fontNumber=0)
                name = t["name"]
                fname = (name.getDebugName(16) or name.getDebugName(1) or "").lower()
                sub = (name.getDebugName(17) or name.getDebugName(2) or "").lower()
                t.close()
            except Exception:
                continue
            if fname == fam:
                if sub in ("regular", "normal", "book", "roman") and "regular" not in found:
                    found["regular"] = path
                elif sub == "bold" and "bold" not in found:
                    found["bold"] = path
        if "regular" in found:
            break
    return found


def find_font(family):
    key = (family or "").strip().lower()
    with _lock:
        if key in _cache:
            return _cache[key]
    found = {}
    names = KNOWN_FILES.get(key)
    if names:
        for d in font_dirs():
            for style in ("regular", "bold"):
                if style in found:
                    continue
                for n in names[style]:
                    p = os.path.join(d, n)
                    if os.path.exists(p):
                        found[style] = p
                        break
    if "regular" not in found and key:
        found.update({k: v for k, v in _scan_by_name(family).items() if k not in found})
    info = {"family": family, "files": found, "found": "regular" in found}
    info["factor"] = metrics_factor(found.get("regular")) or KNOWN_FACTORS.get(key) or 1.2207
    info["has_arabic"] = has_arabic(found.get("regular")) if found.get("regular") else None
    with _lock:
        _cache[key] = info
    return info


def metrics_factor(path):
    if not path:
        return None
    try:
        from fontTools.ttLib import TTFont
        t = TTFont(path, lazy=True, fontNumber=0)
        upm = t["head"].unitsPerEm
        os2 = t["OS/2"]
        f = (os2.usWinAscent + os2.usWinDescent) / float(upm)
        t.close()
        return round(f, 4)
    except Exception:
        return None


def has_arabic(path):
    try:
        from fontTools.ttLib import TTFont
        t = TTFont(path, lazy=True, fontNumber=0)
        cmap = t.getBestCmap() or {}
        t.close()
        return all(c in cmap for c in (0x0627, 0x0628, 0x0661))
    except Exception:
        return None


def fonts_css(family):
    info = find_font(family)
    fam = (family or "Calibri").replace('"', "")
    reg_src = ['local("%s")' % fam, 'local("%s Regular")' % fam]
    bold_src = ['local("%s Bold")' % fam, 'local("%s-Bold")' % fam.replace(" ", "")]
    if info["files"].get("regular"):
        reg_src.append('url("/sysfont/regular")')
    if info["files"].get("bold"):
        bold_src.append('url("/sysfont/bold")')
    css = []
    css.append('@font-face { font-family: "QSymbols"; src: url("/static/fonts/ExamSymbols-Regular.ttf") format("truetype"); unicode-range: U+2052; }')
    css.append('@font-face { font-family: "QPrimary"; src: %s; font-weight: 400; font-style: normal; }' % ", ".join(reg_src))
    css.append('@font-face { font-family: "QPrimary"; src: %s; font-weight: 700; font-style: normal; }' % ", ".join(bold_src))
    for w, n in ((400, "Regular"), (700, "Bold")):
        css.append('@font-face { font-family: "QLatinFallback"; src: url("/static/fonts/ExamLatinFallback-%s.ttf") format("truetype"); font-weight: %d; }' % (n, w))
        css.append('@font-face { font-family: "QArabicFallback"; src: url("/static/fonts/ExamArabicFallback-%s.ttf") format("truetype"); font-weight: %d; }' % (n, w))
    return "\n".join(css) + "\n"


def status(family):
    info = find_font(family)
    return {
        "family": family,
        "found": info["found"],
        "files": {k: os.path.basename(v) for k, v in info["files"].items()},
        "has_arabic": info["has_arabic"],
        "factor": info["factor"],
    }
