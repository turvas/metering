#!/usr/bin/python3
import datetime
import os
import sys  # for translate
import glob  # for file matching
import time

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


def set_dir_path():
    """:returns: and sets OS dependent directory"""
    global dirpath
    if os.name == 'posix':
        dirpath = "/var/metering/"
    else:  # windows
        return dirpath


def is_int(value: str):
    """:returns: True if string can be converted to int"""
    try:
        int(value)
        return True
    except ValueError:
        return False


#
def get_log_records(date: str, changes_only=True, linefeed="<br>"):
    """:returns: unique (by default) lines from control log"""
    outline = ""
    fn = dirpath + logfile
    lastaction = ""
    lastactions = []
    for i in range(0, 32):  # for relays indepenent tracking
        lastactions.append("")
    with open(fn, 'r') as f:
        for line in f:  # read by line
            if date in line:
                if changes_only:
                    linelen = len(line)
                    action = line[24:linelen - 1]
                    relay = line[linelen - 3:linelen - 1]  # 2 last digits
                    if is_int(relay):
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


def get_metering_log(date, filename, linefeed="<br>"):
    """:returns: multiline aggregated hourly readings and daily sum"""
    outline = ""
    total = []
    dsum = 0
    for i in range(0, 24):  # fill with 0
        total.append(0)
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
                    total[hr] += int(pulses)
                except:
                    print(fn + ", line:" + line + ", hr:" + hrstr)
    for hr in range(0, 24):
        outline = outline + str(hr) + ": " + str(total[hr]) + linefeed
        dsum += total[hr]
    outline = outline + "Total day:" + str(dsum)
    return outline


def get_log_dates(filename: str):
    """:returns: reverse sorted list unique date part existing in file (first word in line)"""
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


def get_files(pattern: str):
    """:returns: reverse sorted list of files (most recent first) matching pattern"""
    files = []
    os.chdir(dirpath)
    for file in glob.glob(pattern):
        files.append(file)
    files.sort(reverse=True)
    return files


def get_schedule(fn='schedule.html'):
    """:returns schedule file contents with date"""
    now = datetime.datetime.now()
    today = now.strftime("%Y-%m-%d")
    content = "Schedule for " + today + ":<br>"
    filename = dirpath + fn
    with open(filename, "r") as f:
        content += f.read()
    return content


def get_relay_states():
    """:return: html formatted color coded states,
    picks from control logfile last N events based on same timestamp """
    fn = dirpath + logfile
    lastlines = []
    with open(fn, 'r') as f:  # find N last lines based on same timestamp
        for line in (f.readlines()[-10:]):  # read last 10 line
            # 2020-08-05 00:00:17 00 unpowering boiler1, relay GPIO: 17
            if "relay" in line:
                # ll = len(line)
                gpio = "GPIO: " + line[-3:-1]  # 2 chars from end, exclude newline
                if len(lastlines) == 0:  # first time
                    lastlines.append(line)
                else:
                    i = 0
                    found = False
                    for lline in lastlines:
                        if gpio in lline:  # new record for existing relay
                            lastlines[i] = line
                            found = True
                        i += 1
                    if not found:
                        lastlines.append(line)

    # <p style="background-color:red;">A red paragraph.</p>
    html = 'Click on buttons to change state for current hour:'
    for line in lastlines:
        # 2020-07-31 23:30:50  23 unpowering boiler2, relay GPIO: 27
        load = line.split()[4]
        rest = line.split(',')[1]
        txt = load + rest
        html += '<button type="button" onclick="location.href=\'/toggle?load=' + load + '\';" style="background-color:'
        if "unpower" in line:
            html += "red"
        else:
            html += "green"
        html += ';">' + txt + '</button>'
    html += '<br>'
    return html


app = Flask(__name__)


@app.route('/')
def index(body="", title="Home"):
    """:returns: html page headers, modifiable body and footers,
    :arg body optional body, if empty yhen relay states and schedule,
    :arg title page title"""
    # str = "<a href=" + url_for('control_log') + ">Control Log</a>"  # function name here
    menulist = [
        {'caption': 'Home', 'href': url_for('index')},
        {'caption': 'Metering', 'href': url_for('metering')},
        {'caption': 'Schedule', 'href': url_for('schedule')},
        {'caption': 'Control Log', 'href': url_for('control_log')}

    ]
    if body == "":  # if homepage
        body = get_relay_states()
        body += get_schedule()
    outline = render_template('webapp-index.tmpl', navigation=menulist, body=body, title=title) + "<br>"
    return outline


@app.route('/toggle')
def toggle():
    """initialtes relay state change, based on load=load_name, supplied by index page"""
    load = request.args.get('load', '')
    fn = dirpath + "web.control"  # file, read by control app every second
    with open(fn, 'w') as f:
        f.write(load + " toggle ")
    time.sleep(3)  # wait till control app makes change, so next index page can process new states
    return index()


@app.route('/schedule')
def schedule():
    content = get_schedule()
    outline = index(content, "Schedule")
    return outline


@app.route('/control-log', methods=['GET', 'POST'])
def control_log():
    if request.method == 'POST':  # in not first time
        date = request.form['date']
    else:
        now = datetime.datetime.now()
        date = now.strftime("%Y-%m-%d")

    dateslist = get_log_dates(logfile)
    outline = render_template('webapp-contol-log.tmpl', dates=dateslist, file=logfile) + "<br>"

    outline = outline + get_log_records(date)
    outline = index(outline, "Control Log")
    return outline


@app.route('/metering', methods=['GET', 'POST'])
def metering():
    meteringfiles = get_files("pulses-*.txt")

    if request.method == 'POST':  # in not first time
        date = request.form['date']
        meteringfile = request.form['file']
    else:  # first time
        now = datetime.datetime.now()
        date = now.strftime("%Y-%m-%d")
        meteringfile = meteringfiles[0]  # assume there is at least 1 file

    dateslist = get_log_dates(meteringfile)
    if date not in dateslist:  # unlikely nothing for today case
        date = dateslist[0]  # pick last date available
    outline = render_template('webapp-metering-log.tmpl', dates=dateslist, file=meteringfile, date=date,
                              files=meteringfiles) + "<br>"

    outline = outline + get_metering_log(date, meteringfile)
    outline = index(outline, "Metering aggregation")
    return outline


if __name__ == '__main__':
    set_dir_path()
    if os.name == 'posix':
        dbg = False
    else:  # debug on Windows
        dbg = True
    app.run(debug=dbg, host='0.0.0.0')
