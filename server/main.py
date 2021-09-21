import serial
import serial.tools.list_ports
import struct
import random
import time
import sys

ARDUINO_VID = 0x2341
ARDUINO_LEONARDO_PID = 0x8036


def open_serial(name):
    return serial.Serial(name, baudrate=115200, bytesize=serial.EIGHTBITS,
                         parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE,
                         timeout=None, exclusive=True)


def write_pic(port, pic):
    data = b''
    for px in pic:
        data += struct.pack('BBB', *px)
    print('write started')
    port.write(data)
    print('write finished')


def main(port_name):
    with open_serial(port_name) as port:
        while True:
            pic = []
            for i in range(300):
                pic.append((random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)))
            write_pic(port, pic)
            time.sleep(1)
    return 0


if __name__ == '__main__':
    detected_ports = [p.device
                      for p in serial.tools.list_ports.comports()
                      if p.vid == ARDUINO_VID and p.pid == ARDUINO_LEONARDO_PID]

    print('UART:', *detected_ports, file=sys.stderr)

    exit(main(detected_ports[0]))
