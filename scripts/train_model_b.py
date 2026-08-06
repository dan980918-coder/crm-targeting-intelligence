"""Phase 6 - Model B: 향후 구매 가능성 예측 (CLAUDE.md 19, 20~22번).

mart_purchase_propensity 사용 — Model A(mart_churn_target)보다 넓은 모집단
(구매 이력 없는 고관여 탐색/장바구니 고객 포함). "구매함"이 소수 클래스라
Model A와 반대로 Lift@K가 더 유의미하게 나올 것으로 기대(보고서에서 비교).

시간순 분할은 Model A와 동일한 snapshot_date 기준(Train 6/Val 1/Test 2).
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
    frequency_propensity_score,
    overall_rate_score,
    random_score,
    recency_propensity_score,
    visit_propensity_score,
)
from src.models.metrics import full_evaluation

CONFIG_PATH = Path("config/paths.yaml")
REPORT_DIR = Path("reports")

TRAIN_SNAPSHOTS = ["2022-07-21", "2022-08-04", "2022-08-18", "2022-09-01", "2022-09-15", "2022-09-29"]
VAL_SNAPSHOTS = ["2022-10-13"]
TEST_SNAPSHOTS = ["2022-10-27", "2022-11-10"]

FEATURE_COLS = [
    "has_purchase_history",
    "days_since_last_purchase",
    "n_purchase_occasions_so_far",
    "n_page_visit_28d",
    "n_search_query_28d",
    "n_add_to_cart_28d",
    "n_remove_from_cart_28d",
]


def split_data(df: pd.DataFrame):
    df = df.copy()
    df["snapshot_date_str"] = df["snapshot_date"].astype(str)
    train = df[df["snapshot_date_str"].isin(TRAIN_SNAPSHOTS)]
    val = df[df["snapshot_date_str"].isin(VAL_SNAPSHOTS)]
    test = df[df["snapshot_date_str"].isin(TEST_SNAPSHOTS)]
    assert len(train) + len(val) + len(test) == len(df)
    return train, val, test


def prepare_lr_features(train, val, test):
    imputer_median = train["days_since_last_purchase"].median()

    def transform(d):
        d = d.copy()
        d["has_purchase_history"] = d["has_purchase_history"].astype(int)
        d["days_since_last_purchase"] = d["days_since_last_purchase"].fillna(imputer_median)
        return d

    train_t, val_t, test_t = transform(train), transform(val), transform(test)
    scaler = StandardScaler()
    X_train = scaler.fit_transform(train_t[FEATURE_COLS])
    X_val = scaler.transform(val_t[FEATURE_COLS])
    X_test = scaler.transform(test_t[FEATURE_COLS])
    return X_train, X_val, X_test


def run_for_label(df: pd.DataFrame, label_col: str):
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

    for split_name, d, y in [("val", val, y_val), ("test", test, y_test)]:
        record("무작위", split_name, y, random_score(len(y)))
        record("전체_평균", split_name, y, overall_rate_score(len(y), train_rate))
        record("최근성_규칙", split_name, y, recency_propensity_score(d["days_since_last_purchase"], d["has_purchase_history"]))
        record("구매빈도_규칙", split_name, y, frequency_propensity_score(d["n_purchase_occasions_so_far"]))
        record("방문검색_규칙", split_name, y, visit_propensity_score(d["n_page_visit_28d"], d["n_search_query_28d"]))

    X_train, X_val, X_test = prepare_lr_features(train, val, test)
    lr = LogisticRegression(max_iter=1000)
    lr.fit(X_train, y_train)
    record("로지스틱_회귀", "val", y_val, lr.predict_proba(X_val)[:, 1])
    record("로지스틱_회귀", "test", y_test, lr.predict_proba(X_test)[:, 1])

    train_feat = train[FEATURE_COLS].copy()
    val_feat = val[FEATURE_COLS].copy()
    test_feat = test[FEATURE_COLS].copy()
    for d in (train_feat, val_feat, test_feat):
        d["has_purchase_history"] = d["has_purchase_history"].astype(int)

    train_ds = lgb.Dataset(train_feat, label=y_train)
    val_ds = lgb.Dataset(val_feat, label=y_val, reference=train_ds)
    gbm = lgb.train(
        params={"objective": "binary", "metric": "auc", "verbosity": -1, "seed": 42},
        train_set=train_ds,
        num_boost_round=500,
        valid_sets=[val_ds],
        callbacks=[lgb.early_stopping(30, verbose=False)],
    )
    record("LightGBM", "val", y_val, gbm.predict(val_feat))
    record("LightGBM", "test", y_test, gbm.predict(test_feat))

    return results, gbm


def main():
    with open(CONFIG_PATH) as f:
        paths = yaml.safe_load(f)
    con = duckdb.connect(str(paths["database_path"]), read_only=True)
    df = con.sql("SELECT * FROM mart_purchase_propensity").df()
    print(f"전체 행 수: {len(df):,}")

    all_results = []
    for label_col in ["will_purchase_14d", "will_purchase_28d"]:
        print(f"\n{'=' * 80}\n{label_col}\n{'=' * 80}")
        results, gbm = run_for_label(df, label_col)
        all_results.extend(results)
        for r in results:
            print(
                f"[{r['split']}] {r['method']:14s} AUC={r['roc_auc']:.4f} "
                f"PR-AUC={r['pr_auc']:.4f} Lift@10%={r['lift_at_10pct']:.2f} "
                f"Precision@10%={r['precision_at_10pct']:.4f} Recall@10%={r['recall_at_10pct']:.4f}"
            )
        if label_col == "will_purchase_14d":
            importances = pd.DataFrame(
                {"feature": FEATURE_COLS, "importance": gbm.feature_importance(importance_type="gain")}
            ).sort_values("importance", ascending=False)
            print("\nLightGBM feature importance (gain):")
            print(importances.to_string(index=False))
            importances.to_csv(REPORT_DIR / "phase6_model_b_feature_importance.csv", index=False)

    result_df = pd.DataFrame(all_results)
    ordered_cols = ["label", "split", "method", "n", "actual_positive_rate", "roc_auc", "pr_auc",
                     "log_loss", "brier_score",
                     "precision_at_5pct", "recall_at_5pct", "lift_at_5pct",
                     "precision_at_10pct", "recall_at_10pct", "lift_at_10pct",
                     "precision_at_20pct", "recall_at_20pct", "lift_at_20pct"]
    result_df = result_df[ordered_cols]
    REPORT_DIR.mkdir(exist_ok=True)
    result_df.to_csv(REPORT_DIR / "phase6_model_b_results.csv", index=False)
    print(f"\nSaved: {REPORT_DIR / 'phase6_model_b_results.csv'}")


if __name__ == "__main__":
    main()
