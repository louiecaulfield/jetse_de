from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QSlider, QLineEdit, QCheckBox, QWidget
from PyQt6.QtWidgets import QTableWidget
from PyQt6.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot, QTimer, Qt

import time
from config import Config, TrackerConfig
from rate import RateCounter
from typing import List
from math import inf
from rate import RateCounter
from typing import List
from packet import Packet


class TrackerTable(QTableWidget):

    axes = ["x+", "x-", "y+", "y-", "z+", "z-"]
    columns = ["tracker", "channel", "threshold", "duration"] + axes + ["rate", "repeat", "cue"]
    n_trackers = 0

    def __init__(self, config: Config):
        self.config = config
        super().__init__(len(self.config.trackers)*2, len(TrackerTable.columns))
        self.setHorizontalHeaderLabels(TrackerTable.columns)

        for i, tracker in enumerate(config.trackers):
            self.addTracker(i, tracker)
            self.setSpan(i * 2, 0, 2, 1)
            self.setSpan(i * 2, 11, 2, 1)
            self.setSpan(i * 2, 12, 2, 1)

        self.resizeRowsToContents()
        self.resizeColumnsToContents()

    def addTracker(self, idx: int, config: TrackerConfig):
        row = idx * 2
        print(f"Adding tracker {config} at row {row}")

        label = QLabel(f"{idx}")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("font-weight: bold; font-size: 14pt;")
        self.setCellWidget(row, 0, label)

        for i in range(2):
            channel = QSpinBox()
            channel.setMinimum(1)
            channel.setMaximum(100)
            channel.setValue(config.channels[i])
            self.setCellWidget(row+i, 1, channel)

            # Threshold slider + numeric
            threshold_widget = QWidget()
            threshold = QHBoxLayout()
            threshold_widget.setLayout(threshold)
            thresh_slider = QSlider(Qt.Orientation.Horizontal)
            thresh_slider.setMinimum(0)
            thresh_slider.setMaximum(200)
            thresh_slider.setValue(config.threshold[i])
            threshold.addWidget(thresh_slider)

            thresh_spin = QSpinBox()
            thresh_spin.setMinimum(thresh_slider.minimum())
            thresh_spin.setMaximum(thresh_slider.maximum())
            thresh_spin.setValue(config.threshold[i])
            threshold.addWidget(thresh_spin)

            thresh_slider.valueChanged.connect(thresh_spin.setValue)
            thresh_spin.valueChanged.connect(thresh_slider.setValue)
            self.setCellWidget(row+i, 2, threshold_widget)

            # Duration slider + numeric
            duration_widget = QWidget()
            duration = QHBoxLayout()
            duration_widget.setLayout(duration)
            duration_slider = QSlider(Qt.Orientation.Horizontal)
            duration_slider.setMinimum(0)
            duration_slider.setMaximum(200)
            duration_slider.setValue(config.duration[i])
            duration.addWidget(duration_slider)

            duration_spin = QSpinBox()
            duration_spin.setMinimum(duration_slider.minimum())
            duration_spin.setMaximum(duration_slider.maximum())
            duration_spin.setValue(config.duration[i])
            duration.addWidget(duration_spin)

            duration_slider.valueChanged.connect(duration_spin.setValue)
            duration_spin.valueChanged.connect(duration_slider.setValue)
            self.setCellWidget(row+i, 3, duration_widget)

            # Motion axes
            for j, axis in enumerate(TrackerTable.axes):
                axis_checkbox = QCheckBox()
                axis_checkbox.setChecked(config.axes[i] & (1<<j))
                self.setCellWidget(row + i, 4 + j, axis_checkbox)

            rate_label = QLabel()
            rate_label.setText("-- Hz")
            self.setCellWidget(row + i, 10, rate_label)

        # Repeat rate
        repeat_spin = QSpinBox()
        repeat_spin.setMinimum(0)
        repeat_spin.setMaximum(1000)
        repeat_spin.setValue(config.interval)
        self.setCellWidget(row + i, 11, repeat_spin)

        self.cue = QLineEdit()
        self.cue.setText(config.cue)
        self.setCellWidget(row + i, 12, self.cue)

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