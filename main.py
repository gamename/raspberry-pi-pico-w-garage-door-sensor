"""
  Pico W                     Reed Switch         Pico W
  ------                     ---------------     ------
  3v3 (Physical pin #36) --> Normally Closed --> GPIO Pin #22 (Physical Pin #29)
"""
import json
import time

import network
import ntptime
import urequests as requests
import utils
from machine import Pin, reset
from ota import OTAUpdater

import secrets

#
# enable/disable debug
DEBUG = False

#
# The reed switch sensor
CONTACT_PIN = 22  # GPIO pin #22, physical pin #29

#
# A common request header for our POSTs
REQUEST_HEADER = {'content-type': 'application/json'}

#
# Files we want to update over-the-air (OTA)
OTA_UPDATE_GITHUB_REPOS = {
    "gamename/raspberry-pi-pico-w-garage-door-sensor": ["boot.py", "main.py"],
    "gamename/micropython-over-the-air-utility": ["ota.py"],
    "gamename/micropython-gamename-utilities": ["utils.py", "cleanup_logs.py"]
}

#
# How long should we pause before rechecking status?
DOOR_OPEN_PAUSE_TIMER = 600  # seconds (10 min)


def main():
    #
    # Hostname can be no more than 15 chars (boo)
    network.hostname(secrets.HOSTNAME)
    #
    # Turn OFF the access point interface
    ap_if = network.WLAN(network.AP_IF)
    ap_if.active(False)
    #
    # Turn ON and connect the station interface
    wlan = network.WLAN(network.STA_IF)
    utils.wifi_connect(wlan, secrets.SSID, secrets.PASSWORD)
    #
    # Sync system time with NTP
    print("MAIN: Sync system time with NTP")
    try:
        ntptime.settime()
        utils.debug_print("MAIN: System time set successfully.")
    except Exception as e:
        utils.tprint(f"MAIN: Error setting system time: {e}")
        time.sleep(0.5)
        reset()

    utils.purge_old_log_files()

    utils.tprint("MAIN: Configure OTA updates.")
    ota_updater = OTAUpdater(secrets.GITHUB_USER, secrets.GITHUB_TOKEN, OTA_UPDATE_GITHUB_REPOS, debug=DEBUG)

    utils.tprint("MAIN: Check for OTA updates")
    if ota_updater.updated():
        utils.tprint("MAIN: OTA updates added. Resetting system.")
        time.sleep(1)
        reset()
    else:
        utils.tprint("MAIN: No OTA updates found.")

    reed_switch = Pin(CONTACT_PIN, Pin.IN, Pin.PULL_DOWN)

    ota_timer = time.time()

    utils.tprint("MAIN: Starting event loop")
    while True:
        door_is_closed = reed_switch.value()

        if not door_is_closed:
            utils.tprint("MAIN: Door opened.")
            resp = requests.post(secrets.REST_API_URL, headers=REQUEST_HEADER)
            resp.close()
            time.sleep(DOOR_OPEN_PAUSE_TIMER)  # 10 min
        elif utils.ota_update_interval_exceeded(ota_timer):
            utils.tprint("MAIN: Checking for OTA updates.")
            if ota_updater.updated():
                utils.tprint("MAIN: Found OTA updates. Resetting system.")
                time.sleep(0.5)
                reset()
            else:
                utils.tprint("MAIN: No OTA updates. Reset timer instead.")
                ota_timer = time.time()

        if not wlan.isconnected():
            utils.tprint("MAIN: Restart network connection.")
            utils.wifi_connect(wlan, secrets.SSID, secrets.PASSWORD)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("-C R A S H-")
        tb_msg = utils.log_traceback(exc)
        if utils.max_reset_attempts_exceeded():
            # We cannot send every traceback since that would be a problem
            # in a crash loop. But we can send the last traceback. It will
            # probably be a good clue.
            traceback_data = {
                "machine": secrets.HOSTNAME,
                "traceback": tb_msg
            }
            resp = requests.post(secrets.REST_CRASH_NOTIFY_URL, data=json.dumps(traceback_data), headers=REQUEST_HEADER)
            resp.close()
            utils.flash_led(3000, 3)  # slow flashing for about 2.5 hours
        else:
            reset()
