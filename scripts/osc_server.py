from PyQt6.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot
import sys, traceback
from worker import WorkerSignals

from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer

from config import Config

class OscServer(QRunnable):
    config_changed = pyqtSignal()

    def __init__(self, config: Config):
        super(OscServer, self).__init__()
        self.config = config
        self.running = False
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        self.running = True
        self.dispatcher = Dispatcher()
        self.dispatcher.map("/tracker/*", self.handler)
        self.dispatcher.set_default_handler(self.default_handler)
        # self.signals.result.connect(self._do_stop_server)

        while(self.running):
            print(f"Starting OSC receiver on port {self.config.osc_receive_port}")
            self.server = ThreadingOSCUDPServer(('', self.config.osc_receive_port), self.dispatcher)
            self.server.serve_forever()  # Blocks forever
            self.server.server_close()
            self.server = None
            print("OSC receiver stopped")
        try:
            self.signals.finished.emit()
        except RuntimeError:
            print("OscServer not sending finished signal - quitting")

    def update_config(self, config: Config, item: str):
        if item not in ["osc_receive_port"]:
            return
        self.server.shutdown()

    def stop(self):
        self.running = False
        self.server.shutdown()

    def handler(self, address, *args):
        try:
            (_, _, tracker_pointer, attribute_name) = address.strip().split("/")
        except:
            print(f"Bad structure of address {address}")
            return

        if str(int(tracker_pointer)) == tracker_pointer:
            tracker_idx = int(tracker_pointer)
            if tracker_idx > len(self.config.trackers):
                print(f"OSC Server: tracker index {tracker_idx} out of range")
                return
        else:
            for (i, t) in enumerate(self.config.trackers):
                if t.alias == i:
                    tracker_idx = i
                    break
            else:
                print(f"OSC Server: tracker with alias {tracker_pointer} not found")
                return

        tracker = self.config.trackers[tracker_idx]
        if not hasattr(tracker, attribute_name):
            print(f"Unknown tracker config {attribute_name}")
            return

        attribute = getattr(tracker, attribute_name)
        if isinstance(attribute, list):
            if len(args) != 2:
                print(f"I need 2 arguments to update a list value - not {args}")
                return
            if not isinstance(args[0], int):
                print(f"First argument should be an integer, not {type(args[0])}")
                return
            if args[0] >= len(attribute):
                print(f"Index {args[0]} out of range [0,{len(attribute)}]")
                return

            idx = args[0]
            if not isinstance(args[1], type(attribute[idx])):
                print(f"Expecting second argument {args[1]} to be of type {type(attribute[idx])}, not {type(args[1])}")
                return

            print(f"Updating tracker[{tracker_idx}].{attribute_name}[{idx}] to {args[1]}")
            attribute[idx] = args[1]
        else:
            if len(args) != 1:
                print(f"I need exactly arguments to update {attribute_name} - not {args}")
                return

            if not isinstance(args[0], type(attribute)):
                print(f"Expecting argument {args[0]} to be of type {type(attribute)}, not {type(args[0])}")
                return

            print(f"Updating tracker[{tracker_idx}].{attribute_name} to {args[0]}")
            setattr(tracker, attribute_name, args[0])

        self.config_changed.emit()

    def default_handler(self, address, *arg):
        print(f"Ignoring OSC message at {address}")
