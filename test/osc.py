from pythonosc import udp_client
from pythonosc.osc_message_builder import OscMessageBuilder
import pythonosc.osc_server as osc_server
import threading
from pythonosc.dispatcher import Dispatcher
from packet import Packet, Config
from parse import parse
import time

class OscThing():
    def __init__(self, ip, port_listen, port_send):
        self.dispatcher = Dispatcher()
        if(port_listen > 0):
            self.server = osc_server.ThreadingOSCUDPServer(("127.0.0.1", port_listen), self.dispatcher)
        self.client = udp_client.SimpleUDPClient(ip, port_send)

    def add_handler(self, msg: str, handler):
        self.dispatcher.map(msg, handler)

    def start(self):
        if not hasattr(self, "server"):
            print("Not starting server, no listen port defined")
            return

        print("Starting OSC server on {}".format(self.server.server_address))
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.start()

    def stop(self):
        if not hasattr(self, "server"):
            print("Can't stop server, no listen port defined")
            return

        if not hasattr(self, "server_thread"):
            print("Can't stop server, not started")
            return

        self.server.shutdown()
        print("Waiting for server to shut down")
        self.server_thread.join()
        print("Server thread ended")
        delattr(self, "server_thread")

TRIGGER_TIME = 250 #ms
class OscDebug(OscThing):
    def __init__(self, ip, port_listen, port_send, cfg_q, accelero_data):
        super().__init__(ip, port_listen, port_send)
        self.add_handler("/foot/*/threshold", self.foot_handler)
        self.last_motion_times = {}
        self.send_nomotion = {}
        self.cfg_q = cfg_q
        self.accelero_data = accelero_data
        self.motion_off = {id:[] for id in range(6)}

    def foot_handler(self, address, *args):
        if(len(args) != 1):
            print(f"/foot/threshold needs exactly 1 argument")
            return

        channel = parse("/foot/{:d}/threshold", address)[0]

        if(channel < 0):
            print(f"Unable to parse channel from {args[0]}")
            return

        if(not isinstance(args[0], int)):
            print("Argument 1 should be int")
            return

        config = Config(channel, args[0])
        print("Config update: " + str(config))
        self.cfg_q.put(config)

    def handle(self, packet: Packet):
        message = {}
        prefix = f"/foot/{packet.id}"

        if(packet.motion_time != self.last_motion_times.get(packet.id, 0)):
            self.last_motion_times[packet.id] = packet.motion_time
            for i, v in enumerate(packet.motion):
                if v:
                    message |= {f"/motion/{Packet.motion_keys[i]}" : True}
                    self.motion_off[packet.id].append((packet.motion_time + TRIGGER_TIME, Packet.motion_keys[i]))

        for (time, key) in self.motion_off[packet.id]:
            if packet.sensor_time > time:
                print(f"Sending remove {key}")
                self.motion_off[packet.id].remove((time, key))
                message |= {f"/motion/{key}" : False}

        for k,v in message.items():
            self.client.send_message(prefix + k, v)

        if self.accelero_data:
            msg_acc = OscMessageBuilder(prefix + "/acc")
            [msg_acc.add_arg(x) for x in packet.acc]
            self.client.send(msg_acc.build())

        if packet.cfg_update:
            self.client.send_message(prefix + "/threshold", packet.threshold)

class OscQlab(OscThing):
    SAME_SHOE_INTERVAL = .750
    REPEAT_MAX = SAME_SHOE_INTERVAL / 2

    def __init__(self, ip, port_send):
        super().__init__(ip, 0, port_send)
        self.last_motion_times = {}
        self.cue_last_time = {}
        self.cue_map = {}
        self.last_channel_cue = -1

    def map_cue(self, channel, axes, cue):
        axes_nrs = []
        for axis in axes:
            if axis not in Packet.motion_keys:
                print(f"Axis {axis} unknown")
            else:
                axes_nrs.append(Packet.motion_keys.index(axis))
        print(f"Mapping axes {axes_nrs} to cue {cue}")
        self.cue_last_time[cue] = 0
        self.cue_map[channel] = (axes_nrs, cue)

    def handle(self, packet: Packet):
        if(packet.motion_time != self.last_motion_times.get(packet.id, 0)):
            self.last_motion_times[packet.id] = packet.motion_time
            if packet.id not in self.cue_map:
                return
            (axes_nrs, cue) = self.cue_map[packet.id]

            send_cue = False
            for i in axes_nrs:
                if packet.motion[i]:
                    self.send_que(cue, packet)
                    return

    def send_que(self, cue, packet):
        channel = packet.id
        # print(f"{time.time() - self.cue_last_time[cue]}")
        if(channel == self.last_channel_cue and time.time() - self.cue_last_time[cue] < self.SAME_SHOE_INTERVAL):
            print(f"Supressing {cue} on same channel {channel}")
            return

        if(time.time() - self.cue_last_time[cue] < self.REPEAT_MAX):
            print(f"Supressing fast repeated {cue} (faster than {self.REPEAT_MAX} ms)")
            return


        self.last_channel_cue = channel

        self.cue_last_time[cue] = time.time()
        self.client.send_message(f"/cue/{cue}/start", 1)
        print(f"{time.time()} QLAB /cue/{cue}/start")