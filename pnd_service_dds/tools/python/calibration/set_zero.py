import argparse
import json
import os

from config_utils import get_active_joints, lookup_abs_json_key

joint_config_path = ""


def verify_legality():
    try:
        abs_ip_list, _, _ = get_active_joints()
        if not abs_ip_list:
            print("无活跃关节（检查 robot_profile / joints_info）")
            return False
        with open("../model_convert/source/abs.json", "r", encoding="utf-8") as abs_angle_file:
            abs_angle_dict = json.load(abs_angle_file)
        for ip in abs_ip_list:
            k = lookup_abs_json_key(abs_angle_dict, ip)
            if k is None:
                print("abs IP: ", ip, " 在 abs.json 中无对应项（需 joint_ip+10 或旧版 joint_ip key）")
                return False
    except json.decoder.JSONDecodeError:
        print("abs.json is empty!")
        return False
    return True


def set_motor_zero_pos():
    is_ready = True
    joint_config_path_out = "/root/.adam/"
    if not os.path.exists(joint_config_path_out):
        os.makedirs(joint_config_path_out)
    joint_config_path_out += "joint_abs_config.json"
    if not verify_legality():
        print("Setting motor zero position failed!")
        is_ready = False
    abs_ip_list, joint_names, _ = get_active_joints()
    with open("../model_convert/source/abs.json", "r", encoding="utf-8") as abs_angle_file:
        abs_angle_dict = json.load(abs_angle_file)
    try:
        with open(joint_config_path, "r", encoding="utf-8") as joint_config_file:
            joint_config_dict = json.load(joint_config_file)
    except json.decoder.JSONDecodeError:
        print("joint_abs_config_template.json is empty!")
        is_ready = False
        return is_ready
    try:
        for ip_num in range(len(abs_ip_list)):
            ip = abs_ip_list[ip_num]
            k = lookup_abs_json_key(abs_angle_dict, ip)
            if k is None:
                print(ip, "no abs key")
                continue
            entry = abs_angle_dict[k]
            if "radian" in entry and "motor_rotor_abs_pos" in entry:
                jn = joint_names[ip_num]
                joint_config_dict[jn]["absolute_pos_zero"] = entry["radian"]
                joint_config_dict[jn]["motor_rotor_abs_pos"] = entry["motor_rotor_abs_pos"]
            else:
                print(ip, "no abs")
    except Exception as e:
        print(e)
        print("Setting motor zero failed!")
        is_ready = False
        return is_ready
    try:
        with open(joint_config_path_out, "w", encoding="utf-8") as joint_config_w:
            json.dump(joint_config_dict, joint_config_w, indent=4, ensure_ascii=False)
    except OSError:
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
        joint_config_path = f"../configs/joint_abs_config_{args.version}_template.json"
    else:
        print("wrong version")
        return
    is_legal = verify_legality()
    print(is_legal)
    set_motor_zero_pos()


if __name__ == "__main__":
    main()
