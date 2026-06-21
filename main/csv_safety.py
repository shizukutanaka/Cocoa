"""CSV formula-injection (CEMI) hardening.

When a spreadsheet app (Excel, LibreOffice, Google Sheets) opens a CSV, any
cell whose text begins with a formula trigger — ``= + - @`` (and their
full-width variants ``＝ ＋ － ＠``), or a leading TAB/CR — may be evaluated as
a formula rather than shown as text. If that text came from user-controlled
data (a username, a free-text "details" field, …), an attacker can smuggle a
``=cmd|'/C calc'!A0``-style payload into a CSV an admin later opens. This is
CSV Excel Macro Injection (CEMI / CSV injection).

``sanitize_csv_cell`` neutralizes the trigger by prefixing a single quote so
the value is rendered as literal text. Genuine numbers (``-5``, ``+3.14``)
are left untouched so numeric exports stay analyzable.
"""
from typing import Any

# ASCII triggers plus the full-width symbols Excel also honors.
_CSV_TRIGGERS = (
    "=", "+", "-", "@", "\t", "\r",
    "＝",  # ＝ fullwidth equals
    "＋",  # ＋ fullwidth plus
    "－",  # － fullwidth hyphen-minus
    "＠",  # ＠ fullwidth commercial at
)


def sanitize_csv_cell(value: Any) -> str:
    """Return ``value`` as a CSV-safe string, escaping formula triggers.

    A leading trigger character causes a single-quote prefix UNLESS the whole
    cell is a valid number (so "-5"/"+3.14" survive as numbers, while
    "-2+cmd" / "=SUM(...)" / "＝cmd" get quoted as text).
    """
    s = "" if value is None else str(value)
    if not s:
        return s
    if s[0] in _CSV_TRIGGERS:
        try:
            float(s)  # genuine number → safe to leave as-is
        except ValueError:
            return "'" + s
    return s
