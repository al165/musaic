# -*- coding: utf-8 -*-

#%%
from keras.models import Model, load_model
from keras.layers import Input, Embedding, LSTM,\
                 TimeDistributed, Dense, Bidirectional,\
                 Lambda, RepeatVector, Layer, Concatenate
from keras.layers import concatenate as Concat
from keras.metrics import categorical_accuracy, mean_absolute_error
from keras.losses import mean_squared_error, categorical_crossentropy
import keras.backend as K
from keras.utils import to_categorical

import numpy as np
import numpy.random as rand

import pickle
from collections import Counter


from v9.Nets.RhythmEncoder import BarEmbedding, RhythmEncoder

#%%
        

class RhythmNetwork(Model):
    @classmethod
    def init_with_Encoder(cls, bar_embedder, encoder_params, 
                          dec_lstm_size, V,
                          enc_use_meta=False, dec_use_meta=False,
                          compile_now=False):
        
        rhythm_enc = RhythmEncoder(bar_embedder, *encoder_params,
                                   compile_now=False)
        
        return cls(rhythm_encoder=rhythm_enc,
                 dec_lstm_size=dec_lstm_size, V=V,
                 enc_use_meta=enc_use_meta, dec_use_meta=dec_use_meta,
                 compile_now=compile_now)
    
    def __init__(self, rhythm_encoder, dec_lstm_size, V,  
                 enc_use_meta=False, dec_use_meta=False, compile_now=False):
        self.n_voices = 9

        context_size = rhythm_encoder.context_size
        encoded_size = rhythm_encoder.encoding_size
        bar_embedder = rhythm_encoder.bar_embedder
        bar_embed_size = rhythm_encoder.bar_embedder.embedding_size


        prev_bars = [Input(shape=(None,), name="context_" + str(i)) 
                            for i in range(context_size)]
        
        if enc_use_meta or dec_use_meta:
            meta_cat = Input(shape=(None,), name="metaData")

        lead = Input(shape=(None, ), name="lead")
        lead_embedded = bar_embedder(lead)
                        
        # encode        
        embeddings_processed = rhythm_encoder(prev_bars)
        
        # decode
        if dec_use_meta:
            encoded_size += self.n_voices
            encoded_size += bar_embed_size
            embeddings_processed = Concat([embeddings_processed, meta_cat, lead_embedded])
        
        repeated = Lambda(self._repeat, output_shape=(None, encoded_size))\
                                ([prev_bars[0], embeddings_processed])

        decoded = LSTM(dec_lstm_size, 
                       return_sequences=True, name='dec_lstm')(repeated)

        preds = TimeDistributed(Dense(V, activation='softmax'), 
                               name='softmax_layer')(decoded)
    
    
        self.params = [rhythm_encoder.params, dec_lstm_size, V,
                       enc_use_meta, dec_use_meta]
    
#        self.params = [V, context_size, dec_lstm_size,
#                       enc_use_meta, dec_use_meta]
        
        self.use_meta = enc_use_meta or dec_use_meta
    
    
        if enc_use_meta or dec_use_meta:
            super().__init__(inputs=[*prev_bars, meta_cat, lead], outputs=preds,
                 name=repr(self))  
        else:
            super().__init__(inputs=[prev_bars, lead], outputs=preds,
                 name=repr(self))  
        
        if compile_now:
            self.compile_default()
            
    def compile_default(self):
        self.compile(optimizer="adam", 
                     loss=categorical_crossentropy,# + 10000.0, #self.l2(y_true, y_pred), 
                     metrics=[categorical_accuracy])
            
            
    def _repeat(self, args):
        some_bar, vec = args
        bar_len = K.shape(some_bar)[-1]
        return RepeatVector(bar_len)(vec)

    def __repr__(self):
        return "RhythmNetwork_" + "_".join(map(str, self.params[1:]))

#%%
        
#V = 127
#
#bemb = BarEmbedding(V=V, beat_embed_size=12, 
#                    embed_lstm_size=12, out_size=9)
#
#renc = RhythmEncoder(bemb, context_size=4, lstm_size=14)
#
#rn = RhythmNetwork(V=V, rhythm_encoder=renc, dec_lstm_size=10,
#                   dec_use_meta=True, compile_now=True)
