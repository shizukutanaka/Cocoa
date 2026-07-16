from avatar_parameters import AvatarParameters

PRESET_SETS = {
    "標準男性": AvatarParameters(
        height=172.0, weight=68.0, muscle_mass=0.5, flexibility=0.5,
        bone_lengths={"arm": 62, "leg": 92}
    ),
    "標準女性": AvatarParameters(
        height=158.0, weight=54.0, muscle_mass=0.35, flexibility=0.6,
        bone_lengths={"arm": 58, "leg": 88}
    ),
    "筋肉質": AvatarParameters(
        height=175.0, weight=80.0, muscle_mass=0.8, flexibility=0.4,
        bone_lengths={"arm": 64, "leg": 94}
    ),
    "柔軟体型": AvatarParameters(
        height=165.0, weight=58.0, muscle_mass=0.3, flexibility=0.9,
        bone_lengths={"arm": 60, "leg": 90}
    ),
}


def list_presets():
    return list(PRESET_SETS.keys())


def get_preset(name: str) -> AvatarParameters:
    """Return the preset for *name*.

    Raises KeyError if *name* is not registered (never returns None).
    """
    if name not in PRESET_SETS:
        raise KeyError(name)
    return PRESET_SETS[name]
