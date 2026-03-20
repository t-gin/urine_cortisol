from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path('/Users/tegin/Desktop/UCCR/raw_data')
INPUT_CSV = BASE / 'processed' / 'uccr_merged_standardized_full.csv'
OUT_CSV = BASE / 'processed' / 'outliers_for_chart_review.csv'
OUT_JSON = BASE / 'processed' / 'outliers_for_chart_review_summary.json'

# IQR multiplier used for outlier definition.
IQR_K = 1.5

# Metric -> grouping column for outlier bounds.
# Urine-derived values are grouped by urine assay.
# Serum-derived values are grouped by blood assay.
METRICS = {
    'urine_cortisol_nmol_l': 'urine_test_type',
    'urine_creatinine_mmol_l': 'urine_test_type',
    'uccr': 'urine_test_type',
    'baseline_cortisol_nmol_l': 'blood_test_type',
    'post_acth_cortisol_nmol_l': 'blood_test_type',
}


def iqr_bounds(series: pd.Series, k: float = IQR_K) -> tuple[float, float]:
    s = pd.to_numeric(series, errors='coerce').dropna()
    if s.empty:
        return np.nan, np.nan
    q1 = float(s.quantile(0.25))
    q3 = float(s.quantile(0.75))
    iqr = q3 - q1
    return q1 - k * iqr, q3 + k * iqr


def main() -> None:
    df = pd.read_csv(INPUT_CSV)

    # Keep only the columns useful for medical-record lookup and review.
    keep_cols = [
        'source_file',
        'source_sheet',
        'source_row',
        'case_number',
        'patient_name',
        'urine_test_site',
        'urine_test_type',
        'blood_test_site',
        'blood_test_type',
        'urine_cortisol_nmol_l',
        'urine_creatinine_mmol_l',
        'uccr',
        'baseline_cortisol_nmol_l',
        'post_acth_cortisol_nmol_l',
        'clinical_signs',
    ]

    work = df.copy()

    metric_summaries: dict[str, dict[str, object]] = {}
    flag_columns: list[str] = []

    for metric, grp_col in METRICS.items():
        if metric not in work.columns or grp_col not in work.columns:
            continue

        work[metric] = pd.to_numeric(work[metric], errors='coerce')
        flag_col = f'outlier_{metric}'
        low_col = f'{metric}_low_bound'
        high_col = f'{metric}_high_bound'

        work[flag_col] = False
        work[low_col] = np.nan
        work[high_col] = np.nan

        group_details = {}

        # Compute bounds within each assay group.
        for grp_val, idx in work.groupby(grp_col, dropna=False).groups.items():
            g = work.loc[idx, metric]
            lo, hi = iqr_bounds(g)
            work.loc[idx, low_col] = lo
            work.loc[idx, high_col] = hi
            if np.isfinite(lo) and np.isfinite(hi):
                work.loc[idx, flag_col] = (work.loc[idx, metric] < lo) | (work.loc[idx, metric] > hi)
            label = 'MISSING' if pd.isna(grp_val) else str(grp_val)
            group_details[label] = {
                'n_non_missing': int(pd.to_numeric(g, errors='coerce').notna().sum()),
                'low_bound': None if not np.isfinite(lo) else float(lo),
                'high_bound': None if not np.isfinite(hi) else float(hi),
                'n_outliers': int(work.loc[idx, flag_col].sum()),
            }

        metric_summaries[metric] = {
            'grouped_by': grp_col,
            'groups': group_details,
            'n_outliers_total': int(work[flag_col].sum()),
        }
        flag_columns.append(flag_col)

    if not flag_columns:
        raise RuntimeError('No outlier flag columns were created; check expected metric columns.')

    work['outlier_any'] = work[flag_columns].any(axis=1)

    def fields_flagged(row: pd.Series) -> str:
        fields = [
            c.replace('outlier_', '')
            for c in flag_columns
            if bool(row.get(c, False))
        ]
        return '; '.join(fields)

    work['outlier_fields'] = work.apply(fields_flagged, axis=1)

    out = work.loc[work['outlier_any']].copy()

    # Sort by patient and source row for easier chart lookup.
    out = out.sort_values(['patient_name', 'source_file', 'source_sheet', 'source_row'])

    out_cols = keep_cols + flag_columns + ['outlier_fields']
    out[out_cols].to_csv(OUT_CSV, index=False)

    # Example lookup requested by user.
    beau = work.loc[
        work['patient_name'].astype(str).str.contains('Beau Johanningsmeier', case=False, na=False),
        ['patient_name', 'source_file', 'source_sheet', 'source_row', 'outlier_any', 'outlier_fields'],
    ]

    summary = {
        'input_rows': int(len(work)),
        'output_outlier_rows': int(len(out)),
        'iqr_multiplier': IQR_K,
        'metric_summaries': metric_summaries,
        'beau_lookup': beau.to_dict(orient='records'),
        'outputs': {
            'outlier_csv': str(OUT_CSV),
            'summary_json': str(OUT_JSON),
        },
    }

    OUT_JSON.write_text(json.dumps(summary, indent=2))

    print(f'Wrote outlier pull: {OUT_CSV}')
    print(f'Wrote summary: {OUT_JSON}')
    print(f'Outlier rows: {len(out)} / {len(work)}')
    if len(beau) > 0:
        b = beau.iloc[0]
        print(
            'Beau Johanningsmeier -> '
            f"source={b['source_file']}:{b['source_sheet']}:{int(b['source_row'])}, "
            f"outlier_any={bool(b['outlier_any'])}, fields={b['outlier_fields']}"
        )


if __name__ == '__main__':
    main()
