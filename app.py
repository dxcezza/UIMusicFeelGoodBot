from flask import Flask, request, jsonify, send_file, send_from_directory
import os
import logging
import io
import subprocess
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from model import Track, Base
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

app = Flask(__name__, static_folder='dist', static_url_path='')

# Настройка логирования
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Настройка базы данных
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError("DATABASE_URL не установлен в переменных окружения")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

# Инициализация YTMusic
ytmusic = YTMusic()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

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
        
        # Проверяем базу данных на наличие треков
        db = next(get_db())
        existing_tracks = db.query(Track).filter(Track.title.ilike(f"%{query}%")).all()

        if existing_tracks:
            tracks.extend([
                {
                    'title': track.title,
                    'artist': track.artist,
                    'videoId': track.videoId,
                    'thumbnail': track.thumbnail
                }
                for track in existing_tracks
            ])

        return jsonify(tracks)

    except Exception as e:
        logger.error(f"Ошибка поиска треков: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/get_audio/<track_id>', methods=['GET'])
def get_audio(track_id):
    try:
        db = next(get_db())

        # Проверяем, есть ли трек в базе данных
        track = db.query(Track).filter(Track.videoId == track_id).first()

        if track and track.is_downloaded and track.audioData:
            # Если трек уже есть в базе, отправляем его
            return send_file(
                io.BytesIO(track.audioData),
                mimetype='audio/mp3',
                as_attachment=True,
                download_name=f"{track.title}.mp3"
            )

        # Если трека нет или он не скачан, скачиваем его через spotdl
        async def download_song():
            # Формируем URL трека Spotify
            track_url = f"https://open.spotify.com/track/{track_id}"
            
            # Скачиваем трек через spotdl
            cmd = [
                'spotdl',
                '--song', track_url,
                '--output', '-',  # Выводим данные в stdout
                '--format', 'mp3',
                '--bitrate', '128k'
            ]

            logger.debug(f"Running command: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                raise ValueError(f"Failed to download track: {result.stderr}")

            return result.stdout.encode()  # Преобразуем stdout в байты

        audio_data = asyncio.run(download_song())

        # Получаем информацию о треке через ytmusicapi (для метаданных)
        track_info = ytmusic.get_song(track_id)
        if not track_info:
            return jsonify({'error': 'Трек не найден'}), 404

        title = track_info.get('title', 'Unknown')
        artist = track_info.get('artists', [{}])[0].get('name', 'Unknown')
        thumbnail = track_info.get('thumbnails', [{}])[-1].get('url', None)

        # Если трек еще не существует в базе, создаем новую запись
        if not track:
            track = Track(
                videoId=track_id,
                title=title,
                artist=artist,
                thumbnail=thumbnail,
                audioData=audio_data,
                is_downloaded=True
            )
            db.add(track)
        else:
            # Обновляем существующую запись
            track.title = title
            track.artist = artist
            track.thumbnail = thumbnail
            track.audioData = audio_data
            track.is_downloaded = True

        db.commit()

        # Отправляем файл клиенту
        return send_file(
            io.BytesIO(audio_data),
            mimetype='audio/mp3',
            as_attachment=True,
            download_name=f"{title}.mp3"
        )

    except ValueError as ve:
        logger.error(f"ValueError processing track ID {track_id}: {ve}")
        return jsonify({'error': str(ve)}), 404
    except Exception as e:
        logger.error(f"Error processing track ID {track_id}: {e}")
        return jsonify({'error': 'Не удалось скачать аудио'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port)
