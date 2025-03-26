from flask import Flask, request, jsonify, send_file
import os
import logging
import subprocess
from pathlib import Path
from ytmusicapi import YTMusic

app = Flask(__name__)

# Настройка логирования
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Настройка временной директории
TEMP_DIR = 'temp'
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

# Инициализация YTMusic
ytmusic = YTMusic()

@app.route("/")
def index():
    return "Аудиобиблиотека"

@app.route('/api/search', methods=['GET'])
def search_tracks():
    query = request.args.get('query')
    if not query:
        return jsonify({'error': 'Запрос не указан'}), 400

    try:
        # Используем ytmusicapi для поиска
        search_results = ytmusic.search(query, filter='songs', limit=10)
        
        # Форматируем результаты
        tracks = [
            {
                'title': track['title'],
                'artist': track['artists'][0]['name'] if track['artists'] else 'Unknown',
                'videoId': track['videoId'],
                'thumbnail': track['thumbnails'][-1]['url'] if track['thumbnails'] else None
            }
            for track in search_results
        ]
        
        return jsonify(tracks)
    except Exception as e:
        logger.error(f"Error searching tracks: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/get_audio/<track_id>', methods=['GET'])
def get_audio(track_id):
    try:
        logger.debug(f"Processing track ID: {track_id}")

        # Проверяем кэш
        audio_path = os.path.join(TEMP_DIR, f"{track_id}.mp3")
        if os.path.exists(audio_path):
            logger.debug(f"Audio file already exists: {audio_path}")
            return send_file(audio_path, mimetype='audio/mp3')

        # Формируем URL трека YouTube
        track_url = f"https://music.youtube.com/watch?v={track_id}"
        
        # Скачиваем трек через spotdl
        cmd = [
            'spotdl',
            track_url,
            '--output', TEMP_DIR,
            '--format', 'mp3',
            '--bitrate', '320k',
            '--threads', '1'
        ]
        
        logger.debug(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"Download error: {result.stderr}")
            return jsonify({'error': 'Ошибка скачивания'}), 500

        # Ищем скачанный файл
        downloaded_files = list(Path(TEMP_DIR).glob('*.mp3'))
        latest_file = max(downloaded_files, key=os.path.getctime)
        
        # Переименовываем файл для кэширования
        os.rename(latest_file, audio_path)
        
        return send_file(audio_path, mimetype='audio/mp3')

    except Exception as e:
        logger.error(f"Error processing track ID {track_id}: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Проверяем наличие spotdl
    try:
        subprocess.run(['spotdl', '--version'], capture_output=True)
    except FileNotFoundError:
        logger.error("spotdl не установлен. Установите его командой: pip install spotdl")
        exit(1)
        
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port)
