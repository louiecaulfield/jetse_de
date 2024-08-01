from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QDoubleSpinBox, QSpinBox, QComboBox
from PyQt6.QtCore import pyqtSignal, Qt
import pyqtgraph as pg

from config import Config
from rate import RateCounter
from typing import List
from math import inf

class FootPlot(QHBoxLayout):
    threshold_changed = pyqtSignal(int, int) #channel, axis, direction, level, enabled
    duration_changed = pyqtSignal(int, int) #channel, axis, direction, level, enabled

    def __init__(self, channel: int, config: Config):
        super(FootPlot, self).__init__()
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

    def accelero_handler(self, axis: int, data: List[tuple]):
        if axis == 0:
            self.rate.event()
