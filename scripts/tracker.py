from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QDoubleSpinBox, QSpinBox, QComboBox
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
    threshold_changed = pyqtSignal(int, int) #channel, axis, direction, level, enabled
    duration_changed = pyqtSignal(int, int) #channel, axis, direction, level, enabled

    def __init__(self, channel: int, config: Config):
        super(TrackerWidget, self).__init__()
        self.rate = RateCounter(50)
        self.channel = channel

        # Channel ID label

        # Threshold slider & numeric updown

        # Duration slider & numeric updown

        # Status: alive, motion x,y,z

    def threshold_moved(self):
        line = self.sender()
        index = self.threshold_lines.index(line)
        axis = index // 2
        direction = index % 2
        self.trigger_changed.emit(self.channel, axis, direction, line.getPos()[1], line.pen.color().alphaF() == 1.0)

    def threshold_clicked(self):
        sender = self.sender()
        color = sender.pen.color()
        if color.alphaF() == 1.0:
            color.setAlphaF(0.5)
        else:
            color.setAlphaF(1)

        sender.pen.setColor(color)
        self.threshold_moved()

    def update(self, axis: int, data: List[tuple]):
        if axis == 0:
            self.rate.event()

class TrackerFilter(QTimer):
    update = pyqtSignal(int, int, int, float) # channel ID, axis, direction, time

    def __init__(self, tracker_config: TrackerConfig, config: Config):
        super(TrackerFilter, self).__init__()
        self.rate = RateCounter(100)
        self.config = tracker_config

        # self.update_config(config, "filter_")

        self.packet_prev = Packet(0, 0, (0,0,0))
        self.timeout.connect(self.emit)
        self.start_time = time.time()

    # def update_config(self, config: Config, item: str):
    #     if not item.startswith("filter_"):
    #         return

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