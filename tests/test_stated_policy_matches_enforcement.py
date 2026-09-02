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


class TestAuditRecordPromisesAreKept(unittest.TestCase):
    """「必須・監査記録に残ります」 must be true of the server, not of React (#102).

    The moderation console labels every decision field required, and says the
    text goes into the audit record. Measured against a running server before
    this test existed:

        resolve a report with note=""     -> HTTP 200, resolution_note=""
        resolve a report with 1500 chars  -> HTTP 200, 1000 stored, 500 gone

    Both promises were enforced by React alone. This pins the second one --
    the console must not let a moderator type more than the server keeps --
    and tests/test_api_server.py covers the first by calling the endpoints.

    The caps are checked as a SET per file rather than one at a time, so a
    sixth decision field added later without a cap fails here instead of
    silently joining the class (the #101 lesson: N fixes do not close a class,
    only the mechanism that catches N+1 does).
    """

    CONSOLE = "pages/admin/Moderation.tsx"

    def server_limits(self):
        import auth_manager, avatar_marketplace, moderation_queue, refund_manager
        return {
            "QUEUE_NOTES_MAX": moderation_queue.MAX_QUEUE_NOTES_LEN,
            "REPORT_NOTE_MAX": avatar_marketplace.MAX_RESOLUTION_NOTE_LEN,
            "REFUND_NOTE_MAX": refund_manager.MAX_ADMIN_NOTES_LEN,
            "APPLICATION_NOTE_MAX": auth_manager.MAX_REVIEW_NOTE_LEN,
        }

    def test_declared_caps_equal_the_server_constants(self):
        text = frontend_text(self.CONSOLE)
        for name, server_value in self.server_limits().items():
            with self.subTest(constant=name):
                declared = re.findall(rf"const {name} = (\d+);", text)
                self.assertEqual(
                    len(declared), 1,
                    f"{self.CONSOLE} should declare {name} exactly once, found "
                    f"{len(declared)}",
                )
                self.assertEqual(
                    int(declared[0]), server_value,
                    f"the console caps {name} at {declared[0]} but the server keeps "
                    f"{server_value}; text between the two is accepted by the "
                    f"browser and refused (or worse, cut) by the server",
                )

    def test_every_decision_field_declares_a_cap(self):
        """No uncapped text input in the console.

        Every <input>/<textarea> here collects a moderator's reason for a
        decision. Scanning for the ones WITHOUT maxLength is what found #102:
        five of them, all labelled as recorded, none capped. The one input
        that is not a decision field -- the user search box -- is named
        explicitly so adding another exemption is a conscious act.
        """
        text = frontend_text(self.CONSOLE)
        exempt = (
            # maxLength does nothing on a numeric input; these are bounded by
            # min/step and by the server's own range checks.
            'type="number"',
            # Not a decision field: a filter over the user list, typed and
            # discarded, never stored and never shown back as a record.
            "ユーザー名・メール・ID・ロールで検索",
        )
        uncapped = [
            block for block in jsx_elements(text, ("input", "textarea"))
            if "maxLength" not in block and not any(e in block for e in exempt)
        ]
        self.assertEqual(
            [], uncapped,
            "moderation console input without maxLength: the server refuses "
            "over-length notes, so an uncapped field loses the whole submission "
            f"to an error.\n{uncapped}",
        )


def jsx_elements(text, tags):
    """Yield the opening tag of each <tag ...> in `text`.

    Written by hand rather than with a regex because a JSX attribute contains
    arrow functions -- `onChange={(e) => ...}` -- and any `[^>]*` pattern stops
    at the `>` inside the arrow, reporting a capped element as uncapped. That
    exact mistake produced a wrong list of 47 fields while auditing #102
    before being caught.
    """
    for tag in tags:
        start = 0
        while True:
            i = text.find("<" + tag, start)
            if i < 0:
                break
            j, depth, quote = i + len(tag) + 1, 0, None
            while j < len(text):
                c = text[j]
                if quote:
                    if c == quote:
                        quote = None
                    elif c == "\\":
                        j += 1
                elif c in "\"'`":
                    quote = c
                elif c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                elif c == ">" and depth == 0:
                    break
                j += 1
            yield text[i:j + 1]
            start = j + 1


if __name__ == "__main__":
    unittest.main()
