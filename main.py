import os
import json
import shutil
import sqlite3
import re
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ConversationHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler)
from collections import Counter

ADMIN_CHAT_ID = 5115887933
BOT_TOKEN = "7986033726:AAHyB1I77N68Z53-YOj1B5uhJLXEuB7XdEU"
consultation_chats = {}
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
stats_file = os.path.join(BASE_DIR, "stats.json")
db_file = os.path.join(BASE_DIR, "logs.db")
REVIEWS_DB_FILE = "reviews.db"
BACKUP_DIR = "reviews_backup"
MAX_TEXT_LENGTH = 2000
SECRET_MODERATION_CODE = "/140013"
STOP_WORDS = {"и", "в", "на", "с", "по", "за", "к", "для", "это", "не", "а", "о", "у"}
TITLE, RATING, TEXT, NICKNAME, NICKNAME_CUSTOM, CONFIRM, READING = range(7)
WAITING_EDIT_TEXT = 10
ADMIN_READING, ADMIN_EDITING = range(2)
CONSULTANTS = {
    "andrey": {"id": 5115887933, "name": "Юз Андрей Анатольевич", "username": "@worfeva"},
    "valentin": {"id": 1061541258, "name": "Казанов Валентин Александрович", "username": "@kazanovval"}
}

payment_links = {
    "yoomoney": "https://yoomoney.ru/to/4100119195367811",
    "paypal": "https://paypal.me/YAndrej",
    "sberbank": "https://www.sberbank.com/sms/pbpn?requisiteNumber=79175279883"
}
CONSULTANT_WARNING = (
    "Стоимость первичной консультации составляет 2500 рублей. Повторной - 1000 рублей \n\n" 
    "❗️Мы строго соблюдаем врачебную тайну. Намеренное разглашение персональных данных третьим лицам исключено. Тем не менее, в целях Вашей информационной безопасности просьба удалять все личные данные с присылаемых в процессе консультации материалов❗️\n\n"
"❗️Консультации не являются медицинской услугой и не заменяют очный приём❗️\n\n"
    "Создавая консультативный чат Вы подтверждаете, что ознакомлены с условиями обработки персональных данных и оплаты консультации."
)
THANK_YOU_TEXT = (
    "🎉 Спасибо за оплату!\n\n"
    "Теперь Вы можете связаться с доктором по ссылке ниже. Пожалуйста, в первом сообщении подробно изложите Ваш анамнез, сопутствующие заболевания и принимаемые медикаменты (дозировки в милиграммах). Консультант ответит Вам в ближайшее время."
)
# === Сбор статистики ===    
conn_logs = sqlite3.connect(db_file, check_same_thread=False)
cursor_logs = conn_logs.cursor()
cursor_logs.execute("""
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message TEXT,
    date TEXT
)
""")
conn_logs.commit()

word_counter = {}
if os.path.exists(stats_file):
    with open(stats_file, "r", encoding="utf-8") as f:
        try:
            word_counter = json.load(f)
        except json.JSONDecodeError:
            word_counter = {}

async def log_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global word_counter
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()

    cursor_logs.execute(
        "INSERT INTO logs (message, date) VALUES (?, ?)",
        (text, datetime.now().isoformat())
    )
    conn_logs.commit()

    words = re.findall(r'\b\w+\b', text.lower())
    for word in words:
        if word not in STOP_WORDS:
            word_counter[word] = word_counter.get(word, 0) + 1

    with open(stats_file, "w", encoding="utf-8") as f:
        json.dump(word_counter, f, ensure_ascii=False, indent=2)


# === Обработчик команд ==
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text("❌ Диалог отменён.")
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("❌ Диалог отменён.")
    return ConversationHandler.END

	# === /stats ===
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor_logs.execute("SELECT message FROM logs")
    all_messages = cursor_logs.fetchall()
    words = []
    for (msg,) in all_messages:
        msg_words = re.findall(r'\b\w+\b', msg.lower())
        msg_words = [w for w in msg_words if w not in STOP_WORDS]
        words.extend(msg_words)
    counter = Counter(words)
    filtered_words = {word: count for word, count in counter.items() if count > 5}

    if not filtered_words:
        stats_text = "📊 Нет слов, которые встречались более 5 раз."
    else:
        stats_text = "📊 Слова, встречавшиеся более 5 раз:\n\n"
        for word, count in filtered_words.items():
            stats_text += f"• {word} — {count} раз(а)\n"

    await update.message.reply_text(stats_text)

# === /start ===
async def start(update, context):
    await update.message.reply_text("Чем я могу Вам помочь?"
    )
# === Вопросы ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    if not update.message or not update.message.text:
        return

    keywords_ty = ["спасибо", "благодарю", "реквизиты", "поддержать", "пожертвовать", "помочь"]
    if any(keyword in text for keyword in keywords_ty):
        keyboard = [
            [InlineKeyboardButton("💳 ЮMoney / Российские платёжные системы", callback_data="yoomoney")],
            [InlineKeyboardButton("💳 PayPal / ЕС", callback_data="paypal")],
            [InlineKeyboardButton("💳 Прямой перевод через Сбербанк", callback_data="sberbank")],
	    [InlineKeyboardButton("❌ Отмена", callback_data="cancel")],
        ]
        await update.message.reply_text(
            "Пожалуйста! Рад был помочь! 😊\n\n"
            "Если у Вас есть желание поддержать наш проект, Вы можете это сделать, нажав на кнопку ниже. "
            "Благодаря Вашей помощи другие пациенты смогут получить качественную консультацию и достоверную информацию о своём недуге.\n\n"
            "Заранее благодарим за Вашу поддержку!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    keywords_con = ["связаться", "доктором", "консультация"]
    if any(keyword in text for keyword in keywords_con):
        keyboard = [
            [InlineKeyboardButton("Юз Андрей Анатольевич", callback_data="consult_andrey")],
            [InlineKeyboardButton("Казанов Валентин Александрович",  callback_data="consult_valentin")],
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel")],
        ]

        await update.message.reply_text(
            "Пожалуйста, выберите консультанта:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return  

    keywords_bio = ["о докторах", "о врачах", "консультанты",]
    if any(keyword in text for keyword in keywords_bio):
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo="https://i.postimg.cc/ZKM364xq/1.jpg",
            caption=
            "👨‍⚕️ <b>Юз Андрей Анатольевич</b>\n"
            "Окончил ММА им. Сеченова (2010)\n"
            "🔹2012 - Специализация: Травматология и ортопедия\n"
            "🔹2016 - аспирантура на базе РМАПО в области хирургии позвоночника\n"
            "🔹с 2016 - начало работы в Германии, изначально также в специальности «Травматология и ортопедия»\n"
            "🔹2018 - смена специализации на «Внутренние болезни и ревматология»\n"
            'Консультациями в режиме телемедицины занимаюсь с 2020 года изначально на платформе <a href="https://03online.com/doctor/75114-yuz_andrey_anatolevich#ui-id-1">03online.com</a>.\n' 
            "🧾 В лечении используются протоколы Европейского альянса ассоциаций ревматологов (EULAR), а также собственные наработки\n"
            "🔹Действительный член Немецкого общества ревматологов, сертификат по УЗ-диагностике суставов DEGUM, сертификат по неотложной помощи. Автор трёх патентов на изобретения на территории РФ, а также ряда статей в англоязычных PubMed рецензируемых журналах\n",
            parse_mode="html")

        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo="https://i.postimg.cc/cLt3m2FB/2.jpg",
            caption=
            "👨‍⚕️ <b>Казанов Валентин Александрович</b>\n"
            "Окончил Ивановскую медицинскую академию (2019)\n"
            "Специализация: Ревматология (2021)\n"
            "🔹с 2021 по настояще время - работа по специальности в городе Владимир\n"
            "🔹Автор ряда научных публикаций, в том числе опубликованных в междунарожных ВАК-рецензируемых журналах. Участник и докладчик на научно-практических конференциях. Соавтор методики ЛФК при ревматоидном артрите.\n", 
            parse_mode="html")
        return
    await update.message.reply_text(
    "🧐 К сожалению, я пока что не обучен такой команде. Попробуйте снова"
    )
# === Обработчик кнопок ===
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    data = query.data

    if data == "consult_andrey" or data == "consult_valentin":
        consultant = CONSULTANTS["andrey"] if data == "consult_andrey" else CONSULTANTS["valentin"]
        context.user_data["consultant"] = consultant 

        keyboard = [
            [InlineKeyboardButton("Подвердить", callback_data="start_payment")],
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel")],
        ]
        await context.bot.send_message(
            chat_id=user.id,
            text=f"Вы запросили консультацию с {consultant['name']}.\n\n{CONSULTANT_WARNING}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "start_payment":
        keyboard = [
            [InlineKeyboardButton("💳 ЮMoney / Российские платёжные системы", callback_data="yoomoney")],
            [InlineKeyboardButton("💳 PayPal / ЕС", callback_data="paypal")],
            [InlineKeyboardButton("💳 Прямой перевод через Сбербанк", callback_data="sberbank")],
	    [InlineKeyboardButton("❌ Отмена", callback_data="cancel")],
        ]
        await context.bot.send_message(
            chat_id=user.id,
            text="🌍 Выберите способ оплаты:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data in ["yoomoney", "paypal", "sberbank"]:
        payment_link = payment_links.get(data)
        keyboard = [
                [InlineKeyboardButton("💳 Оплатить консультацию", url=payment_link)],
                [InlineKeyboardButton("✅ Я оплатил", callback_data="confirm_sber")],
                [InlineKeyboardButton("↩️ Назад", callback_data="start_payment")],
            ]

        method_names = {
            "sberbank": "Сбербанк",
            "yoomoney": "ЮMoney / Только для России",
            "paypal": "PayPal / страны ЕС"
        }
        chosen_method = method_names.get(data)
        text_msg = (
            f"✅ Вы выбрали оплату через *{chosen_method}*.\n\n"
            "📌 Для продолжения, пожалуйста, оплатите консультацию, нажав «Оплатить консультацию».\n\n"
            "Подтвердите оплату, нажав «✅ Я оплатил»."
        )

        await context.bot.send_message(
            chat_id=user.id,
            text=text_msg,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith("confirm_"):
        consultant = context.user_data.get("consultant")
        keyboard = [
            [InlineKeyboardButton(
                f"Связаться с доктором {consultant['name']}",
                url=f"https://t.me/{consultant['username'].lstrip('@')}")],
	    [InlineKeyboardButton("❌ Отмена", callback_data="cancel")],
        ]
        await context.bot.send_message(
            chat_id=user.id,
            text=THANK_YOU_TEXT,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        consultant_chat_id = consultant["id"]
        user_mention = f"<a href='tg://user?id={user.id}'>{user.first_name}</a>"
        notification_text = (
            f"📢 Пользователь {user_mention} запросил консультацию.\n")
        await context.bot.send_message(
            chat_id=consultant_chat_id,
            text=notification_text,
            parse_mode="HTML")
# ===О_Т_З_Ы_В_Ы_ ===
    # === Инициализация базы ===
if not os.path.exists(REVIEWS_DB_FILE):
    conn = sqlite3.connect(REVIEWS_DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
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
    conn.commit()
    conn.close()

try:
    conn_tmp = sqlite3.connect(REVIEWS_DB_FILE)
    cur_tmp = conn_tmp.cursor()
    cur_tmp.execute("ALTER TABLE reviews ADD COLUMN admin_message_id INTEGER")
    conn_tmp.commit()
    conn_tmp.close()
except sqlite3.OperationalError:
    pass

def get_conn():
    return sqlite3.connect(REVIEWS_DB_FILE, check_same_thread=False)

def backup_db():
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    shutil.copyfile(
        REVIEWS_DB_FILE,
        os.path.join(BACKUP_DIR, f"reviews_{timestamp}.db")
    )

def delete_review_and_traces(review_id, context=None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT title, text, admin_message_id FROM reviews WHERE id=?", (review_id,))
    r = cur.fetchone()
    if not r:
        conn.close()
        return None

    title, text_r, admin_message_id = r
    cur.execute("DELETE FROM reviews WHERE id=?", (review_id,))
    conn.commit()
    conn.close()

    try:
        conn_logs_local = sqlite3.connect(db_file, check_same_thread=False)
        cur_logs_local = conn_logs_local.cursor()
        cur_logs_local.execute(
            "DELETE FROM logs WHERE message = ? OR message = ?",
            (text_r, title)
        )
        conn_logs_local.commit()
        conn_logs_local.close()
    except Exception:
        pass
    # === Просмотр ===
async def user_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer("Диалог отменён", show_alert=False)
        try:
            await query.message.delete()  # удаляем кнопки
        except:
            pass
    elif update.message:
        await update.message.reply_text("❌ Диалог отменён.")
    return ConversationHandler.END

async def read_reviews(update: Update, context: ContextTypes.DEFAULT_TYPE, message=None):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, title, rating, nickname FROM reviews WHERE approved=1 ORDER BY created_at DESC"
    )
    reviews = cursor.fetchall()
    conn.close()

    if not reviews:
        if message:
            await message.reply_text("Пока нет одобренных отзывов.")
        else:
            await update.message.reply_text("Пока нет одобренных отзывов.")
        return READING
    keyboard = [
        [InlineKeyboardButton(f"{title} ({'⭐' * rating}) — {nickname}", callback_data=f"user_read_{review_id}")]
        for review_id, title, rating, nickname in reviews
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if message:
        await message.reply_text("📖 Отзывы:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("📖 Отзывы:", reply_markup=reply_markup)
    return READING
    
async def user_read_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    review_id = int(query.data.split("_")[-1])

    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT title, rating, nickname, text FROM reviews WHERE id=? AND approved=1", (review_id,)
    )
    review = cursor.fetchone()
    conn.close()
    title, rating, nickname, text_r = review

    keyboard = [
        [
            InlineKeyboardButton("⬅️ Назад", callback_data="user_back"),]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        query.message.chat.id,
        text=f"{title} ({rating}⭐)\n\n{text_r}\n\nОт: {nickname}",
        reply_markup=reply_markup
    )
    return READING
    
async def user_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await read_reviews(update, context, message=query.message)

read_reviews_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("(?i)^отзывы$"), read_reviews)],
    states={
        READING: [
            CallbackQueryHandler(user_read_review, pattern=r"^user_read_\d+$"),
            CallbackQueryHandler(user_back, pattern="^user_back$")
        ]
    },
    fallbacks=[],
    allow_reentry=True
)
# === Администрирование ===
async def admin_list_reviews(update: Update, context: ContextTypes.DEFAULT_TYPE, from_secret: bool = False):
    if from_secret and update.effective_user.id != ADMIN_CHAT_ID:
        return

    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, rating, nickname, approved FROM reviews ORDER BY created_at DESC")
    reviews = cursor.fetchall()
    conn.close()

    if not reviews:
        target = update.message if update.message else update.callback_query.message
        await target.reply_text("📭 Пока нет отзывов для модерации.")
        return ADMIN_READING

    keyboard = []
    for review_id, title, rating, nickname, approved in reviews:
        status = "✅" if approved else "🕓"
        button_text = f"{status} {title} ({'⭐' * rating}) — {nickname}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"admin_read_{review_id}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    target = update.message if update.message else update.callback_query.message
    await target.reply_text(
        "🛠️ *Модерация отзывов:*",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    return ADMIN_READING

    # === Просмотр отзыва ===
async def admin_read_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    review_id = int(query.data.split("_")[-1])

    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT title, rating, nickname, text, approved FROM reviews WHERE id=?", (review_id,))
    title, rating, nickname, text_r, approved = cursor.fetchone()
    conn.close()

    if approved:
        buttons = [
            InlineKeyboardButton("✏️ Редактировать", callback_data=f"admin_edit_{review_id}"),
            InlineKeyboardButton("🗑 Удалить", callback_data=f"admin_delete_{review_id}"),
	    InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel"),
        ]
    else:
        buttons = [
            InlineKeyboardButton("✅ Одобрить", callback_data=f"admin_approve_{review_id}"),
            InlineKeyboardButton("🗑 Удалить", callback_data=f"admin_delete_{review_id}"),
	    InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel"),
        ]

    keyboard = [buttons, [InlineKeyboardButton("⬅️ Назад", callback_data="admin_back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"*{title}* ({rating}⭐)\n\n{text_r}\n\n👤 {nickname}",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    return ADMIN_READING

    # === Одобрение ===
async def admin_approve_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    review_id = int(query.data.split("_")[-1])

    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("UPDATE reviews SET approved=1 WHERE id=?", (review_id,))
    cursor.execute("SELECT user_id FROM reviews WHERE id=?", (review_id,))
    user_row = cursor.fetchone()
    conn.commit()
    conn.close()
    backup_db()

    # Отправляем уведомление пользователю
    if user_row and user_row[0]:
        try:
            await context.bot.send_message(chat_id=user_row[0], text="✅ Ваш отзыв опубликован! Спасибо!")
        except Exception:
            pass

    await query.edit_message_text("✅ Отзыв одобрен.")
    return await admin_list_reviews(update, context)

# === Удаление ===
async def admin_delete_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    review_id = int(query.data.split("_")[-1])

    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM reviews WHERE id=?", (review_id,))
    user_row = cursor.fetchone()
    cursor.execute("DELETE FROM reviews WHERE id=?", (review_id,))
    conn.commit()
    conn.close()
    backup_db()

    # Уведомляем пользователя
    if user_row and user_row[0]:
        try:
            await context.bot.send_message(chat_id=user_row[0], text="❌ Ваш отзыв не прошёл модерацию и был удалён.")
        except Exception:
            pass

    await query.edit_message_text("🗑 Отзыв удалён.")
    return await admin_list_reviews(update, context)

# === Редактирование ===
async def admin_edit_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    review_id = int(query.data.split("_")[-1])

    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT title, text FROM reviews WHERE id=?", (review_id,))
    title, text_r = cursor.fetchone()
    conn.close()

    context.user_data["edit_review_id"] = review_id
    await query.edit_message_text(
        f"📝 *Редактирование отзыва* **{title}**:\n\n"
        f"Текущий текст:\n{text_r}\n\n"
        f"✍ Введите новый текст или нажмите 'Отмена'.",
        parse_mode="Markdown"
    )

    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel_edit")]]
    await query.message.reply_text("💬 Напишите новый текст отзыва:", reply_markup=InlineKeyboardMarkup(keyboard))
    return ADMIN_EDITING

async def admin_cancel_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    return await admin_back(update, context)

async def admin_save_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    review_id = context.user_data.get("edit_review_id")
    new_text = update.message.text.strip()

    if not new_text:
        await update.message.reply_text("⚠️ Текст не может быть пустым.")
        return ADMIN_EDITING

    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("UPDATE reviews SET text=? WHERE id=?", (new_text, review_id))
    conn.commit()
    conn.close()
    backup_db()

    await update.message.reply_text("✅ Текст отзыва обновлён.")
    return await admin_list_reviews(update, context)

# === Назад к списку ===
async def admin_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    return await admin_list_reviews(update, context)

# === Вход по секретному коду ===
async def secret_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await admin_list_reviews(update, context, from_secret=True)

# === Регистрация хендлеров ===
moderation_handler = MessageHandler(filters.Regex(f"^{SECRET_MODERATION_CODE}$"), secret_entry)

admin_review_conv = ConversationHandler(
    entry_points=[moderation_handler],
    states={
        ADMIN_READING: [
            CallbackQueryHandler(admin_read_review, pattern=r"^admin_read_\d+$"),
            CallbackQueryHandler(admin_approve_review, pattern=r"^admin_approve_\d+$"),  # одобрить
            CallbackQueryHandler(admin_delete_review, pattern=r"^admin_delete_\d+$"),    # удалить
            CallbackQueryHandler(admin_edit_review, pattern=r"^admin_edit_\d+$"),
            CallbackQueryHandler(admin_back, pattern="^admin_back$"),
	    CallbackQueryHandler(cancel, pattern="^admin_cancel$"),
        ],
        ADMIN_EDITING: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, admin_save_edit),
            CallbackQueryHandler(admin_cancel_edit, pattern="^admin_cancel_edit$"),
	    CallbackQueryHandler(cancel, pattern="^admin_cancel$"),
        ],
    },
    fallbacks=[CommandHandler("cancel",cancel), MessageHandler(filters.Regex(r"^/(start|stats)$"), cancel)],
    allow_reentry=True)

# === О_Т_З_Ы_В_Ы_ ===
    # === Написание ===
async def start_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    if text != "оставить отзыв":
        return

    user_id = update.message.from_user.id
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM reviews WHERE user_id=?", (user_id,))
    if cursor.fetchone():
        conn.close()
        await update.message.reply_text("❌ Вы уже оставили отзыв.")
        return ConversationHandler.END
    conn.close()

    await update.message.reply_text(
        f"👋 Добро пожаловать в систему отзывов об оказанных консультациях!\n\n"
        f"❗️ Правила оставления отзывов:\n"
        f"🕵️ Отзыв можно оставить анонимным\n"
        f" Один отзыв с аккаунта\n"
        f"✍ Максимальная длина — {MAX_TEXT_LENGTH} символов\n"
        f"🔍 Пожалуйста, воздержитесь от нелитературных выражений. Все отзывы проходят модерацию\n\n"
        "👉 Введите заголовок вашего отзыва:"
    )
    return TITLE
    # === Заголовок ===
async def review_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    title = update.message.text.strip()
    if not title:
        await update.message.reply_text("Поле не может быть пустым. Введите снова:")
        return TITLE

    context.user_data["review"] = {
        "title": title,
        "user_id": update.message.from_user.id,
        "username": f"@{update.message.from_user.username}" if update.message.from_user.username else "Anonymous"
    }

    keyboard = [
	[InlineKeyboardButton(f"{i}⭐", callback_data=f"rate_{i}") for i in range(1, 6)],
	[InlineKeyboardButton("❌ Отмена", callback_data="cancel")],
    ]
    await update.message.reply_text("Дайте Вашу оценку консультации по шкале от 1–5:", reply_markup=InlineKeyboardMarkup(keyboard))
    return RATING
    # === Оценка ===
async def review_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    rating = int(query.data.split("_")[1])
    context.user_data["review"]["rating"] = rating

    await query.edit_message_text(
        f"Вы дали оценку: {rating}⭐. Благодарим Вас!\n\nВведите текст отзыва (не более {MAX_TEXT_LENGTH} символов):"
    )
    return TEXT
    # === Подпись ===
async def review_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if len(text) > MAX_TEXT_LENGTH:
        await update.message.reply_text(
            f"Превышена максимальная длинна сообщения в {MAX_TEXT_LENGTH} символов."
        )
        return TEXT
    context.user_data["review"]["text"] = text
    keyboard = [
        [InlineKeyboardButton("Использовать ник Telegram", callback_data="nick_username")],
        [InlineKeyboardButton("Использовать псевдоним", callback_data="nick_custom")],
	[InlineKeyboardButton("❌ Отмена", callback_data="cancel")],
    ]
    await update.message.reply_text("Как подписать отзыв?", reply_markup=InlineKeyboardMarkup(keyboard))
    return NICKNAME
async def review_nickname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "nick_username":
        context.user_data["review"]["nickname"] = context.user_data["review"]["username"] or "Anonymous"
        await query.edit_message_text("Используем ваш ник Telegram")
        return await review_confirm(update, context)
    else:
        await query.edit_message_text("Введите псевдоним:")
        return NICKNAME_CUSTOM

async def review_nickname_custom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nickname = update.message.text.strip()
    if not nickname:
        await update.message.reply_text("Поле не заполнено. Введите снова:")
        return NICKNAME_CUSTOM
    context.user_data["review"]["nickname"] = nickname
    return await review_confirm(update, context)
    # === Подтверждение ===
async def review_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    review = context.user_data["review"]
    date_str = datetime.now().strftime("%d.%m.%Y")
    text = (
        f"✨ Проверьте отзыв перед отправкой\n\n"
        f"**Заголовок:** {review['title']}\n"
        f"**Оценка:** {'⭐'*review['rating']}\n"
        f"**Текст:** {review['text']}\n"
        f"**Автор:** {review['nickname']}"
        f"**Дата:** {date_str}"
    )
    keyboard = [
        [InlineKeyboardButton("✅ Отправить на модерацию", callback_data="send_review")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_review")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)
    return CONFIRM
    # === Отправка ===
async def review_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    review = context.user_data["review"]

    if query.data == "send_review":
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO reviews (user_id, username, nickname, title, rating, text, approved, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 0, ?)
        """, (
            review["user_id"],
            review["username"],
            review["nickname"],
            review["title"],
            review["rating"],
            review["text"],
            datetime.now().isoformat()
        ))
        conn.commit()
        review_id = cursor.lastrowid
        conn.close()
        backup_db()

        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=(
                f"🆕 Новый отзыв от {review['nickname']}\n"
                f"Оценка: {'⭐' * review['rating']}\n")
        )
        await query.edit_message_text(
            "✅ Ваш отзыв отправлен на модерацию. Вы будете оповещены об одобрении отзыва. Спасибо!"
        )
        return ConversationHandler.END
    else:
        await query.edit_message_text("❌ Отзыв отменён.")
        return ConversationHandler.END
review_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex(r"(?i)^оставить отзыв$"), start_review)],
    states={
        TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, review_title)],
        RATING: [CallbackQueryHandler(review_rating, pattern=r"^rate_\d+$")],
        TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, review_text)],
        NICKNAME: [CallbackQueryHandler(review_nickname, pattern="^nick_")],
        NICKNAME_CUSTOM: [MessageHandler(filters.TEXT & ~filters.COMMAND, review_nickname_custom)],
        CONFIRM: [CallbackQueryHandler(review_final, pattern="^(send_review|cancel_review)$"), CallbackQueryHandler(user_cancel, pattern="^cancel$")],
    },
    fallbacks=[
        CommandHandler("cancel", cancel),
	MessageHandler(filters.Regex(r"^/(start|stats)$"), cancel)
    ],
    allow_reentry=True		
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
def main():
    import asyncio
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(review_conv)
    app.add_handler(admin_review_conv)
    app.add_handler(read_reviews_handler)
    app.add_handler(moderation_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, log_message), group=0)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message), group=1)
    app.add_handler(CallbackQueryHandler(user_cancel, pattern="^cancel$"))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.run_polling(drop_pending_updates=True)
    

if __name__ == "__main__": 
            main()