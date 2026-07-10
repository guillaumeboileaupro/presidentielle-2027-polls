from __future__ import annotations

import json
import re
from pathlib import Path
from zipfile import ZipFile

import pandas as pd
import requests

FRANCEINFO_URL = "https://www.franceinfo.fr/elections/legislatives/infographies-elections-legislatives-2024-visualisez-la-repartition-des-circonscriptions-entre-les-partis-du-nouveau-front-populaire_6604014.html"
FLOURISH_EMBED_PREFIX = "https://flo.uri.sh/"
OUTPUT_PATH = Path("data/reference/nfp_internal_party_mapping_2024.csv")
USER_AGENT = "Mozilla/5.0 (compatible; CodexNFPFranceinfo/1.0)"
ZIP_PATHS = [
    Path("/home/gboileau/Téléchargements/2024_legislative.zip"),
    Path("data/reference/2024_legislative.zip"),
]
INNER_CIRCO_RESULTS = "2024_legislative/resultats-definitifs-par-circonscriptions-legislatives.csv"


def normalize_text(value: object) -> str:
    return (
        str(value or "")
        .replace("\xa0", " ")
        .replace("1ere", "1ère")
        .replace("1re", "1ère")
        .replace("2eme", "2ème")
        .replace("e circonscription", "ème circonscription")
        .strip()
        .lower()
    )


def format_circo_key(dept_code: str, circo_code: object) -> str:
    dept = str(dept_code).strip()
    circo = str(circo_code).strip()
    if circo.endswith(".0"):
        circo = circo[:-2]
    return f"{dept}-{circo}"


def load_official_ug_circos() -> pd.DataFrame:
    frame = None
    for path in ZIP_PATHS:
        if not path.exists():
            continue
        with ZipFile(path) as archive:
            if INNER_CIRCO_RESULTS not in archive.namelist():
                continue
            with archive.open(INNER_CIRCO_RESULTS) as handle:
                frame = pd.read_csv(handle, sep=";")
            break
    if frame is None or frame.empty:
        raise RuntimeError("Official circonscription results CSV not found")

    rows: list[dict[str, str]] = []
    candidate_indices = sorted(
        {
            int(match.group(1))
            for column in frame.columns
            for match in [re.match(r"Nuance candidat (\d+)", str(column))]
            if match is not None
        }
    )
    for record in frame.to_dict(orient="records"):
        dept_code = str(record.get("Code département") or "").strip()
        circo_code = record.get("Code circonscription législative")
        dept_label = str(record.get("Libellé département") or "").strip()
        circo_label = str(record.get("Libellé circonscription législative") or "").strip()
        if not dept_code or circo_code is None:
            continue
        for idx in candidate_indices:
            nuance = str(record.get(f"Nuance candidat {idx}") or "").strip().upper()
            if nuance != "UG":
                continue
            rows.append(
                {
                    "circo_key": format_circo_key(dept_code, circo_code),
                    "dept_label": dept_label,
                    "circo_label": circo_label,
                }
            )
    official = pd.DataFrame(rows).drop_duplicates()
    official["dept_label_norm"] = official["dept_label"].map(normalize_text)
    official["circo_label_norm"] = official["circo_label"].map(normalize_text)
    return official


def normalize_party(raw: object) -> str | None:
    text = str(raw or "").strip()
    upper = text.upper()
    if "FRANCE INSOUMISE" in upper or upper == "LFI":
        return "LFI / NFP"
    if "PARTI SOCIALISTE" in upper or upper == "PS":
        return "PS / NFP"
    if "ECOLOG" in upper or "EELV" in upper:
        return "EELV / NFP"
    if "COMMUNISTE" in upper or "PCF" in upper:
        return "PCF / NFP"
    if "NPA" in upper:
        return "NPA / NFP"
    if text:
        return "Autre NFP"
    return None


def extract_flourish_payload(html: str) -> dict[str, object]:
    marker = "_Flourish_data = "
    start = html.find(marker)
    if start == -1:
        raise RuntimeError("Flourish payload marker not found")
    start += len(marker)
    end = html.find(",\n\t\t\t\t_Flourish_visualisation_id", start)
    if end == -1:
        end = html.find(",\n                _Flourish_visualisation_id", start)
    if end == -1:
        raise RuntimeError("Flourish payload end marker not found")
    payload_text = html[start:end].strip()
    return json.loads(payload_text)


def extract_flourish_embed_url(article_html: str) -> str:
    match = re.search(r'<div class="flourish-embed[^"]*"[^>]*data-src="([^"]+)"', article_html)
    if not match:
        raise RuntimeError("Flourish embed data-src not found in franceinfo article")
    raw = match.group(1).lstrip("/")
    raw = raw.split("?", 1)[0].strip("/")
    return FLOURISH_EMBED_PREFIX + raw + "/embed"


def main() -> None:
    response = requests.get(FRANCEINFO_URL, headers={"User-Agent": USER_AGENT}, timeout=30)
    response.raise_for_status()
    flourish_url = extract_flourish_embed_url(response.text)
    flourish_response = requests.get(flourish_url, headers={"User-Agent": USER_AGENT}, timeout=30)
    flourish_response.raise_for_status()
    payload = extract_flourish_payload(flourish_response.text)
    choropleth = pd.DataFrame(payload.get("choropleth", []))
    points = pd.DataFrame(payload.get("points", []))
    if choropleth.empty and points.empty:
        raise RuntimeError("No usable dataset found in Flourish payload")

    circo_rows: list[dict[str, object]] = []
    if not choropleth.empty:
        for row in choropleth.to_dict("records"):
            metadata = row.get("metadata")
            if not isinstance(metadata, list) or len(metadata) < 4:
                continue
            full_label = str(metadata[2] or "")
            party_raw = str(metadata[3] or "")
            if " - " not in full_label:
                continue
            dept_label, circo_label = full_label.split(" - ", 1)
            circo_rows.append(
                {
                    "dept_label": dept_label,
                    "circo_label": circo_label,
                    "party_raw": party_raw,
                }
            )
    if not points.empty:
        for row in points.to_dict("records"):
            metadata = row.get("metadata")
            if not isinstance(metadata, list) or len(metadata) < 3:
                continue
            circo_rows.append(
                {
                    "dept_label": metadata[0],
                    "circo_label": metadata[1],
                    "party_raw": metadata[2],
                }
            )

    points = pd.DataFrame(circo_rows)
    points["nfp_internal_party"] = points["party_raw"].map(normalize_party)
    points["dept_label_norm"] = points["dept_label"].map(normalize_text)
    points["circo_label_norm"] = points["circo_label"].map(normalize_text)
    points = points.loc[points["nfp_internal_party"].notna()].copy()

    official = load_official_ug_circos()

    merged = official.merge(
        points[
            [
                "dept_label",
                "circo_label",
                "dept_label_norm",
                "circo_label_norm",
                "party_raw",
                "nfp_internal_party",
            ]
        ].drop_duplicates(),
        on=["dept_label_norm", "circo_label_norm"],
        how="left",
        suffixes=("_official", "_franceinfo"),
    )
    result = merged[
        [
            "circo_key",
            "dept_label_official",
            "circo_label_official",
            "party_raw",
            "nfp_internal_party",
        ]
    ].rename(
        columns={
            "dept_label_official": "dept_label",
            "circo_label_official": "circo_label",
        }
    )
    result = result.loc[result["nfp_internal_party"].notna()].drop_duplicates(subset=["circo_key"])

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUTPUT_PATH, index=False, sep=";")
    print({"rows": len(result), "path": str(OUTPUT_PATH)})
    if not result.empty:
        print(result["nfp_internal_party"].value_counts().to_dict())


if __name__ == "__main__":
    main()
