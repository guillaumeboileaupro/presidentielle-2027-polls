# Données extraites des 3 pages Wikipédia demandées

Ce dossier contient les 3 pages demandées sous deux formes :

1. PDF Wikipédia téléchargé depuis l’API REST Wikipédia.
2. TXT extrait du PDF avec `pdftotext -layout`.
3. CSV ligne par ligne pour exploitation rapide dans Codex/Python.

Sources :
- Présidentielle 2027 : https://fr.wikipedia.org/wiki/Liste_de_sondages_sur_l%27%C3%A9lection_pr%C3%A9sidentielle_fran%C3%A7aise_de_2027
- Présidentielle 2022 : https://fr.wikipedia.org/wiki/Liste_de_sondages_sur_l%27%C3%A9lection_pr%C3%A9sidentielle_fran%C3%A7aise_de_2022
- Législatives 2024 : https://fr.wikipedia.org/wiki/Liste_de_sondages_sur_les_%C3%A9lections_l%C3%A9gislatives_fran%C3%A7aises_de_2024

Important : les CSV fournis ici conservent toute la donnée textuelle extraite ligne par ligne. Ils ne sont pas encore normalisés en tables électorales longues (`pollster`, `date`, `sample_size`, `party`, `candidate`, `score`). Cette normalisation doit être faite ensuite dans le projet pour éviter d’écraser des tableaux complexes, notamment les hypothèses multiples de 2027 et les projections en sièges de 2024.
