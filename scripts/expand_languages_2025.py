import asyncio
import os
import sys

sys.path.append('main')

from i18n_manager import get_i18n_manager


async def expand_languages():
    """言語ファイルを拡張"""
    print("Starting language expansion...")

    manager = await get_i18n_manager()

    # 追加する言語リスト（現在の19言語以外）
    new_languages = [
        'cs', 'da', 'el', 'fi', 'he', 'hu', 'ro', 'bg', 'hr', 'sl',
        'et', 'lv', 'lt', 'uk', 'fa', 'am', 'sw', 'ha', 'yo', 'ig',
        'zu', 'xh', 'af', 'qu', 'ay', 'gn', 'mi', 'sm', 'to', 'haw',
        'sq', 'hy', 'ka', 'az', 'kk', 'uz', 'ky', 'tg', 'tk', 'mn',
        'bo', 'my', 'lo', 'km', 'jv', 'su', 'ceb', 'ny', 'rw', 'mg',
        'sn', 'sd', 'ps', 'ku', 'ti', 'so', 'om', 'aa', 'ss', 'nr',
        've', 'ts', 'fj', 'bi', 'tn', 'st', 'xh', 'zu', 'nso', 'sot',
        'tsn', 'ven', 'xho', 'zul', 'ssw', 'nde', 'nbl', 'tso', 'sot', 'tsn'
    ]

    print(f"Expanding translations for {len(new_languages)} new languages...")

    try:
        await manager.expand_translations(new_languages)
        print("Language expansion completed successfully!")

        # 作成されたファイルを確認
        locales_dir = 'locales'
        if os.path.exists(locales_dir):  # noqa: ASYNC240
            files = [f for f in os.listdir(locales_dir) if f.endswith('.json')]
            print(f"Total language files: {len(files)}")
            print(f"Files: {sorted(files)}")

    except Exception as e:
        print(f"Error during expansion: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(expand_languages())
