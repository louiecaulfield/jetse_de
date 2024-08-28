from PyQt6.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot
import sys, traceback
from worker import WorkerSignals

from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer

from config import Config

class OscServer(QRunnable):
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

    def handler(self, address, *arg):
        print(f"{address}: {arg}")

    def default_handler(self, address, *arg):
        print(f"DEFAULT {address}: {arg}")
