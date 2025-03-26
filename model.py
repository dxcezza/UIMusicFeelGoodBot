from sqlalchemy import Column, String, Boolean, create_engine, LargeBinary, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()

class Track(Base):
    __tablename__ = 'tracks'

    videoId = Column(String, primary_key=True)  # ID трека
    title = Column(String, nullable=False)      # Название трека
    artist = Column(String, nullable=False)     # Исполнитель
    thumbnail = Column(String, nullable=False)   # URL обложки
    audioData = Column(LargeBinary, nullable=True)  # Двоичные данные аудио
    is_downloaded = Column(Boolean, default=False)  # Статус скачивания
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'videoId': self.videoId,
            'title': self.title,
            'artist': self.artist,
            'thumbnail': self.thumbnail,
            'is_downloaded': self.is_downloaded
        }
