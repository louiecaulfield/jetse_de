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
        self.config = config
        self.running = False
        self.signals = WorkerSignals()
        self.cues = queue.Queue()

    @pyqtSlot()
    def run(self):
        try:
            self.running = True
            self.restart = False
            while(self.running):
                self.client = udp_client.SimpleUDPClient(self.config.osc_ip, self.config.osc_send_port)
                print(f"Starting OSC client to {self.config.osc_ip}:{self.config.osc_send_port}")
                while(True):
                    try:
                        cue_name = self.cues.get(True, .5)
                        self.client.send_message(cue_name, 1)
                        # print(f"Sent cue {cue_name} to {self.ip}:{self.port}")
                    except queue.Empty:
                        pass
                    finally:
                        if(self.restart or not self.running):
                            print("Restarting OSC client")
                            self.restart = False
                            break


        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        finally:
            try:
                self.signals.finished.emit()
            except RuntimeError:
                print("OscClient not sending finished signal - quitting")

    def send_cue(self, cue: str):
        self.cues.put(cue)

    def update_config(self, config: Config, item: str):
        if item not in ["osc_ip", "osc_send_port"]:
            return
        self.restart = True

    def stop(self):
        self.running = False
