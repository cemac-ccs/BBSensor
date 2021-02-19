#!/usr/bin/env/python3
# -*- coding: utf-8 -*-

"""
StaticSensorPI LIBRARY
A library to run the portable sensors for the born in brandford project.
Project: Born In Bradford Breathes
Usage : python3 -m sensorpi
"""

__author__ = "Dan Ellis, Christopher Symonds"
__copyright__ = "Copyright 2020, University of Leeds"
__credits__ = ["Dan Ellis", "Christopher Symonds", "Jim McQuaid", "Kirsty Pringle"]
__license__ = "MIT"
__version__ = "0.5.0"
__maintainer__ = "C. Symonds"
__email__ = "C.C.Symonds@leeds.ac.uk"
__status__ = "Prototype"

########################################################
##  Imports and constants
########################################################

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


### hours (not inclusive)
SCHOOL = [9,15] # stage db during school hours

#how often to save to file
SAMPLE_LENGTH = 10

DATE   = date.today().strftime("%d/%m/%Y")
STOP   = False
TYPE   = 3 # { 1 = static, 2 = dynamic, 3 = isolated_static, 4 = home/school}
LAST_SAVE = None
SERIAL = os.popen('cat /sys/firmware/devicetree/base/serial-number').read() #16 char key

########################################################
##  Imports
########################################################

## conditional Imports
if DHT_module: from . import DHT

# Check Modules
from .tests import pyvers
from .SensorMod.log_manager import getlog
log = getlog(__name__)
print = log.print ## replace print function with a wrapper
log.info('########################################################'.replace('#','~'))

from .SensorMod.gps.geolocate import lat,lon,alt
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
if not CSV:
    from .SensorMod import db
    from .SensorMod.db import builddb, __RDIR__
else:
    log.critical('WRITING CSV ONLY')
    from .db import __RDIR__
    CSV = __RDIR__+'/simplesensor.csv'
    SAMPLE_LENGTH = SAMPLE_LENGTH_slow
    from pandas import DataFrame
    columns='SERIAL,TYPE,TIME,LOC,PM1,PM3,PM10,T,RH,BINS,SP,RC,UNIXTIME'.split(',')
    # inefficient I know, but it will only be used for testing
from .SensorMod import upload
from .SensorMod import gps
from .SensorMod import R1

########################################################
##  Setup
########################################################
try:
    gpsdaemon = gps.init(wait=False)
    TYPE = 2
    log.info("GPS Connected - Running in portable mode")
    if OLED_module : oled.standby(message = "   --  Portable  --   ")
except:
    log.info("No GPS connected - Running in stationary mode")
    if OLED_module : oled.standby(message = "   -- Stationary --   ")
if not gpsdaemon:
    log.warning('NO GPS FOUND!')
    if OLED_module : oled.standby(message = "   -- NO GLONASS --   ")
alpha = R1.alpha
loading = power.blink_nonblock_inf()



def interrupt(channel):
    log.warning("Pull Down on GPIO 21 detected: exiting program")
    global STOP
    STOP = True

GPIO.add_event_detect(21, GPIO.RISING, callback=interrupt, bouncetime=300)

log.info('########################################################')
log.info('starting {}'.format(datetime.now()))
log.info('########################################################')


R1.clean(alpha)

while loading.isAlive():
    log.debug('stopping loading blink ...')
    power.stopblink(loading)
    loading.join(.1)


########################################################
## Check for pre-existing LAST_SAVE value
########################################################

if os.path.exists(os.path.join(__RDIR__,'.uploads')):
    with open (os.path.join(__RDIR__,'.uploads'),'r') as f:
        lines = f.readlines()
    for line in lines:
        if 'LAST_SAVE = ' in line:
            LAST_SAVE = line[12:].strip()
    if LAST_SAVE == None:
        with open (os.path.join(__RDIR__,'.uploads'),'a') as f:
            f.write('LAST_SAVE = None\n')
        LAST_SAVE = 'None'
else:
    with open (os.path.join(__RDIR__,'.uploads'),'w') as f:
        f.write("LAST_SAVE = None\n")
    LAST_SAVE = 'None'

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
    while time.time()-start < SAMPLE_LENGTH
        now = datetime.utcnow()
        pm = R1.poll(alpha)

        if float(pm['PM1'])+float(pm['PM10'])  > 0:
            # if there are results.

            if DHT_module: rh,temp = DHT.read()
            else:
                temp = pm['Temperature']
                rh   = pm[  'Humidity' ]

            if TYPE == 2:
                loc = gps.last.copy()
            else:
                loc = {'gpstime':now.strftime("%H%M%S"),'lat':lat,'lon':lon,'alt':alt}

            unixtime = int(datetime.utcnow().strftime("%s")) # to the second

            bins = pickle.dumps([float(pm['Bin %s'%i]) for i in range(16)])

            results.append( [
                SERIAL,
                TYPE,
                loc['gpstime'][:6],
                scramble(('%(lat)s_%(lon)s_%(alt)s'%loc).encode('utf-8')),
                float(pm['PM1']),
                float(pm['PM2.5']),
                float(pm['PM10']),
                float(temp),
                float(rh),
                bins,
                float(pm['Sampling Period']),
                int(pm['Reject count glitch']),
                unixtime,
            ] )

            if OLED_module:
                now = str(datetime.utcnow()).split('.')[0]
                oled.updatedata(now,results[-1])

        if STOP:break
        time.sleep(1) # keep as 1

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

    if SAMPLE_LENGTH>0:
        power.ledoff()

        ## run cycle
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

        #if DEBUG:
                # if bserial : os.system("screen -S ble -X stuff 'sudo echo \"%s\" > /dev/rfcomm1 ^M' " %'_'.join([str(i) for i in d[-1]]))



        power.ledon()

    if STOP:break

    hour = datetime.now().hour

    if CSV:
        log.debug('CSV - skipping conditionals')

    elif (hour > SCHOOL[0]) and (hour < SCHOOL[1]):

        log.debug('@School, hour={}'.format(hour))
        ''' at school - try upload'''
        ''' rfkill block wifi; to turn it on, rfkill unblock wifi. For Bluetooth, rfkill block bluetooth and rfkill unblock bluetooth.'''

        DATE = date.today().strftime("%d/%m/%Y")

        if DATE != LAST_SAVE:

            if TYPE == 2:
                if gpsdaemon.is_alive() == False: gpsdaemon = gps.init(wait=False)

            if upload.connected():
                if OLED_module: oled.standby(message = "   --  uploading  --   ")
                #check if connected to wifi
                loading = power.blink_nonblock_inf_update()
                ## SYNC
                try:
                    upload_success = upload.sync(SERIAL,__RDIR__)
                except Exception as e:
                    log.error("Error in attempting staging upload to serverpi - {}".format(e))
                    upload_success = False
                if upload_success:
                    cursor=db.conn.cursor()
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                    table_list=[]
                    for table_item in cursor.fetchall():
                        table_list.append(table_item[0])
                    for table_name in table_list:
                        log.debug('Dropping table : '+table_name)
                        db.conn.execute('DROP TABLE IF EXISTS ' + table_name)

                    log.info('rebuilding db')
                    builddb.builddb(db.conn)

                    log.debug('upload complete {} {}'.format(DATE, hour))

                    with open (os.path.join(__RDIR__,'.uploads'),'r') as f:
                        lines=f.readlines()
                    with open (os.path.join(__RDIR__,'.uploads'),'w') as f:
                        for line in lines:
                            f.write(sub(r'LAST_SAVE = '+LAST_SAVE, 'LAST_SAVE = '+DATE, line))

                    LAST_SAVE = DATE
                    log.debug('LAST_SAVE = {}'.format(LAST_SAVE))

                while loading.isAlive():
                    power.stopblink(loading)
                    loading.join(.1)


    elif (hour < SCHOOL[0]) or (hour > SCHOOL[1]):

        if upload.online():

            ## update time!
            log.info(os.popen('sudo timedatectl &').read())

            ## run git pull
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
