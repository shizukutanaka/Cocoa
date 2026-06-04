#!/usr/bin/env python3
"""
言語ファイル統合スクリプト
Consolidate language files from main/ to locales/
"""
import json
import shutil
from pathlib import Path


def consolidate_language_files():
    """main/ から locales/ へ言語ファイルを統合"""
    project_root = Path(__file__).resolve().parent.parent
    main_dir = project_root / 'main'
    locales_dir = project_root / 'locales'

    # 統合する言語コード
    lang_codes = [
        'ar', 'bn', 'de', 'es', 'fr', 'hi',
        'id', 'ko', 'pt', 'ru', 'ur', 'zh'
    ]

    consolidated = 0
    skipped = 0

    for lang in lang_codes:
        main_file = main_dir / f'{lang}.json'
        locales_file = locales_dir / f'{lang}.json'

        if main_file.exists():
            if not locales_file.exists():
                # locales/ にファイルが存在しない場合、コピー
                shutil.move(str(main_file), str(locales_file))
                print(f"✓ Moved {lang}.json to locales/")
                consolidated += 1
            else:
                # locales/ に既に存在する場合、統合
                try:
                    # main/ の内容を読み込み
                    with open(main_file, 'r', encoding='utf-8') as f:
                        main_data = json.load(f)

                    # locales/ の内容を読み込み
                    with open(locales_file, 'r', encoding='utf-8') as f:
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


if __name__ == "__main__":
    consolidate_language_files()
