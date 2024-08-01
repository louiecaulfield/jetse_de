from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QBoxLayout
from PyQt6.QtWidgets import QLabel, QSpinBox, QSlider, QLineEdit, QCheckBox, QWidget
from PyQt6.QtWidgets import QTableWidget
from PyQt6.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot, QTimer, Qt

import time
from config import Config, TrackerConfig
from rate import RateCounter
from typing import List
from math import inf
from rate import RateCounter
from typing import List
from packet import Packet, Config


class Columns:
    CH         = 1
    THR_SLIDER = 2
    THR_SPIN   = 3
    DUR_SLIDER = 4
    DUR_SPIN   = 5
    AXES       = (6,7,8,9,10,11)
    RATE       = 12
    REPEAT     = 13
    CUE        = 14

class TrackerTable(QTableWidget):
    update_config = pyqtSignal(Config) # Channel ID, Config
    config_changed = pyqtSignal()

    axes = ["x+", "x-", "y+", "y-", "z+", "z-"]

    #               0         1           2       3       4       5               12       13       14
    columns = ["tracker", "channel", "threshold", "", "duration", ""] + axes + ["rate", "repeat", "cue"]

    n_trackers = 0

    def __init__(self, config: Config):
        self.config = config
        super().__init__(len(self.config.trackers)*2, len(TrackerTable.columns))
        self.setHorizontalHeaderLabels(TrackerTable.columns)

        self.threshold_sliders  = {}
        self.threshold_spinners = {}
        self.duration_sliders   = {}
        self.duration_spinners  = {}

        self.filters = []
        self.rates = {}
        for i, tracker in enumerate(config.trackers):
            self.addTracker(i, tracker)
            self.setSpan(i * 2, 0, 2, 1)
            self.setSpan(i * 2, Columns.REPEAT, 2, 1)
            self.setSpan(i * 2, Columns.CUE, 2, 1)
            self.filters.append(TrackerFilter(tracker))

        self.resizeRowsToContents()
        self.resizeColumnsToContents()

    def table_value_changed(self, arg):
        for row in range(self.rowCount()):
            for column in range(self.columnCount()):
                if self.cellWidget(row, column) == self.sender():
                    break
            else:
                continue
            break
        else:
            raise Exception("Failed to find widget for change in value by sender")

        tracker_id = row // 2
        tracker = self.config.trackers[tracker_id]
        offset  = row % 2

        match column:
            case Columns.CH:
                print(f"Channel changed for tracker {tracker_id} -> {arg}")
                tracker.channels[offset] = arg
                self.update_config.emit(Config(tracker.channels[offset], tracker.threshold[offset], tracker.duration[offset]))
                self.rates[row].reset()

            case Columns.THR_SLIDER:
                print(f"Threshold slider changed for tracker {tracker_id} -> {arg}")
                tracker.threshold[offset] = arg

            case Columns.THR_SPIN:
                print(f"Threshold spinner changed for tracker {tracker_id} -> {arg}")
                tracker.threshold[offset] = arg
                self.update_config.emit(Config(tracker.channels[offset], tracker.threshold[offset], tracker.duration[offset]))

            case Columns.DUR_SLIDER:
                print(f"Duration slider changed for tracker {tracker_id} -> {arg}")
                tracker.duration[offset] = arg

            case Columns.DUR_SPIN:
                print(f"Duration spinner changed for tracker {tracker_id} -> {arg}")
                tracker.duration[offset] = arg
                self.update_config.emit(Config(tracker.channels[offset], tracker.threshold[offset], tracker.duration[offset]))

            case axis if column in Columns.AXES:
                axis -= Columns.AXES[0]
                print(f"Axis changed for tracker {tracker_id} / {axis} -> {arg}")
                tracker.axes[offset][axis] = (arg == Qt.CheckState.Checked)

            case Columns.RATE:
                print(f"Rate changed for tracker {tracker_id} -> {arg}")
                raise Exception("IMPOSSIBLE")

            case Columns.REPEAT:
                print(f"Repeat changed for tracker {tracker_id} -> {arg}")
                tracker.repeat = arg

            case Columns.CUE:
                print(f"Cue changed for tracker {tracker_id} -> {arg}")
                tracker.cue = arg

        self.config_changed.emit()

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
            channel.valueChanged.connect(self.table_value_changed)
            self.setCellWidget(row+i, Columns.CH, channel)

            # Threshold slider + numeric
            thresh_slider = QSlider(Qt.Orientation.Horizontal)
            thresh_slider.setMinimum(0)
            thresh_slider.setMaximum(200)
            thresh_slider.setValue(config.threshold[i])
            thresh_slider.valueChanged.connect(self.table_value_changed)
            self.setCellWidget(row+i, Columns.THR_SLIDER, thresh_slider)

            thresh_spin = QSpinBox()
            thresh_spin.setMinimum(thresh_slider.minimum())
            thresh_spin.setMaximum(thresh_slider.maximum())
            thresh_spin.setValue(config.threshold[i])
            thresh_spin.valueChanged.connect(self.table_value_changed)
            self.setCellWidget(row+i, Columns.THR_SPIN, thresh_spin)

            thresh_slider.valueChanged.connect(thresh_spin.setValue)
            thresh_spin.valueChanged.connect(thresh_slider.setValue)
            self.threshold_sliders[row+i] = thresh_slider
            self.threshold_spinners[row+i] = thresh_spin

            # Duration slider + numeric
            duration_slider = QSlider(Qt.Orientation.Horizontal)
            duration_slider.setMinimum(0)
            duration_slider.setMaximum(200)
            duration_slider.setValue(config.duration[i])
            duration_slider.valueChanged.connect(self.table_value_changed)
            self.setCellWidget(row+i, Columns.DUR_SLIDER, duration_slider)

            duration_spin = QSpinBox()
            duration_spin.setMinimum(duration_slider.minimum())
            duration_spin.setMaximum(duration_slider.maximum())
            duration_spin.setValue(config.duration[i])
            duration_spin.valueChanged.connect(self.table_value_changed)
            self.setCellWidget(row+i, Columns.DUR_SPIN, duration_spin)

            duration_slider.valueChanged.connect(duration_spin.setValue)
            duration_spin.valueChanged.connect(duration_slider.setValue)
            self.duration_sliders[row+i] = duration_slider
            self.duration_spinners[row+i] = duration_spin

            # Motion axes
            for j, axis in enumerate(TrackerTable.axes):
                axis_checkbox = QCheckBox()
                axis_checkbox.setChecked(config.axes[i][j])
                axis_checkbox.stateChanged.connect(self.table_value_changed)
                self.setCellWidget(row + i, Columns.AXES[0] + j, axis_checkbox)

            rate_label = QLabel()
            rate_label.setText("-- Hz")
            self.setCellWidget(row + i, Columns.RATE, rate_label)
            self.rates[row+i] = RateCounter(30)

        # Repeat rate
        repeat_spin = QSpinBox()
        repeat_spin.setMinimum(0)
        repeat_spin.setMaximum(1000)
        repeat_spin.setValue(config.interval)
        repeat_spin.valueChanged.connect(self.table_value_changed)
        self.setCellWidget(row + i, Columns.REPEAT, repeat_spin)

        self.cue = QLineEdit()
        self.cue.setText(config.cue)
        self.cue.textChanged.connect(self.table_value_changed)
        self.setCellWidget(row + i, Columns.CUE, self.cue)

    def process(self, packet: Packet):
        print(f"Packet: {packet}")
        for filter in self.filters:
            filter.process(packet)

        for row in range(self.rowCount()):
            if(self.cellWidget(row, 1).value() == packet.id):
                self.updateRowChannelInfo(row, packet)

    def updateRowChannelInfo(self, row: int, packet: Packet):
        print(f"Updating row {row} for channel {packet.id}")
        self.rates[row].event()

        if packet.cfg_update:
            self.threshold_spinners[row].blockSignals(True)
            self.threshold_sliders[row].setValue(packet.threshold)
            self.threshold_sliders[row].setValue(packet.threshold)
            self.threshold_spinners[row].blockSignals(False)

            self.duration_spinners[row].blockSignals(True)
            self.duration_sliders[row].setValue(packet.duration)
            self.duration_spinners[row].setValue(packet.duration)
            self.duration_spinners[row].blockSignals(False)

    def update_rates(self):
        for row in range(self.rowCount()):
            self.cellWidget(row, Columns.RATE).setText(f"{self.rates[row]():5.2f} Hz")

class TrackerFilter(QObject):
    event = pyqtSignal(str) # cue

    def __init__(self, config: TrackerConfig):
        super(TrackerFilter, self).__init__()
        self.rate = RateCounter(100)
        self.config = config

        # self.update_config(config, "filter_")
        self.last_motion_times = {}
        self.cue_last_time = {}

        # self.timeout.connect(self.emit)
        self.start_time = time.time()

    def process(self, packet: Packet):
        if packet.id not in self.config.channels:
            return

        packet_time = packet.host_time - self.start_time

        if(packet.motion_time != self.last_motion_times.get(packet.id, 0)):
            self.last_motion_times[packet.id] = packet.motion_time
            for idx, enabled in enumerate(self.config.axes):
                if enabled and packet.motion[idx]:
                    print(f"Sending cue {self.config.cue} for ch {packet.id} cos of axis {idx} = {Packet.motion_keys_short[idx]}")
                    self.event.emit(self.config.cue)
                    return