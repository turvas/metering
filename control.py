#!/usr/bin/python3
# used to control heating, boilers etc, based on lowest hourly energy prices
# takes account expected energy need and average (over hr) used power
# Copyright by turvas
#
import datetime
import time
import os.path
# manually install all below: pip install requests
import requests
import schedule
from decimal import *  # fix precision floating point
# modules below might need manual install only in Windows
from gpiozero import Device, LED
# for Win testing
from gpiozero.pins.mock import MockFactory  # https://gpiozero.readthedocs.io/en/stable/api_pins.html#mock-pins
from requests.models import Response
# shared variables and functions: dirpath, ..
import shared_energy_management as sem

# by hour, index is hr, todo-2 add summer and wintertime /DST difference handling
transahinnad = [0.0158, 0.0158, 0.0158, 0.0158, 0.0158, 0.0158, 0.0158, 0.0158, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274,
                0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274]
# validity by day of week, starting Mon, in case of False transahinnad[0] is used
transahinnad_wkday = [True, True, True, True, True, False, False]
taastuvenergiatasu = 15.6 / (24 * 30)  # 0.02     # tunni kohta arvutatud (1400 kwh)
ampritasu = 14.46 / (24 * 30)  # 0.02    # kuutasu jagatud tunni peale (25A)
baseurl = "https://dashboard.elering.ee/et/api/nps?type=price"
nps_export_fn = "nps-export.csv"  # subject to dir prepend
prices = []             # list 24, kwh cost by hr
schedules = []          # list of schedules (which are lists)
relays = []
# power kW, consumption in Kwh, hrStart2 in 24h system, if no zone2, then 'hrStart2': 24
loads = [
    {'name': 'boiler1', 'gpioPin': 17, 'power': 2, 'daily_consumption': 9, 'hrStart2': 15, 'consumption2': 3},
    {'name': 'boiler2', 'gpioPin': 27, 'power': 2, 'daily_consumption': 9, 'hrStart2': 15, 'consumption2': 3}
]
# in shell:
# echo none | sudo tee /sys/class/leds/led0/trigger
# echo gpio | sudo tee /sys/class/leds/led1/trigger
# powerLED: LED       # /sys/class/leds/led1    # power is hardwired on original Pi
activityLED: LED  # /sys/class/leds/led0


def logger(msg: str, output="both"):
    """log to logfile and screen"""
    now = datetime.datetime.now()
    line = now.strftime("%Y-%m-%d %H:%M:%S %z") + " " + msg + "\n"
    if output == "both":
        print(line)
        with open(sem.dirpath + sem.control_log_fn, 'a') as f:
            f.write(line)


def blink_led():
    """blink/toggle system LED for 1 sec"""
    activityLED.toggle()
    time.sleep(1)
    activityLED.toggle()


def download_file(filename: str):
    """Downloads file for today,
    :returns: True, if success
    :parameter filename to save"""
    if time.daylight and time.localtime().tm_isdst > 0:  # consider DST,
        offset = time.altzone               # is negative for positive timezone and in seconds
    else:
        offset = time.timezone
    offset = int(offset / 3600)             # in seconds -> hrs (in python3 result would be float)
    hour_in_gmt = str(24 + offset)          # works for GMT+3 at least (=21)
    utc_offset = str(0 - offset) + ":00"    # because now.strftime("%z") not working (on Win at least)
    now = datetime.datetime.now()
    if offset < 0:
        now -= datetime.timedelta(1)   # UTC time in URL, wind back time by 1 day (we are GMT+..), as we need today-s prices
    start = now.strftime("%Y-%m-%d")        # UTC time in URL, prognosis starts yesterday from period (which is today)
    tomorrow = now + datetime.timedelta(1)  # add 1 day
    end = tomorrow.strftime("%Y-%m-%d")
    # &start=2020-04-12+21:00:00&end=2020-04-13+21:00:00&format=csv
    # &start=2020-04-12+21%3A00%3A00&end=2020-04-13+21%3A00%3A00&format=csv
    uri = "&start=" + start + "+" + hour_in_gmt + "%3A00%3A00&end=" + end + "+" + hour_in_gmt + "%3A00%3A00&format=csv"
    url = baseurl + uri
    resp = requests.get(url, allow_redirects=True)  # type: Response
    if resp.ok and len(resp.text) > 100:
        open(filename, 'w', encoding="utf-8").write(resp.text)  # need encoding in py3
        logger("File for " + end + "(localtime) downloaded OK to " + filename + " using UTC offset " + utc_offset)
        ret = True
    else:
        logger("ERROR: download of " + url + " failed!, response:" + str(resp.content))
        ret = False
    return ret


def is_float(value: str):
    """:returns: True if string can be converted to float"""
    try:
        float(value)
        return True
    except ValueError:
        return False


def read_prices(filename: str):
    """:returns: list of 24 elements with börsihind, Eur/kwh, based on filename"""
    borsihinnad = []
    with open(filename, "r") as f:
        f.readline()  # header line
        for line in f:  # read by line
            items = line.split(";")
            if items[0] == 'ee':  # can be lv, lt, fi..
                item2 = items[2]
                hind1 = item2.replace("\n", "")  # last item contains CR
                hind = hind1.replace(",", ".")  # input file uses Euro form of comma: ,
                if is_float(hind):  # excpt first line which is rowheads
                    hind_mw = float(hind)
                    hind_kw = hind_mw / 1000
                    borsihinnad.append(hind_kw)
    return borsihinnad


def calc_prices(borsihinnad: list):
    """:return: list of 24 elements of real price, incl time sensitive trans, and other fix fees,
    :param borsihinnad list of 24 elements of borsihind"""
    hr = 0
    hinnad = []
    getcontext().prec = 4  # decimal precision
    today = datetime.datetime.now()
    wkd = today.weekday()
    for raw in borsihinnad:
        if transahinnad_wkday[wkd]:   # is it weekday with different transahid or weekend with flat night tariff
            hind0 = Decimal(raw + transahinnad[hr] + taastuvenergiatasu + ampritasu)
        else:
            hind0 = Decimal(raw + transahinnad[0] + taastuvenergiatasu + ampritasu)
        hind = hind0.quantize(Decimal('1.0000'))
        hinnad.append(float(hind))
        hr += 1
    return hinnad


def output_html_table_row(columns: list, is_header=False):
    """:returns: html table row from list elements, cells background with value False are colored green
    :param columns list of column values,
    :param is_header: if True then html table header marking is used"""
    html = "<tr>" + "\n"
    if is_header:
        tags = ["<th>", "</th>", "<th>"]
    else:
        tags = ['<td>', '</td>', '<td bgcolor="green">"']
    for item in columns:
        if not item:  # = False
            pos = 2
        else:  # default, no backgroundcolor
            pos = 0
        html += tags[pos] + str(item) + tags[1] + "\n"
    html += "</tr>" + "\n"
    return html


def output_html_table(rows: list, rownames: list, header: list = None):
    """:return: HTML table from list of lists, default with numbers as table headers,
    :param rows list of rows(lists), typically schedules,
    :param rownames list of dictionaries, where "name" key is used for first column,
    :param header optional list of Header row columns"""
    if header is None:
        header = []
    count = len(rows[0])
    style = '<style> ' \
            'table, th, td {' \
            '   border: 1px solid black;' \
            '    width: 100 %;' \
            '}' \
            '</style>'
    html = style + '<table style="width:100%">' + "\n"
    if len(header) == 0:
        for i in range(0, count):
            header.append(i)
    html += output_html_table_row(["Hours:"] + header, True)  # one empty cell in beginning
    for i in range(len(rows)):
        html += output_html_table_row([rownames[i]["name"]] + rows[i])  # create list from name string, to concatenate lists
    html += '</table>' + "\n"
    return html


def get_price(di: dict):
    """:returns: float Price from pricing dict item,
        :rtype: float"""
    return di['price']


def create_schedule(power, daily_consumption, hr_start=0, hr_end=24):
    """:return: list of 24 (default), with True (open realy) or False (leave connected),
    :param hr_end: end of schedule,
    :param hr_start: beginning of schedule,
    :param power kW (max. average/hr, not peak),
    :param daily_consumption kWh"""
    price_dict = []
    for hr in range(hr_start, hr_end):  # prepare list of dictionary items for sorting
        di = {'hour': hr, 'price': prices[hr]}
        price_dict.append(di)
    price_dict.sort(key=get_price)  # cheapest hours first
    relay_open = []
    for hr in range(24):  # fill with disconnected state all time (save power)
        relay_open.append(True)
    i = consumed = 0
    while consumed < daily_consumption:  # iterate list sorted by cheap hours (relay load connected)
        di = price_dict[i]
        hr = di['hour']
        relay_open[hr] = False
        consumed += power
        i += 1
    return relay_open


def create_schedule2(power, daily_consumption, hr_start2, consumption2):
    """prepares 2-zone schedule.
    :param power: kW of load/heater
    :param daily_consumption: kwh
    :param hr_start2 starining hr of zone2,
    :param consumption2 kWh during zone 2 (usually significantly less than daily_consumption),
    :returns: list of 24 (always), with content of True (open realy) or False (leave connected)"""
    schedule0 = create_schedule(power, daily_consumption - consumption2, 0, hr_start2 - 1)
    schedule2 = create_schedule(power, consumption2, hr_start2, 24)  # after cutover
    for hr in range(hr_start2, 24):
        schedule0[hr] = schedule2[hr]  # overwrite
    return schedule0


def create_schedule_fn(load_name):
    """:returns: filename with load name integrated"""
    suffix = sem.schedule_fn[-4:]
    sche_fn = sem.schedule_fn[:-4] + "-" + load_name + suffix
    return sche_fn


def create_schedules():
    """creates schedules for all relays,
    :returns: count of schedules """
    global schedules
    for heater in loads:
        schedule0 = create_schedule2(heater["power"], heater["daily_consumption"],
                                     heater["hrStart2"], heater["consumption2"])
        schedules.append(schedule0)
        heater_name = heater['name']
        logger(heater_name + ": " + str(schedule0))
        sch_fn = create_schedule_fn(heater_name)
        with open(sch_fn, "w") as f:
            f.write(str(schedule0))
    return len(schedules)


# default relay is (fail-)closed, connected.
# if needed to save power, (most of time), it will be opened/disconnected
def control_relay(load, schedule_open, relay, hr=-1):
    """sets proper state for load, relay, based on schedule, if hr is given, then executes as if hr has arrived"""
    global activityLED
    gpio_pin = load["gpioPin"]
    if hr == -1:  # not simulation/testing
        now = datetime.datetime.now()
        hrs = now.strftime("%H")  # string, hour 24h, localtime, not 0 padded
        hr = int(hrs)
    else:  # simulation/testing
        hrs = str(hr)
    # careful with log format change, "relay" and gpio pin positions are critical for webapp relay status display
    if schedule_open[hr]:  # True, activate relay => disconnect load by relay
        logger(hrs + " unpowering " + load["name"] + ", relay GPIO: " + str(gpio_pin))
        relay.off()  # disconnect load, with driving output to low - trigger relay
        activityLED.off()  # reversed, this means on !
    else:
        logger(hrs + " powering " + load["name"] + ", relay GPIO: " + str(gpio_pin))
        relay.on()  # positive releases realy back to free state
        activityLED.on()  # reversed, this means off !
    # time.sleep(1)  # seconds


def process_relays():
    """ iterates all relays/schedules, used by scheduler"""
    i = 0
    for load in loads:
        control_relay(load, schedules[i], relays[i])  # assumes schedules order is not modified
        i += 1


def calc_filename(filename: str):
    """:returns: filename for todays date"""
    now = datetime.datetime.now()
    today = now.strftime("%Y-%m-%d")
    fnl = len(filename)
    fn = filename[0:fnl-4]
    fn += "-" + today + ".csv"
    return fn


def daily_job():
    """downloads file for tomorrow and creates schedules"""
    global prices
    # logger("downloadFile ..")
    filename = calc_filename(nps_export_fn)
    ret = download_file(filename)
    if ret:
        # logger("readPrices ..")
        borsihinnad = read_prices(filename)
        # logger("calcPrices ..")
        prices = calc_prices(borsihinnad)
        # logger("createSchedules ..")
        if len(prices) > 23:
            n = create_schedules()
            # prepare outputs for webapp:
            html = output_html_table(schedules + [prices], loads + [{"name": "Prices"}])  # append last row with prices
            with open(sem.schedule_html_fn, "w") as f:
                f.write(html)
            with open(sem.prices_fn, "w") as f:
                f.write(str(prices))
            logger("DailyJob run completed, created " + str(n) + " schedules")
        else:
            logger("DailyJob run completed with errors, no prices obtained")
    else:
        logger("DailyJob run download_file failed, keeping existing schedules")


def find_load(load_name: str):
    """:returns: index in list of load objects, based on name, or -1 if not found"""
    loadcount = len(loads)
    for i in range(loadcount):
        if load_name == loads[i]["name"]:
            return i
    return -1  # not found


def process_web_commands():
    """reads commands sent by webapp from file and executes relay control"""
    fn = sem.dirpath + sem.control_fn
    if os.path.isfile(fn):
        with open(fn, 'r') as f:
            for line in f:
                # boiler1, toggle
                load_name = line.split(',')[0]  # there is "," after load name
                command = line.split()[1]
                load_index = find_load(load_name)
                if load_index > -1:  # found
                    # scheduleTmp = []
                    if command == 'toggle':
                        now = datetime.datetime.now()
                        hrs = now.strftime("%H")  # string, hour 24h, localtime, not 0 padded
                        hr = int(hrs)
                        curstate = schedules[load_index][hr]
                        if curstate:  # = True
                            schedules[load_index][hr] = False
                        else:
                            schedules[load_index][hr] = True
                        # for hr in range(24):  # fill with disconnected state all time (save power)
                    #    scheduleTmp.append(True)
                    control_relay(loads[load_index], schedules[load_index], relays[load_index])
        os.remove(fn)


def init_system():
    """initial setup steps"""
    global nps_export_fn, relays, activityLED
    # global sem.schedule_html_fn, sem.schedule_fn, sem.prices_fn,

    logger("init control module..")

    sem.set_dir_path()
    nps_export_fn = sem.dirpath + nps_export_fn     # prepend dir to original name
    sem.schedule_html_fn = sem.dirpath + sem.schedule_html_fn
    sem.prices_fn = sem.dirpath + sem.prices_fn
    sem.schedule_fn = sem.dirpath + sem.schedule_fn

    if os.name == 'posix':
        os.system('echo none | sudo tee /sys/class/leds/led0/trigger')
    else:                   # windows for dev
        Device.pin_factory = MockFactory()  # Set the default pin factory to a mock factory

    for load in loads:
        relay = LED(load["gpioPin"])            # init output objects for relays
        relays.append(relay)

    # powerLED = LED(35)  # /sys/class/leds/led1
    activityLED = LED(16)  # /sys/class/leds/led0   #16 on original Pi 1, todo-3: make dynamic based on Pi version

def cleanup_system():
    if os.name == 'posix':
        os.system("echo mmc0 | sudo tee/sys/class/leds/led0/trigger")  # restore override by us

def main():

    init_system()
    # logger("dailyJob..")
    daily_job()                                         # load today-s prices
    # logger("processRelays..")
    process_relays()                                    # set proper state
    # logger("prepare schedules..")
    schedule.every().day.at("00:01").do(daily_job)      # pisut enne uue paeva algust
    schedule.every(5).minutes.do(process_relays)
    schedule.every(3).seconds.do(blink_led)             # heartbeat 1:2 suhtega
    schedule.every().second.do(process_web_commands)    # webapp may trigger relays
    # logger("create GracefulKiller..")
    killer = sem.GracefulKiller()
    killer.cleanup_func = cleanup_system                # setup cleanup task
    while not killer.kill_now:
        schedule.run_pending()
        time.sleep(1)  # seconds
    print("valmis, exit..")


if __name__ == '__main__':
    main()
