"""
"""
import time

import network
import urequests as requests
from machine import Pin

import secrets

MAX_HOSTNAME_LENGTH = 15  # The API only allows a max of 15 chars (grr)
NETWORK_SLEEP_INTERVAL = 10  # seconds


def set_picow_hostname(name):
    """
    Set the hostname of the Raspberry Pi Pico W

    Args:
        name - a string

    Returns:
        Nothing
    """
    if len(name) > MAX_HOSTNAME_LENGTH:
        # current api only allows a max of 15 chars
        new_name = name[:MAX_HOSTNAME_LENGTH]
    else:
        new_name = name
    network.hostname(new_name)
    return


def connect():
    """
    Connect to Wi-Fi

    Args: None

    Returns:
        True when successful
    """
    led = Pin("LED", Pin.OUT)
    led.off()
    wlan = network.WLAN(network.STA_IF)
    wlan.config(pm=0xa11140)  # turn OFF power save mode
    wlan.active(True)
    time.sleep(NETWORK_SLEEP_INTERVAL)
    while not wlan.isconnected():
        wlan.connect(secrets.SSID, secrets.PASSWORD)
        time.sleep(NETWORK_SLEEP_INTERVAL)
    led.on()
    return True


MINUTES = 10
CONTACT_PIN = 0
PAUSE_MINUTES = 60 * MINUTES
contact_switch = Pin(CONTACT_PIN, Pin.IN, Pin.PULL_UP)

set_picow_hostname('pico-garage')

if connect():
    while True:
        # if connection is broken, the garage door is open
        if not contact_switch.value():
            requests.post(secrets.URL,
                          headers={'content-type': 'application/json'})
            time.sleep(PAUSE_MINUTES)
