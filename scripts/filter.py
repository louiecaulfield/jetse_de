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
from config import Config

class SensorFilter(QTimer):
    accelero    = pyqtSignal(int, list)
    triggered   = pyqtSignal(int, int, int, float) # channel ID, axis, direction, time

    def __init__(self, channel, config: Config):
        super(SensorFilter, self).__init__()
        self.rate = RateCounter(100)
        self.channel = channel

        self.accelero_data   = [Queue() for _ in range(3)]

        self.update_config(config, "filter_")

        self.packet_prev = Packet(0, 0, (0,0,0))
        self.timeout.connect(self.emit)
        self.start_time = time.time()

    def update_config(self, config: Config, item: str):
        if not item.startswith("filter_"):
            return

    def process(self, packet: Packet):
        if packet.id != self.channel:
            return

        packet_time = packet.host_time - self.start_time
        time_diff = packet.sensor_time - self.packet_prev.sensor_time
        for axis in range(3):
            self.accelero_data[axis].put((packet.acc[axis], packet_time))

        # if ???:
        #     self.triggered.emit(self.channel, axis, ??, packet.host_time)

        self.packet_prev = packet
        self.rate.event()

    def emit(self):
        for axis in range(3):
            accelero_list = []
            while not self.accelero_data[axis].empty():
                accelero_list.append(self.accelero_data[axis].get())

            if len(accelero_list) > 0:
                self.accelero.emit(axis, accelero_list)

            # if random.random() > 0.9 and len(derivative_list) > 0:
            #     direction = random.random() > 0.5
            #     t=random.choice(derivative_list)[1]
            #     print(f"Random event on axis {axis}/{direction}/{t}")
            #     self.triggered.emit(axis, direction, t)
