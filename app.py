from flask import Flask, request, jsonify, send_file, render_template, send_from_directory
import subprocess
import os
import yt_dlp
from ytmusicapi import YTMusic

app = Flask(__name__, static_folder='dist', static_url_path='')

# Инициализация YTMusic API
ytmusic = YTMusic()

# Папка для сохранения скачанных файлов
DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Функция для генерации пути к файлу на основе track_id
def get_file_path(track_id):
    # Ожидаемое имя файла в формате <track_id>.mp3
    return os.path.join(DOWNLOAD_FOLDER, f"{track_id}.mp3")

@app.route('/api/search', methods=['GET'])
def search_tracks():
    query = request.args.get('query', '')
    if not query:
        return jsonify({"error": "Query parameter is required"}), 400

    # Поиск треков через YTMusic API
    search_results = ytmusic.search(query, filter="songs")
    
    # Формируем ответ в нужном формате
    formatted_results = [
        {
            "videoId": result["videoId"],
            "title": result["title"],
            "artist": result["artists"][0]["name"] if result.get("artists") else "Unknown",
            "thumbnail": result["thumbnails"][0]["url"] if result.get("thumbnails") else None
        }
        for result in search_results
    ]

    return jsonify(formatted_results)

@app.route('/api/get_audio/<track_id>', methods=['GET'])
def download_track(track_id):
    try:
        # URL трека на YouTube Music
        youtube_url = f"https://music.youtube.com/watch?v={track_id}"
        
        # Генерируем путь к файлу
        expected_file_path = get_file_path(track_id)
        
        # Проверяем, существует ли файл
        if os.path.exists(expected_file_path):
            return send_file(expected_file_path, mimetype='audio/mp3', as_attachment=True, download_name=f"{track_id}.mp3")
        
        # Формируем команду для spotdl
        output_path_template = os.path.join(DOWNLOAD_FOLDER, f"%(title)s.%(ext)s")
        command = [
            "spotdl", "download", youtube_url,
            "--output", output_path_template,
            "--ffmpeg", "ffmpeg"  # Убедитесь, что ffmpeg установлен
        ]
        
        # Выполняем команду через subprocess
        result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # Выводим результат выполнения команды
        print("Выходные данные:")
        print(result.stdout)
        
        # Проверяем, успешно ли создан файл
        if os.path.exists(expected_file_path):
            return send_file(expected_file_path, mimetype='audio/mp3', as_attachment=True, download_name=f"{track_id}.mp3")
        else:
            return jsonify({"error": f"Ошибка при сохранении трека {track_id}."}), 500
    
    except subprocess.CalledProcessError as e:
        print(f"Произошла ошибка при выполнении команды: {e}")
        print("Ошибки:")
        print(e.stderr)
        return jsonify({"error": f"Произошла ошибка при скачивании трека {track_id}."}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port)
