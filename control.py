#!/usr/bin/python
import datetime
import time
import os
# manually install all below: pip install requests
import requests
import schedule
#import urllib

#from gpiozero import

# by hour, index is hr
transahinnad = [0.0158, 0.0158, 0.0158, 0.0158, 0.0158, 0.0158, 0.0158, 0.0158, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274]
# tunni kohta arvutatud
taastuvenergiatasu = 0.0113
# kuutasu jagatud tunni peale (25A siin)
ampritasu = 0.0112
baseurl = "https://dashboard.elering.ee/et/api/nps?type=price"
dirpath = ""
hinnad = []     # list 24, kwh cost by hr
schedule1 = []
schedules = []  # list of schedules (which are lists)
relays = [
    {'name': 'boiler', 'gpioPin':4, 'power':2, 'daily_consumption': 10, 'hrStart2': 15, 'consumption2': 1}
]

# log to logfile and screen
def logger(msg, output="both"):
    print(msg)
    now = datetime.datetime.now()
    line = now.strftime("%Y-%m-%d %H:%M:%S %z")+" "+msg+"\n"
    with open(dirpath + "control.log", 'a') as f:
        f.write(line)
    #f.close()

# sets OS dependent directory
def setDirPath():
    global dirpath
    if os.name == 'posix':
        dirpath = "/var/metering/"
    return dirpath

# filename to save
def downloadFile(filename, firstRun=False):
    # &start=2020-04-12+21:00:00&end=2020-04-13+21:00:00&format=csv
    # &start=2020-04-12+21%3A00%3A00&end=2020-04-13+21%3A00%3A00&format=csv
    hourInGMT="21"  # todo, calculate based on local time DST
    now = datetime.datetime.now()
    if firstRun:    # wind back time by 1 day, as we need today-s prices
        now -= datetime.timedelta(1)
    start = now.strftime("%Y-%m-%d")    # UTC time in URL, prognosis starts yesterday from period (which is today)
    tomorrow = now + datetime.timedelta(1)   # add 1 day
    end = tomorrow.strftime("%Y-%m-%d")
    uri = "&start=" + start + "+"+hourInGMT+"%3A00%3A00&end="+end+"+"+hourInGMT+"%3A00%3A00&format=csv"
    url = baseurl + uri
    r = requests.get(url, allow_redirects=True)
    if len(r.content) > 0:
        open(filename, 'w').write(str(r.content))
        logger ("File downloaded OK to " + filename)
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
def readFile(filename):
    borsihind = []
    with open(filename, "r") as f:
        for line in f:
            items = line.split(";")
            if items[0] == 'ee':        # can be lv, lt, fi..
                item2 = items[2]
                hind1 = item2.replace("\n", "")  # last item contains CR
                hind = hind1.replace(",",".")  # input file uses Euro form of comma: ,
                if isFloat(hind):  # excpt first line whing is rowheadinfs
                    hindMW = float(hind)
                    hindKW = hindMW / 1000
                    borsihind.append(hindKW)
#    f.close()
    return borsihind

# in list of 24 elements of borsihind
# out list of 24 elements of real price, incl time sensitive trans, and other fix fees
def calcPrice(borsihind):
    # type: (borsihind) -> list
    global transahinnad, taastuvenergiatasu, ampritasu
    hr = 0
    hinnad = []
    for raw in borsihind:
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
    priceDict.sort(key=getPrice)    # cheapest hours first
    relayOpen = []
    for hr in range(24):            # fill with disconnected state all time (save power)
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
    return len(schedules)

# default relay is (fail-)closed, connected.
# if needed to save power, (most of time), it will be opened/disconnected
def controlRelay(gpioPIN, scheduleOpen, hr=-1):
    if hr == -1:    # not simulation/testing
        now = datetime.datetime.now()
        hrs = now.strftime("%H")  # string, hour 24h, localtime, not 0 padded
        hr = int(hrs)
    else:           # simulation/testing
        hrs = str(hr)
    if scheduleOpen[hr] == True:        # activate relay => disconnect load by relay
        logger(hrs + " opening relay " + str(gpioPIN))
    else:
        logger(hrs + " stay connected relay " + str(gpioPIN))

# used by scheduler, iterates all relays/schedules
def processRelays():
    i = 0
    for relay in relays:
        controlRelay(relay["gpioPin"], schedules[i]) # assumes schedules order is not modified
        i += 1

# downloads file for tomorrow and creates schedule1
def dailyJob(firstRun=False):
    global schedule1, hinnad
    downloadFile(filename, firstRun)
    borsihinnad = readFile(filename)
    hinnad = calcPrice(borsihinnad)
    #schedule1 = createSchedule2(2, 10, hinnad, 15, 1)
    n = createSchedules()
    logger("DailyJob run completed, created " +str(n)+ " schedules")

#import os
#pwd = os.getcwd()
#print("PWD=" + pwd)

#import sys
#print(sys.version)
#print("\n \n")
#print(sys.path)

setDirPath()
filename = dirpath + "nps-export.csv"
# first time init
dailyJob(True)  # first time to load today-s prices
#schedule.every(5).minutes.do( controlRelay, relayID=1, scheduleOpen=schedule1 )
schedule.every(5).minutes.do(processRelays)
schedule.every().day.at("23:56").do(dailyJob)     # minut peale viimast relay juhtimist

while True:
    schedule.run_pending()
    time.sleep(1)               # seconds
print("valmis")

