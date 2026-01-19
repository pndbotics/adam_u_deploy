#!/bin/bash
export LD_LIBRARY_PATH=/opt/ros/humble/lib:$LD_LIBRARY_PATH
export ROS_LOCALHOST_ONLY=1
export ROS_LOG_DIR=/tmp/ros2_logs_$(date +%s)

./pnd_adam_u_deploy_dds