# bots/json_utils.py
# Utilitaires JSON partagés

import json
import os
from typing import Dict, List, Optional, Any


def load_json_safe(path: str) -> Optional[Dict]:
    """
    Charge un fichier JSON de manière sécurisée.

    Args:
        path: Chemin du fichier

    Returns:
        Dictionnaire ou None si erreur/fichier inexistant
    """
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_json(data: Any, path: str, indent: int = 2) -> None:
    """
    Sauvegarde des données en JSON.

    Args:
        data: Données à sauvegarder
        path: Chemin du fichier
        indent: Indentation (default: 2)
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent)


def load_signals_log(path: str) -> List[Dict]:
    """
    Charge le fichier de log des signaux.

    Args:
        path: Chemin du fichier de log

    Returns:
        Liste des signaux ou liste vide si erreur
    """
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def save_signals_log(log: List[Dict], path: str, sort: bool = True) -> None:
    """
    Sauvegarde le fichier de log des signaux.

    Args:
        log: Liste des signaux
        path: Chemin du fichier de log
        sort: Si True, trie les signaux avant de sauvegarder
    """
    if sort:
        log = sorted(
            log,
            key=lambda e: (
                e.get("date_signal", ""),
                e.get("universe", ""),
                e.get("strategy", ""),
                e.get("ticker", ""),
            ),
        )

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2)
