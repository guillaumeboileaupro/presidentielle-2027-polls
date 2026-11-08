# Réunification des dépôts Git — audit du 8 novembre 2026

## Décision de consolidation

La branche de consolidation part de `origin/main` à `daec802`. L'historique extérieur n'est pas fusionné avec `--allow-unrelated-histories` : bien que ses 75 commits n'aient aucun ancêtre commun avec les 87 commits distants, son commit final `7c9124e` possède exactement le même arbre (`aa1bf2a0fa9073ef1e8f264df68db2f68b20f6ed`) que le commit distant `2ea9210`. Les fonctionnalités de cette copie sont donc déjà dans l'historique GitHub, sous des SHA différents.

Les 12 modifications suivies et les 5 fichiers non suivis de la copie intérieure ont été transférés sans modification dans `codex/reunify-repositories`. Les patchs binaires source et destination ont la même empreinte SHA-256 : `be6a2a196c42f29a639851081f401be8687b36be0c384d1f834992feea8f71c0`.

## Sauvegardes vérifiées

Les sauvegardes locales sont conservées dans `_reunification_backups/20261108T124133+0100/` au niveau du dépôt extérieur. Elles comprennent deux bundles Git complets et deux archives de worktree. Leur manifeste contient les tailles, empreintes SHA-256, exclusions et commandes de vérification. Aucun dépôt n'a été supprimé ou déplacé.

## Fonctionnalités locales intégrées

- état atomique et verrou interprocessus du rafraîchissement automatique ;
- reprise rapide après un démarrage hors ligne et temporisation anti-sollicitation au lancement ;
- réutilisation d'un snapshot Wikipédia lorsque la révision est inchangée ;
- invalidation automatique du cache du dashboard lorsque les données changent ;
- miroir de compatibilité du CSV normalisé historique ;
- documentation, configuration et tests de non-régression associés.

## Données et arbitrages

Le CSV historique passe de 1 116 à 3 306 lignes, de 147 à 279 identifiants de sondage, de 74 à 120 scénarios et de 40 à 51 candidats. Il est strictement identique au CSV V2 (`e98324403aac9e513dc27a6fd3aca7989f4e12e6b38703afba6c874720d63fd0`). Les 279 groupes sondage/scénario totalisent entre 99 et 100,5 points ; aucun n'est hors de l'intervalle 95–105 et aucune ligne n'est dupliquée.

Le fichier remplace les 1 054 lignes issues de la page Wikipédia anglophone et 62 lignes francophones par 3 306 lignes issues de la page francophone. Ce choix provient du travail local préexistant et reste visible dans la PR pour revue ; les anciennes données restent récupérables dans Git et dans les sauvegardes, sans écrasement silencieux.

Le classeur Excel consolidé contient six feuilles ; sa taille est de 611 984 octets et son empreinte est `6a4644678c35f4598bef09e6c5c61315f9b49b319dc6141098aaad3b705d2042`. La base locale `data/polls.sqlite3` n'a pas été modifiée et reste ignorée par Git ; son empreinte de contrôle est `07ca8efcd0ae183a6689e0679ec833ed7bca0daf10e1d706420cedb7607772ab`.

## Configuration des agents

`AGENTS.md` et `CLAUDE.md` pointent tous deux vers les règles partagées de `AGENT.md`. Trois skills projet sont présents et valides sous `.claude/skills/` : audit d'ingestion, vocabulaire politique canonique et validation des ajustements. Il n'existe pas de configuration `.codex/`, `.agents/`, `.mcp.json`, `DASHBOARD.md`, `TODO.md` ou `DEVELOPMENT_PLAN.md` dans ce dépôt ; aucun fichier factice n'a été créé.

## Validation locale

- `python -m pytest -q` : 193 tests réussis, couverture 98,96 % ;
- `python -m ruff check src tests` : réussi ;
- `python -m mypy src` : 17 erreurs préexistantes dans des fichiers non modifiés (`excel_parser.py`, `make_wiki_datasets.py` et trois modules analytics).

Les deux tests Excel nécessitent deux classeurs locaux ignorés par Git. Ils ont été copiés dans le worktree de validation avec des empreintes identiques à la copie intérieure, sans être ajoutés au commit.

## État de livraison

Une seule branche et une seule PR sont prévues. La PR ne doit pas être fusionnée automatiquement. Le dépôt extérieur, le dépôt intérieur, les sauvegardes et le worktree restent conservés jusqu'à validation explicite du propriétaire.
