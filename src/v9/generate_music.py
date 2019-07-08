# -*- coding: utf-8 -*-

from Nets.CombinedNetwork import CombinedNetwork
from Nets.MetaEmbedding import MetaEmbedding
from Nets.MetaPredictor import MetaPredictor


import numpy as np
import numpy.random as rand


#if __name__ == "__main__":
    
    #%%
    
    # LOAD META
    meta_embedder = MetaEmbedding.from_saved_custom("meta_saved")
    meta_embed_size = meta_embedder.embed_size
    meta_predictor = MetaPredictor.from_saved_custom("meta_saved")
    meta_predictor.freeze()
    
    weights_folder = "Nets/weights/Wed_Apr__3_19-56-27_2019"
    
    comb_net = CombinedNetwork.from_saved_custom(weights_folder, 
                                                 meta_predictor,
                                                 generation=True,
                                                 compile_now=False)
    
    
    #%%
    
    context_size = comb_net.params["context_size"]
    
    m = comb_net.params["melody_bar_len"]
    
    bar_embed_params = comb_net.params["bar_embed_params"]    
    
    rhythm_enc_params, *rhythm_net_params = comb_net.params["rhythm_net_params"]
    melody_enc_params, *melody_net_params = comb_net.params["melody_net_params"]
    V_rhythm, V_melody = rhythm_net_params[1], melody_net_params[2]
    
    
    #%%
    
    context_size = comb_net.params["context_size"]
    
    V_rhythm = comb_net.params["bar_embed_params"][0]
    
    m, V_melody = comb_net.params["melody_net_params"][0], comb_net.params["melody_net_params"][1]
    
    meta_emb_size = comb_net.params["meta_embed_size"]
    
    print("\n", "-"*40,  "\nINFO FOR LOADED NET:", comb_net)
    print("\n - Used context size: ", context_size)
    
    print("\n - Meta data embedding size: ", meta_embed_size)
    
    
    print("\n - Expected rhythm input size: "+
          "(?, ?) with labels in [0, {}]".format(V_rhythm))
    
    print("\n - Expected melody input size: "+
          "(?, ?, {}) with labels in [0, {}]".format(m, V_melody))
    
    
    print("\n - Expected metaData input size: " + 
          "(?, {})".format(meta_emb_size))
    
    print("\n", "-"*40)
    #%%
    
    batch_size = 5
    bar_length = 4
    
    example_rhythm_contexts = [rand.randint(0, V_rhythm, size=(batch_size, bar_length))
                                    for _ in range(context_size)]
    
    rhythms = rand.randint(0, V_rhythm, size=(batch_size, bar_length))
    
    example_melody_contexts = rand.randint(0, V_melody, size=(batch_size, context_size, 48))
    
    # NOTE: EMBED FIRST
    prev_meta = meta_embedder.predict(rand.random(size=(batch_size, 10)))
    cur_meta = meta_embedder.predict(rand.random(size=(batch_size, 10)))
    
    
    #%%
    
    # asterisk on example_rhythm_contexts is important
    example_output = comb_net.predict(x=[*example_rhythm_contexts,
                                         example_melody_contexts,
                                         cur_meta])
    
    
    sampled_rhythm = np.argmax(example_output[0], axis=-1)
    sampled_melody = np.argmax(example_output[1], axis=-1)
    
    
    
