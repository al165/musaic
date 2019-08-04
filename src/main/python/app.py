
#pylint: disable=invalid-name,missing-docstring

import time
import threading
import tkinter as tk
import multiprocessing

from pythonosc import udp_client
from mido import Message, MidiFile, MidiTrack, MetaMessage

from core import Instrument, DEFAULT_SECTION_PARAMS
from network import NetworkEngine
#from gui.gui import TimeLine, InstrumentPanel

APP_NAME = "musAIc (v0.9.0.)"

CLIENT_ADDR = '127.0.0.1'
#CLIENT_ADDR = '192.168.56.102'
#CLIENT_ADDR = '100.75.0.230'
CLIENT_PORT = 57120

STOPPED = 0
PLAYING = 1


class Player(multiprocessing.Process):

    def __init__(self, msgQueue, clockVar):
        super(Player, self).__init__()

        self.msgQueue = msgQueue
        self.clockVar = clockVar

        # {barNum: {tick: [('/addr', (args))]}}
        #self.messages = dict()
        self.instrumentMessages = dict()
        self.instrumentChannels = dict()
        self.instrumentOctave = dict()
        self.instrumentMute = dict()

        self.client = udp_client.SimpleUDPClient(CLIENT_ADDR, CLIENT_PORT)
        self.sendClock = True
        self.bpm = 80
        self.globalTranspose = 0

        self.stopRequest = multiprocessing.Event()
        self.playing = multiprocessing.Event()
        self.stopping = False

    def run(self):
        while not self.stopRequest.is_set():

            self.checkMessages()

            if self.playing.is_set():
                # --- Before measure starts
                print('[PLAYER]', 'Bar', self.clockVar[0])

                # BPM=80
                tickTime = (60/self.bpm)/24

                measures = [(id_, m.get(self.clockVar[0], dict()))
                            for id_, m in self.instrumentMessages.items()]
                clockOn = time.time()

                # --- During measure
                for tick in range(24 * 4):
                    if self.sendClock:
                        self.client.send_message('/clock', tick)
                    self.clockVar[1] = tick
                    for measure in measures:
                        for event in measure[1].get(tick, []):
                            addr, (_, nn, vel) = event
                            if not self.instrumentMute[measure[0]]:
                                nn += (12*self.instrumentOctave[measure[0]])
                                nn += self.globalTranspose
                                args = (self.instrumentChannels[measure[0]], nn, vel)
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
                if self.clockVar[2] == 0:
                    print('[Player]', 'stopping...')
                    #self.clockVar[1] = 0
                    self.allOff()
                    self.client.send_message('/clockStop', 1)
                    self.stopping = False


            else:
                time.sleep(0.1)


    def join(self, timeout=None):
        self.stopRequest.set()
        self.allOff()
        super(Player, self).join(timeout)

    def checkMessages(self):
        try:
            while True:
                # format (id, messages)
                msg = self.msgQueue.get(block=False)
                try:
                    mType = msg['type']
                    data = msg['data']
                except KeyError:
                    print('[Player]', 'Message in wrong format:', msg)
                    continue

                #print(mType, data)
                if mType == 'midi':
                    # recieved midi data...
                    self.instrumentMessages[data[0]] = data[1]
                elif mType == 'chan':
                    # recieve channel change...
                    self.instrumentChannels[data[0]] = data[1]
                elif mType == 'mute':
                    # recieved mute change...
                    self.instrumentMute[data[0]] = data[1]
                elif mType == 'octave':
                    # recieved octave trasposition...
                    self.instrumentOctave[data[0]] = data[1]
                elif mType == 'bpm':
                    # change of BPM...
                    self.bpm = data
                elif mType == 'global_transpose':
                    # change of global transposition...
                    self.globalTranspose = data
                elif mType == 'client_options':
                    print('[Player]', 'client options set', data)
                    addr = data[0]
                    port = data[1]
                    self.client = udp_client.SimpleUDPClient(addr, port)
                    self.sendClock = data[2]
                else:
                    print('[Player]', 'Unknown message type:', msg)

        except multiprocessing.queues.Empty:
            return

    def setPlaying(self, n=None):
        if self.playing.is_set():
            return

        if n != None:
            self.clockVar[0] = n
        self.clockVar[2] = 1
        self.client.send_message('/clockStart', 1)
        self.playing.set()

    def setStop(self):
        self.playing.clear()
        self.stopping = True
        self.clockVar[2] = 0
        print('[Player]', 'setStop', self.stopping)

    def allOff(self):
        print('[Player]', 'allOff')
        self.client.send_message('/panic', 0)


class Engine(threading.Thread):

    def __init__(self, resources_path=None, guiHandle=None, argv=None):
        super(Engine, self).__init__()

        self.guiHandle = guiHandle

        self.instruments = []
        self.instrumentOctave = dict()
        self.global_transpose = 0

        self.msgQueue = multiprocessing.Queue()
        self.requests = []
        self.netRequestQueue = multiprocessing.Queue()
        self.netReturnQueue = multiprocessing.Queue()

        self.clientOptions = {
            'addr': CLIENT_ADDR,
            'port': CLIENT_PORT,
            'clock': True
        }

        self.setClientOptions(CLIENT_ADDR, CLIENT_PORT, True)

        self.clockVar = multiprocessing.Array('i', [0, 0, 0])
        self.player = Player(self.msgQueue, self.clockVar)

        self.networkEngine = NetworkEngine(self.netRequestQueue,
                                           self.netReturnQueue,
                                           resources_path=resources_path)

        self.status = STOPPED
        self.stopRequest = multiprocessing.Event()

        self.player.start()
        self.networkEngine.start()

    def run(self):
        while not self.stopRequest.is_set():
            self.checkSendMessages()
            self.checkReturnedMessages()

            time.sleep(1/10)

    def checkSendMessages(self):
        # find all requests that meet requirements and send to network...
        unsentMsgs = []
        for msg in self.requests:
            if not any([b.isEmpty() for b in msg['requires']]):
                #print('[Engine]', 'adding measure', msg['measure_address'], 'to requests queue')
                payload = {
                    'request': msg['request'],
                    'measure_address': msg['measure_address']
                }
                self.netRequestQueue.put(payload)
            else:
                unsentMsgs.append(msg)
        self.requests = unsentMsgs

    def checkReturnedMessages(self):
        # check for any returned messages...
        try:
            result = self.netReturnQueue.get(False)
            #print('[Engine]', 'recieved result for measure', result['measure_address'], ':')
            #print(result['result'])
            self.getMeasure(*result['measure_address']).setNotes(result['result'])

        except multiprocessing.queues.Empty:
            pass

    def join(self, timeout=None):
        self.stopRequest.set()
        self.player.join(timeout)
        self.networkEngine.join(timeout)
        super(Engine, self).join(timeout)

    def sendInstrumentEvents(self, id_=None):
        #print('[Engine]', 'sending instrument events for', id_)
        if id_ != None:
            msg = {'type': 'midi'}
            msg['data'] = (id_, self.instruments[id_].compileMidiMessages())
            self.msgQueue.put(msg)
        else:
            for instrument in self.instruments:
                self.sendInstrumentEvents(instrument.id_)

    def changeChannel(self, insID, newChan):
        self.instruments[insID].chan = newChan
        msg = {'type': 'chan',
               'data': (insID, newChan)}
        self.msgQueue.put(msg)

    def changeMute(self, insID, mute=False):
        msg = {'type': 'mute',
               'data': (insID, mute)}
        self.msgQueue.put(msg)

    def changeOctaveTranspose(self, insID, octave=0):
        msg = {'type': 'octave',
               'data': (insID, octave)}
        self.instrumentOctave[insID] = octave
        self.msgQueue.put(msg)

    def setGlobalTranspose(self, transpose=0):
        msg = {'type': 'global_transpose',
               'data': transpose}
        self.global_transpose = transpose
        self.msgQueue.put(msg)

    def setBPM(self, bpm=80):
        if bpm < 20:
            bpm = 20
        elif bpm > 300:
            bpm = 300

        msg = {'type': 'bpm',
               'data': bpm}
        self.msgQueue.put(msg)

    def setClientOptions(self, addr, port, clock):
        self.clientOptions['addr'] = addr
        self.clientOptions['port'] = port
        self.clientOptions['clock'] = clock
        msg = {'type': 'client_options',
               'data': (addr, port, clock)}
        self.msgQueue.put(msg)

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
        instrument.track.addCallback(lambda x: self.sendInstrumentEvents(id_))
        self.instruments.append(instrument)
        self.changeChannel(id_, id_+1)
        self.changeOctaveTranspose(id_)
        self.changeMute(id_)
        return instrument

    def measuresAt(self, instrumentID, n):
        assert isinstance(n, (int, list, tuple))
        try:
            return self.instruments[instrumentID].measuresAt(n)
        except IndexError:
            print('[Engine]', 'cannot find instrument', instrumentID)
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
                for t, e in m.getMidiEvents().items():
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
                nn = args[1] + 12*self.instrumentOctave[instrument.id_] + self.global_transpose
                msg = Message(msgType, channel=instrument.chan,
                              note=nn, velocity=args[2], time=t)
                track.append(msg)

            track.append(MetaMessage('end_of_track'))
            mid.tracks.append(track)

        mid.save(name)
        print('[Engine]', 'done')


#class MusaicApp:
#
#    def __init__(self):
#        self.root = tk.Tk()
#        self.root.title(APP_NAME)
#        self.root.geometry('1500x500+10+50')
#        self.root.resizable(0, 0)
#        self.mainframe = tk.Frame(self.root)
#        self.mainframe.pack(fill='both', expand=True)
#
#        self.engine = Engine(guiHandle=self)
#
#        self.addInsButton = tk.Button(self.mainframe, text='+', command=self.addInstrument,
#                                      width=40)
#        self.addInsButton.grid(row=2, column=0, sticky='ew')
#
#        self.instrumentPanels = []
#        self.timeLine = TimeLine(self.mainframe, self.instrumentPanels, self.engine)
#
#        mainControls = tk.Frame(self.mainframe)
#        playButton = tk.Button(mainControls, text='play', command=self.engine.startPlaying)
#        playButton.grid(row=0, column=0)
#        stopButton = tk.Button(mainControls, text='stop', command=self.engine.stopPlaying)
#        stopButton.grid(row=0, column=1)
#        saveButton = tk.Button(mainControls, text='export', command=self.engine.exportMidiFile)
#        saveButton.grid(row=0, column=2)
#        mainControls.grid(row=0, column=0)
#
#        self.guiLoop()
#        self.engine.start()
#        self.addInstrument()
#
#        self.root.mainloop()
#
#        print('Closing musaAIc', end='')
#        self.engine.join(timeout=1)
#        print()
#
#    def addInstrument(self):
#        instrument = self.engine.addInstrument()
#        panel = InstrumentPanel(self.mainframe, instrument, self.engine, self.timeLine)
#        panel.newSection()
#        self.instrumentPanels.append(panel)
#        for i, insPanel in enumerate(self.instrumentPanels):
#            insPanel.updateLeadOptions([j for j in range(len(self.instrumentPanels)) if j != i])
#        self.addInsButton.grid(row=len(self.instrumentPanels)+2)
#
#    def guiLoop(self):
#        barNum, tick = self.engine.getTime()
#        self.timeLine.updateCursor(barNum, tick)
#        for ip in self.instrumentPanels:
#            ip.updateCursor(barNum, tick)
#
#        self.root.after(1000//20, self.guiLoop)
#
#    def requestRedraw(self, insID=None):
#        if insID:
#            self.instrumentPanels[insID].updateCanvas()
#        else:
#            for instrumentPanel in self.instrumentPanels:
#                instrumentPanel.updateCanvas()
#
#
#if __name__ == '__main__':
#    app = MusaicApp()

# EOF
