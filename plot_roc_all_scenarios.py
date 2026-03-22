from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

BASE = Path('/Users/tegin/Desktop/UCCR/raw_data')
CORE_PATH = BASE / 'processed' / 'uccr_merged_standardized.csv'
OUT_DIR = BASE / 'processed' / 'roc_scenarios'
SUMMARY_JSON = OUT_DIR / 'roc_scenarios_summary.json'
SUMMARY_CSV = OUT_DIR / 'roc_scenarios_summary.csv'
POINTS_CSV = OUT_DIR / 'roc_scenarios_points.csv'

DIAG_POST_THRESHOLD = 55.18
EXCL_BASE_THRESHOLD = 55.18
EXCL_POST_THRESHOLD = 55.18
BASAL_LT_1_UGDL_NMOLL = 27.59
BASAL_LT_2_UGDL_NMOLL = 55.18


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

    if baseline_excluded is True or post_excluded is True:
        return 1.0

    baseline_not_excluded = le(value_baseline, q_baseline, EXCL_BASE_THRESHOLD)
    post_not_excluded = le(value_post, q_post, EXCL_POST_THRESHOLD)

    if baseline_not_excluded is True or post_not_excluded is True:
        return 0.0

    return np.nan


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


def metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    tp = int(((y_true == 1) & (y_pred == 1)).sum())
    tn = int(((y_true == 0) & (y_pred == 0)).sum())
    fp = int(((y_true == 0) & (y_pred == 1)).sum())
    fn = int(((y_true == 1) & (y_pred == 0)).sum())
    sens = tp / (tp + fn) if (tp + fn) else np.nan
    spec = tn / (tn + fp) if (tn + fp) else np.nan
    acc = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) else np.nan
    return {
        'tp': float(tp),
        'tn': float(tn),
        'fp': float(fp),
        'fn': float(fn),
        'sensitivity': float(sens),
        'specificity': float(spec),
        'accuracy': float(acc),
        'youden_j': float(sens + spec - 1 if not np.isnan(sens) and not np.isnan(spec) else np.nan),
    }


def compute_roc(d: pd.DataFrame, feature_col: str, label_col: str) -> tuple[pd.DataFrame, dict] | tuple[None, None]:
    x = pd.to_numeric(d[feature_col], errors='coerce')
    y = pd.to_numeric(d[label_col], errors='coerce')
    keep = x.notna() & y.notna()
    d2 = pd.DataFrame({'x': x[keep], 'y': y[keep].astype(int)})

    if d2.empty or d2['y'].nunique() < 2:
        return None, None

    pos = d2.loc[d2['y'] == 1, 'x']
    neg = d2.loc[d2['y'] == 0, 'x']
    if pos.empty or neg.empty:
        return None, None

    direction = 'higher' if pos.median() > neg.median() else 'lower'
    thresholds = np.r_[-np.inf, np.sort(d2['x'].unique()), np.inf]

    rows = []
    for t in thresholds:
        y_pred = (d2['x'].to_numpy() >= t).astype(int) if direction == 'higher' else (d2['x'].to_numpy() <= t).astype(int)
        m = metrics(d2['y'].to_numpy(), y_pred)
        rows.append(
            {
                'threshold': float(t),
                'tpr': float(m['sensitivity']),
                'fpr': float(1 - m['specificity']),
                'specificity': float(m['specificity']),
                'accuracy': float(m['accuracy']),
                'youden_j': float(m['youden_j']),
            }
        )

    roc = pd.DataFrame(rows)
    roc = roc.sort_values(['fpr', 'tpr']).groupby('fpr', as_index=False)['tpr'].max().sort_values('fpr')
    auc = float(np.trapezoid(roc['tpr'].to_numpy(), roc['fpr'].to_numpy()))

    finite = pd.DataFrame(rows)
    finite = finite[np.isfinite(finite['threshold'])]
    best_row = finite.sort_values(['youden_j', 'tpr', 'specificity'], ascending=[False, False, False]).iloc[0]

    best_pred = (d2['x'].to_numpy() >= best_row['threshold']).astype(int) if direction == 'higher' else (d2['x'].to_numpy() <= best_row['threshold']).astype(int)
    best_metrics = metrics(d2['y'].to_numpy(), best_pred)

    info = {
        'direction': direction,
        'auc': auc,
        'best_threshold': float(best_row['threshold']),
        'best_sensitivity': float(best_metrics['sensitivity']),
        'best_specificity': float(best_metrics['specificity']),
        'best_accuracy': float(best_metrics['accuracy']),
        'n_total': int(len(d2)),
        'n_pos': int((d2['y'] == 1).sum()),
        'n_neg': int((d2['y'] == 0).sum()),
    }
    return roc, info


def plot_single_roc(roc: pd.DataFrame, info: dict, out_png: Path, title: str) -> None:
    plt.figure(figsize=(7, 6))
    plt.plot(roc['fpr'], roc['tpr'], color='#1f77b4', lw=2, label=f"ROC (AUC={info['auc']:.3f})")
    plt.plot([0, 1], [0, 1], linestyle='--', color='#7f7f7f', lw=1.2, label='No-discrimination')

    fpr_best = 1 - info['best_specificity']
    tpr_best = info['best_sensitivity']
    op = '>=' if info['direction'] == 'higher' else '<='
    plt.scatter([fpr_best], [tpr_best], color='#d62728', zorder=3, label=f"Best Youden: {op}{info['best_threshold']:.2f}")

    plt.title(title)
    plt.xlabel('1 - Specificity (False Positive Rate)')
    plt.ylabel('Sensitivity (True Positive Rate)')
    plt.xlim(0, 1)
    plt.ylim(0, 1)
    plt.grid(alpha=0.25)
    plt.legend(loc='lower right', frameon=True)
    plt.tight_layout()
    plt.savefig(out_png, dpi=300)
    plt.close()


def scenario_frame(df: pd.DataFrame, scenario_key: str) -> tuple[pd.DataFrame, int]:
    if scenario_key == 'base':
        return df.copy(), 0
    if scenario_key == 'exclude_missing_post_if_basal_lt1ugdl':
        m = missing_post_and_low_basal_mask(df, BASAL_LT_1_UGDL_NMOLL)
        return df.loc[~m].copy(), int(m.sum())
    if scenario_key == 'exclude_missing_post_if_basal_lt2ugdl':
        m = missing_post_and_low_basal_mask(df, BASAL_LT_2_UGDL_NMOLL)
        return df.loc[~m].copy(), int(m.sum())
    raise ValueError(f'Unknown scenario: {scenario_key}')


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(CORE_PATH)
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

    scenarios = {
        'base': 'Base (no extra exclusions)',
        'exclude_missing_post_if_basal_lt1ugdl': 'Exclude post missing AND basal <1 ug/dL',
        'exclude_missing_post_if_basal_lt2ugdl': 'Exclude post missing AND basal <2 ug/dL',
    }

    analyses = [
        ('uccr', 'UCCR'),
        ('urine_cortisol_nmol_l', 'UrineCortisol'),
    ]
    outcomes = [
        ('diag_label', 'Diagnosis'),
        ('excl_label', 'Exclusion'),
    ]

    summary_rows: list[dict] = []
    points_rows: list[pd.DataFrame] = []

    for scenario_key, scenario_label in scenarios.items():
        sdf, excluded_rows = scenario_frame(df, scenario_key)

        for feature_col, analysis_label in analyses:
            for label_col, outcome_label in outcomes:
                for test_type in ('CLIApost', 'RIA'):
                    g = sdf.loc[sdf['urine_test_type'].eq(test_type)].copy()
                    roc, info = compute_roc(g, feature_col, label_col)
                    if roc is None or info is None:
                        continue

                    file_name = f"roc_{scenario_key}_{analysis_label.lower()}_{outcome_label.lower()}_{test_type.lower()}.png"
                    out_png = OUT_DIR / file_name
                    title = f"ROC: {analysis_label} {outcome_label} | {test_type} | {scenario_label}"
                    plot_single_roc(roc, info, out_png, title)

                    summary_rows.append(
                        {
                            'scenario_key': scenario_key,
                            'scenario_label': scenario_label,
                            'analysis': analysis_label,
                            'outcome': outcome_label,
                            'urine_test_type': test_type,
                            'excluded_rows': excluded_rows,
                            'remaining_rows': int(len(sdf)),
                            'n_total_model': info['n_total'],
                            'n_pos': info['n_pos'],
                            'n_neg': info['n_neg'],
                            'direction': info['direction'],
                            'auc': info['auc'],
                            'best_threshold': info['best_threshold'],
                            'best_sensitivity': info['best_sensitivity'],
                            'best_specificity': info['best_specificity'],
                            'best_accuracy': info['best_accuracy'],
                            'roc_png': str(out_png),
                        }
                    )

                    p = roc.copy()
                    p['scenario_key'] = scenario_key
                    p['analysis'] = analysis_label
                    p['outcome'] = outcome_label
                    p['urine_test_type'] = test_type
                    points_rows.append(p)

    summary_df = pd.DataFrame(summary_rows).sort_values(['scenario_key', 'analysis', 'outcome', 'urine_test_type'])
    points_df = pd.concat(points_rows, ignore_index=True) if points_rows else pd.DataFrame()

    summary_df.to_csv(SUMMARY_CSV, index=False)
    points_df.to_csv(POINTS_CSV, index=False)

    out_payload = {
        'n_curves_generated': int(len(summary_df)),
        'summary_csv': str(SUMMARY_CSV),
        'points_csv': str(POINTS_CSV),
        'output_dir': str(OUT_DIR),
    }
    SUMMARY_JSON.write_text(json.dumps(out_payload, indent=2))

    print(f'Generated {len(summary_df)} ROC curves')
    print(f'Summary: {SUMMARY_CSV}')
    print(f'Points: {POINTS_CSV}')
    print(f'Metadata: {SUMMARY_JSON}')


if __name__ == '__main__':
    main()
