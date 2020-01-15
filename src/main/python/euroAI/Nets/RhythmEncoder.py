# -*- coding: utf-8 -*-

from keras.models import Model
from keras.layers import Input, Embedding, LSTM,\
                 TimeDistributed, Dense, Bidirectional,\
                 Lambda, RepeatVector, Layer, Concatenate
from keras.layers import concatenate as Concat
from keras.metrics import categorical_accuracy, mean_absolute_error
from keras.losses import mean_squared_error, categorical_crossentropy
import keras.backend as K
from keras.utils import to_categorical



#%%

class BarEmbedding(Model):
    def __init__(self, V, 
                 beat_embed_size, embed_lstm_size, out_size, compile_now=False):
                
        self.embedding_size = out_size
        self.vocab_size = V
        
        embed_layer = Embedding(input_dim=V, output_dim=beat_embed_size)
        lstm_layer = Bidirectional(LSTM(embed_lstm_size), merge_mode="concat")
        out_layer = Dense(out_size)

        some_bar = Input(shape=(None,))

        embedded = embed_layer(some_bar)
        bar_processed = lstm_layer(embedded)
        self.bar_embedded = out_layer(bar_processed)
        
        super().__init__(inputs=some_bar, outputs=self.bar_embedded)
        
        self.params = [V, beat_embed_size, embed_lstm_size, out_size]
        
        
        
class RhythmEncoder(Model):
    def __init__(self, bar_embedder, context_size, 
                 lstm_size, compile_now=False):

        prev_bars = [Input(shape=(None,), name="context_" + str(i)) 
                            for i in range(context_size)]

        embeddings = [bar_embedder(pb) for pb in prev_bars]
        embed_size = bar_embedder.embedding_size                
        
        embeddings_stacked = Lambda(lambda ls: K.stack(ls, axis=1), 
                           output_shape=(context_size, 
                                         embed_size)
                           )(embeddings)
                        
        # encode        
        embeddings_processed = LSTM(lstm_size)(embeddings_stacked)

        self.params = [context_size, lstm_size]
        self.context_size = context_size
        self.encoding_size = lstm_size     

        super().__init__(inputs=prev_bars, 
                         outputs=embeddings_processed,
                         name=repr(self)) # "RhythmEncoder")  
        
        self.bar_embedder = bar_embedder
        
        if compile_now:
            self.compile_default()
            
    def compile_default(self):
        self.compile(optimizer="adam", 
                     loss=lambda y_true, y_pred: categorical_crossentropy(y_true, y_pred),# + 10000.0, #self.l2(y_true, y_pred), 
                     metrics=[categorical_accuracy])
        
        
    def __repr__(self):
        return "RhythmEncoder_" + "_".join(map(str, self.params))
    
    
#%%
#        
#be = BarEmbedding(375, 12, 12, 8)
#
#renc = RhythmEncoder(be, 4, 28)