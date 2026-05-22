import json

from config_utils import get_active_joints, load_json_file, lookup_abs_json_key

read_abs_num = 0


def validate_abs():
    global read_abs_num
    abs_ips, _, _ = get_active_joints()
    with open("../model_convert/source/abs.json", "r", encoding="utf-8") as abs_angle_file:
        abs_angle_data = json.load(abs_angle_file)
    for ip in abs_ips:
        k = lookup_abs_json_key(abs_angle_data, ip)
        if k is None:
            print(
                f"[WARN] abs.json 无关节 {ip} 对应项（需 joint_ip+10 的 key 或旧版 joint_ip key），"
                "read_abs 未写入或路径错误"
            )
            continue
        entry = abs_angle_data[k]
        if (
            "motor_rotor_abs_pos" in entry
            and "radian" in entry
        ):
            read_abs_num += 1


def main():
    global read_abs_num
    read_abs_num = 0
    validate_abs()

    config_data = load_json_file(
        "../../../configs/robot/robot_profile.json", "robot_profile.json"
    )

    adam_type = config_data.get("adam_type", "")
    active_ips, _, _ = get_active_joints()
    expected_abs_num = len(active_ips)

    if expected_abs_num == 0:
        print(f"错误: {adam_type} 下无活跃执行器（是否全部在 robot_profile 中禁用？）")
        print("False")
        return

    if read_abs_num != expected_abs_num:
        print(f"adam_type:\t{adam_type}")
        print(f"expected_abs_num (活跃关节数):\t{expected_abs_num}")
        print(f"read_abs_num:\t{read_abs_num}")
        print("False - ABS数量不匹配（keys 需为 joint_ip+10 或旧版 joint_ip）")
    else:
        print(f"adam_type:\t{adam_type}")
        print(f"ABS数量验证通过: {expected_abs_num}")
        print("True")


if __name__ == "__main__":
    main()
