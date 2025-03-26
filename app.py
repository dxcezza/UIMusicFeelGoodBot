from flask import Flask, request, jsonify, send_file
import os
import logging
import subprocess
from pathlib import Path
from ytmusicapi import YTMusic

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
        
        # Используем yt-dlp напрямую вместо spotdl
        output_template = os.path.join(TEMP_DIR, f"{track_id}.%(ext)s")
        cmd = [
            'yt-dlp',
            '-x',  # извлечь аудио
            '--audio-format', 'mp3',
            '--audio-quality', '0',  # лучшее качество
            '-o', output_template,
            track_url
        ]
        
        logger.debug(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"Download error: {result.stderr}")
            return jsonify({'error': 'Ошибка скачивания'}), 500
        
        logger.debug(f"Download output: {result.stdout}")

        # Проверяем, что файл существует
        if not os.path.exists(audio_path):
            logger.error(f"Expected file not found: {audio_path}")
            return jsonify({'error': 'Файл не был скачан'}), 500
        
        return send_file(audio_path, mimetype='audio/mp3')

    except Exception as e:
        logger.error(f"Error processing track ID {track_id}: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Проверяем наличие yt-dlp
    try:
        subprocess.run(['yt-dlp', '--version'], capture_output=True)
    except FileNotFoundError:
        logger.error("yt-dlp не установлен. Установите его командой: pip install yt-dlp")
        exit(1)
    
    # Проверяем наличие ffmpeg
    try:
        logger.info("Проверка наличия ffmpeg...")
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        if result.returncode != 0:
            logger.error("ffmpeg не найден. Пожалуйста, установите ffmpeg")
            exit(1)
        logger.info("ffmpeg найден")
    except Exception as e:
        logger.error(f"Ошибка при проверке ffmpeg: {e}")
        logger.error("Пожалуйста, установите ffmpeg вручную")
        exit(1)
        
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port)
