from flask import Flask, request, jsonify, send_file, send_from_directory, Response
import os
import logging
import io
import subprocess
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from model import Track, Base
from dotenv import load_dotenv
from ytmusicapi import YTMusic
import asyncio

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

# Генерация таблицы
Base.metadata.create_all(engine)

# Подключение к базе данных
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.route("/")
def index():
    return send_file(os.path.join(app.static_folder, 'index.html'))

@app.route('/api/search', methods=['GET'])
def search_tracks():
    query = request.args.get('query')
    if not query:
        return jsonify({'error': 'Запрос не указан'}), 400

    try:
        # Используем ytmusicapi для поиска
        ytmusic = YTMusic()
        search_results = ytmusic.search(query, filter='songs', limit=10)

        tracks = [
            {
                'videoId': track['videoId'],
                'title': track['title'],
                'artist': track['artists'][0]['name'] if track['artists'] else 'Unknown',
                'thumbnail': track['thumbnails'][-1]['url'] if track['thumbnails'] else "https://example.com/default_thumbnail.jpg"
            }
            for track in search_results
        ]

        # Проверяем базу данных на наличие треков
        db = next(get_db())
        existing_tracks = db.query(Track).filter(Track.title.ilike(f"%{query}%")).all()

        if existing_tracks:
            tracks.extend([
                {
                    'videoId': track.videoId,
                    'title': track.title,
                    'artist': track.artist,
                    'thumbnail': track.thumbnail or "https://example.com/default_thumbnail.jpg"
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
            logger.debug("Audio data already exists in database")
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
            song = await Song.from_url(track_url)
            if not song:
                raise ValueError("Track not found on Spotify")

            result = await Spotdl().download(song)
            if not result:
                raise ValueError("Failed to download track")

            # Читаем скачанный файл как байты
            with open(result, 'rb') as audio_file:
                audio_data = audio_file.read()

            # Получаем метаданные о треке
            title = song.name or 'Unknown'
            artist = song.artists[0] if song.artists else 'Unknown'
            thumbnail = song.cover_url or "https://example.com/default_thumbnail.jpg"  # Стандартная обложка

            return {
                'title': title,
                'artist': artist,
                'thumbnail': thumbnail,
                'audio_data': audio_data
            }

        song_info = asyncio.run(download_song())

        # Если трек еще не существует в базе, создаем новую запись
        if not track:
            track = Track(
                videoId=track_id,
                title=song_info['title'],
                artist=song_info['artist'],
                thumbnail=song_info['thumbnail'],  # Используем стандартную обложку, если она отсутствует
                audioData=song_info['audio_data'],
                is_downloaded=True
            )
            db.add(track)
        else:
            # Обновляем существующую запись
            track.title = song_info['title']
            track.artist = song_info['artist']
            track.thumbnail = song_info['thumbnail']  # Используем стандартную обложку, если она отсутствует
            track.audioData = song_info['audio_data']
            track.is_downloaded = True

        db.commit()

        # Отправляем файл клиенту
        return send_file(
            io.BytesIO(song_info['audio_data']),
            mimetype='audio/mp3',
            as_attachment=True,
            download_name=f"{song_info['title']}.mp3"
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
