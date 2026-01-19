import json

abs_ip_addresses = [
    "10.10.10.100",
    "10.10.10.101",
    "10.10.10.102",
    "10.10.10.103",
    "10.10.10.104",
    "10.10.10.60",
    "10.10.10.61",
    "10.10.10.62",
    "10.10.10.63",
    "10.10.10.64",
    "10.10.10.65",
    "10.10.10.80",
    "10.10.10.81",
    "10.10.10.82",
    "10.10.10.83",
    "10.10.10.84",
    "10.10.10.85",
    "10.10.10.20",
    "10.10.10.21",
    "10.10.10.22",
    "10.10.10.23",
    "10.10.10.24",
    "10.10.10.25",
    "10.10.10.26",
    "10.10.10.40",
    "10.10.10.41",
    "10.10.10.42",
    "10.10.10.43",
    "10.10.10.44",
    "10.10.10.45",
    "10.10.10.46",
]

joint_names = [
    "waistRoll",
    "waistPitch",
    "waistYaw",
    "neckYaw",
    "neckPitch",
    "hipPitch_Right",
    "hipRoll_Right",
    "hipYaw_Right",
    "kneePitch_Right",
    "anklePitch_Right",
    "ankleRoll_Right",
    "hipPitch_Left",
    "hipRoll_Left",
    "hipYaw_Left",
    "kneePitch_Left",
    "anklePitch_Left",
    "ankleRoll_Left",
    "shoulderPitch_Left",
    "shoulderRoll_Left",
    "shoulderYaw_Left",
    "elbow_Left",
    "wristYaw_Left",
    "wristPitch_Left",
    "wristRoll_Left",
    "shoulderPitch_Right",
    "shoulderRoll_Right",
    "shoulderYaw_Right",
    "elbow_Right",
    "wristYaw_Right",
    "wristPitch_Right",
    "wristRoll_Right",
]
read_abs_num = 0


def validate_abs():
    global read_abs_num
    # Read abs.json
    # Check if abs is empty
    with open("../model_convert/source/abs.json", "r", encoding="utf-8") as abs_angle_file:
        abs_angle_data = json.load(abs_angle_file)
    # Check if the number of abs is correct
    for ip in abs_ip_addresses:
        ip_exists = (
            ip in abs_angle_data
            and "motor_rotor_abs_pos" in abs_angle_data[ip]
            and "radian" in abs_angle_data[ip]
        )
        if ip_exists:
            read_abs_num += 1


def main():
    validate_abs()

    # 定义 adam_type 到 abs_num 的映射关系
    adam_type_to_abs_num = {
        "adam_pro": 31,
        "adam_sp": 29,
        "adam_lite": 23,
        "adam_u": 19,
    }

    # 打开并读取 JSON 文件
    with open("../../../configs/robot/robot_profile.json", mode="r", encoding="utf-8") as pnc_config_file:
        config_data = json.load(pnc_config_file)

    # 提取 "adam_type" 的值
    adam_type = config_data.get("adam_type", "")  # 默认空字符串

    # 根据 adam_type 获取对应的 abs_num
    expected_abs_num = adam_type_to_abs_num.get(adam_type)

    if expected_abs_num is None:
        print(f"错误: 未知的 adam_type '{adam_type}'")
        print(f"支持的型号: {list(adam_type_to_abs_num.keys())}")
        return

    # 与读取的 abs_num 进行比较
    if expected_abs_num != read_abs_num:
        print(f"adam_type:\t{adam_type}")
        print(f"expected_abs_num:\t{expected_abs_num}")
        print(f"read_abs_num:\t{read_abs_num}")
        print("False - ABS数量不匹配")
    else:
        print(f"adam_type:\t{adam_type}")
        print(f"ABS数量验证通过: {expected_abs_num}")
        print("True")


if __name__ == "__main__":
    main()
