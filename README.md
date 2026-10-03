# 📚 BookFlow Studio

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![CLI Tool](https://img.shields.io/badge/CLI-Typer%20%26%20Rich-magenta.svg)](https://typer.tiangolo.com/)
[![Tests](https://img.shields.io/badge/tests-pytest-brightgreen.svg)](https://docs.pytest.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **CLI d'ingénierie bibliographique** pour l'audit, le renommage normalisé et l'enrichissement automatique de métadonnées pour corpus d'ePubs et de PDFs (via Dublin Core, heuristiques de releases scene et API Open Library).

---

## 🎯 Problématique & Solution

Dans les bibliothèques d'e-books volumineuses (packs de 6 000+ ePubs, téléchargements communautaires, archives de romans), les fichiers souffrent couramment de :
- Noms de releases "scene" encombrés : `Bernard.Minier.2020.Le.Commandant.Servaz.T6.La.Vallee.FRENCH.Epub-NoGRP.epub`
- Métadonnées internes Dublin Core incomplètes ou erratiques.
- Titres pollués : `Tombes oubliées (French Edition)`.
- Absence d'indexation des séries et numéros de tomes pour liseuses (Kobo, Kindle, Apple Books).

**BookFlow Studio** résout ce défi de bout en bout grâce à un pipeline robuste en 5 phases :

```mermaid
flowchart TD
    A["📁 Fichier Source (EPUB / PDF)"] --> B["🔍 Phase 1 : Extraction Interne\n(Dublin Core, Calibre OPF, EPUB3)"]
    A --> C["🧩 Phase 2 : Parseur Heuristique\n(Tags scene, Détection T1/Tome, Année)"]
    B --> D["⚖️ Fusion & Arbitrage Métadonnées"]
    C --> D
    D --> E{"🌐 Métadonnées Complètes ?"}
    E -- Non / --enrich --> F["🏛️ API Open Library\n(Search & Works, Cache SQLite)"]
    E -- Oui --> G["✨ Normalisation Stricte"]
    F --> G
    G --> H["🏷️ Nommage Standard :\nPrénom Nom - Série T01 - Titre.epub"]
    H --> I{"🛡️ Mode d'Exécution"}
    I -- "--dry-run" --> J["📋 Rapport Prévisualisation Rich"]
    I -- "--execute" --> K["🚀 Déplacement / Copie Physique\n+ Écriture Métadonnées EPUB"]
```

---

## 🏷️ Convention de Nommage

BookFlow applique par défaut une convention **lisible, élégante et sans ambiguïté** (`--naming-style standard`), préservant les prénoms, les accents et les apostrophes :

### 1. Style Standard (Par défaut — recommandé pour Finder, liseuses & Calibre)
- **Avec Série & Tome :**
  ```text
  Prénom Nom - Série T01 - Titre.epub
  ```
  *Exemples :*
  - `Bernard Minier - Le Commandant Servaz T06 - La Vallée.epub`
  - `Jean-Christophe Grangé - Sans Soleil T01 - Disco Inferno.epub`
  - `Douglas Preston & Lincoln Child - Nora Kelly T01 - Tombes Oubliées.epub`
  - `Isaac Asimov - Fondation T01 - Fondation.epub`

- **Sans Série (One-shot) :**
  ```text
  Prénom Nom - Titre.epub
  ```
  *Exemples :*
  - `Alain Damasio - La Horde du Contrevent.epub`
  - `Bruce Benamran - L'Ultime Expérience.epub`

### 2. Styles Alternatifs Disponibles (`--naming-style`)
- **`--naming-style bracket`** : `Prénom Nom - [Série 01] - Titre.epub`
- **`--naming-style posix`** : `Nom_Série_01_Titre.epub` (slug sans espace)

---

## 🚀 Installation & Démarrage Rapide

### Prérequis
- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/) (recommandé pour la rapidité)

### 1. Installation globale CLI via `uv tool`
```bash
git clone https://github.com/Boblebol/bookflow.git
cd bookflow
uv tool install --editable .
```

La commande `bookflow` est immédiatement accessible dans votre terminal.

---

## 🛠️ Commandes & Guide d'Utilisation

### 1. `bookflow scan` — Auditer un répertoire
Analyse l'état de votre bibliothèque, liste les formats, détecte les séries et identifie les métadonnées manquantes :
```bash
bookflow scan "/Volumes/WD_BLACK/Media/books"
```

### 2. `bookflow inspect` — Inspection approfondie d'un livre
Extrait et affiche l'ensemble des métadonnées internes, simule la recherche Open Library et montre le nommage normalisé calculé :
```bash
bookflow inspect "/chemin/vers/Bernard.Minier.2020.Le.Commandant.Servaz.T6.La.Vallee.FRENCH.Epub-NoGRP.epub"
```

### 3. `bookflow organize` — Normaliser et ranger
Par défaut, `bookflow organize` s'exécute en **mode simulation sécurisé (`--dry-run`)** :

```bash
# Simulation sans toucher aux fichiers
bookflow organize "/Volumes/WD_BLACK/Media/books/Sans soleil 2T"

# Rangement physique effectif (copie ou déplacement)
bookflow organize "/Volumes/WD_BLACK/Media/books/Sans soleil 2T" --target "/Volumes/WD_BLACK/Media/books_clean" --execute

# Rangement avec mise à jour des métadonnées internes de l'EPUB
bookflow organize "/source/books" --target "/clean/books" --execute --write-metadata
```

#### Options clés :
| Option | Rôle | Valeur par défaut |
| :--- | :--- | :--- |
| `--dry-run / --execute` | Protection anti-erreur (simulation vs exécution réelle) | `--dry-run` |
| `--target / -t` | Répertoire de destination (ou sur place si omis) | Répertoire source |
| `--mode / -m` | Action physique : `move` (déplacement) ou `copy` (copie) | `move` |
| `--structure / -s` | Arborescence : `hierarchical` (`Auteur/Série/Livre`) ou `flat` | `hierarchical` |
| `--enrich / --no-enrich` | Interrogation externe d'Open Library si nécessaire | `--enrich` |
| `--write-metadata / -w` | Réécriture atomique des tags Dublin Core / Calibre dans l'ePub | `False` |
| `--author-format / -a` | Format auteur : `last` (Asimov), `full` (Isaac-Asimov), `last-first` | `last` |
| `--preserve-accents` | Conserver les accents dans les noms de fichiers | `False` (strip accents) |

### 4. `bookflow lookup` — Interroger l'API Open Library
Recherche directe sur les millions d'œuvres répertoriées par Internet Archive :
```bash
bookflow lookup "Fondation" --author "Isaac Asimov"
```

---

## 🧪 Tests & Qualité de Code

Le projet est testé unitairement avec `pytest` :
```bash
uv run pytest -v
```

Tests couverts :
- Détection et nettoyage des releases scene (groupes de release, tags de codec, numéros de tomes `T1`, `T01`, `Tome 6`).
- Normalisation et extraction des noms d'auteurs (particules, auteurs multiples, inversion nom/prénom).
- Casing intelligent des titres francophones et anglophones (`stop-words` respectés).
- Cache SQLite Open Library et tolérance aux pannes réseau.
- Écriture atomique sécurisée dans les fichiers EPUB sans corruption d'archive.

---

## 📄 Licence

Distribué sous licence **MIT**. Voir [`LICENSE`](LICENSE) pour plus de détails.
