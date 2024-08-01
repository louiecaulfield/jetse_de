from time import time
from collections import deque

class RateCounter:
    def __init__(self, count):
        self.timestamps = deque(maxlen=count)

    def event(self):
        self.timestamps.append(time())

    def __call__(self) -> float:
        if len(self.timestamps) < 2:
            return 0
        return len(self.timestamps) / (self.timestamps[-1] - self.timestamps[0])