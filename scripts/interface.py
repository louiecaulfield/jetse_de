from PyQt6.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot
import sys, traceback
from worker import WorkerSignals

from packet import *
from queue import Queue
from rate import RateCounter
import serial
from cobs import cobs
from time import sleep

class SensorInterface(QRunnable):
    def __init__(self, port: str, n_channels: int):
        super(SensorInterface, self).__init__()
        self.rate = RateCounter(10)
        self.portname = port
        self.running = False
        self.signals = WorkerSignals()
        self.config_q = Queue()

        self.channel_config = [ChannelConfig(i, 255,255) for i in range(n_channels)]
        self.channel_config_dirty = [True for i in range(n_channels)]

    def receive(self, timeout=None):
        self.port.timeout = timeout
        buf_enc = self.port.read_until(expected=b'\x00')
        try:
            buf = cobs.decode(buf_enc[:-1])
            return packet_from_bytes(buf)

        except cobs.DecodeError as e:
            print(e)
            return None

    def send_config(self, channel):
        config = self.channel_config[channel]
        buf = cobs.encode(config.get_bytes()) + b'\x00'
        for tries in range(20):
            self.port.write(buf)

            # Receiver should send back packet by means of ACK
            ack = self.receive(1000)
            if config == ack:
                self.channel_config_dirty[channel] = False
                return

        raise Exception(f"Failed to get ACK on config for channel {channel}")

    def send_reset(self):
        self.port.write(cobs.encode(ResetPacket().get_bytes()) + b'\x00')

    def get_config_from_q(self):
        while not self.config_q.empty():
            cfg = self.config_q.get()
            self.channel_config[cfg.channel] = cfg
            self.channel_config_dirty[cfg.channel] = True

    def send_dirty_config(self):
        for (ch, dirty) in enumerate(self.channel_config_dirty):
            if not dirty:
                continue

            self.send_config(ch)

    @pyqtSlot()
    def run(self):
        attempts = 10
        self.running = True
        try:
            while(self.running):
                try:
                    self.port = serial.Serial(self.portname, 115200, dsrdtr=True)
                    self.port.timeout = None
                    self.port.close()
                    self.port.open()
                    self.send_reset()
                    self.port.dtr = False
                    sleep(0.1)
                    self.port.dtr = True

                    while(self.running):
                        packet = self.receive(10)
                        match packet:
                            case ChannelEventPacket():
                                self.rate.event()
                                self.signals.result.emit(packet)
                            case ChannelConfigRequestPacket():
                                self.get_config_from_q()
                                self.send_config(packet.channel)
                                continue
                            case LogPacket():
                                self.signals.result.emit(packet)
                                continue
                            case _:
                                print(f"Received garbage on {self.portname}")
                                continue

                        self.get_config_from_q()
                        self.send_dirty_config()
                except Exception as e:
                    if attempts == 0 or not self.running:
                        raise e
                    attempts -= 1
                    # traceback.print_exc()
                    # print(e)
                    print("[!!!] Port communication failed - restarting")
                    sleep(0.1)
        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        finally:
            try:
                self.signals.finished.emit()
            except RuntimeError:
                print("SensorInterface not sending finished signal - quitting")
            finally:
                self.port.close()

    def stop(self):
        self.running = False
        try:
            self.port.cancel_read()
        except Exception as e:
            print("Failed to cancel serial port operation" + str(e))

    def update_config(self, config:  ChannelConfig):
        self.config_q.put(config)
