#!/usr/bin/env python3

from PyQt6.QtWidgets import *
from PyQt6.QtCore import QThreadPool, pyqtSlot, pyqtSignal, QTimer

from worker import Worker
from interface import SensorInterface
from config import Config, ConfigForm
from packet import Packet
from tracker import TrackerWidget, TrackerFilter
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

        super().__init__()
        self.threadpool = QThreadPool()
        self.interface = None
        self.osc_client = None

        self.setWindowTitle("Footstep tracker")

        layout = QVBoxLayout()

        # Main layout (plots + config)
        layout_main = QHBoxLayout()

        # Config
        self.config_widget = ConfigForm(self.config, config_path)
        self.config_widget.serial_connect.connect(self.serial_connect)
        self.serial_disconnected.connect(self.config_widget.serial_disconnected)
        self.config_widget.osc_connect.connect(self.osc_connect)
        self.osc_connected.connect(self.config_widget.osc_connected)

        # Plots
        self.trackers = {}
        plot_widget = QWidget()
        plot_layout = QVBoxLayout()
        plot_widget.setLayout(plot_layout)

        for i, tracker in enumerate(self.config.trackers):
            print(f"Tracker {i} -> {tracker}")
            tracker_widget = TrackerWidget(tracker)

            self.config_widget.config_changed.connect(tracker_widget.update_config)

            # plot.trigger_changed.connect(sensor_filter.update_trigger)
            # plot.trigger_changed.connect(self.config_widget.update_trigger)

            self.trackers[i] = tracker_widget

            self.destroyed.connect(tracker_widget.stop)
            tracker_widget.start()

            plot_layout.addLayout(tracker_widget)


        layout_main.addWidget(plot_widget)
        layout_main.addWidget(self.config_widget)
        layout.addLayout(layout_main)

        # Initialization
        container = QWidget()
        container.setLayout(layout)

        self.setCentralWidget(container)
        self.statusBar()

        self.timer_status = QTimer()
        self.timer_status.setInterval(500)
        self.timer_status.timeout.connect(self.update_status)
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
            for f in self.filters.values():
                self.interface.signals.result.connect(f.process)
            self.interface.signals.finished.connect(self.on_serial_disconnect)
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
            for f in self.filters.values():
                f.triggered.connect(self.osc_client.handle_trigger)
            self.threadpool.start(self.osc_client)
            self.osc_connected.emit(True)

        else:
            print("Stopping osc client")
            self.osc_client.stop()

    def on_osc_disconnect(self):
        print(f"OSC disconnected")
        self.osc_client = None
        self.osc_connected.emit(False)

    def closeEvent(self,event):
        if self.config_widget.dirty:
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
