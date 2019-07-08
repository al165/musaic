
#pylint: disable=invalid-name,missing-docstring

import time
import threading
import multiprocessing

import tkinter as tk

from pythonosc import udp_client
from mido import Message, MidiFile, MidiTrack, MetaMessage

from core import Instrument
from gui import TimeLine, InstrumentPanel

APP_NAME = "musAIc (v1.0_dev)"

CLIENT_ADDR = '127.0.0.1'
CLIENT_PORT = 57120

STOPPED = 0
PLAYING = 1


class Player(multiprocessing.Process):

    def __init__(self, client, msgQueue, clockVar):
        super(Player, self).__init__()

        self.client = client
        self.msgQueue = msgQueue
        self.clockVar = clockVar

        #self.barNum = 0
        #self.tick = 0

        self.clockVar['barNum'] = 0
        self.clockVar['tick'] = 0

        # self.messages  = {barNum: {tick: [('/addr', (args))]}}
        self.messages = dict()

        self.stopRequest = multiprocessing.Event()
        self.playing = multiprocessing.Event()
        self.stopping = False

    def run(self):
        while not self.stopRequest.is_set():
            if self.playing.is_set():
                # --- Before measure starts
                print('[PLAYER]', 'Bar', self.clockVar['barNum'])
                try:
                    self.messages = self.msgQueue.get(block=False)
                except multiprocessing.queues.Empty:
                    pass

                # BPM=80
                tickTime = (60/80)/24

                measure = self.messages.get(self.clockVar['barNum'], dict())
                clockOn = time.time()

                # --- During measure
                for tick in range(24 * 4):
                    self.client.send_message('/clock', tick)
                    self.clockVar['tick'] = tick
                    #print(measure[tick])
                    for event in measure.get(tick, []):
                        addr, args = event
                        print(addr, args)
                        self.client.send_message(addr, args)

                    if self.stopRequest.is_set():
                        return

                    nextTime = clockOn + (tick+1)*tickTime
                    time.sleep(max(0, nextTime - time.time()))

                # --- After measure
                self.clockVar['barNum'] += 1
                self.clockVar['tick'] = 0

                # --- Stopping playback
                if self.stopping:
                    self.clockVar['tick'] = 0
                    self.allOff()
                    self.client.send_message('/clockStop', 1)
                    self.stopping = False

            else:
                time.sleep(0.01)

    def join(self, timeout=None):
        self.stopRequest.set()
        self.allOff()
        super(Player, self).join(timeout)

    def setPlaying(self, n=None):
        if self.playing.is_set():
            return

        if n:
            self.clockVar['barNum'] = n
        self.client.send_message('/clockStart', 1)
        self.playing.set()

    def setStop(self):
        self.playing.clear()
        self.stopping = True

    def allOff(self):
        self.client.send_message('/panic', 0)

class Engine(threading.Thread):

    def __init__(self):
        super(Engine, self).__init__()

        self.instruments = []

        self.msgQueue = multiprocessing.Queue()

        manager = multiprocessing.Manager()
        client = udp_client.SimpleUDPClient(CLIENT_ADDR, CLIENT_PORT)
        self.clockVar = manager.dict()
        self.player = Player(client, self.msgQueue, self.clockVar)

        self.currentBar = 0
        self.status = STOPPED

        self.stopRequest = multiprocessing.Event()
        self.player.start()

    def run(self):
        pass
        #while not self.stopRequest.is_set():

    def join(self, timeout=None):
        self.stopRequest.set()
        self.player.join(timeout=timeout)
        super(Engine, self).join(timeout)

    def getAllEvents(self):
        print('[Engine]', 'building MIDI events')
        def addEvents(d, n, t, e):
            if n not in events:
                d[n] = dict()

            if t not in events[n]:
                d[n][t] = []

            d[n][t].extend(e)

        events = dict()
        # messages  = {barNum: {tick: [('/addr', (args))]}}
        for instrument in self.instruments:
            for n, m in enumerate(instrument.track.flatMeasures):
                if m:
                    for t, e in m.MIDIEvents.items():
                        addEvents(events, n, t, e)

        return events

    def startPlaying(self):
        while not self.msgQueue.empty():
            _ = self.msgQueue.get()

        events = self.getAllEvents()
        if events:
            self.msgQueue.put(events)

        self.player.setPlaying()
        self.status = PLAYING

    def setBarNumber(self, n):
        if n < 0:
            n = 0
        self.clockVar['barNum'] = n

    def stopPlaying(self):
        self.player.setStop()
        self.status = STOPPED

    def getTime(self):
        return self.clockVar['barNum'], self.clockVar['tick']

    def addInstrument(self):
        id_ = len(self.instruments)
        instrument = Instrument(id_, 'INS ' + str(id_), 1)
        self.instruments.append(instrument)
        return instrument

    def exportMidiFile(self, name='test.mid'):
        #allEvents = self.getAllEvents()
        print('[Engine]', 'exporting MIDI file')
        mid = MidiFile(ticks_per_beat=24, type=1)

        for instrument in self.instruments:
            track = MidiTrack()

            events = []
            for n, m in enumerate(instrument.track.flatMeasures):
                if not m:
                    continue
                for t, e in m.MIDIEvents.items():
                    for msg in e:
                        events.append((n*96+t, msg))

            events.sort(key=lambda x: x[0])

            track.append(MetaMessage('track_name', name=instrument.name))
            for i, e in enumerate(events):
                msgType = {'/noteOn': 'note_on',
                           '/noteOff': 'note_off'}[e[1][0]]
                args = e[1][1]
                if i > 0:
                    t = e[0] - events[i-1][0]
                else:
                    t = e[0]

                print(msgType, args, t)
                msg = Message(msgType, channel=instrument.chan,
                              note=args[1], velocity=args[2], time=t)
                track.append(msg)

            track.append(MetaMessage('end_of_track'))
            mid.tracks.append(track)

        mid.save(name)
        print('[Engine]', 'done')

class MusaicApp:

    def __init__(self):
        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.mainframe = tk.Frame(self.root)
        self.mainframe.pack()

        self.engine = Engine()

        self.addInsButton = tk.Button(self.mainframe, text='+', command=self.addInstrument,
                                      width=40)
        self.addInsButton.grid(row=2, column=0, sticky='ew')

        self.instrumentPanels = []
        self.timeLine = TimeLine(self.mainframe, self.instrumentPanels, self.engine)

        playButton = tk.Button(self.mainframe, text='play', command=self.engine.startPlaying)
        playButton.grid(row=0, column=0)
        stopButton = tk.Button(self.mainframe, text='stop', command=self.engine.stopPlaying)
        stopButton.grid(row=0, column=1)
        saveButton = tk.Button(self.mainframe, text='export', command=self.engine.exportMidiFile)
        saveButton.grid(row=0, column=2)

        self.guiLoop()
        self.engine.start()
        self.root.mainloop()

        print('Closing', end='')
        self.engine.join(timeout=1)
        print()

    def addInstrument(self):
        instrument = self.engine.addInstrument()
        panel = InstrumentPanel(self.mainframe, instrument, self.engine, self.timeLine)

        self.instrumentPanels.append(panel)
        self.addInsButton.grid(row=len(self.instrumentPanels)+2)

    def guiLoop(self):
        barNum, tick = self.engine.getTime()
        self.timeLine.updateCursor(barNum, tick)
        for ip in self.instrumentPanels:
            ip.updateCursor(barNum, tick)

        self.root.after(1000//25, self.guiLoop)

if __name__ == '__main__':
    app = MusaicApp()

# EOF
