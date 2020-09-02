#!/usr/bin/python3
import datetime
import os
import sys  # for translate
import glob  # for file matching
import time

from flask import Flask, url_for, render_template
from flask import request
import shared_energy_management as sem

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


def is_int(value: str):
    """:returns: True if string can be converted to int"""
    try:
        int(value)
        return True
    except ValueError:
        return False


def get_log_records(date: str, changes_only=True, linefeed="<br>"):
    """:returns: unique (by default) lines from control log"""
    outline = ""
    fn = sem.dirpath + sem.control_log_fn
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


def get_metering_log(date: str, filename: str, linefeed="<br>", sum_only=False):
    """:returns: multiline aggregated hourly (or daily) readings and daily/monthly sum,
    :param date in form MM/DD/YY or All for full month,
    :param filename from where raw data is processed, usually matching pattern pulses-LOAD-YYYY-MM.txt"""
    outline = ""
    total = []
    dsum = 0
    msum = 0
    if date == "All":  # monthly
        tic = time.perf_counter()
        yr = filename[-9:-7]
        mo = filename[-6:-4]
        for day in range(1, 32):
            d = str(day)
            if day < 10:
                d = "0" + d
            date = mo + "/" + d + "/" + yr
            daily = get_metering_log(date, filename, sum_only=True)  # 07/16/20 3084
            outline += daily
            consumed = daily[9:-4]  # energy before web linefeed
            msum += int(consumed)
        outline += linefeed + "Total month:" + str(msum)
        toc = time.perf_counter()
        outline += linefeed + "Generated in " + str(toc - tic)[:5] + " sec"
    else:  # daily, given date
        for i in range(0, 24):  # fill with 0
            total.append(0)
        fn = sem.dirpath + filename
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
        for hr in range(24):
            if not sum_only:
                outline = outline + str(hr) + ": " + str(total[hr]) + linefeed
            dsum += total[hr]
        if not sum_only:  # daily
            outline = outline + "Total day:" + str(dsum)
        else:  # monthly, All
            outline = outline + date + " " + str(dsum) + linefeed
    return outline


def get_metering_db(date: str, gpio_pin: str, linefeed="<br>", sum_only=False):
    """:returns: multiline aggregated hourly (or daily) readings and daily/monthly sum,
    :param date in form YYYY-MM-DD or All for full month"""
    outline = ""
    dsum = 0
    if date != "All":
        for hr in range(24):
            total = sem.get_hourly_sum_db(gpio_pin, hr, date)
            if not sum_only:
                outline = outline + str(hr) + ": " + str(total) + linefeed
            dsum += total
        if not sum_only:
            outline += "Total "
        outline += date + ": " + str(dsum) + linefeed
    else:  # monthly
        tic = time.perf_counter()
        msum = 0
        date_format = "%Y-%m"  # YYYY-MM
        yydd = datetime.datetime.now().strftime(date_format) + '-'
        for day in range(1, 32):
            if day < 10:
                days_s = "0" + str(day)
            else:
                days_s = str(day)
            line = get_metering_db(yydd + days_s, gpio_pin, sum_only=True)
            outline += line
            nrg = line.split()[1]
            msum += int(nrg[:-4])  # remove <br>
        outline += linefeed + "Total " + date + ": " + str(msum) + linefeed
        toc = time.perf_counter()
        outline += linefeed + "Generated in " + str(toc - tic)[:5] + " sec"
    return outline


def get_log_dates(filename: str):
    """:returns: reverse sorted list unique date part existing in file (first word in line)"""
    dateslist = []
    fn = sem.dirpath + filename
    with open(fn, 'r') as f:
        for line in f:  # read by line
            pos = line.find(" ")  # date boundary
            date = line[0:pos]
            if date not in dateslist:
                dateslist.append(date)
    dateslist.sort(reverse=True)  # fresh dates first
    return dateslist


def get_files(pattern: str):
    """:returns: reverse sorted list of files in dirpath (most recent first) matching pattern"""
    files = []
    os.chdir(sem.dirpath)
    for file in glob.glob(pattern):
        files.append(file)
    files.sort(reverse=True)
    return files


def get_schedule(fn=sem.schedule_html_fn):
    """:returns schedule file contents with date"""
    now = datetime.datetime.now()
    today = now.strftime("%Y-%m-%d")
    content = "Schedule for " + today + ":<br>"
    filename = sem.dirpath + fn
    with open(filename, "r") as f:
        content += f.read()
    return content


def get_control_last_output_lines(lines=10):
    """:return: list of N last lines with relay states,
    picks from control logfile last N events based on same timestamp """
    fn = sem.dirpath + sem.control_log_fn
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
    return lastlines


def get_relay_states():
    """:return: list of relays(name, gpiopin, state)
    picks from control logfile last N events based on same timestamp """
    lastlines = get_control_last_output_lines()
    relays = []
    for line in lastlines:
        # 2020-07-31 23:30:50  23 unpowering boiler2, relay GPIO: 27
        spl = line.split()
        gpio = spl[7]
        load = spl[4][:-1]  # remove , from end
        if "unpower" in line:
            state = False
        else:
            state = True
        relay = list((load, gpio, state))
        relays.append(relay)
    return relays


def get_relay_states_html():
    """:return: html formatted color coded states as buttons,
    picks from control logfile last N events based on same timestamp """

    html = 'Click on buttons to change state for current hour:'
    relays = get_relay_states()
    for relay in relays:
        load = relay[0]
        gpiopin = relay[1]
        html += '<button type="button" onclick="location.href=\'/toggle?load=' + load + '\';" style="background-color:'
        if not relay[2]:
            html += "red"
        else:
            html += "green"
        html += ';">' + load + ", relay GPIO:" + gpiopin + '</button>'
    html += '<br>'
    return html


def check_control_app():
    """:return: error message if not working/logging, or empty string, if all OK"""
    ret = ""
    lastline = get_control_last_output_lines(1)[0]
    td = lastline.split()[:2]   # first 2 elements
    tds = td[0]+" "+td[1]
    last_time = datetime.datetime.fromisoformat(tds)
    now = datetime.datetime.now()
    diff = now - last_time
    if diff.seconds > 360:  # 6 minutes
        ret = '<br><div style="background-color:yellow;">Control program logs older than 5 mins, latest ' + tds + "</div><br>"
    return ret

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
        {'caption': 'Metering DB', 'href': url_for('metering2')},
        {'caption': 'Schedule', 'href': url_for('schedule')},
        {'caption': 'Control Log', 'href': url_for('control_log')}

    ]
    if body == "":  # if homepage
        body = check_control_app()
        body += get_relay_states_html()
        body += get_schedule()
    outline = render_template('webapp-index.tmpl', navigation=menulist, body=body, title=title) + "<br>"
    return outline


@app.route('/toggle')
def toggle():
    """initialtes relay state change, based on load=load_name, supplied by index page"""
    load = request.args.get('load', '')
    fn = sem.dirpath + sem.control_fn  # file, read by control app every second
    with open(fn, 'w') as f:
        f.write(load + " toggle ")
    time.sleep(3)  # wait till control app makes change, so next index page can process new states
    return index()


def create_graph(bar_color_fn: str, bar_height_fn=sem.prices_fn):
    """:returns: html with graph, title from filename
    :param bar_height_fn: with contents of prices by hr list,
    :param bar_color_fn with contents of schedule list gives bar color
    :rtype: str"""
    bar_labels = []
    for hr in range(24):
        bar_labels.append(hr)
    with open(sem.dirpath + bar_height_fn, "r") as f:
        bar_values = f.readline()

    with open(sem.dirpath + bar_color_fn, "r") as f:
        schedule0 = f.read()
    loadname = bar_color_fn[9:-4]
    # [True, True, True, False, False, False, True, True, True, True, True, True, True, True, True, True, True, True, True, True, True, False, True, False]
    schedule1 = schedule0[1:-1] + " "  # remove []
    schedule2 = schedule1.split(', ')
    bg_colors = []
    brd_colors = []
    for hr in range(24):
        sc = schedule2[hr]
        if sc == 'True':  # str: True
            bg_colors.append('rgba(255, 99, 132, 0.2)')  # red
            brd_colors.append('rgba(255, 99, 132, 1)')
        else:
            bg_colors.append('rgba(75, 192, 192, 0.2)')  # green
            brd_colors.append('rgba(75, 192, 192, 1)')
    bgc = bg_colors
    brdc = brd_colors
    content = render_template('webapp-bar-chart.html', title='Kw/h Price', max=2.0, labels=bar_labels,
                              values=bar_values, bg_colors=bgc, brd_colors=brdc, label=loadname)
    return content


@app.route('/schedule')
def schedule():
    content = get_schedule()

    schedule_files = get_files('schedule-*.txt')
    if len(schedule_files) > 0:
        fn = schedule_files[0]
        content += create_graph(fn)

    outline = index(content, "Schedule")
    return outline


@app.route('/control-log', methods=['GET', 'POST'])
def control_log():
    if request.method == 'POST':  # in not first time
        date = request.form['date']
    else:
        now = datetime.datetime.now()
        date = now.strftime("%Y-%m-%d")

    dateslist = get_log_dates(sem.control_log_fn)
    outline = render_template('webapp-contol-log.tmpl', dates=dateslist, file=sem.control_log_fn) + "<br>"

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

    dateslist = get_log_dates(meteringfile) + ["All"]
    if date not in dateslist:  # unlikely nothing for today case
        date = dateslist[0]  # pick last date available
    outline = render_template('webapp-metering-log.tmpl', dates=dateslist, file=meteringfile, date=date,
                              files=meteringfiles) + "<br>"

    outline = outline + get_metering_log(date, meteringfile)
    outline = index(outline, "Metering aggregation")
    return outline


@app.route('/metering2', methods=['GET', 'POST'])
def metering2():
    meters = sem.get_configs_db()
    meter_names = []
    for meter in meters:
        meter_name = meter[2]  # id, gpio, name, ...
        meter_names.append(meter_name)

    if request.method == 'POST':  # in not first time
        date = request.form['date']
        meter_name = request.form['file']
    else:  # first time
        now = datetime.datetime.now()
        date = now.strftime("%Y-%m-%d")
        meter_name = meter_names[0]  # assume there is at least 1
    for meter in meters:  # search gpiopin
        if meter[2] == meter_name:  # name matches
            gpio = meter[1]
    dateslist = sem.get_db_dates(str(gpio)) + ["All"]
    if date not in dateslist:  # unlikely nothing for today case
        date = dateslist[0]  # pick last date available
    outline = render_template('webapp-metering-log.tmpl', dates=dateslist, file=meter_name, date=date,
                              files=meter_names) + "<br>"

    outline = outline + get_metering_db(date, str(gpio))

    outline = index(outline, "Metering aggregation")
    sem.close_db()
    return outline


if __name__ == '__main__':
    sem.set_dir_path()
    if os.name == 'posix':
        dbg = False
    else:  # debug on Windows
        dbg = True
    app.run(debug=dbg, host='0.0.0.0')
