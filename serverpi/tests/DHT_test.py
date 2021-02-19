from ..SensorMod import DHT

counter = 20
while counter:

    humidity, temperature = DHT.read()

    if humidity is not None and temperature is not None:
        print("Temp={0:0.1f}*C  Humidity={1:0.1f}%".format(temperature, humidity))
        counter -= 1
    else:
        print("Failed to retrieve data from humidity sensor")
