# Solar heating controller

## Hardware

- Inverter: Growatt SPH 8000TL3 BH-UP connected to Server via Growatt ShineWifi-X
- Shelly Plug to switch the load, HTTP API enabled
- Load: Generic Heater, connected to shelly plug
- Raspberry Pi Pico to run the python script on
 
## Software

- The software retrieves the current battery capacity from the Growatt server
- The software is able to switch a load using shelly HTTP API
- The software switches the load on when the battey percentage is equal to or above a configurable threshold
- The load is switched off again when the battey percentage drops under or is equal to another threshold
- When the server is not reachable for a certain time frame or the system crashes completely, the load is switched off for safety reasons
  - This is realized by sending a one-shot timer to the shelly with a configurable amount of seconds
- The load is always switched off at nighttime (configurable time frame)

### Configuration

Example `conf/config.ini`:

```ini
[growatt]
username = user
password = secret123$

[shelly]
baseurl = http://192.168.x.x
username = admin
password = secret123$
turnon_seconds = 1800

[main]
check_interval_seconds = 300
battery_threshold_on_percent = 75
battery_threshold_off_percent = 25
night_start_hour = 22
night_start_minute = 00
night_end_hour = 5
night_end_minute = 00
```