"""FundBrowserService：无同类组时的筛选参数必须显式拒绝，不能静默忽略。纯离线。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.fund_browser_service import FundBrowserService


class FundBrowserFilterValidationTest(unittest.TestCase):
    def test_return_filter_without_peer_group_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            FundBrowserService().browse(return_1y_min=0)
        self.assertIn("peer_group is required", str(ctx.exception))
        self.assertIn("return_1y_min", str(ctx.exception))

    def test_style_tags_without_peer_group_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            FundBrowserService().browse(style_tags=["成长"])
        self.assertIn("style_tags", str(ctx.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
