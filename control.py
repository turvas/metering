import os
import datetime

# by hour, index is hr
transahinnad = [0.0158, 0.0158, 0.0158, 0.0158, 0.0158, 0.0158, 0.0158, 0.0158, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274]
# tunni kohta arvutatud
taastuvenergiatasu = 0.0113
# kuutasu jagatud tunni peale (25A siin)
ampritasu = 0.0112


def isFloat(value):
    try:
        float(value)
        return True
    except ValueError:
        return False

# out list od 24 elements, kwh
def readFile(fn):
    borsihind = []
    f = open(fn, "r")
    for line in f:
        items = line.split(";")
        if items[0] == 'ee':        # can be lv, lt, fi..
            item2 = items[2]
            hind1 = item2.replace("\n", "")  # last item contain CR
            hind = hind1.replace(",",".")  # input file uses Euro form of comma
            if isFloat(hind):  # excpt first line whing is rowheadinfs
                hindMW = float(hind)
                hindKW = hindMW / 1000
                borsihind.append(hindKW)
    f.close()
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

# default relay is (fail-)closed, connected.
# if needed to save power, (most of time), it will be opened/disconnected
def controlRelay(relayID, scheduleOpen, hr=-1):
    if hr == -1:    # not simulation/testing
        now = datetime.datetime.now()
        hrs = now.strftime("%H")  # string, hour 24h, localtime
        hr = int(hrs)
    else:           # simulation/testing
        hrs = str(hr)
    if scheduleOpen[hr] == True:        # activate relay => disconnect load by relay
        print(hrs + " opening relay")
    else:
        print(hrs + " relay stay connected")

# Price extractor for pricing dict
def getPrice(e):
  return e['price']

# in power kW (max. average/hr, not peak),
# daily_consumption kWh, prices list in Eur
#out list of 24, with True (open realy) or False (leave connected)
def createSchedule(power, daily_consumption, prices):
    priceDict = []
    hr = 0
    for hind in prices:   # prepare list of dictionary items for sorting
        di = {'hour': hr, 'price': hind}
        priceDict.append(di)
        hr += 1
    priceDict.sort(key=getPrice)    # cheapest hours first
    i = consumed = 0
    relayOpen = []
    for hr in range(24):            # fill with disconnected state all time (save power)
        relayOpen.append(True)
    while consumed < daily_consumption: # iterate list sorted by cheap hours (relay load connected)
        di = priceDict[i]
        hr = di['hour']
        relayOpen[hr] = False
        consumed += power
        i += 1
    return relayOpen

#pwd = os.getcwd()
#print("PWD=" + pwd)
# downloadFile
borsihinnad = readFile("nps-export.csv")
hinnad = calcPrice(borsihinnad)
#print(hinnad)
schedule1 = createSchedule(2, 10, hinnad)
for hr in range(24): # simulation
    controlRelay(1, schedule1, hr)
print("valmis")

