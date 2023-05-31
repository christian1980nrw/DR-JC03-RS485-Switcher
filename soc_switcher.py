import serial
import time
import datetime
import logging
import ftplib
import os
import subprocess

logging.basicConfig(level=logging.INFO, format='%(message)s')

def chksum_data(str):
    result = 0
    for datacheck in str:
        result = result + ord(datacheck)
    result = result ^ 0xFFFF
    return result + 1

def Lchksum(value):
    value = value & 0x0FFF
    n1 = value & 0xF
    n2 = (value >> 4) & 0xF
    n3 = (value >> 8) & 0xF
    chksum = ((n1 + n2 + n3) & 0xF) ^ 0xF
    chksum = chksum + 1
    return value + (chksum << 12)

def CID2_decode(CID2):
    if CID2 == '00':
        logging.info('CID2 response ok.')
        return 0
    elif CID2 == '01':
        logging.error('VER error.')
    elif CID2 == '02':
        logging.error('CHKSUM error.')
    elif CID2 == '03':
        logging.error('LCHKSUM error.')
    elif CID2 == '04':
        logging.error('CID2 invalid.')
    elif CID2 == '05':
        logging.error('Command format error.')
    elif CID2 == '06':
        logging.error('INFO data invalid.')
    elif CID2 == '90':
        logging.error('ADR error.')
    elif CID2 == '91':
        logging.error('Battery communication error.')
    return -1

logging.info('--------------------------------')
HEATER_OFF = 1
HEATER_ON = 0
heater = HEATER_OFF
sent = b'~22014A42E00201FD28\r'
ser_port = '/dev/ttyUSB0'

# Wait for the system to be started
time.sleep(5)

# Stop serial communication on the specified port (Victron Venus OS specific)
subprocess.call(['/opt/victronenergy/serial-starter/stop-tty.sh', ser_port])

# Wait for the serial communication to stop
time.sleep(2)

# Open the serial port for communication
ser = serial.Serial(ser_port, 9600)

HEATER_OFF_SOC_THRESHOLD = 97.5   # Threshold for turning off the heater depending on SOC
HEATER_ON_SOC_THRESHOLD = 99.75   # Threshold for turning on the heater based on SOC
HEATER_OFF_VOLT_THRESHOLD = 52.85 # Threshold for turning off the heater depending on voltage
HEATER_ON_VOLT_THRESHOLD = 54.4   # Threshold for turning on the heater based on voltage
use_SOC_for_control = False       # Flag to determine if SOC should be used for control, set to False to use voltage
# Note: Use of voltage is recommended because the DR-JC03 sometimes shows wrong SOC values especially if the last full cycle is long ago.

is_turned_on = False  # Flag to track if turn on script has been executed
is_turned_off = False  # Flag to track if turn off script has been executed
previous_SOC = 0.0  # Variable to store previous SOC value
previous_VOLT = 0.0  # Variable to store previous voltage value


while True:
    rcv = ''
    ser.write(sent)
    logging.info('Request sent: {}'.format(datetime.datetime.now()))
    time.sleep(4)
    while ser.inWaiting() > 0:
        try:
            chr = ser.read()
            rcv += chr.decode()
            if chr == b'\r':
                break
        except:
            pass

    valid_data = 1
    try:
        CID2 = rcv[7:9]
        if CID2_decode(CID2) == -1:
            valid_data = -1
    except:
        valid_data = -1

    logging.info('Received data: {}'.format(rcv))

    try:
        LENID = int(rcv[9:13], base=16)
        length = LENID & 0x0FFF
        if Lchksum(length) == LENID:
            logging.info('Data length ok.')
        else:
            logging.error('Data length error.')
            valid_data = -1
    except:
        valid_data = -1

    try:
        chksum = int(rcv[len(rcv)-5:], base=16)
        if chksum_data(rcv[1:len(rcv)-5]) == chksum:
            logging.info('Checksum ok.')
        else:
            logging.error('Checksum error.')
            valid_data = -1
    except:
        valid_data = -1

    if valid_data == 1:
        data = rcv[13:len(rcv)-5]
        SOC = int(data[2:6], base=16) / 100
        voltage = int(data[6:10], base=16) / 100
        current = int(data[106:110], base=16)
        if current > 32767:
            current = -(32768-(current - 32768))
        current /= 100
        logging.info('--------------------------------')
        logging.info('SOC:     {}%'.format(SOC))
        logging.info('Voltage: {}V'.format(voltage))
        logging.info('Current: {}A'.format(current))
        logging.info('--------------------------------')

        # Check if the heater is already off based on SOC or voltage
        if (heater == HEATER_OFF) and (previous_SOC > HEATER_OFF_SOC_THRESHOLD) and (previous_VOLT > HEATER_OFF_VOLT_THRESHOLD) and (use_SOC_for_control and SOC <= HEATER_OFF_SOC_THRESHOLD) or (not use_SOC_for_control and voltage <= HEATER_OFF_VOLT_THRESHOLD) and not is_turned_off:
            logging.info('Heater OFF.')
            is_turned_off = True
            subprocess.call("/data/turnoff.sh", shell=True)  # Turn off the heater using shell script
            logging.info('is_turned_off: {}'.format(is_turned_off))

        # Check if the heater is already on based on SOC or voltage
        elif (heater == HEATER_ON) and (previous_SOC < HEATER_ON_SOC_THRESHOLD) and (previous_VOLT < HEATER_ON_VOLT_THRESHOLD) and (use_SOC_for_control and SOC >= HEATER_ON_SOC_THRESHOLD) or (not use_SOC_for_control and voltage >= HEATER_ON_VOLT_THRESHOLD) and not is_turned_on:
            logging.info('Heater ON.')
            is_turned_on = True
            subprocess.call("/data/turnon.sh", shell=True)  # Turn on the heater using shell script
            logging.info('is_turned_on: {}'.format(is_turned_on))

        # Check if the heater needs to be turned off based on SOC or voltage
        elif (heater == HEATER_ON) and ((use_SOC_for_control and SOC <= HEATER_OFF_SOC_THRESHOLD) or (not use_SOC_for_control and voltage <= HEATER_OFF_VOLT_THRESHOLD)) and not is_turned_off:
            heater = HEATER_OFF
            logging.info('Heater OFF.')
            subprocess.call("/data/turnoff.sh", shell=True)  # Turn off the heater using shell script
            is_turned_off = True
            logging.info('is_turned_off: {}'.format(is_turned_off))

        # Check if the heater needs to be turned on based on SOC or voltage
        elif (heater == HEATER_OFF) and ((use_SOC_for_control and SOC >= HEATER_ON_SOC_THRESHOLD) or (not use_SOC_for_control and voltage >= HEATER_ON_VOLT_THRESHOLD)) and not is_turned_on:
            heater = HEATER_ON
            logging.info('Heater ON.')
            subprocess.call("/data/turnon.sh", shell=True)  # Turn on the heater using shell script
            is_turned_on = True
            logging.info('is_turned_on: {}'.format(is_turned_on))

        logging.info('--------------------------------')

    else:
        logging.info('Invalid data.\n----------------------')

    previous_SOC = SOC  # Store current SOC as previous SOC
    previous_VOLT = voltage  # Store current voltage as previous voltage

ser.close()
time.sleep(120)
#os.system('reboot')
