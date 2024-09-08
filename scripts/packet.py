import struct
from random import random
from time import time

class PacketType:
    LOG                 = 0
    CHANNEL_EVENT       = 1
    CHANNEL_CONFIG_REQ  = 2
    CHANNEL_CONFIG      = 3

class Packet():
    format_header = '<HB' # Magic + packet type
    format_footer = '<B'  # CRC
    size_header = struct.calcsize(format_header)
    size_footer = struct.calcsize(format_footer)
    size_min = size_header + size_footer

class LogPacket(Packet):
    def __init__(self, msg):
        self.msg = msg

    def __repr__(self) -> str:
        return self.msg

    @classmethod
    def from_payload(cls, buf) -> "ChannelEventPacket":
        return cls(buf.decode('utf-8'))

class ChannelEventPacket(Packet):
    motion_keys =  ["z_pos", "z_neg", "y_pos", "y_neg", "x_pos", "x_neg"]
    motion_keys_short =  ["Z", "z", "Y", "y", "X", "x"]
    format = '<BBLLhhhBBBB'
    size = struct.calcsize(format)

    def __init__(self, frequency: int, id:int, sensor_time:int,
                 cfg_update: bool, threshold: int, duration: int,
                 motion: list[bool], motion_time: int, acc:tuple[float, float, float]):
        self.host_time = time()
        self.frequency = frequency
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

        str = f"[ChanEvent|{self.id:2d} - {self.sensor_time:10d} ms - THR:{self.threshold:3d} - DUR:{self.duration:3d} ms"
        # if self.motion:
        str += f" - MOTION @{self.motion_time:10d}ms" + \
                    "<" + ",".join([f"{v:7d}" for v in self.acc]) + f"> {motion_str}"
        str += "]"
        return str

    @classmethod
    def from_payload(cls, buf) -> "ChannelEventPacket":
        if len(buf) != cls.size:
            print(f"ChannelEventPacket payload bad size {len(buf)} != {cls.size}")
            return None

        (frequency, id, sensor_time,
            time_last_motion,
            acc_x, acc_y, acc_z,
            motion_status,
            cfg_update, cfg_threshold, cfg_duration) = struct.unpack(cls.format, buf)

        return cls(frequency, id, sensor_time,
                   cfg_update, cfg_threshold, cfg_duration,
                    [(motion_status & (1 << i) != 0) for i in range(8)][2:],
                    time_last_motion,
                    (acc_x, acc_y, acc_z))

class ChannelConfigRequestPacket(Packet):
    format = '<B'
    size = struct.calcsize(format)

    def __init__(self, channel:int):
        self.channel = channel

    def __repr__(self) -> str:
        return f"[ChanCfgReq|{self.channel:2d}]"

    @classmethod
    def from_payload(cls, buf) -> "ChannelConfigRequestPacket":
        if len(buf) != cls.size:
            print(f"ChannelConfigRequestPacket payload bad size {len(buf)} != {cls.size}")
            return None

        (channel, ) = struct.unpack(cls.format, buf)

        return cls(channel)

class ChannelConfig():
    format = '<BBB'
    size = struct.calcsize(format)

    def __init__(self, channel: int, threshold: int, duration: int):
        self.channel = channel & 0xff
        self.threshold = threshold & 0xff
        self.duration = duration & 0xff

    def __eq__(self, other: "ChannelConfig"):
        return isinstance(other, ChannelConfig)  and \
               self.channel   == other.channel   and \
               self.threshold == other.threshold and \
               self.duration  == other.duration

    def packet_bytes(self) -> bytes:
        payload = [0xE1, 0xBA, PacketType.CHANNEL_CONFIG, self.channel, self.threshold, self.duration]
        payload.append(sum(payload) & 0xff)
        return bytes(payload)

    @classmethod
    def from_payload(cls, buf) -> "ChannelConfig":
        if len(buf) != cls.size:
            print(f"ChannelConfig payload bad size {len(buf)} != {cls.size}")
            return None

        (channel, threshold, duration) = struct.unpack(cls.format, buf)

        return cls(channel, threshold, duration)

    def __repr__(self):
        return f"[ChanCfg|{self.channel:2d}:THR{self.threshold}:DUR{self.duration}]"

def packet_from_bytes(buf) -> "Packet":
    if len(buf) < Packet.size_min:
        print(f"Buffer too small to be a packet ({len(buf)})")
        return None

    (magic, ptype) = struct.unpack(Packet.format_header, buf[0:Packet.size_header])
    (checksum_exp, ) = struct.unpack(Packet.format_footer, buf[-Packet.size_footer:])

    if magic != 0xBAE1:
        print(f"Unexpected magic {magic:04X}")
        return None

    checksum = sum(buf[0:-1]) & 0xff
    if checksum != checksum_exp:
        print(f"Checksum mismatch {checksum:02X} != {checksum_exp:02X}")
        return None

    payload = buf[Packet.size_header:-Packet.size_footer]
    match ptype:
        case PacketType.LOG:
            return LogPacket.from_payload(payload)
        case PacketType.CHANNEL_CONFIG_REQ:
            return ChannelConfigRequestPacket.from_payload(payload)
        case PacketType.CHANNEL_CONFIG:
            return ChannelConfig.from_payload(payload)
        case PacketType.CHANNEL_EVENT:
            return ChannelEventPacket.from_payload(payload)
        case _:
            print(f"Unsupported packet type {ptype}")
            return payload
