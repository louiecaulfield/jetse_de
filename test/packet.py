from queue import Queue
import serial
import struct
import time
import threading


class Packet():
    motion_keys =  ["z_pos", "z_neg", "y_pos", "y_neg", "x_pos", "x_neg"]
    motion_keys_short =  ["Z", "z", "Y", "y", "X", "x"]
    format = '<HBLLhhhBBBB'
    size = struct.calcsize(format)

    def __init__(self, id:int, sensor_time:int,
                 cfg_update: bool, threshold: int,
                 motion: list[bool], motion_time: int, acc:tuple[float, float, float]):
        self.host_time = time.time()
        self.id = id
        self.cfg_update = cfg_update
        self.threshold = threshold
        self.sensor_time = sensor_time
        self.motion = motion
        self.motion_time = motion_time
        self.acc = acc

    def __repr__(self) -> str:
        motion_str = "".join([self.motion_keys_short[i] if v else " " for i, v in enumerate(self.motion)])

        str = f"[{self.id} - {self.sensor_time:10d} ms - {self.threshold:05d} "
        # if self.motion:
        str += f" - MOTION @{self.motion_time:10d}ms" + \
                    "<" + ",".join([f"{v:7d}" for v in self.acc]) + f"> {motion_str}"
        str += "]"
        return str

    @classmethod
    def from_bytes(cls, buf) -> "Packet":
        if len(buf) != Packet.size:
            return None
        (magic, id, sensor_time,
            time_last_motion,
            acc_x, acc_y, acc_z,
            motion_status,
            cfg_update, cfg_threshold,
            checksum_exp) = struct.unpack(Packet.format, buf)

        if magic != 0xE1BA:
            print(f"Unexpected magic {magic:04X}")
            return None

        checksum = sum(buf[2:-1]) & 0xff
        if checksum != checksum_exp:
            print(f"Unexpected checksum {checksum:02X} != {checksum_exp:02X}")
            return None

        return cls(id, sensor_time,
                   cfg_update, cfg_threshold,
                    [(motion_status & (1 << i) != 0) for i in range(8)][2:],
                    time_last_motion,
                    (acc_x, acc_y, acc_z))

class Config():
    def __init__(self, channel: int, threshold: int):
        self.channel = channel & 0xff
        self.threshold = threshold & 0xff

    def bytes(self) -> bytes:
        payload = [0xE1, 0xBA, self.channel, self.threshold]
        payload.append(sum(payload) & 0xff)
        return bytes(payload)

    def __repr__(self):
        return f"<Config:CH{self.channel}:THR{self.threshold}>"

class SerialInterface(threading.Thread):
    def __init__(self, port: str):
        self.port = serial.Serial(port, 115200)
        self.port.close()
        self.port.open()
        self.config_q = Queue()
        self.packet_q = Queue()
        self.running = False
        threading.Thread.__init__(self)

    def sync(self):
        tries = 0
        magic = 0x00
        packet = None
        while packet is None and tries < 10:
            while magic != 0xBAE1:
                magic = ((magic << 8) | self.port.read(1)[0]) & 0xFFFF
            packet = Packet.from_bytes(bytes([0xBA, 0xE1]) + self.port.read(Packet.size - 2))
            tries += 1
        if packet is None:
            raise Exception(f"Failed to sync to serial port after {tries} tries")
        print(f"Sync done after {tries} attempt(s)")

    def run(self):
        self.running = True
        self.sync()
        while(self.running):
            packet = Packet.from_bytes(self.port.read(Packet.size))
            if packet is not None:
                self.packet_q.put(packet)

            if not self.config_q.empty():
                self.port.write(self.config_q.get().bytes())

    def stop(self):
        self.running = False
        self.port.cancel_read()
        print("Waiting for serial thread to stop")
        self.join()
        print("Serial thread stopped")

    def send_config(self, config: Config):
        self.config_q.put(config)

    def get_packet(self) -> Packet:
        return self.packet_q.get()