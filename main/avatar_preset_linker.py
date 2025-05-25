import os
import json
import sys

# アバターメタデータとプリセット（パラメータセット）を紐付け管理する簡易ツール
LINKS_FILE = "avatar_preset_links.json"

class AvatarPresetLinker:
    def __init__(self, links_file=LINKS_FILE):
        self.links_file = links_file
        self.links = self.load_links()

    def load_links(self):
        if os.path.exists(self.links_file):
            try:
                with open(self.links_file, encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def save_links(self):
        with open(self.links_file, 'w', encoding='utf-8') as f:
            json.dump(self.links, f, ensure_ascii=False, indent=2)

    def link(self, avatar_path, preset_path):
        self.links[os.path.abspath(avatar_path)] = os.path.abspath(preset_path)
        self.save_links()

    def get_preset(self, avatar_path):
        return self.links.get(os.path.abspath(avatar_path))

    def list_links(self):
        return self.links.items()

if __name__ == "__main__":
    linker = AvatarPresetLinker()
    if len(sys.argv) == 3 and sys.argv[1] == "list":
        for avatar, preset in linker.list_links():
            print(f"{avatar} -> {preset}")
    elif len(sys.argv) == 4 and sys.argv[1] == "link":
        linker.link(sys.argv[2], sys.argv[3])
        print(f"Linked: {sys.argv[2]} <-> {sys.argv[3]}")
    elif len(sys.argv) == 3 and sys.argv[1] == "get":
        preset = linker.get_preset(sys.argv[2])
        print(preset if preset else "Not linked")
    else:
        print("使い方:")
        print("  python avatar_preset_linker.py link <avatar_file> <preset_file>")
        print("  python avatar_preset_linker.py get <avatar_file>")
        print("  python avatar_preset_linker.py list")
