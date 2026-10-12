"""可被 unittest / 直接运行的自检。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lexicon.cli import cmd_selftest
from lexicon.mschxudp import MAGIC, build_dat, verify_dat
from lexicon.mask import classify_text
from lexicon.pinyin_util import is_valid_ime_pinyin, to_pinyin


class TestMschxudp(unittest.TestCase):
    def test_magic(self):
        data = build_dat([("测试词", "ceshici", 1)], timestamp=1)
        self.assertEqual(data[:8], MAGIC)
        self.assertEqual(data[:8], b"mschxudp")

    def test_verify(self):
        out = Path(__file__).parent / "_unit_out.dat"
        out.write_bytes(build_dat([("微软拼音", "weiruanpinyin", 1)], timestamp=2))
        ok, msg = verify_dat(out)
        self.assertTrue(ok, msg)


class TestMask(unittest.TestCase):
    def test_phone(self):
        sens, reason = classify_text("联系电话13812345678")
        self.assertTrue(sens)
        self.assertEqual(reason, "电话")

    def test_company(self):
        sens, reason = classify_text("某某科技有限公司")
        self.assertTrue(sens)
        self.assertEqual(reason, "客户全称")


class TestPinyin(unittest.TestCase):
    def test_valid(self):
        py = to_pinyin("微软拼音")
        if py != "拼音待核":
            self.assertTrue(is_valid_ime_pinyin(py), py)



class TestBrowse(unittest.TestCase):
    def test_browse_non_windows_cancels(self):
        from lexicon.webui import _do_browse, browse_folder
        # On Linux box, browse_folder returns None; API reports cancelled.
        self.assertIsNone(browse_folder(""))
        r = _do_browse("source", "/tmp")
        self.assertFalse(r.get("ok"))
        self.assertTrue(r.get("cancelled"))

    def test_browse_which_validation(self):
        from lexicon.webui import _do_browse
        r = _do_browse("nope", "")
        self.assertFalse(r.get("ok"))
        self.assertTrue(r.get("cancelled"))

    def test_html_has_browse_buttons(self):
        from lexicon.webui import HTML_PAGE
        self.assertIn("浏览…", HTML_PAGE)
        self.assertIn("doBrowse('source')", HTML_PAGE)
        self.assertIn("doBrowse('output')", HTML_PAGE)
        self.assertIn("/api/browse", HTML_PAGE)

if __name__ == "__main__":
    # 先跑 cli selftest
    class NS:
        output = str(Path(__file__).parent / "_selftest_out")

    rc = cmd_selftest(NS())
    if rc != 0:
        raise SystemExit(rc)
    unittest.main()
