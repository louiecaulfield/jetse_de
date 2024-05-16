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
import time

import asyncio

packet_format = '<HBLLhhhBB'
packet_size = struct.calcsize(packet_format)

motion_keys =  ["z_pos", "z_neg", "y_pos", "y_neg", "x_pos", "x_neg"]
motion_keys_short =  ["Z", "z", "Y", "y", "X", "x"]

class Packet():
    def __init__(self, id:int, time:int,
                 motion: list[bool], motion_time: int, acc:tuple[float, float, float]):
        self.id = id
        self.time = time
        self.motion = motion
        self.motion_time = motion_time
        self.acc = acc

    def __repr__(self) -> str:
        motion_str = "".join([motion_keys_short[i] if v else " " for i, v in enumerate(self.motion)])

        str = f"[{self.id} - {self.time:10d} ms"
        # if self.motion:
        str += f" - MOTION @{self.motion_time:10d}ms" + \
                    "<" + ",".join([f"{v:7d}" for v in self.acc]) + f"> {motion_str}"
        str += "]"
        return str

    @classmethod
    def from_bytes(cls, buf) -> "Packet":
        (magic, id, time,
            time_last_motion,
            acc_x, acc_y, acc_z,
            motion_status,
            checksum_exp) = struct.unpack(packet_format, buf)

        if magic != 0xE1BA:
            print(f"Unexpected magic {magic:04X}")
            return None

        checksum = sum(buf[2:-1]) & 0xff
        if checksum != checksum_exp:
            print(f"Unexpected checksum {checksum:02X} != {checksum_exp:02X}")
            return None

        return cls(id, time,
                    [(motion_status & (1 << i) != 0) for i in range(8)][2:],
                    time_last_motion,
                    (acc_x, acc_y, acc_z))

class Config():
    def __init__(self, channel: int, threshold: int):
        self.channel = channel & 0xff
        self.threshold = threshold & 0xff

    def bytes(self) -> bytes:
        payload = [0xE1, 0xBA, self.channel, self.threshold]
        payload.append(sum(payload) & 0xff)
        return bytes(payload)

    def __repr__(self):
        return f"<Config:CH{self.channel}:THR{self.threshold}>"

config_q = queue.Queue()
def foot_handler(address, *args):
    if(len(args) != 2):
        print("/foot/threshold needs exactly 2 arguments")
        return

    if(isinstance(args[0], str)):
        channel = int(args[0])

    if(isinstance(args[0], int)):
        channel = args[0]

    if(channel < 0):
        print(f"Unable to parse channel from {args[0]}")
        return

    if(not isinstance(args[1], float)):
        print("Argument 1 should be float")
        return

    config = Config(channel, (int)(args[1] * 255))
    print("Config update: " + str(config))
    config_q.put(config.bytes())



dispatcher = Dispatcher()
dispatcher.map("/foot/threshold", foot_handler)
qlab_queue_last_time = {}

TRIGGER_TIME = 100 #ms
REPEAT_TIME = 500 #ms
QLAB_REPEAT = 200 / 1000
colors = ['blue', 'red']

def start_server(ip, port):
    print("Starting Server")
    server = osc_server.ThreadingOSCUDPServer(
        (ip, port), dispatcher)
    print("Serving on {}".format(server.server_address))
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    return server

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", default="127.0.0.1",
        help="The ip to connect to")
    parser.add_argument("--listen", type=int, default=5008,
        help="The port to listen on")
    parser.add_argument("--send", type=int, default=5005,
        help="The port to send to")
    parser.add_argument("port", type=str,
        help="The serial port")
    args = parser.parse_args()

    server = start_server("127.0.0.1", args.listen)
    client_local = udp_client.SimpleUDPClient("127.0.0.1", 5005)
    client = udp_client.SimpleUDPClient(args.ip, args.send)

    ser = serial.Serial(args.port, 115200)
    ser.close()
    ser.open()

    deltas = collections.deque([1], maxlen=100)
    last_times = {}
    last_motion_times = {}
    send_nomotion = {}

    start_time = time.time()
    qlab_last_send_time = 0
    try:
        while(True):
            now = time.time()
            if not config_q.empty():
                ser.write(config_q.get())

            packet = Packet.from_bytes(ser.read(packet_size))

            if packet.id in last_times != 0:
                deltas.append(packet.time - last_times[packet.id])
            last_times[packet.id] = packet.time

            message = {}
            prefix = f"/foot/{packet.id}"
            qlab_queues = []
            if(packet.motion_time != last_motion_times.get(packet.id, 0)):
                color=colors[packet.id] if packet.id < len(colors) else "green"
                # color='red'
                last_motion_times[packet.id] = packet.motion_time
                message |= {f"/motion/{motion_keys[i]}" : v for i,v in enumerate(packet.motion)}
                send_nomotion[packet.id] = True
                qlab_queues += [f"{packet.id}.{motion_keys[i]}" for i, v in enumerate(packet.motion) if v]
                for q in qlab_queues:
                    if packet.motion_time - qlab_queue_last_time.get(q, 0) < REPEAT_TIME:
                        print("Dropping fast repeated queue " + q)
                        qlab_queues.remove(q)
                    qlab_queue_last_time[q] = packet.motion_time
                # print(qlab_queue_last_time)
                # print(qlab_queues)
                # if packet.motion[0]:
                print(colored(f"{time.time() - start_time:7.3} s", 'yellow') + colored(str(packet), color) + " QLAB --> " + colored(":".join(qlab_queues),'yellow'))
            elif(send_nomotion.get(packet.id, False) and packet.time - packet.motion_time > TRIGGER_TIME):
                send_nomotion[packet.id] = False
                message |= {f"/motion/{motion_keys[i]}" : False for i in range(len(packet.motion))}


            for k,v in message.items():
                client_local.send_message(prefix + k, v)
            msg_acc = OscMessageBuilder(prefix + "/acc")
            [msg_acc.add_arg(x) for x in packet.acc]
            client_local.send(msg_acc.build())

            if packet.motion[1] and now - qlab_last_send_time < QLAB_REPEAT:
                print(colored(f"Supressing fast queue repeat {now - qlab_last_send_time}", "red"))
            elif len(qlab_queues) > 0:
                print("Sending qlab")
                [client.send_message(f"/cue/{q}/start", 1) for q in qlab_queues]
                if packet.motion[1]:
                    qlab_last_send_time = now
    except KeyboardInterrupt:
        print("CTRL-C hit, ending")

    server.shutdown()
