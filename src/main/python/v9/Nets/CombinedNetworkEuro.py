# -*- coding: utf-8 -*-

from keras.layers import Input, Lambda, Dense
from keras.models import Model, load_model
from keras.utils import to_categorical, plot_model
import keras.backend as K

import tensorflow as tf

import numpy as np
import numpy.random as rand


from v9.Nets.RhythmEncoder import BarEmbedding, RhythmEncoder
from v9.Nets.RhythmNetwork import RhythmNetwork
from v9.Nets.MelodyEncoder import MelodyEncoder
from v9.Nets.MelodyNetwork import MelodyNetwork
from v9.Nets.MetaPredictor import MetaPredictor

from v9.Data.DataGenerators import CombinedGenerator

import json

#%%

class CombinedNetwork(Model):
    @classmethod
    def from_network_parameters(cls, context_size, melody_bar_len, meta_embed_size,
                                bar_embed_params, rhythm_net_params, melody_net_params,
                                meta_predictor, generation=False, compile_now=True):

        bar_embedder = BarEmbedding(*bar_embed_params, compile_now=False)
        rhythm_net = RhythmNetwork(bar_embedder,
                                        *rhythm_net_params, compile_now=False)
        melody_net = MelodyNetwork(*melody_net_params, compile_now=False)

        combined_net = cls(context_size, melody_bar_len, meta_embed_size,
                           bar_embedder, rhythm_net, melody_net, meta_predictor,
                           generation=generation, compile_now=compile_now)

        return combined_net


    def __init__(self, context_size, melody_bar_len, meta_embed_size,
                               bar_embedder, rhythm_net, melody_net, meta_predictor,
                               generation=False, compile_now=True):
        if generation and compile_now:
            raise ValueError("Cannot be used to generate and train at the same time!")

        if not rhythm_net.use_meta and not melody_net.use_meta:
            raise NotImplementedError("Neither RhythmNet nor MelodyNet are using metaData."+
                                      " This is not implemented!")

        if not rhythm_net.n_voices == melody_net.n_voices == meta_embed_size:
            raise ValueError("n_voices not the same for all networks:" +
                             " ,".join((str(rhythm_net.n_voices), 
                                        str(melody_net.n_voices),
                                        str(meta_embed_size))))

        rhythm_contexts = [Input(shape=(None,),
                                 name="rythm_context_"+str(i))
                            for i in range(context_size)]

        melody_contexts = Input(shape=(None, melody_bar_len),
                                name="melody_contexts")

        meta_embedded = Input(shape=(meta_embed_size,), name="meta_embedded")
        
        lead_rhythm = Input(shape=(None, ), name="lead_rhythm")
        lead_melody = Input(shape=(None, melody_bar_len), name="lead_melody")
        

        rhythm_preds = rhythm_net([*rhythm_contexts, meta_embedded, lead_rhythm])

        if generation:
            rhythms_from_net = Lambda(lambda probs: K.argmax(probs),
                                      output_shape=(None,))(rhythm_preds)
            rhythms_embedded = bar_embedder(rhythms_from_net)
        else:
            rhythms = Input(shape=(None,), name="rhythms")
            rhythms_embedded = bar_embedder(rhythms)


        melody_preds = melody_net([melody_contexts, rhythms_embedded, 
                                   meta_embedded, lead_melody])


        if generation:
            super().__init__(inputs=[*rhythm_contexts, melody_contexts, 
                                     meta_embedded, lead_rhythm, lead_melody],
                             outputs=[rhythm_preds, melody_preds])
        else:
            print(meta_embed_size)
            #meta_embedded_prev = Input(shape=(12, ))
            meta_embedded_prev = Input(shape=(meta_embed_size, ))

            meta_embedded_recon = meta_predictor([rhythm_preds, 
                                                  melody_preds, 
                                                  meta_embedded_prev])

            
            super().__init__(inputs=[*rhythm_contexts, rhythms, melody_contexts, 
                                     meta_embedded, meta_embedded_prev,
                                     lead_rhythm, lead_melody],
                             outputs=[rhythm_preds, melody_preds, meta_embedded_recon])


        self.bar_embedder = bar_embedder
        self.rhythm_net = rhythm_net
        self.melody_encoder = melody_net.encoder
        self.melody_net = melody_net
        self.meta_predictor = meta_predictor

        self.params = {"context_size": context_size,
                       "melody_bar_len": melody_bar_len,
                       "meta_embed_size": meta_embed_size,
                       "bar_embed_params": self.bar_embedder.params,
                       "rhythm_net_params": self.rhythm_net.params,
                       "melody_net_params": self.melody_net.params}

        print('[CombinedNetwork]', 'self.params:', self.params)

        if compile_now:
            self.compile_default()


        print('[CombinedNetwork]', 'init done')


    def compile_default(self):
        self.compile("adam",
                       loss={repr(self.rhythm_net):"categorical_crossentropy",
                             repr(self.melody_net):"categorical_crossentropy",
                             repr(self.meta_predictor):"categorical_crossentropy"},
                       metrics={repr(self.rhythm_net):"categorical_crossentropy",
                             repr(self.melody_net):"categorical_crossentropy",
                             repr(self.meta_predictor):"mean_absolute_error"},
                        loss_weights={repr(self.rhythm_net):0.2,
                             repr(self.melody_net):0.2,
                             repr(self.meta_predictor):0.6})



    @classmethod
    def from_saved_custom(cls, save_dir, meta_predictor, generation=False, compile_now=True):
        with open(save_dir + "/parameters.json", "r") as handle:
            param_dict = json.load(handle)

        #print('[CombinedNet]')
        #print(json.dumps(param_dict, indent=4))

        bar_embedder = BarEmbedding(*param_dict["bar_embed_params"], compile_now=False)

        rhythm_net = RhythmNetwork.init_with_Encoder(bar_embedder,
                                        *param_dict["rhythm_net_params"],
                                        compile_now=False)
        melody_net = MelodyNetwork.init_with_Encoder(*param_dict["melody_net_params"],
                                   compile_now=False)

        bar_embedder.load_weights(save_dir + "/bar_embedding_weights")
        rhythm_net.load_weights(save_dir + "/rhythm_net_weights")
        melody_net.load_weights(save_dir + "/melody_net_weights")


#        print(param_dict["context_size"],
#                           param_dict["melody_bar_len"],
#                           param_dict["meta_len"],
#                           bar_embedder,
#                           rhythm_net,
#                           melody_net,
#                           meta_predictor,
#                           generation,
#                           compile_now)
        
        combined_net = cls(param_dict["context_size"],
                           param_dict["melody_bar_len"],
                           param_dict["meta_embed_size"],
                           bar_embedder,
                           rhythm_net,
                           melody_net,
                           meta_predictor,
                           generation=generation,
                           compile_now=compile_now)

        return combined_net


    def save_model_custom(self, dir_to_save):
        self.bar_embedder.save_weights(dir_to_save + "/bar_embedding_weights")
        self.rhythm_net.save_weights(dir_to_save + "/rhythm_net_weights")
        self.melody_net.save(dir_to_save + "/melody_net_weights")

        with open(dir_to_save + "/parameters.json", "w") as handle:
            json.dump(self.params, handle)

#%%            
#            
#            
#loaded_net = CombinedNetwork.from_saved_custom("Nets/weights/Fri_Mar_15_05-50-18_2019")            
#            
#            
#
##%%
#
#save_dir = "Nets/weights/Fri_Mar_15_05-50-18_2019"
#
#with open(save_dir + "/parameters") as handle:
#    params = json.load(handle)
#    
#    
##params["rhythm_net_params"] = [5, 32, 28, False, True]
#    
#bar_embedder = BarEmbedding(*params["bar_embed_params"], compile_now=False)
#rhythm_net = RhythmNetwork(bar_embedder, 
#                                        *params["rhythm_net_params"], 
#                                        compile_now=False)
#melody_net = MelodyNetwork(*params["melody_net_params"], 
#                                   compile_now=False)
#
#bar_embedder.load_weights(save_dir + "/bar_embedding_weights")
#rhythm_net.load_weights(save_dir + "/rhythm_net_weights")
#melody_net.load_weights(save_dir + "/melody_net_weights")
#        
#        
#combined_net = CombinedNetwork(params["context_size"], 
#                           params["melody_bar_len"], 
#                           params["meta_len"],
#                           bar_embedder, 
#                           rhythm_net, 
#                           melody_net, 
#                           generation=True,
#                           compile_now=False)
#
#
#%%
#
#be2 = BarEmbedding(V=V_rhythm, beat_embed_size=beat_embed_size, embed_lstm_size=embed_lstm_size, out_size=out_size)
#
#rhythm_net2 = RhythmNetwork(bar_embedder=be2, context_size=context_size, 
#                           enc_lstm_size=rhythm_enc_lstm_size, dec_lstm_size=rhythm_dec_lstm_size, meta_len=meta_data_len)
#
#melody_net2 = MelodyNetwork(m=m, V=V_melody, rhythm_embed_size=out_size,
#                           conv_f=conv_f, conv_win_size=conv_win_size, enc_lstm_size=melody_enc_lstm_size,
#                           dec_lstm_1_size=melody_dec_lstm_1_size, dec_lstm_2_size=melody_dec_lstm_2_size, 
#                           meta_len=meta_data_len)
##%%
#    
#cur = "Wed_Mar__6_17-22-49_2019"
#    
#be2.load_weights("Nets/weights/" + cur + "/bar_embedding_weights")
#rhythm_net2.load_weights("Nets/weights/" + cur + "/rhythm_net_weights")
#melody_net2.load_weights("Nets/weights/" + cur + "/melody_net_weights")
#
#
#
##%%
#
#comb_net2 = CombinedNetwork(context_size, m, meta_data_len, be2, rhythm_net2, melody_net2)
#
#
#
#
##%%
#comb_net2.fit_generator(data_iter, 
#                       steps_per_epoch=cg.num_pieces, epochs=5, verbose=2)
#
#
#




#%%
#context_size = 3  
#m = 48          
#            
#rhythm_embed_size = 2
#
#be = BarEmbedding(V=50, beat_embed_size=2, 
#                  embed_lstm_size=2, out_size=rhythm_embed_size)            
#
#
#rn = RhythmNetwork(bar_embedder=be, context_size=context_size, 
#                 enc_lstm_size=2, dec_lstm_size=2, 
#                 enc_use_meta=False, dec_use_meta=True, compile_now=False)
#
#
#mn = MelodyNetwork(m=m, V=24, rhythm_embed_size=rhythm_embed_size,
#                 conv_f=2, conv_win_size=2, 
#                 enc_lstm_size=2, dec_lstm_1_size=2,
#                 enc_use_meta=False, dec_use_meta=True,
#                 compile_now=False)
#            
##%%
#            
#cn = CombinedNetwork(context_size=context_size, melody_bar_len=m, meta_len=9,
#                               bar_embedder=be, rhythm_net=rn, melody_net=mn, 
#                               generation=False, compile_now=True)            
