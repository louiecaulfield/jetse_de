#!/usr/bin/env python3
import argparse
import serial
import struct
from termcolor import colored
from pythonosc import udp_client
from pythonosc.osc_message_builder import OscMessageBuilder

# parser = argparse.ArgumentParser()
packet_format = '<HBBLLLfffB'
packet_size = struct.calcsize(packet_format)

class Packet():
    def __init__(self, id:int, time:int,
                 knock: bool, knock_time:int,
                 motion: bool, motion_time: int, acc:tuple[float, float, float]):
        self.id = id
        self.time = time

        self.knock = knock
        self.knock_time = knock_time

        self.motion = motion
        self.motion_time = motion_time
        self.acc = acc

    def __repr__(self) -> str:
        str = f"[{self.id} - {self.time} ms"
        # if self.knock:
        str += f" - KNOCK @{self.knock_time}ms "
        # if self.motion:
        str += f" - MOTION @{self.motion_time}ms" + \
                    "<" + ",".join([f"{v:5.2f}" for v in self.acc]) + ">"
        str += "]"
        return str

    @classmethod
    def from_bytes(cls, buf) -> "Packet":
        (magic, id, flags, \
            time, time_last_knock, time_last_motion,
            acc_x, acc_y, acc_z, checksum_exp) = struct.unpack(packet_format, buf)

        if magic != 0xE1BA:
            print(f"Unexpected magic {magic:04X}")
            return None

        checksum = sum(buf[2:-1]) & 0xff
        if checksum != checksum_exp:
            print(f"Unexpected checksum {checksum:02X} != {checksum_exp:02X}")
            return None

        return cls(id, time,
                flags & 0x2, time_last_knock,
                flags & 0x1, time_last_motion, (acc_x, acc_y, acc_z))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", default="127.0.0.1",
        help="The ip of the OSC server")
    parser.add_argument("--port", type=int, default=5005,
        help="The port the OSC server is listening on")
    args = parser.parse_args()

    client = udp_client.SimpleUDPClient(args.ip, args.port)

    port = "/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0"
    ser = serial.Serial(port, 115200)
    ser.close()
    ser.open()
    while(True):
        packet = Packet.from_bytes(ser.read(packet_size))
        prefix = f"/foot/{packet.id}"
        message = {
            "/time": packet.time,
            "/knock": packet.knock,
            "/knock_time": packet.knock_time,

            "/motion": packet.motion,
            "/motion_time": packet.motion,

        }
        for k,v in message.items():
            client.send_message(prefix + k, v)
        msg_acc = OscMessageBuilder(prefix + "/acc")
        [msg_acc.add_arg(x) for x in packet.acc]
        client.send(msg_acc.build())
        print(colored(str(packet), 'red' if packet.motion else 'green' if packet.knock else 'white'))
