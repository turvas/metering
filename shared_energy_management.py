import os
import signal
import datetime
import sqlite3

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


def insert_row_db(gpio_pin: int, value: int):
    """saves pulses to database table"""
    db = get_db()
    cur = db.cursor()
    val = (gpio_pin, value)
    cur.execute('INSERT INTO pulses(gpiopin, pulses) VALUES (?,?)', val)  # to avoid sql injection
    db.commit()
