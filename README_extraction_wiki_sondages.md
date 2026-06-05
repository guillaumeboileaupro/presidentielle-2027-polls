# Extraction des 3 fichiers demandés

Tu as demandé 3 fichiers avec toutes les données des pages Wikipédia suivantes :

1. Présidentielle 2027
2. Présidentielle 2022
3. Législatives 2024

Le script `make_wiki_datasets.py` génère automatiquement :

- `sondages_presidentielle_2027_wikipedia_tables.csv`
- `sondages_presidentielle_2022_wikipedia_tables.csv`
- `sondages_legislatives_2024_wikipedia_tables.csv`
- `wikipedia_sondages_2022_2024_2027_tables.xlsx`

Commande :

```bash
pip install pandas lxml beautifulsoup4 requests openpyxl
python make_wiki_datasets.py
```

Le script met en cache les pages HTML dans `data/raw/wikipedia_html/`.
Si le réseau vers Wikipédia n’est pas disponible, tu peux relancer avec les fichiers HTML déjà présents dans ce dossier.

Les CSV contiennent les tableaux Wikipédia, avec :
- `source_page`
- `source_url`
- `page_key`
- `table_index`
- `section`
- `row_index`
- colonnes originales de Wikipédia
- `row_links_json` avec les liens trouvés dans chaque ligne

Le script garde aussi les URLs sources et les liens trouvés dans chaque ligne via `row_links_json`.

Note d'usage dans le repo :

- pour les législatives 2024, le dashboard et les corrections historiques doivent lire en priorité `sondages_legislatives_2024_wikipedia_tables.csv` ;
- les `visual_rows` issus du PDF Wikipédia restent utiles pour le debug visuel, mais pas comme source principale pour reconstruire les blocs nationaux RN / NFP / ENS / LR.
