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

def getLogRecords(date, linefeed="<br>"):
    outline = ""
    fn = dirpath + logfile
    with open(fn, 'r') as f:
        for line in f:  # read by line
            if date in line:
                outline = outline + line + linefeed
    return outline

def getLogDates():
    dateslist = []
    #datesdictlist = []
    fn = dirpath + logfile
    with open(fn, 'r') as f:
        for line in f:  # read by line
            date = line[0:10]
            if date not in dateslist:
                dateslist.append(date)
                #datesdict = dict(value=date)
                #datesdictlist.append(datesdict)
    dateslist.sort(reverse=True)    # fresh dates first
    return dateslist

app = Flask(__name__)

@app.route('/')
def index():
    str = "<a href=" + url_for('control_log') + ">Control Log</a>"  # function name here

    return str

@app.route('/control-log', methods=['GET', 'POST'])
def control_log():
    if request.method == 'POST':        # in not first time
        date= request.form['date']
    else:
        now = datetime.datetime.now()
        date = now.strftime("%Y-%m-%d")

    dateslist = getLogDates()
    outline = render_template('webapp-contol-log.tmpl', dates=dateslist )+"<br>"

    outline = outline + getLogRecords(date)
    return outline

if __name__ == '__main__':
    setDirPath()
    app.run(debug=True, host='0.0.0.0')