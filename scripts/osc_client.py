from PyQt6.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot
import sys, traceback
from worker import WorkerSignals

from pythonosc import udp_client
from pythonosc.osc_message_builder import OscMessageBuilder
import queue
import time
from config import Config

class OscClient(QRunnable):
    def __init__(self, config: Config):
        super(OscClient, self).__init__()
        self.ip = config.osc_ip
        self.port = config.osc_port
        self.cues = config.cues.copy()
        self.running = False
        self.signals = WorkerSignals()
        self.triggers = queue.Queue()
        self.last_msg_time = {ch: time.time() for ch in config.cues.keys()}

    @pyqtSlot()
    def run(self):
        INTERVAL_MIN = 1.000
        try:
            print("Starting OSC client")
            self.running = True
            self.client = udp_client.SimpleUDPClient(self.ip, self.port)
            print("Client running")

            while(self.running):
                try:
                    (pid, axis, direction, rx_time) = self.triggers.get(True, 2)
                    latency = time.time() - rx_time
                    time_since_last = rx_time - self.last_msg_time[pid]
                    if time_since_last > INTERVAL_MIN:
                        cue_name = f"/cue/{self.cues[pid]}/start"
                        self.client.send_message(cue_name, 1)
                        print(f"Sent cue {cue_name} to {self.ip}:{self.port}")
                        print(f"[@{rx_time}s D{time_since_last}s] Packet {pid} / {axis} / {direction} / {latency} s")
                        self.last_msg_time[pid] = rx_time
                    else:
                        print("Supressing fast repeat")
                except queue.Empty:
                    continue

        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        finally:
            self.signals.finished.emit()

    def handle_trigger(self, *args):
        self.triggers.put(args)

    def update_config(self, config: Config, item: str):
        if not item in ["cues", "osc_ip", "osc_port"]:
            return

        self.cues = config.cues.copy()

    def stop(self):
        self.running = False
