from dataclasses import dataclass, field
from typing import Dict

@dataclass
class AvatarParameters:
    # 基本情報
    height: float  # cm
    weight: float  # kg
    muscle_mass: float  # 0.0~1.0 (筋肉量比率)
    flexibility: float  # 0.0~1.0 (柔軟性)
    bone_lengths: Dict[str, float] = field(default_factory=dict)  # 各部位の長さ
    # 追加パラメータも必要に応じて拡張可能


def estimate_joint_range(joint_name: str, params: AvatarParameters) -> float:
    """
    骨格・筋肉・柔軟性から関節可動域（degree）を推定する簡易モデル
    joint_name: 'shoulder', 'elbow', 'knee' など
    """
    # デフォルト可動域（例: 肩180, 肘150, 膝140）
    base_ranges = {'shoulder': 180, 'elbow': 150, 'knee': 140}
    base = base_ranges.get(joint_name, 120)
    # 筋肉量が多いほど狭く、柔軟性が高いほど広く
    muscle_factor = -params.muscle_mass * 20
    flex_factor = params.flexibility * 20
    # 骨長による微調整（平均170cm基準）
    avg_height = 170
    bone_factor = -abs(params.height - avg_height) * 0.1
    return max(30, base + muscle_factor + flex_factor + bone_factor)
