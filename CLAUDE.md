# JAP Assistant — Backend

API REST pour la gestion de tournois de padel, destinée aux Juges Arbitres de Padel (JAP).

## Tech Stack

| Outil | Usage |
|-------|-------|
| Python 3.13 | Langage |
| Django 5.1+ | Framework web |
| Django REST Framework 3.15+ | API REST |
| djangorestframework-simplejwt | Auth JWT |
| PostgreSQL 17 | Base de données |
| Redis 7 | Canal WebSocket + broker Celery |
| Django Channels | WebSockets (temps réel) |
| Celery | Tâches asynchrones |
| uv | Gestion dépendances & virtualenv |
| pytest + factory-boy | Tests |
| ruff | Linting |
| Docker + Docker Compose | Environnements local & dev |

## Structure du projet

```
config/
  settings/
    base.py       # Settings communs
    local.py      # Dev local (Docker)
    dev.py        # Staging
    prod.py       # Production (Railway)
  urls.py
  asgi.py         # ASGI + WebSocket routing
  routing.py      # WebSocket URL patterns

apps/
  users/          # Auth JWT, profil utilisateur
  common/         # TimeStampedModel, utilitaires partagés
  tournaments/    # Tournois, catégories, tableaux (à créer)
  players/        # Joueurs, inscriptions, paires (à créer)
  matches/        # Matchs, scores, arbitrage (à créer)
  notifications/  # Temps réel WebSocket + Celery (à créer si besoin)

docker/
  local/          # Dockerfile dev (hot reload)
  prod/           # Dockerfile prod (gunicorn + uvicorn)

docker-compose.yml      # Local (avec hot reload)
docker-compose.dev.yml  # Dev/staging
```

## Démarrage local

```bash
# 1. Copier les variables d'environnement
cp .env.example .env

# 2. Lancer les services (DB + Redis + API avec hot reload)
docker compose up

# 3. Créer un superuser (dans un autre terminal)
docker compose exec api uv run python manage.py createsuperuser

# L'API est disponible sur http://localhost:8000
# Swagger UI : http://localhost:8000/api/docs/
```

## Commandes courantes

```bash
# Tests
uv run pytest

# Tests avec couverture
uv run pytest --cov

# Linting
uv run ruff check .
uv run ruff format .

# Migrations
uv run python manage.py makemigrations
uv run python manage.py migrate

# Shell Django
uv run python manage.py shell
```

## Conventions

### Language
- **Code en anglais** : noms de variables, fonctions, classes, commentaires, docstrings, messages de commit, noms de tests, champs de modèles, champs de serializers, noms d'URL
- **Contenu utilisateur en français** : messages d'erreur, labels, valeurs d'enum exposées à l'utilisateur — l'app est destinée à un public francophone uniquement, sans besoin de traduction

### Architecture
- **Settings** : ne jamais modifier `base.py` pour du config spécifique à un env — utiliser `local.py`, `dev.py` ou `prod.py`
- **Apps Django** : chaque app dans `apps/` a sa propre responsabilité métier. Créer une nouvelle app avec `uv run python manage.py startapp <name>` puis la déplacer dans `apps/`
  - **Quand créer une nouvelle app** : quand le domaine métier est distinct et a son propre cycle de vie (ex: `tournaments`, `players`, `matches`). Ne pas créer une app pour 1-2 modèles accessoires qui appartiennent clairement à un domaine existant.
  - **Répartition modèles/views** : un modèle et ses views vont dans la même app. Suivre le modèle dominant — si une view manipule principalement `Tournament`, elle va dans `tournaments/`. Les imports cross-apps sont normaux (ex: `matches` importe `Tournament` et `Player`), mais doivent aller dans une seule direction pour éviter les imports circulaires.
  - **Code partagé** : mixins, validators, utilitaires → `apps/common/`. Intégrations externes (Stripe, email) → app dédiée.
- **URLs** : versionnées sous `/api/v1/`, enregistrées dans `config/urls.py`
- **Modèles** : toujours utiliser `AUTH_USER_MODEL` (jamais importer `User` directement), `ATOMIC_REQUESTS=True` activé
- **Modèle de base** : tout modèle métier doit hériter de `TimeStampedModel` (défini dans `apps/common/models.py`) pour avoir `created_at` et `updated_at` automatiquement. Exception : `User` qui hérite de `AbstractUser` (qui fournit déjà `date_joined`)
  ```python
  from apps.common.models import TimeStampedModel

  class Tournament(TimeStampedModel):
      ...
  ```
  > ⚠️ `updated_at` n'est **pas** mis à jour par `QuerySet.update()` — seulement par `.save()`. Si besoin, passer `update_fields=["field", "updated_at"]`.

### Code Python
- Type hints sur toutes les fonctions
- Pas de `import *` sauf dans les settings enfants (`from .base import *`)
- Nommage : `snake_case` pour variables/fonctions, `PascalCase` pour classes
- Longueur de ligne : 88 caractères (ruff)

### API / DRF
- Serializers séparés des views (jamais de logique métier dans les views)
- Utiliser `generics.*` ou `ModelViewSet` selon le cas
- Toujours définir `permission_classes` explicitement sur chaque view
- Retourner des codes HTTP sémantiques (201 pour création, 204 pour suppression, etc.)
- Pagination activée par défaut (20 items)

### Gestion des erreurs

Toutes les erreurs API suivent un format unifié géré par `apps.common.exceptions.custom_exception_handler` (enregistré via `REST_FRAMEWORK["EXCEPTION_HANDLER"]`).

**Format de réponse d'erreur :**
```json
{
  "message":   "Les données envoyées sont invalides.",
  "code":      "validation_error",
  "fields":    { "email": ["Ce champ est requis."] },
  "detail":    "ValidationError: ...",
  "traceback": "Traceback (most recent call last): ..."
}
```
- `message` — message lisible par l'utilisateur, **en français**, à afficher côté front
- `code` — code machine (ex: `validation_error`, `not_found`, `authentication_failed`)
- `fields` — erreurs par champ, **présent uniquement pour les 400 de validation**
- `detail` — message dev avec type d'exception + message — **présent uniquement si `DEBUG=True`**
- `traceback` — stacktrace Python — **présent uniquement si `DEBUG=True`**

**Règles :**
- Ne jamais retourner `Response({"field": "error"}, status=400)` manuellement — utiliser `raise ValidationError({"field": ["message."]})`
- Les 500 non gérés sont automatiquement catchés, loggés et retournés dans ce format
- Les messages `message` et les valeurs de `fields` sont **en français** (public francophone)
- Les messages `detail` sont **en anglais** (devs)

### Swagger (drf-spectacular)
- **Tout endpoint doit être visible dans `/api/docs/`** — c'est une exigence, pas une option
- `generics.*` et `ModelViewSet` : inférence automatique, rien à faire
- `APIView` : **obligatoire** d'ajouter `@extend_schema` sur chaque méthode, sinon body et réponses n'apparaissent pas :
  ```python
  from drf_spectacular.utils import extend_schema

  class MyView(APIView):
      @extend_schema(request=MySerializer, responses={200: MySerializer})
      def post(self, request): ...
  ```

### TDD
- **Red → Green → Refactor** : écrire le test qui échoue d'abord
- Tests dans `apps/<app>/tests/test_<feature>.py`
- Factories dans `apps/<app>/tests/factories.py` (factory-boy)
- Fixtures pytest dans `conftest.py` (racine ou niveau app)
- Couverture minimale : 80% (enforced par pytest)
- Utiliser `@pytest.mark.django_db` et `APIClient` pour les tests d'intégration

### Variables d'environnement
- Toujours lire via `django-environ` (`env("VAR_NAME")`)
- Jamais hardcoder de secrets — même en local, passer par `.env`
- `.env` est gitignored — utiliser `.env.example` comme référence

## Environnements

| Env | Settings module | Docker compose |
|-----|----------------|----------------|
| Local | `config.settings.local` | `docker-compose.yml` |
| Dev/Staging | `config.settings.dev` | `docker-compose.dev.yml` |
| Production | `config.settings.prod` | Railway (Dockerfile prod) |

## Agents disponibles

- **`/tdd`** : Implémente une feature en TDD (tests d'abord, code ensuite)
- **`/api-review`** : Review un endpoint DRF (serializer, view, permissions, tests)
