import json
import math
import os
import socket
from typing import Any, Dict, List, Optional, Tuple

from config_utils import get_joint_rows_with_active_flag, joint_ip_to_abs_file_key

# JOINT_ROWS：joints_info 全量顺序；(motor_ip, name, is_active)。仅 is_active=False（robot_profile 软禁用）时跳过 2561/2334。
# MOTOR_IPS / ACTIVE_NAMES：仅活跃关节，与 abs.json 写入一致。
# UDP：**2561** 仅访问 encoder_ip（+10）；**2334** 仅访问 motor_ip。
JOINT_ROWS, ADAM_TYPE = get_joint_rows_with_active_flag()
MOTOR_IPS = [ip for ip, _, active in JOINT_ROWS if active]
ACTIVE_NAMES = [name for _, name, active in JOINT_ROWS if active]
ENCODER_IPS: list[str] = [joint_ip_to_abs_file_key(ip) for ip in MOTOR_IPS]


def _dbg(msg: str) -> None:
    """逐步调试：export READ_ABS_DEBUG=1 后生效。"""
    if os.environ.get("READ_ABS_DEBUG", "0").strip() == "1":
        print(f"[DEBUG] read_abs: {msg}", flush=True)


def _last_octet(ip: str) -> int:
    parts = ip.split(".")
    return int(parts[3]) if len(parts) == 4 else -1


_dbg(f"模块加载: adam_type={ADAM_TYPE!r}")
_dbg(f"MOTOR_IPS（2334 /abs_encoder）({len(MOTOR_IPS)}) = {MOTOR_IPS}")
_dbg(f"ENCODER_IPS（2561 encoder.angle，与 abs.json key）({len(ENCODER_IPS)}) = {ENCODER_IPS}")
_dbg(f"ACTIVE_NAMES ({len(ACTIVE_NAMES)}) = {ACTIVE_NAMES}")
_dbg(f"环境: READ_ABS_BIND_IP={os.environ.get('READ_ABS_BIND_IP', '')!r}")
for _i, (_mot, _name, _act) in enumerate(JOINT_ROWS):
    _enc = joint_ip_to_abs_file_key(_mot)
    _dbg(
        f"[{_i}] name={_name!r} motor_ip={_mot} encoder_ip={_enc} active={_act}"
    )

udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
udp_socket.settimeout(0.35)
remote_port_number = 2334

abs_angle_dict: Dict[str, Any] = {}
motor_rotor_angle_dict: Dict[str, Any] = {}

ABS_RPC_PORT = 2561
OLD_ABS_RPC_PORT = 2334
PER_HOST_RPC_TIMEOUT_S = float(os.environ.get("READ_ABS_RPC_TIMEOUT", "0.65"))
# ABS RPC:
#   new ABS: encoder_ip:2561 encoder.angle
#   old ABS: encoder_ip:2334 Encoder.Angle
DEVICE_INFO_PAYLOAD = {"id": 0, "method": "device.info"}
OLD_ENCODER_ANGLE_PAYLOAD: Dict[str, Any] = {
    "id": 1,
    "method": "Encoder.Angle",
    "params": "",
}
ENCODER_ANGLE_REQUESTS: List[Tuple[int, Dict[str, Any]]] = [
    (ABS_RPC_PORT, {"id": 0, "method": "encoder.angle"}),
    (OLD_ABS_RPC_PORT, OLD_ENCODER_ANGLE_PAYLOAD),
]


def _udp_rpc_json(host: str, port: int, payload: dict, timeout: float) -> Optional[Dict[str, Any]]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    bind_ip = os.environ.get("READ_ABS_BIND_IP", "").strip()
    try:
        if bind_ip:
            sock.bind((bind_ip, 0))
    except OSError as e:
        print(f"[WARN] READ_ABS_BIND_IP={bind_ip!r} bind 失败: {e!r}")
    sock.settimeout(timeout)
    try:
        msg = json.dumps(payload).encode("utf-8")
        _dbg(f"UDP send {host}:{port} timeout={timeout}s payload={payload!r}")
        sock.sendto(msg, (host, port))
        data, _addr = sock.recvfrom(4096)
        text = data.decode("utf-8", errors="replace")
        preview = text if len(text) <= 400 else text[:400] + "…"
        _dbg(f"UDP recv {host}:{port} from={_addr!r} bytes={len(data)} body={preview!r}")
        return json.loads(text)
    except OSError as e:
        print(f"[WARN] UDP RPC {host}:{port} {e!r}")
        _dbg(f"UDP {host}:{port} OSError: {e!r}")
        return None
    except json.JSONDecodeError as e:
        print(f"[WARN] UDP RPC {host}:{port} JSON 解析失败: {e!r}")
        _dbg(f"UDP {host}:{port} JSONDecodeError: {e!r}")
        return None
    finally:
        sock.close()


def _radian_from_encoder_angle_reply(jo: dict) -> Optional[float]:
    if not isinstance(jo, dict):
        return None
    res = jo.get("result")
    if isinstance(res, dict):
        if res.get("radian") is not None:
            try:
                return float(res["radian"])
            except (TypeError, ValueError):
                pass
        if res.get("angle") is not None:
            try:
                ang = float(res["angle"])
            except (TypeError, ValueError):
                return None
            if abs(ang) <= 12.566370614359172:
                return ang
            return ang * math.pi / 180.0
    if jo.get("radian") is not None:
        try:
            return float(jo["radian"])
        except (TypeError, ValueError):
            pass
    return None


def _retries_and_timeout_for_abs(abs_ip: str) -> Tuple[int, float]:
    lo = _last_octet(abs_ip)
    if 10 <= lo <= 19:
        n = int(os.environ.get("READ_ABS_LOW_OCTET_RETRIES", "3"))
        t = float(os.environ.get("READ_ABS_LOW_OCTET_TIMEOUT", "1.0"))
        return max(1, n), max(PER_HOST_RPC_TIMEOUT_S, t)
    return 1, PER_HOST_RPC_TIMEOUT_S


def poll_device_info_once():
    _dbg("poll_device_info_once: 开始（2561 → encoder_ip）")
    for motor_ip, joint_name, is_active in JOINT_ROWS:
        encoder_ip = joint_ip_to_abs_file_key(motor_ip)
        if not is_active:
            _dbg(f"device.info 跳过（软禁用）name={joint_name!r} motor_ip={motor_ip}")
            print(
                f"[INFO] 跳过 2561 device.info 关节={joint_name!r} motor={motor_ip}（robot_profile 软禁用）"
            )
            continue
        _dbg(f"device.info motor_ip={motor_ip} encoder_ip={encoder_ip}")
        jo = _udp_rpc_json(
            encoder_ip, ABS_RPC_PORT, DEVICE_INFO_PAYLOAD, PER_HOST_RPC_TIMEOUT_S
        )
        if isinstance(jo, dict) and jo.get("error") is None and isinstance(jo.get("result"), dict):
            print(f"{motor_ip} (2561 @ encoder {encoder_ip}) device.info OK")
            _dbg(f"device.info OK motor_ip={motor_ip} result_keys={list(jo.get('result', {}).keys())}")
        else:
            print(f"{motor_ip} (2561 @ encoder {encoder_ip}) device.info skip/fail")
            _dbg(f"device.info skip/fail motor_ip={motor_ip} jo={jo!r}")
    _dbg("poll_device_info_once: 结束")


def read_all_abs_angle_sequential():
    _dbg(
        "read_all_abs_angle_sequential: 开始（2561 → encoder_ip："
        "encoder.angle（id=0），失败再 Encoder.Angle 旧协议）"
    )
    abs_angle_dict.clear()
    for motor_ip, joint_name, is_active in JOINT_ROWS:
        encoder_ip = joint_ip_to_abs_file_key(motor_ip)
        if not is_active:
            _dbg(
                f"--- 跳过 2561 name={joint_name!r} motor_ip={motor_ip}（robot_profile 软禁用） ---"
            )
            print(
                f"[INFO] 跳过 2561 关节={joint_name!r} motor={motor_ip} encoder={encoder_ip}（robot_profile 软禁用）"
            )
            continue
        _dbg(f"--- 关节 name={joint_name!r} motor_ip={motor_ip} encoder_ip={encoder_ip} ---")
        hosts = [encoder_ip]
        n_try, tmo = _retries_and_timeout_for_abs(motor_ip)
        _dbg(f"hosts_2561={hosts} n_try={n_try} timeout={tmo}")
        rad: Optional[float] = None
        angle_disp: Optional[float] = None
        last_jo: Optional[Dict[str, Any]] = None
        got = False
        win_method: Optional[str] = None
        for host in hosts:
            for attempt in range(n_try):
                for port, payload in ENCODER_ANGLE_REQUESTS:
                    _dbg(
                        f"ABS try host={host}:{port} attempt={attempt + 1}/{n_try} "
                        f"payload id={payload.get('id')} method={payload.get('method')!r}"
                    )
                    jo = _udp_rpc_json(host, port, payload, tmo)
                    last_jo = jo if isinstance(jo, dict) else last_jo
                    if isinstance(jo, dict):
                        rad = _radian_from_encoder_angle_reply(jo)
                        res = jo.get("result")
                        if isinstance(res, dict) and res.get("angle") is not None:
                            try:
                                angle_disp = float(res["angle"])
                            except (TypeError, ValueError):
                                angle_disp = None
                        _dbg(
                            f"2561 解析 radian_extracted={rad!r} "
                            f"angle_disp={angle_disp!r} raw_error={jo.get('error')!r}"
                        )
                    if rad is not None:
                        got = True
                        win_method = str(payload.get("method", ""))
                        break
                if got:
                    break
            if got:
                break

        if rad is not None:
            entry = {"radian": rad}
            if angle_disp is not None:
                entry["angle"] = angle_disp
            abs_angle_dict[motor_ip] = entry
            _dbg(
                f"ABS 成功 motor_ip={motor_ip} host={host} method={win_method!r} entry={entry!r}"
            )
            print(
                f"[OK] ABS joint={motor_ip} host={host} radian={rad} method={win_method!r}"
            )
        else:
            if isinstance(last_jo, dict) and last_jo.get("error") is not None:
                print(
                    f"[WARN] ABS motor={motor_ip} encoder={encoder_ip} error={last_jo.get('error')}"
                )
            else:
                raw = str(last_jo) if last_jo is not None else "None"
                print(
                    f"[WARN] ABS motor={motor_ip} encoder={encoder_ip} "
                    f"无有效 radian（默认不会用 motor_rotor_abs_pos 回填）: {raw[:160]}"
                )
                _dbg(f"2561 ABS 最终失败 motor_ip={motor_ip} last_jo={raw[:300]!r}")

    _dbg(f"read_all_abs_angle_sequential: 结束 abs_angle_dict.keys={list(abs_angle_dict.keys())}")


def _fetch_motor_rotor_rad_at_host(host: str) -> Optional[float]:
    """2334 GET /abs_encoder，成功返回转子绝对角 (rad)，失败返回 None（不再静默写 0）。"""
    data_dict = {"method": "GET", "reqTarget": "/abs_encoder"}
    json_string = json.dumps(data_dict)
    try:
        _dbg(f"2334 send {host}:{remote_port_number} {json_string!r}")
        udp_socket.sendto(str.encode(json_string), (host, remote_port_number))
        received_data, _addr = udp_socket.recvfrom(1024)
        text = received_data.decode("utf-8")
        _dbg(f"2334 recv {host} from={_addr!r} {text[:300]!r}")
        json_object = json.loads(text)
    except Exception as e:
        _dbg(f"2334 {host} 异常: {e!r}")
        return None
    if json_object.get("status") != "OK":
        _dbg(f"2334 {host} status!=OK full={json_object!r}")
        return None
    try:
        raw = int(json_object["abs_pos"])
    except (KeyError, TypeError, ValueError):
        _dbg(f"2334 {host} abs_pos 解析失败 full={json_object!r}")
        return None
    rad_out = raw * 2 * math.pi / 16384.0
    _dbg(f"2334 {host} abs_pos_raw={raw} -> rad={rad_out!r}")
    return rad_out


def read_motor_rotor_abs_pos():
    """对每台关节在 motor_ip 上读 2334 GET /abs_encoder（仅此一台，无回退）。"""
    _dbg("read_motor_rotor_abs_pos: 开始（2334 /abs_encoder → motor_ip）")
    motor_rotor_angle_dict.clear()
    for motor_ip, joint_name, is_active in JOINT_ROWS:
        encoder_ip = joint_ip_to_abs_file_key(motor_ip)
        if not is_active:
            _dbg(
                f"2334 跳过 name={joint_name!r} motor_ip={motor_ip}（robot_profile 软禁用）"
            )
            print(
                f"[INFO] 跳过 2334 关节={joint_name!r} motor={motor_ip} encoder={encoder_ip}（robot_profile 软禁用）"
            )
            continue
        hosts = [motor_ip]
        _dbg(f"2334 关节 name={joint_name!r} motor_ip={motor_ip} encoder_ip={encoder_ip} hosts={hosts}")
        got = False
        for host in hosts:
            mrp = _fetch_motor_rotor_rad_at_host(host)
            if mrp is not None:
                motor_rotor_angle_dict[motor_ip] = {"motor_rotor_abs_pos": mrp}
                print(
                    f"[OK] motor_rotor_abs_pos joint={motor_ip} 2334@{host} radian={mrp:.6f}"
                )
                got = True
                break
        if not got:
            print(
                f"[WARN] motor_rotor /abs_encoder 失败 joint={motor_ip} 2334@{motor_ip}"
            )
    _dbg(
        f"read_motor_rotor_abs_pos: 结束 motor_rotor_angle_dict.keys="
        f"{list(motor_rotor_angle_dict.keys())}"
    )


def merge_dicts(dict1, dict2):
    _dbg(f"merge_dicts: dict1_keys={list(dict1.keys())} dict2_keys={list(dict2.keys())}")
    merged_dict = dict1.copy()
    for key, value in dict2.items():
        if key in merged_dict:
            merged_dict[key].update(value)
            _dbg(f"merge_dicts: 合并 key={key!r} -> {merged_dict[key]!r}")
        else:
            merged_dict[key] = value
            _dbg(f"merge_dicts: 新增 key={key!r} -> {value!r}")
    return merged_dict


def fill_missing_radian_from_motor(all_angle: Dict[str, Any]) -> None:
    """
    历史上这里会在 ABS radian 缺失时用 motor_rotor_abs_pos 回填 radian。
    这会把双编码器伪造成同一路读数，默认禁用；仅显式设置
    READ_ABS_ALLOW_RADIAN_FALLBACK=1 时才保留旧行为。
    """
    if os.environ.get("READ_ABS_ALLOW_RADIAN_FALLBACK", "0") != "1":
        _dbg("fill_missing_radian_from_motor: 默认禁用 motor->radian 回填")
        for motor_ip in MOTOR_IPS:
            k = joint_ip_to_abs_file_key(motor_ip)
            ent = all_angle.get(k)
            if isinstance(ent, dict) and ent.get("radian") is None and ent.get("motor_rotor_abs_pos") is not None:
                print(
                    f"[WARN] {k}（motor 行 {motor_ip}）缺少 ABS radian，未用 motor_rotor_abs_pos 回填；"
                    "请检查 ABS 读取链路"
                )
        return
    for motor_ip in MOTOR_IPS:
        k = joint_ip_to_abs_file_key(motor_ip)
        if k not in all_angle:
            _dbg(f"fill_missing: 跳过 motor_ip={motor_ip} key={k!r}（不在 merged）")
            continue
        ent = all_angle[k]
        if ent.get("radian") is not None:
            _dbg(f"fill_missing: 跳过 key={k!r} 已有 radian={ent.get('radian')!r}")
            continue
        mrp = ent.get("motor_rotor_abs_pos")
        if mrp is None:
            _dbg(f"fill_missing: 跳过 key={k!r} 无 motor_rotor_abs_pos")
            continue
        ent["radian"] = float(mrp)
        print(
            f"[INFO] {k}（motor 行 {motor_ip}）2561 无 radian，已用 motor_rotor_abs_pos 填 radian（窄带/旧固件）"
        )
        _dbg(f"fill_missing: 已填 key={k!r} radian={ent['radian']!r} <- motor {mrp!r}")


def main():
    _dbg("main: 入口")
    if ADAM_TYPE == "unknown" and not JOINT_ROWS:
        print("[ERROR] 无法加载 robot_profile / joints_info（read_abs 退出）")
        _dbg("main: JOINT_ROWS 为空且 adam_type unknown，退出")
        return
    if not MOTOR_IPS:
        print("[ERROR] 无活跃关节 IP（检查 configs/robot/robot_profile.json 与 joints_info）")
        _dbg("main: MOTOR_IPS 为空，退出")
        return
    if os.environ.get("READ_ABS_DEVICE_INFO", "0") == "1":
        _dbg("main: 执行 poll_device_info_once（READ_ABS_DEVICE_INFO=1）")
        poll_device_info_once()

    read_all_abs_angle_sequential()
    print(f"abs angle dict keys: {list(abs_angle_dict.keys())}")
    print("read abs complete!")
    read_motor_rotor_abs_pos()
    print("read motor abs complete!")
    _dbg("main: 合并 2561 + 2334")
    all_angle_dict = merge_dicts(abs_angle_dict, motor_rotor_angle_dict)
    _dbg(f"main: 按 joint_ip_to_abs_file_key 改 key，合并前条目数={len(all_angle_dict)}")
    all_angle_dict = {joint_ip_to_abs_file_key(ip): v for ip, v in all_angle_dict.items()}
    _dbg(f"main: 改 key 后 keys={list(all_angle_dict.keys())}")
    fill_missing_radian_from_motor(all_angle_dict)
    out_path = "../model_convert/source/abs.json"
    _dbg(f"main: 写入 {out_path!r}")
    with open(out_path, mode="w", encoding="utf-8") as abs_file:
        abs_file.write(json.dumps(all_angle_dict, indent=4))
    _dbg("main: 结束")


if __name__ == "__main__":
    main()
