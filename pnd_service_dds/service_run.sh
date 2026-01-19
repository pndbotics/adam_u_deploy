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
    exit 1
fi

echo "[INFO] 找到网络接口: $NETWORK_INTERFACE (IP: $TARGET_IP)"
PROGRAM_CMD="sudo $SCRIPT_DIR/pnd_service_dds -i $NETWORK_INTERFACE"

# 配置目录（新架构路径）
CONFIG_DIR="$SCRIPT_DIR/tools/python/calibration"

MAX_RETRIES=3
LONG_WAIT_MINUTES=10
LONG_WAIT_SECONDS=$((LONG_WAIT_MINUTES * 60))

LOCK_FILE="/tmp/$(basename "$0").lock"
PID_FILE="/tmp/$PROGRAM.pid"
PROGRAM_PID=""

cleanup_on_exit() {
    echo "[INFO] 收到停止信号，开始清理..."
    
    # 首先尝试通过 PID 文件杀死（如果存在）
    if [ -f "$PID_FILE" ]; then
        local saved_pid=$(cat "$PID_FILE" 2>/dev/null)
        if [ -n "$saved_pid" ] && kill -0 "$saved_pid" 2>/dev/null; then
            echo "[INFO] 通过 PID 文件停止程序 (PID: $saved_pid)..."
            kill -TERM "$saved_pid" 2>/dev/null
            # 使用可中断的等待（1秒）
            read -t 1 _ 2>/dev/null || sleep 1
            if kill -0 "$saved_pid" 2>/dev/null; then
                echo "[WARN] 程序未响应 TERM 信号，强制杀死..."
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
        # 等待最多3秒，使用可中断的等待
        for i in {1..30}; do
            local remaining=$(pgrep -f "pnd_service_dds.*-i.*$NETWORK_INTERFACE" 2>/dev/null)
            if [ -z "$remaining" ]; then
                break
            fi
            read -t 0.1 _ 2>/dev/null || true
            sleep 0.1 2>/dev/null || break
        done
        # 如果还有进程在运行，强制杀死
        local remaining=$(pgrep -f "pnd_service_dds.*-i.*$NETWORK_INTERFACE" 2>/dev/null)
        if [ -n "$remaining" ]; then
            echo "[WARN] 仍有进程未响应，强制杀死..."
            for pid in $remaining; do
                kill -KILL "$pid" 2>/dev/null
            done
        fi
    fi
    
    # 也尝试杀死保存的 PROGRAM_PID（可能是 sudo 进程）
    if [ -n "$PROGRAM_PID" ] && kill -0 "$PROGRAM_PID" 2>/dev/null; then
        echo "[INFO] 停止启动进程 (PID: $PROGRAM_PID)..."
        kill -TERM "$PROGRAM_PID" 2>/dev/null
        # 使用可中断的等待（0.5秒）
        read -t 0.5 _ 2>/dev/null || sleep 0.5
        if kill -0 "$PROGRAM_PID" 2>/dev/null; then
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

is_running() {
    if pgrep -f "$PROGRAM_CMD" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

start_program() {
    echo "[INFO] 启动程序：$PROGRAM_CMD"
    cd "$SCRIPT_DIR" || return 1
    $PROGRAM_CMD &
    local local_pid=$!
    PROGRAM_PID=$local_pid  # 保存到全局变量（可能是 sudo 进程的 PID）
    # 使用可中断的等待（8秒）
    for i in {1..80}; do
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

while true; do
    retry_count=0
    success_flag=0

    while [ $retry_count -lt $MAX_RETRIES ] && [ $success_flag -eq 0 ]; do
        cd "$CONFIG_DIR" || exit
        python3 read_abs.py
        result=$(python3 check_abs.py | tail -n 1)

        if [ "$result" != "True" ]; then
            echo "[WARN] ABS not complete，发送 OFF/ON 后重试"
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
        send_udp_message "$MSG_OFF"
        echo "[INFO] 等待 ${LONG_WAIT_MINUTES} 分钟后将自动重试..."
        # 使用可中断的等待，每1秒检查一次
        for i in $(seq 1 $LONG_WAIT_SECONDS); do
            # 使用 read -t 替代 sleep，可以被信号中断
            read -t 1 _ 2>/dev/null || sleep 1
        done
    fi
done
