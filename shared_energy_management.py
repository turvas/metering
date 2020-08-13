import os
import signal
import sqlite3
#from flask import current_app, g
#from flask.cli import with_appcontext

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

    def exit_gracefully(self):  # , signum, frame
        """exit program with cleanup_func"""
        logger("service stop signal")
        if cleanup_func is not None:
            cleanup_func()
        self.kill_now = True

# database helpers
def get_db():
    """:return: sqlite3 Connection object"""
    global db_conn
    if db_conn is None:
        db_conn = sqlite3.connect(dirpath + database_fn, detect_types=sqlite3.PARSE_DECLTYPES)
        #g.db.row_factory = sqlite3.Row
    return db_conn


def close_db(e=None):
    """close db connection"""
    if db_conn is not None:
        db_conn.close()


def init_db():
    """initializes db, if empty"""
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type ='table' AND name NOT LIKE 'sqlite_%';")
    exist = cur.fetchone()
    if exist is None:    # empty
        with open('energy-management.sql', "r",encoding='utf8') as f:
            fcontent = f.read()
            db.executescript(fcontent)
        print("Database initialized")


def insert_row_db(gpio_pin: int, value: int):
    """saves pulses to database table"""
    db = get_db()
    cur = db.cursor()
    val = (gpio_pin, value)
    cur.execute('INSERT INTO pulses(gpiopin, pulses) VALUES (?,?)', val)   # to avoid sql injection
    db.commit()