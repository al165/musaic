
#pylint: disable=invalid-name,missing-docstring

import time
import random

import pickle as pkl

import numpy as np

from v9.Nets.ChordNetwork import ChordNetwork
from v9.Nets.MetaEmbedding import MetaEmbedding
from v9.Nets.MetaPredictor import MetaPredictor
from v9.Nets.CombinedNetwork import CombinedNetwork


class NeuralNet():

    def __init__(self):

        print('[NeuralNet]', 'Initialising')
        startTime = time.time()

        trainingsDir = './v9/Trainings/first_with_lead/'

        with open(trainingsDir + 'DataGenerator.conversion_params', 'rb') as f:
            conversionParams = pkl.load(f)

        self.rhythmDict = conversionParams['rhythm']
        for k, v in list(self.rhythmDict.items()):
            self.rhythmDict[v] = k

        self.metaEmbedder = MetaEmbedding.from_saved_custom(trainingsDir + '/meta')
        metaPredictor = MetaPredictor.from_saved_custom(trainingsDir + '/meta')

        weightsFolder = trainingsDir + 'weights/_checkpoint_19'

        self.combinedNet = CombinedNetwork.from_saved_custom(weightsFolder, metaPredictor,
                                                             generation=True, compile_now=False)

        #self.contextSize = self.combinedNet.params['context_size']

        #self.vRhythm = self.combinedNet.params['rhythm_net_params'][2]
        #self.vMelody = self.combinedNet.params['melody_net_params'][3]
        self.vocabulary = {
            'rhythm': self.combinedNet.params['rhythm_net_params'][2],
            'melody': self.combinedNet.params['melody_net_params'][3]
        }
        #self.m = self.combinedNet.params['melody_bar_len']

        with open(trainingsDir + 'ChordGenerator.conversion_params', 'rb') as f:
            chordConversionParams = pkl.load(f)

        self.chordDict = chordConversionParams['chords']
        for k, v in list(self.chordDict.items()):
            self.chordDict[v] = k

        self.chordNet = ChordNetwork.from_saved_custom(trainingsDir + '/chord/',
                                                       load_melody_encoder=True)

        print('[NeuralNet]', 'Neural network loaded in', int(time.time() - startTime), 'seconds')

    def generateBar(self, octave=4, **kwargs):
        ''' Expecting...
            - 'lead_bar'
            - 'prev_bars'
            - 'sample_mode'
            - 'chord_mode'
            - 'lead_mode'
            - 'inject_mode'
            - 'injection_params'
            - 'meta_data'
            - 'octave'
        '''

        if kwargs['inject_mode'] == 'none':
            rhythmContexts = np.zeros((4, 1, 4))
            melodyContexts = np.zeros((1, 4, 48))
            for i, b in enumerate(kwargs['prev_bars'][-4:]):
                r, m = self.convertNotesToContext(b)
                rhythmContexts[i, :, :] = r
                melodyContexts[:, i, :] = m
        else:
            rhythmPool = []
            for rhythmType in kwargs['injection_params'][0]:
                rhythmPool.extend({
                    'qb': [self.rhythmDict[(0.0,)]],
                    'lb': [self.rhythmDict[()]],
                    'eb': [self.rhythmDict[(0.0, 0.5)],
                           self.rhythmDict[(0.5,)]],
                    'fb': [self.rhythmDict[(0.0, 0.25, 0.5, 0.75)],
                           self.rhythmDict[(0.0, 0.25, 0.5)]],
                    'tb': [self.rhythmDict[()]],
                }[rhythmType])
            rhythmContexts = [np.random.choice(rhythmPool, size=(1, 4)) for _ in range(4)]

            melodyPool = {
                'maj': [1, 3, 5, 6, 8, 10, 12],
                'min': [1, 3, 4, 6, 8, 10, 11],
                'pen': [1, 4, 6, 8, 11],
                '5th': [1, 8]
            }[kwargs['injection_params'][1]]
            melodyContexts = np.random.choice(melodyPool, size=(1, 4, 48))

        embeddedMetaData = self._embedMetaData(kwargs['meta_data'])

        if kwargs['lead_mode'] == 'none':
            leadRhythm = rhythmContexts[-1]
            leadMelody = melodyContexts[:, -1:, :]
        elif kwargs['lead_mode'] == 'both':
            leadRhythm, leadMelody = self.convertNotesToContext(kwargs['lead_bar'])
        elif kwargs['lead_mode'] == 'melody':
            leadRhythm = rhythmContexts[-1]
            _, leadMelody = self.convertNotesToContext(kwargs['lead_bar'])

        output = self.combinedNet.predict(x=[*rhythmContexts,
                                             melodyContexts,
                                             embeddedMetaData,
                                             leadRhythm,
                                             leadMelody])

        if kwargs['sample_mode'] == 'argmax':
            sampledRhythm = np.argmax(output[0], axis=-1)
            sampledMelody = np.argmax(output[1], axis=-1)
        elif kwargs['sample_mode'] == 'dist':
            sampledRhythm = np.array([[np.random.choice(self.vocabulary['rhythm'], p=dist)
                                       for dist in output[0][0]]])
            sampledMelody = np.array([[np.random.choice(self.vocabulary['melody'], p=dist)
                                       for dist in output[1][0]]])

        return self.convertContextToNotes(sampledRhythm[0], sampledMelody[0], octave=octave)

    def _embedMetaData(self, metaData):
        values = []
        for k in sorted(metaData.keys()):
            if k == 'ts':
                values.extend([4, 4])
            else:
                values.append(metaData[k])

        md = np.tile(values, (1, 1))

        return self.metaEmbedder.predict(md)

    def convertNotesToContext(self, notes):
        '''
        Converts a list of notes (nn, start_tick, end_tick) to context
        format for network to use
        TODO: handle chords
        '''

        if not notes:
            # empty bar...
            rhythm = [self.rhythmDict[()] for _ in range(4)]
            melody = [random.choice([1, 7] for _ in range(48))]
            return np.array([rhythm]), np.array([[melody]])

        rhythm = []
        melody = [-1]*48
        pcs = []

        onTicks = [False] * 96
        for n in notes:
            try:
                onTicks[n[1]] = True
                melody[n[1]//2] = n[0]%12 + 1
                pcs.append(n[0]%12+1)
            except IndexError:
                pass

        for i in range(4):
            beat = onTicks[i*24:(i+1)*24]
            word = []
            for j in range(24):
                if beat[j]:
                    word.append(round(j/24, 4))
            try:
                rhythm.append(self.rhythmDict[tuple(word)])
            except KeyError:
                print('[NeuralNet]', 'Beat not found, using eigth note...')
                rhythm.append(self.rhythmDict[(0.0, 0.5)])

        for j in range(48):
            if melody[j] == -1:
                melody[j] = random.choice(pcs)

        return np.array([rhythm]), np.array([[melody]])


    def convertContextToNotes(self, rhythmContext, melodyContext, octave=4):
        notes = []
        onTicks = [False] * 96
        for i, beat in enumerate(rhythmContext):
            b = self.rhythmDict[beat]
            for onset in b:
                onTicks[int((i+onset)*24)] = True

        startTicks = [i for i in range(96) if onTicks[i]]

        for i, tick in enumerate(startTicks):
            nn = 12*(octave+1) + melodyContext[i//2] - 1
            try:
                note = nn, tick, startTicks[i+1]
            except IndexError:
                note = nn, tick, 96

            notes.append(note)

        return notes
