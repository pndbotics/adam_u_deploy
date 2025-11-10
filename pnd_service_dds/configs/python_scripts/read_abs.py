import socket
import json
import math
import asyncio
from enum import Enum


class AbsVerEnum(Enum):
    ABS_VER_OLD = 0
    ABS_VER_NEW = 1


ABS_IPS = [
    "10.10.10.100",
    "10.10.10.101",
    "10.10.10.102",
    "10.10.10.103",
    "10.10.10.104",
    "10.10.10.20",
    "10.10.10.21",
    "10.10.10.22",
    "10.10.10.23",
    "10.10.10.24",
    "10.10.10.25",
    "10.10.10.26",
    "10.10.10.40",
    "10.10.10.41",
    "10.10.10.42",
    "10.10.10.43",
    "10.10.10.44",
    "10.10.10.45",
    "10.10.10.46",
]

udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
udp_socket.settimeout(0.03)
remote_port_number = 2334

abs_angle_dict = {}
motor_rotor_angle_dict = {}


def get_motor_rotor_abs_pos(address_list, motor_rotor_angle_dict):
    data_dict = {
        "method": "GET",
        "reqTarget": "/abs_encoder",
    }
    json_string = json.dumps(data_dict)
    for i in address_list:
        try:
            udp_socket.sendto(str.encode(json_string), (i, remote_port_number))
            received_data, address = udp_socket.recvfrom(1024)
            json_object = json.loads(received_data.decode("utf-8"))
        except:
            json_object = {"status": "OK", "reqTarget": "/abs_encoder", "abs_pos": 0}

        if json_object["status"] == "OK":
            abs_data = {
                "motor_rotor_abs_pos": int(json_object["abs_pos"]) * 2 * math.pi / 16384
            }
            motor_rotor_angle_dict[i] = abs_data
            # print(f"ip: {i} json_object: {json_object}")
        else:
            print(f"ip {i} get motor abs pos failed!")


def read_motor_rotor_abs_pos():
    ips = [
        "10.10.10.90",
        "10.10.10.91",
        "10.10.10.92",
        "10.10.10.93",
        "10.10.10.94",
        "10.10.10.10",
        "10.10.10.11",
        "10.10.10.12",
        "10.10.10.13",
        "10.10.10.14",
        "10.10.10.15",
        "10.10.10.16",
        "10.10.10.30",
        "10.10.10.31",
        "10.10.10.32",
        "10.10.10.33",
        "10.10.10.34",
        "10.10.10.35",
        "10.10.10.36",
    ]
    motor_enc_dict = {}
    get_motor_rotor_abs_pos(ips, motor_enc_dict)
    i = 0
    for key, value in motor_enc_dict.items():
        motor_rotor_angle_dict[ABS_IPS[i]] = value
        i += 1


def merge_dicts(dict1, dict2):
    merged_dict = dict1.copy()
    for key, value in dict2.items():
        if key in merged_dict:
            merged_dict[key].update(value)
        else:
            merged_dict[key] = value
    return merged_dict


abs_version_dict = {ip_addr: None for ip_addr in ABS_IPS}
device_info_dict = {"id": 0, "method": "device.info"}
encoder_angle_dict = {"id": 0, "method": "encoder.angle"}
old_encoder_angle_dict = {"id": 1, "method": "Encoder.Angle", "params": ""}


class UDPClientProtocol:
    def __init__(self, host, message, on_response, on_error):
        self.host = host
        self.message = message
        self.on_response = on_response
        self.on_error = on_error
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport
        print(f"Send to {self.host}: {self.message}")
        self.transport.sendto(self.message.encode())

    def datagram_received(self, data, addr):
        self.on_response(data, addr)

    def error_received(self, exc):
        print(f"Error received: {exc}")
        self.on_error(self.host)

    def connection_lost(self, exc):
        print("Connection closed")


async def get_abs_info_handle(host, on_response, on_error):
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: UDPClientProtocol(
            host, json.dumps(device_info_dict), on_response, on_error
        ),
        remote_addr=(host, 2561),
    )
    return transport


async def get_abs_info():
    def handle_response(data, addr):
        print(f"Received from {addr}: {data.decode()}")
        abs_version_dict[addr[0]] = AbsVerEnum.ABS_VER_NEW

    def handle_error(host):
        abs_version_dict[host] = AbsVerEnum.ABS_VER_OLD

    tasks = []
    for host in ABS_IPS:
        task = get_abs_info_handle(host, handle_response, handle_error)
        tasks.append(task)

    await asyncio.gather(*tasks)
    await asyncio.sleep(0.7)
    for task in tasks:
        task.close()


async def get_new_abs_angle_handle(host, on_response, on_error):
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: UDPClientProtocol(
            host, json.dumps(encoder_angle_dict), on_response, on_error
        ),
        remote_addr=(host, 2561),
    )
    return transport

async def get_old_abs_angle_handle(host, on_response, on_error):
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: UDPClientProtocol(
            host, json.dumps(old_encoder_angle_dict), on_response, on_error
        ),
        remote_addr=(host, 2334),
    )
    return transport


async def get_all_abs_angle():
    def handle_response(data, addr):
        print(f"Received from {addr}: {data.decode()}")
        json_object = json.loads(data.decode("utf-8"))
        abs_data = {
            "angle": json_object["result"]["angle"],
            "radian": json_object["result"]["radian"],
        }
        abs_angle_dict[addr[0]] = abs_data

    def handle_error(host):
        pass

    tasks = []
    for host in ABS_IPS:
        if abs_version_dict[host] == AbsVerEnum.ABS_VER_OLD:
            task = get_old_abs_angle_handle(host, handle_response, handle_error)
        elif abs_version_dict[host] == AbsVerEnum.ABS_VER_NEW:
            task = get_new_abs_angle_handle(host, handle_response, handle_error)
        else:
            print(f"Unknown ABS version for host {host}")
            continue
        tasks.append(task)

    await asyncio.gather(*tasks)
    await asyncio.sleep(0.7)
    for task in tasks:
        task.close()
    for host in ABS_IPS:
        if host not in abs_angle_dict:
            print(f"get new abs angle failed! {host}")


def main():
    abs_file = open("source/abs.json", mode="w+", encoding="utf-8")
    for _ in range(3):
        asyncio.run(get_abs_info())
    for abs_ip, abs_type in abs_version_dict.items():
        print(abs_ip, abs_type)
    
    asyncio.run(get_all_abs_angle())
    print(f"abs angle dict: {abs_angle_dict}")
    print("read abs complete!")
    read_motor_rotor_abs_pos()
    print("read motor abs complete!")
    all_angle_dict = merge_dicts(abs_angle_dict, motor_rotor_angle_dict)

    json_string = json.dumps(all_angle_dict, indent=4)
    abs_file.write(json_string)


if __name__ == "__main__":
    main()