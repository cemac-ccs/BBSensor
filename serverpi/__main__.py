#!/usr/bin/env/python3
# -*- coding: utf-8 -*-

"""
SERVERPI LIBRARY

A library to run the portable sensors for the born in brandford project.

Project: Born In Bradford Breathes

Usage : python3 -m sensorpi

"""

__author__ = "Christopher Symonds, Dan Ellis"
__copyright__ = "Copyright 2020, University of Leeds"
__credits__ = ["Dan Ellis", "Christopher Symonds", "Jim McQuaid", "Kirsty Pringle"]
__license__ = "MIT"
__version__ = "0.4.1"
__maintainer__ = "C. Symonds"
__email__ = "C.C.Symonds@leeds.ac.uk"
__status__ = "Prototype"

# Built-in/Generic Imports
import time,sys,os
from re import sub
from datetime import date,datetime

# Check Modules
from .tests import pyvers
from .geolocate import lat,lon,alt
loc = {'lat':lat,'lon':lon,'alt':alt}
from .log_manager import getlog
log = getlog(__name__)
print = log.print ## replace print function with a wrapper
log.info('########################################################'.replace('#','~'))

# Exec modules
from .exitcondition import GPIO
from . import power
from .crypt import scramble
from . import db
from .db import builddb, __RDIR__
from . import upload

########################################################
##  Running Parameters
########################################################

## runtime constants
SERIAL = os.popen('cat /sys/firmware/devicetree/base/serial-number').read() #16 char key
DATE   = date.today().strftime("%d/%m/%Y")
STOP   = False
SAMPLE_LENGTH = 10
TYPE   = 2 # { 1 = static, 2 = dynamic, 3 = isolated_static, 4 = home/school}
LAST_SAVE = None
LAST_UPLOAD = None
DHT_module = False
OPC = True

if DHT_module: from . import DHT
if OPC:
    from . import R1
    alpha = R1.alpha


### hours (not inclusive)
SCHOOL = [9,15] # stage db during school hours, and upload outside these hours

def interrupt(channel):
    log.warning("Pull Down on GPIO 21 detected: exiting program")
    global STOP
    STOP = True

GPIO.add_event_detect(21, GPIO.RISING, callback=interrupt, bouncetime=300)

log.info('########################################################')
log.info('starting {}'.format(datetime.now()))
log.info('########################################################')


if OPC: R1.clean(alpha)



########################################################
## Retrieving previous upload and staging dates
########################################################

if os.path.exists(os.path.join(__RDIR__,'.uploads')):
    with open (os.path.join(__RDIR__,'.uploads'),'r') as f:
        lines = f.readlines()
    for line in lines:
        if 'LAST_SAVE = ' in line:
            LAST_SAVE = line[12:].strip()
        elif 'LAST_UPLOAD = ' in line:
            LAST_UPLOAD = line[14:].strip()
    if LAST_SAVE == None:
        with open (os.path.join(__RDIR__,'.uploads'),'a') as f:
            f.write('LAST_SAVE = None\n')
        LAST_SAVE = 'None'
    if LAST_UPLOAD == None:
        with open (os.path.join(__RDIR__,'.uploads'),'a') as f:
            f.write('LAST_UPLOAD = None\n')
        LAST_UPLOAD = 'None'
else:
    with open (os.path.join(__RDIR__,'.uploads'),'w') as f:
        f.write("LAST_SAVE = None\n")
        f.write("LAST_UPLOAD = None\n")
    LAST_SAVE = 'None'
    LAST_UPLOAD = 'None'

########################################################
## Main Loop
########################################################

def runcycle():
    '''
    # data = {'TIME':now.strftime("%H%M%S"),
    #         'SP':float(pm['Sampling Period']),
    #         'RC':int(pm['Reject count glitch']),
    #         'PM1':float(pm['PM1']),
    #         'PM3':float(pm['PM2.5']),
    #         'PM10':float(pm['PM10']),
    #         'LOC':scramble(('%s_%s_%s'%(lat,lon,alt)).encode('utf-8'))
    #         'UNIXTIME': int(unixtime)
    #          }
    # Date,Type, Serial

    #(SERIAL,TYPE,d["TIME"],DATE,d["LOC"],d["PM1"],d["PM3"],d["PM10"],d["SP"],d["RC"],)
    '''
    global SAMPLE_LENGTH

    results = []
    alpha.on()
    start = time.time()
    while time.time()-start < SAMPLE_LENGTH:

        now = datetime.utcnow()

        pm = R1.poll(alpha)

        if float(pm['PM1'])+float(pm['PM10'])  > 0:  #if there are results.

            if DHT_module: rh,temp = DHT.read()
            else:
                temp = pm['Temperature']
                rh   = pm[  'Humidity' ]

            unixtime = int(now.strftime("%s")) # to the second

            results.append([
                SERIAL,
                TYPE,
                now.strftime("%H%M%S"),
                scramble(('%(lat)s_%(lon)s_%(alt)s'%loc).encode('utf-8')),
                float(pm['PM1']),
                float(pm['PM2.5']),
                float(pm['PM10']),
                float(temp),
                float(rh),
                float(pm['Sampling Period']),
                int(pm['Reject count glitch']),
                unixtime,
                ] )

        if STOP:break
        time.sleep(.1) # keep as 1

    alpha.off()
    time.sleep(1)# Let the rpi turn off the fan
    return results


########################################################
########################################################


'''
MAIN
'''

########################################################
## Run Loop
########################################################

while True:
    #update less frequenty in loop
    #DATE = date.today().strftime("%d/%m/%Y")

    if OPC:
        d = runcycle()

        db.conn.executemany("INSERT INTO MEASUREMENTS (SERIAL,TYPE,TIME,LOC,PM1,PM3,PM10,T,RH,SP,RC,UNIXTIME) \
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", d );

        db.conn.commit() # dont forget to commit!

    if STOP:break

    hour = datetime.now().hour

    if (hour > SCHOOL[0]) and (hour < SCHOOL[1]):

        DATE = date.today().strftime("%d/%m/%Y")

        if DATE != LAST_SAVE:

            stage_success = upload.stage(SERIAL, __RDIR__)

            if stage_success:
                cursor=db.conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                table_list=[]
                for table_item in cursor.fetchall():
                    table_list.append(table_item[0])

                for table_name in table_list:
                    log.debug ('Dropping table : '+table_name)
                    db.conn.execute('DROP TABLE IF EXISTS ' + table_name)

                log.debug('rebuilding db')
                builddb.builddb(db.conn)

                log.info('staging complete on {}, hour = {}'.format(DATE, hour))

                with open (os.path.join(__RDIR__,'.uploads'),'r') as f:
                    lines=f.readlines()
                with open (os.path.join(__RDIR__,'.uploads'),'w') as f:
                    for line in lines:
                        f.write(sub(r'LAST_SAVE = '+LAST_SAVE, 'LAST_SAVE = '+DATE, line))

                LAST_SAVE = DATE

    elif (hour < SCHOOL[0]) or (hour > SCHOOL[1]):

        if upload.online():
            if DATE != LAST_UPLOAD:
                #check if connected to wifi
                ## SYNC
                success = upload.upload()

                if success:
                    log.debug('upload complete on {}, hour = {}'.format(DATE, hour))

                    with open (os.path.join(__RDIR__,'.uploads'),'r') as f:
                        lines=f.readlines()
                    with open (os.path.join(__RDIR__,'.uploads'),'w') as f:
                        for line in lines:
                            f.write(sub(r'LAST_UPLOAD = '+LAST_UPLOAD, 'LAST_UPLOAD = '+DATE, line))

                    LAST_UPLOAD = DATE

                else:
                    log.debug('Upload failed on {}, hour = {}'.format(DATE, hour))

                ## update time!
                log.info(os.popen('sudo timedatectl &').read())

            ## run git pull
            branchname = os.popen("git rev-parse --abbrev-ref HEAD").read()[:-1]
            os.system("git fetch -q origin {}".format(branchname))
            if not (os.system("git status --branch --porcelain | grep -q behind")):
                STOP = True



if not (os.system("git status --branch --porcelain | grep -q behind")):

    now = datetime.utcnow().strftime("%F %X")
    log.critical('Updates available. We need to reboot. Shutting down at %s'%now)
    os.system("sudo reboot")
