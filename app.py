from flask import Flask, request, jsonify, send_file, render_template, send_from_directory
import os
import logging
import subprocess
from pathlib import Path
from ytmusicapi import YTMusic
import ffmpeg

app = Flask(__name__, static_folder='dist', static_url_path='')

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
    return send_from_directory(app.static_folder, 'index.html')

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
        
        # Получаем список файлов до скачивания
        files_before = set(os.listdir(TEMP_DIR))
        
        # Скачиваем трек через spotdl
        cmd = [
            'spotdl',
            track_url,
            '--output', TEMP_DIR,
            '--format', 'mp3',
            '--bitrate', '128k',
            '--threads', '1'
        ]
        
        logger.debug(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"Download error: {result.stderr}")
            return jsonify({'error': 'Ошибка скачивания'}), 500

        # Получаем список файлов после скачивания
        files_after = set(os.listdir(TEMP_DIR))
        
        # Находим новые файлы
        new_files = files_after - files_before
        logger.debug(f"New files: {new_files}")
        
        if not new_files:
            logger.error("No new files found after download")
            return jsonify({'error': 'Файл не был скачан'}), 500
            
        # Ищем среди новых файлов MP3
        mp3_files = [f for f in new_files if f.endswith('.mp3')]
        
        if not mp3_files:
            logger.error("No MP3 files found among new files")
            return jsonify({'error': 'MP3 файл не найден'}), 500
            
        # Берем первый найденный MP3 файл
        downloaded_file = os.path.join(TEMP_DIR, mp3_files[0])
        
        # Переименовываем файл для кэширования
        os.rename(downloaded_file, audio_path)
        
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
