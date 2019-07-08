from keras.layers import Dense, Input, LSTM, TimeDistributed, Lambda
from keras.models import Model

from keras.metrics import categorical_crossentropy, mean_absolute_error,\
                mean_squared_error
                
from keras.regularizers import Regularizer

import keras.backend as K


import numpy as np
import numpy.random as rand

import json


class EntropyRegulariser(Regularizer):
    def __init__(self, factor=1., V=np.exp(1)):
        self.factor = factor
        self.max = K.log(V)
        
    def __call__(self, x):
        clipped_x = K.clip(x, 10**-7, 1-10**-7)
        return (-K.sum(clipped_x*K.log(clipped_x)) / self.max) * self.factor     
    
         
class MetaEmbedding(Model):
    def __init__(self, meta_len, embed_size, compile_now=False):
        embed_V=K.cast_to_floatx(embed_size)
        
        preprocess = Dense(embed_size, activation="relu")
        categorise = Dense(embed_size, activation="softmax", name="vales_embedding",
                           activity_regularizer=EntropyRegulariser(factor=0.01, 
                                                                   V=embed_V))

        meta = Input(shape=(meta_len, ))        
        preproced = preprocess(meta)
        embedded = categorise(preproced)    
                
        super().__init__(inputs=meta, outputs=embedded, name="MetaEmbedder")
        
        self.meta_len = meta_len
        self.embed_size = embed_size
        
        self.params = {"meta_len": meta_len,
                           "embed_size": embed_size}
        
        if compile_now:
            self.compile_default()
            
            
    def compile_default(self):
        self.compile("adam", 
                     loss=self.entropy,
                     metrics=[self.entropy])
        
    def freeze(self):
        for l in self.layers:
            l.trainable = False
        
        
    def entropy(self, y_true, y_pred):
        return -K.sum(y_pred*K.log(y_pred), axis=-1)
    
    
    def save_model_custom(self, dir_to_save):
        self.save_weights(dir_to_save + "/meta_embedding_weights")
        with open(dir_to_save + "/meta_embedding_parameters.json", "w") as handle:
            json.dump(self.params, handle)
            
    @classmethod  
    def from_saved_custom(cls, save_dir, compile_now=False):
        with open(save_dir + "/meta_embedding_parameters.json", "r") as handle:
            param_dict = json.load(handle)
            
        meta_embedder = cls(param_dict["meta_len"],
                            param_dict["embed_size"],
                            compile_now=compile_now)
        
        meta_embedder.load_weights(save_dir + "/meta_embedding_weights")
        
        meta_embedder.freeze()
        if compile_now:
            meta_embedder.compile_default()
        meta_embedder._make_predict_function()
        
        return meta_embedder
        
    
class MetaTrainer(Model):
    def __init__(self, meta_embedder, compile_now=True):
        meta_len = meta_embedder.meta_len
        meta = Input(shape=(meta_len,))
        embedded = meta_embedder(meta)
        meta_recon = Dense(meta_len,
                           activation="softplus",
                           name="reconstructed")(embedded) # ,activation="softplus")
        
        super().__init__(inputs=meta, outputs=[embedded, meta_recon])
        
        self.meta_embedder = meta_embedder
        
        if compile_now:
            self.compile_default()
        
        
    def compile_default(self):
        self.compile("adam",
                     loss={"reconstructed": mean_squared_error},
                     metrics=[mean_absolute_error])
        
        
        
def get_meta_embedder(meta_samples, embed_size, epochs=1000, 
                      evaluate=True, verbose=1):
    N, meta_len = meta_samples.shape
    meta_samples = rand.permutation(meta_samples)
    
    
    meta_emb = MetaEmbedding(meta_len, embed_size, compile_now=True)
    meta_trainer = MetaTrainer(meta_emb)
    
    if evaluate:
        train_n = int(N*0.8)
        meta_trainer.fit(x=meta_samples[:train_n], 
                         y=meta_samples[:train_n], 
                         epochs=epochs, verbose=verbose)
        eval_results = meta_trainer.evaluate(x=meta_samples[train_n:],
                                             y=meta_samples[train_n:],
                                             verbose=0)
        eval_results = dict(zip(meta_trainer.metrics_names, eval_results))
    
    meta_emb.freeze()
    meta_emb.compile_default()
    meta_emb._make_predict_function()

    
    if evaluate: return meta_emb, eval_results
    else: return meta_emb