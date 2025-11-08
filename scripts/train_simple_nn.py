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
from sklearn.linear_model import SGDClassifier, LogisticRegression
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score
import random

TRAIN_BAL = 'data/train_features_balanced.csv'
TEST = 'data/test_features.csv'


def load_features_csv(path, features):
    """Load one or more numeric features and labels.

    Rows missing any requested feature are skipped.
    Returns X (n,k) and y (n,).
    """
    X = []
    y = []
    feats = list(features)
    with open(path, newline='', encoding='utf-8') as f:
        r = csv.DictReader(f)
        for row in r:
            vals = []
            missing = False
            for feat in feats:
                sv = row.get(feat, '')
                if sv == '' or sv is None:
                    missing = True
                    break
                try:
                    vals.append(float(sv))
                except Exception:
                    missing = True
                    break
            if missing:
                continue
            X.append(vals)
            y.append(1 if row.get('played', '0') == '1' else 0)
    return np.array(X, dtype=float), np.array(y, dtype=int)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--features', default='pct_played_prior', help='Comma-separated feature names to use')
    parser.add_argument('--epochs', type=int, default=30)
    parser.add_argument('--batch-size', type=int, default=1024)
    parser.add_argument('--lr', type=float, default=0.01)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--solver', choices=['sgd', 'lbfgs'], default='sgd', help='Training algorithm for logistic regression')
    parser.add_argument('--model', choices=['logreg', 'mlp'], default='logreg', help='Model type: logistic regression or 1-hidden-layer MLP')
    parser.add_argument('--hidden', type=int, default=16, help='Hidden layer size for MLP')
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)

    features = [s.strip() for s in args.features.split(',') if s.strip()]
    print('Features:', features)
    print('Loading train (balanced):', TRAIN_BAL)
    X_train, y_train = load_features_csv(TRAIN_BAL, features)
    print('Loading test:', TEST)
    X_test, y_test = load_features_csv(TEST, features)

    print(f'Train shape: {X_train.shape}, positives: {y_train.sum()}, negatives: {len(y_train)-y_train.sum()}')
    print(f'Test shape:  {X_test.shape}, positives: {y_test.sum()}, negatives: {len(y_test)-y_test.sum()}')

    # scale feature
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)

    history = []
    if args.model == 'mlp':
        # One hidden layer MLP
        clf = MLPClassifier(hidden_layer_sizes=(args.hidden,), activation='relu', solver='adam',
                            learning_rate_init=args.lr, max_iter=300, early_stopping=True,
                            n_iter_no_change=10, validation_fraction=0.1, random_state=args.seed)
        clf.fit(X_train, y_train)
        preds = clf.predict(X_test)
        acc = accuracy_score(y_test, preds)
        history.append(acc)
        print(f"MLP (1 hidden layer={args.hidden}) — Test acc: {acc:.4f}")
    else:
        if args.solver == 'sgd':
            # SGDClassifier with log loss (logistic regression), warm_start via partial_fit
            clf = SGDClassifier(loss='log_loss', learning_rate='constant', eta0=args.lr, random_state=args.seed)
            classes = np.array([0, 1])
            n = X_train.shape[0]
            batch = args.batch_size
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
        else:
            # Exact logistic regression via LBFGS
            clf = LogisticRegression(max_iter=2000, solver='lbfgs', random_state=args.seed)
            clf.fit(X_train, y_train)
            preds = clf.predict(X_test)
            acc = accuracy_score(y_test, preds)
            history.append(acc)
            print(f'LBFGS logistic — Test acc: {acc:.4f}')

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
    weights = None
    bias = None
    mlp_layers = None
    try:
        if args.model == 'mlp' and hasattr(clf, 'coefs_'):
            # Store full layer weights for MLP
            mlp_layers = {
                'coefs': [[float(v) for v in np.ravel(w)] for w in clf.coefs_],
                'intercepts': [[float(v) for v in b] for b in clf.intercepts_],
                'shapes': [list(w.shape) for w in clf.coefs_]
            }
        elif hasattr(clf, 'coef_') and hasattr(clf, 'intercept_'):
            coef = clf.coef_.ravel()
            weights = [float(w) for w in coef]
            bias = float(clf.intercept_.ravel()[0])
    except Exception:
        pass

    mean_val = [float(m) for m in getattr(scaler, 'mean_', [])] if hasattr(scaler, 'mean_') and getattr(scaler, 'mean_', None) is not None else []
    scale_val = [float(s) for s in getattr(scaler, 'scale_', [])] if hasattr(scaler, 'scale_') and getattr(scaler, 'scale_', None) is not None else []

    model_summary = {
        'created_at': datetime.now(timezone.utc).isoformat(),
        'features': features,
        'epochs': args.epochs,
        'batch_size': args.batch_size,
        'learning_rate': args.lr,
        'seed': args.seed,
        'model_type': args.model,
        'final_accuracy': float(final_acc),
        'best_accuracy': best_acc,
        'best_epoch': best_epoch,
        'weights': weights,
        'bias': bias,
        'scaler': {
            'mean': mean_val,
            'scale': scale_val
        },
        'mlp_layers': mlp_layers
    }
    # Backward-compat keys if single-feature
    if model_summary['weights'] and len(model_summary['weights']) == 1 and len(features) == 1:
        model_summary['feature'] = features[0]
        model_summary['weight'] = model_summary['weights'][0]

    out_model = 'data/model_simple.json'
    with open(out_model, 'w', encoding='utf-8') as f:
        json.dump(model_summary, f, ensure_ascii=False, indent=2)
    print('Wrote model summary to', out_model)


if __name__ == '__main__':
    main()
