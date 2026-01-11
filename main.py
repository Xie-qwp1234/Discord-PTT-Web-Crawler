from flask import Flask
from threading import Thread
# 啟動迷你網頁，讓 Render 持續上線
app = Flask(__name__)

@app.route('/')
def home():
    return "I'm alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True

    t.start()
