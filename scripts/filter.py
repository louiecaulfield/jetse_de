from PyQt6.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot, QTimer
import sys, traceback
from worker import WorkerSignals
import numpy as np
import scipy
import random
from math import inf
import time
from collections import deque
from queue import Queue
from rate import RateCounter
from typing import List

from packet import Packet
from config import Config, TrackerConfig

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
