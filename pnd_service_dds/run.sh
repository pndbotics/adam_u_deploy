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

# 根据本机已配置地址解析 DDS 绑定网卡：优先 10.10.20.127，找不到再试 10.10.10.127
#（与 service_run.sh 一致；LD_LIBRARY_PATH 已 export 时，管道里的 ip 可能异常，故用洁净环境调用）
TARGET_IP_PRIMARY="10.10.20.127"
TARGET_IP_FALLBACK="10.10.10.127"
TARGET_IP=""
NETWORK_INTERFACE=""

pnd_ip_addr_show() {
    local ip_bin out
    for ip_bin in /sbin/ip /usr/sbin/ip; do
        [ -x "$ip_bin" ] || continue
        out=$(env -i PATH="/usr/sbin:/sbin:/usr/bin:/bin" HOME="${HOME:-/}" LANG=C LC_ALL=C \
            LD_LIBRARY_PATH= LD_PRELOAD= \
            "$ip_bin" addr show 2>/dev/null) || out=""
        if [ -n "$out" ]; then
            printf '%s\n' "$out"
            return 0
        fi
    done
    return 1
}

pnd_ifconfig_all() {
    local ifc out
    ifc=$(PATH="/sbin:/usr/sbin:/bin:/usr/bin" command -v ifconfig 2>/dev/null) || return 1
    [ -n "$ifc" ] || return 1
    out=$(env -i PATH="/sbin:/usr/sbin:/bin:/usr/bin" HOME="${HOME:-/}" LANG=C LC_ALL=C \
        LD_LIBRARY_PATH= LD_PRELOAD= \
        "$ifc" 2>/dev/null) || out=""
    if [ -n "$out" ]; then
        printf '%s\n' "$out"
        return 0
    fi
    return 1
}

pnd_resolve_interface_for_ip() {
    local tip="$1" iface="" IP_ADDR_OUT IFCONFIG_OUT

    if [ "$tip" = "127.0.0.1" ] || [ "$tip" = "::1" ]; then
        if [ -d /sys/class/net/lo ]; then
            printf '%s\n' "lo"
        fi
        return 0
    fi

    IP_ADDR_OUT=$(pnd_ip_addr_show) || IP_ADDR_OUT=""
    if [ -n "$IP_ADDR_OUT" ] && echo "$IP_ADDR_OUT" | grep -qF "$tip"; then
        iface=$(echo "$IP_ADDR_OUT" | grep -B 2 -F "$tip" | grep "^[0-9]*:" | awk '{print $2}' | sed 's/:$//' | head -n 1)
    fi
    if [ -z "$iface" ]; then
        IFCONFIG_OUT=$(pnd_ifconfig_all) || IFCONFIG_OUT=""
        if [ -n "$IFCONFIG_OUT" ]; then
            iface=$(echo "$IFCONFIG_OUT" | grep -B 1 -F "$tip" | head -n 1 | awk '{print $1}' | sed 's/:$//')
        fi
    fi
    if [ -n "$iface" ]; then
        printf '%s\n' "$iface"
    fi
}

for cand in "$TARGET_IP_PRIMARY" "$TARGET_IP_FALLBACK"; do
    NETWORK_INTERFACE=$(pnd_resolve_interface_for_ip "$cand")
    if [ -n "$NETWORK_INTERFACE" ]; then
        TARGET_IP="$cand"
        break
    fi
done

if [ -z "$NETWORK_INTERFACE" ]; then
    echo "[ERROR] 未找到本机地址 $TARGET_IP_PRIMARY 或 $TARGET_IP_FALLBACK 对应的网络接口"
    echo "[ERROR] 请检查网络配置（至少配置其一，用于 pnd_service_dds -i）"
    rm -f "$LOCKFILE"
    exit 1
fi

echo "[INFO] 找到网络接口: $NETWORK_INTERFACE（匹配本机 IP: $TARGET_IP；优先 $TARGET_IP_PRIMARY，否则 $TARGET_IP_FALLBACK）"

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
