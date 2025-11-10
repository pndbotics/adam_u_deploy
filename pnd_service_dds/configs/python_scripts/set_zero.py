import argparse
import json
import os

abs_ip_list = [
    "10.10.10.100",
    "10.10.10.101",
    "10.10.10.102",
    "10.10.10.103",
    "10.10.10.104",
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
joint_config_path = ""


def verify_legality():
    is_legal = True
    # Read abs.json
    # Check if abs is empty
    try:
        with open("source/abs.json", "r", encoding="utf-8") as abs_angle_file:
            abs_angle_dict = json.load(abs_angle_file)
        # Check if the number of abs is correct
        for ip in abs_ip_list:
            exist_flag = ip in abs_angle_dict
            if not exist_flag:
                is_legal = False
                print("abs IP: ", ip, " does not exist!")
                return is_legal
    except json.decoder.JSONDecodeError:
        print("abs.json is empty!")
        is_legal = False
        return is_legal
    return is_legal


def set_motor_zero_pos():
    is_ready = True
    joint_config_path_out = "/root/.adam/"
    if not os.path.exists(joint_config_path_out):
        os.makedirs(joint_config_path_out)
    joint_config_path_out += "joint_abs_config.json"
    # Check the legality of abs
    if not verify_legality():
        print("Setting motor zero position failed!")
        is_ready = False
        # return is_ready
    # Load abs
    with open("source/abs.json", "r", encoding="utf-8") as abs_angle_file:
        abs_angle_dict = json.load(abs_angle_file)
    # Load joint
    try:
        with open(joint_config_path, "r", encoding="utf-8") as joint_config_file:
            joint_config_dict = json.load(joint_config_file)
    except json.decoder.JSONDecodeError:
        print("joint_abs_config_template.json is empty!")
        is_ready = False
        return is_ready
    # Set zero position
    try:
        for ip_num in range(len(abs_ip_list)):
            if (
                "radian" in abs_angle_dict[abs_ip_list[ip_num]].keys()
                and "motor_rotor_abs_pos" in abs_angle_dict[abs_ip_list[ip_num]].keys()
            ):
                joint_config_dict[joint_names[ip_num]]["absolute_pos_zero"] = (
                    abs_angle_dict[abs_ip_list[ip_num]]["radian"]
                )
                joint_config_dict[joint_names[ip_num]]["motor_rotor_abs_pos"] = (
                    abs_angle_dict[abs_ip_list[ip_num]]["motor_rotor_abs_pos"]
                )
            else:
                print(abs_ip_list[ip_num], "no abs")
    except Exception as e:
        print(e)
        print("Setting motor zero failed!")
        is_ready = False
        return is_ready
    # Write into motorlist
    try:
        with open(joint_config_path_out, "w", encoding="utf-8") as joint_config_w:
            json.dump(joint_config_dict, joint_config_w, indent=4, ensure_ascii=False)
    except:
        print("Writing into joint_config_path_out.json failed!")
        is_ready = False
        return is_ready
    print("Successfully set zero position!")
    return is_ready


def main():
    parser = argparse.ArgumentParser(description="example: python set_zero.py -v pvt")
    parser.add_argument("-v", "--version", type=str)
    args = parser.parse_args()
    global joint_config_path
    if args.version is None:
        print("no version")
        return
    if args.version == "evt" or args.version == "dvt" or args.version == "pvt":
        print(f"{args.version} version")
        joint_config_path = f"joint_abs_config_{args.version}_template.json"
    else:
        print("wrong version")
        return
    is_legal = verify_legality()
    print(is_legal)
    set_motor_zero_pos()


if __name__ == "__main__":
    main()
