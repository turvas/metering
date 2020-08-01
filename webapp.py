#!/usr/bin/python3
import datetime
import os
import sys  # for translate
import glob  # for file matching
import string
from flask import Flask, url_for, render_template
from flask import request

dirpath = "./"
logfile = "control.log"

# by ChrisP from https://stackoverflow.com/questions/92438/stripping-non-printable-characters-from-a-string-in-python
# build a table mapping all non-printable characters to None
NOPRINT_TRANS_TABLE = {
    i: None for i in range(0, sys.maxunicode + 1) if not chr(i).isprintable()
}


def make_printable(s):
    """Replace non-printable characters in a string."""
    # the translate method on str removes characters
    # that map to None from the string
    return s.translate(NOPRINT_TRANS_TABLE)


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


# from control log
def getLogRecords(date, changesOnly=True, linefeed="<br>"):
    outline = ""
    fn = dirpath + logfile
    lastaction = ""
    lastactions = []
    for i in range(0, 32):  # for relays indepenent tracking
        lastactions.append("")
    with open(fn, 'r') as f:
        for line in f:  # read by line
            if date in line:
                if changesOnly:
                    linelen = len(line)
                    action = line[24:linelen - 1]
                    relay = line[linelen - 3:linelen - 1]  # 2 last digits
                    if isInt(relay):
                        relaynum = int(relay)
                    else:
                        relaynum = 0
                    if relaynum > 0:  # if relay action
                        if action != lastactions[relaynum]:
                            lastactions[relaynum] = action
                            outline = outline + line + linefeed
                    else:  # not relay action
                        if action != lastaction:
                            lastaction = action
                            outline = outline + line + linefeed
                else:  # all lines
                    outline = outline + line + linefeed
    return outline


# aggregates hourly readings and daily sum
def getLogMetering(date, filename, linefeed="<br>"):
    outline = ""
    sum = []
    dsum = 0
    for i in range(0, 24):  # fill with 0
        sum.append(0)
    fn = dirpath + filename
    with open(fn, 'r') as f:
        for line in f:  # read by line
            if date in line:
                line1 = line.strip()  # remove linefeed from end, sometimes spaces in beginning
                line = make_printable(line1)
                strlen = len(line)
                try:
                    hrstr = line[9:11]
                    hr = int(hrstr)  # last not included
                    pulses = line[18:strlen]  # last char is linefeed, tody verify str lengt
                    sum[hr] += int(pulses)
                except:
                    print(fn + ", line:" + line + ", hr:" + hrstr)
    for hr in range(0, 24):
        outline = outline + str(hr) + ": " + str(sum[hr]) + linefeed
        dsum += sum[hr]
    outline = outline + "Total day:" + str(dsum)
    return outline


# get unique date part existing in file (first word in line)
def getLogDates(filename):
    dateslist = []
    # datesdictlist = []
    fn = dirpath + filename
    with open(fn, 'r') as f:
        for line in f:  # read by line
            pos = line.find(" ")  # date boundary
            date = line[0:pos]
            if date not in dateslist:
                dateslist.append(date)
                # datesdict = dict(value=date)
                # datesdictlist.append(datesdict)
    dateslist.sort(reverse=True)  # fresh dates first
    return dateslist


def getFiles(pattern):
    '''return list of files matching pattern'''

    files = []
    os.chdir(dirpath)
    for file in glob.glob(pattern):
        files.append(file)
    return files


def getSchedule():
    filename = dirpath + 'schedule.html'
    with open(filename, "r") as f:
        content = f.read()
    return content


app = Flask(__name__)


# picks last N events based on same timestamp
def getRelayStates():
    fn = dirpath + logfile
    lasttime = ""
    lastlines = []
    N = 10
    dtlen = 19
    with open(fn, 'r') as f:
        for line in (f.readlines()[-N:]):  # read last N line
            if "relay" in line:
                if len(lasttime) == 0:  # first time
                    lasttime = line[0:dtlen]
                else:
                    thistime = line[0:dtlen]
                    if thistime == lasttime:
                        lastlines.append(line)
                    else:
                        lasttime = thistime
                        lastlines = [line]
    # <p style="background-color:red;">A red paragraph.</p>
    html = ''
    for line in lastlines:
        # 2020-07-31 23:30:50  23 unpowering boiler2, relay GPIO: 27
        html += '<p style="background-color:'
        if "unpower" in line:
            html += "red"
        else:
            html += "green"
        load = line.split()[4]
        rest = line.split(',')[1]
        txt = load + rest
        html += ';">' + txt + '</p>'
    html += '<br>'
    return html


@app.route('/')
def index(body="", title="Home"):
    # str = "<a href=" + url_for('control_log') + ">Control Log</a>"  # function name here
    menulist = [
        {'caption': 'Home', 'href': url_for('index')},
        {'caption': 'Metering', 'href': url_for('metering')},
        {'caption': 'Schedule', 'href': url_for('schedule')},
        {'caption': 'Control Log', 'href': url_for('control_log')}

    ]
    if body == "":  # if homepage
        body = getRelayStates()
        body += getSchedule()
    outline = render_template('webapp-index.tmpl', navigation=menulist, body=body, title=title) + "<br>"
    return outline


@app.route('/schedule')
def schedule():
    content = getSchedule()
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
        meteringfile = request.form['file']
    else:
        now = datetime.datetime.now()
        date = now.strftime("%Y-%m-%d")
        meteringfile = "pulses-boiler-2020-07.txt"

    meteringfiles = getFiles("pulses-*.txt")
    dateslist = getLogDates(meteringfile)
    outline = render_template('webapp-metering-log.tmpl', dates=dateslist, file=meteringfile, date=date, files=meteringfiles) + "<br>"

    outline = outline + getLogMetering(date, meteringfile)
    outline = index(outline, "Metering aggregation")
    return outline


if __name__ == '__main__':
    setDirPath()
    app.run(debug=True, host='0.0.0.0')
