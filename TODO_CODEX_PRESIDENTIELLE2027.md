# TODO CODEX — Fiabilisation complète des sondages, des partis et de l’affichage

## Objectif général

Auditer puis corriger le projet `presidentielle2027` afin de garantir :

1. la conservation de tous les sondages et de toutes les lignes utiles ;
2. la correction des mauvaises unités de pourcentage ;
3. l’absence de points aberrants provoqués par la perte d’un séparateur décimal ;
4. la cohérence des scénarios complets de sondage ;
5. la suppression des doublons sémantiques de partis comme `LE` et `EELV` ;
6. la séparation stricte entre `PS` et `PP` ;
7. la disparition des catégories artificielles `PS-PP`, `LE` et `EPR` dans les données finales ;
8. la cohérence des familles politiques, couleurs, logos et tableaux ;
9. la possibilité d’activer ou désactiver certaines forces politiques dans le dashboard ;
10. la conservation de cette sélection dans un cookie ;
11. l’ajout de tests empêchant toute régression.

Ne pas modifier le code sur la base de suppositions. Avant chaque changement, localiser les fonctions, dictionnaires et chemins réellement utilisés dans le dépôt.

---

# Phase prioritaire — Performance du dashboard

État au 29 juillet 2026 :

- fait : pipeline Wikipédia découplé des reruns Streamlit ;
- fait : caches préservés et préparation globale des tendances supprimée ;
- fait : courbes par candidat et tableau détaillé chargés uniquement sur demande ;
- fait : régressions locales mises en cache et payload Plotly ramené à 300 points par courbe ;
- mesuré : environ `0,02 s` pour une préparation en cache et `0,004 s` pour une courbe LOWESS en cache ;
- fait le 25 août 2026 : contrôle Chromium headless des quatre vues principales ;
- mesuré à froid : premier tour `4,07 s`, historique 2022 `2,28 s`, législatives 2024
  `2,25 s`, circonscriptions 2024 `2,13 s` ;
- conclusion : les vues historiques ne sont plus les plus lentes et ne nécessitent pas
  d'optimisation corrective supplémentaire à ce stade ; la page de premier tour reste la cible
  prioritaire des futures optimisations.

## P.1. Ne plus rafraîchir Wikipédia à chaque exécution Streamlit

- Découpler `run_refresh_pipeline()` du rendu de `live_app.py`.
- Ne pas relancer le téléchargement, la génération des datasets, la normalisation, la persistance en base, le rapport de couverture et les moyennes à chaque interaction avec un widget.
- Déplacer ce rafraîchissement vers une tâche périodique ou une action manuelle explicite.
- Conserver au démarrage la lecture du dernier dataset local valide.

## P.2. Préserver les caches

- Ne plus appeler systématiquement `load_dashboard_data.clear()` et `prepare_dashboard_frame.clear()`.
- Invalider les caches uniquement lorsqu’un nouveau dataset a réellement été produit.
- Mesurer séparément le temps de chargement à froid et le temps d’un rerun Streamlit.

## P.3. Éviter les calculs inutiles avant le rendu

- Ne pas calculer toutes les tendances globales avant de connaître la page active.
- Calculer uniquement les agrégations et courbes nécessaires à la vue affichée.
- Mettre en cache les séries agrégées et les régressions locales avec les filtres comme clé.

## P.4. Alléger la page initiale

- Éviter de recalculer simultanément le graphique par blocs et les quinze courbes par candidat.
- Différer le second graphique dans un onglet, un expander ou une vue distincte.
- Limiter le volume transmis à Plotly et au tableau détaillé sans perdre les données exportables.

## P.5. Mesurer avant et après

- Ajouter des mesures pour le rafraîchissement des sources, la préparation du DataFrame, le calcul LOWESS et le rendu Plotly.
- Définir une cible mesurable pour le premier affichage et pour une interaction avec un filtre.
- Ajouter un test garantissant qu’une interaction de dashboard ne déclenche pas le pipeline d’ingestion.

---

# Phase 0 — Audit obligatoire avant modification

## 0.1. Rechercher toutes les occurrences problématiques

Exécuter une recherche globale dans le dépôt pour les chaînes suivantes :

```text
PS-PP
PP-PS
PS/PP
PP/PS
PP/PS/DVG
PS/PP/DVG
LE
EELV
Les Écologistes
Europe Écologie Les Verts
EPR
Ensemble pour la République
ENS
centre_left
centre_gauche
greens
green
écologistes
estimate_percent
raw_text_context
drop_duplicates
errors="coerce"
continue
zip(order, tokens)
```

Produire un inventaire précis :

```text
fichier
ligne
fonction ou dictionnaire
rôle dans le pipeline
```

## 0.2. Identifier le chemin exact des données

Tracer complètement le chemin :

```text
fichiers bruts
→ parseurs
→ DataFrame normalisé
→ CSV ou base de données
→ fonctions analytiques
→ tableau du dashboard
→ graphique du dashboard
```

Identifier notamment :

- quel CSV ou quelle base est réellement lu par le dashboard ;
- si le dashboard utilise un ancien fichier normalisé déjà présent ;
- si les données sont reparsées à chaque lancement ;
- si Streamlit met en cache le DataFrame ;
- à quel moment sont exécutés les `groupby` ;
- à quel moment les partis et familles sont canonicalisés.

Ne pas appliquer uniquement une correction dans le parseur si le dashboard peut relire un ancien CSV sans repasser par ce parseur.

---

# Phase 1 — Corriger les pourcentages sans supprimer de sondages

## 1.1. Règle fondamentale

Une opération de correction doit être réfléchie au niveau du **scénario complet**, et non uniquement au niveau d’un point isolé.

La clé de scénario à utiliser doit être vérifiée dans le code réel. Elle devrait normalement inclure :

```python
["poll_id", "round", "scenario_name"]
```

Ajouter d’autres colonnes si `poll_id` n’identifie pas réellement un scénario unique.

## 1.2. Ne supprimer aucune ligne pendant la correction

La fonction de correction des pourcentages ne doit contenir aucune logique qui retire des lignes :

```text
pas de drop
pas de dropna
pas de filtre conservant uniquement les lignes valides
pas de suppression du scénario
pas de reclassification automatique en second tour
```

Avant et après correction :

```python
assert len(corrected) == len(frame)
assert corrected.index.equals(frame.index)
```

Si l’index est volontairement réinitialisé, vérifier au minimum que le nombre de lignes et les identifiants sont inchangés.

## 1.3. Ne plus corriger arbitrairement dans `_parse_raw_poll_percent`

La fonction `_parse_raw_poll_percent` doit uniquement :

- extraire le nombre ;
- convertir la virgule en point ;
- retourner un nombre ou `None`.

Elle ne doit pas décider seule :

```text
250 → 25
85 → 8,5
65 → 6,5
```

car elle ne connaît pas le contexte du scénario complet.

La correction d’unité doit être effectuée après construction du DataFrame du scénario.

## 1.4. Corriger les valeurs manifestement impossibles

Une valeur individuelle supérieure à `100` est forcément dans une mauvaise unité.

Mais sa correction doit être cohérente avec le scénario complet.

Exemples possibles :

```text
250 → 25
2195 → 21,95
2785 → 27,85
2315 → 23,15
```

Ne pas se limiter à une seule division par dix :

```python
if parsed > 100:
    parsed /= 10
```

car :

```text
2195 → 219,5
```

reste faux.

## 1.5. Corriger les décimales perdues sous 100

Le problème restant concerne aussi des valeurs telles que :

```text
85 au lieu de 8,5
65 au lieu de 6,5
35 au lieu de 3,5
25 au lieu de 2,5
```

Ces valeurs ne peuvent pas être corrigées uniquement avec une règle `> 100`.

Elles ne doivent pas non plus être corrigées automatiquement avec une règle :

```python
value > 50
```

car `65 %` peut être une vraie valeur de second tour.

La somme du scénario doit servir de signal de détection.

## 1.6. Utiliser la somme du scénario comme contrôle

Pour chaque scénario :

1. convertir temporairement les valeurs numériques ;
2. calculer la somme ;
3. si la somme est raisonnable, ne rien modifier ;
4. si la somme est très supérieure à `100`, rechercher une perte de séparateur décimal ;
5. produire un nouveau vecteur complet de valeurs ;
6. remplacer le scénario complet en une seule opération.

Ne pas remplacer un point isolé sans conserver la cohérence du vecteur complet.

Exemple :

```text
vecteur extrait :
[5, 115, 35, 5, 85, 22, 25, 85, 3, 31.5, 35]
```

vecteur possible après reconstruction :

```text
[0.5, 11.5, 3.5, 5, 8.5, 22, 2.5, 8.5, 3, 31.5, 3.5]
```

La somme obtenue doit être proche de `100`.

## 1.7. Ne pas appliquer un facteur unique aveuglément à tous les éléments

Ne pas supposer systématiquement qu’un scénario entier doit être divisé par `10`.

Dans certains scénarios :

```text
22
31,5
3
```

sont déjà corrects, tandis que :

```text
85
35
25
```

ont perdu une décimale.

Le correcteur doit reconstruire le vecteur complet en choisissant, pour chaque valeur ambiguë, les interprétations plausibles.

## 1.8. Limiter la recherche combinatoire

Ne pas utiliser une recherche exponentielle non bornée sur toutes les lignes du scénario.

Éviter une boucle du type :

```python
for mask in range(1, 1 << len(candidate_indexes)):
```

sur un nombre élevé de candidats.

Utiliser une méthode bornée :

- générer uniquement les options plausibles pour les tokens ambigus ;
- ne traiter que les scénarios dont la somme est réellement aberrante ;
- limiter le nombre d’options par valeur ;
- utiliser une programmation dynamique, un branch-and-bound ou une recherche avec seuil ;
- interrompre les branches dont la somme ne peut plus atteindre la zone cible.

## 1.9. Conserver la traçabilité des corrections

Ajouter des colonnes de diagnostic, au moins dans le DataFrame de travail ou dans un rapport séparé :

```text
estimate_percent_original
estimate_percent_corrected
percentage_correction_applied
percentage_correction_factor
percentage_correction_reason
scenario_total_before
scenario_total_after
```

Ne pas écraser définitivement l’information brute sans historique.

## 1.10. Gérer les cas ambigus

Si plusieurs corrections sont également plausibles :

- ne pas supprimer le scénario ;
- conserver les données ;
- marquer le scénario comme ambigu ;
- enregistrer un rapport d’anomalie ;
- ne pas inventer une correction arbitraire.

Créer par exemple :

```text
data/processed/poll_percentage_correction_report.csv
```

avec :

```text
poll_id
round
scenario_name
polling_company
candidate_name
raw_text_context
value_before
value_after
scenario_total_before
scenario_total_after
status
reason
```

---

# Phase 2 — Empêcher la disparition silencieuse de données

## 2.1. Audit des `continue`

Les `continue` ne suppriment pas directement une ligne déjà créée, mais ils peuvent empêcher la création d’une ligne ou ignorer un scénario.

Auditer tous les `continue` dans les parseurs.

Pour chacun, préciser :

```text
ce qui est ignoré
pourquoi
si la ligne doit être conservée
si l’anomalie doit être journalisée
```

## 2.2. Valeurs non parsables

Le code contient des logiques comme :

```python
estimate = _parse_raw_poll_percent(cell_text)
if estimate is None:
    continue
```

Cette logique fait disparaître le candidat du résultat.

À remplacer par une stratégie explicite :

- conserver une ligne avec `estimate_percent = None` si la cellule correspond réellement à un candidat ;
- conserver `raw_text_context` ;
- marquer le statut de parsing ;
- exclure seulement du graphique numérique, pas du dataset brut.

Ajouter par exemple :

```text
parse_status
parse_error
```

## 2.3. Dates non reconnues

Le code contient des logiques comme :

```python
if fieldwork_start_date is None and fieldwork_end_date is None:
    continue
```

Cela peut supprimer un sondage entier à cause d’une date mal parsée.

Nouvelle règle :

- conserver la ligne ;
- laisser les dates à `None` ;
- stocker la date brute ;
- marquer l’échec de parsing.

## 2.4. Filtre sur les dates de publication

Le code contient potentiellement :

```python
publication_dates = pd.to_datetime(..., errors="coerce")
normalized = normalized.loc[publication_dates.notna()]
```

Cela supprime toutes les lignes dont la date est invalide.

Remplacer par une logique qui :

- conserve les dates invalides ;
- retire uniquement les dates reconnues et réellement futures, si ce comportement est voulu ;
- produit un rapport pour les dates non reconnues.

## 2.5. `drop_duplicates`

Auditer chaque `drop_duplicates`.

Un sous-ensemble tel que :

```python
[
    "round",
    "polling_company",
    "fieldwork_start_date",
    "fieldwork_end_date",
    "scenario_name",
    "candidate_name",
    "estimate_percent",
]
```

peut supprimer deux sondages distincts ayant le même résultat.

La déduplication doit utiliser un identifiant fiable :

```text
poll_id
source_url
source_name
scenario_name
candidate_name
```

Ne dédupliquer que si les deux lignes représentent réellement la même observation.

Avant/après chaque déduplication, produire :

```text
nombre de lignes
identifiants supprimés
raison de la suppression
```

## 2.6. `zip(order, tokens)`

Les boucles :

```python
for candidate_name, token in zip(order, tokens):
```

tronquent silencieusement la séquence la plus longue.

Ajouter obligatoirement un contrôle :

```python
if len(order) != len(tokens):
    ...
```

Ne pas ignorer silencieusement les valeurs supplémentaires.

Créer un rapport avec :

```text
poll_id
source
candidate_count
token_count
raw_vector
candidate_order_reference
```

## 2.7. Tokens `-`

Une valeur `-` signifie généralement « non testé » ou « absent du scénario ».

Décider explicitement si :

- aucune ligne ne doit être créée ;
- ou une ligne doit être créée avec `estimate_percent = None`.

Cette décision doit être documentée et testée.

Ne pas confondre « candidat absent du scénario » et « valeur perdue par le parseur ».

## 2.8. `raw_block_needs_parser`

Les lignes marquées :

```text
raw_block_needs_parser
```

ne doivent pas disparaître sans trace.

Elles doivent :

- rester accessibles dans un rapport ;
- être comptées ;
- être exclues uniquement du dataset quantitatif final tant qu’elles ne sont pas parsées ;
- être signalées dans le dashboard ou dans les logs.

---

# Phase 3 — Canonicalisation des partis et familles politiques

## 3.1. Règles obligatoires

Appliquer strictement les règles suivantes :

```text
PS reste PS
PP reste PP
PS et PP sont deux partis distincts
PS et PP appartiennent à la famille centre_gauche
PS est rose
PP est jaune
EELV reste EELV
LE doit être converti en EELV
Les Écologistes doit être converti en EELV
Europe Écologie Les Verts doit être converti en EELV
centre_left doit être converti en centre_gauche
EPR ne doit pas rester comme catégorie canonique
PS-PP ne doit pas rester comme catégorie canonique
```

## 3.2. Résolution des libellés PS/PP composites

Traiter au minimum :

```text
PS-PP
PP-PS
PS/PP
PP/PS
PP/PS/DVG
PS/PP/DVG
```

Résoudre selon le candidat :

```text
Raphaël Glucksmann → PP
François Hollande → PS
Olivier Faure → PS
Boris Vallaud → PS
```

Pour un candidat non reconnu :

- ne pas convertir arbitrairement en PS ;
- ne pas convertir arbitrairement en PP ;
- marquer l’alias composite comme non résolu ;
- produire un diagnostic.

## 3.3. Résolution de EPR

`EPR` ne doit pas rester comme parti canonique.

Résoudre selon le candidat ou selon les règles réellement présentes dans le dépôt.

Cas demandés :

```text
Édouard Philippe + EPR → HOR
Gabriel Attal + EPR → RE
Gérald Darmanin + EPR → RE
Emmanuel Macron + EPR → RE
Sébastien Lecornu + EPR → RE
```

Si un candidat EPR n’est pas connu, ne pas inventer. Produire une anomalie de canonicalisation.

## 3.4. Uniformiser les familles

Normaliser :

```text
centre_left → centre_gauche
green → écologistes
greens → écologistes
écologistes → écologistes
```

Ne pas transformer :

```text
centre_gauche → LFI
```

Ne pas transformer automatiquement :

```text
écologistes → gauche
```

dans les tableaux descriptifs.

Les éventuels regroupements électoraux pour un modèle de report de voix doivent rester séparés de la famille politique affichée.

## 3.5. Une seule source de vérité

Créer une source centrale de canonicalisation, par exemple dans :

```text
presidentielle2027/extraction/canonicalization.py
```

Tous les autres modules doivent l’utiliser.

Ne pas dupliquer les alias dans :

```text
colors.py
party_assets.py
historical_corrections.py
table_views.py
analysis_2022.py
```

Ces fichiers doivent recevoir des valeurs déjà canonicalisées.

## 3.6. Canonicaliser avant les `groupby`

Le problème visible dans le tableau est :

```text
LE   | LE   | écologistes | 2,8 %
EELV | EELV | greens      | 2,8 %
```

La canonicalisation doit avoir lieu avant le regroupement.

Après canonicalisation :

```text
LE → EELV
greens → écologistes
```

Les deux lignes doivent appartenir au même groupe.

Attention : ne pas additionner aveuglément deux lignes si elles représentent exactement le même sondage dupliqué. D’abord déterminer si ce sont :

- deux observations distinctes ;
- ou deux représentations du même point.

La déduplication et la canonicalisation doivent être ordonnées correctement :

1. conserver l’identité brute ;
2. canonicaliser ;
3. détecter les doublons sémantiques ;
4. dédupliquer uniquement les vrais doublons ;
5. agréger.

## 3.7. Migration des données historiques

Modifier le code ne suffit pas si le dashboard relit un ancien CSV ou une ancienne base.

Créer une migration explicite sur les données existantes :

```text
candidate_party:
LE → EELV
Les Écologistes → EELV
Europe Écologie Les Verts → EELV

political_family:
centre_left → centre_gauche
green → écologistes
greens → écologistes
```

Pour `PS-PP` et `EPR`, utiliser le candidat pour résoudre.

La migration doit :

- conserver une sauvegarde ;
- produire un rapport avant/après ;
- être idempotente ;
- pouvoir être relancée sans modifier une deuxième fois les valeurs.

---

# Phase 4 — Couleurs et logos

## 4.1. Couleurs obligatoires

Valeurs finales :

```text
PS → rose
PP → jaune
EELV → vert
```

Ne pas conserver une couleur pour :

```text
PS-PP
LE
EPR
```

car ces catégories ne doivent plus atteindre la couche d’affichage.

## 4.2. Logos obligatoires

Valeurs finales :

```text
PS → logo Parti socialiste
PP → logo Place publique
EELV → logo Les Écologistes
```

Ne pas conserver un logo générique pour `PS-PP`.

Les exceptions candidat ne doivent être nécessaires qu’en dernier recours. Idéalement, la canonicalisation doit produire directement le bon parti.

## 4.3. `ENS` et nom de fichier `Groupe EPR.png`

Ne pas confondre :

```text
clé politique : ENS
nom du fichier : Groupe EPR.png
```

Le nom d’un fichier image ne crée pas une catégorie politique `EPR`.

## 4.4. Valeurs inconnues

Si un parti n’a pas de couleur ou de logo :

- utiliser une couleur neutre ;
- afficher le code réel ;
- journaliser l’absence d’asset ;
- ne pas fusionner arbitrairement avec un autre parti.

---

# Phase 5 — Dashboard : activation/désactivation des forces

## 5.1. Sélecteur de forces

Ajouter dans la vue concernée un contrôle permettant d’activer ou désactiver chaque force politique.

Le sélecteur doit agir uniquement sur l’affichage :

- points ;
- courbes ;
- projections ;
- tableau récapitulatif ;
- légende.

Il ne doit jamais modifier ni supprimer les données de base.

## 5.2. Source de la liste

La liste des forces disponibles doit être construite après canonicalisation.

Elle ne doit donc pas contenir simultanément :

```text
LE
EELV
PS
PP
PS-PP
EPR
```

mais uniquement les catégories finales.

## 5.3. Persistance dans un cookie

Stocker la sélection dans un cookie.

Prévoir une clé différente selon le mode d’affichage si nécessaire :

```text
partis
familles politiques
```

Le cookie doit :

- être lu au chargement ;
- ignorer les valeurs qui n’existent plus ;
- inclure par défaut les nouvelles forces inconnues du cookie, ou documenter le comportement choisi ;
- être mis à jour uniquement quand la sélection change ;
- ne pas provoquer de boucle de rerun Streamlit.

## 5.4. Boutons pratiques

Ajouter :

```text
Tout afficher
Tout masquer
Réinitialiser
```

`Tout masquer` peut afficher un message clair au lieu d’un graphique vide silencieux.

---

# Phase 6 — Cache, fichiers produits et régénération

## 6.1. Identifier les caches

Rechercher :

```text
st.cache_data
st.cache_resource
lru_cache
CSV normalisé
SQLite
Parquet
pickle
```

Après migration :

- invalider les caches ;
- régénérer les fichiers normalisés ;
- reconstruire la base si nécessaire.

## 6.2. Versionner le schéma de normalisation

Ajouter une constante, par exemple :

```python
NORMALIZATION_VERSION = 2
```

Stocker cette version dans les fichiers produits ou les métadonnées.

Si un ancien fichier est détecté, le pipeline doit :

- le migrer ;
- ou le reconstruire.

---

# Phase 7 — Tests obligatoires

## 7.1. Tests de pourcentages

Ajouter des tests pour :

```text
250 → 25
2195 → 21,95
2785 → 27,85
2315 → 23,15
```

Ajouter un scénario avec décimales perdues sous 100.

Vérifier :

```text
nombre de lignes identique
mêmes poll_id
mêmes candidats
somme corrigée cohérente
aucun sondage supprimé
```

## 7.2. Cas normal non modifié

Tester :

```text
35 + 65 = 100
```

Aucune correction.

Tester un premier tour normal :

```text
30 + 25 + 20 + 15 + 10 = 100
```

Aucune correction.

## 7.3. Cas ambigu

Créer un scénario où plusieurs interprétations sont possibles.

Le code doit :

- conserver les données ;
- marquer le scénario comme ambigu ;
- ne pas choisir arbitrairement.

## 7.4. Tests de conservation

Pour chaque parseur :

```python
assert aucun sondage valide n’est perdu
assert les dates invalides sont signalées
assert les valeurs non parsables sont conservées dans le rapport
assert les différences order/tokens sont détectées
```

## 7.5. Tests de partis

Tester :

```text
LE → EELV
Les Écologistes → EELV
Europe Écologie Les Verts → EELV
EELV → EELV

centre_left → centre_gauche
greens → écologistes
green → écologistes

Raphaël Glucksmann + PS-PP → PP
François Hollande + PS-PP → PS
Olivier Faure + PS-PP → PS
Boris Vallaud + PS-PP → PS

PS → PS
PP → PP
```

## 7.6. Tests EPR

Tester :

```text
Édouard Philippe + EPR → HOR
Gabriel Attal + EPR → RE
Gérald Darmanin + EPR → RE
Emmanuel Macron + EPR → RE
Sébastien Lecornu + EPR → RE
```

## 7.7. Tests d’agrégation

Entrée :

```text
LE   / écologistes / valeur A
EELV / greens      / valeur B
```

Après canonicalisation :

```text
EELV / écologistes
```

Vérifier que le tableau ne contient plus deux lignes de parti.

Vérifier séparément que les vrais doublons ne sont pas comptés deux fois.

## 7.8. Tests couleurs et logos

Vérifier :

```text
PS → couleur rose et logo PS
PP → couleur jaune et logo PP
EELV → couleur verte et logo EELV
```

Vérifier l’absence de :

```text
PS-PP
LE
EPR
centre_left
```

dans la sortie finale du dashboard.

## 7.9. Tests du cookie

Tester :

- sélection initiale ;
- désactivation d’une force ;
- rechargement ;
- restauration de la sélection ;
- force supprimée du modèle mais encore présente dans le cookie ;
- nouvelle force absente de l’ancien cookie ;
- réinitialisation.

---

# Phase 8 — Rapport final attendu de Codex

À la fin, produire un rapport avec :

## Fichiers modifiés

```text
chemin
raison
résumé du changement
```

## Données avant/après

```text
nombre total de lignes
nombre de sondages
nombre de scénarios
nombre de valeurs > 100
nombre de scénarios dont la somme > 100
nombre de LE
nombre de EELV
nombre de PS-PP
nombre de PS
nombre de PP
nombre de EPR
nombre de centre_left
nombre de centre_gauche
```

## Corrections automatiques

```text
nombre de valeurs corrigées
nombre de scénarios corrigés
nombre de scénarios ambigus
nombre de lignes supprimées
```

La valeur attendue pour :

```text
nombre de lignes supprimées par la correction d’unité
```

doit être :

```text
0
```

## Tests

Fournir :

```text
commande exécutée
nombre de tests
résultat
```

---

# Critères d’acceptation finaux

Le travail n’est terminé que si :

```text
Aucun point n’est supprimé par la correction des unités.
Aucun scénario n’est supprimé parce que sa somme dépasse 100.
Les scénarios aberrants sont corrigés ou marqués comme ambigus.
Les opérations de correction sont réalisées au niveau du scénario complet.
LE n’apparaît plus dans les données finales.
EELV reste la seule clé écologiste de parti.
greens et green deviennent écologistes.
PS et PP restent distincts.
PS-PP n’apparaît plus comme parti canonique.
PS et PP ont la famille centre_gauche.
centre_left n’apparaît plus.
PP est jaune.
PS est rose.
EELV est vert.
EPR n’apparaît plus comme parti canonique.
Les anciennes données sont migrées.
Les caches sont invalidés.
Le tableau n’affiche plus simultanément LE et EELV.
Le filtre des forces fonctionne.
La sélection des forces est restaurée par cookie.
Tous les tests passent.
```
