"""Numbers the UI states must equal the constants that enforce them (audit #99).

Why this exists
---------------
A recurring defect family in this repo is a stated number that reality does not
honour: earnings that ignored refunds (#91), a discount on a fee nobody charges
(#92), a bundle price two credits above the charge (#93), a cart total that was
not the amount payable (#94), facet counts clicking did not deliver (#96), a
creator rating that differed between two pages (#98).

Several of those were one number computed in two places. The same shape exists
wherever the frontend hardcodes a POLICY number the server also defines: a
refund window, a referral bonus, a minimum bundle size, a password rule. Today
they all agree -- this was verified by reading each pair -- and the point of
this test is that they keep agreeing. A server-side change to any of these
constants otherwise leaves the interface quietly stating the old rule, and the
user follows what they were told and is refused.

Where a value can be served instead of duplicated, serving it is better (#93
made the server quote bundle prices). These four are static policy shown as
prose, so the cheap correct thing is to pin them together.
"""
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "main"))

FRONTEND = REPO_ROOT / "frontend" / "src"


def frontend_text(*relative_paths):
    return "\n".join((FRONTEND / p).read_text(encoding="utf-8") for p in relative_paths)


def stated_numbers(text, unit):
    """Every number the page states before `unit`, e.g. 72 from "72時間以内".

    Extracting the value keeps a failure readable: asserting a substring
    against a whole page dumps the entire file into the report.
    """
    return {int(n) for n in re.findall(rf"(\d+){re.escape(unit)}", text)}


class TestStatedNumbersMatchTheEnforcedOnes(unittest.TestCase):
    def test_refund_window(self):
        from refund_manager import REFUND_WINDOW_HOURS
        stated = stated_numbers(frontend_text("pages/me/OrderDetail.tsx"), "時間以内")
        self.assertEqual(
            stated, {REFUND_WINDOW_HOURS},
            f"the order page states {sorted(stated)}h but refund_manager enforces "
            f"{REFUND_WINDOW_HOURS}h",
        )

    def test_referral_bonus(self):
        from referral_manager import REFERRAL_BONUS_CREDITS
        stated = stated_numbers(
            frontend_text("pages/me/Referrals.tsx", "pages/Register.tsx"), "クレジット"
        )
        self.assertEqual(
            stated, {REFERRAL_BONUS_CREDITS},
            f"pages advertise {sorted(stated)} credits but referral_manager awards "
            f"{REFERRAL_BONUS_CREDITS}",
        )

    def test_minimum_bundle_size(self):
        import bundle_manager
        stated = stated_numbers(frontend_text("pages/me/Bundles.tsx"), "件以上")
        self.assertEqual(
            stated, {bundle_manager._MIN_LISTINGS},
            f"the bundle page states a minimum of {sorted(stated)} but "
            f"bundle_manager enforces {bundle_manager._MIN_LISTINGS}",
        )

    def test_password_rule_is_stated_wherever_a_password_is_set(self):
        # The server requires length AND a digit AND a letter
        # (AuthManager._validate_password_strength). Stating only the length
        # gets a user rejected for following the rule they were shown -- which
        # is what the change-password form used to do.
        pages = ("pages/Register.tsx", "pages/ResetPassword.tsx", "pages/me/Security.tsx")
        for page in pages:
            with self.subTest(page=page):
                text = frontend_text(page)
                self.assertIn("8文字以上", text, f"{page} does not state the length rule")
                self.assertIn(
                    "数字と文字", text,
                    f"{page} states only the length while the server also requires "
                    "a digit and a letter",
                )

    def test_the_enforced_password_rule_is_the_one_stated(self):
        # Guard the other direction: if the server's rule changes, the pages
        # above are stating something that is no longer true.
        from auth_manager import AuthManager
        AuthManager._validate_password_strength("abcd1234")  # 8, digit, letter
        for bad, why in (
            ("abc1", "shorter than 8"),
            ("abcdefgh", "no digit"),
            ("12345678", "no letter"),
        ):
            with self.subTest(password=why):
                with self.assertRaises(ValueError):
                    AuthManager._validate_password_strength(bad)


if __name__ == "__main__":
    unittest.main()
