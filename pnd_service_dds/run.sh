#!/bin/bash
exec 100>/tmp/pnd_service.lock || exit 1
flock -n 100 || { echo "Script is already running"; exit 1; }

cd "$(dirname "$0")"/configs/python_scripts || exit
python3 read_abs.py
result=$(python3 check_abs.py | tail -n 1)

if [ "$result" = "True" ]; then
    cd ../../
    # 直接运行（需SUID或sudo免密）
    ./pnd_service_dds -i eth0
    # 或用sudo（确保无密码）
    # sudo ./pnd_service_dds -i eth0
else
    echo "ABS not complete, retry later."
    exit 1
fi
