# -*- coding: utf-8 -*-

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
import json
from collections import Counter


from v9.Nets.MelodyEncoder import MelodyEncoder


class ChordNetwork(Model):
    def __init__(self, melody_encoder, dense_size, V, compile_now=False):
        m = melody_encoder.m
        
        self.n_voices = 10
        
        root_note = Input(shape=(1, ), name="root_note")
        melody_context = Input(shape=(None, m), name="bar_melody")
        meta_embedded = Input(shape=(self.n_voices, ), name="meta_embedded")
        
        root_encoded = Dense(dense_size)(root_note)
        context_encoded = melody_encoder(melody_context)
        
        inputs_concat = Concat([root_encoded, context_encoded, meta_embedded])
        
        decoded = Dense(dense_size)(inputs_concat)
        
        preds = Dense(V,
                        activation="softmax")(decoded)
        
        super().__init__(inputs=[root_note, melody_context, meta_embedded],
                         outputs=preds)
        
        self.params = [dense_size, V]
        self.melody_encoder = melody_encoder
        
        
        if compile_now:
            self.compile_default()
            
            
    def compile_default(self):
        self.compile("adam",
                     loss=categorical_crossentropy,
                     metrics=[categorical_accuracy])
        
        
        
    def save_model_custom(self, dir_to_save, save_melody_encoder):
        self.save_weights(dir_to_save + "/chord_net_weights")
        with open(dir_to_save + "/chord_net_parameters.json", "w") as handle:
            json.dump(self.params, handle)
            
        
        self.melody_encoder.save_weights(dir_to_save + "/melody_encoder_weights")
        with open(dir_to_save + "/melody_encoder_parameters.json", "w") as handle:
            json.dump(self.melody_encoder.params, handle)
            
            
    @classmethod  
    def from_saved_custom(cls, save_dir, melody_encoder=None, 
                          load_melody_encoder=False, compile_now=False):     
        
        if melody_encoder and load_melody_encoder:
            raise ValueError("MelodyEncoder *NOT* None and load_melody_encoder=True!")
            
        if not melody_encoder and not load_melody_encoder:
            raise ValueError("MelodyEncoder *IS* None and load_melody_encoder=False!")
        
        
        if load_melody_encoder:
            with open(save_dir + "/melody_encoder_parameters.json", "r") as handle:
                melody_enc_params = json.load(handle)
            
            melody_encoder = MelodyEncoder(*melody_enc_params, compile_now=True)
            melody_encoder.load_weights(save_dir + "/melody_encoder_weights")
            
            
            for l in melody_encoder.layers:
                l.trainable = False
                
            melody_encoder.compile_default()
        
        
        with open(save_dir + "/chord_net_parameters.json", "r") as handle:
            params = json.load(handle)
        
        chord_net = cls(melody_encoder, *params, compile_now=compile_now)
        
        chord_net.load_weights(save_dir + "/chord_net_weights")
        
        return chord_net

        
#%%     
        
    
#loaded_chord_net = ChordNetwork.from_saved_custom("Trainings/chord_test/chord",
#                                                  load_melody_encoder=True,
#                                                  compile_now=True)
