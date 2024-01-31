#!/usr/bin/env python3

"""
Growatt Shelly Switcher

This program periodically checks the battery state of a Growatt solar power plant. Depending on the current charge
level of the battery, a load that is connected to a shelly relay is switched on for a certain amount of time.
The timer runs independently on the shelly relay and is refreshed on each check cycle of the program, if needed.

The state of the solar power plant is requested by using the cloud based Growatt Server API.
To communicate with the shelly relay, the shelly HTTP API is used.

The software has a night-time mode - during configurable hours of the day, the load is always switched off.

Configuration:
    Configuration is loaded from two files: ``conf/config.ini`` and ``conf/logging.ini``.
    Please check the provided examples for further details.
"""

import time
import datetime
import json
import logging
import logging.config
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


def growatt_login(growattApi: growattServer.GrowattApi):
    """
    Logs in to Growatt Server. Retries the login on failure since sometimes the Growatt Server throws random
    HTTP 403 or 405s.

    Args:
        growattApi: Growatt API object.

    Returns:
        str: User ID of the logged in account.
    """
    logger.debug('Logging in to Growatt Server at \'%s\' with user agent \'%s\'',
                 growattApi.server_url, growattApi.agent_identifier)
    for i in range(1, growatt_login_tries + 1):
        try:
            login_response = growattApi.login(growatt_username, growatt_password)
        except Exception as e:
            if i == growatt_login_tries:
                logger.error('Login to Growatt Server failed - retries exhausted (retry %s/%s): %s',
                             i, growatt_login_tries, e)
                raise e
            else:
                logger.warning('Login to Growatt Server failed - retrying in %ss (retry %s/%s): %s',
                               growatt_login_retry_wait_seconds, i, growatt_login_tries, e)
                time.sleep(growatt_login_retry_wait_seconds)
                continue
    if not login_response['success']:
        logger.error('Login to Growatt Server failed: %s', login_response['error'])
        raise Exception('Growatt Server login failed')
    username = login_response['user']['accountName']
    userid = login_response['user']['id']
    logger.info('Logged in to Growatt Server with user \'%s\' (ID \'%s\')', username, userid)
    return userid


def update_state(growattApi: growattServer.GrowattApi, growatt_userid: str):
    """
    Gets the solar plant battery state.
    Then checks the current state of the shelly relay and updates it appropriately.

    Args:
        growattApi: Object to interact with the Growatt API. Must be logged in before.
        growatt_userid: User ID of the logged in user.
    """
    # get plant and inverter IDs
    growatt_plant_list = growattApi.plant_list(growatt_userid)
    growatt_plant_id = growatt_plant_list['data'][0]['plantId']
    growatt_plant_name = growatt_plant_list['data'][0]['plantName']
    growatt_inverter_id = growattApi.device_list(growatt_plant_id)[0]['deviceSn']
    logger.debug('Using plant \'%s\' with ID \'%s\' and inverter with ID \'%s\'',
                 growatt_plant_name, growatt_plant_id, growatt_inverter_id)

    # get battery status
    inverter_system_status = growattApi.mix_system_status(growatt_inverter_id, growatt_plant_id)
    logger.debug('Current inverter status: %s', str(inverter_system_status))
    battery_capacity_percent = int(inverter_system_status['SOC'])
    logger.info('Current battery percentage: %s%%', str(battery_capacity_percent))

    # print load status to debug log
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

    # print load status to debug log
    load_status = get_load_state()
    logger.debug('Current load status: %s', str(load_status))


def get_load_state():
    """
    Gets the current state of the shelly relay.

    Returns:
        dict: Parsed JSON response from the shelly device containing the relay state.
    """
    request_url = shelly_baseurl + '/relay/0'
    try:
        r = requests.get(request_url, auth=HTTPBasicAuth(shelly_username, shelly_password))
        r.raise_for_status()
    except Exception as e:
        logger.error('Getting load status failed!')
        raise e
    status = json.loads(r.content)
    return status


def set_load_state(target_state: bool, timer_sec: int = None):
    """
    Sets the state of the shelly relay.

    Args:
        target_state: The target state of the relay. Relay is on if True.
        timer_sec: An optional timer to send to the shelly, given in seconds.
    """
    if target_state and timer_sec is not None:
        request_url = shelly_baseurl + '/relay/0?turn=on&timer=' + str(timer_sec)
    elif target_state:
        request_url = shelly_baseurl + '/relay/0?turn=on'
    else:
        request_url = shelly_baseurl + '/relay/0?turn=off'
    try:
        r = requests.get(request_url, auth=HTTPBasicAuth(shelly_username, shelly_password))
        r.raise_for_status()
    except Exception as e:
        logger.error('Setting load status failed!')
        raise e


def is_time_between(start_time: datetime.time, end_time: datetime.time):
    """
    Determines if the current time is between two given datetimes

    Args:
        start_time: The boundary start time to compare against.
        end_time: The boundary end time to compare against.

    Returns:
        bool: True if current time is between the boundaries.
    """
    now = datetime.datetime.now().time()
    if start_time < end_time:
        return now >= start_time and now <= end_time
    else:  # crosses midnight
        return now >= start_time or now <= end_time


def main():
    # initially log in to growatt server
    growattApi = growattServer.GrowattApi(False, requests.utils.default_headers()['User-Agent'])
    growattApi.server_url = growatt_server_url
    growatt_userid = growatt_login(growattApi)
    # run periodic update job
    while True:
        if is_time_between(datetime.time(night_start_hour, night_start_minute),
                           datetime.time(night_end_hour, night_end_minute)):
            logger.info('Nighttime mode is enabled between %02d:%02d and %02d:%02d - ensuring the load is OFF',
                        night_start_hour, night_start_minute, night_end_hour, night_end_minute)
            set_load_state(False)
        else:
            logger.info('Starting update job')
            try:
                update_state(growattApi, growatt_userid)
                logger.info('Update job finished successfully')
            except json.decoder.JSONDecodeError:
                logger.warning('Update job failed, could not decode response from server. '
                               'Assuming expired session, trying to renew...')
                try:
                    growatt_userid = growatt_login(growattApi)
                    update_state(growattApi, growatt_userid)
                    logger.info('Update job finished successfully')
                except Exception as e:
                    logger.exception('Renewing expired session failed, caught exception: %s', e)
            except Exception as e:
                logger.exception('Update job failed, caught exception: %s', e)
        logger.info('Sleeping for %s seconds...', check_interval_seconds)
        time.sleep(check_interval_seconds)


if __name__ == '__main__':
    main()
