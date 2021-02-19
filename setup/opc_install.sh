sudo apt-get -y update;
sudo apt-get -y upgrade;

sudo apt-get install -y python-dev python3-dev;
sudo apt-get install -y python-rpi.gpio python3-rpi.gpio ;
sudo apt-get install -y git python3-pip;
sudo apt-get install -y python-serial python3-serial;
# sudo apt-get install -y python-spidev python3-spidev;
sudo apt-get install -y python-smbus;
sudo apt-get install -y i2c-tools;
sudo apt-get install -y python3-ipython;
sudo apt-get install -y screen;


git submodule update --init --recursive;
pip3 install pyusbiss;
pip3 install git+https://github.com/doceme/py-spidev.git;

cd py-opc-R1 && sudo python3 setup.py develop ; cd -

pip3 install db-sqlite3;
pip3 install cryptography;

pip3 install wifindme;
sudo apt-get install ntp --yes ;


sudo timedatectl set-ntp true
pip3 install Adafruit_DHT;
pip3 uninstall numpy -y;
sudo apt-get install python3-numpy --yes ;
pip3 install pandas;
pip3 install boto3; # for uploading data to aws
pip3 install adal
pip3 install Office365-REST-Python-Client==2.2.2 # for uploading data to sharepoint


#/dev/ttyS0 is owned by the user root and the group dialout, so to be able to acesss the serial device, I would add myself to the dialout group:

sudo usermod -a -G tty $USER ;
sudo chmod 666 /dev/ttyS0 ;

sudo apt autoremove -y;
echo 'finished'

python3 -m serverpi.db new;
cd serverpi && python3 runtests.py;


sudo reboot;
