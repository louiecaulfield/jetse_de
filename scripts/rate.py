from time import time
from collections import deque

class RateCounter:
    def __init__(self, count):
        self.timestamps = deque(maxlen=count)

    def event(self):
        self.timestamps.append(time())

    def reset(self):
        self.timestamps.clear()

    def older_than(self, time_ms):
        if len(self.timestamps) == 0:
            return True
        print(f"Older than {time_ms}? {time() - self.timestamps[-1]}")
        return (time() - self.timestamps[-1]) * 1000 > time_ms

    def __call__(self) -> float:
        if len(self.timestamps) < 2:
            return 0
        return len(self.timestamps) / (self.timestamps[-1] - self.timestamps[0])