"""
  Pico W                     Reed Switch         Pico W
  ------                     ---------------     ------
  3v3 (Physical pin #36) --> Normally Closed --> GPIO Pin #22 (Physical Pin #29)
"""
import time

import network
import urequests as requests
import utils
from machine import Pin
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
    utils.time_sync()

    utils.tprint("MAIN: Handle any old traceback logs")
    utils.purge_old_log_files()
    #
    utils.tprint("MAIN: Configure OTA.")
    ota_updater = OTAUpdater(secrets.GITHUB_USER,
                             secrets.GITHUB_TOKEN,
                             OTA_UPDATE_GITHUB_REPOS,
                             update_interval_minutes=1440,
                             update_on_initialization=True,
                             debug=DEBUG)

    reed_switch = Pin(CONTACT_PIN, Pin.IN, Pin.PULL_DOWN)

    utils.tprint("MAIN: Starting event loop")
    while True:
        door_is_closed = reed_switch.value()

        if not door_is_closed:
            utils.tprint("MAIN: Door opened.")
            resp = requests.post(secrets.REST_API_URL, headers=REQUEST_HEADER)
            resp.close()
            time.sleep(DOOR_OPEN_PAUSE_TIMER)  # 10 min
        else:
            ota_updater.updated()

        if not wlan.isconnected():
            utils.tprint("MAIN: Restart network connection.")
            utils.wifi_connect(wlan, secrets.SSID, secrets.PASSWORD)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        utils.handle_exception(exc, secrets.HOSTNAME, secrets.REST_CRASH_NOTIFY_URL)
