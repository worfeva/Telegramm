import sqlite3
import glob
import os

# Путь к папке с бэкапами
backup_folder = backup_folder = "C:\\Users\\User\\reviews_backup"

# Итоговая база
merged_db = "reviews_merged.db"

# Получаем список всех файлов .db в папке
backup_files = sorted(glob.glob(os.path.join(backup_folder, "*.db")))

# Создаем/открываем итоговую базу
conn_merged = sqlite3.connect(merged_db)
cursor_merged = conn_merged.cursor()

# Создаем таблицу, если ее нет
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

# Объединяем все файлы
for file in backup_files:
    print(f"Обрабатываем: {file}")
    conn = sqlite3.connect(file)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, nickname, title, rating, text, approved, created_at, admin_message_id FROM reviews")
    rows = cursor.fetchall()

    for row in rows:
        try:
            cursor_merged.execute("""
                INSERT INTO reviews (user_id, username, nickname, title, rating, text, approved, created_at, admin_message_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, row)
        except sqlite3.IntegrityError:
            pass  # если вдруг дубликат id

    conn.commit()
    conn.close()

conn_merged.commit()
conn_merged.close()
print("✅ Все отзывы объединены в reviews_merged.db")