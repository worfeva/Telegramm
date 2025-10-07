from flask import Flask
import threading
import requests
import time
import os

app = Flask(__name__)

REPLIT_URL = os.environ.get("REPLIT_URL", "https://replit.com/@worfeva/Telegramm#main.py")

@app.route("/")
def home():
    return "Ping Replit!"

def ping_replit():
    while True:
        try:
            print("Пингуем Replit...")
            requests.get(REPLIT_URL)
        except Exception as e:
            print("Ошибка пинга:", e)
        time.sleep(5 * 60)  # раз в 5 минут

if __name__ == "__main__":
    threading.Thread(target=ping_replit).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))