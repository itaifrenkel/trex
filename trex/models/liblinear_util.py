"""
This script parses the model and predictions files generated from the
'train' and 'predict' executables from liblinear.
"""
import os

import numpy as np
from sklearn.datasets import dump_svmlight_file


def create_data_file(X, y, data_file):
    """
    Creates a liblinear formatted data file where each line is
    <label>: <feature_1>: <val_1> <feature_2>:<val_2>
    """
    dump_svmlight_file(X, y, data_file, zero_based=False)


def train_linear_svc(data_file, model_file, C=1.0):
    """
    Trains an l2-regularized l2-loss (squared hinge) support vector classifier
    by solving the dual formulation using a linear kernel.

    Solver '1' in liblinear: https://github.com/cjlin1/liblinear
    Sklearn LinearSVC: https://github.com/scikit-learn/scikit-learn/blob/\
    fd237278e895b42abe8d8d09105cbb82dc2cbba7/sklearn/svm/_base.py#L782
    """
    dir_path = os.path.dirname(os.path.realpath(__file__))
    cmd = '{}/liblinear/train -s 1 -B 0 -c {} {} {} > /dev/null'.format(dir_path, C, data_file, model_file)
    result = os.system(cmd)
    assert result == 0


def train_lr(data_file, model_file, C=1.0):
    """
    Trains an l2-regularized logistic regression classifier using the
    dual formulation with a linear kernel.

    Solver '7' in liblinear: https://github.com/cjlin1/liblinear
    """
    dir_path = os.path.dirname(os.path.realpath(__file__))
    cmd = '{}/liblinear/train -s 7 -B 0 -c {} {} {} > /dev/null'.format(dir_path, C, data_file, model_file)
    result = os.system(cmd)
    assert result == 0


def predict_linear_svc(data_file, model_file, prediction_file):
    """
    Generates labels from the linear SVC model.
    """
    dir_path = os.path.dirname(os.path.realpath(__file__))
    cmd = '{}/liblinear/predict -b 0 {} {} {} > /dev/null'
    result = os.system(cmd.format(dir_path, data_file, model_file, prediction_file))
    assert result == 0


def predict_lr(data_file, model_file, prediction_file):
    """
    Generates labels and probability estimates using an l2 lr dual liblinear model.
    """
    dir_path = os.path.dirname(os.path.realpath(__file__))
    cmd = '{}/liblinear/predict -b 1 {} {} {} > /dev/null'.format(dir_path, data_file, model_file, prediction_file)
    result = os.system(cmd)
    assert result == 0


def parse_model_file(model_file):
    """
    Parses a liblinear output file as a result of running 'train -s 7 -B 0 <data_file> <filepath>'.
    Returns the alpha_i coefficients, representing the weights of each training instance.
    """
    assert os.path.exists(model_file)

    with open(model_file, 'r') as f:
        lines = f.readlines()

    bias = None
    alpha = None

    for i, line in enumerate(lines):
        line = line.strip()
        if line.startswith('solver_type'):
            assert line.split(' ')[1] in ['L2R_LR_DUAL', 'L2R_L2LOSS_SVC_DUAL']
        elif line.startswith('nr_class'):
            assert line.split(' ')[1] == '2'
        elif line.startswith('label'):
            assert line.split(' ')[1] == '1' and (line.split(' ')[2] == '0' or line.split(' ')[2] == '-1')
        elif line.startswith('nr_feature'):
            nr_feature = int(line.split(' ')[1])
        elif line.startswith('bias'):
            continue
        elif line.startswith('w'):
            w = lines[i + 1: i + nr_feature]
            w = [float(x.strip()) for x in w]
        elif line.startswith('nr_sample'):
            nr_sample = int(line.split(' ')[1])
        elif line.startswith('alpha'):
            alpha = [float(x) for x in lines[i + 1].strip().split(' ')]
            assert len(alpha) == nr_sample

    return np.array(alpha)


def parse_linear_svc_predictions(prediction_path, minus_to_zeros=True):
    """
    Parses a liblinear output file as a result of running 'predict -b 1 <data_file> <model_file> <filepath>'.
    """
    assert os.path.exists(prediction_path)

    with open(prediction_path, 'r') as f:
        lines = f.readlines()

    pred_label = np.array([int(p_str.strip()) for p_str in lines])

    if minus_to_zeros:
        pred_label = np.where(pred_label == -1, 0, 1)

    return pred_label


def parse_lr_predictions(prediction_path, minus_to_zeros=True):
    """
    Parses a liblinear output file as a result of running 'predict -b 1 <data_file> <model_file> <filepath>'.
    """
    assert os.path.exists(prediction_path)

    with open(prediction_path, 'r') as f:
        lines = f.readlines()

    assert lines[0] == 'labels 1 -1\n' or lines[0] == 'labels 1 0\n'

    pred_label = []
    proba_1 = []
    proba_0 = []

    for p_str in lines[1:]:
        items = p_str.strip().split(' ')
        pred_label.append(int(items[0]))
        proba_1.append(float(items[1]))
        proba_0.append(float(items[2]))

    proba = np.vstack([proba_0, proba_1]).T
    pred_label = np.array(pred_label)

    if minus_to_zeros:
        pred_label = np.where(pred_label == -1, 0, 1)

    return pred_label, proba
