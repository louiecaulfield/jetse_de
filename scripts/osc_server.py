from PyQt6.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot
import sys, traceback
from worker import WorkerSignals

from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer

from config import Config

class OscServer(QRunnable):
    def __init__(self, config: Config):
        super(OscServer, self).__init__()
        self.port = config.osc_receive_port
        self.running = False
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        self.running = True
        self.dispatcher = Dispatcher()
        self.dispatcher.map("/tracker/*", self.handler)
        self.dispatcher.set_default_handler(self.default_handler)

        self.server = ThreadingOSCUDPServer(('', self.port), self.dispatcher)
        self.server.serve_forever()  # Blocks forever

        try:
            print("OSC SERVER STOPPED")
            self.signals.finished.emit()
        except RuntimeError:
            print("OscClient not sending finished signal - quitting")

    def update_config(self, config: Config, item: str):
        if not item in ["osc_receive_port"]:
            return
        print("CONFIG UPDATE for OSC SERVER?")

    def stop(self):
        self.server.shutdown()
        self.server.server_close()

    def handler(self, address, *arg):
        print(f"{address}: {args}")

    def default_handler(self, addres, *arg):
        print(f"DEFAULT {address}: {args}")
