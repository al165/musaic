# -*- coding: utf-8 -*-

#%%
from keras.models import Model, load_model
from keras.layers import Input, Embedding, LSTM,\
                 TimeDistributed, Dense, Bidirectional,\
                 Lambda, RepeatVector, Layer, Conv1D, Reshape
from keras.layers import concatenate as Concat
from keras.metrics import categorical_accuracy, mean_absolute_error
from keras.losses import mean_squared_error, categorical_crossentropy
import keras.backend as K
from keras.utils import to_categorical, plot_model

import numpy as np
import numpy.random as rand

import pickle
from collections import Counter


from v9.Nets.MelodyEncoder import MelodyEncoder

#%%

class MelodyNetwork(Model):
    @classmethod
    def init_with_Encoder(cls, encoder_params, 
                          rhythm_embed_size, dec_lstm_size, V,
                          enc_use_meta=False, dec_use_meta=False,
                          compile_now=False):
        
        melody_enc = MelodyEncoder(*encoder_params, compile_now=False)
        
        return cls(melody_encoder=melody_enc,
                 rhythm_embed_size=rhythm_embed_size, 
                 dec_lstm_size=dec_lstm_size, V=V,
                 enc_use_meta=enc_use_meta, dec_use_meta=dec_use_meta,
                 compile_now=compile_now)
        
    
    def __init__(self, melody_encoder,
                 rhythm_embed_size, dec_lstm_size, V,
                 enc_use_meta=False, dec_use_meta=False,
                 compile_now=False):

        self.n_voices = 9
        self.use_meta = enc_use_meta or dec_use_meta
        m = melody_encoder.m

        prev_melodies = Input(shape=(None, m), name="contexts")
        bar_embedding = Input(shape=(rhythm_embed_size, ), name="bar_rhythm_embedded")
        if self.use_meta:
            meta_cat = Input(shape=(self.n_voices,), name="metaData")

        lead = Input(shape=(None, m), name="lead")
        lead_enc = self.get_lead_encoder(melody_encoder)


        #encode
        processed = melody_encoder(prev_melodies)
        processed_with_rhythms = Concat([processed, bar_embedding])

        # decode
        if dec_use_meta:
            processed_with_rhythms = Concat([processed_with_rhythms, meta_cat])


        lead_processed = lead_enc(lead)
        processed_with_lead = Concat([processed_with_rhythms, lead_processed])

        proc_repeated = RepeatVector(m)(processed_with_lead)

        lstm_outputs = LSTM(dec_lstm_size, return_sequences=True)(proc_repeated)

        preds = TimeDistributed(Dense(V, activation="softmax"))(lstm_outputs)


        self.params = [melody_encoder.params, rhythm_embed_size,
                       dec_lstm_size, V, enc_use_meta, dec_use_meta]

#        self.params = [V, rhythm_embed_size,
#                       dec_lstm_size,
#                       enc_use_meta, dec_use_meta]

        if self.use_meta:
            super().__init__(inputs=[prev_melodies, bar_embedding, 
                                     meta_cat, lead], 
                             outputs=preds, name=repr(self))
        else:
            super().__init__(inputs=[prev_melodies, bar_embedding, lead], 
                             outputs=preds, name=repr(self))

        self.encoder = melody_encoder

        if compile_now:
            self.compile_default()

    def compile_default(self):
        self.compile("adam",
                     loss=categorical_crossentropy,
                     metrics=[categorical_accuracy])

    def __repr__(self):
        return "MelodyNetwork_" + "_".join(map(str, self.params[1:]))
    
    
    def get_lead_encoder(self, encoder):
        m, conv_f, conv_win_size, enc_lstm_size = encoder.params
        lead_enc = MelodyEncoder(m=m, conv_f=conv_f, conv_win_size=1, 
                                 enc_lstm_size=enc_lstm_size)
        return lead_enc

#%%
#        
#menc = MelodyEncoder(m=48, conv_f=4, conv_win_size=3,enc_lstm_size=52)
#
#mnet = MelodyNetwork(V=25, rhythm_embed_size=16, melody_encoder=menc, 
#                     dec_lstm_size=32, dec_use_meta=True, compile_now=True)
#

