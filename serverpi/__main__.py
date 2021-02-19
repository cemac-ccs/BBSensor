#!/usr/bin/env/python3
# -*- coding: utf-8 -*-

"""
SERVERPI LIBRARY

A library to run the portable sensors for the born in bradford project.

Project: Born In Bradford Breathes

Usage : python3 -m serverpi

"""

__author__ = "Christopher Symonds, Dan Ellis"
__copyright__ = "Copyright 2020, University of Leeds"
__credits__ = ["Dan Ellis", "Christopher Symonds", "Jim McQuaid", "Kirsty Pringle"]
__license__ = "MIT"
__version__ = "0.5.0"
__maintainer__ = "C. Symonds"
__email__ = "C.C.Symonds@leeds.ac.uk"
__status__ = "Prototype"

# Built-in/Generic Imports
import time,sys,os,pickle
from datetime import date,datetime
from re import sub

########################################################
##  Running Parameters
########################################################

## runtime constants

CSV = False

DHT_module = False
OPC = True

### hours (not inclusive)
SCHOOL = [9,15] # stop 10 -2

#how often we save to file
SAMPLE_LENGTH = 10

DATE   = date.today().strftime("%d/%m/%Y")
STOP   = False
TYPE   = 3 # { 1 = static, 2 = dynamic, 3 = isolated_static, 4 = home/school}
LAST_SAVE = None
LAST_UPLOAD = None
SERIAL = os.popen('cat /sys/firmware/devicetree/base/serial-number').read() #16 char key

########################################################
##  Imports
########################################################

#Conditional Imports
if DHT_module: from .Sensormod import DHT
if OPC:
    from .SensorMod import R1

# Check Modules
from .tests import pyvers
from .SensorMod.log_manager import getlog
log = getlog(__name__)
print = log.print ## replace print function with a wrapper
log.info('########################################################'.replace('#','~'))

from .SensorMod.geolocate import lat,lon,alt
loc = {'lat':lat,'lon':lon,'alt':alt}

try:
    from .SensorMod import oled
    oled.standby(message = "   -- loading... --   ")
    OLED_module=True
except ImportError:
    OLED_module=False
log.info('USING OLED = %s'%OLED_module)

# Exec modules
from .SensorMod.exitcondition import GPIO
from .SensorMod import power
from .crypt import scramble
if not CSV
    from .SensorMod import db
    from .SensorMod.db import builddb, __RDIR__
else:
    log.critical('WRITING CSV ONLY')
    from .SensorMod.db import __RDIR__
    CSV = __RDIR__+'/simplesensor.csv'
    SAMPLE_LENGTH = SAMPLE_LENGTH_slow
    from pandas import DataFrame
    columns='SERIAL,TYPE,TIME,LOC,PM1,PM3,PM10,T,RH,BINS,SP,RC,UNIXTIME'.split(',')
from .SensorMod import upload

########################################################
##  Setup
########################################################

if OPC: alpha = R1.alpha
loading = power.blink_nonblock_inf()



def interrupt(channel):
    log.warning("Pull Down on GPIO 21 detected: exiting program")
    global STOP
    STOP = True

GPIO.add_event_detect(21, GPIO.RISING, callback=interrupt, bouncetime=300)

log.info('########################################################')
log.info('starting {}'.format(datetime.now()))
log.info('########################################################')

if OPC: R1.clean(alpha)

while loading.isAlive():
    log.debug('stopping loading blink ...')
    power.stopblink(loading)
    loading.join(.1)


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

            bins = pickle.dumps([float(pm['Bin %s'%i]) for i in range(16)])

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
                           bins,
                           float(pm['Sampling Period']),
                           int(pm['Reject count glitch']),
                           unixtime,] )

            if OLED_module:
                now = str(datetime.utcnow()).split('.')[0]
                oled.updatedata(now,results[-1])

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
    #update less frequently in loop
    #DATE = date.today().strftime("%d/%m/%Y")
    if SAMPLE_LENGTH>0:
        power.ledoff()

        if OPC:
            d = runcycle()

                ''' add to db'''
        if not CSV:
            if OLED_module: oled.standby(message = "   --  write db  --   ")
            db.conn.executemany("INSERT INTO MEASUREMENTS (SERIAL,TYPE,TIME,LOC,PM1,PM3,PM10,T,RH,BINS,SP,RC,UNIXTIME) \
                  VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", d );
            db.conn.commit() # dont forget to commit!
            log.info('DB saved at {}'.format(datetime.utcnow().strftime("%X")))
        else:
            if OLED_module: oled.standby(message = "   --  write csv  --   ")
            DataFrame(d,columns=columns).to_csv(CSV,mode='a')
            log.info('CSV saved at {}'.format(datetime.utcnow().strftime("%X")))

        power.ledon()

    if STOP:break

    hour = datetime.now().hour

    if CSV:
        log.debug('CSV - skipping conditionals')

    elif (hour > SCHOOL[0]) and (hour < SCHOOL[1]):

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
                loading = power.blink_nonblock_inf_update()
                #check if connected to wifi
                ## SYNC
                try:
                    upload_success = upload.upload()
                except Exception as e:
                    log.error("Error in trying to upload data to external storage")
                    upload_success = False
                if upload_success:
                    log.debug('upload complete on {}, hour = {}'.format(DATE, hour))

                    with open (os.path.join(__RDIR__,'.uploads'),'r') as f:
                        lines=f.readlines()
                    with open (os.path.join(__RDIR__,'.uploads'),'w') as f:
                        for line in lines:
                            f.write(sub(r'LAST_UPLOAD = '+LAST_UPLOAD, 'LAST_UPLOAD = '+DATE, line))

                    LAST_UPLOAD = DATE

                else:
                    log.debug('Upload failed on {}, hour = {}'.format(DATE, hour))

                while loading.isAlive():
                    power.stopblink(loading)
                    loading.join(.1)

            ## update time!
            log.info(os.popen('sudo timedatectl &').read())

            ## run git pull
            log.debug('Checking git repo')
            branchname = os.popen("git rev-parse --abbrev-ref HEAD").read()[:-1]
            os.system("git fetch -q origin {}".format(branchname))
            if not (os.system("git status --branch --porcelain | grep -q behind")):
                STOP = True


########################################################
########################################################


log.info('exiting - STOP: %s'%STOP)
if not CSV:
    db.conn.commit()
    db.conn.close()
power.ledon()
if OLED_module: oled.shutdown()
if not (os.system("git status --branch --porcelain | grep -q behind")):
    now = datetime.utcnow().strftime("%F %X")
    log.critical('Updates available. We need to reboot. Shutting down at %s'%now)
    os.system("sudo reboot")
