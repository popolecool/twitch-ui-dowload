from flask import Flask, render_template, request, jsonify, send_file
import os
import json
import streamlink
import threading
import subprocess
import time
from datetime import datetime, timedelta
import ftplib
import smbclient
from pathlib import Path
import requests
import schedule
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)
app.secret_key = 'twitch_downloader_secret_key'

# Configuration
CONFIG_FILE = 'config.json'
STREAMS_FILE = 'streams.json'
RECORDINGS_DIR = 'recordings'
TEMP_SEGMENTS_DIR = 'temp_segments'

# Créer les dossiers nécessaires
os.makedirs(RECORDINGS_DIR, exist_ok=True)
os.makedirs(TEMP_SEGMENTS_DIR, exist_ok=True)

# Variables globales pour les enregistrements actifs
active_recordings = {}
recording_threads = {}
live_check_thread = None
processing_queue = []
low_power_segments = {}
executor = ThreadPoolExecutor(max_workers=4)

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
            # Fusionner avec la config par défaut
            default_config.update(config)
            return default_config
    except FileNotFoundError:
        return default_config

def save_config(config):
    """Sauvegarder la configuration dans le fichier JSON"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def load_streams():
    """Charger la liste des streams depuis le fichier JSON"""
    try:
        with open(STREAMS_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_streams(streams):
    """Sauvegarder la liste des streams dans le fichier JSON"""
    with open(STREAMS_FILE, 'w') as f:
        json.dump(streams, f, indent=2)

def get_recordings():
    """Obtenir la liste des enregistrements"""
    recordings = []
    if os.path.exists(RECORDINGS_DIR):
        for file in os.listdir(RECORDINGS_DIR):
            if file.endswith(('.mp4', '.mkv', '.flv')):
                file_path = os.path.join(RECORDINGS_DIR, file)
                stat = os.stat(file_path)
                recordings.append({
                    'filename': file,
                    'size': stat.st_size,
                    'date': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                })
    return sorted(recordings, key=lambda x: x['date'], reverse=True)

def check_stream_live(stream_url):
    """Vérifier si un stream est en live"""
    try:
        # Extraire le nom du streamer depuis l'URL
        if 'twitch.tv/' in stream_url:
            streamer_name = stream_url.split('twitch.tv/')[-1].split('?')[0]
            
            # Utiliser l'API Twitch pour vérifier le statut (nécessite une clé API)
            # Pour l'instant, on utilise streamlink pour vérifier
            cmd = ['streamlink', stream_url, '--json']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                return len(data.get('streams', {})) > 0
        return False
    except Exception as e:
        print(f"Erreur lors de la vérification du stream {stream_url}: {e}")
        return False

def auto_check_live_streams():
    """Vérifier automatiquement le statut des streams et démarrer l'enregistrement"""
    config = load_config()
    if not config['auto_check_live']:
        return
        
    streams = load_streams()
    for stream in streams:
        stream_name = stream['name']
        stream_url = stream['url']
        
        # Ne pas vérifier si déjà en cours d'enregistrement
        if stream_name in active_recordings:
            continue
            
        # Vérifier si le stream est live
        if check_stream_live(stream_url):
            print(f"Stream {stream_name} détecté en live, démarrage de l'enregistrement...")
            thread = threading.Thread(target=record_stream, args=(stream_url, stream_name, config['quality'], config['video_format'], config['low_power_mode']))
            thread.daemon = True
            thread.start()
            recording_threads[stream_name] = thread

def start_live_checker():
    """Démarrer le vérificateur automatique de streams live"""
    global live_check_thread
    config = load_config()
    
    if config['auto_check_live'] and live_check_thread is None:
        def check_loop():
            while True:
                try:
                    auto_check_live_streams()
                    time.sleep(config['check_interval'])
                except Exception as e:
                    print(f"Erreur dans le vérificateur de streams: {e}")
                    time.sleep(60)
        
        live_check_thread = threading.Thread(target=check_loop)
        live_check_thread.daemon = True
        live_check_thread.start()
        print("Vérificateur automatique de streams démarré")

def record_stream(stream_url, stream_name, quality, video_format='mp4', low_power_mode=False):
    """Enregistrer un stream Twitch"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    if low_power_mode:
        # Mode faible consommation : enregistrer en segments
        segments_dir = os.path.join(TEMP_SEGMENTS_DIR, f"{stream_name}_{timestamp}")
        os.makedirs(segments_dir, exist_ok=True)
        
        filename_pattern = f"{stream_name}_{timestamp}_segment_%03d.{video_format}"
        output_path = os.path.join(segments_dir, filename_pattern)
        
        # Commande streamlink pour enregistrer en segments
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
        
        # Stocker les informations pour le traitement ultérieur
        low_power_segments[stream_name] = {
            'segments_dir': segments_dir,
            'final_filename': f"{stream_name}_{timestamp}.{video_format}",
            'start_time': datetime.now().isoformat(),
            'video_format': video_format
        }
    else:
        # Mode normal : enregistrement direct
        filename = f"{stream_name}_{timestamp}.{video_format}"
        output_path = os.path.join(RECORDINGS_DIR, filename)
        
        # Commande streamlink pour enregistrer
        cmd = [
            'streamlink',
            stream_url,
            quality,
            '--output', output_path,
            '--retry-streams', '5',
            '--retry-max', '10'
        ]
    
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        active_recordings[stream_name] = {
            'process': process,
            'filename': filename if not low_power_mode else f"{stream_name}_{timestamp}.{video_format}",
            'start_time': datetime.now().isoformat(),
            'low_power_mode': low_power_mode
        }
        
        # Attendre la fin du processus
        process.wait()
        
        # Traitement post-enregistrement
        if low_power_mode:
            # Ajouter à la queue de traitement
            processing_queue.append({
                'stream_name': stream_name,
                'segments_info': low_power_segments[stream_name],
                'timestamp': timestamp
            })
            print(f"Segments de {stream_name} ajoutés à la queue de traitement")
            
            # Traitement intelligent si aucun stream actif
            config = load_config()
            if config['smart_processing'] and len(active_recordings) == 1:  # Seul ce stream était actif
                process_segments_queue()
        else:
            # Mode normal : répliquer directement si activé
            config = load_config()
            if config['auto_replicate'] and os.path.exists(output_path):
                replicate_file(output_path, config)
        
        # Supprimer de la liste des enregistrements actifs
        if stream_name in active_recordings:
            del active_recordings[stream_name]
        
        # Nettoyer les segments si mode faible consommation
        if low_power_mode and stream_name in low_power_segments:
            del low_power_segments[stream_name]
            
    except Exception as e:
        print(f"Erreur lors de l'enregistrement de {stream_name}: {e}")
        if stream_name in active_recordings:
            del active_recordings[stream_name]
        if low_power_mode and stream_name in low_power_segments:
            del low_power_segments[stream_name]

def process_segments_queue():
    """Traiter la queue des segments en attente"""
    if not processing_queue:
        return
        
    print(f"Traitement de {len(processing_queue)} éléments dans la queue...")
    
    for item in processing_queue.copy():
        try:
            segments_info = item['segments_info']
            segments_dir = segments_info['segments_dir']
            final_filename = segments_info['final_filename']
            video_format = segments_info['video_format']
            
            # Fusionner les segments avec ffmpeg
            final_path = os.path.join(RECORDINGS_DIR, final_filename)
            
            # Créer la liste des segments
            segment_files = sorted([f for f in os.listdir(segments_dir) if f.endswith(f'.{video_format}')])
            
            if segment_files:
                # Créer un fichier de liste pour ffmpeg
                list_file = os.path.join(segments_dir, 'segments_list.txt')
                with open(list_file, 'w') as f:
                    for segment in segment_files:
                        f.write(f"file '{os.path.join(segments_dir, segment)}'\n")
                
                # Commande ffmpeg pour fusionner
                cmd = [
                    'ffmpeg',
                    '-f', 'concat',
                    '-safe', '0',
                    '-i', list_file,
                    '-c', 'copy',
                    final_path,
                    '-y'  # Overwrite output file
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    print(f"Segments fusionnés avec succès : {final_filename}")
                    
                    # Supprimer les segments temporaires
                    import shutil
                    shutil.rmtree(segments_dir)
                    
                    # Répliquer si activé
                    config = load_config()
                    if config['auto_replicate']:
                        replicate_file(final_path, config)
                else:
                    print(f"Erreur lors de la fusion des segments : {result.stderr}")
            
            # Retirer de la queue
            processing_queue.remove(item)
            
        except Exception as e:
            print(f"Erreur lors du traitement des segments : {e}")
            processing_queue.remove(item)

def schedule_processing():
    """Programmer le traitement automatique des segments"""
    config = load_config()
    if config.get('auto_process_time'):
        schedule.every().day.at(config['auto_process_time']).do(process_segments_queue)
        
        def run_scheduler():
            while True:
                schedule.run_pending()
                time.sleep(60)
        
        scheduler_thread = threading.Thread(target=run_scheduler)
        scheduler_thread.daemon = True
        scheduler_thread.start()
        print(f"Traitement automatique programmé à {config['auto_process_time']}")

def replicate_file(file_path, config):
    """Répliquer un fichier vers FTP ou SMB"""
    filename = os.path.basename(file_path)
    
    # Réplication FTP
    if config['ftp_enabled']:
        try:
            ftp = ftplib.FTP(config['ftp_host'])
            ftp.login(config['ftp_user'], config['ftp_password'])
            ftp.cwd(config['ftp_path'])
            
            with open(file_path, 'rb') as f:
                ftp.storbinary(f'STOR {filename}', f)
            
            ftp.quit()
            print(f"Fichier {filename} répliqué vers FTP")
        except Exception as e:
            print(f"Erreur FTP: {e}")
    
    # Réplication SMB
    if config['smb_enabled']:
        try:
            # Note: smbclient nécessite une configuration spécifique
            # Cette partie peut nécessiter des ajustements selon l'environnement
            print(f"Réplication SMB de {filename} (à implémenter selon l'environnement)")
        except Exception as e:
            print(f"Erreur SMB: {e}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/streams')
def streams_page():
    streams = load_streams()
    return render_template('streams.html', streams=streams, active_recordings=active_recordings)

@app.route('/recordings')
def recordings_page():
    recordings = get_recordings()
    return render_template('recordings.html', recordings=recordings)

@app.route('/settings')
def settings_page():
    config = load_config()
    return render_template('settings.html', config=config)

@app.route('/processing')
def processing_page():
    return render_template('processing.html')

@app.route('/api/streams', methods=['GET', 'POST', 'DELETE'])
def api_streams():
    if request.method == 'GET':
        return jsonify(load_streams())
    
    elif request.method == 'POST':
        data = request.json
        streams = load_streams()
        
        new_stream = {
            'id': len(streams) + 1,
            'name': data['name'],
            'url': data['url'],
            'active': False
        }
        
        streams.append(new_stream)
        save_streams(streams)
        return jsonify(new_stream)
    
    elif request.method == 'DELETE':
        stream_id = request.json['id']
        streams = load_streams()
        streams = [s for s in streams if s['id'] != stream_id]
        save_streams(streams)
        return jsonify({'success': True})

@app.route('/api/start_recording', methods=['POST'])
def start_recording():
    data = request.json
    stream_name = data['name']
    stream_url = data['url']
    
    if stream_name in active_recordings:
        return jsonify({'error': 'Enregistrement déjà en cours'}), 400
    
    config = load_config()
    quality = config['quality']
    video_format = config['video_format']
    low_power_mode = config['low_power_mode']
    
    # Démarrer l'enregistrement dans un thread séparé
    thread = threading.Thread(target=record_stream, args=(stream_url, stream_name, quality, video_format, low_power_mode))
    thread.daemon = True
    thread.start()
    
    recording_threads[stream_name] = thread
    
    return jsonify({'success': True, 'message': f'Enregistrement de {stream_name} démarré'})

@app.route('/api/stop_recording', methods=['POST'])
def stop_recording():
    data = request.json
    stream_name = data['name']
    
    if stream_name in active_recordings:
        process = active_recordings[stream_name]['process']
        process.terminate()
        del active_recordings[stream_name]
        
        if stream_name in recording_threads:
            del recording_threads[stream_name]
        
        return jsonify({'success': True, 'message': f'Enregistrement de {stream_name} arrêté'})
    
    return jsonify({'error': 'Aucun enregistrement actif trouvé'}), 400

@app.route('/api/settings', methods=['POST'])
def save_settings():
    config = request.json
    save_config(config)
    return jsonify({'success': True})

@app.route('/api/download/<filename>')
def download_recording(filename):
    file_path = os.path.join(RECORDINGS_DIR, filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    return jsonify({'error': 'Fichier non trouvé'}), 404

@app.route('/api/check_live/<stream_name>', methods=['GET'])
def check_live_status(stream_name):
    streams = load_streams()
    stream = next((s for s in streams if s['name'] == stream_name), None)
    
    if not stream:
        return jsonify({'error': 'Stream non trouvé'}), 404
    
    is_live = check_stream_live(stream['url'])
    return jsonify({'stream_name': stream_name, 'is_live': is_live})

@app.route('/api/process_segments', methods=['POST'])
def manual_process_segments():
    try:
        process_segments_queue()
        return jsonify({'success': True, 'message': f'{len(processing_queue)} segments traités'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/processing_queue', methods=['GET'])
def get_processing_queue():
    queue_info = []
    for item in processing_queue:
        queue_info.append({
            'stream_name': item['stream_name'],
            'timestamp': item['timestamp'],
            'segments_count': len(os.listdir(item['segments_info']['segments_dir'])) if os.path.exists(item['segments_info']['segments_dir']) else 0
        })
    
    return jsonify({
        'queue': queue_info,
        'active_segments': list(low_power_segments.keys())
    })

@app.route('/api/system_status', methods=['GET'])
def get_system_status():
    return jsonify({
        'active_recordings': len(active_recordings),
        'processing_queue': len(processing_queue),
        'live_checker_active': live_check_thread is not None and live_check_thread.is_alive(),
        'temp_segments': len(low_power_segments)
    })

if __name__ == '__main__':
    # Démarrer les services automatiques
    start_live_checker()
    schedule_processing()
    
    app.run(debug=False, host='0.0.0.0', port=5000)