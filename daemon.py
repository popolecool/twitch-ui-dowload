#!/usr/bin/env python3
"""
Twitch Stream Recorder Daemon
Service autonome pour surveiller et enregistrer automatiquement les streams Twitch
Peut fonctionner en tâche de fond sur un VPS sans interface web
"""

import os
import json
import subprocess
import threading
import time
import signal
import sys
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler
import schedule
from pathlib import Path

# Configuration
CONFIG_FILE = 'config.json'
STREAMS_FILE = 'streams.json'
RECORDINGS_DIR = 'recordings'
TEMP_SEGMENTS_DIR = 'temp_segments'
LOG_FILE = 'daemon.log'

# Variables globales
active_recordings = {}
recording_threads = {}
processing_queue = []
low_power_segments = {}
shutdown_flag = threading.Event()

# Configuration du logging
def setup_logging():
    """Configurer le système de logging"""
    logger = logging.getLogger('TwitchRecorder')
    logger.setLevel(logging.INFO)
    
    # Handler pour fichier avec rotation
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.INFO)
    
    # Handler pour console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # Format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logging()

def load_config():
    """Charger la configuration depuis le fichier JSON"""
    default_config = {
        'quality': 'best',
        'video_format': 'mp4',
        'auto_replicate': False,
        'auto_check_live': True,
        'check_interval': 60,
        'low_power_mode': False,
        'auto_process_time': '03:00',
        'smart_processing': True,
        'ftp_enabled': False,
        'ftp_host': '',
        'ftp_user': '',
        'ftp_password': '',
        'ftp_path': '/',
        'smb_enabled': False,
        'smb_host': '',
        'smb_share': '',
        'smb_user': '',
        'smb_password': '',
        'smb_path': '/'
    }
    
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            default_config.update(config)
            return default_config
    except FileNotFoundError:
        logger.warning(f"Fichier de configuration {CONFIG_FILE} non trouvé, utilisation des valeurs par défaut")
        return default_config
    except json.JSONDecodeError as e:
        logger.error(f"Erreur de lecture du fichier de configuration: {e}")
        return default_config

def load_streams():
    """Charger la liste des streams depuis le fichier JSON"""
    try:
        with open(STREAMS_FILE, 'r') as f:
            streams = json.load(f)
            logger.info(f"Chargé {len(streams)} streams depuis {STREAMS_FILE}")
            return streams
    except FileNotFoundError:
        logger.warning(f"Fichier {STREAMS_FILE} non trouvé, liste de streams vide")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Erreur de lecture du fichier des streams: {e}")
        return []

def check_stream_live(stream_url):
    """Vérifier si un stream est en live"""
    try:
        cmd = ['streamlink', stream_url, '--json']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return len(data.get('streams', {})) > 0
        return False
    except subprocess.TimeoutExpired:
        logger.warning(f"Timeout lors de la vérification du stream {stream_url}")
        return False
    except json.JSONDecodeError:
        logger.error(f"Erreur de décodage JSON pour {stream_url}")
        return False
    except Exception as e:
        logger.error(f"Erreur lors de la vérification du stream {stream_url}: {e}")
        return False

def record_stream(stream_url, stream_name, quality, video_format='mp4', low_power_mode=False):
    """Enregistrer un stream Twitch"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    if low_power_mode:
        # Mode faible consommation : enregistrer en segments
        segments_dir = os.path.join(TEMP_SEGMENTS_DIR, f"{stream_name}_{timestamp}")
        os.makedirs(segments_dir, exist_ok=True)
        
        filename_pattern = f"{stream_name}_{timestamp}_segment_%03d.{video_format}"
        output_path = os.path.join(segments_dir, filename_pattern)
        
        cmd = [
            'streamlink',
            stream_url,
            quality,
            '--output', output_path,
            '--retry-streams', '5',
            '--retry-max', '10',
            '--hls-segment-timeout', '60',
            '--hls-segment-attempts', '3'
        ]
        
        low_power_segments[stream_name] = {
            'segments_dir': segments_dir,
            'final_filename': f"{stream_name}_{timestamp}.{video_format}",
            'start_time': datetime.now().isoformat(),
            'video_format': video_format
        }
        
        logger.info(f"Enregistrement en mode faible consommation : {stream_name} dans {segments_dir}")
    else:
        # Mode normal : enregistrement direct
        filename = f"{stream_name}_{timestamp}.{video_format}"
        output_path = os.path.join(RECORDINGS_DIR, filename)
        
        cmd = [
            'streamlink',
            stream_url,
            quality,
            '--output', output_path,
            '--retry-streams', '5',
            '--retry-max', '10'
        ]
        
        logger.info(f"Enregistrement en mode normal : {stream_name} dans {output_path}")
    
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        active_recordings[stream_name] = {
            'process': process,
            'filename': filename if not low_power_mode else f"{stream_name}_{timestamp}.{video_format}",
            'start_time': datetime.now().isoformat(),
            'low_power_mode': low_power_mode
        }
        
        logger.info(f"Enregistrement de {stream_name} démarré (PID: {process.pid})")
        
        # Attendre la fin du processus
        process.wait()
        
        # Traitement post-enregistrement
        if low_power_mode:
            processing_queue.append({
                'stream_name': stream_name,
                'segments_info': low_power_segments[stream_name],
                'timestamp': timestamp
            })
            logger.info(f"Segments de {stream_name} ajoutés à la queue de traitement")
            
            config = load_config()
            if config['smart_processing'] and len(active_recordings) == 1:
                logger.info("Traitement intelligent activé, démarrage du traitement des segments")
                process_segments_queue()
        else:
            config = load_config()
            if config['auto_replicate'] and os.path.exists(output_path):
                replicate_file(output_path, config)
        
        if stream_name in active_recordings:
            del active_recordings[stream_name]
        
        if low_power_mode and stream_name in low_power_segments:
            del low_power_segments[stream_name]
        
        logger.info(f"Enregistrement de {stream_name} terminé")
            
    except Exception as e:
        logger.error(f"Erreur lors de l'enregistrement de {stream_name}: {e}")
        if stream_name in active_recordings:
            del active_recordings[stream_name]
        if low_power_mode and stream_name in low_power_segments:
            del low_power_segments[stream_name]

def process_segments_queue():
    """Traiter la queue des segments en attente"""
    if not processing_queue:
        logger.info("Aucun segment à traiter")
        return
    
    logger.info(f"Traitement de {len(processing_queue)} éléments dans la queue...")
    
    for item in processing_queue.copy():
        try:
            segments_info = item['segments_info']
            segments_dir = segments_info['segments_dir']
            final_filename = segments_info['final_filename']
            video_format = segments_info['video_format']
            
            final_path = os.path.join(RECORDINGS_DIR, final_filename)
            
            segment_files = sorted([f for f in os.listdir(segments_dir) if f.endswith(f'.{video_format}')])
            
            if segment_files:
                list_file = os.path.join(segments_dir, 'segments_list.txt')
                with open(list_file, 'w') as f:
                    for segment in segment_files:
                        f.write(f"file '{os.path.join(segments_dir, segment)}'\n")
                
                cmd = [
                    'ffmpeg',
                    '-f', 'concat',
                    '-safe', '0',
                    '-i', list_file,
                    '-c', 'copy',
                    final_path,
                    '-y'
                ]
                
                logger.info(f"Fusion des segments pour {final_filename}...")
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    logger.info(f"Segments fusionnés avec succès : {final_filename}")
                    
                    import shutil
                    shutil.rmtree(segments_dir)
                    logger.info(f"Segments temporaires supprimés : {segments_dir}")
                    
                    config = load_config()
                    if config['auto_replicate']:
                        replicate_file(final_path, config)
                else:
                    logger.error(f"Erreur lors de la fusion des segments : {result.stderr}")
            
            processing_queue.remove(item)
            
        except Exception as e:
            logger.error(f"Erreur lors du traitement des segments : {e}")
            processing_queue.remove(item)

def replicate_file(file_path, config):
    """Répliquer un fichier vers FTP ou SMB"""
    filename = os.path.basename(file_path)
    
    if config['ftp_enabled']:
        try:
            import ftplib
            ftp = ftplib.FTP(config['ftp_host'])
            ftp.login(config['ftp_user'], config['ftp_password'])
            ftp.cwd(config['ftp_path'])
            
            with open(file_path, 'rb') as f:
                ftp.storbinary(f'STOR {filename}', f)
            
            ftp.quit()
            logger.info(f"Fichier {filename} répliqué vers FTP")
        except Exception as e:
            logger.error(f"Erreur FTP: {e}")
    
    if config['smb_enabled']:
        try:
            logger.info(f"Réplication SMB de {filename} (à implémenter selon l'environnement)")
        except Exception as e:
            logger.error(f"Erreur SMB: {e}")

def auto_check_live_streams():
    """Vérifier automatiquement le statut des streams et démarrer l'enregistrement"""
    config = load_config()
    if not config['auto_check_live']:
        return
    
    streams = load_streams()
    if not streams:
        logger.debug("Aucun stream configuré")
        return
    
    logger.debug(f"Vérification du statut de {len(streams)} streams...")
    
    for stream in streams:
        if shutdown_flag.is_set():
            break
            
        stream_name = stream['name']
        stream_url = stream['url']
        
        if stream_name in active_recordings:
            continue
        
        if check_stream_live(stream_url):
            logger.info(f"🔴 Stream {stream_name} détecté en live, démarrage de l'enregistrement...")
            thread = threading.Thread(
                target=record_stream,
                args=(stream_url, stream_name, config['quality'], config['video_format'], config['low_power_mode'])
            )
            thread.daemon = True
            thread.start()
            recording_threads[stream_name] = thread

def live_check_loop(interval):
    """Boucle de vérification automatique des streams"""
    logger.info(f"Démarrage de la vérification automatique des streams (intervalle: {interval}s)")
    
    while not shutdown_flag.is_set():
        try:
            auto_check_live_streams()
            time.sleep(interval)
        except Exception as e:
            logger.error(f"Erreur dans le vérificateur de streams: {e}")
            time.sleep(60)

def schedule_processing_loop():
    """Boucle pour le traitement programmé des segments"""
    config = load_config()
    if config.get('auto_process_time'):
        schedule.every().day.at(config['auto_process_time']).do(process_segments_queue)
        logger.info(f"Traitement automatique programmé à {config['auto_process_time']}")
    
    while not shutdown_flag.is_set():
        schedule.run_pending()
        time.sleep(60)

def signal_handler(signum, frame):
    """Gérer les signaux d'arrêt"""
    logger.info(f"Signal {signum} reçu, arrêt en cours...")
    shutdown_flag.set()
    
    # Arrêter les enregistrements en cours
    for stream_name, recording_info in list(active_recordings.items()):
        try:
            process = recording_info['process']
            logger.info(f"Arrêt de l'enregistrement : {stream_name}")
            process.terminate()
            process.wait(timeout=10)
        except Exception as e:
            logger.error(f"Erreur lors de l'arrêt de {stream_name}: {e}")
    
    logger.info("Daemon arrêté proprement")
    sys.exit(0)

def main():
    """Point d'entrée principal du daemon"""
    logger.info("=" * 60)
    logger.info("Twitch Stream Recorder Daemon - Démarrage")
    logger.info("=" * 60)
    
    # Créer les dossiers nécessaires
    os.makedirs(RECORDINGS_DIR, exist_ok=True)
    os.makedirs(TEMP_SEGMENTS_DIR, exist_ok=True)
    logger.info(f"Dossiers créés : {RECORDINGS_DIR}, {TEMP_SEGMENTS_DIR}")
    
    # Charger la configuration
    config = load_config()
    logger.info(f"Configuration chargée : qualité={config['quality']}, format={config['video_format']}")
    logger.info(f"Auto-check: {config['auto_check_live']}, Intervalle: {config['check_interval']}s")
    logger.info(f"Mode faible consommation: {config['low_power_mode']}")
    
    # Charger les streams
    streams = load_streams()
    logger.info(f"Streams configurés : {[s['name'] for s in streams]}")
    
    # Configurer les gestionnaires de signaux
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Démarrer le thread de vérification automatique
    if config['auto_check_live']:
        check_thread = threading.Thread(
            target=live_check_loop,
            args=(config['check_interval'],)
        )
        check_thread.daemon = True
        check_thread.start()
        logger.info("Thread de vérification automatique démarré")
    else:
        logger.warning("Vérification automatique désactivée dans la configuration")
    
    # Démarrer le thread de traitement programmé
    if config.get('auto_process_time'):
        schedule_thread = threading.Thread(target=schedule_processing_loop)
        schedule_thread.daemon = True
        schedule_thread.start()
        logger.info("Thread de traitement programmé démarré")
    
    logger.info("Daemon en cours d'exécution. Appuyez sur Ctrl+C pour arrêter.")
    
    # Garder le programme en vie
    try:
        while not shutdown_flag.is_set():
            time.sleep(1)
    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)

if __name__ == '__main__':
    main()
