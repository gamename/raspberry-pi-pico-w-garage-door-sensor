"""


Pico W 3v3/Physical pin #36 ----> reed switch (normally open) ----> Pico W GPIO Pin #22/Physical Pin #29



"""
import gc
import os
import sys
import time

import network
import ntptime
import uio
import urequests as requests
import utime
from machine import Pin, reset
from ota import OTAUpdater

import secrets

CONTACT_PIN = 22  # GPIO pin #22, physical pin #29

#
# how long between door state rechecks?
DOOR_RECHECK_PAUSE_TIMER = 600  # seconds (10 min)

#
# Over-the-air (OTA) Updates
#
# How often should we check for updates?
OTA_UPDATE_GITHUB_CHECK_INTERVAL = 600  # seconds (10 min)
#
# This is a dictionary of repos and their files we will be auto-updating
OTA_UPDATE_GITHUB_REPOS = {
    "gamename/raspberry-pi-pico-w-garage-door-sensor": ["boot.py", "main.py"],
    "gamename/micropython-over-the-air-utility": ["ota.py"]
}


def current_time_to_string():
    """
    Convert the current time to a human-readable string

    :return: timestamp string
    :rtype: str
    """
    current_time = utime.localtime()
    year, month, day_of_month, hour, minute, second, *_ = current_time
    return f'{year}-{month}-{day_of_month}-{hour}-{minute}-{second}'


def log_traceback(exception):
    """
    Keep a log of the latest traceback

    :param exception: An exception intercepted in a try/except statement
    :type exception: exception
    :return: Nothing
    """
    traceback_stream = uio.StringIO()
    sys.print_exception(exception, traceback_stream)
    traceback_file = current_time_to_string() + '-' + 'traceback.log'
    with open(traceback_file, 'w') as f:
        f.write(traceback_stream.getvalue())


def flash_led(count=100, interval=0.25):
    """
    Flash on-board LED

    :param: How many times to flash
    :param: Interval between flashes

    :return: Nothing
    """
    led = Pin("LED", Pin.OUT)
    for _ in range(count):
        led.toggle()
        time.sleep(interval)
    led.off()


def wifi_connect(wlan, ssid, password, connection_attempts=10, sleep_seconds_interval=3):
    """
    Start a Wi-Fi connection

    :param wlan: A network handle
    :type wlan: network.WLAN
    :param ssid: Wi-Fi SSID
    :type ssid: str
    :param password: Wi-Fi password
    :type password: str
    :param connection_attempts: How many times should we attempt to connect?
    :type connection_attempts: int
    :param sleep_seconds_interval: Sleep time between attempts
    :type sleep_seconds_interval: int
    :return: Nothing
    :rtype: None
    """

    led = Pin("LED", Pin.OUT)
    led.off()
    print("WIFI: Attempting network connection")
    wlan.active(True)
    time.sleep(sleep_seconds_interval)
    counter = 0
    wlan.connect(ssid, password)
    while not wlan.isconnected():
        print(f'WIFI: Attempt: {counter}')
        time.sleep(sleep_seconds_interval)
        counter += 1
        if counter > connection_attempts:
            print("WIFI: Network connection attempts exceeded. Restarting")
            time.sleep(1)
            reset()
    led.on()
    print("WIFI: Successfully connected to network")


def max_reset_attempts_exceeded(max_exception_resets=10):
    """
    Determine when to stop trying to reset the system when exceptions are
    encountered. Each exception will create a traceback log file.  When there
    are too many logs, we give up trying to reset the system.  Prevents an
    infinite crash-reset-crash loop.

    :param max_exception_resets: How many times do we crash before we give up?
    :type max_exception_resets: int
    :return: True if we should stop resetting, False otherwise
    :rtype: bool
    """
    log_file_count = 0
    files = os.listdir()
    for file in files:
        if file.endswith(".log"):
            log_file_count += 1
    return bool(log_file_count > max_exception_resets)


def ota_update_check(updater):
    #
    # The update process is memory intensive, so make sure
    # we have all the resources we need.
    gc.collect()

    if updater.updated():
        print("CHECK: Restarting device after update")
        time.sleep(1)  # Gives the system time to print the above msg
        reset()


def main():
    #
    # Set up a timer to force reboot on system hang
    network.hostname(secrets.HOSTNAME)
    #
    # Turn OFF the access point interface
    ap_if = network.WLAN(network.AP_IF)
    ap_if.active(False)
    #
    # Turn ON and connect the station interface
    wlan = network.WLAN(network.STA_IF)
    wifi_connect(wlan, secrets.SSID, secrets.PASSWORD)
    #
    # Sync system time with NTP
    ntptime.settime()
    reed_switch = Pin(CONTACT_PIN, Pin.IN, Pin.PULL_DOWN)
    ota_updater = OTAUpdater(secrets.GITHUB_USER,
                             secrets.GITHUB_TOKEN,
                             OTA_UPDATE_GITHUB_REPOS)

    ota_update_check(ota_updater)

    ota_timer = time.time()
    print("MAIN: Starting event loop")
    while True:
        garage_door_closed = reed_switch.value()

        if not garage_door_closed:
            print("MAIN: Door opened.")
            requests.post(secrets.REST_API_URL, headers={'content-type': 'application/json'})
            time.sleep(DOOR_RECHECK_PAUSE_TIMER)

        if not wlan.isconnected():
            print("MAIN: Restart network connection.")
            wifi_connect(wlan, secrets.SSID, secrets.PASSWORD)

        ota_elapsed = int(time.time() - ota_timer)
        if ota_elapsed > OTA_UPDATE_GITHUB_CHECK_INTERVAL and garage_door_closed:
            ota_update_check(ota_updater)
            ota_timer = time.time()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log_traceback(exc)
        #
        # This is a gamble. If the crash happens in the wrong place,
        # the below request is a waste of time. But... its worth a try.
        requests.post(secrets.REST_CRASH_NOTIFY_URL,
                      data=secrets.HOSTNAME,
                      headers={'content-type': 'application/json'})
        flash_led(1000, 3)  # slow flashing
