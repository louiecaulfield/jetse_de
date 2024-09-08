from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QBoxLayout
from PyQt6.QtWidgets import QLabel, QSpinBox, QSlider, QLineEdit, QCheckBox, QWidget
from PyQt6.QtWidgets import QTableWidget, QHeaderView
from PyQt6.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot, QTimer, Qt, QEvent
from PyQt6.QtGui import QPalette

import time
from config import Config, TrackerConfig
from rate import RateCounter
from typing import List
from math import inf
from rate import RateCounter
from typing import List, Dict
from packet import ChannelEventPacket, ChannelConfig


class Columns:
    INDEX       = 0
    ALIAS       = 1
    CH          = 2
    THR_SLIDER  = 3
    THR_SPIN    = 4
    DUR_SLIDER  = 5
    DUR_SPIN    = 6
    AXES        = tuple(range(7,13))
    RATE        = 13
    FREQ        = 14
    REPEAT_SAME = 15
    REPEAT_DIFF = 16
    CUE         = 17

class Colors:
    GOOD        = "b6ef8e"
    WARN        = "efd042"
    BAD         = "ef8e8e"
    HIGHLIGHT   = "ef5bd4"
    ENABLED     = GOOD
    DISABLED    = BAD

FLASH_TIMEOUT = 200

class QLabelDblClick(QLabel):
    doubleClicked = pyqtSignal(QEvent)
    def mouseDoubleClickEvent(self, event: QEvent):
        self.doubleClicked.emit(event)
        event.accept()


class TrackerTable(QTableWidget):
    update_config = pyqtSignal(ChannelConfig) # Channel ID, Config
    config_changed = pyqtSignal()

    #               0        1         2           3       4       5       6                                               13      14       15           16        17
    columns = ["tracker", "alias", "channel", "threshold", "", "duration", ""] + ChannelEventPacket.motion_keys_short + ["rate", "freq", "rpt same", "rpt diff", "cue"]

    n_trackers = 0

    def __init__(self, config: Config):
        self.config = config
        super().__init__(len(self.config.trackers)*2, len(TrackerTable.columns))
        self.setHorizontalHeaderLabels(TrackerTable.columns)

        self.threshold_sliders  = {}
        self.threshold_spinners = {}
        self.duration_sliders   = {}
        self.duration_spinners  = {}
        self.freq_labels        = {}

        self.filters = []
        self.rates = {}
        for i, tracker in enumerate(config.trackers):
            self.addTracker(i, tracker)
            self.setSpan(i * 2, Columns.INDEX, 2, 1)
            self.setSpan(i * 2, Columns.ALIAS, 2, 1)
            self.setSpan(i * 2, Columns.REPEAT_SAME, 2, 1)
            self.setSpan(i * 2, Columns.REPEAT_DIFF, 2, 1)
            self.setSpan(i * 2, Columns.CUE, 2, 1)
            tracker_filter = TrackerFilter(tracker)
            self.filters.append(tracker_filter)
            tracker_filter.cue.connect(self.handle_cue)

        self.resizeRowsToContents()
        self.resizeColumnsToContents()

        header = self.horizontalHeader()
        header.setSectionResizeMode(Columns.ALIAS, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(Columns.THR_SLIDER, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(Columns.DUR_SLIDER, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(Columns.RATE, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(Columns.FREQ, QHeaderView.ResizeMode.Stretch)

        self.packets = {}
        self.flash_timers : Dict[QWidget, QTimer] = {}

    def find_table_position(self, widget):
        for row in range(self.rowCount()):
            for column in range(self.columnCount()):
                if self.cellWidget(row, column) == widget:
                    return (row, column)
        return (-1, -1)


    def table_value_changed(self, arg):
        (row, column) = self.find_table_position(self.sender())
        if row < 0:
            return

        tracker_id = row // 2
        tracker = self.config.trackers[tracker_id]
        offset  = row % 2

        match column:
            case Columns.ALIAS:
                # print(f"Alias changed for tracker {tracker_id} -> {arg}")
                tracker.alias = arg

            case Columns.CH:
                # print(f"Channel changed for tracker {tracker_id} -> {arg}")
                tracker.channels[offset] = arg
                self.update_config.emit(ChannelConfig(tracker.channels[offset], tracker.threshold[offset], tracker.duration[offset]))
                self.rates[row].reset()

            case Columns.THR_SLIDER:
                # print(f"Threshold slider changed for tracker {tracker_id} -> {arg}")
                tracker.threshold[offset] = arg

            case Columns.THR_SPIN:
                # print(f"Threshold spinner changed for tracker {tracker_id} -> {arg}")
                tracker.threshold[offset] = arg
                self.update_config.emit(ChannelConfig(tracker.channels[offset], tracker.threshold[offset], tracker.duration[offset]))

            case Columns.DUR_SLIDER:
                # print(f"Duration slider changed for tracker {tracker_id} -> {arg}")
                tracker.duration[offset] = arg

            case Columns.DUR_SPIN:
                # print(f"Duration spinner changed for tracker {tracker_id} -> {arg}")
                tracker.duration[offset] = arg
                self.update_config.emit(ChannelConfig(tracker.channels[offset], tracker.threshold[offset], tracker.duration[offset]))

            case axis if column in Columns.AXES:
                axis -= Columns.AXES[0]
                state = Qt.CheckState(arg)
                # print(f"Axis changed for tracker {tracker_id} / {axis} -> {state} =? {state == Qt.CheckState.Checked}")
                tracker.axes[offset][axis] = state == Qt.CheckState.Checked

            case Columns.RATE:
                # print(f"Rate changed for tracker {tracker_id} -> {arg}")
                raise Exception("IMPOSSIBLE")

            case Columns.FREQ:
                raise Exception("IMPOSSIBLE")

            case Columns.REPEAT_SAME:
                # print(f"Repeat same changed for tracker {tracker_id} -> {arg}")
                tracker.repeat_same = arg

            case Columns.REPEAT_DIFF:
                # print(f"Repeat diff changed for tracker {tracker_id} -> {arg}")
                tracker.repeat_different = arg

            case Columns.CUE:
                # print(f"Cue changed for tracker {tracker_id} -> {arg}")
                tracker.cue = arg

        self.config_changed.emit()

    def addTracker(self, idx: int, config: TrackerConfig):
        row = idx * 2
        label = QLabelDblClick(f"{idx + 1}")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("font-weight: bold; font-size: 14pt;")
        self.setCellWidget(row, Columns.INDEX, label)
        label.doubleClicked.connect(self.labelDoubleClicked)

        alias = QLineEdit()
        alias.setText(config.alias)
        alias.textChanged.connect(self.table_value_changed)
        self.setCellWidget(row, Columns.ALIAS, alias)

        for i in range(2):
            channel = QSpinBox()
            channel.setMinimum(0)
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
            for j, axis in enumerate(ChannelEventPacket.motion_keys_short):
                axis_checkbox = QCheckBox()
                axis_checkbox.setChecked(config.axes[i][j])
                axis_checkbox.stateChanged.connect(self.table_value_changed)
                self.setCellWidget(row + i, Columns.AXES[0] + j, axis_checkbox)

            rate_label = QLabel()
            rate_label.setText("-- Hz")
            rate_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setCellWidget(row + i, Columns.RATE, rate_label)
            self.rates[row+i] = RateCounter(5)

            freq_label = QLabel()
            freq_label.setText("-- MHz")
            freq_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setCellWidget(row + i, Columns.FREQ, freq_label)
            self.freq_labels[row+i] = freq_label

        # Repeat rate
        repeat_same_spin = QSpinBox()
        repeat_same_spin.setMinimum(0)
        repeat_same_spin.setMaximum(2000)
        repeat_same_spin.setValue(config.repeat_same)
        repeat_same_spin.valueChanged.connect(self.table_value_changed)
        self.setCellWidget(row, Columns.REPEAT_SAME, repeat_same_spin)

        repeat_diff_spin = QSpinBox()
        repeat_diff_spin.setMinimum(0)
        repeat_diff_spin.setMaximum(2000)
        repeat_diff_spin.setValue(config.repeat_different)
        repeat_diff_spin.valueChanged.connect(self.table_value_changed)
        self.setCellWidget(row, Columns.REPEAT_DIFF, repeat_diff_spin)

        self.cue = QLineEdit()
        self.cue.setText(config.cue)
        self.cue.textChanged.connect(self.table_value_changed)
        self.setCellWidget(row, Columns.CUE, self.cue)

        self.visualise_tracker_enabled(idx)

    def process(self, packet: ChannelEventPacket):
        if not isinstance(packet, ChannelEventPacket):
            return

        for filter in self.filters:
            filter.process(packet)

        for row in range(self.rowCount()):
            if(self.cellWidget(row, Columns.CH).value() == packet.id):
                self.updateRowChannelInfo(row, packet)

    def updateRowChannelInfo(self, row: int, packet: ChannelEventPacket):
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

        self.freq_labels[row].setText(f"{packet.frequency + 2400} MHz")

        last_packet = self.packets.get(packet.id, None)
        if last_packet is None or packet.motion_time != last_packet.motion_time:
            self.packets[packet.id] = packet
            for axis, motion in enumerate(packet.motion):
                if motion:
                    self.flash(self.cellWidget(row, Columns.AXES[axis]))

    def labelDoubleClicked(self):
        (row, _) = self.find_table_position(self.sender())
        self.config.trackers[row // 2].enabled = not self.config.trackers[row // 2].enabled
        self.visualise_tracker_enabled(row // 2)

    def visualise_tracker_enabled(self, tracker_idx):
        cue: QLineEdit = self.cellWidget(tracker_idx * 2, Columns.CUE)
        if self.config.trackers[tracker_idx].enabled:
            cue.setStyleSheet(f"background-color: #{Colors.ENABLED}")
        else:
            cue.setStyleSheet(f"background-color: #{Colors.DISABLED}")


    @pyqtSlot()
    def update_table_from_config(self):
        for (i, tracker) in enumerate(self.config.trackers):
            row = i * 2

            self.visualise_tracker_enabled(i)

            alias: QLineEdit = self.cellWidget(row, Columns.ALIAS)
            if alias.text() != tracker.alias:
                alias.setText(tracker.alias)

            repeat_same_spin: QSpinBox = self.cellWidget(row, Columns.REPEAT_SAME)
            if repeat_same_spin.value() != tracker.repeat_same:
                repeat_same_spin.setValue(tracker.repeat_same)

            repeat_diff_spin: QSpinBox = self.cellWidget(row, Columns.REPEAT_DIFF)
            if repeat_diff_spin.value() != tracker.repeat_different:
                repeat_diff_spin.setValue(tracker.repeat_different)

            cue: QLineEdit = self.cellWidget(row, Columns.CUE)
            if cue.text() != tracker.cue:
                cue.setText(tracker.cue)

            for j in range(2):
                row = i * 2 + j
                emit_update = False

                channel: QSpinBox = self.cellWidget(row, Columns.CH)
                if channel.value() != tracker.channels[j]:
                    emit_update = True
                    channel.setValue(tracker.channels[j])

                thresh_slider: QSlider = self.cellWidget(row, Columns.THR_SLIDER)
                if thresh_slider.value() != tracker.threshold[j]:
                    emit_update = True
                    thresh_slider.setValue(tracker.threshold[j])

                thresh_spin: QSpinBox = self.cellWidget(row, Columns.THR_SPIN)
                if thresh_spin.value() != tracker.threshold[j]:
                    emit_update = True
                    thresh_spin.setValue(tracker.threshold[j])

                duration_slider: QSlider = self.cellWidget(row, Columns.DUR_SLIDER)
                if duration_slider.value() != tracker.duration[j]:
                    emit_update = True
                    duration_slider.setValue(tracker.duration[j])

                duration_spin: QSpinBox = self.cellWidget(row, Columns.DUR_SPIN)
                if duration_spin.value() != tracker.duration[j]:
                    emit_update = True
                    duration_spin.setValue(tracker.duration[j])

                for ax in range(len(Columns.AXES)):
                    col = Columns.AXES[ax]
                    axis_checkbox: QCheckBox = self.cellWidget(row, col)
                    if axis_checkbox.isChecked() != tracker.axes[j][ax]:
                        axis_checkbox.setChecked(tracker.axes[j][ax])

                if emit_update:
                    print(f"Emitting update for tracker {tracker.alias}[{i}]")
                    self.update_config.emit(ChannelConfig(tracker.channels[j], tracker.threshold[j], tracker.duration[j]))


    def update_rates(self):
        for row in range(self.rowCount()):
            rate = self.rates[row]
            rate_widget : QLabel = self.cellWidget(row, Columns.RATE)
            if rate.older_than(1000):
                rate_widget.setStyleSheet(f"background-color: #{Colors.BAD}")
                rate_widget.setText(f"N/A")
                rate.reset()
            elif rate.older_than(400):
                rate_widget.setStyleSheet(f"background-color: #{Colors.WARN}")
            else:
                rate_widget.setStyleSheet(f"background-color: #{Colors.GOOD}")
                rate_widget.setText(f"{rate():5.2f} Hz")

    def flash(self, widget: QWidget):
        if widget in self.flash_timers.keys():
            self.flash_timers[widget][0].stop()
            stylesheet = self.flash_timers[widget][1]
        else:
            stylesheet = widget.styleSheet()

        timer = QTimer()

        timer.setInterval(FLASH_TIMEOUT)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self.flash_restore(widget))
        timer.start()
        self.flash_timers[widget] = (timer, stylesheet)

        widget.setStyleSheet(stylesheet + f"background-color:#{Colors.HIGHLIGHT};")

    def flash_restore(self, widget: QWidget):
        widget.setStyleSheet(self.flash_timers[widget][1])
        del self.flash_timers[widget]

    def handle_cue(self, cue: str, sender: "TrackerFilter", offset: int):
        row = self.filters.index(sender) * 2
        label = self.cellWidget(row, Columns.INDEX)
        self.flash(label)

class TrackerFilter(QObject):
    cue = pyqtSignal(str, object, int) # cue, filter, channel offset

    def __init__(self, config: TrackerConfig):
        super(TrackerFilter, self).__init__()
        self.rate = RateCounter(100)
        self.config = config

        # self.update_config(config, "filter_")
        self.last_motion_times = {}
        self.cue_last_time = -1000
        self.last_offset = -1

        # self.timeout.connect(self.emit)
        self.start_time = time.time()

    def process(self, packet: ChannelEventPacket):
        if packet.id not in self.config.channels:
            return

        if not self.config.enabled:
            return

        offset = self.config.channels.index(packet.id)

        packet_time = packet.host_time - self.start_time

        if(packet.motion_time != self.last_motion_times.get(packet.id, 0)):
            self.last_motion_times[packet.id] = packet.motion_time
            interval = (packet.host_time - self.cue_last_time) * 1000
            # print(f"Motion with interval {interval}")
            for idx, enabled in enumerate(self.config.axes[offset]):
                if enabled and packet.motion[idx]:
                    if offset != self.last_offset and interval > self.config.repeat_different:
                        # print("Sending cue for different foot")
                        self.last_offset = offset
                        self.cue_last_time = packet.host_time
                        # print(f"Delay = {(time.time() - packet.host_time)*1000}")
                        self.cue.emit(self.config.cue, self, offset)
                        return
                    elif offset == self.last_offset and interval > self.config.repeat_same:
                        # print("Sending cue for same foot")
                        # print(f"Delay = {(time.time() - packet.host_time)*1000}")
                        self.cue_last_time = packet.host_time
                        self.cue.emit(self.config.cue, self, offset)
                        return
                    else:
                        # print("Not sending cue, too fast repeat")
                        return # One packet can only cause 1 que