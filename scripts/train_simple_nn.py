#!/usr/bin/env python3
"""Train a simple single-layer network (logistic) using one feature.

Uses SGDClassifier (log loss) with partial_fit to emulate epochs and batching.
Prints accuracy on test set per epoch and final accuracy.
"""
import csv
import argparse
import json
from datetime import datetime, timezone
import numpy as np
from sklearn.linear_model import SGDClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score
import random

TRAIN_BAL = 'data/train_features_balanced.csv'
TEST = 'data/test_features.csv'


def load_feature_csv(path, feature):
    X = []
    y = []
    with open(path, newline='', encoding='utf-8') as f:
        r = csv.DictReader(f)
        for row in r:
            v = row.get(feature, '')
            if v == '' or v is None:
                continue
            try:
                X.append([float(v)])
            except Exception:
                continue
            y.append(1 if row.get('played', '0') == '1' else 0)
    return np.array(X, dtype=float), np.array(y, dtype=int)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--feature', default='pct_played_prior')
    parser.add_argument('--epochs', type=int, default=30)
    parser.add_argument('--batch-size', type=int, default=1024)
    parser.add_argument('--lr', type=float, default=0.01)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)

    print('Loading train (balanced):', TRAIN_BAL)
    X_train, y_train = load_feature_csv(TRAIN_BAL, args.feature)
    print('Loading test:', TEST)
    X_test, y_test = load_feature_csv(TEST, args.feature)

    print(f'Train shape: {X_train.shape}, positives: {y_train.sum()}, negatives: {len(y_train)-y_train.sum()}')
    print(f'Test shape:  {X_test.shape}, positives: {y_test.sum()}, negatives: {len(y_test)-y_test.sum()}')

    # scale feature
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)

    # build SGDClassifier with log loss (logistic regression), warm_start via partial_fit
    clf = SGDClassifier(loss='log_loss', learning_rate='constant', eta0=args.lr, random_state=args.seed)

    classes = np.array([0, 1])
    n = X_train.shape[0]
    batch = args.batch_size

    history = []
    for epoch in range(1, args.epochs + 1):
        # shuffle training data
        idx = np.arange(n)
        np.random.shuffle(idx)
        Xs = X_train[idx]
        ys = y_train[idx]
        # iterate minibatches
        for i in range(0, n, batch):
            xb = Xs[i:i+batch]
            yb = ys[i:i+batch]
            if epoch == 1 and i == 0:
                clf.partial_fit(xb, yb, classes=classes)
            else:
                clf.partial_fit(xb, yb)
        # evaluate on test set
        preds = clf.predict(X_test)
        acc = accuracy_score(y_test, preds)
        history.append(acc)
        print(f'Epoch {epoch:02d}/{args.epochs}  Test acc: {acc:.4f}')

    final_preds = clf.predict(X_test)
    final_acc = accuracy_score(y_test, final_preds)
    print('\nFinal test accuracy:', final_acc)

    # write history
    out_hist = 'data/train_epochs_accuracy.csv'
    with open(out_hist, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['epoch', 'test_accuracy'])
        for i, a in enumerate(history, start=1):
            w.writerow([i, a])
    print('Wrote epoch accuracy to', out_hist)

    # Also write simple model summary (weights, bias, metrics) to JSON for web viz
    best_acc = float(max(history)) if history else float(final_acc)
    best_epoch = int(np.argmax(history) + 1) if history else args.epochs
    try:
        weight = float(clf.coef_.ravel()[0])
        bias = float(clf.intercept_.ravel()[0])
    except Exception:
        weight = None
        bias = None

    mean_val = float(scaler.mean_[0]) if hasattr(scaler, 'mean_') and getattr(scaler, 'mean_', None) is not None and len(scaler.mean_) > 0 else 0.0
    scale_val = float(scaler.scale_[0]) if hasattr(scaler, 'scale_') and getattr(scaler, 'scale_', None) is not None and len(scaler.scale_) > 0 else 1.0

    model_summary = {
        'created_at': datetime.now(timezone.utc).isoformat(),
        'feature': args.feature,
        'epochs': args.epochs,
        'batch_size': args.batch_size,
        'learning_rate': args.lr,
        'seed': args.seed,
        'final_accuracy': float(final_acc),
        'best_accuracy': best_acc,
        'best_epoch': best_epoch,
        'weight': weight,
        'bias': bias,
        'scaler': {
            'mean': mean_val,
            'scale': scale_val
        }
    }

    out_model = 'data/model_simple.json'
    with open(out_model, 'w', encoding='utf-8') as f:
        json.dump(model_summary, f, ensure_ascii=False, indent=2)
    print('Wrote model summary to', out_model)


if __name__ == '__main__':
    main()
