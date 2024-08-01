import struct
from random import random
from time import time

class Packet():
    now = time()
    motion_keys =  ["z_pos", "z_neg", "y_pos", "y_neg", "x_pos", "x_neg"]
    motion_keys_short =  ["Z", "z", "Y", "y", "X", "x"]
    format = '<HBQhhhB'
    size = struct.calcsize(format)

    def __init__(self, id:int, sensor_time:int, acc:tuple[float, float, float]):
        self.host_time = time()
        self.id = id
        self.sensor_time = sensor_time
        self.acc = acc

    def __repr__(self) -> str:

        str = f"[{self.id} - {self.sensor_time:10d} ms "
        # if self.motion:
        str += "<" + ",".join([f"{v:7d}" for v in self.acc]) + ">"
        str += "]"
        return str

    @classmethod
    def from_bytes(cls, buf) -> "Packet":
        if len(buf) != Packet.size:
            return None
        (magic, id, sensor_time,
            acc_x, acc_y, acc_z,
            checksum_exp) = struct.unpack(Packet.format, buf)

        if magic != 0xE1BA:
            print(f"Unexpected magic {magic:04X}")
            return None

        checksum = sum(buf[2:-1]) & 0xff
        if checksum != checksum_exp:
            print(f"Unexpected checksum {checksum:02X} != {checksum_exp:02X}")
            return None

        return cls(id, sensor_time / 1e6, (acc_x, acc_y, acc_z))

    @classmethod
    def random(cls, id, ranges) -> "Packet":
        return cls(id, time() - cls.now, tuple([random() * i for i in ranges]))
