#!/usr/bin/env python3

import argparse
from statistics import mean
from termcolor import colored
import time

from packet import SerialInterface, Config
from osc import OscThing, OscDebug, OscQlab
from plotter import FootPlotter

if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument("--ip", default="127.0.0.1",
        help="The ip to connect to")
    parser.add_argument("--send", type=int, default=53000,
        help="The port to send to")

    parser.add_argument("--ctrl-listen", type=int, default=5008,
        help="The port to listen on")
    parser.add_argument("--ctrl-send", type=int, default=5005,
        help="The port to send to")
    parser.add_argument("port", type=str,
        help="The serial port")
    args = parser.parse_args()

    foot_interface = SerialInterface(args.port)

    osc_ctrl = OscDebug("127.0.0.1", args.ctrl_listen, args.ctrl_send, foot_interface.config_q, False)
    osc_remote = OscQlab(args.ip, args.send)
    axes = [
        "x_pos",
        "x_neg",
        "y_pos",
        "y_neg",
        "z_pos",
        "z_neg",
    ]
    osc_remote.map_cue(1, axes, "25.1")
    osc_remote.map_cue(2, axes, "25.1")

    foot_interface.start()
    osc_ctrl.start()
    osc_remote.start()

    plotter = FootPlotter()

    try:
        while(True):
            packet = foot_interface.get_packet()
            osc_remote.handle(packet)
            osc_ctrl.handle(packet)
            plotter.handle(packet)

    except KeyboardInterrupt:
        print("CTRL-C hit, ending")

    plotter.stop()
    foot_interface.stop()
    osc_ctrl.stop()
    osc_remote.stop()
