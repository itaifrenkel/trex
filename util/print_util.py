"""
Utility methods for displaying data.
"""


def show_test_instance(test_ndx, svm_pred, pred_label, y_test=None, label=None):

    # show test instance
    if y_test is not None and label is not None:
        test_str = '\n\nTest [{}], distance to separator: {:.3f}, prediction: {}, actual: {}'
        print(test_str.format(test_ndx, svm_pred, label[pred_label], label[y_test[test_ndx]]))

    elif y_test is not None:
        test_str = '\n\nTest [{}], distance to separator: {:.3f}, prediction: {}, actual: {}'
        print(test_str.format(test_ndx, svm_pred, pred_label, y_test[test_ndx]))

    else:
        test_str = '\n\nTest [{}], distance to separator: {:.3f}, prediction: {}'
        print(test_str.format(test_ndx, svm_pred, pred_label))


def show_train_instances(impact_list, y_train, k=5, label=None):

    # show most influential train instances
    n_items = len(impact_list[0])

    if n_items == 2:
        train_str = 'Train [{}], impact: {:.3f}, label: {}'
    elif n_items == 4:
        train_str = 'Train [{}], impact: {:.3f}, similarity: {:.3f}, weight: {:.3f}, label: {}'
    else:
        exit('3 train impact items is ambiguous!')

    nonzero_sv = [items[0] for items in impact_list if abs(items[1]) > 0]
    print('\nSupport Vectors: {}'.format(len(impact_list)))
    print('Nonzero Support Vectors: {}'.format(len(nonzero_sv)))

    print('\nMost Impactful Train Instances')
    for items in impact_list[:k]:
        train_label = y_train[items[0]] if label is None else label[y_train[items[0]]]
        items += (train_label,)
        print(train_str.format(*items))


def show_fidelity(both_train, diff_train, y_train, both_test=None, diff_test=None, y_test=None):
    print('\nFidelity')

    n_both, n_diff, n_train = len(both_train), len(diff_train), len(y_train)
    print('train overlap: {} ({:.4f})'.format(n_both, n_both / n_train))
    print('train difference: {} ({:.4f})'.format(n_diff, n_diff / n_train))

    if both_test is not None and diff_test is not None and y_test is not None:
        n_both, n_diff, n_test = len(both_test), len(diff_test), len(y_test)
        print('test overlap: {} ({:.4f})'.format(n_both, n_both / n_test))
        print('test difference: {} ({:.4f})'.format(n_diff, n_diff / n_test))
