#!/bin/bash
# 让动态链接器在启动时优先搜索本目录下的 lib（例如 librbdl.so）
BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
export LD_LIBRARY_PATH="${BASE_DIR}/lib:${LD_LIBRARY_PATH}"

# 使用 mktemp 在 /tmp 目录创建一个唯一的锁文件
LOCKFILE=$(mktemp -p /tmp pnd_service_lock.XXXXXX) || exit 1

# 将文件描述符关联到这个锁文件
exec 100>"$LOCKFILE" || exit 1

# 尝试获取锁
flock -n 100 || { echo "Script is already running"; rm -f "$LOCKFILE"; exit 1; }

# 检查 10.10.20.127 是否存在并获取对应的网络接口
TARGET_IP="10.10.20.127"
NETWORK_INTERFACE=""

# 方法1: 使用 ip 命令查找 IP 对应的接口
if command -v ip >/dev/null 2>&1; then
    if ip addr show | grep -q "$TARGET_IP"; then
        # 查找包含该 IP 的接口名
        NETWORK_INTERFACE=$(ip addr show | grep -B 2 "$TARGET_IP" | grep "^[0-9]*:" | awk '{print $2}' | sed 's/:$//' | head -n 1)
    fi
fi

# 方法2: 如果 ip 命令失败，尝试使用 ifconfig
if [ -z "$NETWORK_INTERFACE" ] && command -v ifconfig >/dev/null 2>&1; then
    NETWORK_INTERFACE=$(ifconfig | grep -B 1 "$TARGET_IP" | head -n 1 | awk '{print $1}' | sed 's/:$//')
fi

if [ -z "$NETWORK_INTERFACE" ]; then
    echo "[ERROR] 未找到 IP 地址 $TARGET_IP 对应的网络接口"
    echo "[ERROR] 请检查网络配置，确保 $TARGET_IP 已配置"
    rm -f "$LOCKFILE"
    exit 1
fi

echo "[INFO] 找到网络接口: $NETWORK_INTERFACE (IP: $TARGET_IP)"

# 进入标定脚本目录（新架构路径）
cd "${BASE_DIR}/tools/python/calibration" || exit
python3 read_abs.py
result=$(python3 check_abs.py | tail -n 1)

if [ "$result" = "True" ]; then
    cd "${BASE_DIR}"
    # 使用检测到的网络接口运行（需SUID或sudo免密）
    ./pnd_service_dds -i "$NETWORK_INTERFACE"
else
    echo "ABS not complete, retry later."
    rm -f "$LOCKFILE"
    exit 1
fi
