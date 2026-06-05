from __future__ import annotations

import pickle
from datetime import date
from pathlib import Path

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, root_mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sqlalchemy.orm import Session

from presidentielle2027.config import get_settings
from presidentielle2027.db.models import ModelRun
from presidentielle2027.ml.features import FEATURE_COLUMNS, build_feature_frame


def _build_pipeline(model_type: str) -> Pipeline:
    categorical_features = ["polling_company", "candidate_party", "political_family", "collection_method", "round"]
    numeric_features = ["days_until_election", "sample_size", "scenario_size", "publication_month"]
    preprocessor = ColumnTransformer(
        transformers=[
            (
                "categorical",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("encoder", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                categorical_features,
            ),
            (
                "numeric",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scaler", StandardScaler()),
                    ]
                ),
                numeric_features,
            ),
        ]
    )
    estimator = Ridge(alpha=1.0) if model_type == "ridge" else RandomForestRegressor(n_estimators=200, random_state=42)
    return Pipeline(steps=[("preprocessor", preprocessor), ("model", estimator)])


def train_adjustment_model(
    training_frame: pd.DataFrame,
    session: Session | None = None,
    model_type: str = "ridge",
    target_column: str = "observed_bias",
    election_date: date | None = None,
) -> tuple[Pipeline, dict[str, float], Path]:
    if target_column not in training_frame.columns:
        raise ValueError(f"Missing target column '{target_column}' in training data.")
    features = build_feature_frame(training_frame, election_date or date.fromisoformat(get_settings().default_election_date))
    target = pd.to_numeric(training_frame[target_column], errors="coerce").fillna(0.0)
    pipeline = _build_pipeline(model_type=model_type)
    pipeline.fit(features[FEATURE_COLUMNS], target)
    predictions = pipeline.predict(features[FEATURE_COLUMNS])
    metrics = {
        "mae": float(mean_absolute_error(target, predictions)),
        "rmse": float(root_mean_squared_error(target, predictions)),
    }

    artifact_dir = get_settings().processed_dir / "models"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"{model_type}_bias_model.pkl"
    with artifact_path.open("wb") as handle:
        pickle.dump(pipeline, handle)

    if session is not None:
        session.add(
            ModelRun(
                run_name=f"{model_type}_adjustment_model",
                model_type=model_type,
                target_name=target_column,
                metrics=metrics,
                artifact_path=str(artifact_path),
                training_data_path="in_memory",
                notes="Experimental bias-correction model. Not an election prediction model.",
            )
        )
        session.commit()

    return pipeline, metrics, artifact_path

