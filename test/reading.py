#!/usr/bin/env python3
import argparse
import serial
import collections
import struct
from statistics import mean
from termcolor import colored
from pythonosc import udp_client
from pythonosc.osc_message_builder import OscMessageBuilder
import pythonosc.osc_server as osc_server
import threading
from pythonosc.dispatcher import Dispatcher
import queue

import asyncio

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

class Config():
    def __init__(self, channel: int, threshold: int):
        self.channel = channel & 0xff
        self.threshold = threshold & 0xff

    def bytes(self) -> bytes:
        payload = [0xE1, 0xBA, self.channel, self.threshold]
        payload.append(sum(payload) & 0xff)
        return bytes(payload)

config_q = queue.Queue()
def foot_handler(address, *args):
    print(f"{address}: {args} {len(args)}")
    if(len(args) != 2):
        print("/foot/threshold needs exactly 2 arguments")
        return

    if(not isinstance(args[0], int)):
        print("Argument 0 should be integer")
        return

    if(not isinstance(args[1], float)):
        print("Argument 1 should be float")
        return

    config_q.put(Config(args[0], (int)(args[1] * 255)).bytes())



dispatcher = Dispatcher()
dispatcher.map("/foot/threshold", foot_handler)

def start_server(ip, port):
    print("Starting Server")
    server = osc_server.ThreadingOSCUDPServer(
        (ip, port), dispatcher)
    print("Serving on {}".format(server.server_address))
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    return thread

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", default="127.0.0.1",
        help="The ip to connect to")
    parser.add_argument("--listen", type=int, default=5008,
        help="The port to listen on")
    parser.add_argument("--send", type=int, default=5005,
        help="The port to send to")
    args = parser.parse_args()

    server_thread = start_server(args.ip, args.listen)
    client = udp_client.SimpleUDPClient(args.ip, args.send)

    port = "/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0"
    ser = serial.Serial(port, 115200)
    ser.close()
    ser.open()

    deltas = collections.deque([1], maxlen=100)
    last_time = 0
    config = Config(1, 5)
    try:
        while(True):
            if not config_q.empty():
                ser.write(config_q.get())

            packet = Packet.from_bytes(ser.read(packet_size))

            if last_time != 0:
                deltas.append(packet.time - last_time)
            last_time = packet.time

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
            # if packet.motion or packet.knock:
            print(colored(f"{1e3/mean(deltas):5.2f}Hz", 'yellow') + colored(str(packet), 'red' if packet.motion else 'green' if packet.knock else 'white'))
            # if packet.motion:
            #     client.send_message("/cue/3/start", 1)
            # if packet.knock:
            #     client.send_message("/cue/4/start", 1)
    except KeyboardInterrupt:
        print("CTRL-C hit, ending")

    server_thread.stop()
