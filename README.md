# UCCR Comparison Summary (Moya et al. 2022 vs Current Dataset)

This README summarizes how our current processed dataset compares with the study by Moya et al. (2022).

## Assay Naming Note

In Moya et al. (2022), when `CLIA` is referenced, interpret it here as `CLIApre`.

In our dataset, urine assay groups are:
- `CLIApost`
- `RIA`

## Study/Analysis Setup Comparison

| Parameter | Moya et al. (2022) | Current Dataset (This Workspace) |
|---|---|---|
| Number of dogs used | 148 total (41 HA, 107 NAI) | 330 total merged rows; 306 usable for HA diagnosis analysis (44 HA, 262 non-HA) |
| Inclusion criteria | Dogs tested for HA via basal cortisol or ACTH stimulation; no age/breed/sex restrictions | Merged from 3 workbooks; `UCCR_rawdata` restricted to `Final Combined Group`; data-quality filters and deduplication applied |
| Exclusion criteria | Hyperadrenocorticism; recent glucocorticoids/azole antifungals; equivocal status | Medication-history exclusions not available in source files; only data-quality exclusions applied |
| Serum cutoff to diagnose HA | Pre and post ACTH cortisol <=55 nmol/L (2 ug/dL) | Primary diagnostic analysis in this workflow used post-ACTH cortisol <=55.18 nmol/L (2 ug/dL) |
| Serum cutoff to exclude HA | Basal >55 nmol/L OR post-ACTH >138 nmol/L | Comparison run used basal >55.18 nmol/L OR post-ACTH >55.18 nmol/L (2 ug/dL) |

## UCCR Medians (IQR) by Assay

| Assay/Protocol | HA median (IQR) | Non-HA median (IQR) |
|---|---|---|
| Moya RIA | 0 (0 to 0) | 22 (7 to 47.3) |
| Current RIA | 0.0 (0.0 to 1.0) | 22.0 (13.0 to 42.5) |
| Moya CLIA (=CLIApre) | 1 (0 to 1.3) | 71 (30 to 127) |
| Current CLIApost | 0.5 (0.0 to 1.8225) | 19.88 (10.615 to 45.92) |

## Urine Cortisol Medians (nmol/L)

| Assay/Protocol | Median (IQR) |
|---|---|
| Moya CLIA (=CLIApre) | 433 (98 to >1380) |
| Current CLIApost | 160.02 (30.35 to 514.55) |
| Moya RIA | 85 (5 to 476) |
| Current RIA | 200 (93 to 459) |

## Optimal UCCR Cutpoints for HA Diagnosis

Using current workflow diagnostic definition: post-ACTH <=2 ug/dL.

| Assay/Protocol | Optimal cutpoint | Sensitivity | Specificity |
|---|---|---|---|
| Moya CLIA (=CLIApre) | <=10 | 100% | 100% |
| Current CLIApost | <=4.6 | 96.9% | 93.7% |
| Moya RIA | <=2 | 97.2% | 93.6% |
| Current RIA | <=3.0 | 91.7% | 99.4% |

## Optimal UCCR Cutpoints for HA Exclusion

Using exclusion definition: baseline >2 ug/dL OR post-ACTH >2 ug/dL.

| Assay/Protocol | Optimal cutpoint | Sensitivity | Specificity |
|---|---|---|---|
| Current CLIApost | >=4.83 | 94.7% | 86.5% |
| Current RIA | >=4.0 | 99.4% | 91.7% |

## Overall Interpretation Across the Moya Comparison Workbook

1. Overall discrimination is high across assay/outcome/scenario combinations, with ROC AUCs spanning approximately 0.94 to 0.99.
2. For HA diagnosis, top-performing cutoffs are stable across scenarios: UCCR CLIApost <=4.6, UCCR RIA <=3.0, urine cortisol CLIApost <=27.59, and urine cortisol RIA <=55.00.
3. For HA exclusion, RIA retains strong and stable specificity (UCCR >=4.0 with 91.7% specificity; urine cortisol >=58.00 with 100.0% specificity).
4. Applying additional-condition exclusions (missing post-ACTH plus low basal) mainly improves CLIApost exclusion specificity while preserving sensitivity.
5. No group reaches 100% overall accuracy; some groups achieve isolated 100% sensitivity or 100% specificity cutoffs, so threshold choice should follow whether rule-out or rule-in performance is prioritized.
6. Compared with Moya, the current dataset is larger and supports robust stratified interpretation by assay type (CLIApost vs RIA).

## Data Sources in This Workspace

- `processed/uccr_merged_standardized.csv`
- `processed/uccr_merged_standardized_full.csv`
- `processed/uccr_review_pack.xlsx`
