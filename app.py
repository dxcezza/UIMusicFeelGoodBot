from flask import Flask, request, jsonify, send_file
import os
import logging
from spotdl import Spotdl
from spotdl.types.song import Song
from spotdl.utils.search import get_search_results
import asyncio
import nest_asyncio
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Применяем патч для работы с асинхронным кодом
nest_asyncio.apply()

app = Flask(__name__)

# Настройка логирования
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Настройка временной директории
TEMP_DIR = 'temp'
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

# Настройка HTTP-сессии с повторными попытками и увеличенным таймаутом
session = requests.Session()
retry_strategy = Retry(
    total=3,  # количество повторных попыток
    backoff_factor=1,  # фактор задержки между попытками
    status_forcelist=[429, 500, 502, 503, 504]  # коды ошибок для повторных попыток
)
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("https://", adapter)
session.mount("http://", adapter)

# Создаем экземпляр spotdl с учетными данными Spotify
spotdl_client = Spotdl(
    client_id='3ca65da03635428ea7cb29981ee7220a',
    client_secret='e9e3c7a8e864403abfa9b1443d2c0017',
)

# Настраиваем параметры скачивания отдельно
spotdl_client.downloader.output = TEMP_DIR
spotdl_client.downloader.output_format = 'mp3'
spotdl_client.downloader.threads = 1

# ... existing code ...

async def download_track(song):
    """Асинхронная функция для скачивания трека"""
    try:
        return await spotdl_client.download(song)
    except Exception as e:
        logger.error(f"Download error: {e}")
        raise e

@app.route('/api/get_audio/<track_url>', methods=['GET'])
def get_audio(track_url):
    try:
        logger.debug(f"Processing track URL: {track_url}")

        # Формируем полный URL Spotify
        full_track_url = f"https://open.spotify.com/track/{track_url}"
        
        # Проверяем кэш
        audio_path = os.path.join(TEMP_DIR, f"{track_url}.mp3")
        if os.path.exists(audio_path):
            logger.debug(f"Audio file already exists: {audio_path}")
            return send_file(audio_path, mimetype='audio/mp3')

        # Получаем информацию о треке
        song = Song.from_url(full_track_url)
        logger.debug(f"Song info: {song.name} by {song.artists}")

        # Создаем и настраиваем новый event loop
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            # Запускаем скачивание в текущем event loop
            download_info = loop.run_until_complete(download_track(song))
        finally:
            loop.close()
            asyncio.set_event_loop(None)

        logger.debug(f"Download info: {download_info}")

        if not download_info:
            return jsonify({'error': 'Не удалось скачать аудио'}), 500

        # Получаем путь к скачанному файлу
        downloaded_file = download_info[0]
        if not os.path.exists(downloaded_file):
            return jsonify({'error': 'Файл не найден после скачивания'}), 500

        # Переименовываем файл для кэширования
        os.rename(downloaded_file, audio_path)

        return send_file(audio_path, mimetype='audio/mp3')

    except Exception as e:
        logger.error(f"Error processing track URL {track_url}: {e}")
        return jsonify({'error': str(e)}), 500

# ... rest of the code ...

@app.route('/api/search', methods=['GET'])
def search_tracks():
    query = request.args.get('query')
    if not query:
        return jsonify({'error': 'Запрос не указан'}), 400

    try:
        # Ищем треки по запросу
        search_results = spotdl_client.search([query])
        tracks = [
            {
                'title': song.name,
                'artist': song.artists[0],
                'videoId': song.url.split('/')[-1],
                'thumbnail': song.cover_url
            }
            for song in search_results
        ]
        return jsonify(tracks)
    except Exception as e:
        logger.error(f"Error searching tracks: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(port=3000)
