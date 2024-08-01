import struct
from random import random
from time import time

class Packet():
    now = time()
    motion_keys =  ["z_pos", "z_neg", "y_pos", "y_neg", "x_pos", "x_neg"]
    motion_keys_short =  ["Z", "z", "Y", "y", "X", "x"]
    format = '<HBLLhhhBBBBB'
    size = struct.calcsize(format)

    def __init__(self, id:int, sensor_time:int,
                 cfg_update: bool, threshold: int, duration: int,
                 motion: list[bool], motion_time: int, acc:tuple[float, float, float]):
        self.host_time = time()
        self.id = id
        self.cfg_update = cfg_update
        self.threshold = threshold
        self.duration = duration
        self.sensor_time = sensor_time
        self.motion = motion
        self.motion_time = motion_time
        self.acc = acc

    def __repr__(self) -> str:
        motion_str = "".join([self.motion_keys_short[i] if v else " " for i, v in enumerate(self.motion)])

        str = f"[{self.id} - {self.sensor_time:10d} ms - THR:{self.threshold:3d} - DUR:{self.duration:3d} ms"
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
            cfg_update, cfg_threshold, cfg_duration,
            checksum_exp) = struct.unpack(Packet.format, buf)

        if magic != 0xE1BA:
            print(f"Unexpected magic {magic:04X}")
            return None

        checksum = sum(buf[2:-1]) & 0xff
        if checksum != checksum_exp:
            print(f"Unexpected checksum {checksum:02X} != {checksum_exp:02X}")
            return None

        return cls(id, sensor_time,
                   cfg_update, cfg_threshold, cfg_duration,
                    [(motion_status & (1 << i) != 0) for i in range(8)][2:],
                    time_last_motion,
                    (acc_x, acc_y, acc_z))

    @classmethod
    def random(cls, id, ranges) -> "Packet":
        return cls(id,
                   time() - cls.now,
                   False, 0, 0, [], -1, tuple([random() * i for i in ranges]))

class Config():
    def __init__(self, channel: int, threshold: int, duration: int):
        self.channel = channel & 0xff
        self.threshold = threshold & 0xff
        self.duration = duration & 0xff

    def bytes(self) -> bytes:
        payload = [0xE1, 0xBA, self.channel, self.threshold, self.duration]
        payload.append(sum(payload) & 0xff)
        return bytes(payload)

    def __repr__(self):
        return f"<Config:CH{self.channel}:THR{self.threshold}:DUR{self.duration}>"
