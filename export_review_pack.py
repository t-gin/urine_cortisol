import pandas as pd
from pathlib import Path

base = Path('/Users/tegin/Desktop/UCCR/raw_data')
processed = base / 'processed'
merged_core_path = processed / 'uccr_merged_standardized.csv'
merged_full_path = processed / 'uccr_merged_standardized_full.csv'
audit_path = processed / 'uccr_conversion_audit.csv'
out_path = processed / 'uccr_review_pack.xlsx'

merged_core = pd.read_csv(merged_core_path)
merged_full = pd.read_csv(merged_full_path)
audit = pd.read_csv(audit_path)

core_dictionary_rows = [
    {'column': 'patient_name', 'description': 'Patient name.'},
    {'column': 'age_years', 'description': 'Age in years.'},
    {'column': 'sex', 'description': 'Sex code from source data.'},
    {'column': 'clinical_signs', 'description': 'Combined clinical text from source columns (e.g., indication for testing, presenting complaint, alternate ddx, comments).'},
    {'column': 'urine_test_site', 'description': 'Urine testing site assigned by source workbook.'},
    {'column': 'urine_test_type', 'description': 'Urine testing method assigned by source workbook.'},
    {'column': 'blood_test_site', 'description': 'Blood testing site assigned by source workbook.'},
    {'column': 'blood_test_type', 'description': 'Blood testing method assigned by source workbook.'},
    {'column': 'urine_cortisol_nmol_l', 'description': 'Urine cortisol standardized to nmol/L.'},
    {'column': 'urine_cortisol_qualifier', 'description': 'Qualifier attached to urine cortisol when present (<, >, <=, >=).'},
    {'column': 'urine_creatinine_mmol_l', 'description': 'Urine creatinine standardized to mmol/L.'},
    {'column': 'urine_creatinine_qualifier', 'description': 'Qualifier attached to urine creatinine when present (<, >, <=, >=).'},
    {'column': 'uccr', 'description': 'UCCR value (reported UCCR when present, otherwise calculated cortisol/creatinine ratio).'},
    {'column': 'uccr_qualifier', 'description': 'Qualifier attached to reported UCCR when present (<, >, <=, >=).'},
    {'column': 'pre_acth_baseline_cortisol_nmol_l', 'description': 'Pre-ACTH (baseline) cortisol standardized to nmol/L.'},
    {'column': 'pre_acth_baseline_cortisol_qualifier', 'description': 'Qualifier attached to baseline cortisol when present (<, >, <=, >=).'},
    {'column': 'post_acth_cortisol_nmol_l', 'description': 'Post-ACTH cortisol standardized to nmol/L.'},
    {'column': 'post_acth_cortisol_qualifier', 'description': 'Qualifier attached to post-ACTH cortisol when present (<, >, <=, >=).'},
]

full_dictionary_rows = [
    {'column': 'source_file', 'description': 'Original workbook filename.'},
    {'column': 'source_sheet', 'description': 'Original worksheet name.'},
    {'column': 'source_row', 'description': 'Row number in source sheet (1-based Excel indexing).'},
    {'column': 'case_number', 'description': 'Case/MRN identifier where available.'},
    {'column': 'patient_name', 'description': 'Patient name.'},
    {'column': 'age_years', 'description': 'Age in years.'},
    {'column': 'sex', 'description': 'Sex code from source data.'},
    {'column': 'clinical_signs', 'description': 'Combined clinical text from source columns.'},
    {'column': 'urine_test_site', 'description': 'Urine testing site assigned by source workbook.'},
    {'column': 'urine_test_type', 'description': 'Urine testing method assigned by source workbook.'},
    {'column': 'blood_test_site', 'description': 'Blood testing site assigned by source workbook.'},
    {'column': 'blood_test_type', 'description': 'Blood testing method assigned by source workbook.'},
    {'column': 'breed', 'description': 'Breed from source data.'},
    {'column': 'urine_cortisol_nmol_l', 'description': 'Urine cortisol standardized to nmol/L.'},
    {'column': 'urine_cortisol_qualifier', 'description': 'Qualifier from source value (<, >, <=, >=) when present.'},
    {'column': 'urine_creatinine_mmol_l', 'description': 'Urine creatinine standardized to mmol/L.'},
    {'column': 'urine_creatinine_qualifier', 'description': 'Qualifier from source value (<, >, <=, >=) when present.'},
    {'column': 'uccr_reported', 'description': 'Reported UCCR from source file, parsed as numeric.'},
    {'column': 'uccr_reported_qualifier', 'description': 'Qualifier attached to reported UCCR when present.'},
    {'column': 'baseline_cortisol_nmol_l', 'description': 'Baseline/Pre-ACTH cortisol standardized to nmol/L.'},
    {'column': 'baseline_cortisol_qualifier', 'description': 'Qualifier attached to baseline cortisol when present.'},
    {'column': 'post_acth_cortisol_nmol_l', 'description': 'Post-ACTH cortisol standardized to nmol/L.'},
    {'column': 'post_acth_cortisol_qualifier', 'description': 'Qualifier attached to post-ACTH cortisol when present.'},
    {'column': 'uccr_calculated', 'description': 'Calculated UCCR = urine_cortisol_nmol_l / urine_creatinine_mmol_l.'},
]

core_data_dictionary = pd.DataFrame(core_dictionary_rows)
full_data_dictionary = pd.DataFrame(full_dictionary_rows)

with pd.ExcelWriter(out_path, engine='openpyxl') as writer:
    merged_core.to_excel(writer, sheet_name='merged_core', index=False)
    merged_full.to_excel(writer, sheet_name='merged_full', index=False)
    audit.to_excel(writer, sheet_name='conversion_audit', index=False)
    core_data_dictionary.to_excel(writer, sheet_name='dictionary_core', index=False)
    full_data_dictionary.to_excel(writer, sheet_name='dictionary_full', index=False)

print(f'Wrote: {out_path}')
print('Sheets: merged_core, merged_full, conversion_audit, dictionary_core, dictionary_full')
