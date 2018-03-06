'''
This module is an sklearn compatible pipeline for machine learning
time series data and sequences using a sliding window segmentation
'''
# Author: David Burns
# License: BSD


import numpy as np
from sklearn.utils.metaestimators import _BaseComposition
from sklearn.utils.validation import check_is_fitted
from sklearn.pipeline import Pipeline

class SegPipe(_BaseComposition):
    '''
    The pipeline supports learning multi-variate time series with or without relational static variables (see introduction).

    The purpose of this pipeline is to assemble the segmentation, feature extraction (optional), feature processing (optional), and final estimator steps into a single pipeline that can be cross validated together setting different parameters.

    The pipeline is applied in three steps.

    The first step is applied by the 'feed' pipeline (or transformer) that performs the sliding window segmentation, and optionally any feature extraction. Feature extraction is not required for estimators that learn the segments directly (eg a recurrent neural network). Feature extraction can be helpful for classifiers such as RandomForest or SVC that learn a feature representation of the segments.

    The second step expands the target vector (y), aligning it with the segments computed during the first step. The segmentation changes the effective number of samples available to the estimator, which is not supported within native sklearn pipelines and is the motivation for this extension.

    The third step applies the 'est' estimator pipeline (or estimator) that performs additional feature processing (optional) and applies the final estimator for classification or regression.

    Parameters
    ----------
    feed : Segment transformer or sklearn pipeline chaining Segment with a feature extractor
    est : sklearn estimator or pipeline for feature processing (optional) and applying the final estimator
    shuffle : bool, optional
        shuffle the segments before fitting the 'est' pipeline (recommended)
    '''
    def __init__(self, feed, est, shuffle = True):
        self.feed = feed
        self.est = est
        self.shuffle = shuffle

    def fit(self, X, y, **est_fit_params):
        ''' X can be array like time series or a dictionary with time and heuristic data '''
        self._reset()
        X = self._check_data(X)

        self.feed.fit(X, y)
        X = self.feed.transform(X)

        if type(self.feed) is Pipeline:
            self.f_labels = self.feed._final_estimator.f_labels
        else:
            self.f_labels = self.feed.f_labels

        X, y = self._ts_expand(X, y)
        self.N_train = len(X)
        if self.shuffle is True:
            # X, y = self._shuffle(X, y)
            pass
        self.est.fit(X, y, **est_fit_params)

    def transform(self, X, y = None):
        check_is_fitted(self, 'N_train')
        X = self._check_data(X)
        X = self.feed.transform(X)
        X, y = self._ts_expand(X, y)
        return self.est.transform(X, y), y


    def predict(self, X, y):
        check_is_fitted(self, 'N_train')

        X = self._check_data(X)
        X = self.feed.transform(X)
        X, y = self._ts_expand(X, y)
        yp = self.est.predict(X)
        self.N_test = len(y)
        return y, yp


    def score(self, X, y, sample_weight = None):
        check_is_fitted(self, 'N_train')

        X = self._check_data(X)
        X = self.feed.transform(X)
        X, y = self._ts_expand(X, y)
        self.N_test = len(y)

        if sample_weight is None:
            return self.est.score(X, y)
        else:
            return self.est.score(X, y, sample_weight)

    def set_params(self, **params):

        # multiple elements in the pipe mapped to the same thing
        keys = list(params.keys())
        for key in params:
            if params[key] in keys:
                params[key] = params[params[key]]

        feed_params = {key[2:]:params[key] for key in params if 'f$' in key}
        est_params = {key[2:]:params[key] for key in params if 'e$' in key}
        self.feed.set_params(**feed_params)
        self.est.set_params(**est_params)
        return self

    # def get_params(self, deep=True):
    #     feed_params = self.feed.get_params()
    #     feed_params = {'f$'+key:feed_params[key] for key in feed_params}
    #
    #     est_params = self.est.get_params()
    #     est_params = {'e$' + key: est_params[key] for key in est_params}
    #
    #     return dict(list(feed_params.items()) + list(est_params.items()))


    def _reset(self):
        if hasattr(self,'N_train'):
            del self.N_train
            del self.f_labels
        if hasattr(self, 'N_test'):
            del self.N_test

    def _check_data(self, X, y = None): #todo: check y
        try:
            dnames = X.dtype.names
            assert 'ts' in dnames
            return X
        except:
            return np.core.records.fromarrays([X], names = ['ts'])

    def _ts_expand(self, X, y = None):
        # if its a record array we need to expand 'ts' and 'h'
        N = len(X)
        Nt = [len(X['ts'][i]) for i in np.arange(N)]

        ye = []
        if y is not None:
            ye = np.concatenate([np.full(Nt[i], y[i]) for i in np.arange(N)])

        Xt = np.concatenate(X['ts'])
        s_names = [h for h in X.dtype.names if h != 'ts']

        if len(s_names) == 0:
            return Xt, ye
        else:
            s_arrays = []
            for h in s_names:
                s_arrays.append(np.concatenate([np.full(Nt[i],X[h][i]) for i in np.arange(N)]))
            X_new = np.core.records.fromarrays(Xt + s_arrays, names=['ts'] + s_names)
            return X_new, ye

    def _shuffle(self, X, y):
        ind = np.arange(len(y), dtype=np.int)
        np.random.shuffle(ind)
        X = X[ind]
        y = y[ind]
        return X, y

