
#pylint: disable=invalid-name,missing-docstring

import time
import threading
import multiprocessing

from collections import defaultdict

import tkinter as tk

from pythonosc import udp_client

from core import Instrument
from gui import TimeLine, InstrumentPanel

CLIENT_ADDR = '127.0.0.1'
CLIENT_PORT = 57120

STOPPED = 0
PLAYING = 1


class Player(multiprocessing.Process):

    def __init__(self, client, msgQueue):
        super(Player, self).__init__()

        self.client = client
        self.msgQueue = msgQueue

        self.barNum = 0
        self.tick = 0

        # self.messages  = {barNum: {tick: [('/addr', (args))]}}
        self.messages = dict()

        self.startTime = time.time()

        self.stopRequest = multiprocessing.Event()
        self.playing = multiprocessing.Event()

    def run(self):
        while not self.stopRequest.is_set():
            if self.playing.is_set():
                try:
                    self.messages = self.msgQueue.get(block=False)
                except multiprocessing.queues.Empty:
                    pass

                # BPM=80
                tickTime = (60/80)/24

                measure = self.messages.get(self.barNum, [])
                clockOn = time.time()

                for tick in range(24 * 4):
                    self.client.send_message('/clock', tick)
                    self.tick = tick
                    for event in measure.get(tick, []):
                        for addr, args in event:
                            print(addr, args)
                            self.client.send_message(addr, args)

                    if self.stopRequest.is_set():
                        return

                    nextTime = clockOn + (i+1)*tickTime
                    time.sleep(max(0, nextTime - time.time()))

                self.tick = 0

            else:
                time.sleep(0.01)

    def join(self, timeout=None):
        self.stopRequest.set()
        super(Player, self).join(timeout)

    def setPlaying(self, n=0):
        if self.playing.is_set():
            return
        self.barNum = n
        self.client.send_message('/clockStart', 1)
        self.startTime = time.time()
        self.playing.set()

    def setStop(self):
        self.playing.clear()


class Engine(threading.Thread):

    def __init__(self, instruments, player, msgQueue):
        super(Engine, self).__init__()

        self.instruments = instruments
        self.player = player
        self.msgQueue = msgQueue

        self.currentBar = 0
        self.status = STOPPED

        self.stopRequest = multiprocessing.Event()

    def run(self):
        while not self.stopRequest.is_set():
            # 25 times a second make sure every status is correct and any jobs need
            # to be done... (e.g. update player)
            if self.status == PLAYING:
                # make sure the player has messages in the queue...

                # update current bar...
                pass

            elif self.status == STOPPED:
                pass

            time.sleep(1000//25)

    def join(self, timeout=None):
        self.stopRequest.set()
        super(Engine, self).join(timeout)

    def getAllEvents(self):
        events = defaultdict(dict)

#        for instrument in self.instruments:
#            for n, m in enumerate(instrument.track.flatMeasures):
#                events[n][]



        #for instrument in self.instruments:
        #    event = instrument.measureAt(n).MIDIEvents
        #    if event:
        #        events.append(event)
        return events

    def startPlaying(self):
        while not self.msgQueue.empty():
            _ = self.msgQueue.get()

        events = self.getAllEvents()
        if events:
            self.msgQueue.put(events)

        self.player.setPlaying()
        self.status = PLAYING




class MusaicApp:

    def __init__(self):
        self.root = tk.Tk()
        self.mainframe = tk.Frame(self.root)
        self.mainframe.pack()

        self.addInsButton = tk.Button(self.mainframe, text='+', command=self.addInstrument,
                                      width=40)
        self.addInsButton.grid(row=2, column=0, sticky='ew')

        self.instruments = []
        self.instrumentPanels = []
        self.timeLine = TimeLine(self.mainframe, self.instrumentPanels)

        client = udp_client.SimpleUDPClient(CLIENT_ADDR, CLIENT_PORT)
        msgQueue = multiprocessing.Queue()
        self.player = Player(client, msgQueue)

        engine = Engine(self.instruments, self.player, msgQueue)

        self.root.mainloop()


    def addInstrument(self):
        id_ = len(self.instruments)
        instrument = Instrument(id_, 'INS ' + str(id_), 1)
        panel = InstrumentPanel(self.mainframe, instrument, self.timeLine)

        self.instruments.append(instrument)
        self.instrumentPanels.append(panel)
        self.addInsButton.grid(row=len(self.instruments)+2)


if __name__ == '__main__':
    app = MusaicApp()

# EOF
