from PyQt6.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot
import sys, traceback
from worker import WorkerSignals

from packet import Packet
from queue import Queue
from rate import RateCounter
import serial

class SensorInterface(QRunnable):
    def __init__(self, port: str):
        super(SensorInterface, self).__init__()
        self.rate = RateCounter(100)
        self.portname = port
        self.running = False
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        last_packet = Packet.random(1, [100,100,100])
        try:
            self.running = True
            self.port = serial.Serial(self.portname, 115200)
            self.port.close()
            self.port.open()
            self.sync()

            while(self.running):
                packet = Packet.from_bytes(self.port.read(Packet.size))
                if packet is None:
                    self.sync()
                else:
                    self.rate.event()
                    self.signals.result.emit(packet)
                    # print(packet.sensor_time - last_packet.sensor_time)
                    # last_packet = packet

        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        finally:
            self.signals.finished.emit()

    def sync(self):
        tries = 0
        magic = 0x00
        packet = None
        while packet is None and tries < 10:
            magic_tries = 0
            while magic != 0xBAE1 and magic_tries < 100:
                byte = self.port.read(1)
                if len(byte) != 1:
                    raise Exception("Couldn't read byte")
                magic = ((magic << 8) | byte[0]) & 0xFFFF
                magic_tries += 1
            if magic != 0xBAE1:
                raise Exception("Failed to sync to serial port, magic not found")
            packet = Packet.from_bytes(bytes([0xBA, 0xE1]) + self.port.read(Packet.size - 2))
            tries += 1
        if packet is None:
            raise Exception(f"Failed to sync to serial port after {tries} tries")
        print(f"Sync done after {tries} attempt(s)")

    def stop(self):
        self.running = False
        self.port.cancel_read()
