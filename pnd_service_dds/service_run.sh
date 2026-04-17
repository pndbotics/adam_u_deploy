#!/bin/bash

# ==========================
# 基本配置
# ==========================
UDP_IP="10.10.10.200"
UDP_PORT=2561

MSG_OFF='{ "id": "0", "method": "device.power", "params": 0 }'
MSG_ON='{ "id": "0", "method": "device.power", "params": 1 }'

PROGRAM="pnd_service_dds"
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# 勿在此处 export LD_LIBRARY_PATH：${SCRIPT_DIR}/lib 若含与系统不兼容的 .so，
# 会导致动态链接的系统工具（如 iproute2 的 ip）在管道里段错误，接口检测失败。
# 仅在启动 pnd_service_dds 时通过 PROGRAM_EXEC / sudo env 注入库路径即可。

# 根据本机已配置地址解析 DDS 绑定网卡：优先 10.10.20.127，找不到再试 10.10.10.127
TARGET_IP_PRIMARY="10.10.20.127"
TARGET_IP_FALLBACK="10.10.10.127"
TARGET_IP=""
NETWORK_INTERFACE=""

# systemd 启动时 unit 可能带 LD_LIBRARY_PATH/LD_PRELOAD；仅用 LD_LIBRARY_PATH= 仍可能让 ip 段错误。
# 在「洁净环境」下调用 iproute2，并优先使用绝对路径。
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

# 给定 IP，输出其所在网卡名（单行 stdout）；找不到则无输出。环回不调用 ip。
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
    exit 1
fi

echo "[INFO] 找到网络接口: $NETWORK_INTERFACE（匹配本机 IP: $TARGET_IP；优先 $TARGET_IP_PRIMARY，否则 $TARGET_IP_FALLBACK）"
# 通过 sudo 启动时显式传递 LD_LIBRARY_PATH，避免 sudo 清理环境导致动态库找不到。
# 必须用数组再 "${PROGRAM_EXEC[@]}" 执行：若写成整串变量再 $VAR 展开，内嵌引号
# 不会在二次 word-split 中按预期生效，env 可能收不到 LD_LIBRARY_PATH，表现为
# lib/ 下已有 librbdl.so 仍报 cannot open shared object file。
PROGRAM_EXEC=(
  sudo env "LD_LIBRARY_PATH=${SCRIPT_DIR}/lib"
  "$SCRIPT_DIR/$PROGRAM" -i "$NETWORK_INTERFACE"
)

# 配置目录（新架构路径）
CONFIG_DIR="$SCRIPT_DIR/tools/python/calibration"

MAX_RETRIES=3
LONG_WAIT_MINUTES=10
LONG_WAIT_SECONDS=$((LONG_WAIT_MINUTES * 60))

LOCK_FILE="/tmp/$(basename "$0").lock"
PID_FILE="/tmp/$PROGRAM.pid"
PROGRAM_PID=""

# SIGTERM 后等待主进程退出的最长时间（秒）。过短会导致 DdsService 尚未析构即 SIGKILL，
# Runtime::~Runtime 中 disableAllJoints() 来不及执行。可 export PND_TERM_GRACE_SEC=45 等。
PND_TERM_GRACE_SEC="${PND_TERM_GRACE_SEC:-35}"

# 等待 PID 不存在或超时（步进 0.2s）；返回 0 表示已退出，1 表示仍存活
_pnd_wait_pid_gone() {
    local pid="$1"
    local max_sec="${2:-35}"
    local steps=$((max_sec * 5))
    local i
    for ((i = 0; i < steps; i++)); do
        kill -0 "$pid" 2>/dev/null || return 0
        read -t 0.2 _ 2>/dev/null || sleep 0.2 2>/dev/null || break
    done
    kill -0 "$pid" 2>/dev/null && return 1
    return 0
}

cleanup_on_exit() {
    echo "[INFO] 收到停止信号，开始清理..."
    
    # 首先尝试通过 PID 文件杀死（如果存在）
    if [ -f "$PID_FILE" ]; then
        local saved_pid=$(cat "$PID_FILE" 2>/dev/null)
        if [ -n "$saved_pid" ] && kill -0 "$saved_pid" 2>/dev/null; then
            echo "[INFO] 通过 PID 文件停止程序 (PID: $saved_pid)，TERM 后最多等待 ${PND_TERM_GRACE_SEC}s 以便 disableAllJoints..."
            kill -TERM "$saved_pid" 2>/dev/null
            if ! _pnd_wait_pid_gone "$saved_pid" "$PND_TERM_GRACE_SEC"; then
                echo "[WARN] 程序未在 ${PND_TERM_GRACE_SEC}s 内退出，发送 KILL..."
                kill -KILL "$saved_pid" 2>/dev/null
            fi
        fi
    fi
    
    # 使用 pgrep 查找所有 pnd_service_dds 进程（包括通过 sudo 启动的）
    local pids=$(pgrep -f "pnd_service_dds.*-i.*$NETWORK_INTERFACE" 2>/dev/null)
    if [ -n "$pids" ]; then
        echo "[INFO] 找到运行中的程序进程，正在停止..."
        for pid in $pids; do
            if kill -0 "$pid" 2>/dev/null; then
                echo "[INFO] 停止进程 (PID: $pid)..."
                kill -TERM "$pid" 2>/dev/null
            fi
        done
        local i
        local steps=$((PND_TERM_GRACE_SEC * 5))
        for ((i = 0; i < steps; i++)); do
            local remaining=$(pgrep -f "pnd_service_dds.*-i.*$NETWORK_INTERFACE" 2>/dev/null)
            if [ -z "$remaining" ]; then
                break
            fi
            read -t 0.2 _ 2>/dev/null || sleep 0.2 2>/dev/null || break
        done
        # 如果还有进程在运行，强制杀死
        local remaining=$(pgrep -f "pnd_service_dds.*-i.*$NETWORK_INTERFACE" 2>/dev/null)
        if [ -n "$remaining" ]; then
            echo "[WARN] 仍有进程未响应 TERM（已等待 ${PND_TERM_GRACE_SEC}s），强制杀死..."
            for pid in $remaining; do
                kill -KILL "$pid" 2>/dev/null
            done
        fi
    fi
    
    # 也尝试杀死保存的 PROGRAM_PID（可能是 sudo 包装进程）
    if [ -n "$PROGRAM_PID" ] && kill -0 "$PROGRAM_PID" 2>/dev/null; then
        echo "[INFO] 停止启动进程 (PID: $PROGRAM_PID)..."
        kill -TERM "$PROGRAM_PID" 2>/dev/null
        if ! _pnd_wait_pid_gone "$PROGRAM_PID" "$PND_TERM_GRACE_SEC"; then
            kill -KILL "$PROGRAM_PID" 2>/dev/null
        fi
    fi

    # 清理文件
    rm -f "$LOCK_FILE" "$PID_FILE"
    echo "[INFO] 清理完成，脚本退出。"
    exit 0
}

trap cleanup_on_exit INT TERM EXIT

send_udp_message() {
    echo -n "$1" > /dev/udp/$UDP_IP/$UDP_PORT 2>/dev/null
}

# 灯带报错：向 light_controller 微服务（127.0.0.1:8627）发送 ENCODER 错误
send_light_encoder_error() {
    echo -n '{"action":"add_error","error":"ENCODER"}' > /dev/udp/127.0.0.1/8627 2>/dev/null
}

# 灯带清除错误：向 light_controller 微服务发送 clear_errors
send_light_clear_errors() {
    echo -n '{"action":"clear_errors"}' > /dev/udp/127.0.0.1/8627 2>/dev/null
}

is_running() {
    if pgrep -f "pnd_service_dds.*-i.*$NETWORK_INTERFACE" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# RK3588 等：默认 ondemand/schedutil 易导致 wakeup 抖动，进而放大 getNextFeedback 读锁超时。
# 启动时尽量设为 performance；无 cpufreq、无权限时仅告警。跳过：PND_SKIP_CPUFREQ_PERFORMANCE=1
try_set_cpufreq_performance() {
    if [ "${PND_SKIP_CPUFREQ_PERFORMANCE:-0}" = "1" ]; then
        echo "[INFO] 跳过 CPU governor 设置（PND_SKIP_CPUFREQ_PERFORMANCE=1）"
        return 0
    fi
    local base="/sys/devices/system/cpu"
    shopt -s nullglob
    local gov_paths=( "${base}"/cpu*/cpufreq/scaling_governor )
    shopt -u nullglob
    if [ ${#gov_paths[@]} -eq 0 ]; then
        echo "[INFO] 未检测到 cpufreq scaling_governor，跳过 performance 设置"
        return 0
    fi
    local wrote=0
    for g in "${gov_paths[@]}"; do
        if echo performance >"$g" 2>/dev/null; then
            wrote=1
        fi
    done
    if [ "$wrote" = "1" ]; then
        echo "[INFO] CPU scaling_governor 已设为 performance（降低周期抖动，建议 RK3588 部署保持）"
        return 0
    fi
    if command -v sudo >/dev/null 2>&1; then
        if sudo bash -c 'shopt -s nullglob; ok=0; for g in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do echo performance > "$g" && ok=1; done; exit $((ok==0))' 2>/dev/null; then
            echo "[INFO] CPU scaling_governor 已设为 performance（通过 sudo）"
            return 0
        fi
    fi
    echo "[WARN] 未能写入 scaling_governor=performance（需 root）。可手动: echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor"
    return 0
}

start_program() {
    echo "[INFO] 启动程序：sudo env LD_LIBRARY_PATH=\"${SCRIPT_DIR}/lib\" ${SCRIPT_DIR}/$PROGRAM -i ${NETWORK_INTERFACE}"
    cd "$SCRIPT_DIR" || return 1
    "${PROGRAM_EXEC[@]}" &
    local local_pid=$!
    PROGRAM_PID=$local_pid  # 保存到全局变量（可能是 sudo 进程的 PID）
    # 使用可中断的等待（最多8秒的初始化时间，如果进程在中途退出则停止等待）
    for i in {1..80}; do
        if ! kill -0 $local_pid 2>/dev/null; then
            break
        fi
        read -t 0.1 _ 2>/dev/null || true
        sleep 0.1 2>/dev/null || break
    done

    # 查找实际程序的 PID（不是 sudo 的 PID）
    local actual_pid=$(pgrep -f "pnd_service_dds.*-i.*$NETWORK_INTERFACE" | grep -v "^$local_pid$" | head -n 1)
    
    if [ -z "$actual_pid" ]; then
        # 如果找不到实际程序，检查 sudo 进程是否还在运行
        if ! kill -0 $local_pid 2>/dev/null; then
            echo "[ERROR] 程序启动后立即退出。"
            PROGRAM_PID=""
            return 1
        fi
        # sudo 进程还在，但实际程序可能还没启动，再等一会
        for i in {1..20}; do
            read -t 0.1 _ 2>/dev/null || true
            sleep 0.1 2>/dev/null || break
        done
        actual_pid=$(pgrep -f "pnd_service_dds.*-i.*$NETWORK_INTERFACE" | grep -v "^$local_pid$" | head -n 1)
        if [ -z "$actual_pid" ]; then
            echo "[ERROR] 无法找到实际程序进程。"
            PROGRAM_PID=""
            return 1
        fi
    fi

    echo "[INFO] 程序已启动，实际 PID = $actual_pid (启动进程 PID = $local_pid)"
    echo $actual_pid > "$PID_FILE"
    return 0
}

script_is_running() {
    exec 200>"$LOCK_FILE"
    if flock -n 200; then
        return 0
    else
        return 1
    fi
}

echo "[INFO] ===== PND 监控脚本启动 ====="

if ! script_is_running; then
    echo "[ERROR] 另一个实例的脚本正在运行中，本次启动退出。"
    exit 1
fi
echo "[INFO] 获取单一实例锁成功。"

try_set_cpufreq_performance

while true; do
    retry_count=0
    success_flag=0

    while [ $retry_count -lt $MAX_RETRIES ] && [ $success_flag -eq 0 ]; do
        cd "$CONFIG_DIR" || exit
        python3 read_abs.py
        result=$(python3 check_abs.py | tail -n 1)

        if [ "$result" != "True" ]; then
            echo "[WARN] ABS not complete，发送 OFF/ON 后重试"
            send_light_encoder_error
            send_udp_message "$MSG_OFF"
            # 使用可中断的等待（3秒）
            for i in {1..30}; do
                read -t 0.1 _ 2>/dev/null || true
                sleep 0.1 2>/dev/null || break
            done
            send_udp_message "$MSG_ON"
            # 使用可中断的等待（10秒）
            for i in {1..100}; do
                read -t 0.1 _ 2>/dev/null || true
                sleep 0.1 2>/dev/null || break
            done
            continue
        fi

        echo "[INFO] ABS 就绪，尝试启动程序..."
        if start_program; then
            echo "[INFO] 程序启动成功！"
            success_flag=1
            break
        else
            echo "[WARN] 启动失败 → 执行上下电操作 (第 $((retry_count + 1)) 次重试)"
            send_udp_message "$MSG_OFF"
            # 使用可中断的等待（3秒）
            for i in {1..30}; do
                read -t 0.1 _ 2>/dev/null || true
                sleep 0.1 2>/dev/null || break
            done
            send_udp_message "$MSG_ON"
            # 使用可中断的等待（10秒）
            for i in {1..100}; do
                read -t 0.1 _ 2>/dev/null || true
                sleep 0.1 2>/dev/null || break
            done
            ((retry_count++))
        fi
    done

    if [ $success_flag -eq 1 ]; then
        echo "[INFO] 操作成功，进入持续监控状态..."
        send_light_clear_errors
        while is_running; do
            # 使用可中断的等待，每1秒检查一次
            for i in {1..60}; do
                if ! is_running; then
                    break
                fi
                # 使用 read -t 替代 sleep，可以被信号中断
                read -t 1 _ 2>/dev/null || sleep 1
            done
        done
        echo "[WARN] 检测到程序已退出，执行下电上电操作后重新启动..."
        rm -f "$PID_FILE"
        PROGRAM_PID=""
        
        # 执行下电操作
        echo "[INFO] 发送下电命令..."
        send_udp_message "$MSG_OFF"
        # 等待3秒
        for i in {1..30}; do
            read -t 0.1 _ 2>/dev/null || true
            sleep 0.1 2>/dev/null || break
        done
        
        # 执行上电操作
        echo "[INFO] 发送上电命令..."
        send_udp_message "$MSG_ON"
        # 等待10秒
        for i in {1..100}; do
            read -t 0.1 _ 2>/dev/null || true
            sleep 0.1 2>/dev/null || break
        done
        
        echo "[INFO] 下电上电完成，将重新启动程序..."
    else
        echo "[ERROR] 连续 $MAX_RETRIES 次重试均失败，进入长等待模式：${LONG_WAIT_MINUTES} 分钟"
        send_light_encoder_error
        send_udp_message "$MSG_OFF"
        echo "[INFO] 等待 ${LONG_WAIT_MINUTES} 分钟后将自动重试..."
        # 使用可中断的等待，每1秒检查一次
        for i in $(seq 1 $LONG_WAIT_SECONDS); do
            # 使用 read -t 替代 sleep，可以被信号中断
            read -t 1 _ 2>/dev/null || sleep 1
        done
    fi
done
