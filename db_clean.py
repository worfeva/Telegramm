import sqlite3
import shutil
import os

DB_FILE = "reviews.db"

print("🔧 Старт очистки базы…")

# 1. Делаем резервную копию

cursor.execute("""
    SELECT id, user_id, username, nickname, title, rating, text, approved, created_at, admin_message_id
    FROM reviews
""")
rows = cursor.fetchall()
print(f"📄 Загружено записей: {len(rows)}")

# 3. Убираем дубликаты (оставляем первую встреченную запись)
unique_reviews = {}
for row in rows:
    key = (row[3], row[4], row[5], row[6], row[8])  # nickname, title, rating, text, created_at
    if key not in unique_reviews:
        unique_reviews[key] = row

cleaned = list(unique_reviews.values())
print(f"✨ После удаления дублей осталось: {len(cleaned)}")

# 4. Чистим таблицу
cursor.execute("DELETE FROM reviews")
conn.commit()

# 5. Записываем данные обратно с approved = 1
for r in cleaned:
    cursor.execute("""
        INSERT INTO reviews (user_id, username, nickname, title, rating, text, approved, created_at, admin_message_id)
        VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
    """, (r[1], r[2], r[3], r[4], r[5], r[6], r[8], r[9]))

conn.commit()
conn.close()

print("✅ Чтоб ты подавился!")
print("🔍 Можешь проверить через sqlite3 reviews_merged.db → SELECT COUNT(*) FROM reviews;")