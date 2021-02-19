#from .. import R1
from ..SensorMod.R1 import alpha,info,poll,keep
import time,sys

if sys.version[0] != '3':
    sys.exit('Unfortunately this code was written for py3k, \n feel free to update it through on https://github.com/wolfiex/BBSensor')



print('starting test')

print(info(alpha))



print('turning on for 10')
alpha.on()
time.sleep(10)
print('turning off')
alpha.off()



print ('onoff')
for i in range(5):
    print (i)
    alpha.on()
    d = poll(alpha)
    alpha.off()

    print(d)



print ('onstay')
alpha.on()
for i in range(10):
    print (i)
    d = poll(alpha)
    print(d)
alpha.off()
