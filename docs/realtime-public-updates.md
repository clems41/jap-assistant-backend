# Rafraîchissement temps réel des pages publiques (WebSocket)

Ce document décrit le contrat WebSocket à intégrer côté front public
(`/public/tournaments/{public_code}`) pour que les pages tableau/matchs/paires
se rafraîchissent automatiquement quand un JAP modifie une donnée, sans
recharger la page.

## Principe : un signal d'invalidation, pas un flux de données

Le WebSocket ne transporte **jamais** le score, le placement ou toute autre
donnée métier. Il transporte uniquement un signal "la ressource X de ce
tournoi a changé" — c'est au front de refetcher l'endpoint REST public
correspondant (déjà existant, déjà la source de vérité). Ça évite de
dupliquer la sérialisation côté WebSocket et tout risque de divergence entre
ce que le WS annonce et ce que l'API REST renvoie réellement.

Concrètement : ouvrez **une connexion WebSocket par tournoi affiché**, et à
chaque message reçu, refetchez le(s) endpoint(s) REST concerné(s).

## Connexion

Une connexion par `public_code`, aucune authentification requise :

| Environnement | URL |
|---|---|
| Local | `ws://localhost:8000/ws/public/tournaments/{public_code}/` |
| Prod  | `wss://<domaine-api>/ws/public/tournaments/{public_code}/` |

- Si `public_code` n'existe pas, le serveur ferme immédiatement la connexion
  avec le code `4404`.
- La connexion est unidirectionnelle (serveur → client) : n'envoyez rien sur
  le socket, ce n'est pas traité.

## Format des messages

```json
{
  "type": "tournament.update",
  "resources": ["matches", "bracket"]
}
```

`resources` est une liste non vide parmi : `"tournament"`, `"matches"`,
`"bracket"`, `"pairs"`. Un même message peut contenir plusieurs ressources
(ex : saisir un score touche à la fois `matches`, `bracket`, et parfois
`tournament` si le tournoi se termine).

### Table de correspondance ressource → endpoint REST public à refetcher

| `resources[]` | Endpoint REST à refetcher |
|---|---|
| `tournament` | `GET /api/v1/public/tournaments/{code}/` |
| `matches`    | `GET /api/v1/public/tournaments/{code}/matches/` |
| `bracket`    | `GET /api/v1/public/tournaments/{code}/bracket/` |
| `pairs`      | `GET /api/v1/public/tournaments/{code}/pairs/` |

Ne refetchez que les endpoints listés dans `resources` — pas besoin de tout
recharger à chaque message.

## Exemple d'intégration Angular (RxJS)

Service dédié à une connexion par tournoi, avec reconnexion automatique
(backoff exponentiel) — un drop réseau ne doit pas arrêter silencieusement le
rafraîchissement :

```typescript
// public-tournament-updates.service.ts
import { Injectable, OnDestroy } from '@angular/core';
import { Observable, Subject, timer } from 'rxjs';
import { webSocket, WebSocketSubject } from 'rxjs/websocket';
import { retry, share, tap } from 'rxjs/operators';

export type PublicResource = 'tournament' | 'matches' | 'bracket' | 'pairs';

export interface TournamentUpdateMessage {
  type: 'tournament.update';
  resources: PublicResource[];
}

@Injectable()
export class PublicTournamentUpdatesService implements OnDestroy {
  private socket$?: WebSocketSubject<TournamentUpdateMessage>;
  private readonly destroyed$ = new Subject<void>();

  connect(publicCode: string): Observable<TournamentUpdateMessage> {
    const url = `${this.wsBaseUrl()}/ws/public/tournaments/${publicCode}/`;

    this.socket$ = webSocket<TournamentUpdateMessage>(url);

    return this.socket$.pipe(
      retry({
        delay: (_, retryCount) =>
          // backoff exponentiel plafonné à 30s : 1s, 2s, 4s, 8s, 16s, 30s, 30s...
          timer(Math.min(1000 * 2 ** retryCount, 30_000)),
      }),
      share(),
    );
  }

  private wsBaseUrl(): string {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${environment.apiHost}`;
  }

  ngOnDestroy(): void {
    this.destroyed$.next();
    this.socket$?.complete();
  }
}
```

Usage dans un composant de page publique — refetch ciblé selon `resources` :

```typescript
this.updates
  .connect(this.publicCode)
  .pipe(takeUntil(this.destroy$))
  .subscribe((msg) => {
    if (msg.resources.includes('matches')) this.matchesStore.refetch();
    if (msg.resources.includes('bracket')) this.bracketStore.refetch();
    if (msg.resources.includes('pairs')) this.pairsStore.refetch();
    if (msg.resources.includes('tournament')) this.tournamentStore.refetch();
  });
```

Points d'attention :
- Fermez explicitement la connexion (`socket$.complete()`) sur
  `ngOnDestroy`/changement de route — sinon elle reste ouverte côté serveur.
- `rxjs/websocket` avec `retry` + `timer` gère la reconnexion ; pensez à
  re-déclencher un refetch complet (les 4 endpoints) juste après une
  reconnexion réussie, au cas où des messages auraient été manqués pendant
  la coupure.
- N'utilisez **pas** le contenu du message comme source de données — il ne
  sert qu'à déclencher un refetch REST.

## Notes de déploiement

- **`ALLOWED_HOSTS` doit inclure le domaine du front public.** Django Channels
  valide l'en-tête `Origin` de la requête WebSocket via
  `AllowedHostsOriginValidator`, qui réutilise `ALLOWED_HOSTS` (pas
  `CORS_ALLOWED_ORIGINS`, qui ne s'applique qu'aux requêtes HTTP classiques).
  Si le front public est sur un domaine différent de l'API, ce domaine doit
  être ajouté à la variable d'env `ALLOWED_HOSTS` côté backend, sinon la
  connexion WebSocket sera rejetée alors même que les appels REST
  fonctionnent.
- **Passthrough WebSocket sur Railway** : l'app est servie en ASGI
  (`gunicorn -k uvicorn.workers.UvicornWorker`), HTTP et WebSocket sur le même
  port — Railway gère normalement ça nativement, mais à vérifier en
  environnement de dev/staging avant la mise en prod (tester une connexion
  réelle depuis le domaine du front, pas seulement en local).
- Redis (déjà provisionné en prod pour Celery) sert aussi de channel layer
  Channels — aucune ressource supplémentaire à provisionner.
