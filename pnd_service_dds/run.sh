#!/bin/bash

cd $(dirname "$0")/configs/python_scripts || exit
python3 read_abs.py
result=$(python3 check_abs.py)
if [ "$result" = "True" ]
then
    cd ../../
    sudo ./pnd_service_dds -i wlo1
else	
    echo "abs not complete, retry"	
fi

