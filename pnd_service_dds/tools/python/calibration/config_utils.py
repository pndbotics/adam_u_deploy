import json
import os

# robot_profile disabled_groups 与关节名的对应（与 PConfig / read_abs 软禁用一致）
PROFILE_GROUP_MAPPING = {
    "left_arm": [
        "shoulderPitch_Left",
        "shoulderRoll_Left",
        "shoulderYaw_Left",
        "elbow_Left",
        "wristYaw_Left",
        "wristPitch_Left",
        "wristRoll_Left",
    ],
    "right_arm": [
        "shoulderPitch_Right",
        "shoulderRoll_Right",
        "shoulderYaw_Right",
        "elbow_Right",
        "wristYaw_Right",
        "wristPitch_Right",
        "wristRoll_Right",
    ],
    "neck": ["neckYaw", "neckPitch"],
    "waist": ["waistRoll", "waistPitch", "waistYaw"],
    "left_leg": [
        "hipPitch_Left",
        "hipRoll_Left",
        "hipYaw_Left",
        "kneePitch_Left",
        "anklePitch_Left",
        "ankleRoll_Left",
    ],
    "right_leg": [
        "hipPitch_Right",
        "hipRoll_Right",
        "hipYaw_Right",
        "kneePitch_Right",
        "anklePitch_Right",
        "ankleRoll_Right",
    ],
}


def load_json_file(path: str, label: str):
    """
    读取 JSON；解析失败时打印绝对路径与可操作的提示（便于排查机上损坏的 robot_profile 等）。
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        ap = os.path.abspath(path)
        print(f"[ERROR] config_utils: 无效的 JSON（{label}）: {ap}")
        print(f"[ERROR]   {e.msg} (line {e.lineno}, column {e.colno})")
        if "Expecting value" in e.msg:
            print(
                "[ERROR]   常见原因：数组写成 [,]、末尾多逗号等非法形式，或某键后缺少值。"
                " robot_profile.json 中 disabled_joints / disabled_groups 须为字符串数组，例如 [] 或 [\"left_arm\"]。"
            )
        raise


def joint_ip_to_abs_file_key(joint_ip: str) -> str:
    """
    与 C++ RealRobot::readAbsEncoder 中 incrementLastField(ipList) 一致：
    abs.json 顶层 key 为 joints_info 关节行 ip 的末字节 +10（全体关节同一规则）。
    若行 ip 表示执行器，则 +10 与「编码器 = 执行器 +10」在末字节上一致。

    注意：read_abs.py 中 **2561** 固定访问本 key 对应 IP（encoder_ip，行末字节 +10），
    **2334** 固定访问 joints_info 行 IP（motor_ip）；与 C++ processEncoderItem 键值规则一致。
    """
    parts = joint_ip.rsplit(".", 1)
    if len(parts) != 2:
        return joint_ip
    p0, last_s = parts
    try:
        last = int(last_s)
    except ValueError:
        return joint_ip
    if last + 10 > 255:
        return joint_ip
    return f"{p0}.{last + 10}"


def lookup_abs_json_key(abs_data: dict, joint_ip: str):
    """读 abs.json：优先 +10 key，兼容旧脚本以 joint_ip 为 key。"""
    k = joint_ip_to_abs_file_key(joint_ip)
    if k in abs_data:
        return k
    if joint_ip in abs_data:
        return joint_ip
    return None


def get_joint_rows_with_active_flag(base_path="../../../"):
    """
    与 joints_info 中本机型关节顺序一致：(motor_ip, joint_name, is_active)。
    is_active 仅由 robot_profile 的 disabled_joints / disabled_groups 决定。
    read_abs 仅应对 is_active=False 的关节跳过 2561 与 2334。
    """
    try:
        profile_path = os.path.join(base_path, "configs/robot/robot_profile.json")
        joints_info_path = os.path.join(base_path, "configs/device/joints_info.json")
        profile = load_json_file(profile_path, "robot_profile.json")
        joints_info = load_json_file(joints_info_path, "joints_info.json")
        adam_type = profile.get("adam_type", "adam_pro")
        disabled_joints = set(profile.get("disabled_joints", []))
        disabled_groups = set(profile.get("disabled_groups", []))
        joint_to_group = {}
        for group, joints in PROFILE_GROUP_MAPPING.items():
            for jn in joints:
                joint_to_group[jn] = group
        all_joints = joints_info.get("robot_configs", {}).get(adam_type, {}).get("joints", [])
        rows = []
        for joint in all_joints:
            name = joint["name"]
            ip = joint["ip"]
            grp = joint_to_group.get(name)
            soft_off = name in disabled_joints or (grp and grp in disabled_groups)
            rows.append((ip, name, not soft_off))
        return rows, adam_type
    except Exception as e:
        if isinstance(e, json.JSONDecodeError):
            return [], "unknown"
        print(f"[ERROR] config_utils: Failed to load joint rows: {e}")
        return [], "unknown"


def get_active_joints(base_path="../../../"):
    """
    从 robot_profile + joints_info 得到当前应参与标定/读 ABS 的关节 ip 与名称（与 C++ PConfig 软禁用一致）。

    返回的 ip 为 joints_info 每行「ip」字段（常为执行器侧），不是「编码器物理 IP」；
    read_abs 中 2561→encoder_ip（+10）、2334→motor_ip（joints_info 行 IP），与下述无关。
    """
    rows, adam_type = get_joint_rows_with_active_flag(base_path)
    if adam_type == "unknown" and not rows:
        return [], [], "unknown"
    active_ips = [ip for ip, _, active in rows if active]
    active_names = [name for _, name, active in rows if active]
    return active_ips, active_names, adam_type


def is_joint_active(joint_name, base_path="../../../"):
    try:
        profile_path = os.path.join(base_path, "configs/robot/robot_profile.json")
        profile = load_json_file(profile_path, "robot_profile.json")
        disabled_joints = set(profile.get("disabled_joints", []))
        disabled_groups = set(profile.get("disabled_groups", []))
        if joint_name in disabled_joints:
            return False
        for group, joints in PROFILE_GROUP_MAPPING.items():
            if group in disabled_groups and joint_name in joints:
                return False
        return True
    except Exception:
        return True
