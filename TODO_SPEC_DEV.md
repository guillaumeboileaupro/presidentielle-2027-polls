# TODO_SPEC_DEV.md

## Objectif

Ce document fixe la feuille de route technique de `presidentielle-2027-polls`.
Il complète `README.md` et `AGENT.md` avec une vision de développement concrète, priorisée et vérifiable.

Le projet ne doit pas devenir un outil de prédiction électorale certaine.
Il doit rester un pipeline reproductible d'ingestion, normalisation, analyse, redressage exploratoire et visualisation de sondages publics.

## Vision technique

```text
presidentielle-2027-polls = pipeline reproductible d'analyse exploratoire des sondages publics 2027
```

Le projet doit privilégier:

1. la traçabilité des sources;
2. la séparation entre données brutes, transformées et dérivées;
3. la reproductibilité des calculs;
4. la clarté méthodologique;
5. l'incertitude explicite;
6. la prudence dans l'interprétation politique;
7. une architecture Python maintenable.

## Périmètre coeur

### Core obligatoire

- Ingestion de sources publiques.
- Conservation des URLs et métadonnées de provenance.
- Parsing de sources semi-structurées.
- Normalisation vers un schéma tabulaire stable.
- Persistance SQLite par défaut.
- Compatibilité future PostgreSQL via `DATABASE_URL`.
- Calcul de moyennes pondérées.
- Calculs simples de tendances et lissages.
- Estimation explicite de corrections méthodologiques.
- Dashboard Streamlit exploratoire.
- CLI Typer utilisable.
- Tests de normalisation, d'analytics et de persistance.
- Documentation claire des limites.

### Hors périmètre coeur

Ces éléments doivent rester expérimentaux ou optionnels:

- prédiction électorale;
- modèle ML présenté comme prévision fiable;
- scraping non traçable;
- correction opaque sans source historique;
- fusion automatique de scénarios politiquement différents;
- interprétation causale de simples redressages;
- publication de classements sans avertissement méthodologique.

## Règles méthodologiques non négociables

- Ne jamais présenter une sortie comme une prédiction certaine.
- Toujours distinguer brut, reconstruit, agrégé, corrigé et expérimental.
- Garder les sources et métadonnées autant que possible.
- Ne pas inventer de données manquantes.
- Ne pas transformer une hypothèse en fait.
- Ne pas mélanger premier tour et second tour.
- Ne pas fusionner des duels de second tour différents.
- Ne pas comparer directement candidats nominatifs et blocs génériques comme s'ils étaient de même nature.
- Toute correction doit être documentée avec sa formule, sa source et sa limite.

## Roadmap technique

## v0.1 - Repo propre et reproductible

Objectif: rendre le projet propre à cloner, installer, tester et lancer.

### Tâches

- [ ] Remplacer les chemins absolus du README par des chemins relatifs.
- [ ] Vérifier que `make install` fonctionne dans un venv propre.
- [ ] Vérifier que `make test` fonctionne après installation.
- [ ] Vérifier que `make lint` fonctionne.
- [ ] Vérifier que `make dashboard` démarre avec le fallback prévu.
- [ ] Vérifier que `.env.example` contient les variables minimales utiles.
- [ ] Ajouter une section README `Quick start` courte et fiable.
- [ ] Ajouter une section README `Known limitations` maintenue.
- [ ] Ajouter une CI GitHub Actions minimale.
- [ ] Vérifier que la CI exécute installation, lint et tests.

### Critères de validation

- [ ] Un clone propre peut installer le projet avec `make install`.
- [ ] `make test` passe localement.
- [ ] `make lint` passe localement ou les écarts restants sont documentés.
- [ ] Le README ne contient plus de chemins locaux `/home/...`.
- [ ] La CI échoue clairement si les tests ou le lint cassent.

## v0.2 - Pipeline data fiable

Objectif: stabiliser l'ingestion, la normalisation et la couverture des données.

### Tâches

- [ ] Fusionner les extractions Wikipédia V1 et V2 avec déduplication robuste.
- [ ] Stabiliser les identifiants de sondages.
- [ ] Stabiliser les noms de scénarios.
- [ ] Stabiliser les mappings candidat / parti / famille politique.
- [ ] Améliorer la gestion des candidats manquants.
- [ ] Améliorer la détection des doublons.
- [ ] Enrichir les métadonnées via notices Commission des sondages quand disponibles.
- [ ] Ajouter ou consolider le registre des sources web suivies.
- [ ] Documenter le niveau de confiance d'extraction par source.
- [ ] Ajouter des tests pour chaque format de workbook supporté.
- [ ] Ajouter des tests sur les cas incomplets.
- [ ] Ajouter des tests de non-régression sur `verify-coverage`.

### Critères de validation

- [ ] Les données V1 et V2 ne produisent pas de doublons non documentés.
- [ ] Les candidats attendus sont détectés ou signalés explicitement.
- [ ] Les scénarios incomplets sont visibles dans un rapport.
- [ ] Les sources sont traçables par URL ou identifiant documenté.
- [ ] Les transformations sont reproductibles.

## v0.3 - Analytics et corrections prudentes

Objectif: rendre les agrégations et redressages lisibles, testés et prudents.

### Tâches

- [ ] Documenter tous les paramètres de pondération.
- [ ] Exposer clairement la pondération par récence.
- [ ] Exposer clairement la pondération par taille d'échantillon.
- [ ] Tester les moyennes pondérées sur cas simples.
- [ ] Tester les bornes d'incertitude approximatives.
- [ ] Stabiliser le calcul de house effects.
- [ ] Séparer clairement corrections par institut, par famille politique et par temporalité.
- [ ] Documenter la source historique de chaque correction.
- [ ] Ajouter des exports analytiques versionnés dans `data/exports/`.
- [ ] Ajouter une commande CLI d'export analytique récurrent si nécessaire.

### Critères de validation

- [ ] Chaque correction a une formule claire.
- [ ] Chaque correction a une source ou une justification documentée.
- [ ] Les exports indiquent s'ils sont bruts, agrégés, corrigés ou expérimentaux.
- [ ] Les tests couvrent les fonctions analytiques critiques.

## v0.4 - Dashboard sérieux et lisible

Objectif: offrir une visualisation exploratoire sans ambiguïté méthodologique.

### Tâches

- [ ] Garder une séparation stricte entre premier tour et second tour.
- [ ] Garder une séparation stricte entre brut et corrigé.
- [ ] Garder les duels de second tour séparés.
- [ ] Ajouter ou stabiliser une page `Méthodologie`.
- [ ] Ajouter ou stabiliser une page `Sources`.
- [ ] Afficher les limites directement dans l'interface.
- [ ] Afficher la fraîcheur des données.
- [ ] Afficher les métadonnées manquantes critiques.
- [ ] Vérifier le fallback dashboard: base SQLite, CSV V2, CSV V1, sample fictif.
- [ ] Ajouter des tests ou checks légers sur le chargement des datasets dashboard.
- [ ] Éviter toute formulation de type prédiction certaine.

### Critères de validation

- [ ] Le dashboard démarre même sans base remplie.
- [ ] Le sample fictif est clairement signalé comme fictif.
- [ ] Les graphes ne mélangent pas des objets politiques différents.
- [ ] Les limites méthodologiques sont visibles avant interprétation forte.

## v0.5 - ML expérimental sécurisé

Objectif: rendre le module ML strictement expérimental, mais techniquement propre.

### Tâches

- [ ] Interdire la création silencieuse de `observed_bias = 0.0` si la cible manque.
- [ ] Remplacer ce comportement par une erreur explicite.
- [ ] Ajouter éventuellement un flag `--allow-synthetic-target` pour tests uniquement.
- [ ] Définir une variable cible réelle avant tout entraînement utile.
- [ ] Ajouter des datasets historiques 2017 et 2022 si disponibles.
- [ ] Documenter les features réellement utilisées.
- [ ] Documenter les métriques.
- [ ] Documenter le chemin des artefacts modèles.
- [ ] Ajouter du backtesting contrôlé.
- [ ] Empêcher l'affichage du ML comme prévision électorale dans le dashboard.

### Critères de validation

- [ ] Un entraînement sans cible réelle échoue clairement.
- [ ] Les métriques sont sauvegardées et lisibles.
- [ ] Le modèle n'est jamais présenté comme prédiction de résultat.
- [ ] Les données synthétiques restent limitées aux tests et démos.

## v1.0 - Projet maintenable

Objectif: avoir une base publique propre, maintenable et compréhensible.

### Tâches

- [ ] Finaliser README court et fiable.
- [ ] Finaliser AGENT.md si les règles évoluent.
- [ ] Ajouter un CHANGELOG.
- [ ] Ajouter une politique de versionnement.
- [ ] Ajouter une documentation `docs/` si le README devient trop long.
- [ ] Stabiliser les notebooks et leurs dépendances.
- [ ] Vérifier que les notebooks s'exécutent avec le kernel documenté.
- [ ] Ajouter des jeux de données de test minimaux et clairement fictifs.
- [ ] Garder les gros artefacts hors Git si nécessaire.
- [ ] Vérifier la licence et l'attribution des sources.

### Critères de validation

- [ ] Un nouveau contributeur comprend le projet depuis README + AGENT + TODO_SPEC_DEV.
- [ ] Les commandes principales fonctionnent.
- [ ] Les limites sont documentées.
- [ ] Les sources sont traçables.
- [ ] Le projet peut être présenté comme outil exploratoire sérieux.

## Backlog détaillé

## Documentation

- [ ] Supprimer tous les chemins absolus du README.
- [ ] Remplacer les liens locaux par des chemins relatifs.
- [ ] Ajouter une introduction courte pour lecteurs non techniques.
- [ ] Ajouter une introduction technique pour contributeurs.
- [ ] Documenter le pipeline complet.
- [ ] Documenter le modèle de données.
- [ ] Documenter les limites de Wikipédia comme source secondaire.
- [ ] Documenter les notices Commission des sondages comme source primaire à privilégier.
- [ ] Documenter la différence entre sondage, scénario, candidat, parti et famille politique.
- [ ] Documenter brut vs corrigé.
- [ ] Documenter le statut expérimental du ML.

## Ingestion

- [ ] Stabiliser ingestion Wikipédia FR.
- [ ] Stabiliser ingestion Wikipédia EN.
- [ ] Conserver `revision_id`, `page_id` et date de récupération.
- [ ] Vérifier le cache HTML local.
- [ ] Ajouter ingestion notices PDF Commission des sondages.
- [ ] Ajouter extraction minimale des métadonnées depuis PDF si possible.
- [ ] Garder chaque source brute dans `data/raw/`.
- [ ] Journaliser les ingestions dans `ingestion_logs`.

## Extraction / normalisation

- [ ] Stabiliser détection workbook V1.
- [ ] Stabiliser détection workbook V2.
- [ ] Isoler les parseurs par format.
- [ ] Ajouter des tests sur workbooks incomplets.
- [ ] Ajouter des tests sur colonnes inattendues.
- [ ] Harmoniser les noms de candidats.
- [ ] Harmoniser les partis.
- [ ] Harmoniser les familles politiques.
- [ ] Définir une stratégie pour les blocs génériques.
- [ ] Conserver `raw_text_context` pour audit.
- [ ] Conserver `extraction_confidence` conservateur.

## Base de données

- [ ] Vérifier les modèles SQLAlchemy.
- [ ] Vérifier la création SQLite.
- [ ] Vérifier la compatibilité PostgreSQL future.
- [ ] Ajouter migrations Alembic si le schéma évolue.
- [ ] Vérifier les contraintes d'unicité pertinentes.
- [ ] Éviter les suppressions destructives silencieuses.
- [ ] Documenter les tables principales.

## Analytics

- [ ] Tester `compute_weighted_polling_averages` sur cas simple.
- [ ] Tester les poids de récence.
- [ ] Tester les poids de taille d'échantillon.
- [ ] Tester le comportement avec `sample_size` manquant.
- [ ] Tester le comportement avec dates manquantes.
- [ ] Séparer moyennes par tour.
- [ ] Séparer moyennes par scénario ou famille politique selon l'usage.
- [ ] Ajouter exports datés si nécessaire.

## Corrections / ajustements

- [ ] Documenter correction historique 2022.
- [ ] Documenter benchmark législatives 2024.
- [ ] Ajouter datasets historiques propres.
- [ ] Vérifier que les corrections ne modifient pas les données brutes.
- [ ] Stocker les corrections dans une couche séparée.
- [ ] Tester les fonctions d'ajustement.
- [ ] Afficher clairement les corrections dans le dashboard.

## Dashboard

- [ ] Vérifier le chargement SQLite.
- [ ] Vérifier le fallback CSV V2.
- [ ] Vérifier le fallback CSV V1.
- [ ] Vérifier le fallback sample fictif.
- [ ] Signaler visuellement le mode sample fictif.
- [ ] Ajouter page méthodologie.
- [ ] Ajouter page sources.
- [ ] Ajouter filtres par institut.
- [ ] Ajouter filtres par période.
- [ ] Garder les graphes lisibles.
- [ ] Éviter les couleurs ambiguës.
- [ ] Garder les logos comme aide visuelle, pas comme donnée.

## ML expérimental

- [ ] Retirer la cible factice silencieuse.
- [ ] Ajouter une erreur claire si la cible manque.
- [ ] Ajouter tests sur `train-adjustment-model` sans cible.
- [ ] Ajouter tests sur `train-adjustment-model` avec cible de test.
- [ ] Documenter le statut expérimental.
- [ ] Documenter les métriques.
- [ ] Documenter les limites.
- [ ] Ne jamais afficher ces sorties comme prédiction certaine.

## Tests et qualité

- [ ] Ajouter CI GitHub Actions.
- [ ] Exécuter `pytest` en CI.
- [ ] Exécuter `ruff check` en CI.
- [ ] Éventuellement exécuter `mypy` en CI quand le typage est prêt.
- [ ] Ajouter tests pour CLI principales.
- [ ] Ajouter tests pour ingestion mockée.
- [ ] Ajouter tests pour normalisation.
- [ ] Ajouter tests pour analytics.
- [ ] Ajouter tests pour ajustements.
- [ ] Ajouter tests pour dashboard data loading.

## Commandes de référence à maintenir

```bash
make install
make init-db
make ingest
make normalize
make dashboard
make test
make lint
make format
make notebook-kernel
make notebook
make wiki-datasets
```

Ces commandes doivent rester simples et éviter les surprises liées au Python système.

## Prochaines tâches recommandées

Ordre conseillé:

1. Nettoyer les chemins absolus du README.
2. Ajouter la CI minimale.
3. Corriger `train-adjustment-model` pour refuser une cible absente.
4. Ajouter un test pour cette erreur ML.
5. Renforcer les tests `verify-coverage`.
6. Stabiliser la déduplication V1/V2.
7. Ajouter une page méthodologie au dashboard.
8. Ajouter une documentation concise sur les sources primaires et secondaires.

## Règles pour agents de code

Avant modification:

1. Lire `AGENT.md`.
2. Lire ce fichier.
3. Identifier la couche touchée: ingestion, extraction, db, analytics, adjustments, ml, dashboard ou docs.
4. Vérifier si la modification change une hypothèse méthodologique.
5. Préférer le plus petit changement utile.

Après modification:

1. Résumer les fichiers changés.
2. Indiquer les validations lancées.
3. Indiquer les validations non lancées.
4. Indiquer les risques méthodologiques.
5. Ne pas présenter une hypothèse comme résultat fiable.

## Définition de terminé

Une tâche est terminée seulement si:

- le comportement attendu est documenté;
- les sources ou hypothèses sont traçables;
- les tests pertinents sont ajoutés ou lancés;
- les limites sont explicites;
- les données brutes ne sont pas écrasées;
- les sorties ne sont pas présentées comme des prédictions certaines;
- les changements restent reproductibles.
