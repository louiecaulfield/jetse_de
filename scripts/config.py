from PyQt6.QtWidgets import *
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QIcon

import yaml
from pathlib import Path
from serial.tools.list_ports import comports
from math import inf
from typing import List

class ConfigForm(QWidget):
    config_changed = pyqtSignal(object, str)
    serial_connect = pyqtSignal(list)
    connect_osc_tx = pyqtSignal(str, int)
    connect_osc_rx = pyqtSignal(int)
    config_saved = pyqtSignal()

    def __init__(self, config, config_path):

        super(ConfigForm, self).__init__()

        self.config = config
        self.config_path = config_path

        layout = QHBoxLayout()

        # General config
        box = QGroupBox("Tracker receiver connection")
        form = QFormLayout()

        layout_connect = QHBoxLayout()

        self.btn_refresh = QPushButton(QIcon.fromTheme("view-refresh"), "Refresh")
        # self.btn_refresh.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.btn_refresh.clicked.connect(self.serial_refresh_ports)
        layout_connect.addWidget(self.btn_refresh)
        form.addRow(self.tr("port"), layout_connect)

        # Serial port combo box
        self.combo_serial = []
        for i in range(2):
            tag, name = (f"serial_port_{i}", f"Serial port {i}")
            item = QComboBox()
            item.setPlaceholderText(name)
            item.setObjectName(tag)
            item.currentIndexChanged.connect(self.update_config)
            form.addRow(self.tr(name), item)
            self.combo_serial.append(item)

        # Connect button
        self.btn_connect_serial = QPushButton(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay), "Connect")
        self.btn_connect_serial.clicked.connect(self.serial_connect_clicked)
        self.btn_connect_serial.setEnabled(False)
        form.addRow(self.tr("connect"),self.btn_connect_serial)
        self.serial_refresh_ports()

        # Auto-start
        tag, name = ("autostart", "auto-start")
        item = QCheckBox()
        item.setCheckState(Qt.CheckState.Checked if self.config.autostart else Qt.CheckState.Unchecked)
        item.setObjectName(tag)
        item.stateChanged.connect(self.update_config)
        form.addRow(self.tr(name), item)

        box.setLayout(form)
        layout.addWidget(box)

        # OSC Sender config
        box = QGroupBox("OSC Send Config")
        form_with_button = QVBoxLayout()
        form = QFormLayout()

        # OSC server IP
        tag, name = ("osc_ip", "IP address")
        item = QLineEdit()
        item.setPlaceholderText(name)
        item.setText(getattr(self.config, tag))
        item.setObjectName(tag)
        item.textChanged.connect(self.update_config)
        form.addRow(self.tr(name), item)

        # OSC send port
        tag, name = ("osc_send_port", "UDP send port")
        item = QSpinBox()
        item.setMinimum(1024)
        item.setMaximum(60000)
        item.setValue(getattr(self.config, tag))
        item.setObjectName(tag)
        item.valueChanged.connect(self.update_config)
        form.addRow(self.tr(name), item)

        tag, name = ("osc_send_autostart", "auto-start")
        item = QCheckBox()
        item.setCheckState(Qt.CheckState.Checked if self.config.osc_send_autostart else Qt.CheckState.Unchecked)
        item.setObjectName(tag)
        item.stateChanged.connect(self.update_config)
        form.addRow(self.tr(name), item)

        form_with_button.addLayout(form)

        # OSC sender connect button
        self.btn_connect_osc_tx = QPushButton("Connect")
        self.btn_connect_osc_tx.clicked.connect(self.osc_tx_connect_clicked)
        form_with_button.addWidget(self.btn_connect_osc_tx)

        box.setLayout(form_with_button)
        layout.addWidget(box)

        # OSC Receiver config
        box = QGroupBox("OSC Receiver Config")
        form_with_button = QVBoxLayout()
        form = QFormLayout()

        # OSC receive port
        tag, name = ("osc_receive_port", "UDP receive port")
        item = QSpinBox()
        item.setMinimum(1024)
        item.setMaximum(60000)
        item.setValue(getattr(self.config, tag))
        item.setObjectName(tag)
        item.valueChanged.connect(self.update_config)
        form.addRow(self.tr(name), item)

        tag, name = ("osc_receive_autostart", "auto-start")
        item = QCheckBox()
        item.setCheckState(Qt.CheckState.Checked if self.config.osc_receive_autostart else Qt.CheckState.Unchecked)
        item.setObjectName(tag)
        item.stateChanged.connect(self.update_config)
        form.addRow(self.tr(name), item)

        form_with_button.addLayout(form)

        # OSC receiver connect button
        self.btn_connect_osc_rx = QPushButton("Start server")
        self.btn_connect_osc_rx.clicked.connect(self.osc_rx_connect_clicked)
        form_with_button.addWidget(self.btn_connect_osc_rx)

        box.setLayout(form_with_button)

        layout.addWidget(box)

        btn_save = QPushButton("save configuration")
        btn_save.clicked.connect(self.save_clicked)
        layout_v = QVBoxLayout()
        layout_v.addLayout(layout)
        layout_v.addWidget(btn_save)

        self.setLayout(layout_v)

    def update_config(self, args = None):
        item = self.sender()
        tag = item.objectName()

        # print(f"Updating config from {tag}")
        if isinstance(item, QSpinBox) or \
           isinstance(item, QDoubleSpinBox):
            setattr(self.config, tag, item.value())
        elif isinstance(item, QLineEdit):
            setattr(self.config, tag, item.text())
        elif isinstance(item, QComboBox):
            setattr(self.config, tag, item.currentData())
            if item.currentData() is None:
                item.setCurrentIndex(-1)
        elif isinstance(item, QCheckBox):
            state = item.checkState() == Qt.CheckState.Checked
            setattr(self.config, tag, state)
        elif isinstance(item, QTableWidget):
            dictionary = getattr(self.config, tag)
            assert(isinstance(dictionary, dict))
            key = args.data(Qt.ItemDataRole.UserRole)
            value = args.text()
            print(f"key {key} value {value}")
            dictionary[key] = value
            setattr(self.config, tag, dictionary)
        else:
            raise AttributeError(f"No config handler for {tag} / {item}")

        if tag.startswith("serial_port"):
            for combo in self.combo_serial:
                if combo == item:
                    continue
                if combo.currentData() == item.currentData():
                    combo.setCurrentIndex(-1)

            self.btn_connect_serial.setEnabled(any([c.currentData() is not None for c in self.combo_serial]))

        self.config_changed.emit(self.config, tag)

    def update_trigger(self, channel: int, axis: int, direction: int, level: float, enabled: bool):
        self.config.levels[channel][axis * 2 + direction] = level if enabled else inf if direction == 0 else -inf

    def save_clicked(self):
        # print(self.config.dump())
        self.config.save(self.config_path)
        self.config_saved.emit()

    def serial_refresh_ports(self):
        ports = [("", None)]
        for i, p in enumerate(comports()):
            if not p.hwid.startswith("USB"):
                continue
            ports.append((f"{p.name} - {p.description}", p.device))

        for (i, combo) in enumerate(self.combo_serial):
            currentPort = combo.currentData()
            combo.clear()
            for (name, device) in ports:
                combo.addItem(name, device)

            currentIndex = combo.findData(currentPort)
            if currentPort is None or currentIndex == -1:
                currentIndex = combo.findData(getattr(self.config, f"serial_port_{i}"))
            combo.setCurrentIndex(currentIndex)

    def serial_connect_clicked(self):
        [combo.setEnabled(False) for combo in self.combo_serial]
        self.btn_refresh.setEnabled(False)
        self.btn_connect_serial.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop))
        self.btn_connect_serial.setText("Disconnect")
        self.serial_connect.emit([combo.currentData() for combo in self.combo_serial])

    def serial_connected(self, connected: bool):
        if connected:
            return

        self.serial_refresh_ports()
        [combo.setEnabled(True) for combo in self.combo_serial]
        self.btn_refresh.setEnabled(True)
        self.btn_connect_serial.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.btn_connect_serial.setText("Connect")

    def osc_tx_connect_clicked(self):
        self.btn_connect_osc_tx.setEnabled(False)
        self.btn_connect_osc_tx.setText(self.btn_connect_osc_tx.text() + "ing")
        self.connect_osc_tx.emit(self.config.osc_ip, self.config.osc_send_port)

    def osc_tx_connected(self, connected: bool):
        self.btn_connect_osc_tx.setText("Disconnect" if connected else "Connect")
        self.btn_connect_osc_tx.setEnabled(True)

    def osc_rx_connect_clicked(self):
        self.btn_connect_osc_rx.setEnabled(False)
        self.connect_osc_rx.emit(self.config.osc_receive_port)

    def osc_rx_connected(self, connected: bool):
        self.btn_connect_osc_rx.setText("Stop server" if connected else "Start server")
        self.btn_connect_osc_rx.setEnabled(True)


class TrackerConfig(yaml.YAMLObject):
    def __init__(self,
                 channels: List[int],
                 threshold: List[int],
                 duration: List[int],
                 axes: List[bool],
                 cue: str,
                 repeat_same: int,
                 repeat_different: int,
                 enabled: bool,
                 alias: str):
        self.channels = channels
        self.threshold = threshold
        self.duration = duration
        self.cue = cue
        self.axes = axes
        self.repeat_same = repeat_same
        self.repeat_different = repeat_different
        self.enabled = enabled
        self.alias = alias

class Config(yaml.YAMLObject):
    def __init__(self):
        self.osc_ip = "10.10.10.2"
        self.osc_send_port = 5302
        self.osc_receive_port = 5305
        self.osc_send_autostart = True
        self.osc_receive_autostart = True
        self.channels = [1,2]
        self.serial_port_0 = ""
        self.serial_port_1 = ""
        self.autostart = False
        # This value must match the N_CHANNELS used for the hardware
        self.n_channels = 24

        self.trackers = []
        for i in range(12):
            self.trackers.append(TrackerConfig(
                                    channels=[2*i, 2*i+1],
                                    threshold=[35] * 2,
                                    duration=[5] * 2,
                                    axes=[[True] * 6, [True] * 6],
                                    cue=f"/cue/{(i+1)*10}/start",
                                    repeat_different=500,
                                    repeat_same=500,
                                    enabled=True,
                                    alias=f"{(i+1)*10}"))

    def dump(self):
        return yaml.dump(self)

    def save(self, file):
        with open(file, "w") as f:
            f.write(self.dump())

    @classmethod
    def validate(cls, o):
        default = cls()
        remove_list = []
        for (k, v) in o.__dict__.items():
            if k not in default.__dict__:
                print(f"removing unknown key {k}")
                remove_list.append(k)
            # elif not isinstance(v, type(default.__dict__[k])):
            #     print(f"removing bad typed key {k} {type(v)}")
            #     remove_list.append(k)
        [o.__dict__.pop(k) for k in remove_list]

        for (k, v) in default.__dict__.items():
            if k not in o.__dict__:
                print(f"adding missing key {k}")
                o.__dict__[k] = v


    @classmethod
    def load(cls, path):
        config_path = Path.cwd() / path
        print(f"Using config file {config_path.resolve()}")
        if not config_path.exists():
            print(f"Writing default config to new config file")
            Config().save(config_path)

        with open(config_path, 'r') as f:
            config = yaml.load(f.read(), Loader=yaml.Loader)

        assert(isinstance(config, cls))
        cls.validate(config)
        return config