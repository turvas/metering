#!/usr/bin/python3
# used to read energy meters and save consumption
# Copyright by turvas
#
import datetime
import os
import time
import random
# modules below might need manual install everywhere
import schedule
# modules below might need manual install only in Windows
from gpiozero import Device, Button
# for Win testing
from gpiozero.pins.mock import MockFactory  # https://gpiozero.readthedocs.io/en/stable/api_pins.html#mock-pins
# shared variables and functions
import shared_energy_management as sem

# gpioPin is used as index in counters, thus has to be unique
meters = [
    {'name': 'boiler', 'gpioPin': 2},
    {'name': 'katel', 'gpioPin': 3}
]

counters = []  # list 32
buttons = []  # = meters


def init():
    sem.set_dir_path()
    sem.init_db()
    if os.name != 'posix':  # windows
        print("Init MockPins, impulse generation")
        Device.pin_factory = MockFactory()  # Set the default pin factory to a mock factory
        schedule.every(10).seconds.do(simulate_impulses)  # generate some metering impulses


def light_pulse_seen_1(device_calling):
    """callback from Button"""
    global counters
    counters[device_calling.pin.number] += 1


def handle_time_event():
    """called by scheduler every min"""
    global counters
    insert_row()  # log state
    for meter in meters:
        gpio_pin = meter['gpioPin']
        counters[gpio_pin] = 0


def insert_row():
    """writes impulse counts to files, named by metered objects"""
    dt = datetime.datetime.now()
    dtf = dt.strftime("%x %X")
    ym = dt.strftime("%Y-%m")

    for meter in meters:
        gpio_pin = meter['gpioPin']
        val = counters[gpio_pin]
        sem.insert_row_db(gpio_pin, val)

        txt = dtf + " " + str(val) + "\n"
        print(txt)
        fn = sem.dirpath + "pulses-" + meter['name'] + "-" + str(ym) + ".txt"
        with open(fn, "a") as f:
            f.write(txt)


def init_counters():
    """initializes list and Buttons"""
    global counters
    for i in range(32):  # create array of 32 elements
        counters.append(0)
    for meter in meters:
        gpio_pin = meter['gpioPin']
        button = Button(gpio_pin)  # defaults pullup resistor True
        button.when_pressed = light_pulse_seen_1  # same callback for all
        buttons.append(button)


def simulate_impulse(pin=3):
    """simulate/generate 1 impulse on gpio-pin"""
    btn_pin = Device.pin_factory.pin(pin)
    btn_pin.drive_low()
    time.sleep(0.1)
    btn_pin.drive_high()
    time.sleep(0.1)


def simulate_impulses(pin=3, maxcount=9):
    """called by scheduler, random count of pulses with maxcount, defaulting 9"""
    nr = random.randint(0, maxcount)
    for i in range(nr):
        simulate_impulse(pin)

def cleanup():
    sem.close_db()

def main():
    init()
    init_counters()
    handle_time_event()
    schedule.every(1).minutes.do(handle_time_event)

    killer = sem.GracefulKiller()
    killer.cleanup_func = cleanup
    while not killer.kill_now:
        schedule.run_pending()
        time.sleep(1)  # seconds


if __name__ == '__main__':
    main()
