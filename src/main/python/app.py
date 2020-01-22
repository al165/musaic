#pylint: disable=invalid-name,missing-docstring

import time
import json
import threading
import multiprocessing

from pythonosc import udp_client
import mido
from mido import Message, MidiFile, MidiTrack, MetaMessage

from core import Instrument, DEFAULT_SECTION_PARAMS
from network import NetworkEngine

APP_NAME = "musAIc (v0.9.0.)"

CLIENT_ADDR = '127.0.0.1'
CLIENT_PORT = 57120

STOPPED = 0
PLAYING = 1


def convertMidiToOsc(msg):
    return (msg.type, (msg.channel, msg.note, msg.velocity))


class MediaPlayer(multiprocessing.Process):
    '''Server that plays tracks, either MIDI or OSC type.'''

    def __init__(self, msgQueue, clockVar):
        super(MediaPlayer, self).__init__()

        self.msgQueue = msgQueue
        self.clockVar = clockVar

        # {barNum: {tick: [('/addr', (args))]}}
        #self.messages = dict()
        self.instrumentMessages = dict()
        self.instrumentChannels = dict()
        self.instrumentOctave = dict()
        self.instrumentMute = dict()

        self.client = udp_client.SimpleUDPClient(CLIENT_ADDR, CLIENT_PORT)
        self.sendOscClock = True
        self.sendMidiClock = True
        self.bpm = 80
        self.globalTranspose = 0

        self.stopRequest = multiprocessing.Event()
        self.playing = multiprocessing.Event()
        self.stopping = False

        self.osc = True
        self.midi = False
        self.port = None

        #mido.set_backend('mido.backends.pygame')

    def run(self):
        while not self.stopRequest.is_set():

            self.checkMessages()

            if self.playing.is_set():
                # --- Before measure starts
                print('[MediaPlayer]', 'Bar', self.clockVar[0])

                # BPM=80
                tickTime = (60/self.bpm)/24

                # measures = (instrumentID, {tick: [midiMessages]})
                # for each instrument at current bar number
                measures = [(id_, m.get(self.clockVar[0], dict()))
                            for id_, m in self.instrumentMessages.items() if not
                            self.instrumentMute[id_]]

                clockOn = time.time()

                # --- During measure
                for tick in range(24 * 4):
                    if self.sendOscClock and self.osc:
                        self.client.send_message('/clock', tick)
                    self.clockVar[1] = tick

                    for measure in measures:
                        id_ = measure[0]
                        for msg in measure[1].get(tick, []):
                            nn = msg.note + (12*self.instrumentOctave[measure[0]]) + self.globalTranspose
                            print(nn, msg)
                            self.sendOut(msg.copy(note=nn))

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
                    print('[MediaPlayer]', 'stopping...')
                    #self.clockVar[1] = 0
                    self.allOff()
                    self.client.send_message('/clockStop', 1)
                    self.stopping = False


            else:
                time.sleep(0.1)

    def join(self, timeout=None):
        self.stopRequest.set()
        self.allOff()
        if self.port:
            self.port.reset()
            self.port.close()
        super(MediaPlayer, self).join(timeout)

    def sendOut(self, msg):
        if self.client and self.osc:
            self.client.send_message(*convertMidiToOsc(msg))

        if self.midi and self.port:
            self.port.send(msg)

    def checkMessages(self):
        try:
            while True:
                # format (id, messages)
                msg = self.msgQueue.get(block=False)
                try:
                    mType = msg['type']
                    data = msg['data']
                except KeyError:
                    print('[MediaPlayer]', 'Message in wrong format:', msg)
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
                    print('[MediaPlayer]', 'client options set', data)
                    addr = data[0]
                    port = data[1]
                    self.client = udp_client.SimpleUDPClient(addr, port)
                    self.sendOscClock = data[2]
                elif mType == 'midi_port_setting':
                    print('[MediaPlayer]', 'midi options set:', data)
                    if self.port:
                        self.port.panic()
                        self.port.close()
                    self.port = mido.open_output(data[0], client_name="musAIc")
                elif mType == 'midi_out':
                    self.midi = data[0]
                elif mType == 'osc_out':
                    self.osc = data[0]
                else:
                    print('[MediaPlayer]', 'Unknown message type:', msg)

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

    def allOff(self):
        #print('[MediaPlayer]', 'allOff')
        if self.client and self.osc:
            self.client.send_message('/panic', 0)
        if self.port and self.midi:
            self.port.panic()


class Engine(threading.Thread):

    def __init__(self, resources_path=None, guiHandle=None, argv=None):
        super(Engine, self).__init__()

        self.guiHandle = guiHandle

        self.instruments = dict()
        self.instrumentOctave = dict()
        self.global_transpose = 0
        self.bpm = 80

        self.msgQueue = multiprocessing.Queue()
        self.requests = []
        self.netRequestQueue = multiprocessing.Queue()
        self.netReturnQueue = multiprocessing.Queue()

        self.callbacks = {
            'instrument_added': set(),
            'section_added': set(),
        }

        self.oscOptions = {
            'addr': CLIENT_ADDR,
            'port': CLIENT_PORT,
            'clock': True,
            'send': True
        }

        self.midiOptions = {
            'port': None,
            'clock': True,
            'send': False
        }

        self.setClientOptions(CLIENT_ADDR, CLIENT_PORT, True)

        # clock var [bar_num, tick, status]
        self.clockVar = multiprocessing.Array('i', [0, 0, 0])
        self.player = MediaPlayer(self.msgQueue, self.clockVar)

        self.networkEngine = NetworkEngine(self.netRequestQueue,
                                           self.netReturnQueue,
                                           resources_path=resources_path)

        self.status = STOPPED
        self.stopRequest = multiprocessing.Event()

        #mido.set_backend('mido.backends.pygame')
        mido.set_backend('mido.backends.rtmidi')


        self.player.start()
        self.networkEngine.start()

    def run(self):
        while not self.stopRequest.is_set():
            self.checkSendMessages()
            self.checkReturnedMessages()

            time.sleep(1/30)

    def call(self, event, *args):
        for func in self.callbacks[event]:
            func(*args)

    def addCallback(self, event, func):
        self.callbacks[event].add(func)

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
            for instrument in self.instruments.values():
                self.sendInstrumentEvents(instrument.id_)

    def changeChannel(self, insID, newChan):
        #self.instruments[insID].chan = newChan
        self.instruments[insID].changeChannel(newChan)
        msg = {'type': 'chan',
               'data': (insID, newChan)}
        self.msgQueue.put(msg)

    def changeMute(self, insID, mute=False):
        self.instruments[insID].mute = mute
        msg = {'type': 'mute',
               'data': (insID, mute)}
        self.msgQueue.put(msg)

    def changeOctaveTranspose(self, insID, octave=0):
        msg = {'type': 'octave',
               'data': (insID, octave)}
        self.instrumentOctave[insID] = octave
        self.instruments[insID].octave_transpose = octave
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
        self.bpm = bpm

        msg = {'type': 'bpm',
               'data': bpm}
        self.msgQueue.put(msg)

    def setClientOptions(self, addr, port, clock):
        self.oscOptions['addr'] = addr
        self.oscOptions['port'] = port
        self.oscOptions['clock'] = clock
        msg = {'type': 'client_options',
               'data': (addr, port, clock)}
        self.msgQueue.put(msg)

    def setOscOut(self, out):
        self.oscOptions['send'] = out
        msg = {'type': 'osc_out',
               'data': (out,)}
        self.msgQueue.put(msg)

    def setMidiPort(self, port_name, clock=True):
        self.midiOptions['port'] = port_name
        self.midiOptions['clock'] = clock
        msg = {'type': 'midi_port_setting',
               'data': (port_name, clock)}
        self.msgQueue.put(msg)

    def setMidiOut(self, out):
        self.midiOptions['send'] = out
        msg = {'type': 'midi_out',
               'data': (out,)}
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

    def getMidiPorts(self):
        return mido.get_output_names()

    def addInstrument(self, **kwargs):
        id_ = len(self.instruments.keys())
        name = kwargs.get('name', 'INS ' + str(id_))
        instrument = Instrument(id_, name, id_+1, self)

        instrument.track.addCallback(lambda x: self.sendInstrumentEvents(id_))
        self.instruments[id_] = instrument
        self.changeChannel(id_, id_+1)
        self.changeOctaveTranspose(id_)
        self.changeMute(id_)

        self.call('instrument_added', instrument)

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

    def saveFile(self, name='project.mus'):
        if name[-4:] != '.mus':
            name = name + '.mus'

        print('[Engine]', 'saving project as', name, end='... ')

        data = {
            'global_settings': {
                'bpm': self.bpm,
                'global_transpose': self.global_transpose,
            },
            'instruments': dict()
        }

        for instrument in self.instruments.values():
            ins_data = instrument.getData()
            data['instruments'][ins_data['id']] = ins_data

        #print('[Engine]', 'compiled dictionary, saving...')

        try:
            with open(name, 'w') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print('\n------------')
            print(data)
            print('\n------------')
            print(e)
            return

        print('Done')

    def loadFile(self, fp):
        if fp == '':
            return
        try:
            with open(fp, 'r') as f:
                data = json.load(f)
        except FileNotFoundError:
            return

        print('[Engine]', 'opening file', fp, end='... ')

        # reset environment...
        self.requests = []
        self.stopPlaying()
        self.setBarNumber(0)

        while not self.msgQueue.empty():
            _ = self.msgQueue.get()

        self.instruments = dict()

        # load data...
        self.instrumentOctave = dict()
        self.global_transpose = data['global_settings']['global_transpose']
        self.bpm = data['global_settings']['bpm']

        for insID, insData in data['instruments'].items():
            id_ = int(insID)
            print(insData)
            instrument = Instrument(id_, insData['name'], insData['chan'], self)
            instrument.setData(insData)
            instrument.track.addCallback(lambda x: self.sendInstrumentEvents(id_))
            self.instruments[id_] = instrument
            self.changeChannel(id_, insData['chan'])
            self.changeOctaveTranspose(id_, insData['octave_transpose'])
            self.changeMute(id_, insData['mute'])

            self.call('instrument_added', instrument)

        print('loaded')

    def importMidiFile(self, fp):
        if fp == '':
            return

        print('[Engine]', 'importing MIDI file', fp)

        try:
            midi = mido.MidiFile(fp)
        except FileNotFoundError:
            print('[Engine]', fp, 'not found')
            return

        for track in midi.tracks:
            # create new instrument for each track
            instrument = self.addInstrument(name=track.name)
            instrument.newSection(sectionType='fixed', track=track, tpb=midi.ticks_per_beat)

        print('[Engine]', 'done')

    def exportMidiFile(self, fp='test.mid'):
        if fp == '':
            return

        print('[Engine]', 'exporting MIDI file', fp)

        mid = MidiFile(ticks_per_beat=24, type=1)

        for instrument in self.instruments.values():
            track = MidiTrack()

            events = []
            for n, m in enumerate(instrument.track.flatMeasures):
                if not m:
                    continue
                for t, e in m.getMidiEvents().items():
                    for msg in e:
                        events.append((n*96+t, msg))

            # sort by time, then note off events
            events.sort(key=lambda x: (x[0], x[1].type))

            track.append(MetaMessage('track_name', name=instrument.name))
            for i, e in enumerate(events):
                msg = e[1]

                # when saving, time is number of ticks to NEXT event?
                #try:
                #    t = events[i+1][0] - e[0]
                #except IndexError:
                #    #t = len(instrument.track.flatMeasures) * 96 - e[0]
                #    t = 0

                if i > 0:
                    t = e[0] - events[i-1][0]
                else:
                    t = e[0]



                print(msg, t)
                nn = msg.note + 12*self.instrumentOctave[instrument.id_] + self.global_transpose
                track.append(msg.copy(time=t, note=nn))

            track.append(MetaMessage('end_of_track'))
            mid.tracks.append(track)

        mid.save(fp)

        print('[Engine]', 'done')



# EOF
