#!/usr/bin/python

import datetime
import os
import time
# modules below might need manual install
import schedule
from gpiozero import Device, Button
# for Win testing
from gpiozero.pins.mock import MockFactory # https://gpiozero.readthedocs.io/en/stable/api_pins.html#mock-pins
import random

# gpioPin is used as index in counters, thus has to be unique
meters = [
    {'name': 'boiler', 'gpioPin': 2},
    {'name': 'katel', 'gpioPin': 3}
]

counters = []   # list 32
buttons = []    # = meters
dirpath = ""

# sets OS dependent directory
def setDirPath():
    global dirpath
    if os.name == 'posix':
        dirpath = "/var/metering/"
    else:       # windows
        Device.pin_factory = MockFactory()  # Set the default pin factory to a mock factory
        schedule.every(10).seconds.do(simulateImpulses) # generate some metering impulses
    return dirpath

# callback from Button
def light_pulse_seen_1(deviceCalling):
   global counters
   counters[deviceCalling.pin.number] += 1

# called by scheduler every min
def handle_time_event():
    global counters
    insert_row()                # log state
    for meter in meters:
        gpioPin = meter['gpioPin']
        counters[gpioPin] = 0

# writes impule counts to files, named by metered objects
def insert_row():

    dt = datetime.datetime.now()
    dtf=dt.strftime("%x %X")
    ym = dt.strftime("%Y-%m")

    for meter in meters:
        gpioPin = meter['gpioPin']
        val = counters[ gpioPin ]
        txt = dtf + " " + str(val) + "\n"
        print(txt)
        fn = dirpath + "pulses-" + meter['name'] + "-" + str(ym) + ".txt"
        with open(fn, "a") as f:
            f.write(txt)

# initializes list and Buttons, todo all pullups for other inputs than 2,3
def initCounters():
    global counters
    for i in range(32):     # create array of 32 elements
        counters.append(0)
    for meter in meters:
        gpioPin = meter['gpioPin']
        button = Button(gpioPin)
        button.when_pressed = light_pulse_seen_1    # same callback for all
        buttons.append(button)

# simulate/generate 1 impulse on gpio-pin
def simulateImpulse(pin=3):

    btn_pin = Device.pin_factory.pin(pin)
    btn_pin.drive_low()
    time.sleep(0.1)
    btn_pin.drive_high()
    time.sleep(0.1)

# called by scheduler, random count of pulses with maxcount, defaulting 9
def simulateImpulses(pin=2, maxcount=9):
    nr = random.randint(0, maxcount)
    for i in range(nr):
        simulateImpulse(pin)

# MAIN

def main():
    setDirPath()
    initCounters()
    handle_time_event()
    schedule.every(1).minutes.do(handle_time_event)

    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == '__main__':
    main()
