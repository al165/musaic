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


#%%


class MelodyEncoder(Model):
    def __init__(self, m, conv_f, conv_win_size, enc_lstm_size,
                 compile_now=False):

        prev_melodies = Input(shape=(None, m), name="contexts")
        
        conved = Conv1D(filters=conv_f, kernel_size=conv_win_size)(prev_melodies)
        processed = LSTM(enc_lstm_size)(conved)
        
        self.params = [m, conv_f, conv_win_size, enc_lstm_size]
        self.m = m
        
        super().__init__(inputs=prev_melodies, outputs=processed, name=repr(self))
        

        
        if compile_now:
            self.compile_default()
            
    def compile_default(self):
        self.compile("adam", loss=mean_squared_error)
        
    
    def __repr__(self):
        return "MelodyEncoder_" + "_".join(map(str, self.params))
        


        
        


