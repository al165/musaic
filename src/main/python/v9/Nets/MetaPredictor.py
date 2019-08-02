# -*- coding: utf-8 -*-
from keras.layers import Dense, Input, LSTM, TimeDistributed, Lambda, Concatenate,\
                Bidirectional, Dropout
from keras.models import Model

from keras.metrics import categorical_crossentropy, mean_absolute_error,\
                mean_squared_error
                
from keras.regularizers import Regularizer

import keras.backend as K
from keras.utils import to_categorical


import numpy as np
import numpy.random as rand

#from meta_embed import MetaEmbedding, get_meta_embedder

import json 

def dirichlet_noise(one_hot, prep_f=lambda v: v*10+1):
    return rand.dirichlet(prep_f(one_hot))


# meta data is rolling average!
#  => MetaPredictor needs to be function of both (rythm, melody) and
#  previous metaData
class MetaPredictor(Model):
    def __init__(self, rhythm_params, melody_params, meta_embed_size,
                 lstm_size, dense_size, compile_now=True):
        
        rhythms_dist = Input(shape=rhythm_params)
        melodies_dist = Input(shape=melody_params)
        
        rhythms_embed = TimeDistributed(Dense(16))(rhythms_dist)
        
        rhythms_processed = Bidirectional(LSTM(lstm_size), 
                                          merge_mode="concat")(rhythms_embed)
        melodies_processed = Bidirectional(LSTM(lstm_size), 
                                           merge_mode="concat")(melodies_dist)
        
        processed_concat = Concatenate()([rhythms_processed, melodies_processed])
        
        pre_meta = Dense(dense_size)(processed_concat)
        
        
        prev_meta = Input(shape=(meta_embed_size, ))
        prev_meta_dropped = Dropout(0.5)(prev_meta)
        
        metas_combined = Concatenate()([prev_meta_dropped, pre_meta])
        
        meta_embedded = Dense(meta_embed_size, 
                              activation="softmax")(metas_combined)
        
        
        super().__init__(inputs=[rhythms_dist, melodies_dist, prev_meta],
                         outputs=meta_embedded,
                         name=repr(self))
        
        self.params = {"rhythm_params": rhythm_params,
                       "melody_params": melody_params,
                       "meta_embed_size": meta_embed_size,
                       "lstm_size": lstm_size,
                       "dense_size": dense_size}

        
        if compile_now:
            self.compile_default()
            
            
    def compile_default(self):
        self.compile("adam",
                     loss=categorical_crossentropy,
                     metrics=[mean_absolute_error])
    
    def __repr__(self):
        return "MetaPredictor"
    
    def freeze(self):
        for l in self.layers:
            l.trainable = False
            
        self.compile_default()
        
    
    def save_model_custom(self, dir_to_save):
        self.save_weights(dir_to_save + "/meta_predictor_weights")
        with open(dir_to_save + "/meta_predictor_parameters.json", "w") as handle:
            json.dump(self.params, handle)
            
    @classmethod  
    def from_saved_custom(cls, save_dir, compile_now=False):            
        with open(save_dir + "/meta_predictor_parameters.json", "r") as handle:
            param_dict = json.load(handle)
            
        meta_pred = cls(param_dict["rhythm_params"],
                            param_dict["melody_params"],
                            param_dict["meta_embed_size"],
                            param_dict["lstm_size"],
                            param_dict["dense_size"],
                            compile_now=compile_now)
        
        meta_pred.load_weights(save_dir + "/meta_predictor_weights")
        
        return meta_pred