"""
This is a simple script to sense if a garage door is open.  If it is open, then
send an AWS REST API request.  The request triggers a Simple Notification Service
message which is sent to my phone.

An alternative to using AWS is "pushover.net" which also can be configured to send
SMS messages to your phone.
"""
import time

import network
import urequests as requests
from machine import Pin

import secrets

CONTACT_PIN = 22  # GPIO pin 22 (physical pin 29)

# How long to sleep between network connection attempts?
NETWORK_SLEEP_INTERVAL = 10  # seconds

# How long to pause before checking for the garage being open?
MINUTES = 10

# Now, calculate the pause minutes
PAUSE_MINUTES = 60 * MINUTES


def connect(hostname):
    """
    Connect to Wi-Fi

    Args: hostname

    Returns:
        True when successful
    """
    led = Pin("LED", Pin.OUT)
    led.off()
    network.hostname(hostname)
    wlan = network.WLAN(network.STA_IF)
    wlan.config(pm=0xa11140)  # turn OFF power save mode
    wlan.active(True)
    time.sleep(NETWORK_SLEEP_INTERVAL)
    while not wlan.isconnected():
        wlan.connect(secrets.SSID, secrets.PASSWORD)
        time.sleep(NETWORK_SLEEP_INTERVAL)
    led.on()
    return True


def main():
    contact_switch = Pin(CONTACT_PIN, Pin.IN, Pin.PULL_DOWN)
    if connect(secrets.HOSTNAME):
        while True:
            # if connection is broken, the garage door is open
            if not contact_switch.value():
                # Tell the REST API so we get a notification
                requests.post(secrets.URL, headers={'content-type': 'application/json'})
                time.sleep(PAUSE_MINUTES)


if __name__ == "__main__":
    main()
