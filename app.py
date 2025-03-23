from flask import Flask, request, jsonify, send_file, render_template, send_from_directory
from ytmusicapi import YTMusic
import os
import yt_dlp
import ffmpeg
import logging

app = Flask(__name__, static_folder='dist', static_url_path='')

# Настройка логирования
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Инициализация ytmusicapi
ytmusic = YTMusic()

# Настройка временной директории
TEMP_DIR = 'temp'
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

# Путь к файлу cookies (замените на путь к вашему файлу cookies.txt)
COOKIES_FILE = 'cookies.txt'

@app.route("/")
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/api/search', methods=['GET'])
def search_tracks():
    query = request.args.get('query')
    if not query:
        return jsonify({'error': 'Запрос не указан'}), 400

    try:
        results = ytmusic.search(query, filter='songs', limit=10)
        tracks = [
            {
                'title': item['title'],
                'artist': item['artists'][0]['name'] if item['artists'] else 'Unknown',
                'videoId': item['videoId'],
                'thumbnail': item['thumbnails'][-1]['url']  # Берем последнюю (самую большую) миниатюру
            }
            for item in results
        ]
        return jsonify(tracks)
    except Exception as e:
        logger.error(f"Error searching tracks: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/get_audio/<video_id>', methods=['GET'])
def get_audio(video_id):
    try:
        logger.debug(f"Processing video ID: {video_id}")

        # Проверяем, существует ли аудиофайл в кэше
        audio_path = os.path.join(TEMP_DIR, f"{video_id}.mp3")
        if os.path.exists(audio_path):
            logger.debug(f"Audio file already exists: {audio_path}")
            return send_file(audio_path, mimetype='audio/mp3')

        # URL видео
        video_url = f"https://youtube.com/watch?v={video_id}"

        # Настройки yt-dlp для скачивания только аудио
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(TEMP_DIR, f'{video_id}.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'cookiefile': COOKIES_FILE,  # Передача файла cookies
            'retries': 3,  # Количество повторных попыток
            'fragment_retries': 10,  # Количество попыток при скачивании частей файла
            'continue_dl': True,  # Возобновление скачивания при разрыве
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.debug(f"Downloading audio from: {video_url}")
            ydl.download([video_url])

        # Проверяем, что файл успешно создан
        if not os.path.exists(audio_path):
            return jsonify({'error': 'Не удалось скачать аудио'}), 500

        # Отправляем аудио файл
        return send_file(audio_path, mimetype='audio/mp3')

    except Exception as e:
        logger.error(f"Error processing video ID {video_id}: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port)