from flask import Flask, request, jsonify, send_file, send_from_directory
import os
import logging
import io
import yt_dlp
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from model import Track, Base
from dotenv import load_dotenv
from ytmusicapi import YTMusic

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

        # Если трека нет или он не скачан, скачиваем его
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '128',
            }],
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Получаем информацию о треке
            info = ydl.extract_info(f"https://music.youtube.com/watch?v={track_id}", download=False)
            
            # Скачиваем аудио во временный файл
            with ydl.download([f"https://music.youtube.com/watch?v={track_id}"]) as download_path:
                # Читаем скачанный файл
                with open(download_path, 'rb') as audio_file:
                    audio_data = audio_file.read()

                # Если трек еще не существует в базе, создаем новую запись
                if not track:
                    track = Track(
                        videoId=track_id,
                        title=info.get('title', 'Unknown'),
                        artist=info.get('artist', 'Unknown'),
                        thumbnail=info.get('thumbnail', ''),
                        audioData=audio_data,
                        is_downloaded=True
                    )
                    db.add(track)
                else:
                    # Обновляем существующую запись
                    track.audioData = audio_data
                    track.is_downloaded = True

                db.commit()

                # Отправляем файл клиенту
                return send_file(
                    io.BytesIO(audio_data),
                    mimetype='audio/mp3',
                    as_attachment=True,
                    download_name=f"{track.title}.mp3"
                )

    except Exception as e:
        logger.error(f"Ошибка обработки track ID {track_id}: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port)


    
