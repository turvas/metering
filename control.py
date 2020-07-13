import os

# by hour, index is hr
transahinnad = [0.0158, 0.0158, 0.0158, 0.0158, 0.0158, 0.0158, 0.0158, 0.0158, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274, 0.0274]
# tunni kohta arvutatud
taastuvenergiatasu = 0.0113
# kuutasu jagatud tunni peale
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
def calcPrice(borsihind):
    # type: (borsihind) -> list
    global transahinnad, taastuvenergiatasu, ampritasu
    hr = 0
    hinnad = []
    for raw in borsihind:
        hind = raw + transahinnad[hr] + taastuvenergiatasu + ampritasu
        hinnad.append(hind)
        hr = hr + 1
    return hinnad


pwd = os.getcwd()
#print("PWD=" + pwd)
borsihinnad = readFile("nps-export.csv")
hinnad = calcPrice(borsihinnad)
print(hinnad)
print("valmis")
