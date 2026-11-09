# -*- coding: utf-8 -*-
"""أدوات مشتركة للاختبارات: تشغيل الخادم داخل العملية على منفذ حر ببيانات مؤقتة."""
import json
import os
import socket
import sys
import tempfile
import threading
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
APP = os.path.join(ROOT, "app")
if APP not in sys.path:
    sys.path.insert(0, APP)

_SERVER = {}


def playwright_available():
    try:
        import playwright  # noqa: F401
        return True
    except Exception:
        return False


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def server():
    """يشغّل خادمًا واحدًا لكل جلسة اختبار ويعيد (base_url, server_module)."""
    if _SERVER:
        return _SERVER["base"], _SERVER["mod"]
    import server as srv
    data = tempfile.mkdtemp(prefix="qudurat_test_")
    port = free_port()
    srv.init_app(data, port)
    import license_gate
    license_gate.accept(data, True)
    t = threading.Thread(target=srv.serve, args=(port, 4), daemon=True)
    t.start()
    base = "http://127.0.0.1:%d" % port
    for _ in range(100):
        try:
            urllib.request.urlopen(base + "/api/system", timeout=1)
            break
        except Exception:
            time.sleep(0.1)
    _SERVER.update(base=base, mod=srv, data=data)
    return base, srv


def http(method, path, body=None):
    base, _ = server()
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(base + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            raw = r.read()
            ctype = r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode("utf-8"))
    if "json" in ctype:
        return json.loads(raw.decode("utf-8"))
    return raw


def download(path):
    base, _ = server()
    with urllib.request.urlopen(base + urllib.parse.quote(path, safe="/?=&"), timeout=60) as r:
        return r.read()


def demo():
    """ينشئ القسمين والاختبار التجريبي (مرة واحدة)."""
    if "demo" not in _SERVER:
        _, srv = server()
        _SERVER["demo"] = srv.create_demo(srv.DB())
    return _SERVER["demo"]


def flatten_qids(items):
    out = []
    for it in items:
        if it["type"] == "group":
            out += [c["id"] for c in it.get("children") or []]
        else:
            out.append(it["id"])
    return out


import urllib.parse  # noqa: E402
