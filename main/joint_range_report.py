from avatar_parameters import AvatarParameters, estimate_joint_range
from avatar_parameter_sets import list_presets, get_preset

# 複数体型の各関節可動域をレポートとしてテーブル表示する

def generate_joint_range_report(joint_names=None):
    if joint_names is None:
        joint_names = ['shoulder', 'elbow', 'knee']
    presets = list_presets()
    # ヘッダー
    header = ["体型"] + joint_names
    rows = []
    for preset_name in presets:
        params = get_preset(preset_name)
        row = [preset_name]
        for joint in joint_names:
            deg = estimate_joint_range(joint, params)
            row.append(f"{deg:.1f}")
        rows.append(row)
    return header, rows

def print_report_table(header, rows):
    col_widths = [max(len(str(cell)) for cell in col) for col in zip(header, *rows)]
    fmt = " | ".join(f"{{:<{w}}}" for w in col_widths)
    print(fmt.format(*header))
    print("-+-".join("-" * w for w in col_widths))
    for row in rows:
        print(fmt.format(*row))

if __name__ == "__main__":
    header, rows = generate_joint_range_report()
    print_report_table(header, rows)
