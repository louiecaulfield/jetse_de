
from pglive.sources.data_connector import DataConnector
from pglive.sources.live_plot import LiveLinePlot, LiveHBarPlot
from pglive.sources.live_categorized_bar_plot import LiveCategorizedBarPlot
from pglive.sources.live_plot_widget import LivePlotWidget
from pglive.sources.live_axis_range import LiveAxisRange
from pglive.sources.live_axis import LiveAxis
from pglive.kwargs import Axis

from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QDoubleSpinBox, QSpinBox, QComboBox
from PyQt6.QtCore import pyqtSignal, Qt
import pyqtgraph as pg

from config import Config
from rate import RateCounter
from typing import List
from math import inf

class DataPlot(LivePlotWidget):
    def __init__(self, title: str, rate_hz: int,
                 color: str, y_range_controller = None):
        super(DataPlot, self).__init__(title=title, y_range_controller=y_range_controller)
        self.color = color
        self.curve = LiveLinePlot(pen=self.color)
        self.addItem(self.curve)
        self.connector = DataConnector(self.curve,max_points=500, plot_rate=rate_hz)
        self.setMouseEnabled(x=False, y=False)
        self.setMenuEnabled(False)

    def mouseDoubleClickEvent(self, event):
        if self.connector.paused:
            self.connector.resume()
        else:
            self.connector.pause()

class DataPlotTriple(QVBoxLayout):
    def __init__(self, title: str, rate_hz: int, y_range_controller = None):
        super(DataPlotTriple, self).__init__()
        axis_colors = {"x":"red", "y":"yellow", "z":"cyan"}
        self.plots = []
        for axis, color in axis_colors.items():
            self.plots.append(DataPlot(f"{title} ({axis}-axis)", rate_hz, color, y_range_controller))
            self.addWidget(self.plots[-1])
        self.connectors = [p.connector for p in self.plots]

class FootPlot(QHBoxLayout):
    trigger_changed = pyqtSignal(int, int, int, float, bool) #channel, axis, direction, level, enabled

    def __init__(self, channel: int, config: Config):
        super(FootPlot, self).__init__()
        self.rate = RateCounter(50)
        self.channel = channel

        self.plot_acc = DataPlotTriple(f" [CH{channel}] Accelerometer data", config.graph_rate_hz)
        self.addLayout(self.plot_acc)

        # Filtered accelero data + Events
        yrange = 30000
        self.plot_filtered = DataPlotTriple(f"[CH{channel}] Accelerometer data / Filtered", config.graph_rate_hz, y_range_controller=LiveAxisRange(fixed_range=[-yrange, yrange]))
        self.addLayout(self.plot_filtered)

        # yrange = 4e6
        # First derivative
        self.plot_deriv = DataPlotTriple(f"[CH{channel}] Accelerometer data / Derivative", config.graph_rate_hz, y_range_controller=LiveAxisRange(fixed_range=[-yrange, yrange]))
        self.threshold_lines = []
        for i, p in enumerate(self.plot_deriv.plots):
            line_pos = pg.InfiniteLine(pos=config.levels[channel][i * 2], angle=0, bounds=[0, yrange], movable=True, pen=pg.mkPen(color=p.color, dash=[2,4]))
            p.addItem(line_pos)
            line_pos.sigPositionChanged.connect(self.threshold_moved)
            line_pos.sigClicked.connect(self.threshold_clicked)

            line_neg = pg.InfiniteLine(pos=config.levels[channel][i * 2 + 1], angle=0, bounds=[-yrange, 0], movable=True, pen=pg.mkPen(color=p.color, dash=[2,4]))
            p.addItem(line_neg)
            line_neg.sigPositionChanged.connect(self.threshold_moved)
            line_neg.sigClicked.connect(self.threshold_clicked)

            self.threshold_lines += [line_pos, line_neg]

        self.addLayout(self.plot_deriv)

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
        self.plot_acc.connectors[axis].cb_append_data_array(*zip(*data))

    def filtered_handler(self, axis: int, data: List[tuple]):
        self.plot_filtered.connectors[axis].cb_append_data_array(*zip(*data))

    def deriv_handler(self, axis: int, data: List[tuple]):
        self.plot_deriv.connectors[axis].cb_append_data_array(*zip(*data))
