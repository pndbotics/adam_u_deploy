# PND Adam-U Deploy

## 🏷️ Version Information

**Version**: `v1.2.1`  
**Release Date**: 2026-01-28  
**Compatible System**: Ubuntu 22.04 x86_64  
**Supported Platform**: PND Adam-U Humanoid Robot

---

## 🚀 New Features and Updates

- 🔧 **New Deployment Scripts and Automation Support**
  - Support for compiling `pnd_service_dds` and `pnd_adam_dds` modules from source
  - Built-in installation of `cyclonedds` and `cyclonedds-cxx` dependencies
- 🤖 **Improved Simulation and Real Robot Control Flow**
  - Added Mujoco simulation environment configuration and startup examples
  - Complete control link support for Zero / UserControl / Func / Stop modes
- 🎮 **Xbox Controller Interaction Support**
  - Built-in multi-mode mapping logic and safe exit mechanism
  - Action recording functionality written to `pnd_adam_dds/logs/retarget_record.txt`
- 🧠 **Unified DDS Message Definitions**
  - Added four message structures: `rt/lowcmd`, `rt/lowstate`, `rt/handcmd`, `rt/handstate`
  - Aligned C++ and Python SDK message interface formats
- 🧩 **System Compatibility Optimization**
  - Support for wired direct connection development mode (static IP `10.10.20.111`)
  - Optimized network auto-discovery mechanism and secure disconnection recovery

---

## 📦 Installation and Setup

### 1️⃣ Environment Dependencies

```bash
sudo apt update
sudo apt install -y libyaml-cpp-dev libspdlog-dev libboost-all-dev libglfw3-dev python3-pip
```

### 2️⃣ Install Cyclone DDS

```bash
git clone https://github.com/eclipse-cyclonedds/cyclonedds.git
cd cyclonedds && git checkout 0.10.2
mkdir build && cd build && cmake .. && make -j8
sudo make install && sudo ldconfig
```

### 3️⃣ Install Python SDK

```bash
git clone https://github.com/pndbotics/pnd_sdk_python.git
cd pnd_sdk_python
sudo pip3 install -e .
```

### 4️⃣ Install Simulation Environment

```bash
pip3 install mujoco pygame
```

---

## ⚙️ Startup and Execution

### Real Robot Mode

```bash
# Start the main robot process
ssh pnd-humanoid@192.168.41.xx
cd ~/Documents/adam_u_deploy_dds/pnd_service_dds
sudo ./run.sh

# Start the Adam-U control service
cd ~/Documents/adam_u_deploy_dds/pnd_adam_dds
sh run.sh
```

### Simulation Mode

```bash
git clone https://github.com/pndbotics/pnd_mujoco.git
python3 pnd_mujoco/simulate_python/pnd_mujoco.py
```

## 📘 Structure and Protocol Description

- **Message Topics**
  - `rt/lowcmd`: Sends desired joint data
  - `rt/lowstate`: Subscribes to joint state
  - `rt/handcmd`: Sends hand control commands
  - `rt/handstate`: Subscribes to hand state
- **Number of Actuators**
  - Body: 19 joints
  - Hands: 12 degrees of freedom (6 for each hand)
- **Control Parameters**
  - Supports PD/PID control models and Sim-to-Real parameter mapping

---

## 🧩 Example File Structure

```
pnd_adam_u_sdk/
├── docs/
│   ├── wiki/                      # Deployment documentation
│   ├── img/                       # Image resources
├── src/
│   ├── pnd_service_dds/               # Main robot DDS service
│   ├── pnd_adam_dds/               # Adam-U control node
├── scripts/
│   ├── install_deps.sh            # One-click dependency installation
│   ├── run_robot.sh               # Startup script
├── python/
│   ├── sdk/                       # Python SDK interface
└── README.md
```

---

## 🔗 Related Repositories

| Module               | Repository Link                                                         |
| -------------------- | ----------------------------------------------------------------------- |
| 💡 SDK (Python)      | [pndbotics/pnd_sdk_python](https://github.com/pndbotics/pnd_sdk_python) |
| 🎮 Simulation Module | [pndbotics/pnd_mujoco](https://github.com/pndbotics/pnd_mujoco)         |
| 🤖 Deployment Module | [pndbotics/pnd_adam_u_sdk](https://github.com/pndbotics/pnd_adam_u_sdk) |

---

## 📜 Version Log

| Version | Date       | Updates                                                                              |
| ------- | ---------- | ------------------------------------------------------------------------------------ |
| v1.2.1  | 2026-01-28 | Update default adam type                                                             |
| v1.2.0  | 2026-01-19 | Align with Adam                                                                      |
| v1.0.5  | 2025-12-30 | Update hand type                                                                     |
| v1.0.4  | 2025-12-10 | Fix hand-related errors                                                              |
| v1.0.3  | 2025-11-20 | Fix start hand position bug                                                          |
| v1.0.2  | 2025-11-20 | Update user receive data                                                             |
| v1.0.1  | 2025-11-19 | Fix stop2zero bug                                                                    |
| v1.0.0  | 2025-11-11 | First official release, supports integrated Adam-U deployment and simulation control |
| v0.9.0  | 2025-10-15 | Beta version, added DDS message structure and Python SDK bindings                    |

---

## 🧠 Future Roadmap

- ✅ Support Isaac Gym high-speed simulation interface
- 🚧 Integrate ROS 2 DDS bridge (ROS 2 Humble)
- 🚀 Add finger action learning (retargeting replay)
- 📡 Support remote Web control API

## Reference Documentation

- [PND Adam U SDK](https://wiki.pndbotics.com/half_robot/pnd_adam_u_sdk/)
