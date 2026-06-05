from __future__ import annotations


def first_round_methodology_html() -> str:
    return """
    <div class="wiki-panel">
        <h3 style="margin-top:0;">Méthode utilisée dans cette vue</h3>
        <p class="wiki-muted" style="margin-bottom:0.5rem;">
            Les sondages de 2027 sont lus ici par <strong>force politique</strong>, avec regroupement possible par parti ou par famille.
            La courbe affichée est un <strong>ajustement polynomial paramétrable</strong> sur les points comparables disponibles, pas une droite linéaire.
        </p>
        <ul style="margin-top:0.4rem; line-height:1.55;">
            <li><strong>Lecture brute</strong> : chaque point correspond à une mesure publiée, sans redressement.</li>
            <li><strong>Regroupement politique</strong> : les scénarios nominaux sont ramenés à des forces comparables.</li>
            <li><strong>Ajustement polynomial</strong> : l’ordre `2` à `6` peut être choisi dans la vue, avec borne automatique si la série est trop courte.</li>
            <li><strong>Prolongation exploratoire</strong> : une case à cocher permet d’afficher une extension courte jusqu’au scrutin à partir du dernier mois de données, avec incertitude croissante.</li>
        </ul>
        <p class="wiki-muted" style="margin-bottom:0;">
            Les données historiques `2017–2022` sont séparées dans la vue `Analyse historique 2022`. La prolongation affichée ici est exploratoire et ne constitue pas une prévision électorale validée.
        </p>
    </div>
    """


def corrected_dataset_methodology_html() -> str:
    return """
    <div class="wiki-panel">
        <h3 style="margin-top:0;">Lecture corrigée des sondages 2027</h3>
        <p class="wiki-muted" style="margin-bottom:0.5rem;">
            Cette vue affiche d’abord les estimations 2027 redressées. Les données 2022 ne servent ici que de base de calibration.
        </p>
        <ul style="margin-top:0.2rem; line-height:1.55;">
            <li><strong>Biais structurel 2022</strong> : écart moyen entre sondages 2022 et résultat réel par force.</li>
            <li><strong>Biais temporel 2022</strong> : erreur lissée selon la distance au scrutin, pour tenir compte de la dynamique de campagne.</li>
            <li><strong>Biais de trajectoire</strong> : correction liée à la dynamique récente comparée à la dynamique historique ajustée.</li>
        </ul>
        <p class="wiki-muted" style="margin-bottom:0;">
            Les tables 2022 restent disponibles plus bas pour audit, sans remplacer la lecture politique de 2027.
        </p>
    </div>
    """


def second_round_methodology_html() -> str:
    return """
    <div class="wiki-panel">
        <h3 style="margin-top:0;">Point d’appui du second tour</h3>
        <p class="wiki-muted" style="margin-bottom:0.5rem;">
            Le second tour est affiché duel par duel, avec un point d’appui sur les rapports de blocs observés aux législatives 2024.
        </p>
        <ul style="margin-top:0.2rem; line-height:1.55;">
            <li><strong>Base brute</strong> : nuage de points publié pour le duel sélectionné.</li>
            <li><strong>Réserve de blocs 2024</strong> : les rapports de forces observés aux législatives 2024 servent de correction de base.</li>
            <li><strong>Projection exploratoire</strong> : un bouton séparé permet, si besoin, d’afficher une prolongation courte à partir de la dynamique récente ajustée, hors méthode centrale.</li>
        </ul>
    </div>
    """
