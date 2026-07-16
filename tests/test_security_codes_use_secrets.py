"""Repo-wide guard: security-sensitive code/token generators must use `secrets`.

Gift-card, license, referral and promo codes are redeemable for money; 2FA
secrets/backup codes and password-reset/JWT tokens gate authentication. All of
them MUST be generated with the `secrets` module (an OS CSPRNG), never the
`random` module (Mersenne Twister), whose internal state is fully recoverable
from a few hundred outputs — letting an attacker predict future codes/tokens
and take over accounts or mint valid vouchers.

This test parses the security-relevant modules and fails if any of them
imports `random` or calls a `random.<fn>()` generator function. `random` is
legitimately used elsewhere (simulation/telemetry/graphics), so the guard is
deliberately scoped to the modules that mint secrets.
"""
import ast
import pathlib
import unittest

# Modules that generate redeemable codes or auth secrets/tokens.
_SECURITY_MODULES = [
    "gift_card_manager.py",
    "license_manager.py",
    "referral_manager.py",
    "two_factor_auth.py",
    "auth_manager.py",
    "avatar_marketplace.py",  # promo codes + credit ledger
]

# random functions that, if used to build a secret, would be predictable.
_RANDOM_FUNCS = {
    "random", "randint", "randrange", "choice", "choices", "sample",
    "shuffle", "uniform", "getrandbits", "betavariate", "gauss",
}


class TestSecurityCodesUseSecrets(unittest.TestCase):

    def test_security_modules_do_not_use_random_module(self):
        root = pathlib.Path("main")
        offenders = []
        for name in _SECURITY_MODULES:
            py = root / name
            if not py.exists():
                continue
            tree = ast.parse(py.read_text(encoding="utf-8", errors="ignore"))
            for node in ast.walk(tree):
                # import random  /  from random import ...
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == "random" or alias.name.startswith("random."):
                            offenders.append(f"{name}:{node.lineno}: import {alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    if node.module == "random":
                        offenders.append(f"{name}:{node.lineno}: from random import ...")
                # random.<fn>(...)
                elif isinstance(node, ast.Call):
                    f = node.func
                    if (isinstance(f, ast.Attribute) and f.attr in _RANDOM_FUNCS
                            and isinstance(f.value, ast.Name) and f.value.id == "random"):
                        offenders.append(f"{name}:{node.lineno}: random.{f.attr}()")
        self.assertEqual(
            offenders,
            [],
            "Security-sensitive modules must generate codes/tokens with the "
            "`secrets` module, never `random` (predictable Mersenne Twister). "
            "Offenders:\n  " + "\n  ".join(offenders),
        )


if __name__ == "__main__":
    unittest.main()
