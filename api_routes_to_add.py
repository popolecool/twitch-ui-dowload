# Routes API à ajouter à app.py
# Insérer après la route /api/streams existante

@app.route('/api/streams/<int:stream_id>', methods=['PUT'])
def update_stream(stream_id):
    """Mettre à jour les paramètres d'un stream"""
    data = request.json
    streams = load_streams()
    
    # Trouver le stream à mettre à jour
    stream = next((s for s in streams if s['id'] == stream_id), None)
    if not stream:
        return jsonify({'error': 'Stream non trouvé'}), 404
    
    # Mettre à jour les champs
    stream['name'] = data.get('name', stream.get('name'))
    stream['url'] = data.get('url', stream.get('url'))
    stream['display_name'] = data.get('display_name', None)
    stream['custom_quality'] = data.get('custom_quality', None)
    stream['custom_bitrate'] = data.get('custom_bitrate', None)
    
    save_streams(streams)
    return jsonify(stream)


# Modifications à app ort dans la route /api/streams POST:
# Remplacer le bloc new_stream par:
        new_id = max([s['id'] for s in streams], default=0) + 1
        
        new_stream = {
            'id': new_id,
            'name': data['name'],
            'url': data['url'],
            'active': False,
            'display_name': data.get('display_name', None),
            'custom_quality': data.get('custom_quality', None),
            'custom_bitrate': data.get('custom_bitrate', None)
        }


# Modifications à apporter dans la route /api/start_recording:
# Ajouter après "low_power_mode = config['low_power_mode']":
    
    # Vérifier si le stream a des paramètres personnalisés
    streams = load_streams()
    stream = next((s for s in streams if s['name'] == stream_name), None)
    
    if stream and stream.get('custom_quality'):
        quality = stream['custom_quality']
