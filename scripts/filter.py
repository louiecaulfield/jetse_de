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
    derivative  = pyqtSignal(int, list)
    lowpass     = pyqtSignal(int, list)
    triggered   = pyqtSignal(int, int, int, float) # channel ID, axis, direction, time

    def __init__(self, channel, config: Config):
        super(SensorFilter, self).__init__()
        self.rate = RateCounter(100)
        self.channel = channel

        self.accelero_data   = [Queue() for _ in range(3)]
        self.derivative_data = [Queue() for _ in range(3)]
        self.filtered_data   = [Queue() for _ in range(3)]

        self.update_config(config, "filter_")

        self.packet_prev = Packet(0, 0, (0,0,0))
        self.filtered_prev = [0,0,0]
        self.deriv_prev = [0,0,0]
        self.timeout.connect(self.emit)
        self.start_time = time.time()

        self.trigger_levels = config.levels[channel].copy()

    def update_config(self, config: Config, item: str):
        if not item.startswith("filter_"):
            return

        match config.filter_btype:
            case "bandpass" | "bandstop":
                f_crit = [config.filter_f1, config.filter_f2]
            case "lowpass" | "highpass":
                f_crit = config.filter_f1
            case _:
                print(f"Unknown filter type {btype} - not updating filters")
                return

        filter_config = {
            "fs"    : config.filter_fs,
            "f_crit": f_crit,
            "order" : config.filter_order,
            "btype" : config.filter_btype,
            "ftype" : "butter"
        }

        self.filters = [LiveFilter(**filter_config) for _ in range(3)]

    def update_trigger(self, channel: int, axis: int, direction: int, level: float, enabled: bool):
        self.trigger_levels[axis * 2 + direction] = level if enabled else inf if direction == 0 else -inf

    def process(self, packet: Packet):
        if packet.id != self.channel:
            return

        packet_time = packet.host_time - self.start_time
        time_diff = packet.sensor_time - self.packet_prev.sensor_time
        for axis in range(3):
            self.accelero_data[axis].put((packet.acc[axis], packet_time))

            filtered = self.filters[axis].process(packet.acc[axis])
            self.filtered_data[axis].put((filtered, packet_time))

            deriv = filtered #(filtered - self.filtered_prev[axis])/time_diff
            self.derivative_data[axis].put((deriv, packet_time))

            if deriv >= self.trigger_levels[axis * 2] and self.deriv_prev[axis] < self.trigger_levels[axis * 2]:
                self.triggered.emit(self.channel, axis, 0, packet.host_time)
            if deriv <= self.trigger_levels[axis * 2 + 1] and self.deriv_prev[axis] > self.trigger_levels[axis * 2 + 1]:
                self.triggered.emit(self.channel, axis, 1, packet.host_time)

            self.filtered_prev[axis] = filtered
            self.deriv_prev[axis] = deriv

        self.packet_prev = packet
        self.rate.event()

    def emit(self):
        for axis in range(3):
            accelero_list = []
            while not self.accelero_data[axis].empty():
                accelero_list.append(self.accelero_data[axis].get())

            if len(accelero_list) > 0:
                self.accelero.emit(axis, accelero_list)

            derivative_list = []
            while not self.derivative_data[axis].empty():
                derivative_list.append(self.derivative_data[axis].get())
            if len(derivative_list) > 0:
                self.derivative.emit(axis, derivative_list)

            lowpass_list = []
            while not self.filtered_data[axis].empty():
                lowpass_list.append(self.filtered_data[axis].get())
            if len(lowpass_list) > 0:
                self.lowpass.emit(axis, lowpass_list)

            # if random.random() > 0.9 and len(derivative_list) > 0:
            #     direction = random.random() > 0.5
            #     t=random.choice(derivative_list)[1]
            #     print(f"Random event on axis {axis}/{direction}/{t}")
            #     self.triggered.emit(axis, direction, t)

class LiveFilter():
    def __init__(self, fs, f_crit, order, btype, ftype):
        """Initialize live filter based on difference equation.

        Args:
            b (array-like): numerator coefficients obtained from scipy.
            a (array-like): denominator coefficients obtained from scipy.
        """
        self.b, self.a = scipy.signal.iirfilter(order, Wn=f_crit, fs=fs, btype=btype, ftype=ftype)
        self._xs = deque([0] * len(self.b), maxlen=len(self.b))
        self._ys = deque([0] * (len(self.a) - 1), maxlen=len(self.a)-1)

    def process(self, x):
        """Filter incoming data with standard difference equations.
        """
        self._xs.appendleft(x)
        y = np.dot(self.b, self._xs) - np.dot(self.a[1:], self._ys)
        y = y / self.a[0]
        self._ys.appendleft(y)

        return y