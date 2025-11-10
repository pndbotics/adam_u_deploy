echo "pndxyz"  | sudo -S python3 read_abs.py
result=$(python3 check_abs.py)
if echo "$result" | grep -q "True"; then
	echo "pndxyz"  | sudo -S python3 set_part_zero.py
else
	echo "abs missed, retry"
fi
