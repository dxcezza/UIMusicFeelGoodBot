import os
from sqlalchemy import create_engine
from model import Base
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Получаем URL базы данных из переменных окружения
DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    raise ValueError("DATABASE_URL не установлен в переменных окружения")

# Создаем движок базы данных
engine = create_engine(DATABASE_URL)

def run_migrations():
    try:
        # Создаем все таблицы
        Base.metadata.create_all(bind=engine)
        print("Миграция успешно выполнена")
    except Exception as e:
        print(f"Ошибка при выполнении миграции: {e}")

if __name__ == "__main__":
    run_migrations()
