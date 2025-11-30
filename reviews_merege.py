import sqlite3
import glob
import os

# === Настройки ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # директория с ботом
backup_folder = "C:\\Users\\User\\reviews_backup"
final_db = os.path.join(BASE_DIR, "reviews.db")  # итоговая база

# Получаем список всех файлов .db в папке
backup_files = sorted(glob.glob(os.path.join(backup_folder, "*.db")))

# Создаём/открываем итоговую базу
conn_merged = sqlite3.connect(final_db)
cursor_merged = conn_merged.cursor()

# Создаём таблицу, если её нет
cursor_merged.execute("""
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    nickname TEXT,
    title TEXT,
    rating INTEGER,
    text TEXT,
    approved INTEGER DEFAULT 0,
    created_at TEXT,
    admin_message_id INTEGER DEFAULT NULL
)
""")
conn_merged.commit()

# Объединяем все бэкапы
for file in backup_files:
    print(f"Обрабатываем: {file}")
    conn = sqlite3.connect(file)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT user_id, username, nickname, title, rating, text, approved, created_at, admin_message_id
            FROM reviews
        """)
        rows = cursor.fetchall()
    except sqlite3.OperationalError:
        print(f"⚠️ Таблица reviews не найдена в {file}, пропускаем.")
        conn.close()
        continue

    for row in rows:
        user_id, username, nickname, title, rating, text_r, approved, created_at, admin_message_id = row
        # Вставляем все отзывы и делаем их одобренными
        cursor_merged.execute("""
            INSERT INTO reviews (user_id, username, nickname, title, rating, text, approved, created_at, admin_message_id)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
        """, (user_id, username, nickname, title, rating, text_r, created_at, admin_message_id))
    
    conn.commit()
    conn.close()

conn_merged.commit()
conn_merged.close()

print("✅ подавись!")
