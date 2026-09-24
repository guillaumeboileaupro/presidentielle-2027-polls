# Audit du code — 28/08/2026

Audit technique du dépôt `presidentielle-2027-polls` : architecture, robustesse,
typage, tests, sécurité, hygiène du dépôt. Portée volontairement disjointe de
[TODO_CODEX_PRESIDENTIELLE2027.md](TODO_CODEX_PRESIDENTIELLE2027.md), qui couvre déjà en détail
l'audit de la qualité des données de sondage (unités, canonicalisation des partis,
déduplication) — se référer à ce fichier pour ce périmètre, non répété ici.

Méthodologie : `ruff check`, `mypy`, `pytest --cov`, revue manuelle des fichiers les
plus volumineux, recherche de patterns à risque (`eval`, `pickle`, `except Exception`,
secrets, requêtes sans timeout).

État global au 28/08/2026 (avant corrections) : `ruff check src tests` → 0 erreur.
`pytest` → 111 tests passent (couverture *gate* limitée à un seul module, voir
P1.2). `mypy src` → 154 erreurs.

**Mise à jour du 28/08/2026 (après corrections)** : `ruff check` → 0 erreur.
`pytest` → 163 tests passent (111 → 163, +52 tests ajoutés dans cette passe).
`mypy src` → 45 erreurs restantes (154 → 45, voir détail P1.3). Voir l'état de
chaque point ci-dessous.

---

## P0 — Risques architecturaux à traiter en priorité

- [x] **Monkeypatch global de NumPy au chargement du package** — corrigé.
      Retiré de [src/presidentielle2027/__init__.py](src/presidentielle2027/__init__.py)
      (réduit à `__version__`) et déplacé dans
      [tests/conftest.py](tests/conftest.py#L13-L100), qui n'est chargé que par
      pytest. Vérifié : `pytest` (avec coverage, le cas que le patch corrigeait)
      passe toujours à 120/120, et un import nu de `presidentielle2027` +
      `pandas` (`sum`, `max`, `dropna`, indexation booléenne) fonctionne
      normalement sans le patch. Les consommateurs en production (dashboard,
      CLI, notebooks) n'importent plus jamais cette rustine.

- [x] **Monkeypatch global de l'API Streamlit publique** — documenté et couvert
      par des tests, pattern conservé (justifié : c'est le seul moyen de
      garantir qu'aucune vue n'oublie la sanitisation). Docstring étendue sur
      `install_user_facing_text_guard()` dans
      [table_views.py:201-216](src/presidentielle2027/dashboard/table_views.py#L201-L216)
      expliquant le risque et renvoyant vers les tests. Nouveau fichier
      [tests/test_table_views_guard.py](tests/test_table_views_guard.py) (5 tests) :
      idempotence de l'installation, sanitisation réelle de `st.dataframe`/`st.table`
      avant rendu, `format_func` par défaut sur `st.selectbox` sans écraser un
      `format_func` explicite.

- [~] **Fichier god-object `analysis_2024_projection_logic.py`** — avancé selon
      la méthode « tests d'abord » validée avec vous, portée revue après
      cartographie complète (85 fonctions top-level, dont une fonction de
      rendu unique de **1648 lignes**, `_render_official_constituency_results`
      lignes 2772-4420 — la taille réelle du fichier était encore
      sous-estimée dans le constat initial). Fait :
      - [tests/test_projection_logic_pure_helpers.py](tests/test_projection_logic_pure_helpers.py)
        (37 tests) fige le comportement actuel de 17 fonctions pures
        (parsing de pourcentages/nombres, normalisation de texte, mapping
        force→bloc/coalition) — le filet de sécurité minimal avant tout
        déplacement de code.
      - Extraction à faible risque : `_fetch_wikipedia_html` (un simple GET,
        aucune dépendance métier) déplacée vers
        [ingestion/wiki_api.py](src/presidentielle2027/ingestion/wiki_api.py)
        comme `fetch_wikipedia_html`, testée
        ([tests/test_wiki_api.py](tests/test_wiki_api.py)), le fichier
        god-object l'importe désormais au lieu de la redéfinir.
      Non fait : le découpage complet des ~85 fonctions restantes,
      notamment les grosses fonctions de rendu Streamlit (plusieurs
      dépassent 500 lignes). Un vrai découpage de celles-ci demande une
      vérification visuelle du dashboard (captures d'écran avant/après via
      le skill `run`), pas seulement des tests unitaires — je n'ai pas fait
      cette vérification dans cette passe et je ne voulais pas déplacer du
      code de rendu à l'aveugle. À reprendre par tranches (une fonction de
      rendu à la fois, avec vérification visuelle à chaque étape) plutôt
      qu'en un seul chantier.

- [x] **Logique de canonicalisation des partis dupliquée hors de `canonicalization.py`**
      — investigué en détail (agent Explore dédié sur les 8 fichiers restants
      après `excel_parser.py`/`historical_corrections.py`) avant toute
      modification, pour distinguer les vraies duplications des tables de
      correspondance légitimes en aval (couleurs/logos) et du vocabulaire
      `broad_bloc` volontairement séparé (AGENT.md). Résultat : la plupart
      des 9 fichiers listés dans le constat initial n'avaient **pas** de bug
      (couleurs/logos/`broad_bloc`/nuances législatives 2024 sont des
      consommateurs légitimes de valeurs déjà canonicales ou d'un vocabulaire
      distinct). Quatre vrais bugs trouvés et corrigés :
      1. `analysis_2022.py::WIKI_2022_FORCE_MAP` chargeait le CSV Wikipédia
         2022 **directement**, en contournant `canonicalize_candidate_fields`,
         avec des valeurs `political_family` en anglais (`"left"`, `"green"`,
         `"far_right"`, …) au lieu du vocabulaire français canonique — corrigé
         (traduction vers `gauche`/`écologistes`/`extrême_droite`/etc., zéro
         changement de couleur affichée vérifié : `PS-PP` est la seule valeur
         qui dépendait du fallback famille pour sa couleur, et
         `"left"`/`"gauche"` pointent vers le même code couleur dans
         `colors.py`). `broad_bloc` calculé par copie brute de
         `political_family` au lieu du helper partagé `normalize_broad_bloc`
         — corrigé. **Non renommé** : le code `"PS-PP"` lui-même (Hidalgo,
         Taubira), qui est une clé de jointure délibérée et auto-cohérente
         avec `data/reference/historical_results_2022_presidential_first_round.csv`
         pour ce sous-système de backtesting 2022 isolé (aucune candidature
         Place Publique n'existait en 2022) — le renommer exigerait de
         modifier une donnée de référence électorale réelle, hors périmètre
         d'un audit de code. Testé :
         [tests/test_analysis_2022_canonicalization.py](tests/test_analysis_2022_canonicalization.py)
         (3 tests).
      2. `first_round_raw.py::_party_family_label` recalculait la famille
         politique à partir du code parti avec sa propre table, divergente de
         `canonicalization.py::PARTY_FAMILY_DEFAULTS` (RN affichait
         « Extrême droite » au lieu de « Droite nationale », LFH « Centre »
         au lieu de « Droite gaulliste », LFI « Gauche » au lieu de « Gauche
         radicale ») — simplifié pour toujours utiliser la valeur
         `political_family` déjà canonique. Testé dans
         [tests/test_first_round_wikipedia_blocs.py](tests/test_first_round_wikipedia_blocs.py).
      3. `first_round_raw.py` (migration de sélection de cookie) et
         4. `party_assets.py::resolve_party_logo_filename` codaient chacun en
         dur `"LE"→"EELV"` / `"REN"→"RE"` au lieu d'importer
         `PARTY_ALIASES` — corrigé dans les deux cas (bonus : la migration de
         cookie gère maintenant aussi `MDM`/`MODEM`→`MoDem`, pas seulement
         `LE`). Testé dans
         [tests/test_party_assets.py](tests/test_party_assets.py).
      Non touché, à dessein : `historical_corrections.py` a son **propre**
      `FAMILY_BROAD_BLOC_MAP` local (différent de celui de
      `canonicalization.py`, avec des buckets plus grossiers) — c'est une
      vraie duplication de nom mais je ne l'ai pas fusionnée dans cette passe :
      les deux dicts ont des ensembles de valeurs différents et servent des
      usages distincts (regroupement électoral pour le report de voix vs.
      vocabulaire générique), une fusion mal faite casserait silencieusement
      soit le modèle de second tour soit l'affichage. À traiter séparément,
      avec la même rigueur que ci-dessus, si vous le souhaitez.

---

## P1 — Robustesse et qualité de code

- [x] **`except Exception` silencieux dans `analysis_2024_projection_logic.py`**
      corrigé. Les 6 occurrences loguent désormais via
      `logger.warning(..., exc_info=True)` (fallbacks de lecture fichier→fichier)
      ou `logger.error(..., exc_info=True)` (échec terminal renvoyant un
      DataFrame vide), avec le chemin ou l'URL concernée dans le message. Le
      flux de contrôle (`continue`/valeur de repli) n'a pas changé — seule la
      visibilité de l'échec l'a été, conformément à ce que demandait le
      constat. `ruff check` et la suite de tests (120/120) restent au vert.

- [ ] **Gate de couverture de tests limité à un seul module**
      [pyproject.toml:61](pyproject.toml#L61) — `--cov=presidentielle2027.analytics.adjustment_core
      --cov-fail-under=98` ne mesure que 192 lignes sur ~8300. Mesurée sur tout le
      package, la couverture réelle est de **35 %** (`pytest --cov=presidentielle2027`).
      Zones à 0 % : `ml/*.py`, `dashboard/data_quality.py`,
      `dashboard/scenario_labels.py`, `dashboard/views/{overview,metadata,
      data_quality,pollster_bias,candidate_trends}.py`. Le module de projection
      (P0) est à 7 %.
      → Élargir progressivement le périmètre du gate CI (au moins `analytics/` et
      `extraction/` dans leur totalité), sans viser 98 % partout d'un coup ; prioriser
      les modules à 0 % qui contiennent de la logique (pas du pur affichage).

- [~] **`mypy src` : 154 → 45 erreurs restantes** (avancé, pas terminé).
      Bruit `import-untyped` éliminé via
      [pyproject.toml](pyproject.toml#L87-L94) (`[[tool.mypy.overrides]]` sur
      `pandas.*`, `statsmodels.*`, `sklearn.*`, `plotly.*`, `openpyxl.*`).
      `dashboard/app.py` (le point d'entrée) et
      `dashboard/views/first_round_raw.py` sont désormais à 0 erreur : ajout
      d'un `TypedDict PageConfig` pour `PAGE_CONFIG` dans `app.py` (les valeurs
      hétérogènes du dict littéral s'effondraient en `object`, propageant
      l'erreur jusqu'à l'appel du renderer) et des `cast()` ciblés dans
      `first_round_raw.py` là où les dicts `payload`/`path` de l'extension de
      tendance transportent des `pd.Series`/`float` non typés — aucun changement
      de comportement, uniquement des annotations.
      Restent 45 erreurs, concentrées dans `analysis_2024.py`,
      `analysis_2024_projection_logic.py` (le fichier god-object, volontairement
      non touché, voir P0.3), `second_round_raw.py`, `corrected_dataset.py`,
      `analysis_2022.py`, `table_views.py` (conséquence du monkeypatch Streamlit,
      attendu). `make_wiki_datasets.py` (hors `src/`, non couvert par ce
      `mypy src`) a toujours ses 8 erreurs `attr-defined`/`arg-type` liées à un
      typage laxiste de BeautifulSoup — non traité.
      → Reprendre module par module sur les 45 restants si utile ; rendement
      décroissant au-delà de ce qui a été fait ici.

- [ ] **`pickle.load` pour charger le modèle ML**
      [src/presidentielle2027/ml/predict.py:15](src/presidentielle2027/ml/predict.py#L15)
      désérialise un pipeline scikit-learn via `pickle`. Risque d'exécution de code
      arbitraire si le fichier `.pkl` provient d'une source non maîtrisée ou est
      remplacé par un tiers ayant accès au disque. Actuellement le fichier est
      généré localement par `ml/train.py`, donc risque faible en l'état, mais aucun
      contrôle d'intégrité n'existe.
      → Documenter explicitement que le fichier modèle est un artefact de confiance
      locale, jamais téléchargé depuis une source externe ; envisager `joblib` (pas
      plus sûr en soi) uniquement si un besoin de portabilité apparaît — sinon
      laisser en l'état mais garder la trace de la décision.

- [x] **`print()` au lieu de logging structuré** — corrigé.
      [ingestion/pipeline.py](src/presidentielle2027/ingestion/pipeline.py) utilise
      désormais un logger nommé (`logger.error(..., exc_info=True)` sur échec,
      `logger.info(...)` sur succès) au lieu de `print()`. La commande CLI
      `auto-refresh-pipeline` ([cli.py](src/presidentielle2027/cli.py)) appelle
      `logging.basicConfig(level=logging.INFO, ...)` avant de lancer la boucle,
      pour que ces messages restent visibles dans le terminal comme avec l'ancien
      `print()`. Vérifié : aucun test n'asserte sur la sortie `print()` d'origine.

---

## P2 — Sécurité (points vérifiés, rien de bloquant)

- [x] `.env` correctement ignoré par git, non versionné, `.env.example` sans
      secret réel.
- [x] Aucun accès SQL brut (`session.execute(text(...))`) — tout passe par
      l'ORM SQLAlchemy, pas d'injection SQL identifiée.
- [x] Aucun `eval`/`exec`/`yaml.load` non sécurisé, aucun `subprocess(shell=True)`.
- [x] Tous les appels `requests.get` identifiés passent un `timeout` explicite.
- [ ] **`ml/predict.py`** — voir P1, `pickle.load` à surveiller si la provenance du
      modèle change un jour (téléchargement, artefact CI partagé, etc.).

---

## P3 — Hygiène du dépôt

- [x] **Travail en cours non committé sur `main`** — décision prise avec vous :
      laissé tel quel. `git status` montre toujours des modifications non
      indexées sur `Makefile`, `README.md`, `src/presidentielle2027/cli.py`,
      `src/presidentielle2027/ingestion/pipeline.py` (celui-ci a aussi reçu mes
      changements de logging, voir P1.5 — diff mixte assumé),
      `src/presidentielle2027/ingestion/wikipedia_scraper.py`,
      `tests/test_wiki_api.py` (également enrichi par mes tests, voir P0.3),
      plusieurs CSV sous `data/processed/` et à la racine, ainsi qu'un dossier
      `packaging/` non suivi. Non touché intentionnellement.
- [x] **Notebook checkpoints** — présents sur le disque
      (`notebooks/.ipynb_checkpoints/`, `.virtual_documents/`) mais correction
      initiale erronée : vérification faite avec `git ls-files`, ils ne sont **pas**
      suivis par git (déjà couverts par `.gitignore:6-7`). Rien à faire.
- [x] `dist/presidentielle2027_0.1.0_amd64.deb` et `build/` sont bien ignorés par
      git (`git ls-files dist/ build/` ne retourne rien) — présents localement
      uniquement, pas de risque de pollution de l'historique.

---

## Suivi

Fait le 28/08/2026, en deux passes :

**Passe 1 (corrections mécaniques sans arbitrage nécessaire)** : P0.1
(monkeypatch NumPy déplacé en test), P0.2 (guard Streamlit documenté + testé),
P1.1 (except silencieux loggés), P1.3 partiel (mypy 154 → 45, `app.py` et
`first_round_raw.py` à 0 erreur), P1.5 (logging au lieu de print).

**Passe 2 (après votre arbitrage sur P0.3/P0.4/P3)** :
- P0.3 avancé selon la méthode « tests d'abord » : 37 tests de
  caractérisation + extraction du scraping HTTP vers `ingestion/`. Le
  découpage complet des ~85 fonctions restantes (dont une fonction de rendu
  de 1648 lignes) reste à faire par tranches avec vérification visuelle —
  voir le détail dans la section P0.3 ci-dessus, ce n'est pas un oubli mais
  une limite de ce qui est sûr à faire sans capture d'écran du dashboard.
- P0.4 traité : investigation dédiée sur les 8 fichiers suspectés, 4 bugs
  réels trouvés et corrigés (vocabulaire anglais résiduel dans les données
  2022, `broad_bloc` mal calculé, deux alias codés en dur), 5 fichiers
  innocentés (consommateurs légitimes de valeurs déjà canonicales ou du
  vocabulaire `broad_bloc` séparé). Le doublon de nom `FAMILY_BROAD_BLOC_MAP`
  entre `canonicalization.py` et `historical_corrections.py` reste non
  fusionné à dessein (valeurs différentes, usages distincts).
- P3 : travail non committé laissé tel quel, à votre demande.

`ruff check` et `pytest` verts après chaque étape ; 111 → 163 tests au total.

**Restent ouverts, sans besoin d'arbitrage supplémentaire pour les reprendre :**

- Suite de P0.3 (découpage des fonctions de rendu restantes, par tranches).
- P1.2 (élargir le gate de couverture CI) et le reliquat de P1.3 (45 erreurs
  mypy restantes) — rendement décroissant, à reprendre si utile.
- P0.4 sur `historical_corrections.py`/`FAMILY_BROAD_BLOC_MAP` si vous
  voulez pousser la consolidation plus loin.

Le reste de ce fichier n'aborde pas la qualité des données de sondage (unités,
doublons, canonicalisation métier) : voir
[TODO_CODEX_PRESIDENTIELLE2027.md](TODO_CODEX_PRESIDENTIELLE2027.md), toujours
d'actualité.

---

## Revue du 24/09/2026 (arbre de travail complet, y compris le travail non committé)

`origin/main` était déjà à jour (0 commit d'écart). Revue du diff complet, dont les
changements de parseur, de normalizer, de la vue Wikipédia 2027 et du dossier
`packaging/` qui ne venaient pas de la passe précédente. Le correctif de fond du
travail en cours est bon : `pd.read_html(..., decimal=",", thousands=None)` corrige
la lecture de `1,5` en `15`. Bugs trouvés, vérifiés sur les données réelles
(`data/raw`, 248 sondages, 3305 → 3252 lignes) puis corrigés :

- [x] **`replace_all_polls=True` vidait la base sur entrée vide** — reproduit
      (8 sondages → 0). Le refresh automatique horaire aurait effacé toute la base
      au premier fetch/parse vide. `normalize_to_database` lève désormais
      `ValueError` avant toute suppression. Test :
      `test_database_full_replacement_refuses_empty_snapshot`.
- [x] **Préfixe `<1` conservé dans les noms de candidats** (`"<1 Bonnal"`,
      `"<1 Bouamrane"`) — corrigé via `_SCORE_PREFIX_PATTERN`.
- [x] **Borne `<X` codée en dur à `1.0`** et **héritée par les lignes éclatées**
      (`"2 Lisnard"` recevait `upper_bound_percent=1.0`) — la borne est lue dans la
      cellule (`_bounded_upper_percent`), les lignes éclatées ne l'héritent plus et
      gardent le diagnostic de date. Tests table-level dans
      `tests/test_percentage_corrections.py` (mutation vérifiée : le test échoue
      avec l'ancien motif).
- [x] **Candidat fantôme `Unnamed: 17_level_1`** (53 lignes vides `not_tested`, déjà
      présentes dans `HEAD`) — une cellule vide sous une colonne sans en-tête est
      ignorée. Aucune donnée perdue : 0 texte, 0 estimation, 248 sondages inchangés.
- [x] **Tableau au format Wikipédia : `<1` affiché « — » (non testé)** — affiche
      désormais `<1`. Test dans `tests/test_wikipedia_2027_table.py`.
- [x] **Lanceur `.deb` : code périmé après mise à jour** — `.initialized` empêchait
      de recopier `make_wiki_datasets.py` et `scripts/`, donc le correctif décimal
      n'atteignait jamais les installations existantes. Le lanceur les rafraîchit à
      chaque démarrage sans toucher aux données utilisateur. Vérifié par
      simulation d'une mise à jour.

Non fait / à surveiller :
- Le CSV persisté `data/processed/wikipedia_2027_polls_normalized_v2.csv` et la base
  contiennent encore les 2 noms en `<` et les 53 `Unnamed` jusqu'au prochain
  `make refresh` (non lancé : appelle Wikipédia et modifie des fichiers de données
  suivis). Le dashboard n'est pas affecté : il re-parse `data/raw` et remplace les
  lignes `RAW-FR-`/`RAW-SR-`.
- `.deb` non construit dans cette passe (`make deb` copie tout le `.venv`, jupyterlab
  compris, malgré le commentaire de `build-deb.sh` qui dit le contraire).
- 45 erreurs mypy restantes, inchangées.

Nouveau skill : `.claude/skills/canonical-party-vocabulary/SKILL.md`
(vocabulaires `political_family` / `broad_bloc` / nuances 2024 à ne pas fusionner,
double `FAMILY_BROAD_BLOC_MAP`, clé `PS-PP` du backtest 2022), référencé dans
`CLAUDE.md` et `AGENTS.md`. Total : 172 tests, `ruff` propre.

### Suite du 24/09/2026 : scraping réel, dashboard piloté, `.deb` construit

Éléments laissés « non faits » ci-dessus, maintenant exécutés et vérifiés.

**Scraping (`make refresh`, réseau réel, sauvegarde préalable des données)**
- Avant → après, CSV persisté : 3359 → 3306 lignes (−53 = exactement les candidats
  fantômes `Unnamed`), 279 → 279 sondages/scénarios, noms en `<` 2 → 0, `Unnamed`
  53 → 0. Base SQLite : 3268 → 3215 résultats, 279 sondages inchangés.
- Idempotence : un second `make refresh` produit un CSV, des exports et un rapport de
  correction identiques octet pour octet (SHA-256), et la même empreinte en base.
- Plausibilité (pas seulement les tests) : totaux de scénarios 99,0–100,5 % au premier
  tour, 100,0 % au second ; 0 valeur > 100 ou < 0 ; 0 date de terrain manquante ;
  aucun jeton hérité (`PS-PP`, `LE`, `EPR`, `REN`, `centre_left`, `green`).
- Tables Wikipédia source inchangées depuis l'extraction du matin (387 / 1157 / 149
  lignes). Les 8 lignes écartées par le `drop_duplicates` de fusion sont toutes déjà
  marquées `technical_duplicate` (comportement antérieur, non modifié).

**Dashboard lancé et regardé dans Chromium headless** — trois bugs trouvés :
- [x] **`DASHBOARD_HOST`/`DASHBOARD_PORT` ignorés** : `run-dashboard` passait
      `--server.port/address` dans `args` (argv du script) au lieu de `flag_options`.
      Le dashboard écoutait sur `0.0.0.0:8501` quoi qu'on configure, donc exposé sur
      tout le réseau. Corrigé (`load_config_options` + `flag_options`), vérifié avec
      `ss` : `127.0.0.1:8599` seulement, injoignable par l'adresse LAN. Test dans
      `tests/test_cli_dashboard.py`. Le lanceur du `.deb` défaut désormais à
      `127.0.0.1`. Attention : sans cette correction, le défaut de `config.py`
      (`0.0.0.0`) est maintenant réellement appliqué en développement/Docker.
- [x] **Contrôle « sommes de 74,0 % à 100,5 % » trompeur** : il excluait les blocs
      génériques (`NFP`…) alors qu'ils font partie du scénario ; le 26 % d'une cellule
      fusionnée (Harris, `RAW-FR-HARRIS[H]-03-049`) était bien conservé sous `NFP`,
      total réel 100,0 %. Affiche maintenant 99,0–100,5 %. 247 scénarios affichés =
      248 moins le bloc « RÉSULTATS » 2022, exclu volontairement des vues sondages.
- [x] **Colonne Échantillon du tableau Wikipédia** affichait `1943.000000` ; affiche
      `1 943`.

**`.deb`** : construit (`make deb`, 1 min 23, 202 Mo), extrait et exécuté avec son
propre venv et un `HOME` isolé : aide du CLI, `verify-coverage` sur les données
livrées, dashboard sain, écoute locale uniquement, 0 erreur dans le log. Non testé :
`sudo apt install` réel et l'entrée de menu `.desktop`.

Limite de la vérification visuelle : les captures headless demandent un préchauffage
(le premier chargement à froid rend une page presque vide) ; seule la vue « premier
tour » a été regardée, pas les onze autres.

Total : 175 tests, `ruff` propre, mypy inchangé à 45 erreurs.
