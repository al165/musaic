#!/usr/bin/env python3

import os
import time
import random
from itertools import product

from tqdm.auto import tqdm

from app import Engine
from core import DEFAULT_META_DATA, DEFAULT_SECTION_PARAMS, DEFAULT_AI_PARAMS

'''
 == Batch Generator of Songs ==

 Produces N number of V varieties of songs (N*V total), in three folders:

   SAVE_ROOT + 'combined/', 'lead/', 'bass/'

 where each variety is a combination of the PARAMETER_RANGES. Each one of N
 randomly sets the meta_data values.

'''

N = 5
V = 20

ROOT_PATH = os.path.expanduser('~/Projects/batch_chords')

PARAMETER_RANGES = {
    'length': [2, 4, 8],
    'loop_alt_len': [0, 1],
    'sample_mode': ['dist'],
    'chord_mode': [0, 2, 4],
    'injection_params': [
        (('qb', 'eb'), 'maj'),
        (('qb',), 'maj'),
        (('qb', 'lb'), 'maj'),
        (('fb', 'eb'), 'maj'),
        (('tb', 'fb'), 'maj'),
    ],
}

META_DATA_RANGES = {
    'span': (1, 30),
    'jump': (0, 12),
    'cDens': (0, 1),
    'cDepth': (1, 5),
    'tCent': (40, 80),
    'rDens': (0, 8),
    'pos': (0, 1)
}

if __name__ == '__main__':
    print('STARTING')
    app = Engine()
    app.start()

    ##while not app.networkEngine.isLoaded():
    ##    time.sleep(0.01)

    time.sleep(10)

    print(' == Creating instruments...')
    #bass = app.addInstrument(name='bass')
    lead = app.addInstrument(name='chords')

    print(' == Adding sections...')
    #_, bass_sec = bass.newSection(chord_mode=1,
    #                              octave=2,
    #                              transpose_octave=-1,
    #                              length=2,
    #                              loop_num=8)

    _, lead_sec = lead.newSection()

    print(' == Entering space...')

    print(list(PARAMETER_RANGES.keys()))

    counter = 0
    for l, lal, sm, cm, ip in product(*PARAMETER_RANGES.values()):

        #print(l, 16//l, lal, sm, ip)
        params = {**DEFAULT_SECTION_PARAMS, **DEFAULT_AI_PARAMS}
        params['loop_num'] = 8//l
        params['length'] = l
        params['sample_mode'] = sm
        params['loop_alt_len'] = lal
        #params['lead'] = bass.id_
        params['chord_mode'] = cm
        params['octave'] = 4

        lead_sec.changeParameter(**params)
        #print(params)

        for _ in range(N):
            #bass_md = {**DEFAULT_META_DATA}
            #for k, r in META_DATA_RANGES.items():
            #    bass_md[k] = random.uniform(r[0], r[1])
            #bass_sec.changeParameter(meta_data=bass_md)

            lead_md = {**DEFAULT_META_DATA}
            for k, r in META_DATA_RANGES.items():
                lead_md[k] = random.uniform(r[0], r[1])
            lead_sec.changeParameter(meta_data=lead_md)

            # regenerate...
            #bass.requestGenerateMeasures(gen_all=True)
            lead.requestGenerateMeasures(gen_all=True)
            time.sleep(0.1)

            #while not bass_sec.isGenerated() or not lead_sec.isGenerated():
            while not lead_sec.isGenerated():
                time.sleep(0.1)

            #app.exportMidiFile(os.path.abspath(os.path.join(ROOT_PATH, 'combined/', 'combined_{:04}.mid'.format(counter))), track_list=None)
            #app.exportMidiFile(os.path.abspath(os.path.join(ROOT_PATH, 'bass/', 'bass_{:04}.mid'.format(counter))),
            #                   track_list=[bass.id_])
            app.exportMidiFile(os.path.abspath(os.path.join(ROOT_PATH, 'chord/', 'chord_{:04}.mid'.format(counter))),
                               track_list=[lead.id_])

            print(counter, 'generated!')

            counter += 1

    print('DONE')
