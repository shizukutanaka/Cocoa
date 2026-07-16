import logging

from avatar_parameter_sets import get_preset, list_presets
from avatar_parameters import estimate_joint_range

logger = logging.getLogger(__name__)

_DEFAULT_JOINTS = ['shoulder', 'elbow', 'knee']


def generate_joint_range_report(joint_names=None):
    """Return (header, rows) for printing.  Skips presets that cannot be loaded."""
    if joint_names is None:
        joint_names = _DEFAULT_JOINTS
    header = ["体型"] + joint_names
    rows = []
    for preset_name in list_presets():
        try:
            params = get_preset(preset_name)
        except KeyError:
            logger.warning("Preset not found, skipping: %s", preset_name)
            continue
        row = [preset_name]
        for joint in joint_names:
            deg = estimate_joint_range(joint, params)
            row.append(f"{deg:.1f}")
        rows.append(row)
    return header, rows


def report_as_records(joint_names=None) -> list:
    """Return a list of dicts, one per preset: {preset, shoulder, elbow, knee, ...}."""
    if joint_names is None:
        joint_names = _DEFAULT_JOINTS
    records = []
    for preset_name in list_presets():
        try:
            params = get_preset(preset_name)
        except KeyError:
            logger.warning("Preset not found, skipping: %s", preset_name)
            continue
        rec = {"preset": preset_name}
        for joint in joint_names:
            rec[joint] = estimate_joint_range(joint, params)
        records.append(rec)
    return records


def print_report_table(header, rows):
    if not rows:
        print(" | ".join(header))
        return
    col_widths = [max(len(str(cell)) for cell in col) for col in zip(header, *rows)]
    fmt = " | ".join(f"{{:<{w}}}" for w in col_widths)
    print(fmt.format(*header))
    print("-+-".join("-" * w for w in col_widths))
    for row in rows:
        print(fmt.format(*row))


if __name__ == "__main__":
    header, rows = generate_joint_range_report()
    print_report_table(header, rows)
