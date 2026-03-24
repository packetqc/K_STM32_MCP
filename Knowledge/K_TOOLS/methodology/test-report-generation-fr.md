# Génération de rapports de tests — Méthodologie

## Objectif

Générer des publications de rapports de tests enrichis à partir d'évaluations automatisées de pages web. Chaque rapport est un document autonome avec des artéfacts de preuve intégrés (GIF animé, vidéo MP4) et des grilles de résultats détaillées.

## Exécution des tests

Les tests sont **pilotés par la demande** — aucun mode prédéfini. Claude détermine quelles pages tester selon la requête de l'utilisateur.

| Flag | Fonction |
|------|----------|
| `--targets <docs>` | Tester des pages spécifiques identifiées depuis la demande |
| `--detailed <docs>` | Ajouter les tests d'interaction des widgets |
| `--request` | Description synthétisée du test |
| `--original-request` | Message verbatim de l'utilisateur |

## Pipeline d'exécution

```
Demande → Recherche de route → Moteur de test → Capture de preuve → Générateur de rapport → Publication
```

### Étape 1 : Recherche de route

```bash
python3 K_MIND/scripts/routing_lookup.py --subject test --action report
```

Confirme : méthodologie, compétences, scripts, exigences de proof_output.

### Étape 2 : Moteur de test

```bash
# Test ciblé — pages spécifiques
python3 K_TOOLS/scripts/web_test_engine.py --targets doc1.md doc2.md \
    --request "description du test" --original-request "message utilisateur"

# Avec tests d'interaction des widgets
python3 K_TOOLS/scripts/web_test_engine.py --targets doc1.md doc2.md \
    --detailed doc1.md doc2.md \
    --request "description du test" --original-request "message utilisateur"
```

Sorties :
- `test-reports/default-test-report.gif` — preuve animée (Full HD 1920x1080)
- `test-reports/default-test-report.mp4` — preuve vidéo (résolution auto-ajustée sous MP4_MAX_MB)
- `test-reports/results.json` — résultats lisibles par machine

### Étape 3 : Générateur de rapport

```bash
python3 K_TOOLS/scripts/generate_test_report.py \
    --title "Navigateur principal — Test complet" \
    --request "Test complet de tous les liens du navigateur principal" \
    --gif K_TOOLS/test-reports/default-test-report.gif \
    --video K_TOOLS/test-reports/default-test-report.mp4 \
    --results K_TOOLS/test-reports/results.json \
    --slug test-main-navigator \
    -o docs/publications/test-main-navigator/
```

### Étape 4 : Publication

Enregistrer dans `docs/data/tests.json` pour la section TESTS dans le panneau gauche du navigateur.

## Structure du document

| Section | Contenu | Preuve |
|---------|---------|--------|
| Introduction | Demande de test (citation) + date | — |
| Résumé | Tableau des totaux pass/fail/skip | — |
| Preuve d'exécution | GIF animé intégré | GIF (aussi webcard) |
| Enregistrement vidéo | Intégration MP4 avec contrôles | MP4 |
| Grille de test par défaut | Lignes pass/fail par page | — |
| Tests détaillés des widgets | Pass/fail par widget (si détaillé) | — |
| Conclusion | Évaluation auto-générée | — |

## Artéfacts de preuve

- **GIF animé** : Full HD (1920x1080), 2s par image, utilisé comme webcard (`og_image`)
- **Vidéo MP4** : Résolution auto-ajustée (limite MP4_MAX_MB), 2s par image
- **Images PNG** : Captures d'écran individuelles pour inspection détaillée

## Scanner DOM

Le moteur de test scanne l'iframe de chaque page à la recherche de widgets interactifs :

| Type de widget | Découverte | Action de déclenchement |
|---------------|------------|------------------------|
| Bouton | `<button>` | clic |
| Lien | `<a href>` | vérifier que href existe |
| Sélecteur | `<select>` | changer vers option[1] |
| Accordéon | `<details>` | basculer ouvert/fermé |
| Onglet | `[role="tab"]` | clic pour activer |
| Case à cocher | `input[type=checkbox]` | basculer coché |
| Radio | `input[type=radio]` | basculer coché |
| Champ de saisie | `<input>`, `<textarea>` | vérifier l'existence |

## Trois vecteurs de découverte

1. **Code** — lire le HTML/JS/CSS source pour savoir quels widgets devraient exister
2. **Console** — exécuter du JS dans le contexte de la page pour interroger le DOM et inspecter l'état
3. **Visuel** — capture d'écran pour confirmer ce qui est réellement affiché et visible

## Références

- Compétence : `/test` — commande invocable par l'utilisateur
- Scripts : `web_test_engine.py`, `generate_test_report.py`, `render_web_page.py`
- Routage : `routing.json` → route `test-report-generation`
- Section : `docs/data/tests.json` → TESTS dans le navigateur
