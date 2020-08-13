import os
import time
import signal
import datetime
import sqlite3
from datetime import timedelta, datetime, tzinfo, timezone

control_fn = "web.control"
control_log_fn = "control.log"
schedule_fn = "schedule.txt"
schedule_html_fn = "schedule.html"
prices_fn = "prices.txt"
database_fn = "energy-management-sqlite.db"
db_conn = None

dirpath = "./"  # subject to change, depending OS


def set_dir_path():
    """:returns: and sets global dirpath, OS dependent directory,  . for win, /var/metering for ux"""
    global dirpath
    if os.name == 'posix':
        dirpath = "/var/metering/"
    return dirpath


# by Mayank Jaiswal
# from https://stackoverflow.com/questions/18499497/how-to-process-sigterm-signal-gracefully
class GracefulKiller:
    kill_now = False
    cleanup_func = None

    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, signum, frame):  # is called wit 3 args, 2 not used..
        """exit program with cleanup_func"""
        appname = os.path.basename(__file__)[:-3]  # remove .py from end
        Logger(appname + ".log").log("service stop signal")
        if self.cleanup_func is not None:
            self.cleanup_func()
        self.kill_now = True


class Logger:
    filename = ""

    def __init__(self, fn: str):
        self.filename = dirpath + fn

    def log(self, msg: str, output="both"):
        """log to logfile and screen"""
        now = datetime.datetime.now()
        line = now.strftime("%Y-%m-%d %H:%M:%S %z") + " " + msg + "\n"
        if output == "both":
            print(line)
            with open(self.filename, 'a') as f:
                f.write(line)


# database helpers
def get_db():
    """:return: sqlite3 Connection object"""
    global db_conn
    if db_conn is None:
        db_conn = sqlite3.connect(dirpath + database_fn, detect_types=sqlite3.PARSE_DECLTYPES)
        # g.db.row_factory = sqlite3.Row
    return db_conn


def close_db():
    """close db connection"""
    global db_conn
    if db_conn is not None:
        # noinspection PyUnresolvedReferences
        db_conn.close()
        db_conn = None


def init_db():
    """initializes db, if empty"""
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type ='table' AND name NOT LIKE 'sqlite_%';")
    exist = cur.fetchone()
    if exist is None:  # empty
        with open('energy-management.sql', "r", encoding='utf8') as f:
            fcontent = f.read()
            db.executescript(fcontent)
        print("Database initialized")
        sql = "CREATE UNIQUE INDEX idx_gpio ON config (gpiopin);"  # prepare for INSERT or REPLACE
        cur.execute(sql)
        db.commit()


def update_config_db(gpio: int, name: str, type=1, power=0, energy=0, time2=0, energy2=0):
    """updates configuration table with IO objects,
     :params type can be 1=meter(default) or 2=relay"""
    db = get_db()
    cur = db.cursor()
    val = (gpio, name, type, power, energy, time2, energy2)
    cur.execute('REPLACE INTO config(gpiopin, name, type, power, energy, time2, energy2) VALUES (?,?,?,?,?,?,?)', val)  # to avoid sql injection
    db.commit()


def get_configs_db(type=1):
    """:returns: list of objects (list of properties) of requested type,
    :param type can be 1=meter(default) or 2=relay"""
    db = get_db()
    cur = db.cursor()
    cur.execute('SELECT * from config WHERE type='+str(type))
    configs = []
    for row in cur:
        cfg = list((row))
        configs.append(cfg)
    return configs


def insert_row_db(gpio_pin: int, value: int):
    """saves pulses to database table, timestamps are in UTC"""
    db = get_db()
    cur = db.cursor()
    val = (gpio_pin, value)
    cur.execute('INSERT INTO pulses(gpiopin, pulses) VALUES (?,?)', val)  # to avoid sql injection
    db.commit()


def get_offset_utc():
    """:returns: int localtime hours diff from UTC"""
    if time.daylight and time.localtime().tm_isdst > 0:  # consider DST,
        offset = time.altzone               # is negative for positive timezone and in seconds
    else:
        offset = time.timezone
    offset = int(offset / 3600)             # in seconds -> hrs (in python3 result would be float)
    return 0 - offset                         # convert polarity to normal

def get_offset_utc_s():
    """:returns: string localtime hours diff from UTC, formatted as TZ in ISO: 03:00"""
    offset = get_offset_utc()
    if offset > 0:
        utc_offset = "+"
    else:
        utc_offset = "-"
    if abs(offset) < 10:
        utc_offset += "0"
    utc_offset += str(abs(offset)) + ":00"  # because now.strftime("%z") not working (on Win at least)
    return utc_offset

def get_hourly_sum_db(gpio_pin: str, hr: int, day: str):
    """:return hourly sum for given day and hour,
    :param day in formatted as YYYY-MM-DD,
    day and hr are in local tz"""
    db = get_db()
    cur = db.cursor()
    #date_format = "%Y-%m-%d"        #
    #dtstart = day.strftime(date_format) + " " + str(hr) + ":00:00"  # sqlite expects format YYYY-MM-DD HH:MM:SS
    #dtend = day.strftime(date_format) + " " + str(hr + 1) + ":00:00"
    if hr < 10:
        hrs = "0" + str(hr)
    else:
        hrs = str(hr)
    date_format = "%Y-%m-%d %H:%M:%S"
    dtstart = day + " " + hrs + ":00:00" + get_offset_utc_s()  # sqlite expects format YYYY-MM-DD HH:MM:SS
    dtstart_tz = datetime.fromisoformat(dtstart)
    dtstart_utc = dtstart_tz.astimezone(timezone.utc)
    dtstart_utc_s = dtstart_utc.strftime(date_format)
    dtend_utc = dtstart_utc + timedelta(hours=1)
    dtend_utc_s = dtend_utc.strftime(date_format)
    sql = 'SELECT sum(pulses) FROM pulses WHERE gpiopin==' + gpio_pin + \
          ' AND created BETWEEN "' + dtstart_utc_s + '" AND "' + dtend_utc_s + '";'
    cur.execute(sql)
    row = cur.fetchone()
    sum = row[0]
    if sum is None:
        sum = 0
    return sum


def get_db_dates(gpio_pin: str):
    """:return: reverse sorted list unique dates for load,
    :param gpio_pin corrsponding to load"""
    dateslist = []
    db = get_db()
    cur = db.cursor()
    sql = 'SELECT DISTINCT DATE(created) FROM pulses WHERE gpiopin==' + gpio_pin +';'
    cur.execute(sql)
    for row in cur:
        date = row[0]
        dateslist.append(date)
    dateslist.sort(reverse=True)  # fresh dates first
    return dateslist


