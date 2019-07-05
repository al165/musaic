
#pylint: disable=invalid-name,missing-docstring

from copy import deepcopy

DEFAULT_SECTION_PARAMS = {
    'lead': None,
    'length': 4,
    'loop_num': 1,
    'loop_alt_len': 0,
    'loop_alt_num': 0,
    'octave': 4,
    'mute': False
}


class Track:
    '''
    Track: an ordered list of Sections
    '''

    def __init__(self):
        self.track = []
        self.flatMeasures = []

    def appendSection(self, section):
        self.track.append(section)
        self._flattenMeasures()

    def _flattenMeasures(self):
        self.flatMeasures = []
        for s in self.track:
            self.flatMeasures.extend(s.flatMeasures)

    def measureAt(self, n):
        return self.flatMeasures[n]

    def moveSectionBack(self, idx):
        print(idx, len(self.track))
        if idx > 0:
            self.track = self.track[:idx-1] + [self.track[idx]] \
                + [self.track[idx-1]] + self.track[idx+1:]

            self._flattenMeasures()

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

    def __init__(self, name, _id, params=None):
        self.name = name
        self._id = _id

        if params:
            self.params = params
        else:
            self.params = deepcopy(DEFAULT_SECTION_PARAMS)

        self.mainMeasures = None
        self.altEnds = None
        self.flatMeasures = None
        self.generateMeasures()

    def changeParameter(self, **kwargs):
        regen = False
        for key, val in kwargs.items():
            self.params[key] = val

            if key in {'length', 'loop_num', 'loop_alt_len', 'loop_alt_num'}:
                regen = True

        # make sure looping lengths are all correct
        if self.params['loop_alt_len'] >= self.params['length']:
            self.params['loop_alt_len'] = self.params['length'] - 1

        if regen:
            self.generateMeasures()

    def measureAt(self, n):
        assert n < len(self.flatMeasures), f'Index {n} for Section {self.name} too large'

        if self.flatMeasures > 0:
            return self.flatMeasures[n]

        return None

    def generateMeasures(self):
        self.mainMeasures = self.name[0] * (self.params['length'] - self.params['loop_alt_len'])
        self.altEnds = [None] * self.params['loop_alt_num']
        for i in range(self.params['loop_alt_num']):
            self.altEnds[i] = str(i)*self.params['loop_alt_len']

        self.flattenMeasures()

    def flattenMeasures(self):
        track = []
        for i in range(self.params['loop_num']):
            track.extend(self.mainMeasures)
            if self.params['loop_alt_num'] > 0:
                track.extend(self.altEnds[i%self.params['loop_alt_num']])

        self.flatMeasures = track


    def __len__(self):
        return self.params['length'] * self.params['loop_num']

    def __repr__(self):
        return f'|{self.name}, {self.params["length"]}'

    def __str__(self):
        return '|' + ''.join(self.flatMeasures)


class Instrument:

    def __init__(self, id_, name, chan):
        self.id_ = id_
        self.name = name
        self.chan = chan

        # Should be a dictionary with section id
        self.sections = []

        self.track = Track()

    def measureAt(self, n):
        if self.__len__() == 0:
            return None

        return self.track.measureAt(n)

    def newSection(self, params=None):
        idx = len(self.sections)
        section = Section(chr(65+idx), idx, params)
        self.sections.append(section)
        self.track.appendSection(section)

    def duplicateSection(self, idx):
        self.track.appendSection(self.sections[idx])

    def __len__(self):
        return len(self.track)

    def __repr__(self):
        return repr(self.track)
