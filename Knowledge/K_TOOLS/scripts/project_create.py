#!/usr/bin/env python3
"""Crée un nouveau projet avec enregistrement local et intégration GitHub.

Syntaxe officielle : project create [title]

Le programme :
1. Enregistre le projet localement (.claude/projects.json)
2. Crée un GitHub Project board (Projects v2) et le lie au repo
3. Crée une GitHub Issue de tracking pour le projet
4. Lie l'issue au Project board

Le repo cible est obtenu via :
- Variable d'environnement KNW_A3 (valeur du knowledge A3)
- Ou détection automatique depuis git remote

Usage:
  python3 scripts/project_create.py "Mon titre de projet"
"""
import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# scripts/ -> K_TOOLS/ -> Knowledge/ -> ROOT
MODULE_DIR = os.path.dirname(SCRIPT_DIR)
PROJECT_ROOT = os.path.dirname(os.path.dirname(MODULE_DIR))
PROJECTS_PATH = os.path.join(PROJECT_ROOT, "docs", "data", "projects.json")


def charger_projets():
    """Charge la liste des projets existants."""
    if os.path.exists(PROJECTS_PATH):
        with open(PROJECTS_PATH, "r") as f:
            return json.load(f)
    return {"projets": []}


def sauvegarder_projets(data):
    """Sauvegarde la liste des projets."""
    os.makedirs(os.path.dirname(PROJECTS_PATH), exist_ok=True)
    with open(PROJECTS_PATH, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def detecter_repo():
    """Détecte le repo owner/name depuis git remote.

    Note: KNW_A3 contient le nom du *projet* (pas du repo). Pour project create,
    A3 = le titre du projet en cours de création. Le repo cible est toujours
    déterminé depuis git remote origin.
    """
    owner = ""
    repo_name = ""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5
        )
        url = result.stdout.strip()
        # Parse: https://github.com/owner/repo, git@github.com:owner/repo,
        # or proxy format http://proxy@host/git/owner/repo
        parts = url.rstrip("/").rstrip(".git").split("/")
        if len(parts) >= 2:
            owner = parts[-2]
            repo_name = parts[-1]
    except (subprocess.TimeoutExpired, OSError):
        pass

    if not owner:
        owner = "packetqc"  # Fallback

    if repo_name:
        return f"{owner}/{repo_name}"
    return None


def creer_github_project(titre, repo):
    """Crée le GitHub Project board, l'issue de tracking, et les lie.

    Returns:
        Dict avec les résultats ou None si GitHub n'est pas disponible.
    """
    # Importer gh_helper depuis le même répertoire
    sys.path.insert(0, SCRIPT_DIR)
    try:
        from gh_helper import GitHubHelper
    except ImportError:
        print("  GitHub: gh_helper.py non trouvé, skip GitHub integration.")
        return None

    if not os.environ.get("GH_TOKEN"):
        print("  GitHub: GH_TOKEN non défini, skip GitHub integration.")
        return None

    gh = GitHubHelper()
    owner, repo_name = repo.split("/", 1)
    resultats = {}

    # Étape 1 : Créer le Project board
    print(f"  GitHub: Création du Project board '{titre}'...")
    board = gh.project_ensure(titre, owner, repo_name)
    if "error" in board:
        print(f"  GitHub: Erreur board — {board['error']}")
        return None
    resultats["board"] = board
    print(f"  GitHub: Board #{board['number']} créé → {board['url']}")

    # Étape 2 : Créer l'issue de tracking
    issue_title = f"PROJECT: {titre}"
    issue_body = (
        f"## Projet : {titre}\n\n"
        f"Issue de tracking pour le projet.\n\n"
        f"**Board:** #{board['number']}\n"
        f"**Repo:** {repo}\n"
    )
    print(f"  GitHub: Création de l'issue de tracking...")
    issue = gh.issue_create(repo, issue_title, issue_body, labels=["project"])
    if "number" not in issue:
        print(f"  GitHub: Erreur issue — {issue}")
        resultats["issue"] = None
        return resultats
    resultats["issue"] = issue
    print(f"  GitHub: Issue #{issue['number']} créée → {issue['html_url']}")

    # Étape 3 : Lier l'issue au Project board
    print(f"  GitHub: Liaison issue → board...")
    item = gh.project_item_add(board["project_id"], issue["node_id"])
    if "id" in item:
        resultats["linked"] = True
        print(f"  GitHub: Issue #{issue['number']} liée au board #{board['number']}")
    else:
        resultats["linked"] = False
        print(f"  GitHub: Erreur liaison — {item}")

    return resultats


def main():
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print("Erreur : titre du projet manquant.")
        print("Usage : python3 scripts/project_create.py \"Mon titre de projet\"")
        sys.exit(1)

    titre = sys.argv[1].strip()

    data = charger_projets()

    # Vérifier doublon par titre (insensible à la casse)
    for projet in data["projets"]:
        if projet["titre"].lower() == titre.lower():
            print(f"Faux — le projet \"{projet['titre']}\" existe déjà (P{projet['id']}). "
                  f"Utilisez le projet existant au lieu d'en créer un nouveau.")
            sys.exit(1)

    # Détecter le repo cible
    repo = detecter_repo()

    # Étape 1 : Enregistrement local
    nouveau_id = len(data["projets"]) + 1
    projet = {
        "id": nouveau_id,
        "titre": titre,
        "repo": repo,
    }

    # Étape 2 : Intégration GitHub (si disponible)
    github_result = None
    if repo:
        print(f"  Repo cible : {repo}")
        github_result = creer_github_project(titre, repo)
        if github_result:
            if github_result.get("board"):
                projet["board_number"] = github_result["board"]["number"]
                projet["board_url"] = github_result["board"]["url"]
                projet["project_id"] = github_result["board"]["project_id"]
            if github_result.get("issue"):
                projet["issue_number"] = github_result["issue"]["number"]
                projet["issue_url"] = github_result["issue"]["html_url"]
    else:
        print("  Repo non détecté, skip GitHub integration.")

    data["projets"].append(projet)
    sauvegarder_projets(data)

    print(f"Projet créé : {titre}")
    sys.exit(0)


if __name__ == "__main__":
    main()
