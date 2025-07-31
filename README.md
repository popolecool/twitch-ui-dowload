# Twitch Stream Downloader

Une application web moderne pour télécharger et enregistrer automatiquement des flux Twitch en temps réel avec détection automatique et mode faible consommation.

## 🚀 Fonctionnalités

- **Enregistrement en temps réel** : Capturez les streams Twitch pendant qu'ils sont diffusés
- **Détection automatique** : Vérification automatique du statut en live des streamers
- **Gestion multiple de streams** : Ajoutez et gérez plusieurs streams simultanément
- **Formats vidéo multiples** : Support MP4 et MKV
- **Mode faible consommation** : Enregistrement en segments avec traitement différé
- **Traitement intelligent** : Fusion automatique des segments quand aucun stream n'est actif
- **Interface web intuitive** : Interface utilisateur moderne et responsive
- **Qualité configurable** : Choisissez la qualité d'enregistrement (de 160p à 1080p60)
- **Réplication automatique** : Sauvegarde automatique vers serveurs FTP ou SMB/CIFS
- **Historique des enregistrements** : Visualisez et téléchargez vos enregistrements passés
- **Aperçu vidéo** : Prévisualisez vos enregistrements directement dans le navigateur
- **Gestion des segments** : Interface dédiée pour le traitement des segments

## 📋 Prérequis

- Python 3.6 ou supérieur
- Streamlink (pour l'enregistrement des streams)
- FFmpeg (pour le mode faible consommation)
- Connexion Internet stable

## 🛠️ Installation

1. **Cloner le projet**
   ```bash
   git clone <url-du-repo>
   cd twitch-ui-dowload
   ```

2. **Installer les dépendances Python**
   ```bash
   pip install -r requirements.txt
   ```

3. **Installer Streamlink**
   ```bash
   pip install streamlink
   ```
   
   Ou suivez les instructions officielles : https://streamlink.github.io/install.html

4. **Installer FFmpeg** (requis pour le mode faible consommation)
   - Windows : Téléchargez depuis https://ffmpeg.org/download.html
   - Linux : `sudo apt install ffmpeg`
   - macOS : `brew install ffmpeg`

5. **Lancer l'application**
   ```bash
   python app.py
   ```

6. **Accéder à l'interface web**
   Ouvrez votre navigateur et allez à : http://localhost:5000

## 📖 Utilisation

### Ajouter un Stream

1. Allez dans la section "Streams"
2. Cliquez sur "Ajouter un Stream"
3. Entrez le nom du stream et l'URL Twitch
4. Cliquez sur "Ajouter"

### Vérifier le Statut en Live

1. Dans la liste des streams, cliquez sur l'icône satellite pour vérifier manuellement
2. Le statut s'affiche automatiquement : "En Live" (vert) ou "Hors ligne" (rouge)
3. La vérification automatique se fait toutes les 2 minutes

### Démarrer un Enregistrement

1. Dans la liste des streams, cliquez sur "Enregistrer" pour le stream souhaité
2. L'enregistrement démarre automatiquement
3. Le statut passe à "En cours d'enregistrement" avec un indicateur rouge clignotant

### Mode Faible Consommation

1. Activez le mode dans "Paramètres" > "Mode faible consommation"
2. Les streams sont enregistrés en segments dans le dossier `temp_segments/`
3. Les segments sont traités automatiquement selon la configuration :
   - **Manuel** : Via la page "Traitement"
   - **Programmé** : À l'heure configurée
   - **Intelligent** : Quand aucun stream n'est actif

### Gérer le Traitement des Segments

1. Allez dans "Traitement"
2. Visualisez la file d'attente et le statut du système
3. Traitez manuellement les segments en attente
4. Surveillez les enregistrements actifs et les segments temporaires

### Configurer les Paramètres

1. Allez dans "Paramètres"
2. Configurez :
   - **Qualité d'enregistrement** : Choisissez la résolution souhaitée
   - **Format vidéo** : MP4 ou MKV
   - **Détection automatique** : Vérification automatique des streams
   - **Mode faible consommation** : Enregistrement en segments
   - **Réplication automatique** : Sauvegarde FTP/SMB

## ⚙️ Configuration

### Fichier de Configuration

L'application utilise un fichier `config.json` :

```json
{
    "quality": "best",
    "video_format": "mp4",
    "auto_check_live": true,
    "check_interval": 5,
    "low_power_mode": false,
    "auto_process_time": "03:00",
    "smart_processing": true,
    "ftp_enabled": false,
    "ftp_host": "",
    "ftp_port": 21,
    "ftp_username": "",
    "ftp_password": "",
    "ftp_path": "/recordings",
    "smb_enabled": false,
    "smb_host": "",
    "smb_share": "",
    "smb_username": "",
    "smb_password": "",
    "smb_path": "/recordings"
}
```

### Nouvelles Options

- **video_format** : Format de sortie (mp4 ou mkv)
- **auto_check_live** : Vérification automatique du statut en live
- **check_interval** : Intervalle de vérification en minutes (1-60)
- **low_power_mode** : Mode faible consommation avec enregistrement en segments
- **auto_process_time** : Heure de traitement automatique des segments (format HH:MM)
- **smart_processing** : Traitement intelligent quand aucun stream n'est actif

### Qualités d'Enregistrement Disponibles

- `best` : Meilleure qualité disponible (recommandé)
- `1080p60` : 1080p à 60fps
- `1080p` : 1080p à 30fps
- `720p60` : 720p à 60fps
- `720p` : 720p à 30fps
- `480p` : 480p
- `360p` : 360p
- `160p` : Audio seulement
- `worst` : Qualité la plus basse

## 📁 Structure des Fichiers

```
twitch-ui-dowload/
├── app.py                 # Application Flask principale
├── requirements.txt       # Dépendances Python
├── README.md             # Documentation
├── config.json           # Configuration (généré automatiquement)
├── streams.json          # Liste des streams (généré automatiquement)
├── recordings/           # Dossier des enregistrements finaux
├── temp_segments/        # Segments temporaires (mode faible consommation)
└── templates/            # Templates HTML
    ├── base.html
    ├── index.html
    ├── streams.html
    ├── recordings.html
    ├── processing.html
    └── settings.html
```

## 🔧 API Endpoints

### Pages
- `GET /` : Page d'accueil
- `GET /streams` : Gestion des streams
- `GET /recordings` : Visualisation des enregistrements
- `GET /processing` : Traitement des segments
- `GET /settings` : Configuration

### API Streams
- `GET|POST|DELETE /api/streams` : API des streams
- `GET /api/check_live/<stream_name>` : Vérifier le statut en live

### API Enregistrements
- `POST /api/start_recording` : Démarrer un enregistrement
- `POST /api/stop_recording` : Arrêter un enregistrement
- `GET /api/recordings` : Liste des enregistrements
- `DELETE /api/recordings/<filename>` : Supprimer un enregistrement
- `GET /api/download/<filename>` : Télécharger un enregistrement

### API Traitement
- `POST /api/process_segments` : Traiter manuellement les segments
- `GET /api/processing_queue` : État de la file d'attente
- `GET /api/system_status` : Statut du système

### API Configuration
- `GET|POST /api/settings` : Gestion de la configuration

## 🚨 Dépannage

### Streamlink non trouvé
```bash
# Vérifiez l'installation
streamlink --version

# Réinstallez si nécessaire
pip install --upgrade streamlink
```

### FFmpeg non trouvé (mode faible consommation)
```bash
# Vérifiez l'installation
ffmpeg -version

# Ajoutez FFmpeg au PATH si nécessaire
```

### Erreur de permissions
- Assurez-vous que les dossiers `recordings/` et `temp_segments/` sont accessibles en écriture
- Vérifiez les permissions du répertoire de travail

### Problèmes de détection automatique
- Vérifiez la connectivité Internet
- Augmentez l'intervalle de vérification si nécessaire
- Consultez les logs de l'application

### Problèmes de traitement des segments
- Vérifiez que FFmpeg est installé et accessible
- Consultez la page "Traitement" pour voir les erreurs
- Vérifiez l'espace disque disponible

## 📝 Notes

- Les enregistrements sont sauvegardés au format MP4 ou MKV selon la configuration
- Le mode faible consommation réduit l'utilisation CPU/mémoire pendant l'enregistrement
- La détection automatique vérifie le statut des streamers à intervalles réguliers
- Le traitement intelligent optimise l'utilisation des ressources
- L'application fonctionne en arrière-plan pendant les enregistrements
- Les fichiers de configuration sont créés automatiquement au premier lancement

## 📄 Licence

Ce projet est sous licence MIT. Voir le fichier LICENSE pour plus de détails.