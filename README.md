# Twitch Recorder (Docker)

Application FastAPI qui surveille des chaines Twitch, enregistre automatiquement les lives en MP4, gère les replays, des liens de partage publics (avec slug custom), et des playlists auto-ajoutées.

## Fonctionnalités

- Authentification admin (compte unique)
- Vérification des chaines toutes les minutes
- Enregistrement des streams avec Streamlink + FFmpeg (H.264 + AAC)
- Replays renommables
- Partage public via `/share/{slug|token}`
- Slug custom optionnel (`^[a-zA-Z0-9_-]{3,80}$`) avec collision 409
- Playlists + auto-ajout à la fin d'un live par chaîne

## Démarrage rapide

1. Copier `.env.example` vers `.env` et remplir `TWITCH_CLIENT_ID`, `TWITCH_CLIENT_SECRET`.
2. Lancer:

```bash
docker compose up --build
```

3. Ouvrir l'UI admin: http://localhost:8000
4. Se connecter avec `ADMIN_USERNAME` / `ADMIN_PASSWORD`.

## Variables d'environnement

- `APP_SECRET` : secret de session
- `ADMIN_USERNAME` : nom d'utilisateur admin
- `ADMIN_PASSWORD` : mot de passe admin
- `TWITCH_CLIENT_ID` : identifiant Twitch API
- `TWITCH_CLIENT_SECRET` : secret Twitch API
- `POLL_INTERVAL_SECONDS` : intervalle de polling (60 par défaut)
- `DATA_DIR` : dossier des replays
- `DB_PATH` : base SQLite persistante

## Endpoints

### Admin
- `POST /api/auth/login`
- `GET /api/channels`
- `POST /api/channels`
- `PATCH /api/channels/{id}`
- `DELETE /api/channels/{id}`
- `GET /api/recordings`
- `PATCH /api/recordings/{id}`
- `POST /api/recordings/{id}/share`
- `DELETE /api/recordings/{id}/share`
- `GET /api/playlists`
- `POST /api/playlists`
- `PATCH /api/playlists/{id}`
- `DELETE /api/playlists/{id}`
- `POST /api/playlists/{id}/items`
- `DELETE /api/playlists/{id}/items/{recording_id}`
- `GET /api/watch/{id}`
- `GET /api/media/{id}`

### Public
- `GET /share/{key}` : page de lecture
- `GET /share/{key}/media` : flux vidéo
- `GET /healthz`
