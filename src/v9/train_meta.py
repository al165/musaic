# -*- coding: utf-8 -*-

#%%
import numpy as np
import numpy.random as rand

from Data.DataGeneratorsLead import CombinedGenerator

from Nets.MetaPredictor import MetaPredictor, dirichlet_noise
from Nets.MetaEmbedding import get_meta_embedder, MetaEmbedding

from time import asctime

#%%

def gen_meta(comb_gen_instance):
    data_generator = comb_gen_instance.generate_data()
    i = 0
    while True:
        try:
            x, y = next(data_generator)
            yield x[3]
        except IndexError:
            i += 1
            print("IndexError at ", i)
            continue
        except StopIteration:
            return
                
def gen_preds_and_meta(comb_gen_instance, meta_embedder,
                       forever=False):
    data_generator = comb_gen_instance.generate_data()
    null = meta_embedder.predict(np.zeros((1, 10)))
    while True:
        try:
            x, y = next(data_generator)
            meta = x[3]
            rs_one_hot, ms_one_hot = y
            
            rand_alph = rand.randint(1, 10) 
            cur_alphs = lambda v: (v*rand_alph)+1
            rs_noisy = np.asarray([[dirichlet_noise(r_cat, cur_alphs) 
                                    for r_cat in bar] for bar in rs_one_hot])
            ms_noisy = np.asarray([[dirichlet_noise(m_cat, cur_alphs) 
                                    for m_cat in bar] for bar in ms_one_hot])

            embedded = meta_embedder.predict(meta)
            padded = np.vstack([null, embedded[:-1]])

            yield [rs_noisy, ms_noisy, padded], embedded
            
        except IndexError:
            continue
        except StopIteration:
            if not forever:
                return
            
            data_generator = comb_gen_instance.generate_data()
#%%

if __name__ == "__main__":

#%%
    
    top_dir = "Trainings"
    
    save_dir = asctime().split()
    save_dir = "_".join([*save_dir[0:3], *save_dir[3].split(":")[:2]])
    #%%
    cg = CombinedGenerator("Data/lessfiles",
                           save_conversion_params=False,
                           to_list=False)
    
    cg.get_num_pieces()
    
#%%
    meta_examples = rand.permutation(np.vstack(list(gen_meta(cg))))
                    
    meta_emb, eval_results = get_meta_embedder(meta_examples, 
                                               embed_size=9, 
                                               epochs=30, 
                                               evaluate=True, verbose=1)
    
    print("MetaEmbedding trained!\n\tevaluation results:\n\t",
          eval_results)
    
#%%
    
    pred_meta_gen = gen_preds_and_meta(cg, meta_emb, forever=True)
    
    r_params = (None, cg.rhythm_V)
    m_params = (48, cg.melody_V)
    
    mp = MetaPredictor(r_params, m_params, meta_emb.embed_size,
                       8, 12)
    
#%%
    
    mp.fit_generator(pred_meta_gen, 
                     steps_per_epoch=cg.num_pieces, 
                     epochs=4)
    

#%%

    meta_emb.save_model_custom("/".join([top_dir, save_dir, "meta"]))

#%%

    mp.save_model_custom("/".join([top_dir, save_dir, "meta"]))


