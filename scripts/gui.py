#!/usr/bin/env python3

from PyQt6.QtWidgets import *
from PyQt6.QtCore import QThreadPool, pyqtSlot, pyqtSignal, QTimer

from worker import Worker
from interface import SensorInterface
from config import Config, ConfigForm
from packet import Packet
from tracker import TrackerFilter, TrackerTable
from rate import RateCounter
from osc_client import OscClient

import sys
import os
from time import sleep
from typing import List

class MainWindow(QMainWindow):
    serial_disconnected = pyqtSignal()
    osc_connected = pyqtSignal(bool)

    def __init__(self, config_path: str):
        self.config = Config.load(config_path)
        self.config_dirty = False

        super().__init__()
        self.threadpool = QThreadPool()
        self.interface = None
        self.osc_client = None

        self.setWindowTitle("Footstep tracker")

        layout = QVBoxLayout()

        # Config
        self.config_widget = ConfigForm(self.config, config_path)
        self.config_widget.serial_connect.connect(self.serial_connect)
        self.serial_disconnected.connect(self.config_widget.serial_disconnected)
        self.config_widget.osc_connect.connect(self.osc_connect)
        self.osc_connected.connect(self.config_widget.osc_connected)
        self.config_widget.config_changed.connect(self.config_changed)

        # Tracker table
        self.trackers = TrackerTable(self.config)
        self.trackers.config_changed.connect(self.config_changed)
        layout.addWidget(self.config_widget)
        layout.addWidget(self.trackers)

        # Initialization
        container = QWidget()
        container.setLayout(layout)

        self.setCentralWidget(container)
        self.statusBar()

        self.timer_status = QTimer()
        self.timer_status.setInterval(500)
        self.timer_status.timeout.connect(self.update_status)
        self.timer_status.timeout.connect(self.trackers.update_rates)
        self.timer_status.start()
        self.destroyed.connect(self.timer_status.stop)

        if self.config.autostart:
            self.config_widget.btn_connect_serial.click()

    def update_status(self):
        rates = {}
        if self.interface:
            rates["interface"] = self.interface.rate()
        # rates.update({f"CH{ch} filt": f.rate() for ch,f in self.filters.items()})

        # rates.update({f"CH{ch} plot": f.rate() for ch,f in self.plots.items()})

        status = " - ".join([f"{k}: [{v:5.2f}Hz]" for k,v in rates.items()])
        self.statusBar().showMessage(status)

    def serial_connect(self, port):
        if self.interface is None:
            print(f"Connecting to {port}")
            if port is None:
                self.statusBar().showMessage("no interface selected")
                self.serial_disconnected.emit()
                return

            self.interface = SensorInterface(port)
            self.interface.signals.result.connect(self.trackers.process)
            self.interface.signals.finished.connect(self.on_serial_disconnect)
            self.trackers.update_config.connect(self.interface.update_config)
            self.threadpool.start(self.interface)
        else:
            print("Stopping")
            self.interface.stop()

    def on_serial_disconnect(self):
        print("Sensor interface disconnected")
        self.interface = None
        self.serial_disconnected.emit()

    def osc_connect(self):
        if self.osc_client is None:
            print(f"MAking new osc cliecnt {self.config.osc_ip}:{self.config.osc_port}")
            self.osc_client = OscClient(self.config)
            self.config_widget.config_changed.connect(self.osc_client.update_config)
            self.osc_client.signals.finished.connect(self.on_osc_disconnect)
            for f in self.trackers.filters:
                f.event.connect(self.osc_client.send_cue)
            self.threadpool.start(self.osc_client)
            self.osc_connected.emit(True)

        else:
            print("Stopping osc client")
            self.osc_client.stop()

    def on_osc_disconnect(self):
        print(f"OSC disconnected")
        self.osc_client = None
        self.osc_connected.emit(False)

    def config_changed(self):
        self.config_dirty = True

    def closeEvent(self,event):
        if self.config_dirty:
            result = QMessageBox.question(self,
                        "Save config?",
                        f"Config changed. Save to file {self.config_widget.config_path}?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if result == QMessageBox.StandardButton.Yes:
                self.config_widget.save_clicked()

        if self.interface:
            self.interface.stop()
        if self.osc_client:
            self.osc_client.stop()
        event.accept()

if __name__=="__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str,
                                    help="Configuration file",
                                    default="./config.yml")
    args = parser.parse_args()

    app = QApplication(sys.argv)

    from pathlib import Path
    window = MainWindow(str(Path.cwd() / args.config))
    window.show()
    app.exec()
