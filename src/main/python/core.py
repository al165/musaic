
#pylint: disable=invalid-name,missing-docstring

from copy import deepcopy
from collections import defaultdict

DEFAULT_SECTION_PARAMS = {
    'lead': None,
    'length': 4,
    'loop_num': 1,
    'loop_alt_len': 0,
    'loop_alt_num': 2,
    'octave': 4,
    'sample_mode': 'dist',
    'lead_mode': 'melody',
    'context_mode': 'inject',
    'injection_params': (('qb', 'eb'), 'maj'),
    'lead_bar': None,
    'prev_bars': None,
    'chord_mode': 0,
    'meta_data': None,
}

def forceListLength(l, length, alt=None):
    if len(l) > length:
        return l[:length]
    return l + [alt for _ in range(length - len(l))]


class Measure:
    '''
    Measure: Holds note values and associated times
    '''
    def __init__(self, id_, chan=1, notes=None, events=None):

        self.id_ = id_
        self.chan = chan

        self.callbacks = []

        if notes:
            # Note: (nn, start_tick, end_tick), where nn=0 is a pause
            self.notes = notes
            self.convertNotesToMidiEvents()
            self.empty = False
        elif events:
            # {tick: MIDI Event} where MIDI Event = ('/eventType', (chan, nn, vel))
            self.MidiEvents = events
            # FIXME self.convertMidiEventsToNotes()
            self.notes = []
            self.empty = False
        else:
            self.setEmpty()

        self.genRequestSent = False

    def call(self):
        ''' calls functions whenever notes are updated '''
        for func in self.callbacks:
            func()

    def addCallback(self, func):
        if func not in self.callbacks:
            self.callbacks.append(func)

    def convertNotesToMidiEvents(self):
        events = defaultdict(list)
        for n in self.notes:
            if n[0] > 0:
                events[n[1]].append(('/noteOn', (self.chan, n[0], 100)))
                events[n[2]].append(('/noteOff', (self.chan, n[0], 100)))
        self.MidiEvents = dict(events)

    def isEmpty(self):
        return self.empty

    def setNotes(self, notes):
        self.notes = notes
        self.convertNotesToMidiEvents()
        self.empty = False
        self.genRequestSent = False
        self.call()

    def setMidiEvents(self, events):
        self.events = events
        # self.convertMidiEventsToNotes()
        self.empty = False
        self.genRequestSent = False
        self.call()

    def setEmpty(self):
        self.notes = []
        self.MidiEvents = dict()
        self.empty = True
        self.call()

    def __getstate__(self):
        # in order to be picklable, must drop the callbacks...
        state = self.__dict__.copy()
        del state['callbacks']
        return state


class Track:
    '''
    Track: an ordered list of Blocks
    '''
    def __init__(self, instrument):
        ''' callback: function to call whenever self.track changes '''
        self.instrument = instrument

        # {bar number: block}
        self.track = dict()
        # {blockID: [start times]}
        self.blocks = defaultdict(list)

        self.flatMeasures = []
        self.callbacks = []

    def call(self):
        ''' execute functions when self.track if updated '''
        for func in self.callbacks:
            func(self.track)

    def addCallback(self, func):
        if func not in self.callbacks:
            self.callbacks.append(func)

    def setTrack(self, new_track):
        self.track = new_track
        self.flattenMeasures()

    def appendSection(self, section):
        bar_num = len(self)
        return self.insertSection(bar_num, section)

    def insertSection(self, bar_num, section):
        #print(self.track, bar_num, section)
        if bar_num in self.track:
            # TODO: make smarter
            print('[Track]', idx, 'occupied, appending section to end')
            bar_num = len(self)
            #self.insertSection(len(self), section)
            #return

        section.addCallback(self.flattenMeasures)

        id_ = self.getNextBlockID()
        block = Block(id_, [section])

        self.track[bar_num] = block
        self.blocks[id_] = bar_num
        self.flattenMeasures()

        print(self.track)
        return bar_num

    def deleteBlock(self, id_):
        print('[Track]', 'deleteBlock', id_)
        start_time = self.blocks[id_]
        del self.track[start_time]
        del self.blocks[id_]
        self.flattenMeasures()
        print(self.flatMeasures)
        print(self.track)

    def getNextBlockID(self):
        x = 0
        for blockID in self.blocks.keys():
            x = max(x, blockID)
        return x+1

    def moveBlockFromTo(self, from_, to_):
        try:
            block = self.track[from_]
        except KeyError:
            print('[Track]', 'block at', from_, 'not found')
            return

        del self.track[from_]

        for section in block:
            self.insertSection(to_, section)

    def moveBlockTo(self, blockID, to_):
        start = self.blocks[blockID][0]
        self.moveSectionFromTo(start, to_)

    def flattenMeasures(self):
        ''' Recalculates all the start times '''
        #print('[Track]', 'flatten measures')

        new_blocks = defaultdict(list)
        new_track = dict()
        x = 0

        #print(self.track.items())
        for st in sorted(self.track.keys()):
            block = self.track[st]
            start_time = max(x, st)
            new_track[start_time] = block
            new_blocks[block.id_] = start_time
            x = start_time + len(block)
            #print('Section', section.name, 'starts at', start_time)

        self.track = new_track
        self.blocks = new_blocks
        self.flatMeasures = [None]*x

        for start_time, block in self.track.items():
            for i, m in enumerate(block.flattenMeasures()):
                self.flatMeasures[start_time+i] = m

        #print(self.flatMeasures)

        self.call()

    def measuresAt(self, n):
        ''' Returns None bars for n < 0 and n > length'''
        if isinstance(n, int):
            if n < 0 or n >= len(self):
                return None
            return self.flatMeasures[n]
        return [self.measuresAt(b) for b in n]

    def getBlocks(self):
        return [(bar_num, self.track[bar_num]) for bar_num in sorted(self.track.keys())]

    def getNumberOfBlocks(self):
        return len(self.track.keys())

    def getSectionTimes(self, id_):
        ''' Returns the bar number of the first occurance of section ID '''

        for st in sorted(self.track.keys()):
            block = self.track[st]
            if block.sections[0].id_ == id_:
                return st
        return None

    def __len__(self):
        return len(self.flatMeasures)

    def __repr__(self):
        s = ['_' for _ in range(len(self))]
        for st, sec in self.track.items():
            for i in range(len(sec)):
                s[st+i] = sec.name[0]

        return ''.join(s)


class Section:
    '''
    Section: collection of parameters, attributes and properties of a musical section.
    '''
    def __init__(self, name, id_, blank=False, **kwargs):
        self.name = name
        self.id_ = id_

        self.callbacks = []

        self.params = deepcopy(DEFAULT_SECTION_PARAMS)
        for k, v in kwargs.items():
            self.params[k] = v

        self.blank = blank

        self.mainMeasures = []
        self.altEnds = [[]]
        self.flatMeasures = [None]*self.params['length']
        self.measures = dict()
        self.measureCount = 0

        self.changeParameter(**self.params)

    def call(self):
        ''' call functions when parameters change'''
        for func in self.callbacks:
            func()

    def addCallback(self, func):
        if func not in self.callbacks:
            self.callbacks.append(func)

    def newMeasure(self, notes=None, events=None):
        id_ = self.measureCount
        if 'chan' in self.params:
            m = Measure(id_, chan=self.params['chan'], notes=notes, events=events)
        else:
            m = Measure(id_, notes=notes, events=events)

        m.addCallback(self.flattenMeasures)
        self.measures[id_] = m
        self.measureCount += 1
        return m

    def changeParameter(self, **kwargs):
        print('[Section]', 'changeParameter', kwargs)
        for key, val in kwargs.items():
            self.params[key] = val
            if key == 'lead' and val == -1:
                self.params['lead'] = None

        # make sure looping lengths are all correct
        if self.params['loop_alt_len'] >= self.params['length']:
            self.params['loop_alt_len'] = self.params['length'] - 1

        # fill in extra measures
        for _ in range(max(0, self.params['length'] - len(self.mainMeasures))):
            self.mainMeasures.append(self.newMeasure())

        self.altEnds[0] = self.mainMeasures[1:]
        # first make sure there are at least the correct number of alternative endings..
        for _ in range(max(0, self.params['loop_alt_num'] - len(self.altEnds))):
            altEnd = [self.newMeasure() for _ in range(self.params['loop_alt_num'])]
            self.altEnds.append(altEnd)

        # then make sure each alternative end is long enough..
        for i in range(1, len(self.altEnds)):
            for _ in range(max(0, self.params['loop_alt_len'] - len(self.altEnds[i]))):
                self.altEnds[i].append(self.newMeasure())

        self.flattenMeasures()

    def measureAt(self, n):
        assert n < len(self.flatMeasures), f'Index {n} for Section {self.name} too large'

        if self.flatMeasures > 0:
            return self.flatMeasures[n]

        return None

    def flattenMeasures(self):
        if self.blank:
            self.flatMeasures = [None]*self.params['length']
            return

        length = self.params['length']
        numAlts = self.params['loop_alt_num']
        lenAlts = self.params['loop_alt_len']

        lenMainMeasures = length - lenAlts

        main = forceListLength(self.mainMeasures, lenMainMeasures)

        track = [None] * (length*self.params['loop_num'])

        for i in range(self.params['loop_num']):
            track[i*length:i*length+lenMainMeasures] = main
            if lenAlts > 0:
                altEnd = self.altEnds[i%numAlts][-lenAlts:]
                track[i*length+lenMainMeasures:i*length+length] = altEnd

        self.flatMeasures = track
        self.call()

    def mainLength(self):
        return self.params['length']

    def __len__(self):
        return self.params['length'] * self.params['loop_num']

    def __repr__(self):
        return f'|{self.name}, {self.params["length"]}'

    def __str__(self):
        return '|' + ''.join(map(str, self.flatMeasures))


class Block:
    '''
    Block: abstract container for sections.
    '''
    def __init__(self, id_, sections=None):
        self.id_ = id_
        if isinstance(sections, list):
            self.sections = sections
        else:
            self.sections = [sections]
        self.flatMeasures = []

    def addSection(self, section):
        self.sections.append(section)
        self.flattenMeasures()

    def flattenMeasures(self):
        self.flatMeasures = []
        for section in self.sections:
            self.flatMeasures.extend(section.flatMeasures)
        return self.flatMeasures

    def __len__(self):
        return sum(map(len, self.sections))

    def __repr__(self):
        return f'[{self.id_}: ' + ''.join(map(str, self.sections)) + ']'

    def __getattr__(self, name):
        if name in self.__dict__:
            return self[name]

        try:
            return getattr(self.sections, name)
        except AttributeError:
            raise AttributeError("'{}' object has no attribute '{}'".format(
                self.__class__.__name__, name
            ))


class Instrument:
    def __init__(self, id_, name, chan, engine):
        self.id_ = id_
        self.name = name
        self.chan = chan
        self.engine = engine

        self.sections = dict()
        self.sectionCount = 0

        self.track = Track(self)

    def measuresAt(self, n):
        if self.__len__() == 0:
            return None

        return self.track.measuresAt(n)

    def newSection(self, blank=False, **params):
        idx = self.sectionCount
        section = Section(chr(65+idx)+str(self.id_), idx, blank=blank, chan=self.id_, **params)
        self.sections[idx] = section
        self.sectionCount += 1
        bar_num = self.track.appendSection(section)
        return bar_num, section

    def duplicateSection(self, id_):
        section = self.sections[id_]
        bar_num = self.track.appendSection(section)
        return bar_num, section

    def compileMidiMessages(self):
        def addEvents(d, n, t, e):
            if n not in events:
                d[n] = dict()

            if t not in events[n]:
                d[n][t] = []

            d[n][t].extend(e)

        events = dict()
        for n, m in enumerate(self.track.flatMeasures):
            if m:
                for t, e in m.MidiEvents.items():
                    if t >= 96:
                        addEvents(events, n+1, t-96, e)
                    else:
                        addEvents(events, n, t, e)

        return events

    def changeSectionParameters(self, id_, **newParams):
        self.sections[id_].changeParameter(**newParams)
        self.track.flattenMeasures()

    def requestGenerateMeasures(self, sectionID=None, gen_all=False):
        ''' Compiles and sends request for section to generate new bars.
        If no section ID is given, then apply to all sections'''
        if sectionID == None:
            for _, block in self.track.getBlocks():
                for section in block.sections:
                    self.requestGenerateMeasures(sectionID=section.id_, gen_all=gen_all)
            return

        section = self.sections[sectionID]
        sectionStart = self.track.getSectionTimes(sectionID)
        if sectionStart == None:
            print('[Instrument]', 'section start for', section, 'not found...')
            return

        leadID = section.params.get('lead', None)

        for i, m in enumerate(section.flatMeasures):
            if not m:
                continue
            if not gen_all and not m.isEmpty():
                continue
            if m.genRequestSent:
                continue

            request = deepcopy(DEFAULT_SECTION_PARAMS)
            for k, v in section.params.items():
                request[k] = v

            if leadID and leadID >= 0:
                leadBar = self.engine.measuresAt(leadID, sectionStart+i)
            else:
                leadBar = self.measuresAt(sectionStart+i-1)

            request['lead_bar'] = leadBar
            prev_bars = self.measuresAt(range(sectionStart+i-4, sectionStart+i))
            request['prev_bars'] = prev_bars

            measureAddress = (self.id_, section.id_, m.id_, )
            requires = [b for b in ([leadBar] + request['prev_bars']) if b]

            m.genRequestSent = True

            self.engine.addPendingRequest({
                'request': request,
                'requires': requires,
                'measure_address': measureAddress})

    def deleteBlock(self, id_):
        self.track.deleteBlock(id_)



    def __len__(self):
        return len(self.track)

    def __repr__(self):
        return self.name + ': ' + repr(self.track)
