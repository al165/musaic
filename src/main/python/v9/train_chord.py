# -*- coding: utf-8 -*-

from Data.DataGeneratorsLeadMetaChords import ChordGenerator

from Nets.ChordNetwork import ChordNetwork

from Nets.CombinedNetwork import CombinedNetwork
from Nets.MelodyEncoder import MelodyEncoder

from Nets.MetaEmbedding import MetaEmbedding
from Nets.MetaPredictor import MetaPredictor


import numpy as np

import os

def get_smaller_weights(bigger_melody_encoder, conv_win_size):
    encoder_weights =  bigger_melody_encoder.get_weights()
    
    slice_end = conv_win_size
    return [encoder_weights[0][0:slice_end]] + encoder_weights[1:]




if __name__ == "__main__":
    
    top_dir = "Trainings"    
#    save_dir = asctime().split()
#    save_dir = "_".join([*save_dir[0:3], *save_dir[3].split(":")[:2]])
    save_dir = "first_with_lead"
    
    
    if not os.path.isdir("/".join([top_dir, save_dir, "chord"])):
        os.makedirs("/".join([top_dir, save_dir, "chord"]))
    
    

    # META
    meta_embedder = MetaEmbedding.from_saved_custom("/".join([top_dir, save_dir, "meta"]))
    meta_embed_size = meta_embedder.embed_size
    meta_predictor = MetaPredictor.from_saved_custom("/".join([top_dir, save_dir, "meta"]))
    meta_predictor.freeze()


#%%

    music_dir = "../../Data/music21"
    ch_gen = ChordGenerator(music_dir, save_conversion_params="/".join([top_dir, save_dir]),
                        to_list=False, meta_prep_f=None) # None

#    data_iter = ch_gen.generate_forever(batch_size=24)

    x, y = ch_gen.list_data()

#%%
    comb_net = CombinedNetwork.from_saved_custom("/".join([top_dir, save_dir, "weights"]), 
                                                 meta_predictor,
                                                 generation=True,
                                                 compile_now=False)
    melody_enc = comb_net.melody_encoder    
    
    size_1 = 1
    fresh_melody_enc = MelodyEncoder(m=48, conv_f=4, conv_win_size=size_1, enc_lstm_size=52, compile_now=False)
    fresh_melody_enc.set_weights(get_smaller_weights(melody_enc, conv_win_size=size_1))
    
#    for l in fresh_melody_enc.layers:
#        l.trainable = False        
    fresh_melody_enc.compile_default()
    
    
#%%

    chord_net = ChordNetwork(fresh_melody_enc, 28, ch_gen.V, compile_now=True)


#%%

    chord_net.fit(x=x, y=y, epochs=250, verbose=2)

#%%

    # ! Number of chords in bar and number of note values
    # above 12 don't match !

#    chord_net.fit_generator(data_iter, steps_per_epoch=50, epochs=1)
    
    
    
    chord_net.save_model_custom("/".join([top_dir, save_dir, "chord"]),
                                save_melody_encoder=True)
    
