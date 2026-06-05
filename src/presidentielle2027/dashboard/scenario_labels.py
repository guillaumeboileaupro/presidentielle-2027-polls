from __future__ import annotations

import pandas as pd


def _ordered_candidates(group: pd.DataFrame) -> list[str]:
    ranked = (
        group.groupby("candidate_name", dropna=False)["estimate_percent"]
        .mean()
        .sort_values(ascending=False)
        .index.tolist()
    )
    return [str(candidate) for candidate in ranked if str(candidate).strip()]


def build_scenario_catalog(frame: pd.DataFrame, round_name: str) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    title = "Premier tour" if round_name == "first_round" else "Second tour"

    for scenario_name, group in frame.groupby("scenario_name", dropna=False):
        candidates = _ordered_candidates(group)
        short_list = " / ".join(candidates[:6])
        if len(candidates) > 6:
            short_list = f"{short_list} / +{len(candidates) - 6}"
        pollsters = sorted(group["polling_company"].dropna().astype(str).unique().tolist())
        pollster_label = pollsters[0] if len(pollsters) == 1 else f"{len(pollsters)} instituts"
        rows.append(
            {
                "scenario_name": scenario_name,
                "scenario_label": f"{title} · {short_list}",
                "candidate_list": candidates,
                "candidate_text": " · ".join(candidates),
                "pollster_label": pollster_label,
                "rows": int(len(group)),
                "pollsters": int(group["polling_company"].nunique()),
                "candidates": int(group["candidate_name"].nunique()),
                "last_publication": group["publication_date"].max(),
            }
        )

    return pd.DataFrame(rows).sort_values(["last_publication", "rows"], ascending=[False, False])
