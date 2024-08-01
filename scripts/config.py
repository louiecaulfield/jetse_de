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
    serial_connect = pyqtSignal(str)
    osc_connect = pyqtSignal(str, int)
    config_saved = pyqtSignal()

    def __init__(self, config, config_path):

        super(ConfigForm, self).__init__()

        self.config = config
        self.config_path = config_path

        layout = QHBoxLayout()

        # General config
        box = QGroupBox("Connection")
        form = QFormLayout()

        layout_connect = QHBoxLayout()

        self.btn_refresh = QPushButton(QIcon.fromTheme("view-refresh"), None)
        # self.btn_refresh.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.btn_refresh.clicked.connect(self.serial_refresh_ports)
        layout_connect.addWidget(self.btn_refresh)

        # Serial port combo box
        tag, name = ("serial_port", "Serial port")
        item = QComboBox()
        item.setPlaceholderText(name)
        item.setObjectName(tag)
        item.currentIndexChanged.connect(self.update_config)
        layout_connect.addWidget(item)
        self.combo_serial = item

        self.btn_connect_serial = QPushButton(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay), None)
        self.btn_connect_serial.clicked.connect(self.serial_connect_clicked)
        self.btn_connect_serial.setEnabled(False)
        layout_connect.addWidget(self.btn_connect_serial)

        self.serial_refresh_ports()

        form.addRow(self.tr("port"), layout_connect)

        # Auto-start
        tag, name = ("autostart", "auto-start")
        item = QCheckBox()
        item.setCheckState(Qt.CheckState.Checked if self.config.autostart else Qt.CheckState.Unchecked)
        item.setObjectName(tag)
        item.stateChanged.connect(self.update_config)
        form.addRow(self.tr(name), item)

        box.setLayout(form)
        layout.addWidget(box)

        # OSC config
        box = QGroupBox("OSC Server Config")
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

        # OSC port
        tag, name = ("osc_port", "UDP port")
        item = QSpinBox()
        item.setMinimum(1024)
        item.setMaximum(60000)
        item.setValue(getattr(self.config, tag))
        item.setObjectName(tag)
        item.valueChanged.connect(self.update_config)
        form.addRow(self.tr(name), item)

        form_with_button.addLayout(form)

        # OSC connect button
        self.btn_connect_osc = QPushButton("Connect")
        self.btn_connect_osc.clicked.connect(self.osc_connect_clicked)
        form_with_button.addWidget(self.btn_connect_osc)

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

        print(f"Updating config from {tag}")
        if isinstance(item, QSpinBox) or \
           isinstance(item, QDoubleSpinBox):
            setattr(self.config, tag, item.value())
        elif isinstance(item, QLineEdit):
            setattr(self.config, tag, item.text())
        elif isinstance(item, QComboBox):
            setattr(self.config, tag, item.currentData())
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

        match tag:
            case "serial_port":
                self.btn_connect_serial.setEnabled(item.currentData() is not None)

        self.config_changed.emit(self.config, tag)

    def update_trigger(self, channel: int, axis: int, direction: int, level: float, enabled: bool):
        self.config.levels[channel][axis * 2 + direction] = level if enabled else inf if direction == 0 else -inf

    def save_clicked(self):
        # print(self.config.dump())
        self.config.save(self.config_path)
        self.config_saved.emit()

    def serial_refresh_ports(self):
        currentPort = self.combo_serial.currentData()
        self.combo_serial.clear()
        for i, p in enumerate(comports()):
            if not p.hwid.startswith("USB"):
                continue
            self.combo_serial.addItem(f"{p.name} - {p.description}", p.device)

        currentIndex = self.combo_serial.findData(currentPort)
        if currentIndex == -1:
            currentIndex = self.combo_serial.findData(self.config.serial_port)
        self.combo_serial.setCurrentIndex(currentIndex)

    def serial_connect_clicked(self):
        self.combo_serial.setEnabled(False)
        self.btn_refresh.setEnabled(False)
        self.btn_connect_serial.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop))
        self.serial_connect.emit(self.config.serial_port)

    def serial_disconnected(self):
        self.serial_refresh_ports()
        self.combo_serial.setEnabled(True)
        self.btn_refresh.setEnabled(True)
        self.btn_connect_serial.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))

    def osc_connect_clicked(self):
        self.btn_connect_osc.setEnabled(False)
        self.btn_connect_osc.setText(self.btn_connect_osc.text() + "ing")
        self.osc_connect.emit(self.config.osc_ip, self.config.osc_port)

    def osc_connected(self, connected: bool):
        self.btn_connect_osc.setText("Disconnect" if connected else "Connect")
        self.btn_connect_osc.setEnabled(True)

class TrackerConfig(yaml.YAMLObject):
    def __init__(self,
                 channels: List[int],
                 threshold: List[int],
                 duration: List[int],
                 axes: List[bool],
                 cue: str,
                 repeat_same: int,
                 repeat_different: int):
        self.channels = channels
        self.threshold = threshold
        self.duration = duration
        self.cue = cue
        self.axes = axes
        self.repeat_same = repeat_same
        self.repeat_different = repeat_different

class Config(yaml.YAMLObject):
    def __init__(self):
        self.osc_ip = "10.10.10.2"
        self.osc_port = 5302
        self.channels = [1,2]
        self.serial_port = ""
        self.autostart = False

        self.trackers = []
        for i in range(7):
            self.trackers.append(TrackerConfig(
                                    [2*i+1, 2*i+2],
                                    [20] * 2,
                                    [10] * 2,
                                    [[True] * 6, [True] * 6],
                                    f"{(i+1)*10}",
                                    750,
                                    750 // 3))

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