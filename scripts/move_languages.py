#!/usr/bin/env python3
"""
残りの言語ファイルをlocales/へ移動
Move remaining language files to locales/
"""
import os
from pathlib import Path
from typing import Dict, List, Optional

DEFAULT_REMAINING_LANGS = [
    'de', 'es', 'fr', 'hi', 'id',
    'ko', 'pt', 'ru', 'ur', 'zh',
]


def move_remaining_languages(
    project_root: Optional[Path] = None,
    langs: Optional[List[str]] = None,
) -> Dict[str, int]:
    """残りの言語ファイルを main/ から locales/ へ移動する。

    Args:
        project_root: プロジェクトルート。未指定時はこのスクリプトの2階層上。
        langs: 移動対象の言語コード。未指定時は DEFAULT_REMAINING_LANGS。

    Returns:
        {"moved": 移動件数}
    """
    if project_root is None:
        project_root = Path(__file__).resolve().parent.parent
    project_root = Path(project_root)
    main_dir = project_root / 'main'
    locales_dir = project_root / 'locales'
    locales_dir.mkdir(parents=True, exist_ok=True)

    if langs is None:
        langs = DEFAULT_REMAINING_LANGS

    moved = 0
    for lang_code in langs:
        filename = f'{lang_code}.json'
        src_path = main_dir / filename
        dst_path = locales_dir / filename

        if src_path.exists():
            try:
                # ファイルを読み込み
                with open(src_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # locales/ に書き込み
                with open(dst_path, 'w', encoding='utf-8') as f:
                    f.write(content)

                # 元ファイルを削除
                os.remove(src_path)
                print(f"✓ Moved {filename}")
                moved += 1

            except Exception as e:
                print(f"✗ Error moving {filename}: {e}")
        else:
            print(f"- {filename} not found")

    print(f"\n移動完了: {moved} files moved")

    return {"moved": moved}


if __name__ == "__main__":
    move_remaining_languages()
