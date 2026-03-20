from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path('/Users/tegin/Desktop/UCCR/raw_data')
CORE_PATH = BASE / 'processed' / 'uccr_merged_standardized.csv'
OUT_JSON = BASE / 'processed' / 'analysis_2ug_results.json'

# Thresholds in nmol/L
DIAG_POST_THRESHOLD = 55.18      # 2 ug/dL
EXCL_BASE_THRESHOLD = 55.18      # 2 ug/dL
EXCL_POST_THRESHOLD = 55.18      # 2 ug/dL
BASAL_LT_1_UGDL_NMOLL = 27.59    # 1 ug/dL
BASAL_LT_2_UGDL_NMOLL = 55.18    # 2 ug/dL


def label_diag_post_2ug(value: float, qualifier: str | float | None) -> float:
    if pd.isna(value):
        return np.nan
    q = '' if pd.isna(qualifier) else str(qualifier).strip()
    if q in {'<', '<='}:
        return 1.0 if value <= DIAG_POST_THRESHOLD else np.nan
    if q in {'>', '>='}:
        return 0.0 if value > DIAG_POST_THRESHOLD else np.nan
    return 1.0 if value <= DIAG_POST_THRESHOLD else 0.0


def label_exclusion(value_baseline: float, q_baseline: str | float | None, value_post: float, q_post: str | float | None) -> float:
    def gt(value, qualifier, threshold):
        if pd.isna(value):
            return None
        q = '' if pd.isna(qualifier) else str(qualifier).strip()
        if q in {'>', '>='}:
            return value >= threshold
        if q in {'<', '<='}:
            return False
        return value > threshold

    def le(value, qualifier, threshold):
        if pd.isna(value):
            return None
        q = '' if pd.isna(qualifier) else str(qualifier).strip()
        if q in {'<', '<='}:
            return value <= threshold
        if q in {'>', '>='}:
            return False
        return value <= threshold

    baseline_excluded = gt(value_baseline, q_baseline, EXCL_BASE_THRESHOLD)
    post_excluded = gt(value_post, q_post, EXCL_POST_THRESHOLD)

    # Positive class = HA excluded
    if baseline_excluded is True or post_excluded is True:
        return 1.0

    baseline_not_excluded = le(value_baseline, q_baseline, EXCL_BASE_THRESHOLD)
    post_not_excluded = le(value_post, q_post, EXCL_POST_THRESHOLD)

    if (baseline_not_excluded is True) or (post_not_excluded is True):
        return 0.0

    return np.nan


def median_iqr(series: pd.Series) -> dict:
    s = pd.to_numeric(series, errors='coerce').dropna()
    if len(s) == 0:
        return {'median': np.nan, 'q1': np.nan, 'q3': np.nan, 'n': 0}
    return {
        'median': float(s.median()),
        'q1': float(s.quantile(0.25)),
        'q3': float(s.quantile(0.75)),
        'n': int(len(s)),
    }


def metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    tp = int(((y_true == 1) & (y_pred == 1)).sum())
    tn = int(((y_true == 0) & (y_pred == 0)).sum())
    fp = int(((y_true == 0) & (y_pred == 1)).sum())
    fn = int(((y_true == 1) & (y_pred == 0)).sum())
    sens = tp / (tp + fn) if (tp + fn) else np.nan
    spec = tn / (tn + fp) if (tn + fp) else np.nan
    ppv = tp / (tp + fp) if (tp + fp) else np.nan
    npv = tn / (tn + fn) if (tn + fn) else np.nan
    acc = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) else np.nan
    youden = sens + spec - 1 if not np.isnan(sens) and not np.isnan(spec) else np.nan
    return {
        'tp': tp,
        'tn': tn,
        'fp': fp,
        'fn': fn,
        'sensitivity': float(sens),
        'specificity': float(spec),
        'ppv': float(ppv),
        'npv': float(npv),
        'accuracy': float(acc),
        'youden_j': float(youden),
    }


def best_cutoff(group: pd.DataFrame, label_col: str) -> dict | None:
    d = group[['uccr', label_col]].dropna().copy()
    if d.empty:
        return None
    d['uccr'] = pd.to_numeric(d['uccr'], errors='coerce')
    d = d.dropna(subset=['uccr'])
    if d.empty or d[label_col].nunique() < 2:
        return None

    pos = d.loc[d[label_col] == 1, 'uccr']
    neg = d.loc[d[label_col] == 0, 'uccr']
    if len(pos) == 0 or len(neg) == 0:
        return None

    direction = 'higher' if pos.median() > neg.median() else 'lower'

    y_true = d[label_col].astype(int).to_numpy()
    x = d['uccr'].to_numpy()

    rows = []
    for t in np.sort(np.unique(x)):
        y_pred = (x >= t).astype(int) if direction == 'higher' else (x <= t).astype(int)
        m = metrics(y_true, y_pred)
        rows.append({'threshold': float(t), **m})

    perf = pd.DataFrame(rows).sort_values(['youden_j', 'sensitivity', 'specificity'], ascending=[False, False, False])
    best = perf.iloc[0].to_dict()
    best.update(
        {
            'direction': direction,
            'n_total': int(len(d)),
            'n_pos': int((d[label_col] == 1).sum()),
            'n_neg': int((d[label_col] == 0).sum()),
        }
    )
    return best


def cutoff_100_table(group: pd.DataFrame, label_col: str) -> dict:
    d = group[['uccr', label_col]].dropna().copy()
    d['uccr'] = pd.to_numeric(d['uccr'], errors='coerce')
    d = d.dropna(subset=['uccr'])

    if d.empty or d[label_col].nunique() < 2:
        return {
            'cutoff_100_sensitivity': None,
            'cutoff_100_specificity': None,
            'cutoff_100_accuracy': None,
        }

    y = d[label_col].astype(int).to_numpy()
    x = d['uccr'].to_numpy()

    rows = []
    for t in np.unique(x):
        for rule in ('<=', '>='):
            y_pred = (x <= t).astype(int) if rule == '<=' else (x >= t).astype(int)
            m = metrics(y, y_pred)
            rows.append({'rule': rule, 'threshold': float(t), **m})

    perf = pd.DataFrame(rows)

    def pick(metric: str):
        candidates = perf[np.isclose(perf[metric], 1.0)]
        if candidates.empty:
            return None
        if metric == 'sensitivity':
            candidates = candidates.sort_values(['specificity', 'accuracy'], ascending=[False, False])
        elif metric == 'specificity':
            candidates = candidates.sort_values(['sensitivity', 'accuracy'], ascending=[False, False])
        else:
            candidates = candidates.sort_values(['sensitivity', 'specificity'], ascending=[False, False])
        r = candidates.iloc[0]
        return {'rule': str(r['rule']), 'threshold': float(r['threshold'])}

    return {
        'cutoff_100_sensitivity': pick('sensitivity'),
        'cutoff_100_specificity': pick('specificity'),
        'cutoff_100_accuracy': pick('accuracy'),
    }


def baseline_lt_threshold(value: float, qualifier: str | float | None, threshold: float) -> bool:
    if pd.isna(value):
        return False
    q = '' if pd.isna(qualifier) else str(qualifier).strip()
    if q in {'<', '<='}:
        return value <= threshold
    if q in {'>', '>='}:
        return False
    return value < threshold


def missing_post_and_low_basal_mask(df: pd.DataFrame, basal_threshold_nmol_l: float) -> pd.Series:
    post_missing = pd.to_numeric(df['post_acth_cortisol_nmol_l'], errors='coerce').isna()
    basal_low = df.apply(
        lambda r: baseline_lt_threshold(
            r['pre_acth_baseline_cortisol_nmol_l'],
            r.get('pre_acth_baseline_cortisol_qualifier', np.nan),
            basal_threshold_nmol_l,
        ),
        axis=1,
    )
    return post_missing & basal_low


def run_analysis(df: pd.DataFrame) -> dict[str, object]:
    results: dict[str, object] = {}

    results['overall_counts'] = {
        'n_total': int(len(df)),
        'n_diag_used': int(df[['diag_label', 'uccr']].dropna().shape[0]),
        'n_diag_ha': int(df['diag_label'].eq(1).sum()),
        'n_diag_nonha': int(df['diag_label'].eq(0).sum()),
        'n_excl_used': int(df[['excl_label', 'uccr']].dropna().shape[0]),
        'n_excluded': int(df['excl_label'].eq(1).sum()),
        'n_not_excluded': int(df['excl_label'].eq(0).sum()),
    }

    uccr_stats = {}
    for test_type, g in df.groupby('urine_test_type', dropna=False):
        label = 'MISSING' if pd.isna(test_type) else str(test_type)
        uccr_stats[label] = {
            'HA': median_iqr(g.loc[g['diag_label'] == 1, 'uccr']),
            'Non-HA': median_iqr(g.loc[g['diag_label'] == 0, 'uccr']),
        }
    results['uccr_median_iqr_by_testtype_diag'] = uccr_stats

    urine_cort_stats = {}
    for test_type, g in df.groupby('urine_test_type', dropna=False):
        label = 'MISSING' if pd.isna(test_type) else str(test_type)
        urine_cort_stats[label] = median_iqr(g['urine_cortisol_nmol_l'])
    results['urine_cortisol_median_iqr_by_testtype'] = urine_cort_stats

    best_diag = {}
    best_excl = {}
    for test_type, g in df.groupby('urine_test_type', dropna=False):
        label = 'MISSING' if pd.isna(test_type) else str(test_type)
        best_diag[label] = best_cutoff(g, 'diag_label')
        best_excl[label] = best_cutoff(g, 'excl_label')
    results['best_cutoffs_diag_by_testtype'] = best_diag
    results['best_cutoffs_excl_by_testtype'] = best_excl

    cutoff_100_diag = {}
    cutoff_100_excl = {}
    for test_type, g in df.groupby('urine_test_type', dropna=False):
        label = 'MISSING' if pd.isna(test_type) else str(test_type)
        cutoff_100_diag[label] = cutoff_100_table(g, 'diag_label')
        cutoff_100_excl[label] = cutoff_100_table(g, 'excl_label')
    results['cutoff_100_diag_by_testtype'] = cutoff_100_diag
    results['cutoff_100_excl_by_testtype'] = cutoff_100_excl

    return results


def main() -> None:
    df = pd.read_csv(CORE_PATH)
    df['uccr'] = pd.to_numeric(df['uccr'], errors='coerce')

    df['diag_label'] = df.apply(
        lambda r: label_diag_post_2ug(r['post_acth_cortisol_nmol_l'], r.get('post_acth_cortisol_qualifier', np.nan)),
        axis=1,
    )

    df['excl_label'] = df.apply(
        lambda r: label_exclusion(
            r['pre_acth_baseline_cortisol_nmol_l'],
            r.get('pre_acth_baseline_cortisol_qualifier', np.nan),
            r['post_acth_cortisol_nmol_l'],
            r.get('post_acth_cortisol_qualifier', np.nan),
        ),
        axis=1,
    )

    results: dict[str, object] = {
        'thresholds': {
            'diagnosis_post_acth_nmol_l': DIAG_POST_THRESHOLD,
            'exclusion_baseline_nmol_l': EXCL_BASE_THRESHOLD,
            'exclusion_post_acth_nmol_l': EXCL_POST_THRESHOLD,
        }
    }

    # Keep current top-level outputs unchanged (base analysis).
    results.update(run_analysis(df))

    mask_lt1 = missing_post_and_low_basal_mask(df, BASAL_LT_1_UGDL_NMOLL)
    mask_lt2 = missing_post_and_low_basal_mask(df, BASAL_LT_2_UGDL_NMOLL)

    results['additional_conditions'] = {
        'exclude_missing_post_if_basal_lt1ugdl': {
            'condition': 'Exclude rows when post-ACTH cortisol is missing AND baseline cortisol <1 ug/dL',
            'baseline_threshold_nmol_l': BASAL_LT_1_UGDL_NMOLL,
            'excluded_rows': int(mask_lt1.sum()),
            **run_analysis(df.loc[~mask_lt1].copy()),
        },
        'exclude_missing_post_if_basal_lt2ugdl': {
            'condition': 'Exclude rows when post-ACTH cortisol is missing AND baseline cortisol <2 ug/dL',
            'baseline_threshold_nmol_l': BASAL_LT_2_UGDL_NMOLL,
            'excluded_rows': int(mask_lt2.sum()),
            **run_analysis(df.loc[~mask_lt2].copy()),
        },
    }

    OUT_JSON.write_text(json.dumps(results, indent=2))
    print(f'Wrote: {OUT_JSON}')


if __name__ == '__main__':
    main()
