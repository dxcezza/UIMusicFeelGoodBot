from flask import Flask, request, jsonify, send_file
import os
import logging
import asyncio
from spotdl import Spotdl
from spotdl.types.song import Song
from spotdl.utils.search import get_search_results
# Применяем патч для работы с асинхронным кодом

app = Flask(__name__, static_folder='dist', static_url_path='')

# Настройка логирования
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Настройка временной директории
TEMP_DIR = 'temp'
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

# Создаем экземпляр spotdl
spotdl_client = Spotdl(
    client_id='3ca65da03635428ea7cb29981ee7220a',
    client_secret='e9e3c7a8e864403abfa9b1443d2c0017'
)

@app.route("/")
def index():
    return send_from_directory(app.static_folder, 'index.html')
    
@app.route('/api/search', methods=['GET'])
def search_tracks():
    query = request.args.get('query')
    if not query:
        return jsonify({'error': 'Запрос не указан'}), 400

    try:
        # Ищем треки через spotdl
        search_results = asyncio.run(get_search_results(query))
        tracks = [
            {
                'title': song.name,
                'artist': song.artists[0],  # Берем первого исполнителя
                'videoId': song.url.split('/')[-1].split('?')[0],  # ID трека на Spotify
                'thumbnail': song.cover_url  # URL обложки
            }
            for song in search_results
        ]
        return jsonify(tracks)
    except Exception as e:
        logger.error(f"Error searching tracks: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/get_audio/<track_id>', methods=['GET'])
def get_audio(track_id):
    try:
        logger.debug(f"Processing track URL: {track_id}")

        # Проверяем кэш
        audio_path = os.path.join(TEMP_DIR, f"{track_id}.mp3")
        if os.path.exists(audio_path):
            logger.debug(f"Audio file already exists: {audio_path}")
            return send_file(audio_path, mimetype='audio/mp3')

        # Скачиваем трек через spotdl
        async def download_song():
            song = await Song.from_url(f"https://open.spotify.com/track/{track_id}")
            result = await spotdl_client.download(song)
            return result

        # Запускаем асинхронную функцию в синхронном контексте
        result = asyncio.run(download_song())

        if result is None or not os.path.exists(result):
            return jsonify({'error': 'Не удалось скачать аудио'}), 500

        # Копируем файл в временную директорию
        output_file = os.path.join(TEMP_DIR, f"{track_id}.mp3")
        os.rename(result, output_file)

        return send_file(output_file, mimetype='audio/mp3')

    except Exception as e:
        logger.error(f"Error processing track URL {track_id}: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port)
