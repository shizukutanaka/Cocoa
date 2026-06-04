"""Core utilities for preset diff tools."""
from __future__ import annotations

import json
import logging
import webbrowser
import difflib
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_REPORT_DIR = BASE_DIR / "diff_reports"


def configure_logging(log_file: Optional[str] = None, level: int = logging.INFO) -> logging.Logger:
    """Configure and return a scoped logger without altering global logging."""
    logger = logging.getLogger("cocoa.preset_diff")
    logger.setLevel(level)
    logger.propagate = False

    # リハンドラー構成をリセット
    while logger.handlers:
        handler = logger.handlers.pop()
        handler.close()

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    else:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    return logger


def load_preset(path: str) -> Dict:
    """Load a preset JSON file."""
    preset_path = Path(path)
    if not preset_path.exists():
        raise FileNotFoundError(f"プリセットファイルが見つかりません: {path}")

    try:
        with preset_path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError as exc:
        logging.error("[ERROR] JSONデコードエラー %s: %s", path, exc)
        raise
    except PermissionError as exc:
        logging.error("[ERROR] ファイルアクセス権限エラー %s: %s", path, exc)
        raise
    except Exception as exc:  # noqa: BLE001 - surface unknown I/O issues
        logging.error("[ERROR] ファイル読み込みエラー %s: %s", path, exc)
        raise


def _json_lines(payload: Dict, sort_keys: bool) -> List[str]:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=sort_keys).splitlines()


def diff_presets(
    preset1: Dict,
    preset2: Dict,
    name1: str = "preset1",
    name2: str = "preset2",
    *,
    sort_keys: bool = False,
) -> Tuple[bool, List[str]]:
    """Return unified diff lines between two presets."""
    if preset1 == preset2:
        return True, []

    lines1 = _json_lines(preset1, sort_keys)
    lines2 = _json_lines(preset2, sort_keys)
    diff_iter = difflib.unified_diff(lines1, lines2, fromfile=name1, tofile=name2, lineterm="")
    return False, list(diff_iter)


def generate_html_diff(
    preset1: Dict,
    preset2: Dict,
    name1: str,
    name2: str,
    *,
    sort_keys: bool = False,
) -> str:
    """Create an HTML diff table for two presets."""
    differ = difflib.HtmlDiff()
    lines1 = _json_lines(preset1, sort_keys)
    lines2 = _json_lines(preset2, sort_keys)
    html_table = differ.make_table(
        lines1,
        lines2,
        fromdesc=f"Old: {name1}",
        todesc=f"New: {name2}",
        context=True,
        numlines=3,
    )

    return (
        "<!DOCTYPE html>\n"
        "<html>\n"
        "<head>\n"
        "    <title>プリセット差分ビューア</title>\n"
        "    <style>\n"
        "        body { font-family: Arial, sans-serif; margin: 20px; }\n"
        "        h2 { color: #333; }\n"
        "        .diff { width: 100%; border-collapse: collapse; }\n"
        "        .diff_header { background-color: #e0e0e0; }\n"
        "        .diff_next { background-color: #c0c0c0; }\n"
        "        .diff_add { background-color: #aaffaa; }\n"
        "        .diff_chg { background-color: #ffff77; }\n"
        "        .diff_sub { background-color: #ffaaaa; }\n"
        "        td { padding: 3px 10px; }\n"
        "    </style>\n"
        "</head>\n"
        "<body>\n"
        f"    <h2>プリセット差分: {name1} vs {name2}</h2>\n"
        f"    <p>比較日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>\n"
        f"    {html_table}\n"
        "</body>\n"
        "</html>\n"
    )


def save_diff_html(
    html_content: str,
    output_path: Optional[str] = None,
    *,
    report_dir: Optional[Path] = None,
    open_in_browser: bool = True,
) -> str:
    """Persist HTML diff to disk and optionally open in a browser."""
    directory = Path(report_dir or DEFAULT_REPORT_DIR)
    directory.mkdir(parents=True, exist_ok=True)

    if output_path:
        destination = Path(output_path)
        if destination.is_dir():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            destination = destination / f"diff_{timestamp}.html"
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        destination = directory / f"diff_{timestamp}.html"

    with destination.open("w", encoding="utf-8") as handle:
        handle.write(html_content)

    if open_in_browser:
        try:
            webbrowser.open(f"file://{destination.resolve()}")
        except Exception as exc:  # noqa: BLE001
            logging.warning("ブラウザで開けませんでした: %s", exc)

    return str(destination)


def write_diff_output(diff_lines: Iterable[str], output_path: Optional[str] = None) -> None:
    """Write diff lines either to stdout or to a file."""
    diff_text = "\n".join(diff_lines)
    if output_path:
        output = Path(output_path)
        if output.exists() and output.is_dir():
            raise IsADirectoryError(f"出力先がディレクトリです: {output}")
        with output.open("w", encoding="utf-8") as handle:
            handle.write(diff_text)
        print(f"差分をファイルに保存しました: {output_path}")
    else:
        print(diff_text)

__all__ = [
    "configure_logging",
    "diff_presets",
    "generate_html_diff",
    "load_preset",
    "save_diff_html",
    "write_diff_output",
]
