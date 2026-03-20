from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

BASE = Path('/Users/tegin/Desktop/UCCR/raw_data')
CORE_PATH = BASE / 'processed' / 'uccr_merged_standardized.csv'
OUT_PNG = BASE / 'processed' / 'roc_urine_cortisol_cliapost_diagnosis.png'
OUT_POINTS = BASE / 'processed' / 'roc_urine_cortisol_cliapost_diagnosis_points.csv'
OUT_SUMMARY = BASE / 'processed' / 'roc_urine_cortisol_cliapost_diagnosis_summary.json'

DIAG_POST_THRESHOLD = 55.18  # 2 ug/dL


def label_diag_post_2ug(value: float, qualifier) -> float:
    if pd.isna(value):
        return np.nan
    q = '' if pd.isna(qualifier) else str(qualifier).strip()
    if q in {'<', '<='}:
        return 1.0 if value <= DIAG_POST_THRESHOLD else np.nan
    if q in {'>', '>='}:
        return 0.0 if value > DIAG_POST_THRESHOLD else np.nan
    return 1.0 if value <= DIAG_POST_THRESHOLD else 0.0


def confusion(y_true: np.ndarray, y_pred: np.ndarray) -> tuple[int, int, int, int]:
    tp = int(((y_true == 1) & (y_pred == 1)).sum())
    tn = int(((y_true == 0) & (y_pred == 0)).sum())
    fp = int(((y_true == 0) & (y_pred == 1)).sum())
    fn = int(((y_true == 1) & (y_pred == 0)).sum())
    return tp, tn, fp, fn


def sens_spec(y_true: np.ndarray, y_pred: np.ndarray) -> tuple[float, float]:
    tp, tn, fp, fn = confusion(y_true, y_pred)
    sens = tp / (tp + fn) if (tp + fn) else np.nan
    spec = tn / (tn + fp) if (tn + fp) else np.nan
    return sens, spec


def roc_for_lower_values_positive(x: np.ndarray, y_true: np.ndarray) -> pd.DataFrame:
    # For diagnosis, lower urine cortisol implies higher HA likelihood,
    # so classification rule is positive if x <= threshold.
    thresholds = np.r_[-np.inf, np.sort(np.unique(x)), np.inf]
    rows: list[dict] = []

    for t in thresholds:
        y_pred = (x <= t).astype(int)
        sens, spec = sens_spec(y_true, y_pred)
        youden = sens + spec - 1 if not np.isnan(sens) and not np.isnan(spec) else np.nan
        rows.append(
            {
                'threshold_nmol_l': float(t),
                'tpr_sensitivity': float(sens),
                'fpr_1_minus_specificity': float(1 - spec),
                'specificity': float(spec),
                'youden_j': float(youden),
            }
        )

    roc = pd.DataFrame(rows).sort_values('fpr_1_minus_specificity').reset_index(drop=True)
    return roc


def main() -> None:
    df = pd.read_csv(CORE_PATH)

    df['diag_label'] = df.apply(
        lambda r: label_diag_post_2ug(
            r['post_acth_cortisol_nmol_l'],
            r.get('post_acth_cortisol_qualifier', np.nan),
        ),
        axis=1,
    )

    clia = df.loc[df['urine_test_type'].eq('CLIApost')].copy()
    clia['urine_cortisol_nmol_l'] = pd.to_numeric(clia['urine_cortisol_nmol_l'], errors='coerce')

    d = clia[['urine_cortisol_nmol_l', 'diag_label']].dropna().copy()
    d['diag_label'] = d['diag_label'].astype(int)

    if d['diag_label'].nunique() < 2:
        raise RuntimeError('Need both HA and non-HA cases to compute ROC.')

    x = d['urine_cortisol_nmol_l'].to_numpy()
    y = d['diag_label'].to_numpy()

    roc = roc_for_lower_values_positive(x, y)
    auc = float(np.trapezoid(roc['tpr_sensitivity'], roc['fpr_1_minus_specificity']))

    finite = roc[np.isfinite(roc['threshold_nmol_l'])].copy()
    best = finite.sort_values(['youden_j', 'tpr_sensitivity', 'specificity'], ascending=[False, False, False]).iloc[0]

    best_threshold = float(best['threshold_nmol_l'])
    best_tpr = float(best['tpr_sensitivity'])
    best_fpr = float(best['fpr_1_minus_specificity'])
    best_spec = float(best['specificity'])

    y_pred_best = (x <= best_threshold).astype(int)
    tp, tn, fp, fn = confusion(y, y_pred_best)
    acc = float((tp + tn) / len(y))

    plt.figure(figsize=(7, 6))
    plt.plot(
        roc['fpr_1_minus_specificity'],
        roc['tpr_sensitivity'],
        color='#1f77b4',
        lw=2,
        label=f'CLIApost urine cortisol ROC (AUC={auc:.3f})',
    )
    plt.plot([0, 1], [0, 1], linestyle='--', color='#8c8c8c', lw=1.2, label='No-discrimination line')
    plt.scatter([best_fpr], [best_tpr], color='#d62728', zorder=3, label=f'Best Youden cutoff <= {best_threshold:.2f} nmol/L')

    plt.title('ROC: CLIApost Urine Cortisol for HA Diagnosis')
    plt.xlabel('1 - Specificity (False Positive Rate)')
    plt.ylabel('Sensitivity (True Positive Rate)')
    plt.xlim(0, 1)
    plt.ylim(0, 1)
    plt.grid(alpha=0.25)
    plt.legend(loc='lower right', frameon=True)
    plt.tight_layout()
    plt.savefig(OUT_PNG, dpi=300)
    plt.close()

    roc.to_csv(OUT_POINTS, index=False)

    summary = {
        'dataset': 'CLIApost only',
        'predictor': 'urine_cortisol_nmol_l',
        'outcome': 'HA diagnosis (post-ACTH <=2 ug/dL)',
        'n_total': int(len(d)),
        'n_ha': int((d['diag_label'] == 1).sum()),
        'n_nonha': int((d['diag_label'] == 0).sum()),
        'auc': auc,
        'best_youden_cutoff_rule': '<=',
        'best_youden_cutoff_nmol_l': best_threshold,
        'best_sensitivity': best_tpr,
        'best_specificity': best_spec,
        'best_accuracy': acc,
        'confusion_matrix': {'tp': tp, 'tn': tn, 'fp': fp, 'fn': fn},
        'outputs': {
            'roc_png': str(OUT_PNG),
            'roc_points_csv': str(OUT_POINTS),
            'summary_json': str(OUT_SUMMARY),
        },
    }
    OUT_SUMMARY.write_text(json.dumps(summary, indent=2))

    print(f'Wrote ROC figure: {OUT_PNG}')
    print(f'Wrote ROC points: {OUT_POINTS}')
    print(f'Wrote summary: {OUT_SUMMARY}')
    print(
        'Best cutoff <= '
        f'{best_threshold:.2f} nmol/L | Sens={best_tpr * 100:.1f}% '
        f'| Spec={best_spec * 100:.1f}% | Acc={acc * 100:.1f}% | AUC={auc:.3f}'
    )


if __name__ == '__main__':
    main()
