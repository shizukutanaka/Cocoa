import argparse
import json
import logging
import os
import sys
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from .i18n import I18n
except ImportError:
    from i18n import I18n

def load_preset(path: str) -> dict:
    """プリセットファイルを読み込む"""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logging.error(f"[ERROR] JSONデコードエラー {path}: {e}")
        raise
    except Exception as e:
        logging.error(f"[ERROR] ファイル読み込みエラー {path}: {e}")
        raise

def diff_presets(preset1: dict, preset2: dict, name1: str = "preset1", name2: str = "preset2") -> Tuple[bool, List[str]]:
    """2つのプリセットの差分をテキスト形式で取得"""
    if preset1 == preset2:
        return True, []
    text1 = json.dumps(preset1, ensure_ascii=False, indent=2, sort_keys=True).splitlines()
    text2 = json.dumps(preset2, ensure_ascii=False, indent=2, sort_keys=True).splitlines()
    diff = difflib.unified_diff(text1, text2, fromfile=name1, tofile=name2, lineterm="")
    return False, list(diff)

def generate_html_diff(preset1: dict, preset2: dict, name1: str, name2: str) -> str:
    """HTML形式で差分を視覚的に表示"""
    differ = difflib.HtmlDiff()
    text1 = json.dumps(preset1, ensure_ascii=False, indent=2, sort_keys=True).splitlines()
    text2 = json.dumps(preset2, ensure_ascii=False, indent=2, sort_keys=True).splitlines()
    
    # 変更箇所をハイライト
    html = differ.make_table(
        text1, text2,
        fromdesc=f"Old: {name1}",
        todesc=f"New: {name2}",
        context=True,
        numlines=3
    )
    
    # HTMLテンプレートに埋め込み
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>プリセット差分ビューア</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            h2 {{ color: #333; }}
            .diff {{ width: 100%; border-collapse: collapse; }}
            .diff_header {{ background-color: #e0e0e0; }}
            .diff_next {{ background-color: #c0c0c0; }}
            .diff_add {{ background-color: #aaffaa; }}
            .diff_chg {{ background-color: #ffff77; }}
            .diff_sub {{ background-color: #ffaaaa; }}
            td {{ padding: 3px 10px; }}
        </style>
    </head>
    <body>
        <h2>プリセット差分: {name1} vs {name2}</h2>
        <p>比較日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        {html}
    </body>
    </html>
    """

def save_diff_html(html_content: str, output_path: Optional[str] = None) -> str:
    """差分HTMLをファイルに保存し、ブラウザで開く"""
    if not output_path:
        output_dir = Path("diff_reports")
        output_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = str(output_dir / f"diff_{timestamp}.html")
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    try:
        webbrowser.open(f"file://{os.path.abspath(output_path)}")
    except Exception as e:
        logging.warning(f"ブラウザで開けませんでした: {e}")
    
    return output_path

def main():
    parser = argparse.ArgumentParser(description="Satin Preset Diff Tool")
    parser.add_argument("preset1", help="1つ目のプリセットJSON")
    parser.add_argument("preset2", help="2つ目のプリセットJSON")
    parser.add_argument("--output", "-o", help="差分出力ファイル（省略時は標準出力）")
    parser.add_argument("--html", help="HTML形式で出力（ブラウザで表示）", action="store_true")
    parser.add_argument("--log", help="ログファイル", default=None)
    args = parser.parse_args()

    # ログ設定
    log_level = logging.INFO
    if args.log:
        logging.basicConfig(
            filename=args.log,
            level=log_level,
            format='%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    else:
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    logger = logging.getLogger(__name__)
    logger.info(f"プリセット比較を開始: {args.preset1} vs {args.preset2}")
    
    try:
        # プリセット読み込み
        t0 = time.time()
        preset1 = load_preset(args.preset1)
        preset2 = load_preset(args.preset2)
        t1 = time.time()
        
        # 差分比較
        is_same, diff = diff_presets(preset1, preset2, 
                                   os.path.basename(args.preset1), 
                                   os.path.basename(args.preset2))
        t2 = time.time()
        
        logger.info(f"ロード時間: {t1-t0:.3f}秒, 比較時間: {t2-t1:.3f}秒, 合計: {t2-t0:.3f}秒")
        
        if is_same:
            print("プリセットに差分はありません。")
            return 0
            
        # HTML出力モード
        if args.html:
            html_content = generate_html_diff(
                preset1, preset2,
                os.path.basename(args.preset1),
                os.path.basename(args.preset2)
            )
            output_path = save_diff_html(html_content, args.output)
            print(f"HTMLレポートを生成しました: {output_path}")
        # テキスト出力モード
        else:
            diff_text = "\n".join(diff)
            if args.output:
                try:
                    with open(args.output, "w", encoding="utf-8") as f:
                        f.write(diff_text)
                    print(f"差分をファイルに保存しました: {args.output}")
                except IOError as e:
                    logger.error(f"ファイルの書き込みに失敗しました: {e}")
                    return 1
            else:
                print(diff_text)
                
        return 0
        
    except Exception as e:
        logger.error(f"エラーが発生しました: {str(e)}", exc_info=True)
        return 1
                    f.write("\n".join(diff))
                print(f"差分を {args.output} に保存しました")
            except Exception as e:
                print(f"[ERROR] 差分ファイル保存失敗: {e}")
        else:
            print("\n".join(diff))
    else:
        print("差分はありません")

if __name__ == "__main__":
    sys.exit(main())
