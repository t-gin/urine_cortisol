from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd


CORTISOL_UGDL_TO_NMOLL = 27.59
CREATININE_MGDL_TO_MMOLL = 0.0884


def parse_value_and_qualifier(value: object) -> tuple[float, str | None]:
    if pd.isna(value):
        return np.nan, None

    text = str(value).strip()
    if text == "" or text.lower() in {"nan", "none"}:
        return np.nan, None

    text = text.replace(",", "")
    text = re.sub(r"^(pre|post)\s*", "", text, flags=re.IGNORECASE)

    qualifier_match = re.match(r"^(<=|>=|<|>)\s*(.*)$", text)
    qualifier = None
    if qualifier_match:
        qualifier = qualifier_match.group(1)
        text = qualifier_match.group(2).strip()

    numeric_match = re.search(r"[-+]?\d*\.?\d+", text)
    if not numeric_match:
        return np.nan, qualifier

    return float(numeric_match.group(0)), qualifier


def extract_numeric_series(series: pd.Series) -> tuple[pd.Series, pd.Series]:
    parsed = series.apply(parse_value_and_qualifier)
    values = parsed.apply(lambda x: x[0]).astype(float)
    qualifiers = parsed.apply(lambda x: x[1])
    return values, qualifiers


def parse_age_years(value: object) -> float:
    if pd.isna(value):
        return np.nan

    text = str(value).strip().lower()
    if text == "" or text in {"nan", "none"}:
        return np.nan

    numeric_match = re.search(r"[-+]?\d*\.?\d+", text)
    if not numeric_match:
        return np.nan

    age_value = float(numeric_match.group(0))

    if "mo" in text or "month" in text:
        return age_value / 12.0

    return age_value


def extract_age_years(series: pd.Series) -> pd.Series:
    return series.apply(parse_age_years).astype(float)


def clean_text_value(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text == "" or text.lower() in {"nan", "none"}:
        return ""
    return text


def combine_text_columns(df: pd.DataFrame, columns: list[str]) -> pd.Series:
    existing_columns = [column for column in columns if column in df.columns]
    if not existing_columns:
        return pd.Series(["" for _ in range(len(df))], index=df.index)

    def combine_row(row: pd.Series) -> str:
        parts: list[str] = []
        for column in existing_columns:
            text = clean_text_value(row[column])
            if text != "":
                parts.append(text)
        return " | ".join(parts)

    return df[existing_columns].apply(combine_row, axis=1)


def filter_valid_patient_rows(df: pd.DataFrame) -> pd.DataFrame:
    valid_name = df["patient_name"].fillna("").astype(str).str.strip().ne("")
    valid_sex = df["sex"].fillna("").astype(str).str.contains(r"[A-Za-z]", regex=True)
    return df[valid_name & valid_sex].reset_index(drop=True)


def normalize_column_name(name: object) -> str:
    return re.sub(r"\s+", " ", str(name).strip().lower())


def find_column(df: pd.DataFrame, aliases: list[str]) -> str | None:
    normalized = {normalize_column_name(c): c for c in df.columns}
    for alias in aliases:
        if alias in normalized:
            return normalized[alias]
    return None


def standardize_cases_new(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name="Sheet1")

    urine_cort_raw, urine_cort_q = extract_numeric_series(df["Urine Cortisol"])
    urine_creat_raw, urine_creat_q = extract_numeric_series(df["Urine Creatinine"])
    uccr_raw, uccr_q = extract_numeric_series(df["UCCR"])
    baseline_raw, baseline_q = extract_numeric_series(df["Baseline Cortisol"])
    post_raw, post_q = extract_numeric_series(df["Post-ACTH Cortisol"])
    clinical_signs = combine_text_columns(df, ["Presenting Complaint", "Other"])

    out = pd.DataFrame(
        {
            "source_file": "UCCR_cases_new.xlsx",
            "source_sheet": "Sheet1",
            "source_row": np.arange(2, len(df) + 2),
            "case_number": pd.NA,
            "patient_name": df["Name"],
            "age_years": extract_age_years(df["Age"]),
            "sex": df["Sex"],
            "clinical_signs": clinical_signs,
            "breed": df["Breed"],
            "urine_cortisol_nmol_l": urine_cort_raw * CORTISOL_UGDL_TO_NMOLL,
            "urine_cortisol_qualifier": urine_cort_q,
            "urine_creatinine_mmol_l": urine_creat_raw * CREATININE_MGDL_TO_MMOLL,
            "urine_creatinine_qualifier": urine_creat_q,
            "uccr_reported": uccr_raw,
            "uccr_reported_qualifier": uccr_q,
            "baseline_cortisol_nmol_l": baseline_raw * CORTISOL_UGDL_TO_NMOLL,
            "baseline_cortisol_qualifier": baseline_q,
            "post_acth_cortisol_nmol_l": post_raw * CORTISOL_UGDL_TO_NMOLL,
            "post_acth_cortisol_qualifier": post_q,
        }
    )
    return out


def standardize_rawdata(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name="Final Combined Group")

    cort_nmol, cort_nmol_q = extract_numeric_series(df["Urine Cortisol (nMOL/L)"])
    cort_ugdl, cort_ugdl_q = extract_numeric_series(df["Urine Cortisol (UG/DL)"])
    creat_mmol, creat_mmol_q = extract_numeric_series(df["Urine Creat (MMOL/L)"])
    creat_mgdl, creat_mgdl_q = extract_numeric_series(df["Urine Creatinine (mg/DL)"])
    uccr_raw, uccr_q = extract_numeric_series(df["UC:CR"])
    pre_raw, pre_q = extract_numeric_series(df["ACTH Pre (UG/DL)"])
    post_raw, post_q = extract_numeric_series(df["ACTH POST (UG/DL)"])
    clinical_signs = combine_text_columns(
        df,
        [
            "Indication for testing",
            "Alternate ddx",
            "Clinical signs",
            "Concurrent Diseases",
            "Comments",
            "Results",
        ],
    )

    urine_cortisol_nmol_l = cort_nmol.copy()
    urine_cortisol_nmol_l = urine_cortisol_nmol_l.fillna(cort_ugdl * CORTISOL_UGDL_TO_NMOLL)
    urine_cortisol_qualifier = cort_nmol_q.where(~cort_nmol.isna(), cort_ugdl_q)

    urine_creatinine_mmol_l = creat_mmol.copy()
    urine_creatinine_mmol_l = urine_creatinine_mmol_l.fillna(creat_mgdl * CREATININE_MGDL_TO_MMOLL)
    urine_creatinine_qualifier = creat_mmol_q.where(~creat_mmol.isna(), creat_mgdl_q)

    out = pd.DataFrame(
        {
            "source_file": "UCCR_rawdata.xlsx",
            "source_sheet": "Final Combined Group",
            "source_row": np.arange(2, len(df) + 2),
            "case_number": df["Case Number"],
            "patient_name": df["Patient Name"],
            "age_years": pd.to_numeric(df["Age (yrs)"], errors="coerce"),
            "sex": df["Sex"],
            "clinical_signs": clinical_signs,
            "breed": df["Breed"],
            "urine_cortisol_nmol_l": urine_cortisol_nmol_l,
            "urine_cortisol_qualifier": urine_cortisol_qualifier,
            "urine_creatinine_mmol_l": urine_creatinine_mmol_l,
            "urine_creatinine_qualifier": urine_creatinine_qualifier,
            "uccr_reported": uccr_raw,
            "uccr_reported_qualifier": uccr_q,
            "baseline_cortisol_nmol_l": pre_raw * CORTISOL_UGDL_TO_NMOLL,
            "baseline_cortisol_qualifier": pre_q,
            "post_acth_cortisol_nmol_l": post_raw * CORTISOL_UGDL_TO_NMOLL,
            "post_acth_cortisol_qualifier": post_q,
        }
    )
    return filter_valid_patient_rows(out)


def standardize_ha_round2(path: Path) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []

    for sheet_name in ["Cases", "Controls"]:
        df = pd.read_excel(path, sheet_name=sheet_name, header=1)
        df = df.dropna(how="all")

        case_col = find_column(df, ["mrn"])
        name_col = find_column(df, ["name"])
        age_col = find_column(df, ["age"])
        sex_col = find_column(df, ["sex"])
        breed_col = find_column(df, ["breed"])
        urine_cort_col = find_column(df, ["urine cort"])
        urine_creat_col = find_column(df, ["urine creat"])
        uccr_col = find_column(df, ["uccr"])
        baseline_col = find_column(df, ["baseline cort", "baseline cortisol"])
        post_col = find_column(df, ["post-cort", "post cort", "post cortisol"])

        urine_cort_raw, urine_cort_q = extract_numeric_series(df[urine_cort_col])
        urine_creat_raw, urine_creat_q = extract_numeric_series(df[urine_creat_col])
        uccr_raw, uccr_q = extract_numeric_series(df[uccr_col])
        baseline_raw, baseline_q = extract_numeric_series(df[baseline_col])
        post_raw, post_q = extract_numeric_series(df[post_col])
        clinical_signs_col = find_column(df, ["clinical signs", "presenting complaint"])
        indication_col = find_column(df, ["indication for testing"])
        alternate_ddx_col = find_column(df, ["alt ddx", "alternate ddx"])
        clinical_columns = [
            column
            for column in [clinical_signs_col, indication_col, alternate_ddx_col]
            if column is not None
        ]
        clinical_signs = combine_text_columns(df, clinical_columns)

        out = pd.DataFrame(
            {
                "source_file": "UCCR for HA round 2.xlsx",
                "source_sheet": sheet_name,
                "source_row": np.arange(3, len(df) + 3),
                "case_number": df[case_col],
                "patient_name": df[name_col],
                "age_years": extract_age_years(df[age_col]),
                "sex": df[sex_col],
                "clinical_signs": clinical_signs,
                "breed": df[breed_col],
                "urine_cortisol_nmol_l": urine_cort_raw,
                "urine_cortisol_qualifier": urine_cort_q,
                "urine_creatinine_mmol_l": urine_creat_raw,
                "urine_creatinine_qualifier": urine_creat_q,
                "uccr_reported": uccr_raw,
                "uccr_reported_qualifier": uccr_q,
                "baseline_cortisol_nmol_l": baseline_raw,
                "baseline_cortisol_qualifier": baseline_q,
                "post_acth_cortisol_nmol_l": post_raw,
                "post_acth_cortisol_qualifier": post_q,
            }
        )
        frames.append(filter_valid_patient_rows(out))

    return pd.concat(frames, ignore_index=True)


def main() -> None:
    base = Path(__file__).resolve().parent
    out_dir = base / "processed"
    out_dir.mkdir(exist_ok=True)

    cases_new = standardize_cases_new(base / "UCCR_cases_new.xlsx")
    rawdata = standardize_rawdata(base / "UCCR_rawdata.xlsx")
    ha_round2 = standardize_ha_round2(base / "UCCR for HA round 2.xlsx")

    merged = pd.concat([cases_new, rawdata, ha_round2], ignore_index=True)

    merged["uccr_calculated"] = (
        merged["urine_cortisol_nmol_l"] / merged["urine_creatinine_mmol_l"]
    )

    dedup_subset = [
        "source_file",
        "source_sheet",
        "case_number",
        "patient_name",
        "urine_cortisol_nmol_l",
        "urine_creatinine_mmol_l",
        "baseline_cortisol_nmol_l",
        "post_acth_cortisol_nmol_l",
    ]
    merged_clean = merged.drop_duplicates(subset=dedup_subset, keep="first").reset_index(drop=True)

    test_mapping = {
        "UCCR_rawdata.xlsx": {
            "urine_test_site": "MSU",
            "urine_test_type": "RIA",
            "blood_test_site": "NCSU",
            "blood_test_type": "CLIApre",
        },
        "UCCR_cases_new.xlsx": {
            "urine_test_site": "NCSU",
            "urine_test_type": "CLIApost",
            "blood_test_site": "NCSU",
            "blood_test_type": "CLIApost",
        },
        "UCCR for HA round 2.xlsx": {
            "urine_test_site": "MSU",
            "urine_test_type": "CLIApost",
            "blood_test_site": "MSU",
            "blood_test_type": "CLIApost",
        },
    }

    merged_clean["urine_test_site"] = merged_clean["source_file"].map(
        lambda source: test_mapping.get(source, {}).get("urine_test_site", "")
    )
    merged_clean["urine_test_type"] = merged_clean["source_file"].map(
        lambda source: test_mapping.get(source, {}).get("urine_test_type", "")
    )
    merged_clean["blood_test_site"] = merged_clean["source_file"].map(
        lambda source: test_mapping.get(source, {}).get("blood_test_site", "")
    )
    merged_clean["blood_test_type"] = merged_clean["source_file"].map(
        lambda source: test_mapping.get(source, {}).get("blood_test_type", "")
    )

    merged_clean["uccr"] = merged_clean["uccr_reported"].fillna(merged_clean["uccr_calculated"])
    merged_clean["uccr_qualifier"] = merged_clean["uccr_reported_qualifier"]

    merged_clean.to_csv(out_dir / "uccr_merged_standardized_full.csv", index=False)

    merged_core = merged_clean[
        [
            "patient_name",
            "age_years",
            "sex",
            "clinical_signs",
            "urine_test_site",
            "urine_test_type",
            "blood_test_site",
            "blood_test_type",
            "urine_cortisol_nmol_l",
            "urine_cortisol_qualifier",
            "urine_creatinine_mmol_l",
            "urine_creatinine_qualifier",
            "uccr",
            "uccr_qualifier",
            "baseline_cortisol_nmol_l",
            "baseline_cortisol_qualifier",
            "post_acth_cortisol_nmol_l",
            "post_acth_cortisol_qualifier",
        ]
    ].rename(
        columns={
            "baseline_cortisol_nmol_l": "pre_acth_baseline_cortisol_nmol_l",
            "baseline_cortisol_qualifier": "pre_acth_baseline_cortisol_qualifier",
        }
    )

    merged_core.to_csv(out_dir / "uccr_merged_standardized.csv", index=False)

    audit = pd.DataFrame(
        [
            {
                "source_file": "UCCR_cases_new.xlsx",
                "source_sheet": "Sheet1",
                "rows_output": len(cases_new),
                "urine_cortisol_conversion": "ug/dL -> nmol/L",
                "urine_creatinine_conversion": "mg/dL -> mmol/L",
                "blood_cortisol_conversion": "ug/dL -> nmol/L",
            },
            {
                "source_file": "UCCR_rawdata.xlsx",
                "source_sheet": "Final Combined Group (only)",
                "rows_output": len(rawdata),
                "urine_cortisol_conversion": "nMOL/L preferred; UG/DL fallback -> nmol/L",
                "urine_creatinine_conversion": "MMOL/L preferred; mg/dL fallback -> mmol/L",
                "blood_cortisol_conversion": "ACTH Pre/Post UG/DL -> nmol/L",
            },
            {
                "source_file": "UCCR for HA round 2.xlsx",
                "source_sheet": "Cases + Controls",
                "rows_output": len(ha_round2),
                "urine_cortisol_conversion": "assumed already nmol/L (no conversion)",
                "urine_creatinine_conversion": "assumed already mmol/L (no conversion)",
                "blood_cortisol_conversion": "assumed already nmol/L (no conversion)",
            },
            {
                "source_file": "ALL",
                "source_sheet": "ALL",
                "rows_output": len(merged_clean),
                "urine_cortisol_conversion": "target unit: nmol/L",
                "urine_creatinine_conversion": "target unit: mmol/L",
                "blood_cortisol_conversion": "target unit: nmol/L",
            },
        ]
    )
    audit.to_csv(out_dir / "uccr_conversion_audit.csv", index=False)

    print(f"Wrote: {out_dir / 'uccr_merged_standardized.csv'}")
    print(f"Wrote: {out_dir / 'uccr_merged_standardized_full.csv'}")
    print(f"Wrote: {out_dir / 'uccr_conversion_audit.csv'}")
    print(f"Rows in merged standardized dataset: {len(merged_clean)}")


if __name__ == "__main__":
    main()
