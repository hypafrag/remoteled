import serial
import struct
import random
import time


def open_serial(name):
    return serial.Serial(name, baudrate=115200, bytesize=serial.EIGHTBITS,
                         parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE,
                         timeout=None, exclusive=True)


def write_pic(port, pic):
    data = b''
    for px in pic:
        data += struct.pack('BBB', *px)
    port.write(data)


def main():
    with open_serial('COM12') as port:
        while True:
            pic = []
            for i in range(300):
                pic.append((random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)))
            write_pic(port, pic)
            time.sleep(0.4)
    return 0


if __name__ == '__main__':
    exit(main())
