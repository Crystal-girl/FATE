#!/usr/bin/env python
# -*- coding: utf-8 -*-

#
#  Copyright 2019 The FATE Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
import copy
import json
import typing
from types import SimpleNamespace

from federatedml.param.base_param import BaseParam
from federatedml.param.cross_validation_param import CrossValidationParam
from federatedml.param.init_model_param import InitParam
from federatedml.param.predict_param import PredictParam
from federatedml.util import consts
from federatedml.protobuf.generated import mf_model_meta_pb2


class MtxFInitParam(InitParam):
    """
    Matrix Factorization Init Param Class.
    """
    def __init__(self, embed_dim=10, init_method='random_normal'):
        super(MtxFInitParam, self).__init__()
        self.embed_dim = embed_dim
        self.init_method = init_method


class MatrixFactorizationParam(BaseParam):
    """
    Parameters used for MatrixFactorization both for Homo mode or Hetero mode.

    Parameters
    ----------
    optimizer : str, 'SGD', 'RMSprop', 'Adam' or 'Adagrad', default: 'SGD'
        Optimize method

    batch_size : int, default: -1
        Batch size when updating model. -1 means use all data in a batch. i.e. Not to use mini-batch strategy.

    init_param: InitParam object, default: default InitParam object
        Init param method object.

    max_iter : int, default: 100
        The maximum iteration for training.

    early_stop : str, 'diff', 'weight_diff' or 'abs', default: 'diff'
        Method used to judge converge or not.
            a)	diff： Use difference of loss between two iterations to judge whether converge.
            b)  weight_diff: Use difference between weights of two consecutive iterations
            c)	abs: Use the absolute value of loss to judge whether converge. i.e. if loss < eps, it is converged.

    predict_param: PredictParam object, default: default PredictParam object

    cv_param: CrossValidationParam object, default: default CrossValidationParam object

    """

    def __init__(self,
                 secure_aggregate: bool = True,
                 aggregate_every_n_epoch: int = 1,
                 early_stop: typing.Union[str, dict, SimpleNamespace] = "diff",
                 optimizer: typing.Union[str, dict, SimpleNamespace] = 'SGD',
                 batch_size=-1,
                 init_param=MtxFInitParam(),
                 max_iter=100,
                 predict_param=PredictParam(),
                 cv_param=CrossValidationParam(),
                 validation_freqs=None,
                 metrics: typing.Union[str, list] = None,
                 loss: str = 'mse',
                 ):
        super(MatrixFactorizationParam, self).__init__()
        self.secure_aggregate = secure_aggregate
        self.aggregate_every_n_epoch = aggregate_every_n_epoch
        self.early_stop = early_stop
        self.metrics = metrics
        self.loss = loss

        self.optimizer = optimizer
        self.batch_size = batch_size
        self.init_param = copy.deepcopy(init_param)
        self.max_iter = max_iter
        self.predict_param = copy.deepcopy(predict_param)
        self.cv_param = copy.deepcopy(cv_param)
        self.validation_freqs = validation_freqs

    def check(self):
        """
        Check matrix factorization's parameters.
        :return:
        """
        descr = "matrix_factorization's"

        self.early_stop = self._parse_early_stop(self.early_stop)
        self.optimizer = self._parse_optimizer(self.optimizer)
        self.metrics = self._parse_metrics(self.metrics)

        if self.batch_size != -1:
            if type(self.batch_size).__name__ not in ["int"] \
                    or self.batch_size < consts.MIN_BATCH_SIZE:
                raise ValueError(descr + " {} not supported, should be larger than 10 or "
                                         "-1 represent for all data".format(self.batch_size))

        if 'decay' in self.optimizer.__dict__["kwargs"]:
            if not isinstance(self.optimizer.kwargs['decay'], (int, float)) \
                    or (isinstance(self.optimizer.kwargs['decay'], (int, float)) and \
                        self.optimizer.kwargs['decay'] < 0):
                raise ValueError(
                    "svdpp's optimizer.decay {} not supported, should be 'int' or 'float' "
                    "and greater than 0".format(
                        self.optimizer.kwargs['decay']))

        if 'learning_rate' in self.optimizer.__dict__["kwargs"]:
            if not isinstance(self.optimizer.kwargs['learning_rate'], (int, float)) \
                    or (isinstance(self.optimizer.kwargs['learning_rate'], (int, float)) and \
                        self.optimizer.kwargs['learning_rate'] < 0):
                raise ValueError(
                    "svdpp's optimizer.learning_rate {} not supported, should be 'int' or 'float', "
                    "and greater than 0".format(
                        self.optimizer.kwargs['learning_rate']))

        self.init_param.check()

        if type(self.max_iter).__name__ != "int":
            raise ValueError(
                "matrix_factorization's max_iter {} not supported, should be int type".format(self.max_iter))
        elif self.max_iter <= 0:
            raise ValueError(
                "matrix_factorization's max_iter must be greater or equal to 1")

        return True

    def _parse_early_stop(self, param):
        """
           Examples:

               1. "early_stop": "diff"
               2. "early_stop": {
                       "early_stop": "diff",
                       "eps": 0.0001
                   }
        """
        default_eps = 0.0001
        if isinstance(param, str):
            return SimpleNamespace(converge_func=param, eps=default_eps)
        if isinstance(param, dict):
            early_stop = param.get("early_stop", None)
            eps = param.get("eps", default_eps)
            if not early_stop:
                raise ValueError(f"early_stop config: {param} invalid")
            return SimpleNamespace(converge_func=early_stop, eps=eps)
        else:
            raise ValueError(f"invalid type for early_stop: {type(param)}")

    def _parse_optimizer(self, param):
        """
        Examples:

            1. "optimize": "SGD"
            2. "optimize": {
                    "optimizer": "SGD",
                    "learning_rate": 0.05
                }
        """
        kwargs = {}
        if isinstance(param, str):
            return SimpleNamespace(optimizer=param, kwargs=kwargs)
        elif isinstance(param, dict):
            optimizer = param.get("optimizer", kwargs)
            if not optimizer:
                raise ValueError(f"optimizer config: {param} invalid")
            kwargs = {k: v for k, v in param.items() if k != "optimizer"}
            return SimpleNamespace(optimizer=optimizer, kwargs=kwargs)
        else:
            raise ValueError(f"invalid type for optimize: {type(param)}")

    def _parse_metrics(self, param):
        """
        Examples:

            1. "metrics": "Accuracy"
            2. "metrics": ["Accuracy"]
        """
        if not param:
            return []
        elif isinstance(param, str):
            return [param]
        elif isinstance(param, list):
            return param
        else:
            raise ValueError(f"invalid metrics type: {type(param)}")


class HeteroMatrixParam(MatrixFactorizationParam):
    """
    Parameters
    ----------
    re_encrypt_batches : int, default: 2
        Required when using encrypted version HomoLR. Since multiple batch updating coefficient may cause
        overflow error. The model need to be re-encrypt for every several batches. Please be careful when setting
        this parameter. Too large batches may cause training failure.

    aggregate_iters : int, default: 1
        Indicate how many iterations are aggregated once.

    """

    def __init__(self, penalty='L2',
                 tol=1e-5, alpha=1.0, optimizer='sgd',
                 batch_size=-1, learning_rate=0.01, init_param=MtxFInitParam(),
                 max_iter=100, early_stop='diff',
                 predict_param=PredictParam(), cv_param=CrossValidationParam(),
                 decay=1, decay_sqrt=True,
                 aggregate_iters=1, validation_freqs=None
                 ):
        super(HeteroMatrixParam, self).__init__(optimizer=optimizer,
                                                batch_size=batch_size,
                                                init_param=init_param, max_iter=max_iter,
                                                early_stop=early_stop,
                                                predict_param=predict_param,
                                                cv_param=cv_param,
                                                validation_freqs=validation_freqs)
        self.aggregate_iters = aggregate_iters

    def check(self):
        """
        Check parameter values.
        :return:
        """
        super().check()

        if not isinstance(self.aggregate_iters, int):
            raise ValueError(
                "matrix_factorization's aggregate_iters {} not supported, should be int type".format(
                    self.aggregate_iters))

        return True

    def generate_pb(self):
        """
        Generate protobuf from parameters.
        :return: protobuf object.
        """
        pb = mf_model_meta_pb2.HeteroMFParam()
        pb.secure_aggregate = self.secure_aggregate
        pb.aggregate_every_n_epoch = self.aggregate_every_n_epoch
        pb.batch_size = self.batch_size
        pb.max_iter = self.max_iter
        pb.early_stop.early_stop = self.early_stop.converge_func
        pb.early_stop.eps = self.early_stop.eps

        for metric in self.metrics:
            pb.metrics.append(metric)

        pb.optimizer.optimizer = self.optimizer.optimizer
        pb.optimizer.args = json.dumps(self.optimizer.kwargs)
        pb.loss = self.loss
        pb.embed_dim = self.init_param.embed_dim
        return pb

    def restore_from_pb(self, pb):
        """
        Restore parameter from protobuf.
        :param pb: protobuf object.
        """
        self.secure_aggregate = pb.secure_aggregate
        self.aggregate_every_n_epoch = pb.aggregate_every_n_epoch
        self.batch_size = pb.batch_size
        self.max_iter = pb.max_iter
        self.early_stop = self._parse_early_stop(dict(early_stop=pb.early_stop.early_stop, eps=pb.early_stop.eps))
        self.metrics = list(pb.metrics)
        self.optimizer = self._parse_optimizer(dict(optimizer=pb.optimizer.optimizer, **json.loads(pb.optimizer.args)))
        self.loss = pb.loss
        self.init_param = MtxFInitParam(embed_dim=pb.embed_dim)
