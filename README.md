# presidentielle-2027-polls

Repository Python pour collecter, structurer, analyser, redresser et visualiser des sondages publics liés à l'élection présidentielle française de 2027.

Le projet est conçu comme une base de travail maintenable plutôt qu'un script ponctuel. Il sépare les sources brutes, la normalisation, la persistance en base, les calculs analytiques, les ajustements méthodologiques, les expérimentations ML et la visualisation.

## Table des matières

- [Objectif](#objectif)
- [Principes méthodologiques](#principes-méthodologiques)
- [État actuel du projet](#état-actuel-du-projet)
- [Architecture du repository](#architecture-du-repository)
- [Modèle de données](#modèle-de-données)
- [Sources prises en charge](#sources-prises-en-charge)
- [Jeux de données présents dans le repo](#jeux-de-données-présents-dans-le-repo)
- [Installation](#installation)
- [Configuration](#configuration)
- [Démarrage rapide](#démarrage-rapide)
- [Notebooks](#notebooks)
- [Utilisation détaillée de la CLI](#utilisation-détaillée-de-la-cli)
- [Pipeline de données](#pipeline-de-données)
- [Dashboard](#dashboard)
- [Statistiques et redressages implémentés](#statistiques-et-redressages-implémentés)
- [Machine learning expérimental](#machine-learning-expérimental)
- [Tests et qualité](#tests-et-qualité)
- [Développement dans Codespaces / VS Code](#développement-dans-codespaces--vs-code)
- [Limites connues](#limites-connues)
- [Feuille de route conseillée](#feuille-de-route-conseillée)
- [Avertissement](#avertissement)

## Objectif

Le projet vise à fournir une base logicielle pour :

- récupérer des sondages publics liés à la présidentielle française de 2027 ;
- conserver les liens vers les sources d'origine ;
- extraire ou importer des résultats de sondages sous des formats hétérogènes ;
- normaliser ces données dans un schéma relationnel stable ;
- calculer des moyennes pondérées et des tendances temporelles ;
- estimer des effets institut et appliquer des corrections simples ;
- préparer une couche expérimentale de correction de biais historiques via machine learning ;
- exposer un dashboard pour l'exploration visuelle de l'évolution des intentions de vote.

Le projet ne cherche pas à prédire avec certitude le résultat de l'élection.

## Principes méthodologiques

Quelques principes guident la structure du repository :

- Ne jamais confondre agrégation statistique et prévision certaine.
- Garder les données brutes et les données transformées séparées.
- Préserver les métadonnées de source autant que possible.
- Permettre l'ajout futur de nouvelles sources, de nouveaux scénarios et de nouveaux candidats.
- Éviter les scripts monolithiques difficiles à maintenir.
- Documenter explicitement ce qui est fiable, ce qui est reconstruit et ce qui reste incertain.

## État actuel du projet

La version actuelle fournit déjà une base de travail exploitable :

- base SQLite avec modèles SQLAlchemy ;
- CLI Typer ;
- ingestion initiale des pages Wikipédia ;
- ingestion via l'API MediaWiki avec repli HTML et métadonnées de page ;
- import de fichiers Excel d'extraction Wikipédia en deux formats ;
- rapport de couverture des scénarios pour repérer les candidats manquants ;
- registre local des sources web récentes suivies ;
- dataset d'exemple fictif pour test rapide ;
- calcul de moyennes pondérées ;
- lissage simple ;
- estimation simple de house effects ;
- correction historique 2022 par force politique et par institut ;
- benchmark expérimental de second tour à partir des législatives 2024 ;
- série de notebooks métier ;
- dashboard Streamlit restructuré par usage ;
- architecture ML baseline ;
- premiers tests unitaires.

Les fichiers Excel suivants ont déjà été intégrés :

- [presidentielle_2027_sondages_wikipedia_extraction.xlsx](/home/gboileau/Documents/Presidentielle/presidentielle-2027-polls/data/raw/presidentielle_2027_sondages_wikipedia_extraction.xlsx)
- [presidentielle_2027_sondages_wikipedia_extraction_v2.xlsx](/home/gboileau/Documents/Presidentielle/presidentielle-2027-polls/data/raw/presidentielle_2027_sondages_wikipedia_extraction_v2.xlsx)

Des CSV normalisés ont déjà été générés :

- [wikipedia_2027_polls_normalized.csv](/home/gboileau/Documents/Presidentielle/presidentielle-2027-polls/data/processed/wikipedia_2027_polls_normalized.csv)
- [wikipedia_2027_polls_normalized_v2.csv](/home/gboileau/Documents/Presidentielle/presidentielle-2027-polls/data/processed/wikipedia_2027_polls_normalized_v2.csv)

Le dashboard lit en priorité la base SQLite si elle contient des résultats. Sinon, il prend en fallback le CSV V2, puis le CSV V1, puis le sample fictif.

Un registre de veille des sources récentes est aussi maintenu dans :

- [latest_web_sources.csv](/home/gboileau/Documents/Presidentielle/presidentielle-2027-polls/data/reference/latest_web_sources.csv)

Des références historiques utilisées par le redressage sont aussi présentes :

- [historical_polls_2022_first_round.csv](/home/gboileau/Documents/Presidentielle/presidentielle-2027-polls/data/reference/historical_polls_2022_first_round.csv)
- [historical_results_2022_presidential_first_round.csv](/home/gboileau/Documents/Presidentielle/presidentielle-2027-polls/data/reference/historical_results_2022_presidential_first_round.csv)
- [historical_results_2024_legislatives_blocs.csv](/home/gboileau/Documents/Presidentielle/presidentielle-2027-polls/data/reference/historical_results_2024_legislatives_blocs.csv)
- [polling_representativity_factors.csv](/home/gboileau/Documents/Presidentielle/presidentielle-2027-polls/data/reference/polling_representativity_factors.csv)

## Architecture du repository

```text
presidentielle-2027-polls/
  .devcontainer/
  alembic/
  data/
    raw/
    interim/
    processed/
    exports/
    historical/
  notebooks/
  src/presidentielle2027/
    adjustments/
    analytics/
    dashboard/
    db/
    extraction/
    ingestion/
    ml/
    cli.py
    config.py
  tests/
  README.md
  AGENT.md
  pyproject.toml
  Makefile
  docker-compose.yml
```

### Répertoires de données

- `data/raw/` : sources brutes téléchargées ou copiées sans normalisation.
- `data/interim/` : zone tampon pour transformations intermédiaires.
- `data/processed/` : tables normalisées ou enrichies prêtes pour analyses.
- `data/exports/` : sorties analytiques exportées, par exemple moyennes pondérées.
- `data/historical/` : futurs datasets historiques 2017/2022 pour backtesting et correction de biais.

### Modules applicatifs

- `db/` : modèles SQLAlchemy, session et initialisation de base.
- `ingestion/` : récupération des pages Wikipédia et téléchargement de PDF.
- `extraction/` : parsing de tableaux, parsing PDF, parsing Excel, validation et normalisation.
- `analytics/` : moyennes pondérées, incertitude, tendances.
- `adjustments/` : pondération par récence, taille d'échantillon, house effects, ajustement turnout.
- `ml/` : features, entraînement baseline, prédiction, backtesting préparatoire.
- `dashboard/` : app Streamlit et pages métier.

## Modèle de données

Le schéma SQLAlchemy implémente les tables suivantes :

- `sources`
- `polling_companies`
- `polls`
- `poll_scenarios`
- `candidates`
- `poll_results`
- `adjustments`
- `model_runs`
- `forecasts_or_smoothed_estimates`
- `ingestion_logs`

### Logique relationnelle

- `sources` représente l'origine d'un document ou d'une page.
- `polls` représente un sondage donné avec ses métadonnées transverses.
- `poll_scenarios` sépare les configurations de candidats au sein d'un même sondage.
- `poll_results` stocke les scores candidat par candidat.
- `candidates` déduplique les acteurs politiques.
- `adjustments` documente les corrections appliquées.
- `model_runs` trace les entraînements ML.
- `forecasts_or_smoothed_estimates` permet de stocker des séries lissées ou futures estimations.
- `ingestion_logs` garde une trace des opérations d'import.

Le backend par défaut est SQLite, avec compatibilité prévue pour PostgreSQL via `DATABASE_URL`.

## Sources prises en charge

### Sources initiales

- page Wikipédia française sur les sondages 2027 ;
- page Wikipédia anglaise sur les sondages 2027 ;
- fichiers Excel d'extraction dérivés de Wikipédia ;
- PDF publics de notices ou instituts, quand l'URL est disponible.

### Sources futures prévues

L'architecture permet d'ajouter ensuite :

- Elabe
- Ifop
- Ipsos
- Harris Interactive
- OpinionWay
- Cluster17
- autres instituts ou médias partenaires

### Sources web récentes déjà recensées

Au 30 mai 2026, les sources publiques suivantes sont déjà suivies dans le repo :

- Wikipédia FR : https://fr.wikipedia.org/wiki/Liste_de_sondages_sur_l%27%C3%A9lection_pr%C3%A9sidentielle_fran%C3%A7aise_de_2027
- Wikipédia EN : https://en.wikipedia.org/wiki/Opinion_polling_for_the_2027_French_presidential_election
- Notice Commission des sondages pour Toluna Harris Interactive / M6 / RTL : https://www.commission-des-sondages.fr/notices/medias/fichiers/add/2165
- Page publique Ifop : https://www.ifop.com/article/les-intentions-de-vote-dans-la-perspective-de-la-prochaine-election-presidentielle-2
- Communiqués de la Commission des sondages : https://www.commission-des-sondages.fr/hist/communiques/index.htm

## Jeux de données présents dans le repo

### 1. Données d'exemple fictives

Le fichier [sample_polls.csv](/home/gboileau/Documents/Presidentielle/presidentielle-2027-polls/data/processed/sample_polls.csv) existe uniquement pour tester rapidement le dashboard.

Contraintes respectées :

- `source_name = "sample_data"`
- `extraction_confidence = 0`
- aucun vrai sondage n'est inventé

### 2. Données normalisées depuis l'extraction Wikipédia V1

[wikipedia_2027_polls_normalized.csv](/home/gboileau/Documents/Presidentielle/presidentielle-2027-polls/data/processed/wikipedia_2027_polls_normalized.csv) correspond à la première extraction fournie.

### 3. Données normalisées depuis l'extraction Wikipédia V2

[wikipedia_2027_polls_normalized_v2.csv](/home/gboileau/Documents/Presidentielle/presidentielle-2027-polls/data/processed/wikipedia_2027_polls_normalized_v2.csv) correspond à une extraction plus structurée avec :

- vecteurs bruts premier tour ;
- second tour structuré ;
- blocs de scénarios génériques ;
- éléments de rerun 2022 disponibles pour extension future.

## Installation

Python 3.10+ est requis.

### Installation manuelle

```bash
cd /home/gboileau/Documents/Presidentielle/presidentielle-2027-polls
python3.10 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Cette installation suffit pour :

- la base de données ;
- la normalisation ;
- les notebooks ;
- le dashboard Streamlit.

Les dépendances de développement installent aussi les briques Jupyter du projet :

- `ipykernel`
- `jupyterlab`
- `notebook`
- `nbformat`

### Installation avec la couche ML expérimentale

Le module ML est volontairement séparé du dashboard et des notebooks d’analyse pour éviter de charger `scikit-learn` / `scipy` quand tu veux seulement lancer l’app.

Si tu veux aussi activer `train-adjustment-model` :

```bash
pip install -e ".[ml,dev]"
```

### Installation via Makefile

```bash
make install
```

`make install` utilise automatiquement `.venv/bin/python` si le venv du repo existe déjà. Sinon, il essaie `python3.10`, puis `python3`, puis `python`.

Pour éviter les écarts entre le Python système et le projet, le chemin le plus robuste reste :

```bash
python3.10 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp .env.example .env
```

## Configuration

Le fichier [`.env.example`](/home/gboileau/Documents/Presidentielle/presidentielle-2027-polls/.env.example) expose les variables principales :

```env
DATABASE_URL=sqlite:///./data/polls.sqlite3
APP_ENV=development
WIKIPEDIA_FR_URL=...
WIKIPEDIA_EN_URL=...
```

### Variables utiles

- `DATABASE_URL` : base SQLite ou PostgreSQL.
- `APP_ENV` : environnement logique de l'application.
- `WIKIPEDIA_FR_URL` : source FR par défaut.
- `WIKIPEDIA_EN_URL` : source EN par défaut.

## Démarrage rapide

### Option 1 : voir immédiatement des résultats dans le dashboard

Si le CSV V2 est présent, tu peux lancer directement :

```bash
make dashboard
```

Commande CLI équivalente :

```bash
.venv/bin/python -m presidentielle2027.cli run-dashboard
```

Le dashboard utilisera :

1. la base SQLite si elle contient des données ;
2. sinon `data/processed/wikipedia_2027_polls_normalized_v2.csv` ;
3. sinon `data/processed/wikipedia_2027_polls_normalized.csv` ;
4. sinon `data/processed/sample_polls.csv`.

### Option 2 : remplir la base SQLite puis lancer le dashboard

```bash
.venv/bin/python -m presidentielle2027.cli init-db
.venv/bin/python -m presidentielle2027.cli normalize --input-xlsx data/raw/presidentielle_2027_sondages_wikipedia_extraction_v2.xlsx
.venv/bin/python -m presidentielle2027.cli verify-coverage --input-csv data/processed/wikipedia_2027_polls_normalized_v2.csv --output-csv data/exports/coverage_report.csv
.venv/bin/python -m presidentielle2027.cli compute-averages
make dashboard
```

### Option 3 : ouvrir les notebooks avec le bon kernel

```bash
.venv/bin/python -m presidentielle2027.cli install-notebook-kernel
source .venv/bin/activate
jupyter lab notebooks
```

Dans Jupyter, choisir le kernel :

- `Présidentielle 2027 (.venv)`

## Notebooks

Les notebooks sont maintenant organisés par usage et non comme un bloc exploratoire générique :

- [01_sources_metadata.ipynb](/home/gboileau/Documents/Presidentielle/presidentielle-2027-polls/notebooks/01_sources_metadata.ipynb)
  - inventaire des datasets, instituts et trous méthodologiques ;
- [02_first_round_raw.ipynb](/home/gboileau/Documents/Presidentielle/presidentielle-2027-polls/notebooks/02_first_round_raw.ipynb)
  - premier tour brut, un scénario à la fois ;
- [03_second_round_raw.ipynb](/home/gboileau/Documents/Presidentielle/presidentielle-2027-polls/notebooks/03_second_round_raw.ipynb)
  - second tour brut, un duel à la fois ;
- [04_error_bars_raw.ipynb](/home/gboileau/Documents/Presidentielle/presidentielle-2027-polls/notebooks/04_error_bars_raw.ipynb)
  - barres d'erreur sur les données brutes ;
- [05_corrected_dataset.ipynb](/home/gboileau/Documents/Presidentielle/presidentielle-2027-polls/notebooks/05_corrected_dataset.ipynb)
  - vue corrigée séparée du brut.

### Commandes utiles

```bash
make notebook-kernel
make notebook
```

## Utilisation détaillée de la CLI

### Initialiser la base

```bash
.venv/bin/python -m presidentielle2027.cli init-db
```

Crée les tables SQLAlchemy dans la base configurée.

### Ingestion Wikipédia HTML

```bash
.venv/bin/python -m presidentielle2027.cli ingest-wikipedia
```

Effet :

- télécharge les pages Wikipédia FR et EN ;
- privilégie l'API MediaWiki pour récupérer la version parsée de la page ;
- sauvegarde le HTML brut ;
- sauvegarde aussi un JSON de métadonnées avec `page_id`, `wikidata_item_id` et `revision_id` ;
- extrait les tableaux HTML vers des CSV intermédiaires dans `data/raw/` ;
- journalise l'opération dans `ingestion_logs`.

### Extraire les tables Wikipédia 2022 / 2024 / 2027

Depuis la racine du repo :

```bash
pip install pandas lxml beautifulsoup4 requests openpyxl
.venv/bin/python make_wiki_datasets.py
```

Ou via `make` :

```bash
make wiki-datasets
```

Fichiers générés :

- `sondages_presidentielle_2027_wikipedia_tables.csv`
- `sondages_presidentielle_2022_wikipedia_tables.csv`
- `sondages_legislatives_2024_wikipedia_tables.csv`
- `wikipedia_sondages_2022_2024_2027_tables.xlsx`

Le script conserve aussi les URLs sources et les liens trouvés dans chaque ligne via `row_links_json`.

Les pages HTML sont mises en cache dans `data/raw/wikipedia_html/`. Si l’accès réseau vers Wikipédia échoue, tu peux relancer en utilisant ce cache local.

### Télécharger un PDF

```bash
.venv/bin/python -m presidentielle2027.cli ingest-pdf --url "https://..."
```

Effet :

- télécharge le PDF dans `data/raw/pdfs/`.

### Normaliser un CSV

```bash
.venv/bin/python -m presidentielle2027.cli normalize --input-csv data/processed/sample_polls.csv
```

Effet :

- charge le CSV ;
- valide les colonnes attendues ;
- persiste les résultats dans SQLite.

### Normaliser l'extraction Wikipédia V1

```bash
.venv/bin/python -m presidentielle2027.cli normalize \
  --input-xlsx data/raw/presidentielle_2027_sondages_wikipedia_extraction.xlsx
```

Effet :

- convertit le classeur en CSV normalisé ;
- écrit le résultat dans `data/processed/wikipedia_2027_polls_normalized.csv` ;
- persiste les lignes normalisées dans SQLite.

### Normaliser l'extraction Wikipédia V2

```bash
.venv/bin/python -m presidentielle2027.cli normalize \
  --input-xlsx data/raw/presidentielle_2027_sondages_wikipedia_extraction_v2.xlsx
```

Effet :

- convertit le classeur V2 en long format ;
- écrit le résultat dans `data/processed/wikipedia_2027_polls_normalized.csv` si on passe par la CLI actuelle ;
- ou permet déjà l'usage direct de `data/processed/wikipedia_2027_polls_normalized_v2.csv` généré dans le repo.

Note :

le parseur Excel sait détecter automatiquement le format V1 ou V2 selon les feuilles présentes.

### Calculer les moyennes pondérées

```bash
.venv/bin/python -m presidentielle2027.cli compute-averages
```

Effet :

- lit les résultats depuis la base ;
- calcule les moyennes pondérées ;
- exporte le résultat dans [weighted_averages.csv](/home/gboileau/Documents/Presidentielle/presidentielle-2027-polls/data/exports/weighted_averages.csv).

### Vérifier la couverture des sondages

```bash
.venv/bin/python -m presidentielle2027.cli verify-coverage --input-csv data/processed/wikipedia_2027_polls_normalized_v2.csv --output-csv data/exports/coverage_report.csv
```

Effet :

- lit le CSV normalisé ;
- reconstitue les candidats attendus à partir de `raw_text_context` ;
- signale les scénarios avec candidats manquants ou doublons ;
- exporte un rapport exploitable dans `data/exports/coverage_report.csv`.

### Entraîner le modèle expérimental

Prérequis :

```bash
pip install -e ".[ml,dev]"
```

```bash
.venv/bin/python -m presidentielle2027.cli train-adjustment-model \
  --training-csv data/processed/sample_polls.csv
```

Effet :

- crée un modèle baseline Ridge ou RandomForest ;
- sérialise le pipeline dans `data/processed/models/` ;
- journalise le run si une session DB est active.

### Lancer le dashboard

```bash
make dashboard
```

Commande CLI équivalente :

```bash
.venv/bin/python -m presidentielle2027.cli run-dashboard
```

Le dashboard est accessible en général sur `http://localhost:8501`.

### Installer le kernel Jupyter du projet

```bash
.venv/bin/python -m presidentielle2027.cli install-notebook-kernel
```

Cette commande enregistre le kernel utilisateur `Présidentielle 2027 (.venv)`.

## Pipeline de données

Le pipeline logique est le suivant :

1. acquisition de sources brutes ;
2. stockage des artefacts dans `data/raw/` ;
3. parsing ou éclatement des formats semi-structurés ;
4. normalisation vers le schéma commun ;
5. persistance en base ;
6. calculs analytiques et exports ;
7. visualisation interactive.

### Champs normalisés cibles

Le format cible couvre notamment :

- `poll_id`
- `source_url`
- `source_name`
- `polling_company`
- `commissioner`
- `media_partner`
- `fieldwork_start_date`
- `fieldwork_end_date`
- `publication_date`
- `sample_size`
- `population`
- `collection_method`
- `quota_method`
- `round`
- `scenario_name`
- `candidate_name`
- `candidate_party`
- `political_family`
- `estimate_percent`
- `lower_bound_percent`
- `upper_bound_percent`
- `margin_of_error`
- `undecided_percent`
- `abstention_estimate`
- `registered_voters_basis`
- `raw_text_context`
- `extraction_confidence`

## Dashboard

Le dashboard Streamlit suit maintenant la même logique que les notebooks : séparer les usages, les tours et les types de lecture au lieu de tout mélanger dans une même vue.

L’habillage de l’application reprend désormais une partie de la charte graphique de La France insoumise pour la coque visuelle de l’app :

- palette violette / rouge FI sur le bandeau et les contrôles ;
- fond clair obligatoire ;
- figures Plotly en fond blanc ;
- étiquettes candidates enrichies avec logos de partis quand ils sont disponibles.

### Vues actuelles

- `Premier tour`
  - tous les sondages de premier tour ;
  - regroupement par `Parti politique` ou `Famille politique` ;
  - nuage brut des points ;
  - une seule ligne de tendance par force ;
  - bouton de prolongation de dynamique jusqu’au scrutin.
- `Premier tour corrigé`
  - correction historique fondée sur 2022 ;
  - biais institut ;
  - biais temporel selon la distance au scrutin ;
  - modulation de représentativité ;
  - comparaison brute / corrigée par force politique.
- `Second tour`
  - duel par duel ;
  - ligne brute et ligne corrigée ;
  - benchmark expérimental construit à partir des blocs observés aux législatives 2024.
- `Sources`
  - datasets disponibles ;
  - couverture des métadonnées ;
  - résumé par source et par institut ;
  - références historiques chargées pour la correction ;
  - lignes critiques incomplètes.

### Règles de lecture imposées

- premier tour et second tour ne sont jamais mélangés ;
- le premier tour est lu par forces politiques, pas par scénarios nominaux ;
- les hypothèses concurrentes de second tour ne sont pas fusionnées ;
- les blocs génériques ne servent pas à comparer des personnes ;
- le corrigé est séparé du brut ;
- les métadonnées et les références historiques sont visibles avant l'interprétation des courbes.

## Statistiques et redressages implémentés

### Pondération par récence

Formule :

```text
weight = exp(-lambda * age_in_days)
```

### Pondération par taille d'échantillon

Formule :

```text
weight = sqrt(sample_size)
```

### Moyenne pondérée

Le score agrégé utilise le produit :

```text
combined_weight = recency_weight * sample_size_weight
```

Puis :

```text
weighted_average = sum(estimate_percent * combined_weight) / sum(combined_weight)
```

### Incertitude approximative

Une marge d'erreur approximative est calculée à partir de la taille d'échantillon lorsqu'elle est disponible.

### Lissage

Le lissage actuel repose sur une rolling average simple par candidat et scénario.

### House effects

Le house effect est estimé comme l'écart moyen d'un institut par rapport à une baseline locale observée sur le même scénario, le même candidat et le même tour, en excluant l'institut lui-même de la référence.

### Ajustement house effect

```text
adjusted_estimate = raw_estimate - estimated_house_effect
```

## Machine learning expérimental

Le module ML a un objectif limité et explicite : corriger des biais historiques de sondages une fois que des données de vérité terrain et des historiques 2017/2022 seront ajoutés.

Il ne doit pas être présenté comme une prédiction électorale.

### Features prévues

- `polling_company`
- `candidate_party`
- `political_family`
- `days_until_election`
- `sample_size`
- `collection_method`
- `round`
- `scenario_size`
- `publication_month`

### Modèles baseline

- `Ridge`
- `RandomForestRegressor`

### Fichiers concernés

- [features.py](/home/gboileau/Documents/Presidentielle/presidentielle-2027-polls/src/presidentielle2027/ml/features.py)
- [train.py](/home/gboileau/Documents/Presidentielle/presidentielle-2027-polls/src/presidentielle2027/ml/train.py)
- [predict.py](/home/gboileau/Documents/Presidentielle/presidentielle-2027-polls/src/presidentielle2027/ml/predict.py)
- [backtesting.py](/home/gboileau/Documents/Presidentielle/presidentielle-2027-polls/src/presidentielle2027/ml/backtesting.py)

### Données historiques manquantes

Pour rendre ce module utile, il faudra ajouter des datasets dans `data/historical/` incluant :

- les sondages historiques ;
- les contextes méthodologiques ;
- les résultats observés ou écarts constatés ;
- une définition rigoureuse de la variable cible.

## Tests et qualité

### Tests

```bash
.venv/bin/python -m pytest -q
```

Tests présents :

- normalisation CSV ;
- normalisation Excel V1 ;
- normalisation Excel V2 ;
- roundtrip DB minimal ;
- moyenne pondérée ;
- fonctions d'ajustement.

### Lint

```bash
.venv/bin/python -m ruff check src tests
```

### Format

```bash
.venv/bin/python -m ruff format src tests
```

### Makefile

Commandes disponibles :

- `make install`
- `make init-db`
- `make ingest`
- `make normalize`
- `make dashboard`
- `make test`
- `make lint`

Le `Makefile` choisit automatiquement `.venv/bin/python` si ce fichier existe, ce qui évite d'exécuter la CLI avec un `python` système trop ancien.

## Développement dans Codespaces / VS Code

Le repository inclut un fichier [devcontainer.json](/home/gboileau/Documents/Presidentielle/presidentielle-2027-polls/.devcontainer/devcontainer.json) pour simplifier l'usage dans GitHub Codespaces et VS Code Dev Containers.

Cela permet de garantir un environnement Python récent cohérent avec les dépendances du projet.

## Limites connues

- les pages Wikipédia restent des sources secondaires, utiles pour l'amorçage mais insuffisantes pour une pipeline production sans validation ;
- beaucoup de métadonnées fines manquent encore sans lecture des notices Commission des sondages ou des PDF instituts ;
- certains scénarios du premier tour sont reconstruits à partir de vecteurs bruts ;
- les partis et familles politiques de certains blocs génériques doivent encore être harmonisés ;
- la CLI `normalize --input-xlsx` produit aujourd'hui un flux générique utile mais encore perfectible pour gérer explicitement plusieurs exports nommés ;
- la couche ML est une ossature, pas un modèle exploitable de correction historique en production.

## Feuille de route conseillée

Ordre de travail recommandé :

1. fusionner V1 et V2 avec déduplication robuste ;
2. enrichir les métadonnées via notices PDF et Commission des sondages ;
3. stabiliser les `scenario_name` et les mappings candidats/partis/familles ;
4. ajouter un module d'exports analytiques récurrents ;
5. introduire de vraies données historiques 2017 et 2022 ;
6. formaliser un backtesting de correction de biais.

## Avertissement

Les sorties de ce repository ne doivent pas être présentées comme des prédictions certaines de l'élection présidentielle française de 2027.

Ce projet produit des indicateurs exploratoires fondés sur :

- des données publiques parfois incomplètes ;
- des transformations automatiques ;
- des choix méthodologiques perfectibles ;
- un contexte politique évolutif.

Toute lecture sérieuse doit revenir aux sources d'origine et distinguer clairement :

- les données observées ;
- les données reconstruites ;
- les agrégations ;
- les corrections méthodologiques ;
- les expérimentations ML.
