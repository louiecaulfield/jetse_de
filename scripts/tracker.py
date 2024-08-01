from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QSlider, QLineEdit, QCheckBox
from PyQt6.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot, QTimer, Qt

import time
from config import Config, TrackerConfig
from rate import RateCounter
from typing import List
from math import inf
from rate import RateCounter
from typing import List
from packet import Packet


class TrackerWidget(QHBoxLayout):
    n_trackers = 0

    threshold_changed = pyqtSignal(int, int) #channel, axis, direction, level, enabled
    duration_changed = pyqtSignal(int, int) #channel, axis, direction, level, enabled

    def __init__(self, config: TrackerConfig):
        super(TrackerWidget, self).__init__()
        self.rate = RateCounter(50)
        self.config = config

        # Tracker ID label
        TrackerWidget.n_trackers += 1
        self.label = QLabel(f"Tracker {TrackerWidget.n_trackers}")
        self.addWidget(self.label)

        # Threshold slider & numeric updown
        self.thresh_slider = QSlider(Qt.Orientation.Horizontal)
        self.thresh_slider.setMinimum(0)
        self.thresh_slider.setMaximum(200)
        self.addWidget(self.thresh_slider)

        self.thresh_spin = QSpinBox()
        self.thresh_spin.setMinimum(self.thresh_slider.minimum())
        self.thresh_spin.setMaximum(self.thresh_slider.maximum())
        self.addWidget(self.thresh_spin)

        self.thresh_slider.valueChanged.connect(self.thresh_spin.setValue)
        self.thresh_spin.valueChanged.connect(self.thresh_slider.setValue)

        # Duration slider & numeric updown
        self.duration_slider = QSlider(Qt.Orientation.Horizontal)
        self.duration_slider.setMinimum(0)
        self.duration_slider.setMaximum(200)
        self.addWidget(self.duration_slider)

        self.duration_spin = QSpinBox()
        self.duration_spin.setMinimum(self.duration_slider.minimum())
        self.duration_spin.setMaximum(self.duration_slider.maximum())
        self.addWidget(self.duration_spin)

        self.duration_slider.valueChanged.connect(self.duration_spin.setValue)
        self.duration_spin.valueChanged.connect(self.duration_slider.setValue)

        # Status: update rate
        self.rate = QLabel()
        self.rate.setText("-- Hz")
        self.addWidget(self.rate)

        # Motion
        self.motion_boxes = []
        self.motion_vlayout = QVBoxLayout()
        for ch in self.config.channels:
            layout = QHBoxLayout()
            for _ in range(6):
                self.motion_boxes.append(QCheckBox())
                layout.addWidget(self.motion_boxes[-1])
            self.motion_vlayout.addLayout(layout)
        self.addLayout(self.motion_vlayout)

        # Cue
        self.cue = QLineEdit()
        self.cue.setText(self.config.cue)
        self.addWidget(self.cue)

        self.filter = TrackerFilter(config)
        self.filter.update.connect(self.update)

    def update(self, axis: int, data: List[tuple]):
        if axis == 0:
            self.rate.event()

    def start(self):
        self.filter.start()

    def stop(self):
        self.filter.stop()

    def update_config(self, config: Config, item: str):
        if not item.startswith("filter_"):
            return


class TrackerFilter(QTimer):
    update = pyqtSignal(int, int, int, float) # channel ID, axis, direction, time

    def __init__(self, config: TrackerConfig):
        super(TrackerFilter, self).__init__()
        self.rate = RateCounter(100)
        self.config = config

        # self.update_config(config, "filter_")

        self.packet_prev = Packet(0, 0, (0,0,0))
        self.timeout.connect(self.emit)
        self.start_time = time.time()

    def process(self, packet: Packet):
        if packet.id not in self.config.channels:
            return

        packet_time = packet.host_time - self.start_time
        time_diff = packet.sensor_time - self.packet_prev.sensor_time

        # if ???:
        #     self.update.emit(packet.id, axis, ??, packet.host_time)

        self.packet_prev = packet
        self.rate.event()

    def emit(self):
        pass