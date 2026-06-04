#!/usr/bin/env python3
"""
残りの言語ファイルをlocales/へ移動
Move remaining language files to locales/
"""
import os
from pathlib import Path


def move_remaining_languages():
    """残りの言語ファイルをmain/からlocales/へ移動"""
    project_root = Path(__file__).resolve().parent.parent
    main_dir = project_root / 'main'
    locales_dir = project_root / 'locales'

    # 移動する言語ファイル
    remaining_langs = [
        ('de', 'de.json'),
        ('es', 'es.json'),
        ('fr', 'fr.json'),
        ('hi', 'hi.json'),
        ('id', 'id.json'),
        ('ko', 'ko.json'),
        ('pt', 'pt.json'),
        ('ru', 'ru.json'),
        ('ur', 'ur.json'),
        ('zh', 'zh.json')
    ]

    moved = 0
    for lang_code, filename in remaining_langs:
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


if __name__ == "__main__":
    move_remaining_languages()
