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
import configparser
# shared variables and functions
import shared_energy_management as sem
import paho.mqtt.client as mqtt
mqtt_server = None
mqtt_port = 1883
mqtt_user = 'met_00001'
mqtt_pass = 'testPa55'
log_fn = "measure.log"
conf_fn = "config.env"

# gpioPin is used as index in counters, thus has to be unique
meters = [
    {'name': 'boiler', 'gpioPin': 2},
    {'name': 'katel', 'gpioPin': 3}
]

counters = []  # list 32
buttons = []  # = meters
total_start_time = datetime.datetime.now().isoformat(timespec='seconds')


def init():
    """read configuration file config.env and sets global vars"""
    global mqtt_server, mqtt_port, mqtt_user, mqtt_pass, conf_fn
    sem.set_dir_path()
    sem.init_db()
    for meter in meters:        # update config database
        sem.update_config_db(meter['gpioPin'], meter['name'])
    config = configparser.ConfigParser()
    conf_fn = sem.dirpath + conf_fn             # fix os dependent path
    file_list = config.read(conf_fn)
    if len(file_list) == 0:     # emty list, if failed
        sem.Logger(log_fn).log(" init config failed from: " + conf_fn)
    env = config['DEFAULT']['ENV']
    mqtt_server = config[env]['MQTT_SERVER']    # os.environ.get('MQTT_SERVER', '10.10.10.6')   # os.getenv('MQTT_SERVER')
    mqtt_port = int(config[env]['MQTT_PORT'])    # os.environ.get('MQTT_PORT', '1883') )
    mqtt_user = config[env]['MQTT_USER']    # os.environ.get('MQTT_USER', 'met_00002')
    mqtt_pass = config[env]['MQTT_PASSWORD']    # os.environ.get('MQTT_PASSWORD', 'testPa55')
    sem.Logger(log_fn).log(" init config, MQTT_SERVER=" + mqtt_server + ":" + str(mqtt_port) + " MQTT_USER=" + mqtt_user)
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


def on_connect(client, userdata, flags, rc):
    """callback to be attached to mqtt client"""
    error_msg = ("Connection successful",                               # 0
                 "Connection refused – incorrect protocol version",     # 1
                 "Connection refused – invalid client identifier",      # 2
                 "Connection refused – server unavailable",             # 3
                 "Connection refused – bad username or password",       # 4
                 "Connection refused – not authorised")                 # 5
    if rc > 0:
        client.bad_connection_flag = True
        sem.Logger(log_fn).log(" on_connect, rc=" + str(rc) + " " + error_msg[rc])
    else:
        client.connected_flag = True  # set flag


def create_mqtt(user: str, passw: str, persistent=False, app_name=""):
    """:returns: mqtt.Client, or None, if can't connect
    creates connection using creds"""

    client = mqtt.Client()
    if mqtt_server:                             # is setup during create_app2
        if app_name == "":
            app_name = "rasp-pi"
        mqtt.Client.connected_flag = False                      # create flag in class
        mqtt.Client.bad_connection_flag = False
        client = mqtt.Client(app_name + user, not persistent)  # clean_session=True by default, no msgs are kept after diconnect
        client.username_pw_set(username=user, password=passw)
        client.on_connect = on_connect                          # bind callback function
        try:
            if mqtt_port == 8883:
                client.tls_set()                        # tls_version=ssl.PROTOCOL_TLS
            client.connect(mqtt_server, mqtt_port)
            client.loop_start()                         # Start loop
            while not client.connected_flag or client.bad_connection_flag:  # wait in loop till on_connect callback is executed
                time.sleep(1)
            if client.bad_connection_flag:
                client = None
        except Exception as e:
            sem.Logger(log_fn).log("create_mqtt connect Exception: " + str(e))
            client = None
    else:
        sem.Logger(log_fn).log("create_mqtt WARNING: no MQTT_SERVER assigned!")
    return client


def publish_mqtt():
    """publishes total energy to MQTT channel, run by scheduler every 5 min"""
    try:
        mqtt_client = create_mqtt(mqtt_user, mqtt_pass)   # ('met_00001', 'ISOgvmcglC')
        if mqtt_client is None:
            return
        now = datetime.datetime.now()
        today = datetime.date.today()
        for meter in meters:
            gpio_pin = meter['gpioPin']
            total_count = sem.get_db_pulses(gpio_pin)
            today_count = sem.get_hourly_sum_db(str(gpio_pin), 25, str(today))   # 25 gives whole day
            today_energy = today_count / 1000
            total_energy = total_count / 1000   # to kW
            msg = '{"Time":"' + now.isoformat(timespec='seconds') + '","ENERGY":{"TotalStartTime":"' + total_start_time + \
                  '","Total":' + str(total_energy) + ',"Yesterday":0,"Today":' + str(today_energy) + '}}'
            topic = meter['name']
            fulltopic = "tele/unassigned/" + topic + "/SENSOR"
            info = mqtt_client.publish(fulltopic, msg)
            if info.rc != mqtt.MQTT_ERR_SUCCESS:
                sem.Logger(log_fn).log(" publish_mqtt failed, rc=" + str(info.rc))
        if mqtt_client:
            mqtt_client.loop_stop()  # Stop loop  started
            mqtt_client.disconnect()
    except Exception as e:
        sem.Logger(log_fn).log(" publish_mqtt Exception: " + str(e))


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
    for meter in meters:
        pin = meter['gpioPin']
        nr = random.randint(0, maxcount)
        for i in range(nr):
            simulate_impulse(pin)


def cleanup():
    sem.close_db()


def main():
    init()
    sem.Logger(log_fn).log("Starting metering app.")
    init_counters()
    handle_time_event()
    publish_mqtt()                                  # publish current readings to mqtt
    schedule.every(1).minutes.do(handle_time_event)
    schedule.every(2).minutes.do(publish_mqtt)      # todo change update to 5 min for Live

    killer = sem.GracefulKiller()
    killer.cleanup_func = cleanup
    while not killer.kill_now:
        schedule.run_pending()
        time.sleep(1)  # seconds
    sem.Logger(log_fn).log("Exiting metering app.")


if __name__ == '__main__':
    main()
