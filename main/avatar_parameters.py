from dataclasses import dataclass, field
from typing import Dict


@dataclass
class AvatarParameters:
    height: float       # cm
    weight: float       # kg
    muscle_mass: float  # 0.0–1.0 (ratio)
    flexibility: float  # 0.0–1.0
    bone_lengths: Dict[str, float] = field(default_factory=dict)

    def __post_init__(self):
        if self.height <= 0:
            raise ValueError(f"height must be > 0, got {self.height}")
        if self.weight <= 0:
            raise ValueError(f"weight must be > 0, got {self.weight}")
        if not (0.0 <= self.muscle_mass <= 1.0):
            raise ValueError(f"muscle_mass must be in [0, 1], got {self.muscle_mass}")
        if not (0.0 <= self.flexibility <= 1.0):
            raise ValueError(f"flexibility must be in [0, 1], got {self.flexibility}")


def estimate_joint_range(joint_name: str, params: AvatarParameters) -> float:
    """Estimate joint range of motion (degrees) from skeletal/muscle/flexibility model."""
    base_ranges = {'shoulder': 180, 'elbow': 150, 'knee': 140}
    base = base_ranges.get(joint_name, 120)
    muscle_factor = -params.muscle_mass * 20
    flex_factor = params.flexibility * 20
    bone_factor = -abs(params.height - 170) * 0.1
    return max(30, min(360, base + muscle_factor + flex_factor + bone_factor))
