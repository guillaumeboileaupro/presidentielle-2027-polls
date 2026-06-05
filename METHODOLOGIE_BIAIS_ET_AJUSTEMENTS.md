# Méthodologie des biais, ajustements et prolongations

Ce document décrit la méthode effectivement codée dans le projet pour :

- construire les biais historiques ;
- corriger les sondages de premier tour 2027 ;
- corriger les hypothèses de second tour à partir des législatives 2024 ;
- produire les ajustements polynomiaux visibles dans les graphes ;
- générer la prolongation exploratoire en pointillé jusqu’à l’élection.

Le contenu ci-dessous décrit le code tel qu’il fonctionne actuellement, pas une version idéale ou théorique.

## 1. Fichiers et points d’entrée

Les calculs sont principalement répartis entre :

- [historical_corrections.py](src/presidentielle2027/analytics/historical_corrections.py)
- [trends.py](src/presidentielle2027/analytics/trends.py)
- [biases.py](src/presidentielle2027/dashboard/views/biases.py)
- [corrected_dataset.py](src/presidentielle2027/dashboard/views/corrected_dataset.py)
- [first_round_raw.py](src/presidentielle2027/dashboard/views/first_round_raw.py)
- [second_round_raw.py](src/presidentielle2027/dashboard/views/second_round_raw.py)
- [projection_scenarios.py](src/presidentielle2027/dashboard/views/projection_scenarios.py)

Les fichiers de référence utilisés par le moteur de correction sont :

- [historical_polls_2022_first_round.csv](data/reference/historical_polls_2022_first_round.csv)
- [historical_results_2022_presidential_first_round.csv](data/reference/historical_results_2022_presidential_first_round.csv)
- [historical_results_2024_legislatives_blocs.csv](data/reference/historical_results_2024_legislatives_blocs.csv)
- [historical_results_2024_legislatives_seats.csv](data/reference/historical_results_2024_legislatives_seats.csv)
- [manual_first_round_biases.csv](data/reference/manual_first_round_biases.csv)
- [manual_second_round_bloc_overrides.csv](data/reference/manual_second_round_bloc_overrides.csv)
- [polling_representativity_factors.csv](data/reference/polling_representativity_factors.csv)

Des données supplémentaires issues des extractions Wikipédia sont également chargées dans certaines vues :

- [sondages_presidentielle_2022_wikipedia_tables.csv](sondages_presidentielle_2022_wikipedia_tables.csv)
- [sondages_presidentielle_2027_wikipedia_tables.csv](sondages_presidentielle_2027_wikipedia_tables.csv)
- [sondages_legislatives_2024_wikipedia_tables.csv](sondages_legislatives_2024_wikipedia_tables.csv)
- `sondages_legislatives_2024_wikipedia_tables.csv` pour les tableaux structurés Wikipédia 2024
- fichiers `visual_rows` / `layout_lines` du dossier `data/imported_wiki_zip_complete/` seulement en secours ou pour l’inspection visuelle

## 2. Dates électorales de référence

Les dates codées en dur sont :

- `FIRST_ROUND_ELECTION_DATE = 2022-04-10`
- `LEGISLATIVE_2024_ELECTION_DATE = 2024-06-30`
- `CURRENT_ELECTION_DATE = 2027-04-11`

Elles servent à calculer :

- la distance au scrutin ;
- les fenêtres temporelles ;
- l’éligibilité à la prolongation exploratoire ;
- les repères historiques visibles dans les graphes.

## 3. Normalisation des partis et blocs

Le projet utilise deux niveaux de normalisation.

### 3.1. Force électorale de premier tour

Fonction :

- `normalize_force_label(candidate_party, political_family)`

Exemples de normalisation :

- `LFI`, `NFP` -> `LFI`
- `PS`, `PS-PP`, `PP` -> `PS-PP`
- `RE`, `HOR`, `MODEM`, `MDM` -> `ENS`
- `UDR` -> `RN`
- `green`, `greens`, `écologistes` -> `EELV`

Cette normalisation sert à regrouper les lignes de sondage avant calcul des biais.

### 3.2. Bloc large pour le second tour

Fonction :

- `normalize_broad_bloc(candidate_party, political_family)`

Blocs cibles :

- `gauche`
- `centre`
- `droite`
- `extrême_droite`
- `autres`

Cette normalisation est utilisée pour :

- la matrice de transfert du second tour ;
- le benchmark issu des législatives 2024 ;
- l’agrégation institutionnelle par grands blocs.

## 4. Calcul des erreurs historiques 2022

Le cœur du premier tour repose sur l’historique 2022.

### 4.1. Fusion historique

Le contexte est construit par :

- `compute_first_round_correction_context(reference_dir, current_frame=None)`

Le code charge :

1. les sondages historiques 2022 ;
2. les résultats officiels 2022 ;
3. les facteurs de représentativité ;
4. éventuellement la dynamique courante 2027 si un `current_frame` est fourni ;
5. les overrides manuels de `manual_first_round_biases.csv` quand un correctif explicite est jugé plus robuste que le signal 2022 seul.

La table fusionnée contient notamment :

- `force_label`
- `fieldwork_end_date`
- `estimate_percent`
- `result_percent`
- `days_until_election`
- `days_bucket`
- `historical_error`

Important :

- par défaut, le premier tour conserve 2022 comme historique de fond ;
- mais si `manual_first_round_biases.csv` contient une ligne pour une force, ses composantes remplacent la correction automatique ;
- cela permet notamment de neutraliser une correction automatique jugée trop fragile pour une force donnée ;
- dans l'état actuel du repo, le RN utilise un override dédié sur la composante `legislative_2024_bias_component` pour refléter la surestimation observée dans les sondages nationaux 2024 par rapport au résultat du 30 juin 2024.
- en revanche, le premier tour 2027 intègre désormais un composant distinct de `biais blocs 2024`, calculé à partir des sondages nationaux des législatives 2024 par grands blocs ;
- ce composant peut être surchargé force par force via `manual_first_round_biases.csv` si l'interprétation métier retenue diffère de l'extraction brute ;
- dans l'état actuel du repo, cet override RN est stocké dans `data/reference/manual_first_round_biases.csv`.
- quand un biais 2024 de bloc existe, il sert désormais d'ancre prioritaire pour 2027 et les composantes issues de 2022 sont rétrogradées en bruit de fond pondéré.

Précision méthodologique :

- pour mesurer le biais des sondages nationaux 2024, on compare désormais les colonnes sondages à la ligne `Résultats` de la même table Wikipédia nationale ;
- sur cette base comparable, la colonne `RN et alliés` se lit à `29,26 %` au résultat du 30 juin 2024 ;
- les agrégats ministériels plus larges comme `34,44 %` pour le bloc RN / extrême droite restent utiles pour d'autres lectures institutionnelles, mais pas pour comparer directement la colonne Wikipédia `RN et alliés` ;
- le premier tour 2027 utilise donc une correction de biais sur les sondages ;
- la sous-conversion RN en sièges 2024 sert surtout de signal institutionnel pour les hypothèses de second tour, pas de score brut à recopier ;
- le biais national 2024 de blocs est désormais relu depuis `sondages_legislatives_2024_wikipedia_tables.csv` pour nourrir la correction 2024.
- un override manuel de second tour peut aussi être appliqué par bloc via `manual_second_round_bloc_overrides.csv` lorsque les tableaux de projections en sièges montrent une surestimation trop forte pour être laissée au seul `vote_seat_gap`.

Concrètement, le premier tour 2027 combine maintenant :

- les composantes 2022 `structurel + temporel + trajectoire` ;
- un composant `legislative_2024_bias_component` dérivé du biais national de blocs 2024.
- si une ancre 2024 existe pour la force ou son bloc, les composantes 2022 sont pondérées à `0,40` ;
- dans le même cas, la composante 2024 garde un poids plein à `1,00`.

### 4.2. Formule d’erreur historique

La formule codée est :

```python
historical_error = estimate_percent - result_percent
```

Interprétation :

- erreur positive : le sondage surestime la force ;
- erreur négative : le sondage sous-estime la force.

## 5. Fenêtres temporelles

Le temps avant scrutin est converti en classes par :

- `compute_days_bucket(days_until_election)`

Les buckets utilisés sont :

- `0_30`
- `31_90`
- `91_180`
- `181_plus`

Ils servent au biais temporel du premier tour.

## 6. Trois biais du premier tour 2027

Le moteur produit trois composantes explicites :

- `structural_bias_component`
- `temporal_bias_component`
- `trajectory_bias_component`

Le tout est ensuite additionné dans :

- `historical_correction`

Puis appliqué au score brut pour produire :

- `historically_corrected_estimate`

### 6.1. Biais structurel

Il est calculé dans `_build_bias_catalog(...)`.

Le code commence par construire une erreur moyenne pondérée via :

- `_weighted_error_mean(force_group)`

L’idée est de donner plus de poids aux sondages historiques les plus proches du vote.

La formule finale du biais structurel est :

```python
structural_bias = -weighted_error_mean
```

Interprétation :

- si une force a été historiquement surestimée, la correction est négative ;
- si elle a été sous-estimée, la correction est positive.

### 6.2. Biais temporel

Le code calcule d’abord, pour chaque force et bucket temporel :

```python
historical_error_bucket_mean = mean(historical_error)
```

Puis le biais temporel appliqué est :

```python
temporal_bias = -(bucket_error_mean - weighted_error_mean)
```

Interprétation :

- il ne s’agit pas d’un second biais total indépendant ;
- il s’agit d’un ajustement relatif à la position temporelle courante par rapport au biais structurel moyen.

Le but est d’éviter qu’une force soit corrigée de la même façon à 18 mois et à 10 jours du vote.

### 6.3. Biais de trajectoire

Le moteur compare :

- la pente récente des sondages 2027 ;
- la dynamique historique des erreurs.

Fonctions mobilisées :

- `_compute_recent_slope(...)`
- `_compute_historical_error_momentum(...)`
- `_build_current_force_dynamics(...)`

La formule codée est :

```python
trajectory_bias = clip((current_slope - historical_momentum) * 21.0, -4.0, 4.0)
```

avec bornage :

- minimum `-4.0`
- maximum `+4.0`

Interprétation :

- si la dynamique récente semble plus favorable que ce que racontait l’historique d’erreur, la correction monte ;
- si elle semble moins favorable, la correction baisse.

Ce terme est volontairement borné pour éviter qu’une trajectoire courte produise une explosion du score corrigé.

## 7. Correction totale du premier tour

La correction totale appliquée est :

```python
historical_correction =
    structural_bias_component
    + temporal_bias_component
    + trajectory_bias_component
```

Le score corrigé final est :

```python
historically_corrected_estimate =
    clip(estimate_percent + historical_correction, 0.0, 100.0)
```

Le bornage à `[0, 100]` est appliqué systématiquement.

## 8. Statuts méthodologiques

Le catalogue des biais attribue un statut par force.

Valeurs possibles :

- `calculé`
- `à vérifier`
- `données insuffisantes`

### 8.1. `calculé`

Attribué quand :

- assez de lignes historiques existent ;
- la fenêtre temporelle est exploitable ;
- la dynamique récente existe ;
- la trajectoire est calculable.

### 8.2. `à vérifier`

Attribué quand la base existe mais reste fragile, par exemple :

- moins de `4` sondages dans la fenêtre historique comparable ;
- moins de `4` sondages courants pour la force ;
- `trajectory_bias` non calculable.

### 8.3. `données insuffisantes`

Attribué quand le volume historique est trop faible, actuellement :

```python
len(force_group.index) < 6
```

## 9. Incertitude

Le moteur calcule une incertitude statistique sur l’erreur moyenne historique :

```python
uncertainty = std(historical_error) / sqrt(n)
```

si `n > 1`, sinon `NaN`.

Cette incertitude n’est pas injectée directement dans le score corrigé, mais elle est affichée dans la page `Biais calculés`.

## 10. Facteurs de représentativité

Le projet charge aussi des facteurs de représentativité via :

- `load_representativity_factors(reference_dir)`
- `compute_representativity_multiplier(frame, representativity_factors)`

Le calcul combine :

- un multiplicateur par mode de collecte ;
- un supplément si `sample_size < 1200` ;
- un supplément si `quota_method == "unknown"`.

Exemple de valeurs par défaut si le CSV n’existe pas :

- `online`: `1.15`
- `mixed`: `1.08`
- `phone`: `0.97`
- `unknown`: `1.20`

### Point important

Dans l’état actuel du code, ce terme est calculé mais non appliqué numériquement à la correction finale du premier tour :

```python
working["representativity_bias_component"] = 0.0
```

Donc :

- le multiplicateur de représentativité est bien calculé ;
- il peut être affiché ou audité ;
- mais il n’entre pas encore dans `historical_correction`.

## 11. Correction du second tour à partir des législatives 2024

Le second tour utilise une logique différente, fondée sur les blocs.

Fonction principale :

- `apply_second_round_legislative_correction(frame, reference_dir)`

### 11.1. Pourquoi les voix nationales brutes ne suffisent pas

Le projet n’utilise plus la simple lecture des voix totales nationales comme indicateur principal du rapport de force parlementaire.

La raison est méthodologique :

- le nombre de candidats n’était pas symétrique ;
- les désistements ont modifié la structure de compétition ;
- un total national brut peut surreprésenter un bloc qui a plus de candidatures ou moins de concurrence locale ;
- la capacité à convertir un score en pouvoir institutionnel passe par les sièges et les configurations de second tour.

### 11.2. Benchmark par blocs

Fonction :

- `compute_second_round_legislative_benchmark(candidate_a_bloc, candidate_b_bloc, legislative_frame)`

Étapes :

1. prise du `second_round` 2024 si disponible, sinon du `first_round` ;
2. usage prioritaire de `seat_share_percent` si la table de sièges est fournie ;
3. sinon repli sur `percent_expressed` ;
4. projection via la matrice `SECOND_ROUND_TRANSFER_MATRIX`.

La matrice encode une affinité de transfert entre blocs, par exemple :

- une partie du bloc `centre` peut aller vers `gauche`, `droite` ou `extrême_droite` ;
- une partie du bloc `droite` peut se reporter davantage vers `extrême_droite` que vers `gauche`.

Le benchmark final est normalisé en pourcentages sur le duel considéré.

### 11.3. Biais de sondage 2024

Le code contient aussi :

- `compute_legislative_2024_poll_bias(reference_dir)`

Cette fonction vise à comparer :

- les sondages 2024 extraits du zip complet ;
- le résultat réel 2024 par bloc.

Elle produit :

- `poll_mean`
- `actual_result`
- `poll_bias_2024`
- `n_points`

Ce biais est ensuite injecté dans la correction du second tour via :

- `legislative_poll_bias`

### 11.4. Prime institutionnelle de siège

Le code lit aussi :

- `vote_seat_gap`

depuis [historical_results_2024_legislatives_seats.csv](data/reference/historical_results_2024_legislatives_seats.csv).

Une petite partie de cet écart est réinjectée dans le benchmark :

```python
first_share += premium_map[first_bloc] * 0.08
second_share += premium_map[second_bloc] * 0.08
```

Puis les deux parts sont renormalisées.

### 11.5. Score corrigé de second tour

Le score final n’est pas un remplacement brutal du sondage brut.

Le code combine :

```python
legislatively_corrected_estimate =
    0.62 * raw_estimate
    + 0.38 * legislative_benchmark
```

puis borne le résultat à `[0, 100]`.

Interprétation :

- le brut garde le poids principal ;
- le benchmark 2024 agit comme correcteur de structure.

## 12. Ajustements polynomiaux visibles dans les graphes

Les courbes visibles dans les graphes ne sont pas des régressions linéaires globales.

Le moteur est dans :

- [trends.py](src/presidentielle2027/analytics/trends.py)

### 12.1. Préparation

La fonction `_prepare_xy(...)` :

- convertit les dates ;
- convertit les valeurs en numériques ;
- supprime les `NaN` ;
- trie les dates ;
- supprime les doublons exacts de date ;
- calcule un axe `date_num` en jours depuis la date minimale.

### 12.2. Ajustement polynomial

La fonction `_fit_polynomial(...)` :

- centre et réduit l’axe temporel ;
- ajuste un polynôme via `numpy.polyfit` ;
- applique des poids de récence.

Les poids de récence sont :

```python
1 / (1 + days_from_latest / 45)
```

Donc les points récents pèsent davantage.

### 12.3. Ordre du polynôme

L’ordre peut être :

- choisi explicitement par l’utilisateur ;
- ou plafonné automatiquement par la taille de l’échantillon.

La logique active est :

- minimum exploitable pour une courbe : `5` points ;
- degré forcé entre `2` et `6` si l’utilisateur choisit ;
- plafonnement par `point_count - 1`.

### 12.4. Courbe affichée

Les vues utilisent encore le nom historique `build_lowess_curve(...)`, mais ce wrapper appelle en réalité :

- `build_polynomial_curve(...)`

Le nom `lowess` a été conservé pour compatibilité avec le reste du code, mais le moteur actif est polynomial.

## 13. Prolongation exploratoire en pointillé

La prolongation visible jusqu’au scrutin est calculée par :

- `polynomial_extension(...)`

et exposée dans les vues via :

- `exploratory_extension(...)`

### 13.1. Fenêtre récente

Le calcul est limité au dernier segment récent, par défaut :

- `recent_days = 31`

Donc la prolongation n’utilise pas toute l’histoire du graphe, seulement la dynamique du dernier mois.

### 13.2. Condition minimale

La prolongation nécessite actuellement :

- au moins `5` points sur la série totale ;
- au moins `3` points sur la fenêtre récente.

### 13.3. Bande d’incertitude

Le code calcule :

1. les résidus sur la fenêtre récente ;
2. un écart-type `sigma` ;
3. une croissance de l’incertitude de `1.0` à `1.7` sur l’horizon prolongé ;
4. une bande bornée entre `0.8` et `12.0` points.

Les bornes affichées sont :

```python
lower = clip(extension_y - uncertainty, 0, 100)
upper = clip(extension_y + uncertainty, 0, 100)
```

### 13.4. Nature de la prolongation

La prolongation :

- est un scénario exploratoire ;
- n’est pas une prévision électorale validée ;
- dépend fortement de la densité des points du dernier mois ;
- peut ne pas être affichée si la base récente est trop pauvre.

## 14. Contrôles qualité du dataset corrigé

La page `Dataset corrigé 2027` ajoute des contrôles via :

- `_build_quality_alerts(frame)`

Les alertes portent sur :

- score corrigé hors `[0, 100]` ;
- échantillon `<= 0` ;
- date de publication absente ;
- somme des scores par sondage/scénario hors plage `[85, 105]`.

Le message prévu est par exemple :

- `Somme des scores incohérente : vérifier le parsing du sondage.`

## 15. Ce qui est affiché dans la page “Biais calculés”

La vue [biases.py](src/presidentielle2027/dashboard/views/biases.py) affiche notamment :

- `Force`
- `Années`
- `Sondages historiques`
- `Sondages 2027`
- `Résultat réel 2022`
- `Erreur moyenne`
- `Erreur médiane`
- `Incertitude`
- `Fenêtre 2027`
- `Sondages fenêtre`
- `Biais structurel`
- `Biais temps long`
- `Biais temporel 18m / 12m / 6m / 3m / 1m`
- `Biais trajectoire`
- `Correction totale`
- `Statut`

Le graphe de cette page décompose aussi visuellement :

- `Biais structurel`
- `Biais temps long`
- `Biais trajectoire`

## 16. Limites actuelles

### 16.1. Représentativité

Le facteur de représentativité est calculé mais pas injecté dans la correction finale du premier tour.

### 16.2. Temporalité

La temporalité est actuellement bucketisée en 4 fenêtres, ce qui simplifie beaucoup la structure réelle du temps de campagne.

### 16.3. Trajectoire

Le biais de trajectoire est un terme borné, construit à partir de pentes récentes et d’une dynamique historique d’erreur. Il reste sensible au choix de fenêtre et à la densité des points.

### 16.4. 2024

La logique 2024 est meilleure si elle passe par les sièges et la structure institutionnelle, mais :

- les biais 2024 les plus robustes sont désormais ceux relus depuis les tableaux Wikipédia structurés ;
- l'extraction PDF `visual_rows` reste plus fragile et doit surtout servir au debug visuel ;
- la comparaison n'est fiable que si l'on compare une colonne de sondage à la même colonne de résultat dans la table Wikipédia correspondante.

### 16.5. Courbes visibles

Les courbes visibles sont des polynômes pondérés par récence. Elles sont utiles pour lire une dynamique, mais elles ne doivent pas être lues comme une loi électorale.

## 17. Résumé opérationnel

### Premier tour 2027

1. normaliser la force ;
2. comparer l’historique 2022 au résultat réel ;
3. calculer :
   - biais structurel ;
   - biais temporel ;
   - biais trajectoire ;
4. sommer ces trois composantes ;
5. appliquer la correction au score brut ;
6. borner entre `0` et `100`.

### Second tour 2027

1. normaliser les candidats en grands blocs ;
2. construire un benchmark à partir des législatives 2024 ;
3. intégrer l’effet institutionnel des sièges ;
4. corriger partiellement le brut par ce benchmark ;
5. produire un score corrigé de second tour.

### Graphes

1. ajuster un polynôme pondéré par récence ;
2. afficher les points bruts ;
3. afficher la courbe lissée ;
4. si demandé, prolonger le dernier mois jusqu’à l’élection en pointillé ;
5. afficher une bande d’incertitude sur cette prolongation.

## 18. Points à surveiller lors des évolutions futures

- ne pas réintroduire de droite linéaire simple sur toute la période ;
- ne pas confondre voix nationales 2024 et conversion institutionnelle en sièges ;
- ne pas injecter un coefficient de représentativité arbitraire sans variable observable défendable ;
- conserver la séparation entre :
  - correction du score ;
  - courbe de lecture ;
  - prolongation exploratoire ;
- vérifier que les filtres de période pilotent bien à la fois :
  - les points affichés ;
  - les courbes ;
  - la prolongation.
