import numpy as np
import numpy.random as rand

from Data.DataGeneratorsLead import CombinedGenerator as CGLead
from Data.DataGenerators import CombinedGenerator
from Data.DataGeneratorsLeadMeta import CombinedGenerator as CGLeadMeta

from Nets.CombinedNetwork import BarEmbedding, RhythmEncoder, RhythmNetwork,\
                                    MelodyEncoder, MelodyNetwork,\
                                    CombinedNetwork
                                    
from Nets.MetaEmbedding import MetaEmbedding
from Nets.MetaPredictor import MetaPredictor

import os

#%% META

meta_embedder = MetaEmbedding.from_saved_custom("meta_saved")
meta_embed_size = meta_embedder.embed_size
meta_predictor = MetaPredictor.from_saved_custom("meta_saved")
meta_predictor.freeze()


#%%

rc = 2
mc = 2

cg = CGLeadMeta("Data/lessfiles", save_conversion_params=False, to_list=False,
                meta_prep_f=meta_embedder.predict)
cg.get_num_pieces()


def without_lead(cg_inst):
    data_gen = cg.generate_data(rhythm_context_size=rc,
                            melody_context_size=mc,
                            with_metaData=True)
    
    while True:
        for x, y in data_gen:
            yield (x[:-2], y)
        
        data_gen = cg.generate_data(rhythm_context_size=rc,
                            melody_context_size=mc,
                            with_metaData=True)
            
        
def melody_enc_gen(cg_inst):
    data_gen = cg.generate_data(rhythm_context_size=rc,
                            melody_context_size=mc,
                            with_metaData=True)
    
    while True:
        for x, y in data_gen:
            yield (x[-5], y)
        
        data_gen = cg.generate_data(rhythm_context_size=rc,
                            melody_context_size=mc,
                            with_metaData=True)
    
        


#%% RHYTHM
rV = cg.rhythm_V
r_embed_size = 10

bar_embedder = BarEmbedding(V=rV, beat_embed_size=12, 
                            embed_lstm_size=14, out_size=r_embed_size)
rhythm_encoder = RhythmEncoder(bar_embedder=bar_embedder,
                               context_size=rc,
                               lstm_size=18)
rhythm_net = RhythmNetwork(rhythm_encoder=rhythm_encoder,
                           dec_lstm_size=18, V=rV, 
                           dec_use_meta=True, compile_now=True)

#%% MELODY

mV = cg.melody_V
m = 48

# ATTENTION: conv_win_size must not be greater than context size!
melody_encoder = MelodyEncoder(m=m, conv_f=4, conv_win_size=min(mc, 3), enc_lstm_size=16)
melody_net = MelodyNetwork(melody_encoder=melody_encoder, rhythm_embed_size=r_embed_size,
                           dec_lstm_size=16, V=mV,
                           dec_use_meta=True)


#%% COMBINED

combined_net = CombinedNetwork(context_size=rc, melody_bar_len=m,
                               meta_embed_size=meta_embed_size, 
                               bar_embedder=bar_embedder, rhythm_net=rhythm_net, 
                               melody_net=melody_net, meta_predictor=meta_predictor)


#%% TRAIN

data_gen = without_lead(cg)

combined_net.fit_generator(data_gen, steps_per_epoch=cg.num_pieces, epochs=1)



#%% SAVE

#os.makedirs("test")

combined_net.save_model_custom("test")


#%% LOAD

comb_net2 = CombinedNetwork.from_saved_custom("test", meta_predictor)

#%%

comb_net2.fit_generator(data_gen, steps_per_epoch=cg.num_pieces, epochs=1)


