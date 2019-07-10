
#pylint: disable=invalid-name,missing-docstring

from copy import deepcopy
from collections import defaultdict
from random import randint

DEFAULT_SECTION_PARAMS = {
    'lead': None,
    'length': 4,
    'loop_num': 1,
    'loop_alt_len': 0,
    'loop_alt_num': 2,
    'octave': 4,
    'mute': False
}

DEFAULT_GENERATE_PARAMS = {
    'sample_mode': 'dist',
    'lead_mode': 'melody',
    'inject_mode': 'none'
}

def forceListLength(l, length, alt=None):
    if len(l) > length:
        return l[:length]
    return l + [alt for _ in range(length - len(l))]

class Measure:
    '''
    Measure: Holds note values and associated times
    '''
    def __init__(self, id_, notes=None, events=None):

        self.id_ = id_
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
            self.notes = []
            self.events = []
            self.empty = True

    def convertNotesToMidiEvents(self):
        events = defaultdict(list)
        for n in self.notes:
            if n > 0:
                events[n[1]].append(('/noteOn', (1, n[0], 100)))
                events[n[2]].append(('/noteOff', (1, n[0], 100)))
        self.MidiEvents = dict(events)

    def isEmpty(self):
        return self.empty

    def setNotes(self, notes):
        self.notes = notes
        self.convertNotesToMidiEvents()

    def setEvents(self, events):
        self.events = events
        # self.convertMidiEventsToNotes()

class Track:
    '''
    Track: an ordered list of Sections
    '''

    def __init__(self):
        self.track = []
        self.flatMeasures = []

    def appendSection(self, section):
        self.track.append(section)
        self.flattenMeasures()

    def flattenMeasures(self):
        print('[Track]', 'flatten measures')
        self.flatMeasures = []
        for s in self.track:
            self.flatMeasures.extend(s.flatMeasures)

    def measuresAt(self, n):
        if isinstance(n, int):
            return self.flatMeasures[n]
        return [self.flattenMeasures[b] for b in n]

    def getSectionStart(self, id_):
        ''' Returns the bar number of the first occurance of section ID '''
        barNum = 0
        for s in track:
            if s.id_ == id__:
                return barNum
            barNum += len(s)
        return None

    def moveSectionBack(self, idx):
        if idx > 0:
            self.track = self.track[:idx-1] + [self.track[idx]] \
                + [self.track[idx-1]] + self.track[idx+1:]

            self.flattenMeasures()

    def __len__(self):
        if self.track.__len__() == 0:
            return 0

        return sum([len(s) for s in self.track])

    def __repr__(self):
        return ''.join(map(str, self.track)) + '|'


class Section:
    '''
    Section: collection of parameters, attributes and properties of a musical section.
    '''

    def __init__(self, name, id_, params=None, blank=False):
        self.name = name
        self.id_ = id_

        if params:
            self.params = params
        else:
            self.params = deepcopy(DEFAULT_SECTION_PARAMS)

        self.blank = blank

        #self.mainMeasures = [None]*self.params['length']
        self.mainMeasures = []
        #self.altEnds = [[None]*self.params['loop_alt_len']
        #                for _ in range(self.params['loop_alt_num'])]
        self.altEnds = [[]]
        self.flatMeasures = [None]*self.params['length']
        self.measures = dict()
        self.measureCount = 0

        self.changeParameter(**self.params)

    def newMeasure(self, notes=None, events=None):
        id_ = self.measureCount
        m = Measure(id_, notes=notes, events=events)
        self.measures[id_] = m
        self.measureCount += 1
        return m

    def changeParameter(self, **kwargs):
        print('Section: changeParameter()', kwargs)
        for key, val in kwargs.items():
            self.params[key] = val

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

    def generateAllMeasures(self):
        if self.blank:
            return
        lenMainMeasures = self.params['length'] - self.params['loop_alt_len']
        self.mainMeasures = [Measure(section=self) for _ in range(lenMainMeasures)]

        numAlts = self.params['loop_alt_num']
        lenAlts = self.params['loop_alt_len']
        self.altEnds = [[Measure(section=self) for _ in range(lenAlts)] for _ in range(numAlts)]

        self.flattenMeasures()

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

            #if i%numAlts < len(self.altEnds):
            #    altEnd = forceListLength(self.altEnds[i%numAlts], lenAlts)
            #else:
            #    altEnd = [None for _ in range(lenAlts)]
            if lenAlts > 0:
                altEnd = self.altEnds[i%numAlts][-lenAlts:]
                track[i*length+lenMainMeasures:i*length+length] = altEnd

        self.flatMeasures = track

    def mainLength(self):
        return self.params['length']

    def __len__(self):
        return self.params['length'] * self.params['loop_num']

    def __repr__(self):
        return f'|{self.name}, {self.params["length"]}'

    def __str__(self):
        return '|' + ''.join(self.flatMeasures)


class Instrument:

    def __init__(self, id_, name, chan, engine):
        self.id_ = id_
        self.name = name
        self.chan = chan
        self.engine = engine

        # Should be a dictionary with section id
        self.sections = dict()
        self.sectionCount = 0

        self.track = Track()

    def measuresAt(self, n):
        if self.__len__() == 0:
            return None

        return self.track.measuresAt(n)

    def newSection(self, params=None, blank=False):
        idx = self.sectionCount
        section = Section(chr(65+idx)+str(self.id_), idx, params, blank=blank)
        self.sections[idx] = section
        self.sectionCount += 1
        self.track.appendSection(section)
        return section

    def duplicateSection(self, id_):
        self.track.appendSection(self.sections[id_])

    def changeSectionParameters(self, id_, **newParams):
        self.sections[id_].changeParameter(**newParams)
        self.track.flattenMeasures()

    def requestGenerateMeasures(self, section):
        sectionStart = self.track.getSectionStart(section.id_)
        leadID = section.params.get('lead_num', None)
        if leadID:
            leadBars = self.engine.getMeasures(leadID, range(sectionStart, sectionStart+len(section)))
        else:
            leadBars = self.measuresAt(range(sectionStart-1, sectionStart+len(section)-1))





    def __len__(self):
        return len(self.track)

    def __repr__(self):
        return repr(self.track)
