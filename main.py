"""
  Pico W                     Reed Switch         Pico W
  ------                     ---------------     ------
  3v3 (Physical pin #36) --> Normally Closed --> GPIO Pin #22 (Physical Pin #29)
"""
import json
import os
import sys
import time

import network
import ntptime
import uio
import urequests as requests
from machine import Pin, reset, RTC

import secrets

CONTACT_PIN = 22  # GPIO pin #22, physical pin #29

#
# Max amount of time we will keep a tracelog (in hours)
TRACE_LOG_MAX_KEEP_TIME = 48

#
# Offset from UTC for CST (Central Standard Time)
CST_OFFSET_SECONDS = -6 * 3600  # UTC-6

#
# Offset from UTC for CDT (Central Daylight Time)
CDT_OFFSET_SECONDS = -5 * 3600  # UTC-5

#
# A common request header for our POSTs
REQUEST_HEADER = {'content-type': 'application/json'}


def get_now():
    """
    Get the local time now

    :return: timestamp
    :rtype: time
    """
    current_offset_seconds = CDT_OFFSET_SECONDS if on_us_dst() else CST_OFFSET_SECONDS
    return time.gmtime(time.time() + current_offset_seconds)


def tprint(message):
    """
    Print with a pre-pended timestamp

    :param message: The message to print
    :type message: string
    :return: Nothing
    :rtype: None
    """
    current_time = get_now()
    timestamp = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
        current_time[0], current_time[1], current_time[2],
        current_time[3], current_time[4], current_time[5]
    )
    print("[{}] {}".format(timestamp, message))


def current_local_time_to_string():
    """
    Convert the current time to a human-readable string

    :return: timestamp string
    :rtype: str
    """
    current_time = get_now()
    year, month, day_of_month, hour, minute, second, *_ = current_time
    return f'{year}-{month}-{day_of_month}-{hour}-{minute}-{second}'


def log_traceback(exception):
    """
    Keep a log of the latest traceback

    :param exception: An exception intercepted in a try/except statement
    :type exception: exception
    :return:  formatted string
    """
    traceback_stream = uio.StringIO()
    sys.print_exception(exception, traceback_stream)
    traceback_file = current_local_time_to_string() + '-' + 'traceback.log'
    output = traceback_stream.getvalue()
    print(output)
    time.sleep(0.5)
    with open(traceback_file, 'w') as f:
        f.write(output)
    return output


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


def max_reset_attempts_exceeded(max_exception_resets=3):
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


def on_us_dst():
    """
    Are we on US Daylight Savings Time (DST)?

    :return: True/False
    :rtype: bool
    """
    on_dst = False
    # Get the current month and day
    current_month = RTC().datetime()[1]  # 1-based month
    current_day = RTC().datetime()[2]

    # DST usually starts in March (month 3) and ends in November (month 11)
    if 3 < current_month < 11:
        on_dst = True
    elif current_month == 3:
        # DST starts on the second Sunday of March
        second_sunday = 14 - (RTC().datetime()[6] + 1 - current_day) % 7
        if current_day > second_sunday:
            on_dst = True
    elif current_month == 11:
        # DST ends on the first Sunday of November
        first_sunday = 7 - (RTC().datetime()[6] + 1 - current_day) % 7
        if current_day <= first_sunday:
            on_dst = True

    return on_dst

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
    wifi_connect(wlan, secrets.SSID, secrets.PASSWORD)
    #
    # Sync system time with NTP
    ntptime.settime()
    reed_switch = Pin(CONTACT_PIN, Pin.IN, Pin.PULL_DOWN)

    print("MAIN: Starting event loop")
    while True:
        garage_door_closed = reed_switch.value()

        if not garage_door_closed:
            print("MAIN: Door opened.")
            resp = requests.post(secrets.REST_API_URL, headers=REQUEST_HEADER)
            resp.close()
            time.sleep(600)  # 10 min

        if not wlan.isconnected():
            print("MAIN: Restart network connection.")
            wifi_connect(wlan, secrets.SSID, secrets.PASSWORD)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("-C R A S H-")
        tb_msg = log_traceback(exc)
        if max_reset_attempts_exceeded():
            # We cannot send every traceback since that would be a problem
            # in a crash loop. But we can send the last traceback. It will
            # probably be a good clue.
            traceback_data = {
                "machine": secrets.HOSTNAME,
                "traceback": tb_msg
            }
            resp = requests.post(secrets.REST_CRASH_NOTIFY_URL, data=json.dumps(traceback_data), headers=REQUEST_HEADER)
            resp.close()
            flash_led(3000, 3)  # slow flashing for about 2.5 hours
        else:
            reset()
