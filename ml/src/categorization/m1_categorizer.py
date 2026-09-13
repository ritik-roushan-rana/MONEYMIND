# ml/src/categorization/m1_categorizer.py

from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import classification_report, accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, OneHotEncoder, FunctionTransformer
from xgboost import XGBClassifier

MODELS_DIR = Path(__file__).resolve().parents[2] / "models"


def _log_amount(df: pd.DataFrame) -> np.ndarray:
    """log1p on amount — spending amounts are heavily right-skewed
    (a handful of huge transfers vs. many small purchases), and raw
    amount would let outliers dominate the tree splits."""
    return np.log1p(df[["amount"]].values)


def build_pipeline(n_classes: int) -> Pipeline:
    preprocessor = ColumnTransformer(
        transformers=[
            ("merchant_text", TfidfVectorizer(
                max_features=2000,
                ngram_range=(1, 2),   # unigrams + bigrams — "credit card", "cash withdrawal" etc.
                min_df=2,
            ), "clean_merchant"),
            ("amount", FunctionTransformer(_log_amount, validate=False), ["amount"]),
            ("txn_type", OneHotEncoder(handle_unknown="ignore"), ["txn_type"]),
        ],
    )

    classifier = XGBClassifier(
        objective="multi:softprob",
        num_class=n_classes,
        n_estimators=300,
        max_depth=6,
        learning_rate=0.1,
        eval_metric="mlogloss",
        n_jobs=-1,
    )

    return Pipeline([
        ("preprocess", preprocessor),
        ("classifier", classifier),
    ])


def train_and_evaluate(df: pd.DataFrame, test_size: float = 0.2, random_state: int = 42):
    df = df.copy()
    df["clean_merchant"] = df["clean_merchant"].fillna("")

    label_encoder = LabelEncoder()
    y = label_encoder.fit_transform(df["category"])
    X = df[["clean_merchant", "amount", "txn_type"]]

    # stratify keeps rare categories represented in both train and test
    # instead of accidentally landing entirely in one split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )

    pipeline = build_pipeline(n_classes=len(label_encoder.classes_))
    pipeline.fit(X_train, y_train)

    y_pred = pipeline.predict(X_test)

    print(f"\nOverall accuracy: {accuracy_score(y_test, y_pred):.4f}")
    print("\nPer-category performance:")
    print(classification_report(
        y_test, y_pred,
        labels=range(len(label_encoder.classes_)),
        target_names=label_encoder.classes_,
        zero_division=0,
    ))

    return pipeline, label_encoder


def save_model(pipeline: Pipeline, label_encoder: LabelEncoder, name: str = "m1_categorizer"):
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, MODELS_DIR / f"{name}.joblib")
    joblib.dump(label_encoder, MODELS_DIR / f"{name}_labels.joblib")
    print(f"\nSaved model to {MODELS_DIR / f'{name}.joblib'}")


def load_model(name: str = "m1_categorizer") -> tuple[Pipeline, LabelEncoder]:
    pipeline = joblib.load(MODELS_DIR / f"{name}.joblib")
    label_encoder = joblib.load(MODELS_DIR / f"{name}_labels.joblib")
    return pipeline, label_encoder


def predict_category(pipeline: Pipeline, label_encoder: LabelEncoder, clean_merchant: str, amount: float, txn_type: str) -> str:
    X = pd.DataFrame([{"clean_merchant": clean_merchant, "amount": amount, "txn_type": txn_type}])
    pred_idx = pipeline.predict(X)[0]
    return label_encoder.inverse_transform([pred_idx])[0]