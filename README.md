# JAP Assistant — Backend

API REST pour la gestion de tournois de padel, destinée aux **Juges Arbitres de Padel (JAP)**.

Construit avec Django REST Framework, PostgreSQL et Django Channels pour le temps réel.

---

## Contexte

Les JAP (Juges Arbitres de Padel) organisent et arbitrent les tournois de padel en France. Aujourd'hui, la gestion de ces tournois repose sur des tableurs Excel inadaptés à la mobilité et opaques pour les joueurs.

**JAP Assistant** est une application web mobile-first qui permet aux JAP de gérer leurs tournois depuis leur téléphone sur le terrain, et aux joueurs de suivre le déroulement en temps réel via QR code — sans créer de compte.

---

## Stack technique

| Outil | Rôle |
|-------|------|
| Python 3.13 | Langage |
| Django 6 | Framework web |
| Django REST Framework 3.16 | API REST |
| djangorestframework-simplejwt | Authentification JWT |
| PostgreSQL 17 | Base de données |
| Redis 7 | Canal WebSocket + broker Celery |
| Django Channels | WebSockets (mises à jour temps réel) |
| Celery | Tâches asynchrones |
| uv | Gestion des dépendances |
| Docker + Docker Compose | Environnements local & staging |
| pytest + factory-boy | Tests (TDD) |
| ruff | Linting & formatting |

---

## Prérequis

- [Docker](https://docs.docker.com/get-docker/) et Docker Compose
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (pour le développement hors Docker)

---

## Démarrage rapide (local)

```bash
# 1. Cloner le repo
git clone <url-du-repo>
cd jap-assistant-backend

# 2. Copier les variables d'environnement
cp .env.example .env

# 3. Lancer les services (PostgreSQL + Redis + API avec hot reload)
docker compose up

# 4. Dans un autre terminal — créer un superuser
docker compose exec api uv run python manage.py createsuperuser
```

L'API est disponible sur **http://localhost:8000**

| URL | Description |
|-----|-------------|
| `http://localhost:8000/api/v1/` | Base de l'API |
| `http://localhost:8000/api/docs/` | Swagger UI (documentation interactive) |
| `http://localhost:8000/api/schema/` | Schéma OpenAPI (JSON) |
| `http://localhost:8000/admin/` | Interface d'administration Django |

---

## Environnements

Trois configurations sont disponibles, sélectionnées via `DJANGO_SETTINGS_MODULE` :

| Environnement | Settings module | Commande |
|---------------|----------------|----------|
| **Local** | `config.settings.local` | `docker compose up` |
| **Staging/Dev** | `config.settings.dev` | `docker compose -f docker-compose.dev.yml up` |
| **Production** | `config.settings.prod` | Dockerfile prod (Railway) |

### Variables d'environnement

Copier `.env.example` en `.env` et ajuster les valeurs. Les variables clés :

```bash
SECRET_KEY=...               # Clé secrète Django
DATABASE_URL=...             # URL de connexion PostgreSQL
REDIS_URL=...                # URL Redis
CORS_ALLOWED_ORIGINS=...     # Origins autorisées pour le frontend
```

Pour la production, ajouter également `ALLOWED_HOSTS`, `EMAIL_*`, et optionnellement `SENTRY_DSN`.

---

## Développement

### Environnement virtuel local (pour l'IDE)

Le `.venv` utilisé par Docker est construit **à l'intérieur de l'image** (voir `docker/local/Dockerfile`) et n'est jamais monté dans le conteneur — il est totalement indépendant de tout `.venv` présent sur ta machine. Pour que ton IDE résolve les imports et arrête de signaler des erreurs sur les libs installées, il faut donc un `.venv` **local**, séparé de Docker :

```bash
uv sync --all-groups
```

Cette commande n'a aucun impact sur Docker : modifier ou supprimer ton `.venv` local ne casse rien côté conteneur, et inversement, rebuild l'image Docker ne touche pas à ton `.venv` local.

> ⚠️ Si `uv sync` échoue avec une erreur de permission sur `.venv` (ex: `Permission denied`), c'est que le dossier appartient à un autre utilisateur (souvent `root`, suite à une commande lancée par erreur avec `sudo`). Supprime-le puis relance :
> ```bash
> sudo rm -rf .venv
> uv sync --all-groups
> ```

### Commandes courantes

```bash
# Lancer les tests
uv run pytest

# Tests avec rapport de couverture
uv run pytest --cov

# Linter
uv run ruff check .

# Formatter
uv run ruff format .

# Créer des migrations
uv run python manage.py makemigrations

# Appliquer les migrations
uv run python manage.py migrate

# Shell Django
uv run python manage.py shell
```

### Ajouter une nouvelle app Django

```bash
# 1. Créer l'app
uv run python manage.py startapp <nom_app>

# 2. La déplacer dans apps/
mv <nom_app> apps/

# 3. Mettre à jour apps/<nom_app>/apps.py
#    → changer name = "<nom_app>" en name = "apps.<nom_app>"

# 4. L'enregistrer dans config/settings/base.py (LOCAL_APPS)
# 5. Ajouter ses URLs dans config/urls.py
```

### Structure du projet

```
jap-assistant-backend/
├── config/
│   ├── settings/
│   │   ├── base.py       # Settings communs à tous les envs
│   │   ├── local.py      # Dev local (hot reload, console email)
│   │   ├── dev.py        # Staging
│   │   └── prod.py       # Production
│   ├── urls.py           # Routage principal
│   ├── asgi.py           # ASGI + WebSocket routing
│   ├── routing.py        # WebSocket URL patterns
│   └── wsgi.py
├── apps/
│   └── users/            # Auth JWT, profil utilisateur
│       ├── models.py
│       ├── serializers.py
│       ├── views.py
│       ├── urls.py
│       └── tests/
│           ├── factories.py
│           └── test_auth.py
├── docker/
│   ├── local/            # Dockerfile dev (hot reload, uv sync)
│   └── prod/             # Dockerfile prod (gunicorn + uvicorn)
├── docs/
│   └── product-brief-jap-assistant-2026-01-13.md
├── .claude/
│   └── agents/
│       ├── tdd.md        # Agent TDD (Red→Green→Refactor)
│       └── api-review.md # Agent review DRF
├── docker-compose.yml      # Environnement local
├── docker-compose.dev.yml  # Environnement staging
├── pyproject.toml          # Dépendances & config outils
├── manage.py
├── CLAUDE.md               # Contexte projet pour Claude Code
└── .env.example            # Template des variables d'environnement
```

---

## API

### Authentification

L'API utilise JWT (JSON Web Tokens) via `djangorestframework-simplejwt`.

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `POST` | `/api/v1/auth/register/` | Créer un compte |
| `POST` | `/api/v1/auth/token/` | Obtenir access + refresh token |
| `POST` | `/api/v1/auth/token/refresh/` | Rafraîchir l'access token |
| `POST` | `/api/v1/auth/token/verify/` | Vérifier un token |
| `GET/PATCH` | `/api/v1/auth/me/` | Profil de l'utilisateur connecté |
| `POST` | `/api/v1/auth/me/change-password/` | Changer son mot de passe |

Inclure le token dans les requêtes authentifiées :
```
Authorization: Bearer <access_token>
```

---

## Tests

Le projet suit une approche **TDD (Test-Driven Development)** : les tests sont écrits avant l'implémentation.

```bash
# Lancer tous les tests
uv run pytest

# Tests d'une app spécifique
uv run pytest apps/users/

# Un fichier de test spécifique
uv run pytest apps/users/tests/test_auth.py -v

# Couverture détaillée
uv run pytest --cov --cov-report=html
# → ouvre htmlcov/index.html
```

La couverture minimale requise est de **80%** (enforced par pytest).

---

## Agents Claude Code

Deux agents sont configurés pour assister le développement :

- **`/tdd`** — Implémente une feature en TDD (écrit les tests d'abord, puis le code minimum pour les faire passer, puis refactorise)
- **`/api-review`** — Review un endpoint DRF sur une checklist complète (modèle, serializer, view, URLs, tests, sécurité)

---

## Déploiement (Production)

Le projet est configuré pour Railway, mais compatible avec tout hébergeur supportant Docker.

```bash
# Variables d'environnement requises en production
DJANGO_SETTINGS_MODULE=config.settings.prod
SECRET_KEY=<clé-secrète-forte>
DATABASE_URL=<url-postgresql>
REDIS_URL=<url-redis>
ALLOWED_HOSTS=<domaine.com>
CORS_ALLOWED_ORIGINS=<https://frontend.com>
```

Le serveur de production utilise **Gunicorn + Uvicorn workers** pour supporter à la fois les requêtes HTTP et les WebSockets.

## Mise à jour des classements

```bash
 docker compose exec api uv run python manage.py import_fft_rankings \
   --men input_pdf/classement_padel_france_homme_2026_03_mars.pdf \
   --women input_pdf/classement_padel_france_femme_2026_03_mars.pdf
```