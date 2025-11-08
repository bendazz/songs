#!/usr/bin/env python3
"""Prepare train/test CSVs from the date-song play matrix.

Produces a features CSV for modeling and offers simple balancing options
(undersampling negatives or oversampling positives) without extra deps.

Usage examples:
  python3 scripts/prepare_train_test.py \
    --features years_since_release,pct_played_prior,catalog_size_at_play_date \
    --split-method time --train-size 0.8 --balance undersample --pos_frac 0.5

Outputs:
  data/train_features.csv
  data/test_features.csv
  data/train_features_balanced.csv  (if balance applied)
"""
import argparse
import csv
import os
import random
from datetime import datetime
from typing import List

INPUT_CSV = "data/springsteen_date_song_play_matrix.csv"
OUT_TRAIN = "data/train_features.csv"
OUT_TEST = "data/test_features.csv"
OUT_TRAIN_BAL = "data/train_features_balanced.csv"


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--input", default=INPUT_CSV, help="Path to input matrix CSV (default: data/springsteen_date_song_play_matrix.csv)")
    p.add_argument("--features", default="years_since_release,pct_played_prior,catalog_size_at_play_date",
                   help="Comma-separated list of numeric features to include (must be columns in matrix CSV)")
    p.add_argument("--split-method", choices=["time", "random"], default="time",
                   help="How to split train/test: time-based (by date) or random stratified by label")
    p.add_argument("--train-size", type=float, default=0.8, help="Fraction for training set")
    p.add_argument("--balance", choices=["none", "undersample", "oversample"], default="none",
                   help="Balance training set by undersampling negatives or oversampling positives")
    p.add_argument("--pos-fraction", type=float, default=None,
                   help="Desired positive fraction in balanced train set (e.g., 0.5 for 1:1). If omitted, uses parity for undersample/oversample.")
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


def read_matrix(path: str):
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append(row)
    return rows


def to_float_safe(s):
    try:
        return float(s)
    except Exception:
        return None


def time_split(rows, train_frac):
    # find sorted unique dates
    dates = sorted({r['play_date_iso'] for r in rows if r.get('play_date_iso')})
    if not dates:
        raise RuntimeError("No dates found for time split")
    cutoff_index = max(1, int(len(dates) * train_frac)) - 1
    cutoff = dates[cutoff_index]
    train = [r for r in rows if r.get('play_date_iso') and r['play_date_iso'] <= cutoff]
    test = [r for r in rows if not r.get('play_date_iso') or r['play_date_iso'] > cutoff]
    return train, test, cutoff


def stratified_random_split(rows, train_frac, seed=42):
    rnd = random.Random(seed)
    by_label = {"0": [], "1": []}
    for r in rows:
        label = r.get('played', '0')
        if label not in by_label:
            by_label[label] = []
        by_label[label].append(r)
    train, test = [], []
    for label, lst in by_label.items():
        n_train = int(len(lst) * train_frac)
        rnd.shuffle(lst)
        train.extend(lst[:n_train])
        test.extend(lst[n_train:])
    return train, test, None


def write_features(path: str, rows: List[dict], features: List[str]):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        header = features + ['played', 'play_date_iso', 'song_title']
        writer.writerow(header)
        for r in rows:
            vals = []
            skip = False
            for feat in features:
                v = r.get(feat, None)
                if v is None or v == '':
                    # try safe float parse
                    v = r.get(feat)
                vals.append(v)
            # played label
            vals.append(r.get('played', '0'))
            vals.append(r.get('play_date_iso', ''))
            vals.append(r.get('song_title', ''))
            writer.writerow(vals)


def balance_train(train_rows: List[dict], desired_pos_frac: float = None, seed=42, method='undersample'):
    rnd = random.Random(seed)
    pos = [r for r in train_rows if r.get('played') == '1']
    neg = [r for r in train_rows if r.get('played') != '1']
    n_pos = len(pos)
    n_neg = len(neg)
    if desired_pos_frac is None:
        # default to parity
        desired_pos_frac = 0.5
    total_desired = n_pos + n_neg
    # compute desired positive count
    desired_pos = int(total_desired * desired_pos_frac)
    if method == 'undersample':
        # reduce negatives while keeping positives fixed so that pos/(pos+neg)=desired_pos_frac
        if desired_pos_frac <= 0 or desired_pos_frac >= 1:
            return train_rows
        # desired_neg solves pos/(pos+desired_neg) = f  => desired_neg = pos*(1-f)/f
        desired_neg = int(n_pos * (1.0 - desired_pos_frac) / (desired_pos_frac + 1e-12))
        if desired_neg >= n_neg:
            # nothing to do
            return train_rows
        rnd.shuffle(neg)
        neg_sample = neg[:desired_neg]
        new_rows = pos + neg_sample
        rnd.shuffle(new_rows)
        return new_rows
    else:  # oversample
        # increase positives so that pos/(pos+neg)=desired_pos_frac, keep negatives fixed
        if desired_pos_frac <= 0 or desired_pos_frac >= 1:
            return train_rows
        # desired_pos solves desired_pos/(desired_pos + n_neg) = f => desired_pos = f * n_neg / (1-f)
        desired_pos_count = int((desired_pos_frac * n_neg) / (1.0 - desired_pos_frac + 1e-12))
        if desired_pos_count <= n_pos:
            return train_rows
        needed = desired_pos_count - n_pos
        picks = [rnd.choice(pos) for _ in range(needed)] if pos else []
        new_rows = train_rows + picks
        rnd.shuffle(new_rows)
        return new_rows


def summarize(rows, name="set"):
    total = len(rows)
    pos = sum(1 for r in rows if r.get('played') == '1')
    neg = total - pos
    dates = len({r.get('play_date_iso') for r in rows})
    print(f"{name}: total={total}, pos={pos}, neg={neg}, unique_dates={dates}")


def main():
    args = parse_args()
    random.seed(args.seed)
    features = [f.strip() for f in args.features.split(',') if f.strip()]
    input_csv = args.input or INPUT_CSV
    print("Loading matrix...", input_csv)
    rows = read_matrix(input_csv)
    print(f"Total rows read: {len(rows)}")

    # Optionally filter out rows with missing feature values
    valid_rows = []
    for r in rows:
        ok = True
        for feat in features:
            v = r.get(feat, '')
            if v is None or v == '':
                ok = False
                break
        if ok:
            valid_rows.append(r)
    print(f"Rows with all features present: {len(valid_rows)}")

    if args.split_method == 'time':
        train, test, cutoff = time_split(valid_rows, args.train_size)
        print(f"Time split cutoff: {cutoff}")
    else:
        train, test, cutoff = stratified_random_split(valid_rows, args.train_size, seed=args.seed)

    summarize(train, 'train (before balance)')
    summarize(test, 'test')

    write_features(OUT_TRAIN, train, features)
    write_features(OUT_TEST, test, features)
    print(f"Wrote train -> {OUT_TRAIN} and test -> {OUT_TEST}")

    if args.balance != 'none':
        balanced = balance_train(train, desired_pos_frac=args.pos_fraction, seed=args.seed, method=args.balance)
        summarize(balanced, 'train (after balance)')
        write_features(OUT_TRAIN_BAL, balanced, features)
        print(f"Wrote balanced train -> {OUT_TRAIN_BAL}")


if __name__ == '__main__':
    main()
