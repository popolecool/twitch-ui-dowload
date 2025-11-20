# Déploiement sur VPS - Twitch Stream Recorder

Ce guide explique comment déployer et utiliser le service de surveillance Twitch en tâche de fond sur un VPS Linux.

## 🚀 Installation sur VPS

### Prérequis

```bash
# Mettre à jour le système
sudo apt update && sudo apt upgrade -y

# Installer Python 3 et pip
sudo apt install python3 python3-pip python3-venv -y

# Installer FFmpeg (requis pour le mode faible consommation)
sudo apt install ffmpeg -y

# Installer Streamlink
pip3 install streamlink

# Vérifier les installations
python3 --version
streamlink --version
ffmpeg -version
```

### Installation du projet

```bash
# Cloner ou uploader le projet sur votre VPS
cd /opt
sudo git clone <url-du-repo> twitch-recorder
cd twitch-recorder

# Créer un environnement virtuel (optionnel mais recommandé)
python3 -m venv venv
source venv/bin/activate

# Installer les dépendances Python
pip install -r requirements.txt

# Créer les dossiers nécessaires
mkdir -p recordings temp_segments

# Configurer les permissions
sudo chown -R $USER:$USER /opt/twitch-recorder
```

## ⚙️ Configuration

### 1. Configuration des streams

Éditer `streams.json` pour ajouter vos streamers :

```json
[
  {
    "id": 1,
    "name": "streamer1",
    "url": "https://www.twitch.tv/streamer1",
    "active": true
  },
  {
    "id": 2,
    "name": "streamer2",
    "url": "https://www.twitch.tv/streamer2",
    "active": true
  }
]
```

### 2. Configuration du daemon

Éditer `config.json` :

```json
{
  "quality": "best",
  "video_format": "mkv",
  "auto_check_live": true,
  "check_interval": 60,
  "low_power_mode": false,
  "auto_process_time": "04:00",
  "smart_processing": true,
  "auto_replicate": false,
  "ftp_enabled": false,
  "smb_enabled": false
}
```

**Options importantes :**
- `auto_check_live`: **true** pour vérifier automatiquement les streams
- `check_interval`: Intervalle en secondes (60 = 1 minute, 300 = 5 minutes)
- `low_power_mode`: Mode faible consommation avec segments
- `quality`: `best`, `1080p60`, `720p`, etc.

## 🔧 Méthodes de démarrage

### Méthode 1 : Démarrage manuel (pour tester)

```bash
cd /opt/twitch-recorder

# Rendre le script exécutable
chmod +x start-daemon.sh

# Démarrer le daemon
./start-daemon.sh
```

Pour arrêter : `Ctrl+C`

### Méthode 2 : Service systemd (recommandé pour VPS)

Cette méthode permet un démarrage automatique au boot et une gestion professionnelle du service.

#### Installation du service

```bash
cd /opt/twitch-recorder

# Éditer le fichier service avec vos chemins
sudo nano twitch-recorder.service

# Modifier ces lignes :
# User=VOTRE_USERNAME
# WorkingDirectory=/opt/twitch-recorder
# ExecStart=/usr/bin/python3 /opt/twitch-recorder/daemon.py

# Copier le fichier service
sudo cp twitch-recorder.service /etc/systemd/system/

# Recharger systemd
sudo systemctl daemon-reload

# Activer le service au démarrage
sudo systemctl enable twitch-recorder

# Démarrer le service
sudo systemctl start twitch-recorder
```

#### Commandes de gestion du service

```bash
# Vérifier le statut
sudo systemctl status twitch-recorder

# Arrêter le service
sudo systemctl stop twitch-recorder

# Redémarrer le service
sudo systemctl restart twitch-recorder

# Désactiver le démarrage automatique
sudo systemctl disable twitch-recorder

# Voir les logs en temps réel
sudo journalctl -u twitch-recorder -f

# Voir les derniers logs
sudo journalctl -u twitch-recorder -n 100
```

### Méthode 3 : Screen (alternative simple)

```bash
# Installer screen
sudo apt install screen -y

# Créer une session screen
screen -S twitch-recorder

# Dans la session screen, démarrer le daemon
cd /opt/twitch-recorder
./start-daemon.sh

# Détacher la session : Ctrl+A puis D
# Rattacher la session : screen -r twitch-recorder
```

## 📊 Monitoring et Logs

### Visualiser les logs du daemon

```bash
# Si vous utilisez systemd
sudo journalctl -u twitch-recorder -f

# Ou lire le fichier de log directement
tail -f /opt/twitch-recorder/daemon.log

# Voir les 100 dernières lignes
tail -n 100 /opt/twitch-recorder/daemon.log
```

### Vérifier les enregistrements

```bash
# Lister les enregistrements
ls -lh /opt/twitch-recorder/recordings/

# Voir l'espace disque utilisé
du -sh /opt/twitch-recorder/recordings/
du -sh /opt/twitch-recorder/temp_segments/
```

### Surveillance de l'utilisation des ressources

```bash
# Voir l'utilisation CPU/RAM du daemon
ps aux | grep daemon.py

# Surveillance en temps réel avec htop
sudo apt install htop -y
htop
```

## 🔄 Utilisation avec l'interface web (optionnel)

Le daemon peut fonctionner **en parallèle** avec l'interface web Flask.

### Démarrer l'interface web

```bash
# Dans un terminal séparé ou une autre session screen
cd /opt/twitch-recorder
python3 app.py
```

L'interface web sera accessible sur `http://VOTRE_IP:5000`

### Configuration Nginx en reverse proxy (optionnel)

```bash
# Installer Nginx
sudo apt install nginx -y

# Créer la configuration
sudo nano /etc/nginx/sites-available/twitch-recorder
```

```nginx
server {
    listen 80;
    server_name votre-domaine.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

```bash
# Activer le site
sudo ln -s /etc/nginx/sites-available/twitch-recorder /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## 🛠️ Maintenance

### Mettre à jour le code

```bash
sudo systemctl stop twitch-recorder
cd /opt/twitch-recorder
git pull
sudo systemctl start twitch-recorder
```

### Nettoyer les anciens enregistrements

```bash
# Supprimer les enregistrements de plus de 30 jours
find /opt/twitch-recorder/recordings -name "*.mkv" -mtime +30 -delete
find /opt/twitch-recorder/recordings -name "*.mp4" -mtime +30 -delete
```

### Rotation automatique des logs

Créer `/etc/logrotate.d/twitch-recorder` :

```bash
sudo nano /etc/logrotate.d/twitch-recorder
```

```
/opt/twitch-recorder/daemon.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
}
```

## 🚨 Dépannage

### Le service ne démarre pas

```bash
# Vérifier les logs
sudo journalctl -u twitch-recorder -n 50

# Vérifier les permissions
ls -l /opt/twitch-recorder/daemon.py
chmod +x /opt/twitch-recorder/daemon.py

# Tester manuellement
cd /opt/twitch-recorder
python3 daemon.py
```

### Streamlink ne fonctionne pas

```bash
# Réinstaller streamlink
pip3 install --upgrade streamlink

# Vérifier la version
streamlink --version

# Tester manuellement un stream
streamlink https://www.twitch.tv/STREAMER best --output test.mp4
```

### Manque d'espace disque

```bash
# Vérifier l'espace disponible
df -h

# Trouver les gros fichiers
du -sh /opt/twitch-recorder/* | sort -h

# Nettoyer les segments temporaires
rm -rf /opt/twitch-recorder/temp_segments/*
```

### Le daemon ne détecte pas les streams

1. Vérifier que `auto_check_live` est à `true` dans `config.json`
2. Vérifier que les URLs dans `streams.json` sont correctes
3. Vérifier la connectivité Internet du VPS
4. Consulter les logs pour voir les erreurs

## 📈 Recommandations de sécurité

```bash
# Configurer un firewall
sudo ufw allow 22/tcp  # SSH
sudo ufw allow 80/tcp  # HTTP (si interface web)
sudo ufw enable

# Créer un utilisateur dédié (recommandé)
sudo useradd -r -s /bin/bash twitch
sudo usermod -aG video twitch
sudo chown -R twitch:twitch /opt/twitch-recorder
# Puis modifier User=twitch dans le fichier service
```

## 💡 Astuces

- **Performance** : Utilisez le format `mkv` pour de meilleures performances
- **Stockage** : Activez `low_power_mode` si vous enregistrez beaucoup de streams simultanément
- **Sauvegardes** : Configurez la réplication FTP/SMB pour sauvegarder automatiquement
- **Notifications** : Intégrez des webhooks Discord/Slack dans le code pour être notifié des enregistrements

## 📞 Support

Pour toute question ou problème, consultez les logs :
```bash
tail -f /opt/twitch-recorder/daemon.log
sudo journalctl -u twitch-recorder -f
```
