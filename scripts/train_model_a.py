"""Phase 6 - Model A: 구매 비활성 위험 예측 (PROJECT_GUIDELINES.md 18, 20~22번).

시간순 분할(snapshot_date 기준): Train 6개(07-21~09-29) / Val 1개(10-13) /
Test 2개(10-27, 11-10). 근거는 reports/phase6_model_a_results.md 참고.

기준선(무작위/전체평균/최근성/빈도/라이프사이클) -> 로지스틱 회귀 -> LightGBM
순으로 비교한다 (PROJECT_GUIDELINES.md 20번 "복잡한 모델이 단순 규칙보다 나은지 확인").
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import lightgbm as lgb
import numpy as np
import pandas as pd
import yaml
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.models.baselines import (
    frequency_churn_score,
    lifecycle_tier_churn_score,
    overall_rate_score,
    random_score,
    recency_churn_score,
)
from src.models.metrics import full_evaluation

CONFIG_PATH = Path("config/paths.yaml")
REPORT_DIR = Path("reports")

TRAIN_SNAPSHOTS = ["2022-07-21", "2022-08-04", "2022-08-18", "2022-09-01", "2022-09-15", "2022-09-29"]
VAL_SNAPSHOTS = ["2022-10-13"]
TEST_SNAPSHOTS = ["2022-10-27", "2022-11-10"]

FEATURE_COLS = [
    "days_since_last_purchase",
    "n_purchase_occasions_so_far",
    "n_purchase_days_so_far",
    "avg_purchase_gap_days_so_far",
    "n_purchases_7d",
    "n_purchases_14d",
    "n_purchases_28d",
    "n_categories_so_far",
    "avg_category_repurchase_rate",
    "n_page_visit_28d",
    "n_search_query_28d",
    "n_add_to_cart_28d",
    "n_remove_from_cart_28d",
]


def load_data(con) -> pd.DataFrame:
    return con.sql("SELECT * FROM mart_churn_target").df()


def split_data(df: pd.DataFrame):
    df = df.copy()
    df["snapshot_date_str"] = df["snapshot_date"].astype(str)
    train = df[df["snapshot_date_str"].isin(TRAIN_SNAPSHOTS)]
    val = df[df["snapshot_date_str"].isin(VAL_SNAPSHOTS)]
    test = df[df["snapshot_date_str"].isin(TEST_SNAPSHOTS)]
    assert len(train) + len(val) + len(test) == len(df), "분할 후 행 수 합이 원본과 다름 — 날짜 매칭 오류"
    return train, val, test


def prepare_lr_features(train, val, test):
    gap_median = train["avg_purchase_gap_days_so_far"].median()
    cat_rate_median = train["avg_category_repurchase_rate"].median()

    def transform(d):
        d = d.copy()
        d["avg_gap_missing"] = d["avg_purchase_gap_days_so_far"].isna().astype(int)
        d["avg_purchase_gap_days_so_far"] = d["avg_purchase_gap_days_so_far"].fillna(gap_median)
        d["avg_category_repurchase_rate_missing"] = d["avg_category_repurchase_rate"].isna().astype(int)
        d["avg_category_repurchase_rate"] = d["avg_category_repurchase_rate"].fillna(cat_rate_median)
        return d

    train_t, val_t, test_t = transform(train), transform(val), transform(test)
    cols = FEATURE_COLS + ["avg_gap_missing", "avg_category_repurchase_rate_missing"]

    scaler = StandardScaler()
    X_train = scaler.fit_transform(train_t[cols])
    X_val = scaler.transform(val_t[cols])
    X_test = scaler.transform(test_t[cols])
    return X_train, X_val, X_test


def run_for_label(con, df: pd.DataFrame, label_col: str) -> list[dict]:
    train, val, test = split_data(df)
    y_train = train[label_col].values
    y_val = val[label_col].values
    y_test = test[label_col].values
    train_rate = y_train.mean()

    results = []

    def record(method, split_name, y_true, y_score):
        m = full_evaluation(y_true, y_score)
        m["method"] = method
        m["split"] = split_name
        m["label"] = label_col
        results.append(m)

    # --- 기준선 ---
    for split_name, d, y in [("val", val, y_val), ("test", test, y_test)]:
        record("무작위", split_name, y, random_score(len(y)))
        record("전체_평균", split_name, y, overall_rate_score(len(y), train_rate))
        record("최근성_규칙", split_name, y, recency_churn_score(d["days_since_last_purchase"]))
        record("구매빈도_규칙", split_name, y, frequency_churn_score(d["n_purchases_28d"]))
        record("라이프사이클_규칙", split_name, y, lifecycle_tier_churn_score(d["days_since_last_purchase"]))

    # --- 로지스틱 회귀 ---
    X_train, X_val, X_test = prepare_lr_features(train, val, test)
    lr = LogisticRegression(max_iter=1000)
    lr.fit(X_train, y_train)
    record("로지스틱_회귀", "val", y_val, lr.predict_proba(X_val)[:, 1])
    record("로지스틱_회귀", "test", y_test, lr.predict_proba(X_test)[:, 1])

    # --- LightGBM ---
    train_ds = lgb.Dataset(train[FEATURE_COLS], label=y_train)
    val_ds = lgb.Dataset(val[FEATURE_COLS], label=y_val, reference=train_ds)
    gbm = lgb.train(
        params={
            "objective": "binary",
            "metric": "auc",
            "verbosity": -1,
            "seed": 42,
        },
        train_set=train_ds,
        num_boost_round=500,
        valid_sets=[val_ds],
        callbacks=[lgb.early_stopping(30, verbose=False)],
    )
    record("LightGBM", "val", y_val, gbm.predict(val[FEATURE_COLS]))
    record("LightGBM", "test", y_test, gbm.predict(test[FEATURE_COLS]))

    return results, gbm, lr


def main():
    with open(CONFIG_PATH) as f:
        paths = yaml.safe_load(f)
    con = duckdb.connect(str(paths["database_path"]), read_only=True)

    df = load_data(con)
    print(f"전체 행 수: {len(df):,}")

    all_results = []
    for label_col in ["churn_14d", "churn_28d"]:
        print(f"\n{'=' * 80}\n{label_col}\n{'=' * 80}")
        results, gbm, lr = run_for_label(con, df, label_col)
        all_results.extend(results)
        for r in results:
            print(
                f"[{r['split']}] {r['method']:14s} AUC={r['roc_auc']:.4f} "
                f"PR-AUC={r['pr_auc']:.4f} Lift@10%={r['lift_at_10pct']:.2f} "
                f"Precision@10%={r['precision_at_10pct']:.4f}"
            )
        if label_col == "churn_14d":
            importances = pd.DataFrame(
                {"feature": FEATURE_COLS, "importance": gbm.feature_importance(importance_type="gain")}
            ).sort_values("importance", ascending=False)
            print("\nLightGBM feature importance (gain):")
            print(importances.to_string(index=False))
            importances.to_csv(REPORT_DIR / "phase6_model_a_feature_importance.csv", index=False)

    result_df = pd.DataFrame(all_results)
    ordered_cols = ["label", "split", "method", "n", "actual_positive_rate", "roc_auc", "pr_auc",
                     "log_loss", "brier_score",
                     "precision_at_5pct", "recall_at_5pct", "lift_at_5pct",
                     "precision_at_10pct", "recall_at_10pct", "lift_at_10pct",
                     "precision_at_20pct", "recall_at_20pct", "lift_at_20pct"]
    result_df = result_df[ordered_cols]
    REPORT_DIR.mkdir(exist_ok=True)
    result_df.to_csv(REPORT_DIR / "phase6_model_a_results.csv", index=False)
    print(f"\nSaved: {REPORT_DIR / 'phase6_model_a_results.csv'}")


if __name__ == "__main__":
    main()
