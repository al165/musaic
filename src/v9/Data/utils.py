# -*- coding: utf-8 -*-

import numpy as np

from collections import Counter



#
def label(data, by_rank=False, start=0):
    '''
    Assigns integer labels to the items in data
    :param data: list of items to label
    :param by_rank: if True assign frequency rank to items,
        otherwise label randomly
    :param start: lowest number to use as label
    :return: tuple of labeled data and the dict of item:label
    '''
    types = set(data)
    if by_rank:
        label_d = {d:r for r, (d, c) in 
                   enumerate(Counter(data).most_common(), 1)}
    else:
        label_d = dict(zip(types, range(start, len(types)+start)))
    return list(map(label_d.__getitem__, data)), label_d

def reverse_dict(d):
    '''
    Reverses a given dict. Values in dict d must be hashable.
    :param d: dict object
    :return: dict of value:key
    '''
    return {y:x for x, y in d.items()}

def pad(ls_of_ls, symb=None, front_too=False):
    '''
    Given a list of lists, appends symb until all lists have the length
    of the longest list.
    :param ls_of_ls: list of lists
    :return: numpy array with shape 
                (number of lists, lenght of longest list)
    '''
    if not symb:
        symb = 0
    max_len = max(map(len, ls_of_ls))
    if front_too:
        pad_f = lambda ls: [symb] + ls+[symb]*(max_len-len(ls))
    else:
        pad_f = lambda ls: ls+[symb]*(max_len-len(ls))
    padded = [pad_f(ls) for ls in ls_of_ls]
    return np.asarray(padded)

def shift_seq(seqs, by=1):
    pass
    