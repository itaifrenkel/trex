"""
Experiment: Tests the correlation between leave-one-out retraining and impact scores from sexee.
"""
import argparse

import tqdm
import sexee
import numpy as np
import matplotlib.pyplot as plt
from sklearn.base import clone

from util import model_util, data_util


def approximation(model='lgb', encoding='tree_path', dataset='iris', n_estimators=20,
                  random_state=69, timeit=False, test_ndx=0):

    # get model and data
    clf = model_util.get_classifier(model, n_estimators=n_estimators, random_state=random_state)
    X_train, X_test, y_train, y_test, label = data_util.get_data(dataset, random_state=random_state)

    # train a tree ensemble and explainer
    tree = clone(clf).fit(X_train, y_train)
    exp = sexee.TreeExplainer(tree, X_train, y_train)

    # explain a test instance
    x_test = X_test[test_ndx].reshape(1, -1)
    impact_list, (svm_proba, pred_label) = exp.train_impact(x_test, pred_svm=True)
    impact_list = [impact for impact in impact_list if abs(impact[1]) != 0]
    svm_influence = [impact[1] for impact in impact_list]
    assert pred_label == tree.predict(x_test)

    # compute leave-one-out retraining influence on prediction
    retrain_influence = []
    tree_proba = tree.predict_proba(x_test)[0][pred_label]
    for train_ndx, train_impact in tqdm.tqdm(impact_list):
        new_X_train = np.delete(X_train, train_ndx, axis=0)
        new_y_train = np.delete(y_train, train_ndx, axis=0)
        new_tree = clone(clf).fit(new_X_train, new_y_train)
        new_tree_proba = new_tree.predict_proba(x_test)[0][pred_label]
        retrain_influence.append(new_tree_proba - tree_proba)

    # plot correlation between impact scores
    corr = np.corrcoef(retrain_influence, svm_influence)[0][1]
    fig, ax = plt.subplots()
    ax.scatter(retrain_influence, svm_influence)
    ax.set_title('Approximation (test={}, corr={:.3f})'.format(test_ndx, corr))
    ax.set_xlabel('leave-one-out influence')
    ax.set_ylabel('svm impact')
    plt.show()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Feature representation extractions for tree ensembles',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--dataset', type=str, default='iris', help='dataset to explain.')
    parser.add_argument('--model', type=str, default='lgb', help='model to use.')
    parser.add_argument('--encoding', type=str, default='tree_path', help='type of encoding.')
    parser.add_argument('--n_estimators', metavar='N', type=int, default=20, help='number of trees in random forest.')
    parser.add_argument('--rs', metavar='RANDOM_STATE', type=int, default=69, help='for reproducibility.')
    parser.add_argument('--timeit', action='store_true', default=False, help='Show timing info for explainer.')
    parser.add_argument('--test_ndx', metavar='NUM', type=int, default=0, help='Test instance to explain.')
    args = parser.parse_args()
    print(args)
    approximation(args.model, args.encoding, args.dataset, args.n_estimators, args.rs, args.timeit, args.test_ndx)
