#!/usr/bin/env python
# coding: utf-8

# In[1]:


import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pandas.api.types import is_string_dtype, is_bool_dtype, is_numeric_dtype, is_object_dtype, is_categorical_dtype, is_integer_dtype, is_float_dtype
from fastai.tabular.all import *
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.tree import DecisionTreeRegressor
from IPython.display import Image, display_svg, SVG
from dtreeviz.trees import *
from sklearn.tree import export_graphviz
from scipy.cluster import hierarchy as hc
from sklearn.inspection import plot_partial_dependence
import yaml
import os
import math
import random
import pickle
import time
from tqdm import tqdm
from collections import defaultdict
from sklearn import base
from sklearn.model_selection import KFold


# In[3]:


path = Path('data/test/')


# In[5]:


train_df = pd.read_feather(path/'train_raw_full.feat')
valid_df = pd.read_feather(path/'test_raw_full.feat')


# In[12]:


train_df = train_df[train_df['GFlops'] > 0].reset_index(drop=True)
valid_df = valid_df[valid_df['GFlops'] > 0].reset_index(drop=True)


# In[ ]:


final_cols = ['AreaC', 'TotalFlops', 'LdsNumElements', 'SolutionName',
       'NumElementsPerThread', 'NumGlobalWriteVectorsPerThread', 'SizeL',
       'AreaB', 'AspectRatioB', 'SizeJ', 'StoreRemapVectorWidth', 'AreaA',
       'AspectRatioA', 'LdsOffsetB_Blk', 'LDB', 'LdsNumElementsAlignedB',
       'LoopUnroll', 'AspectRatioC', 'PadB', 'AoverB', 'SizeK',
       'LdsOffsetA_Blk', 'MacroTile1', 'LDC', 'LSCA', 'PadA', 'LSCB', 'SizeI',
       'LDA', 'LoopIters', 'ThreadTile_1', 'GlobalReadVectorWidth',
       'LdsOffsetB', 'LdsNumElementsAlignedA', 'NumLoadsB',
       'NumLoadsPerpendicularA']
dep_var = 'Target'
train_df[dep_var] = train_df.Ranking < 0.1
valid_df[dep_var] = valid_df.Ranking < 0.1
y, valid_y = train_df[dep_var].values, valid_df[dep_var].values
xs = train_df[final_cols]
valid_xs = valid_df[final_cols]


# In[9]:


def acc(pred, target):
    return (pred == target).mean()

def m_acc(m, xs, y):
    return acc(m.predict(xs), y)

def eval_model(m, trn_xs, trn_y, val_xs, val_y):
    return m_acc(m, trn_xs, trn_y), m_acc(m, val_xs, val_y)

def rf(xs, y, n_estimators=40, max_features=0.5, min_samples_leaf=25, **kwargs):
    return RandomForestClassifier(n_jobs=-1, n_estimators=n_estimators, max_features=max_features,
                                  min_samples_leaf=min_samples_leaf,
                                  max_samples=200_000, oob_score=True, **kwargs).fit(xs, y)

def rf_feat_importance(m, df):
    return pd.DataFrame({'cols':df.columns, 'imp':m.feature_importances_}
                       ).sort_values('imp', ascending=False)

def plot_fi(fi):
    return fi.plot('cols', 'imp', 'barh', figsize=(12,7), legend=False)

def tolist(x):
    if isinstance(x, str): return [x]
    elif isinstance(x, tuple): return list(x)
    return x

def tostr(x):
    if isinstance(x, [list, tuple]): return '_'.join(x)
    return x

def kfold_target_encoding(train_df, recipies, n_fold=5, drop=True, tail_name='target'):
    tme_cols = []
    train_new = train_df.copy()
    for i, (gby_col, target_col, op) in enumerate(recipies):
        kf = KFold(n_splits=n_fold, shuffle=True)#, random_state=21)
        for tr_ind, val_ind in kf.split(train_df):
            trn_df, val_df = train_df.iloc[tr_ind], train_df.iloc[val_ind]
            agg = trn_df.groupby(gby_col)[target_col].agg(op)
            col_names = ['_'.join([gby_col, c, tail_name]) for c in agg.columns]
            agg.columns = col_names
            target_mean_enc = agg.reset_index().copy()
            for c in col_names:
                train_new.loc[val_ind, c] = val_df[gby_col].map(agg[c])
        train_new.fillna(train_df[target_col].median(), inplace=True)
    return train_new, target_mean_enc

def gen_target_mean_enc(trn_df, recipies):
    return kfold_target_encoding(trn_df, recipies)

# apply target mean encoding by train dataframe
def apply_target_mean_enc(df, tme, drop=True):
    gby_col = tme.columns[0]
    df = df.merge(tme, on=gby_col, how='left')
    for n in tme.columns[1:]:
        df.fillna(df[n].median(), inplace=True)
    return df

def param_bench(model, params, trn_xs, trn_y, val_xs, val_y):
    res = []
    for f in params['max_features']:
        for s in params['min_samples_leaf']:
            m = model(trn_xs, trn_y, max_features=f, min_samples_leaf=s)
            res.append((f'max_features={f}, min_samples_leaf={s}',
                        m_acc(m, trn_xs, trn_y), m_acc(m, val_xs, val_y)))
            del m
    res_sorted = sorted(res, key=lambda x: x[2])
    return res_sorted


# In[ ]:


enc_cols = ['SolutionName']
xs_final['Target'] = y
agg_op = ['mean']
dep_var = 'Target'
recipies = [(c, dep_var, agg_op) for c in enc_cols]
recipies


# In[ ]:


train_new, tme = gen_target_mean_enc(xs_final, recipies)
# xs_final.drop(['Target', 'SolutionName'], axis=1, inplace=True)
train_new.drop(['Target', 'SolutionName'], axis=1, inplace=True)

valid_new = apply_target_mean_enc(valid_xs_final, tme)
valid_new.drop(['SolutionName'], axis=1, inplace=True)


# In[26]:


(path/'xs_final.pkl').save(train_new)
(path/'valid_xs_final.pkl').save(valid_new)
(path/'y.pkl').save(y)
(path/'valid_y.pkl').save(valid_y)
(path/'target_mean_enc.pkl').save(tme)
(path/'columns_final.pkl').save(train_new.columns)


# ## Final

# In[4]:


xs_final = (path/'xs_final.pkl').load()
valid_xs_final = (path/'valid_xs_final.pkl').load()
y = (path/'y.pkl').load()
valid_y = (path/'valid_y.pkl').load()


# In[ ]:


params = {
    'max_features': [0.5, 'sqrt', 'log2'],
    'min_samples_leaf': [15, 25, 35],
}

res = param_bench(rf, params, train_new, y, valid_new, valid_y)
for o in res:
    print(f"{o[0]}: train = {o[1]:.4f}, valid = {o[2]:.4f}")


# In[ ]:


def final_rf(xs, y, n_estimators=160, max_features=0.5, min_samples_leaf=15, **kwargs):
    return RandomForestClassifier(n_jobs=-1, n_estimators=n_estimators, max_features=max_features,
                                  min_samples_leaf=min_samples_leaf, oob_score=True, **kwargs).fit(xs, y)


# In[ ]:


model = final_rf(train_new, y)
eval_model(model, train_new, y, valid_new, valid_y)


# In[ ]:


(path/'rf_model_final.pkl').save(model)


# In[ ]:




