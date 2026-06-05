from __future__ import annotations

import pandas as pd
import streamlit as st


def render_data_quality_page(frame: pd.DataFrame) -> None:
    st.subheader("Vue qualité des données")
    if frame.empty:
        st.info("Aucune donnée pour les filtres sélectionnés.")
        return
    extraction_confidence = (
        pd.to_numeric(frame["extraction_confidence"], errors="coerce")
        if "extraction_confidence" in frame.columns
        else pd.Series(0, index=frame.index, dtype="float64")
    )
    quality = {
        "Sondages incomplets": int(frame["estimate_percent"].isna().sum()),
        "Effectifs manquants": int(frame["sample_size"].isna().sum()),
        "Dates manquantes": int(frame["publication_date"].isna().sum()),
        "Sources sans PDF": int(frame.get("source_url", pd.Series(dtype=str)).astype(str).str.endswith(".pdf").eq(False).sum()),
        "Extraction confidence faible": int(extraction_confidence.fillna(0).lt(0.5).sum()),
    }
    st.dataframe(pd.DataFrame(list(quality.items()), columns=["Metric", "Count"]), width="stretch")
