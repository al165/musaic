
#pylint: disable=invalid-name,missing-docstring

import time
import threading
import tkinter as tk
import multiprocessing

from pythonosc import udp_client
from mido import Message, MidiFile, MidiTrack, MetaMessage

from core import Instrument
from network import NetworkEngine
from gui import TimeLine, InstrumentPanel

APP_NAME = "musAIc (v1.0_dev)"

#CLIENT_ADDR = '127.0.0.1'
CLIENT_ADDR = '192.168.78.48'
CLIENT_PORT = 57120

STOPPED = 0
PLAYING = 1


class Player(multiprocessing.Process):

    def __init__(self, client, msgQueue, clockVar):
        super(Player, self).__init__()

        self.client = client
        self.msgQueue = msgQueue
        self.clockVar = clockVar

        # {barNum: {tick: [('/addr', (args))]}}
        #self.messages = dict()
        self.instrumentMessages = dict()

        self.stopRequest = multiprocessing.Event()
        self.playing = multiprocessing.Event()
        self.stopping = False

    def run(self):
        while not self.stopRequest.is_set():
            if self.playing.is_set():
                # --- Before measure starts
                print('[PLAYER]', 'Bar', self.clockVar[0])
                try:
                    while True:
                        # format (id, messages)
                        msg = self.msgQueue.get(block=False)
                        self.instrumentMessages[msg[0]] = msg[1]
                except multiprocessing.queues.Empty:
                    pass

                # BPM=80
                tickTime = (60/80)/24

                #measures = self.messages.get(self.clockVar[0], dict())
                measures = [m.get(self.clockVar[0], dict())
                            for m in self.instrumentMessages.values()]
                clockOn = time.time()

                # --- During measure
                for tick in range(24 * 4):
                    self.client.send_message('/clock', tick)
                    self.clockVar[1] = tick
                    for measure in measures:
                        for event in measure.get(tick, []):
                            addr, args = event
                            print(addr, args)
                            self.client.send_message(addr, args)

                    if self.stopRequest.is_set():
                        return

                    nextTime = clockOn + (tick+1)*tickTime
                    time.sleep(max(0, nextTime - time.time()))

                # --- After measure
                with self.clockVar.get_lock():
                    self.clockVar[0] += 1
                    self.clockVar[1] = 0

                # --- Stopping playback
                if self.stopping:
                    self.clockVar[1] = 0
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
            self.clockVar[0] = n
        self.client.send_message('/clockStart', 1)
        self.playing.set()

    def setStop(self):
        self.playing.clear()
        self.stopping = True

    def allOff(self):
        self.client.send_message('/panic', 0)


class Engine(threading.Thread):

    def __init__(self, guiHandle=None):
        super(Engine, self).__init__()

        self.guiHandle = guiHandle

        self.instruments = []

        self.msgQueue = multiprocessing.Queue()
        self.requests = []
        self.netRequestQueue = multiprocessing.Queue()
        self.netReturnQueue = multiprocessing.Queue()

        client = udp_client.SimpleUDPClient(CLIENT_ADDR, CLIENT_PORT)
        self.clockVar = multiprocessing.Array('i', [0, 0])
        self.player = Player(client, self.msgQueue, self.clockVar)

        self.networkEngine = NetworkEngine(self.netRequestQueue, self.netReturnQueue)

        self.status = STOPPED
        self.stopRequest = multiprocessing.Event()

        self.player.start()
        self.networkEngine.start()

    def run(self):
        while not self.stopRequest.is_set():
            # find all requests that meet requirements and send to network...
            unsentMsgs = []
            for msg in self.requests:
                if not any([b.isEmpty() for b in msg['requires']]):
                    print('[Engine]', 'adding measure', msg['measure_address'], 'to requests queue')
                    self.netRequestQueue.put(msg)
                else:
                    unsentMsgs.append(msg)
            self.requests = unsentMsgs

            try:
                result = self.netReturnQueue.get(False)
                print('[Engine]', 'recieved result for measure', result['measure_address'], ':')
                print(result['result'])
                self.getMeasure(*result['measure_address']).setNotes(result['result'])

                if self.guiHandle:
                    self.guiHandle.requestRedraw()

            except multiprocessing.queues.Empty:
                continue

            time.sleep(1/10)

    def join(self, timeout=None):
        self.stopRequest.set()
        self.player.join(timeout)
        self.networkEngine.join(timeout)
        super(Engine, self).join(timeout)

    def sendInstrumentEvents(self, id_=None):
        if id_:
            self.msgQueue.put((id_, self.instruments[id_].compileMidiMessages()))
        else:
            for instrument in self.instruments:
                self.msgQueue.put((instrument.id_, instrument.compileMidiMessages()))

    def startPlaying(self):
        while not self.msgQueue.empty():
            _ = self.msgQueue.get()

        self.sendInstrumentEvents()

        self.player.setPlaying()
        self.status = PLAYING

    def setBarNumber(self, n):
        if n < 0:
            n = 0
        self.clockVar[0] = n

    def stopPlaying(self):
        self.player.setStop()
        self.status = STOPPED

    def getTime(self):
        return self.clockVar[0], self.clockVar[1]

    def addInstrument(self):
        id_ = len(self.instruments)
        instrument = Instrument(id_, 'INS ' + str(id_), id_+1, self)
        self.instruments.append(instrument)
        return instrument

    def measuresAt(self, instrumentID, n):
        assert isinstance(n, (int, list, tuple))
        try:
            self.instruments[instrumentID].getMeasures(n)
        except IndexError:
            print('[Engine]', 'cannot fint instrument', instrumentID)
            if isinstance(n, int):
                return None
            return [None]*len(n)

    def getMeasure(self, instrumentID, sectionID, measureID):
        try:
            m = self.instruments[instrumentID].sections[sectionID].measures[measureID]
        except (IndexError, KeyError):
            print('[Engine]', f'Cannot find measure {instrumentID}:{sectionID}:{measureID}')
            return None
        return m

    def addPendingRequest(self, requestMsg):
        self.requests.append(requestMsg)

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
                for t, e in m.MidiEvents.items():
                    for msg in e:
                        events.append((n*96+t, msg))

            # sort by time, then note off events
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
        self.mainframe.pack(fill='both', expand=True)

        self.engine = Engine(guiHandle=self)

        self.addInsButton = tk.Button(self.mainframe, text='+', command=self.addInstrument,
                                      width=40)
        self.addInsButton.grid(row=2, column=0, sticky='ew')

        self.instrumentPanels = []
        self.timeLine = TimeLine(self.mainframe, self.instrumentPanels, self.engine)

        mainControls = tk.Frame(self.mainframe)
        playButton = tk.Button(mainControls, text='play', command=self.engine.startPlaying)
        playButton.grid(row=0, column=0)
        stopButton = tk.Button(mainControls, text='stop', command=self.engine.stopPlaying)
        stopButton.grid(row=0, column=1)
        saveButton = tk.Button(mainControls, text='export', command=self.engine.exportMidiFile)
        saveButton.grid(row=0, column=2)
        mainControls.grid(row=0, column=0)

        self.guiLoop()
        self.engine.start()
        self.root.mainloop()

        print('Closing musaAIc', end='')
        self.engine.join(timeout=1)
        print()

    def addInstrument(self):
        instrument = self.engine.addInstrument()
        panel = InstrumentPanel(self.mainframe, instrument, self.engine, self.timeLine)

        self.instrumentPanels.append(panel)
        for i, insPanel in enumerate(self.instrumentPanels):
            insPanel.updateLeadOptions([j for j in range(len(self.instrumentPanels)) if j != i])
        self.addInsButton.grid(row=len(self.instrumentPanels)+2)

    def guiLoop(self):
        barNum, tick = self.engine.getTime()
        self.timeLine.updateCursor(barNum, tick)
        for ip in self.instrumentPanels:
            ip.updateCursor(barNum, tick)

        self.root.after(1000//20, self.guiLoop)

    def requestRedraw(self):
        for instrumentPanel in self.instrumentPanels:
            instrumentPanel.updateCanvas()


if __name__ == '__main__':
    app = MusaicApp()

# EOF
