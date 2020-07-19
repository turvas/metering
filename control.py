#!/usr/bin/python
# used to control heating, boilers etc, based on lowest hourly energy prices
# takes account expected energy need and average (over hr) used power
# Copyright by turvas
#
import datetime
import time
import os
# manually install all below: pip install requests
import requests
import schedule
import signal
# modules below might need manual install only in Windows
from gpiozero import Device, LED
# for Win testing
from gpiozero.pins.mock import MockFactory # https://gpiozero.readthedocs.io/en/stable/api_pins.html#mock-pins
from requests.models import Response

# by hour, index is hr, todo-2 add summer and wintertime /DST difference handling
transahinnad = [0.0158, 0.0158, 0.0158, 0.0158, 0.0158, 0.0158, 0.0158, 0.0158, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274]
taastuvenergiatasu = 15.6/(24*30)   #0.02     # tunni kohta arvutatud (1400 kwh)
ampritasu = 14.46/(24*30)           #0.02    # kuutasu jagatud tunni peale (25A)
baseurl = "https://dashboard.elering.ee/et/api/nps?type=price"
dirpath = ""                    # subject to cange, depending OS
filename = "nps-export.csv"     # subject to dir prepend
hinnad = []                     # list 24, kwh cost by hr
schedules = []                  # list of schedules (which are lists)
# power kW, consumption in Kwh, hrStart2 in 24h system
relays = [
    {'name':'boiler1', 'gpioPin':17, 'power':2, 'daily_consumption':5, 'hrStart2':15, 'consumption2':1},
    {'name':'boiler2', 'gpioPin':27, 'power':2, 'daily_consumption':5, 'hrStart2':15, 'consumption2':1}
]
# in shell
# echo none | sudo tee /sys/class/leds/led0/trigger
# echo gpio | sudo tee /sys/class/leds/led1/trigger
# power = None    # /sys/class/leds/led1    # power is hardwired on original Pi
activityLED =None  # /sys/class/leds/led0

# log to logfile and screen
def logger(msg, output="both"):
    now = datetime.datetime.now()
    line = now.strftime("%Y-%m-%d %H:%M:%S %z")+" "+msg+"\n"
    print(line)
    with open(dirpath + "control.log", 'a') as f:
        f.write(line)

# sets OS dependent directory
def setDirPath():
    global dirpath, power, activityLED
    if os.name == 'posix':
        dirpath = "/var/metering/"
        os.system('echo none | sudo tee /sys/class/leds/led0/trigger')
    else:            # windows
        Device.pin_factory = MockFactory()  # Set the default pin factory to a mock factory
    #power = LED(35)  # /sys/class/leds/led1
    activityLED = LED(16)  # /sys/class/leds/led0
    return dirpath

# blink system LED
def blinkLed():
    activityLED.toggle()
    time.sleep(1)
    activityLED.toggle()

# filename to save
def downloadFile(filename, firstRun=False):
    now = datetime.datetime.now()
    if firstRun:    # wind back time by 1 day, as we need today-s prices
        now -= datetime.timedelta(1)
    if time.daylight and time.localtime().tm_isdst > 0: # consider DST,
        offset = time.altzone                           # is negative and in seconds
    else:
        offset = time.timezone
    offset = offset / 3660                              # in seconds -> hrs
    hourInGMT = str(24+offset)
    utc_offset = str(0-offset) + ":00"                  # now.strftime("%z") not working on Win
    start = now.strftime("%Y-%m-%d")    # UTC time in URL, prognosis starts yesterday from period (which is today)
    tomorrow = now + datetime.timedelta(1)   # add 1 day
    end = tomorrow.strftime("%Y-%m-%d")
    # &start=2020-04-12+21:00:00&end=2020-04-13+21:00:00&format=csv
    # &start=2020-04-12+21%3A00%3A00&end=2020-04-13+21%3A00%3A00&format=csv
    uri = "&start=" + start + "+"+hourInGMT+"%3A00%3A00&end="+end+"+"+hourInGMT+"%3A00%3A00&format=csv"
    url = baseurl + uri
    resp = requests.get(url, allow_redirects=True)  # type: Response
    if resp.ok and len(resp.content) > 0:
        open(filename, 'w').write(str(resp.content))
        logger ("File downloaded OK to " + filename + " using UTC offset " + utc_offset)
    else:
        logger("ERROR: download of " + url + " failed!")

# True if string can be converted to float
def isFloat(value):
    try:
        float(value)
        return True
    except ValueError:
        return False

# out list of 24 elements, Eur/kwh
def readPrices(filename):
    borsihinnad = []
    with open(filename, "r") as f:
        for line in f:                  # read by line
            items = line.split(";")
            if items[0] == 'ee':        # can be lv, lt, fi..
                item2 = items[2]
                hind1 = item2.replace("\n", "")  # last item contains CR
                hind = hind1.replace(",",".")   # input file uses Euro form of comma: ,
                if isFloat(hind):               # excpt first line which is rowheads
                    hindMW = float(hind)
                    hindKW = hindMW / 1000
                    borsihinnad.append(hindKW)
    return borsihinnad

# in list of 24 elements of borsihind
# out list of 24 elements of real price, incl time sensitive trans, and other fix fees
def calcPrices(borsihinnad):
    #global transahinnad, taastuvenergiatasu, ampritasu
    hr = 0
    hinnad = []
    for raw in borsihinnad:
        hind = raw + transahinnad[hr] + taastuvenergiatasu + ampritasu
        hinnad.append(hind)
        hr += 1
    return hinnad

# Price extractor for pricing dict item
def getPrice(di):
  return di['price']

# in power kW (max. average/hr, not peak),
#    daily_consumption kWh, prices list(24) in Eur
# out list of 24 (default), with True (open realy) or False (leave connected)
def createSchedule(power, daily_consumption, prices, hrStart=0, hrEnd=24):
    priceDict = []
    for hr in range(hrStart, hrEnd):    # prepare list of dictionary items for sorting
        di = {'hour': hr, 'price': prices[hr]}
        priceDict.append(di)
    priceDict.sort(key=getPrice)        # cheapest hours first
    relayOpen = []
    for hr in range(24):                # fill with disconnected state all time (save power)
        relayOpen.append(True)
    i = consumed = 0
    while consumed < daily_consumption:   # iterate list sorted by cheap hours (relay load connected)
        di = priceDict[i]
        hr = di['hour']
        relayOpen[hr] = False
        consumed += power
        i += 1
    return relayOpen

# prepares 2-zone schedule
# hrStart2 - starining hr of zone2
# consumption2 - during zone 2 (usually significantly less than daily_consumption)
# out list of 24 (always), with True (open realy) or False (leave connected)
def createSchedule2(power, daily_consumption, prices, hrStart2, consumption2):
    schedule0 = createSchedule(power, daily_consumption-consumption2, prices, 0, hrStart2-1)
    schedule2 = createSchedule(power, consumption2, hinnad, hrStart2, 23) # after cutover
    for hr in range(hrStart2, 24):
        schedule0[hr] = schedule2[hr]   # overwrite
    return schedule0

# creates schedules for all relays
# returns count
def createSchedules():
    global schedules
    for relay in relays:
        schedule0 = createSchedule2(relay["power"], relay["daily_consumption"], hinnad,
                                    relay["hrStart2"], relay["consumption2"])
        schedules.append(schedule0)
        logger(relay['name']+": "+str(schedule0))
    return len(schedules)

# default relay is (fail-)closed, connected.
# if needed to save power, (most of time), it will be opened/disconnected
def controlRelay(gpioPIN, scheduleOpen, hr=-1):
    global activityLED
    if hr == -1:    # not simulation/testing
        now = datetime.datetime.now()
        hrs = now.strftime("%H")    # string, hour 24h, localtime, not 0 padded
        hr = int(hrs)
    else:                           # simulation/testing
        hrs = str(hr)
    relay = LED(gpioPIN)
    if scheduleOpen[hr] == True:    # activate relay => disconnect load by relay
        logger(hrs + " opening relay " + str(gpioPIN))
        relay.on()
        activityLED.on()
    else:
        logger(hrs + " stay connected relay " + str(gpioPIN))
        relay.off()
        activityLED.off()

# used by scheduler, iterates all relays/schedules
def processRelays():
    i = 0
    for relay in relays:
        controlRelay(relay["gpioPin"], schedules[i]) # assumes schedules order is not modified
        i += 1

# downloads file for tomorrow and creates schedules
def dailyJob(firstRun=False):
    global hinnad
    downloadFile(filename, firstRun)
    borsihinnad = readPrices(filename)
    hinnad = calcPrices(borsihinnad)
    n = createSchedules()
    logger("DailyJob run completed, created " +str(n)+ " schedules")

def exitHandler(signum, frame):
    logger("service stop signal")
    if os.name == 'posix':
        os.system('echo mmc0 | sudo tee/sys/class /leds / led0 / trigger')  # restore overridy by us

def main():
    global filename
    setDirPath()
    filename = dirpath + filename   # prepend dir to original name

    dailyJob(True)                  # first time to load today-s prices
    schedule.every(5).minutes.do(processRelays)
    schedule.every().day.at("23:58").do(dailyJob)       # pisut enne uue paeva algust
    schedule.every(3).seconds.do(blinkLed)              # heartbeat

    signal.signal(signal.SIGTERM, exitHandler)

    while True:
        schedule.run_pending()
        time.sleep(1)               # seconds

    print("valmis, exit..")

if __name__ == '__main__':
    main()

