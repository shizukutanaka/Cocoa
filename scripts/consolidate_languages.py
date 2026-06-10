#!/usr/bin/env python3
"""
言語ファイル統合スクリプト
Consolidate language files from main/ to locales/
"""
import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional

DEFAULT_LANG_CODES = [
    'ar', 'bn', 'de', 'es', 'fr', 'hi',
    'id', 'ko', 'pt', 'ru', 'ur', 'zh',
]


def consolidate_language_files(
    project_root: Optional[Path] = None,
    lang_codes: Optional[List[str]] = None,
) -> Dict[str, int]:
    """main/ から locales/ へ言語ファイルを統合する。

    Args:
        project_root: プロジェクトルート。未指定時はこのスクリプトの2階層上。
        lang_codes: 統合対象の言語コード。未指定時は DEFAULT_LANG_CODES。

    Returns:
        {"consolidated": 統合件数, "skipped": スキップ件数}
    """
    if project_root is None:
        project_root = Path(__file__).resolve().parent.parent
    project_root = Path(project_root)
    main_dir = project_root / 'main'
    locales_dir = project_root / 'locales'
    locales_dir.mkdir(parents=True, exist_ok=True)

    if lang_codes is None:
        lang_codes = DEFAULT_LANG_CODES

    consolidated = 0
    skipped = 0

    for lang in lang_codes:
        main_file = main_dir / f'{lang}.json'
        locales_file = locales_dir / f'{lang}.json'

        if main_file.exists():
            if not locales_file.exists():
                # locales/ にファイルが存在しない場合、移動
                shutil.move(str(main_file), str(locales_file))
                print(f"✓ Moved {lang}.json to locales/")
                consolidated += 1
            else:
                # locales/ に既に存在する場合、統合
                try:
                    # main/ の内容を読み込み
                    with open(main_file, encoding='utf-8') as f:
                        main_data = json.load(f)

                    # locales/ の内容を読み込み
                    with open(locales_file, encoding='utf-8') as f:
                        locales_data = json.load(f)

                    # マージ（locales/ のデータを優先）
                    merged_data = {**main_data, **locales_data}

                    # マージしたデータをlocales/ に書き込み
                    with open(locales_file, 'w', encoding='utf-8') as f:
                        json.dump(merged_data, f, ensure_ascii=False, indent=2)

                    # main/ のファイルを削除
                    main_file.unlink()
                    print(f"✓ Merged {lang}.json into locales/")
                    consolidated += 1

                except Exception as e:
                    print(f"✗ Error merging {lang}.json: {e}")
                    skipped += 1
        else:
            print(f"- {lang}.json not found in main/")
            skipped += 1

    print("\n統合完了 / Consolidation complete:")
    print(f"  統合ファイル数: {consolidated}")
    print(f"  スキップファイル数: {skipped}")

    return {"consolidated": consolidated, "skipped": skipped}


if __name__ == "__main__":
    consolidate_language_files()
