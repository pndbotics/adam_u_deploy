#!/bin/bash

# 服务部署脚本
# 功能：将pnd_service_dds.service文件部署为系统服务

set -e  # 遇到任何错误立即退出脚本

# ==========================
# 配置变量
# ==========================
SERVICE_NAME="pnd_service_dds.service"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"  # 脚本所在目录
SERVICE_FILE_SOURCE="${SCRIPT_DIR}/${SERVICE_NAME}"
SERVICE_FILE_TARGET="/etc/systemd/system/${SERVICE_NAME}"

# ==========================
# 颜色输出函数
# ==========================
red_echo() { echo -e "\033[31m$1\033[0m"; }
green_echo() { echo -e "\033[32m$1\033[0m"; }
yellow_echo() { echo -e "\033[33m$1\033[0m"; }

# ==========================
# 检查脚本执行权限
# ==========================
check_permissions() {
    if [[ $EUID -eq 0 ]]; then
        red_echo "错误：请不要使用root权限直接运行此脚本"
        red_echo "请使用普通用户权限运行，脚本会在需要时通过sudo提权"
        exit 1
    fi
}

# ==========================
# 检查服务文件是否存在
# ==========================
check_service_file() {
    yellow_echo "检查服务文件..."
    
    if [[ ! -f "$SERVICE_FILE_SOURCE" ]]; then
        red_echo "错误：在以下路径找不到服务文件: $SERVICE_FILE_SOURCE"
        red_echo "请确保脚本与 $SERVICE_NAME 文件在同一目录"
        exit 1
    fi
    
    green_echo "✓ 服务文件存在: $SERVICE_FILE_SOURCE"
}

# ==========================
# 复制服务文件到系统目录
# ==========================
copy_service_file() {
    yellow_echo "复制服务文件到系统目录..."
    
    # 检查目标目录是否存在[1,4](@ref)
    if [[ ! -d "/etc/systemd/system" ]]; then
        red_echo "错误：/etc/systemd/system 目录不存在，请检查systemd是否已安装"
        exit 1
    fi
    
    # 复制文件[5](@ref)
    sudo cp "$SERVICE_FILE_SOURCE" "$SERVICE_FILE_TARGET"
    
    # 设置正确的文件权限[5](@ref)
    sudo chmod 644 "$SERVICE_FILE_TARGET"
    
    green_echo "✓ 服务文件已复制到: $SERVICE_FILE_TARGET"
    green_echo "✓ 文件权限已设置为644"
}

# ==========================
# 重新加载systemd配置
# ==========================
reload_systemd() {
    yellow_echo "重新加载systemd配置..."
    
    sudo systemctl daemon-reload
    green_echo "✓ systemd配置已重新加载"
}

# ==========================
# 启用并启动服务
# ==========================
enable_and_start_service() {
    yellow_echo "启用服务..."
    
    # 启用服务（开机自启）[1,3](@ref)
    sudo systemctl enable "$SERVICE_NAME"
    green_echo "✓ 服务已设置为开机自启"
    
    yellow_echo "启动服务..."
    
    # 启动服务[1,5](@ref)
    sudo systemctl start "$SERVICE_NAME"
    green_echo "✓ 服务启动命令已执行"
}

# ==========================
# 检查服务状态
# ==========================
check_service_status() {
    yellow_echo "检查服务状态..."
    
    # 等待片刻让服务完全启动
    sleep 2
    
    # 显示服务状态[4](@ref)
    sudo systemctl status "$SERVICE_NAME" --no-pager -l
}

# ==========================
# 显示使用说明
# ==========================
show_usage_info() {
    echo ""
    green_echo "服务部署完成！"
    echo ""
    yellow_echo "后续管理命令:"
    echo "查看服务状态: sudo systemctl status $SERVICE_NAME"
    echo "停止服务: sudo systemctl stop $SERVICE_NAME"
    echo "启动服务: sudo systemctl start $SERVICE_NAME"
    echo "重启服务: sudo systemctl restart $SERVICE_NAME"
    echo "查看服务日志: sudo journalctl -u $SERVICE_NAME -f"
    echo "禁用开机自启: sudo systemctl disable $SERVICE_NAME"
    echo ""
}

# ==========================
# 主执行流程
# ==========================
main() {
    green_echo "开始部署 pnd_service_dds 系统服务"
    green_echo "脚本目录: $SCRIPT_DIR"
    echo ""
    
    # 执行部署步骤
    check_permissions
    check_service_file
    copy_service_file
    reload_systemd
    enable_and_start_service
    check_service_status
    show_usage_info
    
    green_echo "服务部署流程完成！"
}

# 执行主函数
main "$@"
