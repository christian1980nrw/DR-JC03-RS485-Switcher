import serial
import time
import logging
import subprocess

logging.basicConfig(level=logging.INFO, format='%(message)s')

debug_output = 0  # Define this if you plan to use it

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

def process_data(data):
    if len(data) < 10:
        print("Invalid data length.")
        return
    
    received_chksum = int(data[-4:], 16)
    calc_chksum = chksum_data(data[2:-4])
    
    if calc_chksum != received_chksum:
        print("Checksum error. Calculated: {}, Received: {}".format(calc_chksum, received_chksum))
        return

    print("Checksum is ok.")

    data = data[:-4]
    for i in range(0, len(data), 4):
        print("Received 4 bytes of data: " + data[i:i+4])


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
HEATER_ON = 1
SOC = 0.0
SOH = 0.0
capacity = 0.0
voltage = 0.0
sent_index = 0
heater = HEATER_OFF
sent = [
    '~22014A42E00201FD28\r',
    '~22014A42E00201FD28\r',
    '~22014A42E00201FD28\r', # Try 3 times the normal request, maybe there was only a fragmented packet.
    '~22014A4D0000FD8E\r', # Use 3 different requests like the original windows software is doing (maybe BMS reset?)
    '~22014A510000FDA0\r',
    '~22014A47E00201FD23\r', # start from the beginning after this
]
ser_port = '/dev/ttyUSB0'

# Wait for the system to be started
time.sleep(5)

# Stop serial communication on the specified port (Victron Venus OS specific)
subprocess.call(['/opt/victronenergy/serial-starter/stop-tty.sh', ser_port])

# Wait for the serial communication to stop
time.sleep(2)

# Open the serial port for communication
ser = serial.Serial(ser_port, 9600)

HEATER_OFF_SOC_THRESHOLD = 95.5   # Threshold for turning off the heater depending on SOC
HEATER_ON_SOC_THRESHOLD = 99.75   # Threshold for turning on the heater based on SOC
HEATER_OFF_VOLT_THRESHOLD = 54.7  # Threshold for turning off the heater depending on voltage
HEATER_ON_VOLT_THRESHOLD = 55.3   # Threshold for turning on the heater based on voltage
use_SOC_for_control = True       # Flag to determine if SOC should be used for control, set to False to use voltage
# Note: Use of voltage is recommended because the DR-JC03 sometimes shows wrong SOC values especially if the last full cycle is long ago.

is_turned_on = True  # Flag to track if turn on script has been executed
is_turned_off = True  # Flag to track if turn off script has been executed
previous_SOC = 0.0  # Variable to store previous SOC value
previous_VOLT = 0.0  # Variable to store previous voltage value
valid_data_received = False  # Flag to track if valid data has been received

while True:
    rcv = ''  # Initialize rcv variable for each new request
    sent_index = 0 if valid_data_received else sent_index  # Use the same index if valid data has been received
    valid_data_received = False  # Reset the flag for each new request

    while True:
        rcv = ''  # Clear rcv variable before receiving new data

        ser.write(sent[sent_index].encode())
        logging.info('Request sent: {}'.format(sent[sent_index]))
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
            calculated_chksum = chksum_data(rcv[1:len(rcv)-5])
            if calculated_chksum == chksum:
                logging.info('Checksum ok.')
            else:
                logging.error('Checksum error. Calculated: {}, Received: {}'.format(calculated_chksum, chksum))
                valid_data = -1

        except Exception as e:
            logging.error('Exception during checksum calculation: {}'.format(e))
            valid_data = -1

        if valid_data == 1:
            valid_data_received = True
            data = rcv[13:len(rcv)-5]
            if len(data) >= 118:
                SOH = int(data[114:118], base=16) / 1
                SOC = int(data[2:6], base=16) / 100
                voltage = int(data[6:10], base=16) / 100
                current = int(data[106:110], base=16)
                mos_temp = int(data[84:88], base=16) / 10 #98
                env_temp = int(data[76:80], base=16) / 10 #90
                cell_temp = int(data[80:84], base=16) / 10 #90
                temp1 = int(data[90:94], base=16) / 10 #104
                temp2 = int(data[94:98], base=16) / 10 #108
                temp3 = int(data[98:102], base=16) / 10 #112
                temp4 = int(data[102:106], base=16) / 10 #116
                capacity = int(data[124:128], base=16) / 100 #138
                if current > 32767:
                    current = -(32768-(current - 32768))
                current /= 100
                logging.info('--------------------------------')
                logging.info('Capacity:  {}Ah remaining'.format(capacity))
                logging.info('SOH:       {}%'.format(SOH))
                logging.info('SOC:       {}%'.format(SOC))
                logging.info('Voltage:   {}V'.format(voltage))
                logging.info('Current:   {}A'.format(current))
                logging.info('MOS Temp:  {}°C'.format(mos_temp))
                logging.info('Env Temp:  {}°C'.format(env_temp))
                logging.info('Cell Temp: {}°C'.format(cell_temp))
                logging.info('Temp 1:    {}°C'.format(temp1))
                logging.info('Temp 2:    {}°C'.format(temp2))
                logging.info('Temp 3:    {}°C'.format(temp3))
                logging.info('Temp 4:    {}°C'.format(temp4))
                logging.info('--------------------------------')
                # Extract cell voltages
                cell_voltages = []
                for i in range(1, 17):
                    cell_voltage = int(data[(i - 1) * 4 + 12: i * 4 + 12], base=16) / 1000
                    cell_voltages.append(cell_voltage)
                    logging.info('Cell {}: {}V'.format(i, cell_voltage))
            else:
                logging.error('Invalid data format: SOH not found')
                continue

        # Check if the heater is already off based on SOC or voltage
        if (heater == HEATER_OFF) and ((use_SOC_for_control and SOC <= HEATER_OFF_SOC_THRESHOLD) or (not use_SOC_for_control and voltage <= HEATER_OFF_VOLT_THRESHOLD)) and not is_turned_off:
            logging.info('Heater OFF.')
            is_turned_off = True
            is_turned_on = False  # Reset is_turned_on flag
            subprocess.call("/data/turnoff.sh", shell=True)  # Turn off the heater using shell script
            logging.info('is_turned_off: {}'.format(is_turned_off))

        # Check if the heater is already on based on SOC or voltage
        elif (heater == HEATER_ON) and ((use_SOC_for_control and SOC >= HEATER_ON_SOC_THRESHOLD) or (not use_SOC_for_control and voltage >= HEATER_ON_VOLT_THRESHOLD)) and not is_turned_on:
            logging.info('Heater ON.')
            is_turned_on = True
            is_turned_off = False  # Reset is_turned_off flag
            subprocess.call("/data/turnon.sh", shell=True)  # Turn on the heater using shell script
            logging.info('is_turned_on: {}'.format(is_turned_on))

        # Check if the heater needs to be turned off based on SOC or voltage
        elif (heater == HEATER_ON) and ((use_SOC_for_control and SOC <= HEATER_OFF_SOC_THRESHOLD) or (not use_SOC_for_control and voltage <= HEATER_OFF_VOLT_THRESHOLD)) and is_turned_on:
            heater = HEATER_OFF
            logging.info('Heater OFF.')
            subprocess.call("/data/turnoff.sh", shell=True)  # Turn off the heater using shell script
            is_turned_off = True
            is_turned_on = False
            logging.info('is_turned_off: {}'.format(is_turned_off))

        # Check if the heater needs to be turned on based on SOC or voltage
        elif (heater == HEATER_OFF) and ((use_SOC_for_control and SOC >= HEATER_ON_SOC_THRESHOLD) or (not use_SOC_for_control and voltage >= HEATER_ON_VOLT_THRESHOLD)) and is_turned_off:
            heater = HEATER_ON
            logging.info('Heater ON.')
            subprocess.call("/data/turnon.sh", shell=True)  # Turn on the heater using shell script
            is_turned_on = True
            is_turned_off = False
            logging.info('is_turned_on: {}'.format(is_turned_on))

            logging.info('--------------------------------')

        else:
            logging.info('--------------------------------')

        previous_SOC = SOC  # Store current SOC as previous SOC
        previous_VOLT = voltage  # Store current voltage as previous voltage

        sent_index = sent_index if valid_data_received else sent_index + 1  # Use the same index if valid data has been received, else use next index
        sent_index = sent_index % len(sent)  # Ensuring sent_index is within the range

    ser.close()
    time.sleep(120)
    #os.system('reboot')
