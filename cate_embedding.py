#!/usr/bin/env python
#encoding=utf-8

"""
@Author: zhongjianlv

@Create Date: 18-8-19, 21:46

@Description:

@Update Date: 18-8-19, 21:46
"""

import os
import pandas as pd
from sklearn.preprocessing import LabelEncoder
import gc
import numpy as np
from sklearn.decomposition import IncrementalPCA,TruncatedSVD,LatentDirichletAllocation,NMF
import scipy
from sklearn.feature_extraction.text import CountVectorizer


def _decomposition_ipca(df, pca_length, decom_col_name):
    if(len(df.columns) != 2):
        print("df should have 2 columns, the one is id and the other is decomposition column")
        exit(1)
    if(decom_col_name is None):
        cols = df.columns
        for _c in cols:
            if(type(df[_c].iloc[0]) is np.ndarray):
                decom_col_name = _c
                break
    if(decom_col_name is None):
        print("decomposition column cannot be None")
        exit(1)
    if(type(df[decom_col_name].iloc[0]) is not np.ndarray):
        print("decomposition column should be ndarray")
        exit(1)
    columns = list(df.columns)
    columns.remove(decom_col_name)
    ipca = IncrementalPCA(n_components=pca_length)
    alls = np.vstack(df[decom_col_name])
    newalls = ipca.fit_transform(alls)
    newdf = pd.DataFrame({columns[0]: df[columns[0]], "{}_deto_{}".format(decom_col_name, pca_length): list(newalls)})
    return newdf

def decomposition_ipca(dataPath, origin_pickle_name, pca_length, decom_col_name = None):
    """
    对 origin_pickle_name
    :param dataPath:
    :param origin_pickle_name:
    :param pca_length:
    :param decom_col_name:
    :return:
    """
    path = os.path.join(dataPath,origin_pickle_name)
    newPath = path.replace(".pickle","_deto_{}.pickle".format(pca_length))
    if(os.path.exists(newPath)):
        f = pd.read_pickle(newPath)
    else:
        f = pd.read_pickle(path)
        newdf = _decomposition_ipca(f,pca_length,decom_col_name)
        newdf.to_pickle(newPath)
        f = newdf
    return f

def simple_countVectorizer(df, dataPath, cate1, cate2, min_df=2):
    if not os.path.exists(os.path.join(dataPath, 'cache/')):
        os.mkdir(os.path.join(dataPath, 'cache/'))
    sentence_file = os.path.join(dataPath, 'cache/%s_%s_mindf_%d_Simple_CountVectorizer_vector.npz' % (cate1, cate2, min_df))
    cate1s_file = os.path.join(dataPath, 'cache/%s_%s_mindf_%d_Simple_CountVectorizer_cate1s.npz' % (cate1, cate2, min_df))
    if (not os.path.exists(sentence_file)) or (not os.path.exists(cate1s_file)):
        # 保证文件内容的是一致的 不能有错位
        if os.path.exists(sentence_file):
            os.remove(sentence_file)
        if os.path.exists(cate1s_file):
            os.remove(cate1s_file)

        mapping = {}
        for sample in df[[cate1, cate2]].astype(str).values:
            mapping.setdefault(sample[0], []).append(sample[1])
        cate1s = list(mapping.keys())
        cate2_as_sentence = [' '.join(mapping[cate]) for cate in cate1s]
        del mapping; gc.collect()

        cate2_as_matrix = CountVectorizer(token_pattern='(?u)\\b\\w+\\b',
                                          min_df=min_df).fit_transform(cate2_as_sentence)
        scipy.sparse.save_npz(sentence_file, cate2_as_matrix)
        np.savez(cate1s_file, cate1s=cate1s)
        return cate1s, cate2_as_matrix
    else:
        cate2_as_matrix = scipy.sparse.load_npz(sentence_file)
        cate1s = np.load(cate1s_file)['cate1s']
        return list(cate1s), cate2_as_matrix


class CateEmbedding(object):
    def __init__(self, main_id):
        self.MAIN_ID = main_id
        if(type(self.MAIN_ID) is not list):
            self.MAIN_ID = [self.MAIN_ID]

    def _generate_doc(self, df, name, concat_name):
        res = df.astype(str).groupby(name)[concat_name].apply((lambda x: ' '.join(x))).reset_index()
        res.columns = [name, '%s_doc' % concat_name]
        return res

    def _read_emb(self, path):
        """
        read emb after deep walk
        :param path:
        :return:
        """

        count = 0
        f = open(path, 'r')
        emb_dict = dict()
        for line in f:
            if count == 0:
                count += 1
                continue
            line = line.split(' ')
            id = int(line[0])

            weights = line[1:]
            weights = np.array([float(i) for i in weights])
            count += 1
            emb_dict[id] = weights
        return emb_dict

    def cate_embeding_by_all_deep_walk(self, dataPath, df, cate1, cate2, n_component):
        """

        :param dataPath:
        :param df:
        :param cate1:
        :param cate2:
        :param n_component:
        :return: cate1_embedding_df, cate2_embedding_df
        """
        _c = "{}_{}_{}_all_deepwalk".format(cate1,cate2,n_component)
        _c1 = "{}_{}".format(_c,cate1)
        _c2 = "{}_{}".format(_c,cate2)
        cate1_path = os.path.join(dataPath, _c1+".pickle")
        cate2_path = os.path.join(dataPath, _c2+".pickle")
        if(os.path.exists(cate1_path) and os.path.exists(cate2_path)):
            cate1_df = pd.read_pickle(cate1_path)
            cate2_df = pd.read_pickle(cate2_path)
        else:
            df = df[[cate1, cate2]]
            adj_fn = "{}_{}.adjlist".format(cate1,cate2)
            adj_path = os.path.join(dataPath,adj_fn)
            emb_path = os.path.join(dataPath,"{}_{}_{}.emb".format(cate1,cate2,n_component))
            cate1n = cate1 + "new"
            cate2n = cate2 + "new"
            df[cate1n] = cate1 + df[cate1].astype(str)
            df[cate2n] = cate2 + df[cate2].astype(str)
            all_label_encoder = LabelEncoder()
            all_label_encoder.fit(list(df[cate1n]) + list(df[cate2n]))
            df[cate1n] = all_label_encoder.transform(df[cate1n])
            df[cate2n] = all_label_encoder.transform(df[cate2n])
            res1 = self._generate_doc(df,cate1n,cate2n)
            res1 = res1.iloc[:,0] + " " + res1.iloc[:,1]
            res2 = self._generate_doc(df,cate2n,cate1n)
            res2 = res2.iloc[:,0] + " " + res2.iloc[:,1]
            adj = pd.concat([res1,res2])
            adj.to_csv(adj_path,index=None)
            cm = "deepwalk --input {}  --output {} --representation-size {} --workers 8 --number-walks 30".format(adj_path,emb_path,n_component)
            os.system(cm)
            emb = self._read_emb(emb_path)
            del res1, res2,adj
            gc.collect()
            indexs = list(emb.keys())
            values = list(emb.values())
            emb_df = pd.DataFrame({"index": indexs,_c : values})
            del emb; gc.collect()
            cate1_df = df[[cate1,cate1n]].drop_duplicates()
            cate2_df = df[[cate2,cate2n]].drop_duplicates()
            cate1_df = cate1_df.merge(emb_df,how="left",left_on = cate1n,right_on = "index")[[cate1,_c]]
            cate2_df = cate2_df.merge(emb_df,how="left",left_on = cate2n,right_on = "index")[[cate2,_c]]
            cate1_df.columns=[cate1,_c1]
            cate2_df.columns=[cate2,_c2]
            #save
            cate1_df.to_pickle(cate1_path)
            cate2_df.to_pickle(cate2_path)
        return cate1_df, cate2_df

    def cate_embedding_by_all_deepwalk_cate1_2(self, dataPath, df,cate1,cate2,n_components,decomposition_to1 = -1,decomposition_to2 = -1):
        """

        :param dataPath:
        :param df:
        :param cate1:
        :param cate2:
        :param n_components:
        :param decomposition_to1:
        :param decomposition_to2:
        :return: df[MAIN_ID,cate1_embedding_column_i,cate2_embedding_column_i] (i： 0 - n_components-1)
        """
        if(decomposition_to1 <=0 or decomposition_to2 <= 0):
            cate1_df, cate2_df = self.cate_embeding_by_all_deep_walk(df, cate1, cate2, n_components,dataPath)

        if(decomposition_to1 > 0):
            _c = "{}_{}_{}_all_deepwalk".format(cate1,cate2,n_components)
            _c1 = "{}_{}".format(_c,cate1)
            cate1_path = os.path.join(dataPath,_c1+".pickle")
            if(not os.path.exists(cate1_path)):
                self.cate_embeding_by_all_deep_walk(df, cate1, cate2, n_components,dataPath)
            cate1_df = decomposition_ipca(dataPath,_c1+".pickle",decomposition_to1)

        if(decomposition_to2 > 0):
            _c = "{}_{}_{}_all_deepwalk".format(cate1,cate2,n_components)
            _c2 = "{}_{}".format(_c,cate2)
            cate2_path = os.path.join(dataPath,_c2+".pickle")
            if(not os.path.exists(cate2_path)):
                self.cate_embeding_by_all_deep_walk(df, cate1, cate2, n_components,dataPath)
            cate2_df = decomposition_ipca(dataPath,_c2+".pickle",decomposition_to2)

        c_set = set()
        for _c in self.MAIN_ID:
            c_set.add(_c)
        c_set.add(cate1)
        c_set.add(cate2)
        c_set = list(c_set)
        interaction = df[c_set]
        cs = list(cate1_df.columns)
        cs.remove(cate1)
        col = cs[0]
        values = np.stack(cate1_df[col])
        u_cols = []
        for _i in range(values.shape[1]):
            _c = "{}_{}".format(col, _i)
            u_cols.append(_c)
            cate1_df[_c] = values[:, _i]
        cate1_df = cate1_df[[cate1] + u_cols]
        cs = list(cate2_df.columns)
        cs.remove(cate2)
        col = cs[0]
        values = np.stack(cate2_df[col])
        p_cols = []
        for _i in range(values.shape[1]):
            _c = "{}_{}".format(col, _i)
            p_cols.append(_c)
            cate2_df[_c] = values[:, _i]
        cate2_df = cate2_df[[cate2] + p_cols]
        interaction = pd.merge(interaction, cate1_df, on=cate1, how="outer")
        interaction = pd.merge(interaction, cate2_df, on=cate2, how="outer")
        return interaction[self.MAIN_ID + u_cols + p_cols]

    def cate_embedding_by_all_deepwalk_cate1(self, df,dataPath,cate1,cate2,n_components, decomposition_to = -1):# just use cate1 embedding
        """

        :param df:
        :param dataPath:
        :param cate1:
        :param cate2:
        :param n_components:
        :param decomposition_to:
        :return: df[MAIN_ID, cate1_embedding_column_i] (i： 0 - n_components-1)
        """
        if(decomposition_to > 0):
            _c = "{}_{}_{}_all_deepwalk".format(cate1,cate2,n_components)
            _c1 = "{}_{}".format(_c,cate1)
            cate1_path = os.path.join(dataPath,_c1+".pickle")
            if(not os.path.exists(cate1_path)):
                self.cate_embeding_by_all_deep_walk(df, cate1, cate2, n_components,dataPath)
            cate1_df = decomposition_ipca(dataPath,_c1+".pickle",decomposition_to)
        else:
            cate1_df,cate2_df = self.cate_embeding_by_all_deep_walk(df, cate1, cate2, n_components,dataPath)
        c_set = set()
        for _c in self.MAIN_ID:
            c_set.add(_c)
        c_set.add(cate1)
        c_set = list(c_set)
        interaction = df[c_set]
        cs = list(cate1_df.columns)
        cs.remove(cate1)
        col = cs[0]
        values = np.stack(cate1_df[col])
        u_cols = []
        for _i in range(values.shape[1]):
            _c = "{}_{}".format(col, _i)
            u_cols.append(_c)
            cate1_df[_c] = values[:, _i]
        cate1_df = cate1_df[[cate1] + u_cols]
        interaction = pd.merge(interaction, cate1_df, on=cate1, how="outer")
        return interaction[self.MAIN_ID + u_cols]

    def cate_embedding_by_all_deepwalk_cate2(self, df, dataPath,cate1,cate2,n_components, decomposition_to = -1):# just use cate2 embedding
        """

        :param df:
        :param dataPath:
        :param cate1:
        :param cate2:
        :param n_components:
        :param decomposition_to:
        :return: df[MAIN_ID,cate2_embedding_column_i] (i： 0 - n_components-1)
        """
        if(decomposition_to > 0):
            _c = "{}_{}_{}_all_deepwalk".format(cate1,cate2,n_components)
            _c2 = "{}_{}".format(_c,cate2)
            cate2_path = os.path.join(dataPath,_c2+".pickle")
            if(not os.path.exists(cate2_path)):
                self.cate_embeding_by_all_deep_walk(df, cate1, cate2, n_components,dataPath)
            cate2_df = decomposition_ipca(dataPath,_c2+".pickle",decomposition_to)
        else:
            cate1_df,cate2_df = self.cate_embeding_by_all_deep_walk(df, cate1, cate2, n_components,dataPath)
        c_set = set()
        for _c in self.MAIN_ID:
            c_set.add(_c)
        c_set.add(cate2)
        c_set = list(c_set)
        interaction = df[c_set]
        cs = list(cate2_df.columns)
        cs.remove(cate2)
        col = cs[0]
        values = np.stack(cate2_df[col])
        p_cols = []
        for _i in range(values.shape[1]):
            _c = "{}_{}".format(col, _i)
            p_cols.append(_c)
            cate2_df[_c] = values[:, _i]
        cate2_df = cate2_df[[cate2] + p_cols]
        interaction = pd.merge(interaction, cate2_df, on=cate2, how="outer")
        return interaction[self.MAIN_ID + p_cols]

    def _embedding(self, dataPath, df, cate1, cate2, method, method_name, n_components=16, min_df=2):
        embedding_query_file = os.path.join(dataPath,
                                            'cache/%s_%s_nc_%d_mindf_%d_%s_embedding.feather' %(cate1, cate2, n_components, min_df, method_name))

        if not os.path.exists(embedding_query_file):
            if not os.path.exists(os.path.join(dataPath, 'cache/')):
                os.mkdir(os.path.join(dataPath, 'cache/'))

            cate1s, cate2_as_matrix = simple_countVectorizer(df, dataPath, cate1, cate2, min_df=min_df)
            topics_of_cate1 = method.fit_transform(cate2_as_matrix)
            del cate2_as_matrix; gc.collect()

            topics_of_cate1 = pd.DataFrame(topics_of_cate1,
                                           columns=["%s_%s_%s_%s" %(cate1, cate2, i, method_name) for i in range(n_components)]).astype('float32')

            topics_of_cate1[cate1] = np.int32(cate1s)
            del cate1s; gc.collect()
            print(topics_of_cate1.head(3))
            del df; gc.collect()
            topics_of_cate1.to_feather(embedding_query_file)
            return topics_of_cate1
        else:
            topics_of_cate1 = pd.read_feather(embedding_query_file)
            return topics_of_cate1

    def lda_embedding(self, dataPath, df, cate1, cate2, n_components=16, min_df=2, batch_size=520, n_jobs=20):
        '''
        此部分是做cate1 cate2的相关embedding,这里只要共同show过的都算相关
        '''
        lda = LatentDirichletAllocation(n_components = n_components,
                                        learning_method = 'online',
                                        batch_size = batch_size,
                                        random_state = 2018,
                                        n_jobs=n_jobs
                                        )

        return self._embedding(dataPath,df,cate1,cate2,lda,"lda",n_components=n_components,min_df=min_df)

    def nmf_embedding(self, dataPath, df, cate1, cate2, n_components=16, min_df=2,
                      max_iter=1000, alpha=.1, l1_ratio=.5):
        nmf = NMF( n_components=n_components,
                   random_state=2018,
                   beta_loss='kullback-leibler',
                   solver='mu',
                   max_iter=max_iter,
                   alpha=alpha,
                   l1_ratio=l1_ratio)

        return self._embedding(dataPath,df,cate1,cate2,nmf,"nmf",n_components=n_components,min_df=min_df)

    def svd_embedding(self, dataPath, df, cate1, cate2, n_components=16, min_df=2,tol=0.,n_iter=5):
        svd = TruncatedSVD(n_components,random_state=2018,tol=tol,n_iter=n_iter)
        return self._embedding(dataPath,df,cate1,cate2,svd,"svd",n_components=n_components,min_df=min_df)

