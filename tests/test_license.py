# -*- coding: utf-8 -*-
"""اختبارات بوابة الترخيص: الإقرار، ومنع الاستخدام قبله، ورفض ملف الترخيص المعدَّل."""
import os
import shutil
import tempfile
import unittest
from unittest import mock

import helpers  # noqa: F401  (يضيف مجلد app إلى المسار)
import license_gate


class LicenseGateTest(unittest.TestCase):
    def setUp(self):
        self.data = tempfile.mkdtemp(prefix="qudurat_lic_")

    def tearDown(self):
        shutil.rmtree(self.data, ignore_errors=True)

    def test_original_license_intact(self):
        text, digest = license_gate.read_license()
        self.assertIsNotNone(text)
        self.assertIn("علي برغله", text)
        self.assertEqual(digest, license_gate.LICENSE_SHA256, "نص LICENSE.txt لا يطابق البصمة المعتمدة")

    def test_not_accepted_until_acknowledged(self):
        self.assertFalse(license_gate.is_accepted(self.data))
        with self.assertRaises(ValueError):
            license_gate.accept(self.data, False)
        self.assertFalse(license_gate.is_accepted(self.data))
        st = license_gate.accept(self.data, True)
        self.assertTrue(st["accepted"])
        self.assertTrue(license_gate.is_accepted(self.data))

    def test_tampered_license_refused(self):
        tmp = os.path.join(self.data, "LICENSE.txt")
        with open(license_gate.LICENSE_PATH, "rb") as f:
            raw = f.read()
        with open(tmp, "wb") as f:
            f.write(raw.replace("ثانوية مجمع المعجل التعليمي".encode("utf-8"), "أي مدرسة".encode("utf-8")))
        with mock.patch.object(license_gate, "LICENSE_PATH", tmp):
            self.assertEqual(license_gate.status(self.data)["state"], "tampered")
            with self.assertRaises(ValueError):
                license_gate.accept(self.data, True)

    def test_line_endings_do_not_matter(self):
        tmp = os.path.join(self.data, "LICENSE.txt")
        with open(license_gate.LICENSE_PATH, "rb") as f:
            raw = f.read().replace(b"\r\n", b"\n")
        with open(tmp, "wb") as f:
            f.write(b"\xef\xbb\xbf" + raw.replace(b"\n", b"\r\n"))
        with mock.patch.object(license_gate, "LICENSE_PATH", tmp):
            self.assertEqual(license_gate.status(self.data)["state"], "ok")

    def test_acceptance_reset_when_license_changes(self):
        license_gate.accept(self.data, True)
        with mock.patch.object(license_gate, "LICENSE_SHA256", "0" * 64):
            self.assertFalse(license_gate.is_accepted(self.data))

    def test_api_blocked_before_acceptance(self):
        base, srv = helpers.server()
        other = tempfile.mkdtemp(prefix="qudurat_lic_srv_")
        old = srv.STATE["data_dir"]
        try:
            srv.STATE["data_dir"] = other
            r = helpers.http("GET", "/api/sections")
            self.assertFalse(r.get("ok"))
            self.assertTrue(r.get("license_required"))
            self.assertTrue(helpers.http("GET", "/api/license")["ok"])
            helpers.http("POST", "/api/license/accept", {"acknowledged": True})
            self.assertTrue(helpers.http("GET", "/api/sections")["ok"])
        finally:
            srv.STATE["data_dir"] = old
            shutil.rmtree(other, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
