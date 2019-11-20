"""
SVM and kernel kernel logistic regression models.
"""
import os
import shutil

import numpy as np
from scipy import sparse as sps
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.multiclass import OneVsRestClassifier
from sklearn.metrics.pairwise import linear_kernel, rbf_kernel
from sklearn.metrics.pairwise import polynomial_kernel, sigmoid_kernel
from sklearn.svm import SVC

from . import liblinear_util


class SVM(BaseEstimator, ClassifierMixin):
    """
    Multiclass wrapper around sklearn's SVC. This is to unify the API for the SVM and Kernel LR models.
    If multiclass, uses a one-vs-rest strategy and fits a BinaryKernelLogisticRegression classifier for each class.
    """

    def __init__(self, C=1.0, kernel='linear', gamma='scale', coef0=0.0, degree=3, pred_size=500,
                 random_state=None):
        """
        Parameters
        ----------
        C: float (default=1.0)
            Regularization parameter.
        kernel: str (default='linear')
            Type of kernel to use. Also 'rbf', 'poly', and 'sigmoid'.
        gamma: float (default=None)
            Kernel coefficient for 'rbf', 'poly', and 'sigmoid'.
            If None, defaults to 1 / n_features.
        coef0: float (default=0.0)
            Independent term in 'poly' and 'sigmoid'.
        degree: int (default=3)
            Degree of the 'poly' kernel.
        pred_size: int (default=1000)
            Max number of instancs to predict at one time. A higher number can
            be faster, but requires more memory to create the similarity matrix.
        random_state: int (default=None)
            Number for reproducibility.
        """
        self.C = C
        self.kernel = kernel
        self.gamma = gamma
        self.coef0 = coef0
        self.degree = degree
        self.pred_size = pred_size
        self.random_state = random_state

    def fit(self, X, y):
        self.X_train_ = X
        self.n_features_ = X.shape[1]
        self._create_kernel_callable()
        estimator = BinarySVM(C=self.C, kernel=self.kernel, gamma=self.gamma_, coef0=self.coef0,
                              degree=self.degree, kernel_func=self.kernel_func_, pred_size=self.pred_size,
                              random_state=self.random_state)
        self.ovr_ = OneVsRestClassifier(estimator).fit(X, y)
        return self

    def decision_function(self, X):
        return self.ovr_.decision_function(X)

    def predict(self, X):
        return self.ovr_.predict(X)

    def similarity(self, X, train_indices=None):
        X_train = self.X_train_[train_indices] if train_indices is not None else self.X_train_
        return self.kernel_func_(X, X_train)

    def get_weight(self):
        """
        Return a sparse matrix of train instance weights.
            If binary, the array has shape (1, n_train_samples).
            If multiclass, the array has shape (n_classes, n_train_samples).
        """
        return sps.vstack([estimator.get_weight() for estimator in self.ovr_.estimators_])

    def explain(self, X, y=None):
        """
        Return a sparse matrix of train instance contributions to X. A positive score
        means the training instance contributed towards the predicted label.

        Parameters
        ----------
        X : 2d array-like
            Instances to explain.
        y : 1d array-like
            If not None, a positive score means the training instance contributed
            to the label in y. Must be the same length as X.

        Returns a sparse matrix of shape (len(X), n_train_samples).
        """
        if y is None:
            y = self.predict(X)
        assert len(y) == len(X)

        # handle multiclass and binary slightly differently
        if len(self.ovr_.estimators_) > 1:
            result = sps.vstack([self.ovr_.estimators_[y[i]].explain(X[[i]]) for i in range(len(X))])
        else:
            result = sps.vstack([self.ovr_.estimators_[0].explain(X[[i]]) for i in range(len(X))])
            result[np.where(y == 0)] *= -1

        return result

    def _create_kernel_callable(self):
        assert self.kernel in ['rbf', 'poly', 'sigmoid', 'linear']

        if self.kernel == 'rbf':
            self._compute_gamma()
            self.kernel_func_ = lambda X1, X2: rbf_kernel(X1, X2, gamma=self.gamma_)
        elif self.kernel == 'poly':
            self._compute_gamma()
            self.kernel_func_ = lambda X1, X2: polynomial_kernel(X1, X2, degree=self.degree, gamma=self.gamma_,
                                                                 coef0=self.coef0)
        elif self.kernel == 'sigmoid':
            self._compute_gamma()
            self.kernel_func_ = lambda X1, X2: sigmoid_kernel(X1, X2, coef0=self.coef0, gamma=self.gamma_)
        elif self.kernel == 'linear':
            self.gamma_ = self.gamma
            self.kernel_func_ = lambda X1, X2: linear_kernel(X1, X2)

    def _compute_gamma(self):
        if self.gamma == 'scale':
            self.gamma_ = 1.0 / (self.n_features_ * self.X_train_.var())
        elif self.gamma is None:
            self.gamma_ = 1.0 / self.n_features_
        else:
            self.gamma_ = self.gamma


class BinarySVM(BaseEstimator, ClassifierMixin):
    """
    Wrapper around sklearn's SVC. This is to unify the API for the SVM and Kernel LR models.
    """

    def __init__(self, C=1.0, kernel='linear', gamma='scale', coef0=0.0, degree=3,
                 kernel_func=None, pred_size=1000, random_state=None):
        """
        Parameters
        ----------
        C: float (default=1.0)
            Regularization parameter.
        kernel: str (default='linear')
            Type of kernel to use. Also 'rbf', 'poly', and 'sigmoid'.
        gamma: float (default=None)
            Kernel coefficient for 'rbf', 'poly', and 'sigmoid'.
            If None, defaults to 1 / n_features.
        coef0: float (default=0.0)
            Independent term in 'poly' and 'sigmoid'.
        degree: int (default=3)
            Degree of the 'poly' kernel.
        kernel_func: callable (default=None)
            Callable similarity kernel.
        pred_size: int (default=1000)
            Max number of instancs to predict at one time. A higher number can
            be faster, but requires more memory to create the similarity matrix.
        random_state: int (default=None)
            Number for reproducibility.
        """
        self.C = C
        self.kernel = kernel
        self.gamma = gamma
        self.coef0 = coef0
        self.degree = degree
        self.kernel_func = kernel_func
        self.pred_size = pred_size
        self.random_state = random_state
        assert callable(self.kernel_func)

    def fit(self, X, y, n_check=10):

        # store training instances for later use
        self.X_train_ = X
        self.n_features_ = X.shape[1]

        # train the SVM
        estimator = SVC(C=self.C, kernel=self.kernel, random_state=self.random_state, gamma=self.gamma,
                        coef0=self.coef0, degree=self.degree)
        self.model_ = estimator.fit(X, y)
        self.coef_ = self.model_.dual_coef_[0]
        self.coef_indices_ = self.model_.support_
        self.intercept_ = self.model_.intercept_[0]

        # # sanity check to make sure our decomposition is making the predictions as the svm
        assert np.allclose(self.model_.predict(X[:n_check]), self.predict(X[:n_check]))
        assert np.allclose(self.model_.decision_function(X[:n_check]), self.decision_function(X[:n_check]))

        return self

    def decision_function(self, X):
        """
        Returns a 1d array of decision values of size=len(X).
        """
        assert X.ndim == 2

        decisions = []
        for i in range(0, len(X), self.pred_size):
            X_sim = self.kernel_func(X[i: i + self.pred_size], self.X_train_[self.coef_indices_])
            decisions.append(np.sum(X_sim * self.coef_, axis=1) + self.intercept_)
        decision = np.concatenate(decisions)
        return decision

    def predict(self, X):
        """
        Returns a 1d array of predicted labels of size=len(X).
        """
        pred_label = np.where(self.decision_function(X) >= 0, 1, 0)
        return pred_label

    def get_weight(self):
        """
        Return a sparse array of train instance weights with shape (1, n_train_samples).
        """
        data = self.coef_
        indices = self.coef_indices_
        indptr = np.array([0, len(data)])
        return sps.csr_matrix((data, indices, indptr), shape=(1, len(self.X_train_)))

    def explain(self, x):
        """
        Return a sparse matrix of the impact of the training instances on x.
        The resulting array is of shape (1, n_train_samples).
        """
        assert x.shape == (1, self.X_train_.shape[1])
        x_sim = self.kernel_func(x, self.X_train_[self.coef_indices_])
        impact = (x_sim * self.coef_)[0]
        indptr = np.array([0, len(impact)])
        return sps.csr_matrix((impact, self.coef_indices_, indptr), shape=(1, len(self.X_train_)))


class KernelLogisticRegression(BaseEstimator, ClassifierMixin):
    """
    Wrapper around liblinear. Solves the l2 logistic regression dual problem using a linear kernel.
    Reference: https://www.csie.ntu.edu.tw/~cjlin/papers/liblinear.pdf
    If multiclass, uses a one-vs-rest strategy and fits a BinaryKernelLogisticRegression classifier for each class.
    """

    def __init__(self, C=1.0, pred_size=1000):
        """
        Parameters
        ----------
        C: float (default=1.0)
            Regularization parameter, where 0 <= alpha_i <= C.
        pred_size: int (default=1000)
            Max number of instancs to predict at one time. A higher number can
            be faster, but requires more memory to create the similarity matrix.
        """
        self.C = C
        self.pred_size = pred_size

    def fit(self, X, y):
        self.X_train_ = X
        self.n_features_ = X.shape[1]
        self.n_classes_ = len(np.unique(y))
        estimator = BinaryKernelLogisticRegression(C=self.C, pred_size=self.pred_size)
        self.ovr_ = OneVsRestClassifier(estimator).fit(X, y)
        self.coef_ = np.vstack([estimator.coef_ for estimator in self.ovr_.estimators_])
        return self

    def predict_proba(self, X):
        return self.ovr_.predict_proba(X)

    def predict(self, X):
        return self.ovr_.predict(X)

    def similarity(self, X, train_indices=None):
        X_train = self.X_train_[train_indices] if train_indices is not None else self.X_train_
        return linear_kernel(X, X_train)

    def get_weight(self):
        return np.vstack([estimator.get_weight() for estimator in self.ovr_.estimators_])

    def explain(self, X, y=None):
        """
        Return an array of train instance contributions to X. A positive score
        means the training instance contributed towards the predicted label.

        Parameters
        ----------
        X : 2d array-like
            Instances to explain.
        y : 1d array-like
            If not None, a positive score means the training instance contributed
            to the label in y. Must be the same length as X.

        Returns a sparse matrix of shape (len(X), n_train_samples).
        """
        if y is None:
            y = self.predict(X)
        assert len(y) == len(X)

        # handle multiclass and binary slightly differently
        if len(self.ovr_.estimators_) > 1:
            result = np.vstack([self.ovr_.estimators_[y[i]].explain(X[[i]]) for i in range(len(X))])
        else:
            result = np.vstack([self.ovr_.estimators_[0].explain(X[[i]]) for i in range(len(X))])
            result[np.where(y == 0)] *= -1

        return result


class BinaryKernelLogisticRegression(BaseEstimator, ClassifierMixin):
    """
    Wrapper around liblinear. Solves the l2 logistic regression dual problem using a linear kernel.
    Reference: https://www.csie.ntu.edu.tw/~cjlin/papers/liblinear.pdf
    """

    def __init__(self, C=1.0, pred_size=1000, temp_dir='.temp_klr'):
        """
        Parameters
        ----------
        C: float (default=1.0)
            Regularization parameter, where 0 <= alpha_i <= C.
        pred_size: int (default=1000)
            Max number of instancs to predict at one time. A higher number can
            be faster, but requires more memory to create the similarity matrix.
        temp_dir: str (default='.temp_klr')
            Temporary directory for storing liblinear models and prediction files.
        """
        self.C = C
        self.pred_size = pred_size
        self.temp_dir = temp_dir

    def fit(self, X, y, n_check=10, atol=1e-5):

        # store training instances for later use
        self.X_train_ = X
        self.classes_ = np.unique(y)
        assert len(self.classes_) == 2

        # remove any previously stored models
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
        os.makedirs(self.temp_dir)

        # setup path names
        train_data_path = os.path.join(self.temp_dir, 'train_data')
        model_path = os.path.join(self.temp_dir, 'model')
        prediction_path = os.path.join(self.temp_dir, 'prediction')

        # train the model using liblinear
        y_liblinear = np.where(y == 0, -1, 1)  # liblinear works better with -1 instead of 0
        liblinear_util.create_data_file(X, y_liblinear, train_data_path)
        liblinear_util.train_model(train_data_path, model_path, C=self.C)
        self.coef_ = liblinear_util.parse_model_file(model_path)

        # make sure our decomposition is making the same predictions as liblinear
        liblinear_util.predict(train_data_path, model_path, prediction_path)
        pred_label, pred_proba = liblinear_util.parse_prediction_file(prediction_path, minus_to_zeros=True)
        assert np.allclose(pred_label[:n_check], self.predict(X[:n_check]))
        assert np.allclose(pred_proba.flatten()[:n_check * 2], self.predict_proba(X[:n_check]).flatten(), atol=atol)

        return self

    def predict_proba(self, X):
        """
        Returns a 2d array of probabilities of shape (n_classes, len(X)).
        """
        assert X.ndim == 2

        pos_probas = []
        for i in range(0, len(X), self.pred_size):
            X_sim = linear_kernel(X[i: i + self.pred_size], self.X_train_)
            pos_probas.append(self._sigmoid(np.sum(X_sim * self.coef_, axis=1)))
        pos_proba = np.concatenate(pos_probas).reshape(-1, 1)
        proba = np.hstack([1 - pos_proba, pos_proba])
        return proba

    def predict(self, X):
        """
        Returns a 1d array of predicted labels of size=len(X).
        """
        pred_label = np.argmax(self.predict_proba(X), axis=1)
        return pred_label

    def get_weight(self):
        """
        Return a 1d array of train instance weights.
        """
        return self.coef_.copy()

    def explain(self, x):
        """
        Return a 2d array of train instance impacts of shape (1, n_train_samples).
        """
        assert x.shape == (1, self.X_train_.shape[1])
        x_sim = linear_kernel(x, self.X_train_)
        impact = x_sim * self.coef_
        return impact

    def _sigmoid(self, z):
        return 1 / (1 + np.exp(-z))