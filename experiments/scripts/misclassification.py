"""
Explanation of missclassified test instances for the NC17_EvalPart1 (train) and
MFC18_EvalPart1 (test) dataset using TREX. Visualizes the most important feature
from the raw data perspective (positive vs negative), then weighting it using the weights
for a global explanation then weighting it using similarity x abs(weight) for a local explanation.
This also plots the weight distribution, as well as thr similarity vs weight distribution
for a single tst instance.
"""
import os
import sys
import argparse
here = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, here + '/../')  # for utility
sys.path.insert(0, here + '/../../')  # for libliner; TODO: remove this dependency

import shap
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
from scipy import stats

from trex.explainer import TreeExplainer
from utility import model_util, data_util, exp_util


def _get_top_features(x, shap_vals, feature, k=5):
    """
    Parameters
    ----------
    x: 1d array like
        Feature values for this instance.
    shap_vals: 1d array like
        Feature contributions to the prediction.
    feature: 1d array like
        Feature names.
    k: int (default=5)
        Only keep the top k features.

    Returns a list of (feature_name, feature_value, feature_shap) tuples.
    """
    assert len(x) == len(shap_vals) == len(feature)
    shap_sort_ndx = np.argsort(np.abs(shap_vals))[::-1]
    return list(zip(feature[shap_sort_ndx], x[shap_sort_ndx], shap_vals[shap_sort_ndx]))[:k]


def _shift_plot_right(ax, amt=0.02):
    """
    Shifts the subplot to the right by a specified amount.
    """
    box = ax.get_position()
    box.x0 += amt
    box.x1 += amt
    ax.set_position(box)


def _get_short_names(feature):
    replace = {}
    replace['p_fibberinh_1_0_mediforsystem'] = 'fibberinh'
    replace['p_kitwaredartmouthjpegdimples_0db8e4c_mediforsystem'] = 'jpegdimples'
    replace['dct03_a_baseline_ta1'] = 'dct03'
    replace['block02_baseline_ta1'] = 'block02'
    replace['p_ucrlstmwresamplingwcmm2_1_0_mediforsystem'] = 'lstmwresampling'
    replace['p_uscisigradbased02a_0_2a_mediforsystem'] = 'gradbased'
    replace['p_purdueta11adoublejpegdetection_2_0_mediforsystem'] = 'doublejpeg'
    replace['p_purdueta11acontrastenhancementdetection_1_0_mediforsystem'] = 'contrast_enhance'
    replace['p_sriprita1imgmdlprnubased_1_0_mediforsystem'] = 'prnubased'
    replace['p_ta11c_1_0_mediforsystem'] = 'tallc'

    feature = np.array([replace.get(f) if replace.get(f) is not None else f for f in feature])
    return feature


def misclassification(model='lgb', encoding='leaf_output', dataset='nc17_mfc18', n_estimators=100, random_state=69,
                      topk_train=4, topk_test=1, data_dir='data', verbose=0, linear_model='lr', kernel='linear',
                      topk_feature=5, true_label=False, alpha=0.5, fontsize=24, out_dir='output/misclassification'):

    # get model and data
    clf = model_util.get_classifier(model, n_estimators=n_estimators, random_state=random_state)
    data = data_util.get_data(dataset, random_state=random_state, data_dir=data_dir, return_feature=True)
    X_train, X_test, y_train, y_test, label, feature = data

    # shorten feature names
    feature = _get_short_names(feature)

    # get index of specified feature
    target_feature = 'lstmwresampling'
    feat_ndx = np.where(feature == target_feature)[0]

    X_train = np.delete(X_train, feat_ndx, axis=1)
    X_test = np.delete(X_test, feat_ndx, axis=1)

    # train a tree ensemble
    tree = clf.fit(X_train, y_train)
    tree_yhat = model_util.performance(tree, X_train, y_train, X_test, y_test)

    # train an svm on learned representations from the tree ensemble
    explainer = TreeExplainer(tree, X_train, y_train, encoding=encoding, random_state=random_state,
                              dense_output=True, linear_model=linear_model, kernel=kernel,
                              use_predicted_labels=not true_label)
    train_weight = explainer.get_weight()[0]

    if verbose > 0:
        print(explainer)

    shap_explainer = shap.TreeExplainer(tree)
    test_shap = shap_explainer.shap_values(X_test)
    train_shap = shap_explainer.shap_values(X_train)

    # extract predictions
    tree_yhat_train, tree_yhat_test = tree_yhat
    tree_pred_train = tree.predict(X_train)
    tree_pred_test = tree.predict(X_test)

    # get worst missed test indices
    test_dist = exp_util.instance_loss(tree.predict_proba(X_test), y_test)
    test_dist_ndx = np.argsort(test_dist)[::-1]
    test_dist = test_dist[test_dist_ndx]
    both_missed_test = test_dist_ndx

    test_dist_ndx1 = np.where((y_test == 1) & (tree.predict(X_test) == 0))[0]
    test_dist_ndx2 = np.where((y_test == 0) & (tree.predict(X_test) == 1))[0]

    if verbose > 0:
        print(test_dist_ndx1, test_dist_ndx1.shape)
        print(test_dist_ndx2, test_dist_ndx2.shape)

    pos_ndx = np.where(y_train == 1)[0]
    neg_ndx = np.where(y_train == 0)[0]

    if verbose > 0:
        print(stats.describe(X_train[pos_ndx][:, feat_ndx]))
        print(stats.describe(X_train[neg_ndx][:, feat_ndx]))

    bins = np.histogram(X_train[:, feat_ndx], bins=40)[1]  # get the bin edges
    if verbose > 0:
        print('bins: {}'.format(bins))

    # show explanations for missed instances
    test_str = '\ntest_{}\npredicted as {}, actual is {}'
    train_str = 'train_{} predicted as {}, actual is {}, contribution={:.3f}'

    # explain test instances
    for test_ndx in both_missed_test[:topk_test]:
        x_test = X_test[[test_ndx]]

        # find the most impactful features
        shap_list = _get_top_features(x_test[0], test_shap[test_ndx], feature, k=topk_feature)
        shap_sum = np.sum(np.abs(test_shap[test_ndx]))

        # find the most impactful training instances
        contributions = explainer.explain(x_test)[0]
        sort_ndx = np.argsort(np.abs(contributions))[::-1]
        contribution_sum = np.abs(contributions).sum()

        # plot the density of the most important featurem weighted by varying levels of explanation
        fig, axs = plt.subplots(1, 3, figsize=(15, 6))

        # show distribution of most important feature, unweighted
        pos_ndx = np.where(y_train == 1)[0]
        neg_ndx = np.where(y_train == 0)[0]
        axs[0].hist(X_train[pos_ndx][:, feat_ndx], bins=bins, color='g', hatch='.', alpha=alpha)
        axs[0].hist(X_train[neg_ndx][:, feat_ndx], bins=bins, color='r', hatch='\\', alpha=alpha)
        axs[0].set_xlabel('value', fontsize=fontsize)
        axs[0].set_ylabel('density', fontsize=fontsize)
        axs[0].set_title('Unweighted', fontsize=fontsize)
        axs[0].set_xlim(-0.25, 1.25)
        axs[0].tick_params(axis='both', which='major', labelsize=fontsize)

        # show distribution of most important feature weighted by TREX's global weights
        axs[1].hist(X_train[pos_ndx][:, feat_ndx], bins=bins, color='g', hatch='.',
                    weights=np.abs(train_weight)[pos_ndx], alpha=alpha)
        axs[1].hist(X_train[neg_ndx][:, feat_ndx], bins=bins, color='r', hatch='\\',
                    weights=np.abs(train_weight)[neg_ndx], alpha=alpha)
        axs[1].set_xlabel('value', fontsize=fontsize)
        axs[1].set_title(r'|$\alpha$|', fontsize=fontsize)
        axs[1].set_xlim(-0.25, 1.25)
        axs[1].tick_params(axis='both', which='major', labelsize=fontsize)

        # show distribution of most important feature, weighted by TREX's local explanation
        sim = explainer.similarity(x_test)[0]
        sim_weight = sim * train_weight
        l1 = axs[2].hist(X_train[pos_ndx][:, feat_ndx], bins=bins, color='g', hatch='.',
                         weights=np.abs(sim_weight)[pos_ndx], alpha=alpha)
        l2 = axs[2].hist(X_train[neg_ndx][:, feat_ndx], bins=bins, color='r', hatch='\\',
                         weights=np.abs(sim_weight)[neg_ndx], alpha=alpha)
        axs[2].set_xlabel('value', fontsize=fontsize)
        axs[2].set_title(r'|$\alpha$| * Similarity', fontsize=fontsize)
        axs[2].set_xlim(-0.25, 1.25)
        axs[2].tick_params(axis='both', which='major', labelsize=fontsize)

        fig.legend((l1[2][0], l2[2][0]), ('positive instances', 'negative instances'), loc='center', ncol=2,
                   bbox_to_anchor=(0.46, 0.05), fontsize=fontsize)
        fig.subplots_adjust(bottom=0.275)

        os.makedirs(out_dir, exist_ok=True)
        plt.savefig(os.path.join(out_dir, 'feature_distribution.pdf'), bbox_inches='tight')
        plt.tight_layout()

        if verbose > 0:
            print(stats.describe(np.abs(contributions)))
            print(tree.predict_proba(x_test))

        # plot TREX's global weights and similarity vs weight
        fig, axs = plt.subplots(1, 2, figsize=(15, 6))

        font_increase = 4

        # plot weight distribution for the training samples
        sns.distplot(train_weight, color='orange', ax=axs[0])
        axs[0].set_xlabel(r'$\alpha$', fontsize=fontsize + font_increase)
        axs[0].set_ylabel('density', fontsize=fontsize + font_increase)
        axs[0].set_title('(a)', fontsize=fontsize + font_increase)
        axs[0].tick_params(axis='both', which='major', labelsize=fontsize + font_increase)

        # plot similarity x weight for the training samples
        sim = explainer.similarity(x_test)[0]
        sns.distplot(sim * train_weight, color='g', ax=axs[1])
        axs[1].set_xlabel(r'$\alpha$ * similarity', fontsize=fontsize + font_increase)
        axs[1].set_title('(b)', fontsize=fontsize + font_increase)
        axs[1].tick_params(axis='both', which='major', labelsize=fontsize + font_increase)

        plt.tight_layout()
        plt.savefig(os.path.join(out_dir, 'weight_distribution.pdf'), bbox_inches='tight')
        plt.show()

        # display test instance
        test_instance_str = test_str.format(test_ndx, tree_pred_test[test_ndx], y_test[test_ndx])
        print(test_instance_str)
        for feature_name, feature_val, feature_shap in shap_list:
            print('\t{}: val={:.3f}, shap={:.3f}'.format(feature_name, feature_val, feature_shap / shap_sum))

        # display training instances
        for i, train_ndx in enumerate(sort_ndx[:topk_train]):

            # find the most impactful features
            shap_list = _get_top_features(X_train[train_ndx], train_shap[train_ndx], feature, k=topk_feature)
            shap_sum = np.sum(np.abs(train_shap[train_ndx]))

            # display train instance
            train_instance_str = train_str.format(train_ndx, tree_pred_train[train_ndx], y_train[train_ndx],
                                                  contributions[train_ndx] / contribution_sum)
            print(train_instance_str)
            for feature_name, feature_val, feature_shap in shap_list:
                print('\t{}: val={:.3f}, shap={:.3f}'.format(feature_name, feature_val, feature_shap / shap_sum))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Feature representation extractions for tree ensembles',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--dataset', type=str, default='nc17_mfc18', help='dataset to explain.')
    parser.add_argument('--model', type=str, default='lgb', help='model to use.')
    parser.add_argument('--linear_model', type=str, default='lr', help='linear model to use.')
    parser.add_argument('--true_label', action='store_true', help='train TREX on the true labels.')
    parser.add_argument('--encoding', type=str, default='leaf_output', help='type of encoding.')
    parser.add_argument('--kernel', type=str, default='linear', help='similarity kernel.')
    parser.add_argument('--n_estimators', metavar='N', type=int, default=100, help='number of trees in the ensemble.')
    parser.add_argument('--rs', metavar='RANDOM_STATE', type=int, default=69, help='for reproducibility.')
    parser.add_argument('--verbose', type=int, default=0, help='verbosity.')
    parser.add_argument('--topk_train', metavar='NUM', type=int, default=4, help='train instances to show.')
    parser.add_argument('--topk_test', metavar='NUM', type=int, default=1, help='missed test instances to show.')
    parser.add_argument('--topk_feature', metavar='NUM', type=int, default=5, help='features to show.')
    args = parser.parse_args()
    print(args)
    misclassification(model=args.model, encoding=args.encoding, dataset=args.dataset, n_estimators=args.n_estimators,
                      random_state=args.rs, topk_train=args.topk_train, topk_test=args.topk_test,
                      linear_model=args.linear_model, kernel=args.kernel, topk_feature=args.topk_feature,
                      true_label=args.true_label, verbose=args.verbose)