'''
scripts to run if connected online
'''
import os
from ..log_manager import getlog
log = getlog(__name__)
print = log.print ## replace print function with a wrapper

def online():

    cmd = '''
    PINGS=2
    TESTIP=8.8.8.8
    if ( ping -c $PINGS $TESTIP > /dev/null ) then
        echo "1"
    else
        echo "0"
    fi
    '''

    return int(os.popen(cmd).read())


def buildtables(conn):

    conn.execute('''
                 CREATE TABLE MEASUREMENTS
                 (
                     SERIAL       CHAR(16)    NOT NULL,
                     TYPE         INT         NOT NULL,
                     TIME         CHAR(6)     NOT NULL,
                     LOC          BLOB        NOT NULL,
                     PM1          REAL        NOT NULL,
                     PM3          REAL        NOT NULL,
                     PM10         REAL        NOT NULL,
                     T            REAL        NOT NULL,
                     RH           REAL        NOT NULL,
                     SP           REAL        NOT NULL,
                     RC           INT         NOT NULL,
                     UNIXTIME     INT         NOT NULL
                     );
                 ''')

    conn.execute('''
                 CREATE TABLE PUSH
                 (
                    SERIAL       CHAR(16)    NOT NULL,
                    TIME         CHAR(6)     NOT NULL,
                    DATE         CHAR(8)     NOT NULL
                    );
                ''')

    conn.commit()

    return

def stage(SERIAL,__RDIR__):

    import sqlite3
    from datetime import datetime, date

    DATE = date.today().strftime("%d%m%Y")
    TIME = datetime.utcnow().strftime("%H%M%S")
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")

    hostname = os.popen('hostname').read().strip()

    newfilename = 'server_'+hostname+'_'+timestamp+'.db'
    newfiledir = '/home/serverpi/datastaging'

    file_name = os.path.join(__RDIR__,'server.db')

    if not os.path.exists(newfiledir):
        os.makedirs(newfiledir)

    newfile = os.path.join(newfiledir,newfilename)

    if os.path.exists(newfile):
        os.remove(newfile)

    try:
        conn_dest = sqlite3.connect(newfile)
    except:
        print("Unable to create new file")
        return False

    try:
        buildtables(conn_dest)
    except:
        print("Unable to write to new db")
        conn_dest.close()
        return False

    cursor_dst = conn_dest.cursor()

    cursor_dst.execute("SELECT name FROM sqlite_master WHERE type='table';")

    table_list=[]
    for table_item in cursor_dst.fetchall():
        table_list.append(table_item[0])

    cmd = "attach ? as toMerge"
    cursor_dst.execute(cmd, (os.path.join(__RDIR__,'server.db'), ))

    for table_name in table_list:

        try:
            cmd = "INSERT INTO {0} SELECT * FROM toMerge.{0};".format(table_name)
            cursor_dst.execute(cmd)
            conn_dest.commit()
            success = True
        except sqlite3.OperationalError:
            print("ERROR!: Merge Failed for " + table_name)
            success = False
        finally:
            if table_name == table_list[-1]:
                cmd = "detach toMerge"
                cursor_dst.execute(cmd, ())

    if not success:
        conn_dest.close()
        return success

    else:
        data = [(SERIAL,TIME,DATE,)]

        try:
            conn_dest.executemany("INSERT INTO PUSH (SERIAL,TIME,DATE) VALUES(?, ?, ?);", data )

            conn_dest.commit()

        except:
            print ("Error! Could not write staging data to PUSH table at {}".format(timestamp))
            success = False

        conn_dest.close()

    return success


#def stage(SERIAL,conn):
#
#    from shutil import copy2
#    from datetime import datetime, date
#
#    DATE = date.today().strftime("%d%m%Y")
#    TIME = datetime.utcnow().strftime("%H%M%S")
#
#    data = [(SERIAL,TIME,DATE,)]
#
#    conn.executemany("INSERT INTO PUSH (SERIAL,TIME,DATE) VALUES(?, ?, ?);", data )
#
#    conn.commit()
#
#    filename = 'server.db'
#
#    # if we are root, write to root dir
#    user = os.popen('echo $USER').read().strip()
#
#    if user == 'root': __RDIR__ = '/root'
#    else: __RDIR__ = '/home/'+user
#
#    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
#
#    uploadfile = '.'.join(filename.split('.')[:-1])+timestamp+'.'+filename.split('.')[-1]
#
#    try:
#        copy2(os.path.join(__RDIR__,filename),os.path.join('/home/serverpi/datastaging',uploadfile))
#    except:
#        print ('Error copying server.db file to staging area')
#        return False
#
#    return True

def upload():

    from .sqlMerge import sqlMerge
    from glob import glob

    merge=sqlMerge()

    dataloc = '/home/serverpi/datastaging'

    sensorfiles = glob(os.path.join(dataloc,'sensor*.db'))

    serverfiles = glob(os.path.join(dataloc,'server*.db'))

    if len (serverfiles) > 1:
        for file in serverfiles[1:]:
            sensorfiles.append(file)
    elif len (serverfiles) < 1:
        print ("Could not find server.db file for merge")
        return False

    print (serverfiles[0])
    print (sensorfiles)

    #Merge the various DB and upload to AWS
    success = merge.mergelist(serverfiles[0], sensorfiles)

    if success:
        return True
    else:
        return False
