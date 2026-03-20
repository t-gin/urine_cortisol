"""
Urine cortisol optimal cutoff analysis
=======================================
Mirrors recompute_analysis_2ug.py but operates on urine_cortisol_nmol_l
instead of the UCCR ratio.

Diagnostic definitions (same as UCCR analysis):
  HA diagnosis:  post-ACTH serum cortisol <= 2 ug/dL  (<=55.18 nmol/L)
  HA exclusion:  baseline serum cortisol  >  2 ug/dL  (>55.18 nmol/L)
                 OR post-ACTH serum cortisol >  2 ug/dL  (>55.18 nmol/L)

Threshold sweep criterion: Youden's J (maximises sensitivity + specificity - 1).
Stratified by urine_test_type (CLIApost, RIA).

Output:
  processed/urine_cortisol_analysis_results.json  – full numeric results
  (printed to stdout as a formatted summary table)
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

BASE       = Path('/Users/tegin/Desktop/UCCR/raw_data')
CORE_PATH  = BASE / 'processed' / 'uccr_merged_standardized.csv'
OUT_JSON   = BASE / 'processed' / 'urine_cortisol_analysis_results.json'

# Serum cortisol thresholds (nmol/L)
DIAG_POST_THRESHOLD = 55.18    # 2 ug/dL – diagnose HA
EXCL_BASE_THRESHOLD = 55.18    # 2 ug/dL – exclude HA (baseline)
EXCL_POST_THRESHOLD = 55.18    # 2 ug/dL – exclude HA (post-ACTH)
BASAL_LT_1_UGDL_NMOLL = 27.59  # 1 ug/dL
BASAL_LT_2_UGDL_NMOLL = 55.18  # 2 ug/dL

URINE_COL = 'urine_cortisol_nmol_l'
QUAL_COL  = 'urine_cortisol_qualifier'


# ---------------------------------------------------------------------------
# Label assignment (identical to recompute_analysis_2ug.py)
# ---------------------------------------------------------------------------

def label_diag_post_2ug(value: float, qualifier) -> float:
    if pd.isna(value):
        return np.nan
    q = '' if pd.isna(qualifier) else str(qualifier).strip()
    if q in {'<', '<='}:
        return 1.0 if value <= DIAG_POST_THRESHOLD else np.nan
    if q in {'>', '>='}:
        return 0.0 if value > DIAG_POST_THRESHOLD else np.nan
    return 1.0 if value <= DIAG_POST_THRESHOLD else 0.0


def label_exclusion(value_baseline, q_baseline, value_post, q_post) -> float:
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
    post_excluded     = gt(value_post,     q_post,     EXCL_POST_THRESHOLD)

    if baseline_excluded is True or post_excluded is True:
        return 1.0

    baseline_not_excl = le(value_baseline, q_baseline, EXCL_BASE_THRESHOLD)
    post_not_excl     = le(value_post,     q_post,     EXCL_POST_THRESHOLD)

    if baseline_not_excl is True or post_not_excl is True:
        return 0.0

    return np.nan


# ---------------------------------------------------------------------------
# Performance metrics
# ---------------------------------------------------------------------------

def metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    tp = int(((y_true == 1) & (y_pred == 1)).sum())
    tn = int(((y_true == 0) & (y_pred == 0)).sum())
    fp = int(((y_true == 0) & (y_pred == 1)).sum())
    fn = int(((y_true == 1) & (y_pred == 0)).sum())
    sens = tp / (tp + fn) if (tp + fn) else np.nan
    spec = tn / (tn + fp) if (tn + fp) else np.nan
    ppv  = tp / (tp + fp) if (tp + fp) else np.nan
    npv  = tn / (tn + fn) if (tn + fn) else np.nan
    acc  = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) else np.nan
    youden = sens + spec - 1 if not np.isnan(sens) and not np.isnan(spec) else np.nan
    return {
        'tp': tp, 'tn': tn, 'fp': fp, 'fn': fn,
        'sensitivity': float(sens),
        'specificity': float(spec),
        'ppv': float(ppv),
        'npv': float(npv),
        'accuracy': float(acc),
        'youden_j': float(youden),
    }


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


# ---------------------------------------------------------------------------
# Threshold sweep — urine cortisol
# ---------------------------------------------------------------------------

def best_cutoff_urine(group: pd.DataFrame, label_col: str) -> dict | None:
    """Find optimal urine cortisol cutoff by Youden's J."""
    d = group[[URINE_COL, label_col]].dropna().copy()
    d[URINE_COL] = pd.to_numeric(d[URINE_COL], errors='coerce')
    d = d.dropna(subset=[URINE_COL])
    if d.empty or d[label_col].nunique() < 2:
        return None

    pos = d.loc[d[label_col] == 1, URINE_COL]
    neg = d.loc[d[label_col] == 0, URINE_COL]
    if len(pos) == 0 or len(neg) == 0:
        return None

    # HA = lower urine cortisol; exclusion = higher urine cortisol
    direction = 'higher' if pos.median() > neg.median() else 'lower'

    y_true = d[label_col].astype(int).to_numpy()
    x = d[URINE_COL].to_numpy()

    rows = []
    for t in np.sort(np.unique(x)):
        y_pred = (x >= t).astype(int) if direction == 'higher' else (x <= t).astype(int)
        m = metrics(y_true, y_pred)
        rows.append({'threshold': float(t), **m})

    perf = pd.DataFrame(rows).sort_values(
        ['youden_j', 'sensitivity', 'specificity'], ascending=[False, False, False]
    )
    best = perf.iloc[0].to_dict()
    best.update({
        'direction': direction,
        'n_total': int(len(d)),
        'n_pos':   int((d[label_col] == 1).sum()),
        'n_neg':   int((d[label_col] == 0).sum()),
    })
    return best


def cutoff_100_table_urine(group: pd.DataFrame, label_col: str) -> dict:
    """Find urine cortisol cutoffs achieving 100% sensitivity / specificity / accuracy."""
    d = group[[URINE_COL, label_col]].dropna().copy()
    d[URINE_COL] = pd.to_numeric(d[URINE_COL], errors='coerce')
    d = d.dropna(subset=[URINE_COL])

    if d.empty or d[label_col].nunique() < 2:
        return {'cutoff_100_sensitivity': None, 'cutoff_100_specificity': None, 'cutoff_100_accuracy': None}

    y = d[label_col].astype(int).to_numpy()
    x = d[URINE_COL].to_numpy()

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
        return {'rule': str(r['rule']), 'threshold': float(r['threshold']),
                'sens': float(r['sensitivity']), 'spec': float(r['specificity']),
                'acc': float(r['accuracy'])}

    return {
        'cutoff_100_sensitivity': pick('sensitivity'),
        'cutoff_100_specificity': pick('specificity'),
        'cutoff_100_accuracy':    pick('accuracy'),
    }


def baseline_lt_threshold(value: float, qualifier, threshold: float) -> bool:
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


def run_analysis_urine(df: pd.DataFrame) -> dict:
    results: dict = {}

    results['overall_counts'] = {
        'n_total':        int(len(df)),
        'n_diag_ha':      int(df['diag_label'].eq(1).sum()),
        'n_diag_nonha':   int(df['diag_label'].eq(0).sum()),
        'n_excl_used':    int(df[['excl_label', URINE_COL]].dropna().shape[0]),
        'n_excluded':     int(df['excl_label'].eq(1).sum()),
        'n_not_excluded': int(df['excl_label'].eq(0).sum()),
    }

    urine_stats: dict = {}
    for test_type, g in df.groupby('urine_test_type', dropna=False):
        label = 'MISSING' if pd.isna(test_type) else str(test_type)
        urine_stats[label] = {
            'HA':     median_iqr(g.loc[g['diag_label'] == 1, URINE_COL]),
            'Non-HA': median_iqr(g.loc[g['diag_label'] == 0, URINE_COL]),
            'All':    median_iqr(g[URINE_COL]),
        }
    results['urine_cortisol_stats_by_testtype'] = urine_stats

    best_diag: dict = {}
    best_excl: dict = {}
    cutoff100_diag: dict = {}
    cutoff100_excl: dict = {}

    for test_type, g in df.groupby('urine_test_type', dropna=False):
        label = 'MISSING' if pd.isna(test_type) else str(test_type)
        best_diag[label] = best_cutoff_urine(g, 'diag_label')
        best_excl[label] = best_cutoff_urine(g, 'excl_label')
        cutoff100_diag[label] = cutoff_100_table_urine(g, 'diag_label')
        cutoff100_excl[label] = cutoff_100_table_urine(g, 'excl_label')

    results['best_cutoffs_diag_by_testtype'] = best_diag
    results['best_cutoffs_excl_by_testtype'] = best_excl
    results['cutoff_100_diag_by_testtype'] = cutoff100_diag
    results['cutoff_100_excl_by_testtype'] = cutoff100_excl

    return results


# ---------------------------------------------------------------------------
# Pretty-print helper
# ---------------------------------------------------------------------------

def fmt_pct(v) -> str:
    return f'{v * 100:.1f}%' if v is not None and not np.isnan(v) else 'N/A'


def print_best(label: str, b: dict | None) -> None:
    if b is None:
        print(f'  {label}: insufficient data')
        return
    d = b['direction']
    op = '<=' if d == 'lower' else '>='
    print(
        f"  {label} | cutoff {op}{b['threshold']:.2f} nmol/L"
        f"  Sens={fmt_pct(b['sensitivity'])}  Spec={fmt_pct(b['specificity'])}"
        f"  PPV={fmt_pct(b['ppv'])}  NPV={fmt_pct(b['npv'])}"
        f"  Acc={fmt_pct(b['accuracy'])}  Youden={b['youden_j']:.4f}"
        f"  (n={b['n_total']}, pos={b['n_pos']}, neg={b['n_neg']})"
    )


def fmt_100(c100: dict) -> str:
    if c100 is None:
        return 'N/A'
    r = c100['rule']
    t = c100['threshold']
    return f"{r}{t:.2f} nmol/L (sens={fmt_pct(c100['sens'])}, spec={fmt_pct(c100['spec'])}, acc={fmt_pct(c100['acc'])})"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    df = pd.read_csv(CORE_PATH)

    # Assign outcome labels
    df['diag_label'] = df.apply(
        lambda r: label_diag_post_2ug(
            r['post_acth_cortisol_nmol_l'],
            r.get('post_acth_cortisol_qualifier', np.nan),
        ),
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

    df[URINE_COL] = pd.to_numeric(df[URINE_COL], errors='coerce')

    # Keep current top-level outputs unchanged (base analysis).
    results = run_analysis_urine(df)

    mask_lt1 = missing_post_and_low_basal_mask(df, BASAL_LT_1_UGDL_NMOLL)
    mask_lt2 = missing_post_and_low_basal_mask(df, BASAL_LT_2_UGDL_NMOLL)

    results['additional_conditions'] = {
        'exclude_missing_post_if_basal_lt1ugdl': {
            'condition': 'Exclude rows when post-ACTH cortisol is missing AND baseline cortisol <1 ug/dL',
            'baseline_threshold_nmol_l': BASAL_LT_1_UGDL_NMOLL,
            'excluded_rows': int(mask_lt1.sum()),
            **run_analysis_urine(df.loc[~mask_lt1].copy()),
        },
        'exclude_missing_post_if_basal_lt2ugdl': {
            'condition': 'Exclude rows when post-ACTH cortisol is missing AND baseline cortisol <2 ug/dL',
            'baseline_threshold_nmol_l': BASAL_LT_2_UGDL_NMOLL,
            'excluded_rows': int(mask_lt2.sum()),
            **run_analysis_urine(df.loc[~mask_lt2].copy()),
        },
    }

    urine_stats = results['urine_cortisol_stats_by_testtype']
    best_diag = results['best_cutoffs_diag_by_testtype']
    best_excl = results['best_cutoffs_excl_by_testtype']
    cutoff100_diag = results['cutoff_100_diag_by_testtype']
    cutoff100_excl = results['cutoff_100_excl_by_testtype']

    # Save JSON
    OUT_JSON.write_text(json.dumps(results, indent=2))
    print(f'Wrote: {OUT_JSON}\n')

    # -----------------------------------------------------------------------
    # Pretty-print summary
    # -----------------------------------------------------------------------
    print('=' * 80)
    print('  URINE CORTISOL OPTIMAL CUTOFF ANALYSIS')
    print(f'  Serum diagnostic thresholds: diagnosis <=2 ug/dL ({DIAG_POST_THRESHOLD} nmol/L)')
    print(f'  Criterion: Youden\'s J  |  Stratified by urine_test_type')
    print('=' * 80)

    counts = results['overall_counts']
    print(f"\nOverall: {counts['n_total']} total rows | "
          f"HA={counts['n_diag_ha']}, Non-HA={counts['n_diag_nonha']}")

    print('\n--- Urine cortisol medians (nmol/L) ---')
    for tt, s in urine_stats.items():
        ha  = s['HA']
        nha = s['Non-HA']
        print(f"  {tt}")
        print(f"    HA     n={ha['n']:>3}  median={ha['median']:.1f}  IQR [{ha['q1']:.1f}–{ha['q3']:.1f}]")
        print(f"    Non-HA n={nha['n']:>3}  median={nha['median']:.1f}  IQR [{nha['q1']:.1f}–{nha['q3']:.1f}]")

    print('\n--- Optimal cutoffs: HA DIAGNOSIS (post-ACTH <=2 ug/dL) ---')
    for tt, b in best_diag.items():
        print_best(tt, b)

    print('\n--- Optimal cutoffs: HA EXCLUSION (baseline >2 ug/dL OR post-ACTH >2 ug/dL) ---')
    for tt, b in best_excl.items():
        print_best(tt, b)

    print('\n--- Cutoffs for 100% sensitivity ---')
    for tt in best_diag:
        c = cutoff100_diag[tt]['cutoff_100_sensitivity']
        print(f"  {tt} diagnosis : {fmt_100(c)}")
    for tt in best_excl:
        c = cutoff100_excl[tt]['cutoff_100_sensitivity']
        print(f"  {tt} exclusion : {fmt_100(c)}")

    print('\n--- Cutoffs for 100% specificity ---')
    for tt in best_diag:
        c = cutoff100_diag[tt]['cutoff_100_specificity']
        print(f"  {tt} diagnosis : {fmt_100(c)}")
    for tt in best_excl:
        c = cutoff100_excl[tt]['cutoff_100_specificity']
        print(f"  {tt} exclusion : {fmt_100(c)}")

    print('\n--- Cutoffs for 100% accuracy ---')
    for tt in best_diag:
        c = cutoff100_diag[tt]['cutoff_100_accuracy']
        print(f"  {tt} diagnosis : {fmt_100(c)}")
    for tt in best_excl:
        c = cutoff100_excl[tt]['cutoff_100_accuracy']
        print(f"  {tt} exclusion : {fmt_100(c)}")

    print('\n--- Additional conditions (excluded rows before calculations) ---')
    c1 = results['additional_conditions']['exclude_missing_post_if_basal_lt1ugdl']
    c2 = results['additional_conditions']['exclude_missing_post_if_basal_lt2ugdl']
    print(
        '  Condition A: post missing AND basal <1 ug/dL '
        f"-> excluded {c1['excluded_rows']} rows, remaining {c1['overall_counts']['n_total']}"
    )
    print(
        '  Condition B: post missing AND basal <2 ug/dL '
        f"-> excluded {c2['excluded_rows']} rows, remaining {c2['overall_counts']['n_total']}"
    )

    print()


if __name__ == '__main__':
    main()
