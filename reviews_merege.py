import sqlite3
import glob
import os
from datetime import datetime

# Путь к папке с бэкапами
backup_folder = "reviews_backup"  # в том же каталоге, что и бот

# Путь к рабочей базе бота
main_db = "reviews.db"

# Получаем список всех файлов .db в папке
backup_files = sorted(glob.glob(os.path.join(backup_folder, "*.db")))

# Открываем рабочую базу бота
conn_main = sqlite3.connect(main_db)
cursor_main = conn_main.cursor()

# Создаём таблицу, если вдруг её нет
cursor_main.execute("""
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
conn_main.commit()

# Проходим по всем бэкапам
for backup_file in backup_files:
    print(f"Обрабатываем: {backup_file}")
    conn_backup = sqlite3.connect(backup_file)
    cursor_backup = conn_backup.cursor()

    cursor_backup.execute("""
        SELECT user_id, username, nickname, title, rating, text, created_at, admin_message_id
        FROM reviews
    """)
    rows = cursor_backup.fetchall()

    for row in rows:
        # Вставляем как новые записи, approved = 1
        cursor_main.execute("""
            INSERT INTO reviews (user_id, username, nickname, title, rating, text, approved, created_at, admin_message_id)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
        """, row)
    
    conn_main.commit()
    conn_backup.close()

conn_main.commit()
conn_main.close()
print("✅ Все отзывы из бэкапов добавлены и помечены как одобренные.")
