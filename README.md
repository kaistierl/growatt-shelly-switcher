# ☀️ Solar Heating Controller

## 🔌 Overview

**Solar Heating Controller** is a lightweight Python-based automation tool that intelligently controls a heating load (or any electrical device) based on the battery charge level of a **Growatt solar power system**. It uses a **Shelly smart relay** to switch the load and ensures safe, efficient usage of excess solar energy.

This is especially useful for setups where you'd like to run a load (like a heater or appliance) **only when sufficient solar energy is available** — without manual monitoring.

---

## 🧰 Hardware Requirements

- **Inverter:** Growatt SPH 8000TL3 BH-UP (connected via Growatt ShineWifi-X). Other Growatt inverters might work as well but I did not test this.
- **Shelly relay or plug** to switch the load  
  - For Gen1 devices: Basic authentication  
  - For Gen2+ devices: Digest authentication  
  - Configurable via `auth_type` in `config.ini`
- **Load:** Generic heating element (connected through an external load contactor)
- **Controller:** Raspberry Pi Zero W (or similar) to run the software

---

## 🧠 Features

- Retrieves the **battery charge level** from the Growatt cloud API
- Switches a **Shelly smart relay** ON/OFF via its HTTP API
- Turns **ON** the load when battery percentage is **equal to or above** a configurable threshold
- Turns **OFF** the load when the battery drops **below or equal** to a separate threshold
- Includes **night-time mode** to automatically disable the load during certain hours
- Implements a **fail-safe mechanism**:  
  - A one-shot timer is sent to the Shelly device. This ensures the load turns off automatically in case of system crash or network issues

---

## ⚙️ Configuration

All runtime settings are configurable via the following files:
- `conf/config.ini` – Connection details, thresholds, and scheduling
- `conf/logging.ini` – Logging format and output configuration

### 📄 Example `conf/config.ini`

```ini
[growatt]
server_url = https://openapi.growatt.com/
; Alternative API endpoint
;server_url = https://server.growatt.com/
username = user
password = secret123$
inverter_sn = TPXXXXXXXX
login_tries = 3
login_retry_wait_seconds = 10

[shelly]
baseurl = http://192.168.x.x
; 'basic' for Gen1 or 'digest' for Gen2+ Shelly devices
auth_type = digest
username = admin
password = secret123$
turnon_seconds = 1800

[main]
check_interval_seconds = 300
battery_threshold_on_percent = 90
battery_threshold_off_percent = 60
night_start_hour = 22
night_start_minute = 00
night_end_hour = 5
night_end_minute = 00
```

## 📦 Installation

Requires Python 3.7 or newer. Install dependencies with:

```bash
pip install -r requirements.txt
```

Run the script with:

```bash
python main.py
```