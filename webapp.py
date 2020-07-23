#!/usr/bin/python
import datetime
import os
from flask import Flask, url_for, render_template
from flask import request

dirpath = ""
logfile = "control.log"


# sets OS dependent directory
def setDirPath():
    global dirpath
    if os.name == 'posix':
        dirpath = "/var/metering/"
    else:  # windows
        return dirpath

# True if string can be converted to int
def isInt(value):
    try:
        int(value)
        return True
    except ValueError:
        return False

def getLogRecords(date, changesOnly=True, linefeed="<br>"):
    outline = ""
    fn = dirpath + logfile
    lastaction = ""
    lastactions = []
    for i in range(0,32):
        lastactions.append("")
    with open(fn, 'r') as f:
        for line in f:  # read by line
            if date in line:
                if changesOnly:
                    linelen = len(line)
                    action = line[24:linelen-1]
                    relay = line[linelen-3:linelen-1]    # 2 last digits
                    if isInt(relay):
                        relaynum = int(relay)
                    else:
                        relaynum = 0
                    if relaynum > 0:            # if relay action
                        if action != lastactions[relaynum]:
                            lastactions[relaynum] = action
                            outline = outline + line + linefeed
                    else:                      # not relay action
                        if action != lastaction:
                            lastaction = action
                            outline = outline + line + linefeed
                else:   # all lines
                    outline = outline + line + linefeed
    return outline

def getLogMetering(date, filename, linefeed="<br>"):
    outline = ""
    sum = []
    dsum = 0
    for i in range(0,24):   # fill with 0
        sum.append(0)
    fn = dirpath + filename
    with open(fn, 'r') as f:
        for line in f:  # read by line
            if date in line:
                strlen = len(line)
                hr = int(line[9:11])          # last not included
                pulses = line[18:strlen-1]    # last char is linefeed, tody verify str lengt
                sum[hr] += int(pulses)
    for hr in range(0, 24):
        outline = outline + str(hr) + ": " + str(sum[hr]) + linefeed
        dsum += sum[hr]
    outline = outline + "Total day:" + str (dsum)
    return outline


def getLogDates(filename):
    dateslist = []
    # datesdictlist = []
    fn = dirpath + filename
    with open(fn, 'r') as f:
        for line in f:  # read by line
            pos = line.find(" ")    # date boundary
            date = line[0:pos]
            if date not in dateslist:
                dateslist.append(date)
                # datesdict = dict(value=date)
                # datesdictlist.append(datesdict)
    dateslist.sort(reverse=True)  # fresh dates first
    return dateslist


app = Flask(__name__)


@app.route('/')
def index(body="", title="Home"):
    # str = "<a href=" + url_for('control_log') + ">Control Log</a>"  # function name here
    menulist = [
        {'caption': 'Home', 'href': url_for('index')},
        {'caption': 'Metering', 'href': url_for('metering')},
        {'caption': 'Schedule', 'href': url_for('schedule')},
        {'caption': 'Control Log', 'href': url_for('control_log')}

    ]
    outline = render_template('webapp-index.tmpl', navigation=menulist, body=body, title=title) + "<br>"
    return outline

@app.route('/schedule')
def schedule():
    filename = dirpath + 'schedule.html'
    with open(filename,"r") as f:
        content = f.read()
    outline = index(content, "Schedule")
    return outline


@app.route('/control-log', methods=['GET', 'POST'])
def control_log():
    if request.method == 'POST':  # in not first time
        date = request.form['date']
    else:
        now = datetime.datetime.now()
        date = now.strftime("%Y-%m-%d")

    dateslist = getLogDates(logfile)
    outline = render_template('webapp-contol-log.tmpl', dates=dateslist, file=logfile) + "<br>"

    outline = outline + getLogRecords(date)
    outline = index(outline, "Control Log")
    return outline

@app.route('/metering', methods=['GET', 'POST'])
def metering():
    if request.method == 'POST':  # in not first time
        date = request.form['date']
    else:
        now = datetime.datetime.now()
        date = now.strftime("%Y-%m-%d")

    meteringfile="pulses-boiler-2020-07.txt"

    dateslist = getLogDates(meteringfile)
    outline = render_template('webapp-contol-log.tmpl', dates=dateslist, file=meteringfile, date=date) + "<br>"

    outline = outline + getLogMetering(date, meteringfile)
    outline = index(outline, "Metering aggregation")
    return outline

if __name__ == '__main__':
    setDirPath()
    app.run(debug=True, host='0.0.0.0')
