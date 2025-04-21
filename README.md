# ☀️ Solar Heating Controller

## 🔌 Overview

The **Solar Heating Controller** is a lightweight Python-based automation tool that intelligently controls a heating load (or any electrical device) based on the battery charge level of a **Growatt solar power system**. It uses a **Shelly smart relay** to switch the load and ensures safe, efficient usage of excess solar energy.

This is especially useful for setups where you'd like to run a load (like a heater or appliance) **only when sufficient solar energy is available** — without manual monitoring.

## ⚠️ Safety Notice & Disclaimer

### Electrical Safety Warning:
This project involves switching mains voltage electrical loads, which can pose serious risk of electric shock, fire, or equipment damage if not handled properly.
All installation, wiring, and modification of electrical systems must be performed by a qualified electrician in accordance with your local electrical code.

- The author assumes no responsibility or liability for any damage, injury, or loss caused by the use of this software or associated hardware setups.

- Always use an external contactor rated for your specific load when switching high-power devices like electric heaters. The built-in relay of a Shelly device may not be suitable for continuous high current switching on its own.

## 🧰 Hardware Requirements

- **Inverter:** Growatt SPH 8000TL3 BH-UP (via ShineWifi-X)  
  _(Other Growatt models may work but are untested)_
- **Shelly relay or plug** to switch the load  
  - For Gen1 devices: Basic authentication  
  - For Gen2+ devices: Digest authentication  
  - Configurable via `auth_type` in `config.ini`
- **Load:** Generic heating element (connected through an external load contactor)
- **Controller:** Raspberry Pi Zero W (or similar) to run the software

## 🧠 Features

- Retrieves the **battery state of charge** from the Growatt cloud API
- Switches a **Shelly smart relay** using HTTP API commands
  - Turns **ON** the load when battery percentage is **equal to or above** a configurable threshold
  - Turns **OFF** the load when the battery drops **below or equal** to a separate threshold
- Includes **night-time mode** to automatically disable the load during certain hours
- Implements a **fail-safe mechanism**:  
  - A one-shot timer is sent to the Shelly device. This ensures the load turns off automatically in case of system crash or network issues
- Has a configurable retry logic for Growatt server connection issues
- Supports full **systemd service** deployment with Ansible

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

## 📦 Manual Installation

Requires Python 3.7 or newer. Install dependencies with:

```bash
pip install -r requirements.txt
```

Run the script with:

```bash
python3 main.py
```

Or using the included `run.sh` script:

```bash
./run.sh
```

Logs will be printed to stdout and saved as `out.log`.

## 🧪 Ansible Deployment

Ansible scripts are available to fully automate installation and provisioning.

### Example Playbook Usage:

```bash
cd ansible
ansible-playbook -i inventory main.yml
```

Customize variables by editing `ansible/vars.yml` (see `vars.yml.example`).

This will:

- Configure hostname and timezone
- Configure SSH (disabling password authentication)
- Remove the default "pi" user
- Install Tailscale for remote access
- Install system dependencies and Python packages
- Deploy the app to /opt/app
- Configure systemd to run the app as a service
- Enable and start the service

After executing the playbook for the first time, connect the device to tailscale:

```bash
tailscale up
```

Once deployed, the application log can be monitored with:

```bash
journalctl -u growatt-app -f
```

## 📝 License

This project is licensed under the [MIT License](LICENSE).

Feel free to use, modify, and distribute it for personal or commercial purposes. No warranty is provided.