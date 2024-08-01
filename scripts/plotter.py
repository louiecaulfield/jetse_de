import numpy as np
from matplotlib import pyplot as plt

from packet import Packet

class FootPlotter():
    def __init__(self, channels):
        self.channels = channels
        self.figs, self.axs = plt.subplots(ncols=1, nrows=channels)

        # for ch in range(channels):
        #     self.axs[ch].annotate(f"channel {ch}",
        #                          ha='center', va='center')

        self.linedata = {}
        for ch in range(channels):
            self.linedata[ch] = np.ndarray((4, 1))

        plt.ioff()
        plt.show(block=False)

    def handle(self, packet: Packet):
        np.append(self.linedata[packet.id][0], packet.host_time)
        np.append(self.linedata[packet.id][1], packet.acc[0])
        self.update()

    def update(self):
        print("Swhoing pltos")
        print(self.linedata[1])
        for ch in range(self.channels):
            self.axs[ch].plot(self.linedata[ch][0], self.linedata[ch][1])
        self.figs.canvas.draw()
        self.figs.canvas.flush_events()

    def start(self):
        pass

    def stop(self):
        pass