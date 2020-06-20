#!/usr/bin/python
import time
import datetime
import schedule
from gpiozero import Button

l_cnt_1 = 0

def light_pulse_seen_1():
    global l_cnt_1
    l_cnt_1 = l_cnt_1 + 1
	
def handle_time_event():
    global l_cnt_1
    insert_row()
    l_cnt_1 = 0

def insert_row():
        global l_cnt_1
	dt = datetime.datetime.now()
	dtf=dt.strftime("%x %X")
        txt = dtf + " " + str(l_cnt_1) + "\n"
        print(txt)

        ym = dt.strftime("%Y-%m")
        fn = "/var/metering/pulses-"+str(ym)+".txt"
	f = open(fn, "a")
	f.write(txt)
	f.close()
	
button = Button(3)
button.when_pressed = light_pulse_seen_1
handle_time_event()
schedule.every(1).minutes.do(handle_time_event)
while True:
    schedule.run_pending()
    time.sleep(1)
