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
        self.running = False
        self.signals = WorkerSignals()
        self.cues = queue.Queue()

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
                    cue_name = self.cues.get(True, 2)
                    self.client.send_message(cue_name, 1)
                    print(f"Sent cue {cue_name} to {self.ip}:{self.port}")
                except queue.Empty:
                    continue

        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        finally:
            self.signals.finished.emit()

    def send_cue(self, cue: str):
        print(f"OSC que {cue}")
        self.cues.put(cue)

    def update_config(self, config: Config, item: str):
        if not item in ["osc_ip", "osc_port"]:
            return

    def stop(self):
        self.running = False
