
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

def forceListLength(l, length, alt=None):
    if len(l) > length:
        return l[:length]
    return l + [alt for _ in range(length - len(l))]

class Measure:
    '''
    Measure: Holds note values and associated times
    '''

    def __init__(self, notes=None, events=None):

        # Note = (nn, start_tick, end_tick)
        if notes:
            self.notes = notes
        else:
            self.notes = []

        # {tick: MIDI Event} where MIDI Event = ('/eventType', (chan, nn, vel))
        if events:
            self.MidiEvents = events
        else:
            self.MidiEvents = defaultdict(list)

        # TEST: fill with random notes
        for i in range(4):
            nn = randint(45, 70)
            note = (nn, i*24, (i+1)*24)
            self.notes.append(note)

        self.convertNotesToMidiEvents()

    def convertNotesToMidiEvents(self):
        events = defaultdict(list)
        for n in self.notes:
            events[n[1]].append(('/noteOn', (1, n[0], 100)))
            events[n[2]].append(('/noteOff', (1, n[0], 100)))
        self.MidiEvents = dict(events)

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

    def measureAt(self, n):
        return self.flatMeasures[n]

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

    def __init__(self, name, id_, params=None):
        self.name = name
        self.id_ = id_

        if params:
            self.params = params
        else:
            self.params = deepcopy(DEFAULT_SECTION_PARAMS)

        self.mainMeasures = None
        self.altEnds = None
        self.flatMeasures = None
        self.generateMeasures()

    def changeParameter(self, **kwargs):
        print('Section: changeParameter()', kwargs)
        for key, val in kwargs.items():
            self.params[key] = val

        # make sure looping lengths are all correct
        if self.params['loop_alt_len'] >= self.params['length']:
            self.params['loop_alt_len'] = self.params['length'] - 1

        # TODO: after changing parameters add None measures to self.mainMeasures etc...

        self.flattenMeasures()

    def measureAt(self, n):
        assert n < len(self.flatMeasures), f'Index {n} for Section {self.name} too large'

        if self.flatMeasures > 0:
            return self.flatMeasures[n]

        return None

    def generateMeasures(self):
        lenMainMeasures = self.params['length'] - self.params['loop_alt_len']
        self.mainMeasures = [Measure() for _ in range(lenMainMeasures)]

        numAlts = self.params['loop_alt_num']
        lenAlts = self.params['loop_alt_len']
        self.altEnds = [[Measure() for _ in range(lenAlts)] for _ in range(numAlts)]

        self.flattenMeasures()

    def flattenMeasures(self):
        print('[Section] flatten measures')
        length = self.params['length']
        numAlts = self.params['loop_alt_num']
        lenAlts = self.params['loop_alt_len']

        lenMainMeasures = length - lenAlts

        main = forceListLength(self.mainMeasures, lenMainMeasures)

        track = [None] * (length*self.params['loop_num'])

        for i in range(self.params['loop_num']):
            track[i*length:i*length+lenMainMeasures] = main

            if i%numAlts < len(self.altEnds):
                altEnd = forceListLength(self.altEnds[i%numAlts], lenAlts)
            else:
                altEnd = [None for _ in range(lenAlts)]

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


class BlankSection():
    '''
    Blank Section: no bars or parameters (except length).
    '''

    def __init__(self, id_, length=None):
        self.name = ''
        self.id_ = id_

        self.params = deepcopy(DEFAULT_SECTION_PARAMS)

        if length:
            self.params['length'] = length

        self.generateMeasures()

        self.flatMeasures = [None] * self.params['length']

    def changeParameter(self, **kwargs):
        if 'length' in kwargs.keys():
            self.params['length'] = kwargs['length']
            self.flattenMeasures()

    def measureAt(self, n):
        return None

    def generateMeasures(self):
        self.flatMeasures = [None] * self.params['length']

    def flattenMeasures(self):
        self.flatMeasures = [None] * self.params['length']

    def mainLength(self):
        return self.params['length']

    def __len__(self):
        return self.params['length']

    def __repr__(self):
        return f'|{self.name}, {self.params["length"]}'

    def __str__(self):
        return '|' + ' '*self.params['length']


class Instrument:

    def __init__(self, id_, name, chan):
        self.id_ = id_
        self.name = name
        self.chan = chan

        # Should be a dictionary with section id
        self.sections = dict()
        self.sectionCount = 0

        self.track = Track()

    def measureAt(self, n):
        if self.__len__() == 0:
            return None

        return self.track.measureAt(n)

    def newSection(self, params=None):
        idx = self.sectionCount
        section = Section(chr(65+idx)+str(self.id_), idx, params)
        self.sections[idx] = section
        self.sectionCount += 1
        self.track.appendSection(section)
        return section

    def newBlankSection(self, params=None):
        idx = self.sectionCount
        length = None
        if params:
            length = params['length']
        section = BlankSection(idx, length=length)
        self.sections[idx] = section
        self.sectionCount += 1
        self.track.appendSection(section)
        return section

    def duplicateSection(self, id_):
        self.track.appendSection(self.sections[id_])

    def changeSectionParameters(self, id_, **newParams):
        self.sections[id_].changeParameter(**newParams)
        self.track.flattenMeasures()

    def __len__(self):
        return len(self.track)

    def __repr__(self):
        return repr(self.track)
