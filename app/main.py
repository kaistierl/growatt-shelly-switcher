import time
import datetime
import json
import logging
from logging.config import fileConfig
import configparser
import growattServer
import requests
from requests.auth import HTTPBasicAuth

# initialize logging
logging.config.fileConfig('conf/logging.ini')
logger = logging.getLogger()
logger.info('Welcome! Initializing...')

# read config
config = configparser.ConfigParser()
config.read('conf/config.ini')
growatt_server_url = str(config['growatt']['server_url'])
growatt_username = str(config['growatt']['username'])
growatt_password = str(config['growatt']['password'])
growatt_login_tries = int(config['growatt']['login_tries'])
growatt_login_retry_wait_seconds = int(config['growatt']['login_retry_wait_seconds'])
shelly_baseurl = str(config['shelly']['baseurl'])
shelly_username = str(config['shelly']['username'])
shelly_password = str(config['shelly']['password'])
shelly_turnon_seconds = int(config['shelly']['turnon_seconds'])
battery_threshold_on = int(config['main']['battery_threshold_on_percent'])
battery_threshold_off = int(config['main']['battery_threshold_off_percent'])
check_interval_seconds = int(config['main']['check_interval_seconds'])
night_start_hour = int(config['main']['night_start_hour'])
night_start_minute = int(config['main']['night_start_minute'])
night_end_hour = int(config['main']['night_end_hour'])
night_end_minute = int(config['main']['night_end_minute'])

# update function
def update_state():
  # login to growatt
  growattApi = growattServer.GrowattApi(False, requests.utils.default_headers()['User-Agent'])
  growattApi.server_url = growatt_server_url
  logger.debug('Logging in to Growatt Server at \'%s\' with user agent \'%s\'',
               growattApi.server_url, growattApi.agent_identifier)
  for i in range(1,growatt_login_tries + 1):
    try:
      login_response = growattApi.login(growatt_username, growatt_password)
    except Exception as e:
      if i == growatt_login_tries:
        logger.error("Login to Growatt Server failed - retries exhausted (retry %s/%s): %s",
                     i, growatt_login_tries, e)
        raise 
      else:
        logger.warning("Login to Growatt Server failed - retrying in %ss (retry %s/%s): %s", 
                       growatt_login_retry_wait_seconds, i, growatt_login_tries, e)
        time.sleep(growatt_login_retry_wait_seconds)
        continue
  if not login_response['success']:
    logger.error('Login to Growatt Server failed: %s', login_response['error'])
    raise Exception("Growatt Server login failed")
  login_username = login_response['user']['accountName']
  logger.info('Logged in to Growatt Server with user \'%s\'', login_username)

  # get plant and inverter IDs
  growatt_plant_id = login_response['data'][0]['plantId']
  growatt_plant_name = login_response['data'][0]['plantName']
  growatt_inverter_id = growattApi.device_list(growatt_plant_id)[0]['deviceSn']
  logger.info('Using plant \'%s\' with ID \'%s\' and inverter with ID \'%s\'',
               growatt_plant_name, growatt_plant_id, growatt_inverter_id)

  # get battery status
  inverter_system_status = growattApi.mix_system_status(growatt_inverter_id, growatt_plant_id)
  logger.debug('Current inverter status: %s', str(inverter_system_status))
  battery_capacity_percent = int(inverter_system_status['SOC'])
  logger.info('Current battery percentage: %s%%', str(battery_capacity_percent))
  
  # get load status
  load_status = get_load_state()
  logger.debug('Current load status: %s', str(load_status))
  
  # check battery status and set appropriate target state of the load
  load_ison = bool(load_status['ison'])
  if (battery_capacity_percent >= battery_threshold_on):
    logger.info('Battery percentage is equal or above threshold of %s%% - Switching ON the load with timer (%ss)',
                str(battery_threshold_on), str(shelly_turnon_seconds))
    set_load_state(True, shelly_turnon_seconds)
  elif (battery_capacity_percent <= battery_threshold_off):
    logger.info('Battery percentage is equal or below threshold of %s%% - Switching OFF the load',
                str(battery_threshold_off))
    set_load_state(False)
  elif load_ison:
    logger.info('Battery percentage is between thresholds of %s%% and %s%% - Load is ON - refreshing timer (%ss)',
                str(battery_threshold_off), str(battery_threshold_on), str(shelly_turnon_seconds))
    set_load_state(True, shelly_turnon_seconds)
  else:
    logger.info('Battery percentage is between thresholds of %s%% and %s%% - Load is OFF - doing nothing',
                str(battery_threshold_off), str(battery_threshold_on))

  # get load status
  load_status = get_load_state()
  logger.debug('Current load status: %s', str(load_status))

# function to get the current state of the load
def get_load_state():
  request_url = shelly_baseurl + "/relay/0"
  try:
    r = requests.get(request_url, auth=HTTPBasicAuth(shelly_username, shelly_password))
    r.raise_for_status()
  except Exception as e:
    logger.error('Getting load status failed!')
    raise e
  status = json.loads(r.content)
  return status

# function to set the state of the load
def set_load_state(target_state: bool, timer_sec : int = None):
  if target_state and timer_sec != None:
    request_url = shelly_baseurl + "/relay/0?turn=on&timer=" + str(timer_sec)
  elif target_state:
    request_url = shelly_baseurl + "/relay/0?turn=on"
  else:
    request_url = shelly_baseurl + "/relay/0?turn=off"
  try:
    r = requests.get(request_url, auth=HTTPBasicAuth(shelly_username, shelly_password))
    r.raise_for_status()
  except Exception as e:
    logger.error('Setting load status failed!')
    raise e

def is_time_between(start_time, end_time):
  now =  datetime.datetime.now().time()
  if start_time < end_time:
    return now >= start_time and now <= end_time
  else: # crosses midnight
    return now >= start_time or now <= end_time

# main loop
while(True):
  if is_time_between(datetime.time(night_start_hour, night_start_minute),
                     datetime.time(night_end_hour, night_end_minute)):
    logger.info('Nighttime mode is enabled between %02d:%02d and %02d:%02d - ensuring the load is OFF',
                night_start_hour, night_start_minute, night_end_hour, night_end_minute)
    set_load_state(False)
  else:
    logger.info('Starting update job')
    try:
      update_state()
      logger.info('Update job finished successfully')
    except Exception as e:
      logger.exception('Update job failed, caught exception: %s', e)
  logger.info('Sleeping for %s seconds...', check_interval_seconds)
  time.sleep(check_interval_seconds)
