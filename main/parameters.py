# avatar_parameters.py
# 10万パラメータ自動生成（カテゴリ×サブカテゴリ×インデックス）

CATEGORIES = [
    "face", "body", "hair", "eye", "eyebrow", "nose", "mouth", "ear", "skin", "clothes",
    "accessory", "expression", "physics", "material", "shader", "texture", "bone", "animation", "voice", "system"
]
SUBCATEGORIES = [
    "shape", "size", "color", "position", "rotation"
]

AVATAR_PARAMETERS = []

for cat in CATEGORIES:
    for sub in SUBCATEGORIES:
        for idx in range(1000):  # 20×5×1000=100,000
            key = f"{cat}_{sub}_{idx+1:04d}"
            label = f"{cat.capitalize()} {sub.capitalize()} #{idx+1}"
            if sub == "color":
                param_type = "color"
                default = "#cccccc"
                AVATAR_PARAMETERS.append({
                    "key": key, "label": label, "type": param_type, "default": default
                })
            elif sub in ("shape", "size", "position", "rotation"):
                param_type = "slider"
                AVATAR_PARAMETERS.append({
                    "key": key, "label": label, "type": param_type, "min": 0, "max": 100, "default": 50
                })
