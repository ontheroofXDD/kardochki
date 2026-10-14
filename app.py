"""
Telegram-бот: коллекционные музыкальные карточки. Deezer-импорт.
Стандартная библиотека Python.
"""
import datetime as dt
import hashlib
import html
import json
import os
import random
import re
import sqlite3
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from urllib.parse import quote

DEBUG_LOG = "bot_debug.log"


def say(msg):
    line = f"{dt.datetime.now():%d.%m %H:%M:%S} {msg}"
    try:
        import resource
        mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024
        line += f" [память {mb} МБ]"
    except Exception:
        pass
    print(line, flush=True)
    try:
        with open(DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _excepthook(t, v, tb):
    say("❌ ОШИБКА:\n" + "".join(traceback.format_exception(t, v, tb)))


sys.excepthook = _excepthook
say("▶ python запустил app.py")


def load_env():
    base = os.path.dirname(os.path.abspath(__file__))
    for path in (os.path.join(base, ".env"), ".env"):
        if os.path.isfile(path):
            with open(path, encoding="utf-8-sig") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
            return


load_env()

TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not TOKEN:
    say("❌ BOT_TOKEN не найден. Проверь .env")
    raise SystemExit(1)
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x.lstrip("-").isdigit()}
DB_PATH = os.getenv("DB_PATH", "music.db")

CLAIM_AMOUNT = int(os.getenv("CLAIM_AMOUNT", "450"))
CLAIM_SECONDS = int(float(os.getenv("CLAIM_HOURS", "2")) * 3600)
CLAIM_BONUS = int(os.getenv("CLAIM_BONUS", "200"))
CLAIM_MAX_SECONDS = max(CLAIM_SECONDS, int(float(os.getenv("CLAIM_MAX_HOURS", "8")) * 3600))
STEP_SECONDS = 3600
PITY_LEGENDARY = int(os.getenv("PITY_LEGENDARY", "50"))
PITY_EPIC = int(os.getenv("PITY_EPIC", "15"))
OPEN_COST = int(os.getenv("OPEN_COST", "300"))
REFERRAL_BONUS = int(os.getenv("REFERRAL_BONUS", "1000"))
REFERRAL_MAX_AGE = 600
SUB_BASIC_STARS = int(os.getenv("SUB_BASIC_STARS", "150"))
SUB_PREMIUM_STARS = int(os.getenv("SUB_PREMIUM_STARS", "250"))
SUB_DAYS = int(os.getenv("SUB_DAYS", "30"))
SUB_BASIC_MULT = float(os.getenv("SUB_BASIC_MULT", "1.5"))
SUB_PREMIUM_MULT = float(os.getenv("SUB_PREMIUM_MULT", "2.0"))
CHANNEL_REWARD = int(os.getenv("CHANNEL_REWARD", "2000"))
CHANNEL2_REWARD = int(os.getenv("CHANNEL2_REWARD", "1500"))

TRADE_TTL = 24 * 3600
PAGE = 12
API = f"https://api.telegram.org/bot{TOKEN}/"
BOT_USERNAME = ""

esc = html.escape

RARITIES = {
    "common":    (68, "⚪", "Обычный", "Обычные"),
    "rare":      (22, "🔵", "Редкий", "Редкие"),
    "epic":      (7,  "🟣", "Эпический", "Эпические"),
    "legendary": (3,  "🟡", "Легендарный", "Легендарные"),
}
RARITY_ORDER_SQL = "CASE {c} WHEN 'legendary' THEN 0 WHEN 'epic' THEN 1 WHEN 'rare' THEN 2 ELSE 3 END"

COSMETICS = {
    "note": ("🎵", "Нотка", 500),
    "mic": ("🎤", "Микрофон", 1000),
    "vinyl": ("💿", "Винил", 1500),
    "fire": ("🔥", "Огонь", 2500),
    "crown": ("👑", "Корона", 5000),
}

FRAMES = {"common": "⬜️", "rare": "🟩", "epic": "🟪", "legendary": "🟧"}
SPECIAL_FRAMES = {"crown": "👑", "fire": "🔥", "diamond": "💎", "rainbow": "🌈"}

ACHIEVEMENTS = {
    "first":   ("🎵", "Первая карточка",  "Собрать 1 карточку"),
    "ten":     ("🎶", "Десятка",          "10 уникальных"),
    "fifty":   ("💿", "Полтинник",        "50 уникальных"),
    "half":    ("🏆", "Половина",         "50% коллекции"),
    "full":    ("👑", "Коллекционер",     "100% коллекции"),
    "c10":     ("⚪", "Обычный день",      "10 common"),
    "r10":     ("🟢", "Редкий улов",       "10 rare"),
    "e5":      ("🟣", "Эпик-ловец",        "5 epic"),
    "l1":      ("🟠", "Легенда",           "1 legendary"),
    "trade1":  ("🤝", "Первый обмен",      "Успешно обменяться"),
    "fire7":   ("🔥", "Марафонец",         "7 дней подряд /open"),
    "rich100": ("💎", "Богач",             "100 экземпляров"),
}

TITLES = {
    "newbie":    ("🎤", "Новичок",      "Первая карточка"),
    "meloman":   ("🎶", "Меломан",      "10 уникальных"),
    "collector": ("💿", "Коллекционер", "25 уникальных"),
    "master":    ("🏆", "Мастер",       "50 уникальных"),
    "legend":    ("👑", "Легенда",      "Вся коллекция"),
    "devoted":   ("🔥", "Преданный",    "Серия 7 дней"),
    "trader":    ("🤝", "Торговец",     "5 обменов"),
    "expert":    ("🎧", "Знаток",       "5+ в 4 жанрах"),
    "rich":      ("💎", "Богач",        "100 экземпляров"),
    "chosen":    ("🌟", "Избранный",    "5+ достижений"),
}
TITLE_ORDER = ["chosen","legend","master","collector","meloman","devoted","trader","rich","expert","newbie"]

DEMO_TRACKS = [
    ('bad guy', 'Billie Eilish', 'When We All Fall Asleep, Where Do We Go?'),
    ('Levitating', 'Dua Lipa', 'Future Nostalgia'),
    ('Someone Like You', 'Adele', '21'),
    ('Shake It Off', 'Taylor Swift', '1989'),
    ('Umbrella', 'Rihanna', 'Good Girl Gone Bad'),
    ('Poker Face', 'Lady Gaga', 'The Fame'),
    ('Like a Prayer', 'Madonna', 'Like a Prayer'),
    ('Blinding Lights', 'The Weeknd', 'After Hours'),
    ('Shape of You', 'Ed Sheeran', '÷ (Divide)'),
    ('Stronger', 'Kanye West', 'Graduation'),
    ('Uptown Funk', 'Mark Ronson', 'Uptown Special'),
    ('Lose Yourself', 'Eminem', '8 Mile (Soundtrack)'),
    ('Imagine', 'John Lennon', 'Imagine'),
    ('Purple Rain', 'Prince', 'Purple Rain'),
    ('Thriller', 'Michael Jackson', 'Thriller'),
    ('Believer', 'Imagine Dragons', 'Evolve'),
    ('Take On Me', 'a-ha', 'Hunting High and Low'),
    ('Creep', 'Radiohead', 'Pablo Honey'),
    ('Группа крови', 'Кино', 'Группа крови'),
    ('Smells Like Teen Spirit', 'Nirvana', 'Nevermind'),
    ('Hotel California', 'Eagles', 'Hotel California'),
    ('Wish You Were Here', 'Pink Floyd', 'Wish You Were Here'),
    ('Bohemian Rhapsody', 'Queen', 'A Night at the Opera'),
    ('Stairway to Heaven', 'Led Zeppelin', 'Led Zeppelin IV'),
]

QUEST_POOL = [
    ("open3",  "🎴", "Открой 3 карточки",        3, 30, "card"),
    ("qty5",   "🎁", "Собери 5 экземпляров",     5, 25, None),
    ("trade1", "🤝", "Соверши 1 обмен",          1, 50, None),
    ("ach1",   "🏅", "Получи новое достижение",  1, 25, None),
    ("msg5",   "💬", "Отправь боту 5 сообщений", 5, 20, None),
    ("open5",  "🔥", "Открой 5 карточек",        5, 60, "card"),
]

IMPORT_HELP = (
    "🎧 <b>Импорт треков из Deezer</b>\n\n"
    "<code>/spotify ссылка_на_артиста</code>\n"
    "или <code>/spotify название артиста</code>\n\n"
    "Ссылку бери на <b>deezer.com</b>: открой артиста → Поделиться → Копировать ссылку.\n\n"
    "Бот импортирует <b>все треки</b> артиста с обложками, создаст его в разделе «🎤 Артисты» "
    "и раскидает редкости автоматически."
)

ALBUM_HELP = (
    "💿 <b>Управление треками</b>\n\n"
    "<code>/addtrack Название | Артист | Альбом | редкость</code>\n"
    "<code>/addalbum Артист | Альбом | редкость | трек1; трек2 [epic]</code> + фото\n"
    "<code>/setcover Артист | Альбом</code> + фото\n"
    "<code>/delalbum Артист | Альбом</code> · <code>/delcard ID</code> · <code>/clearcards</code>\n"
    "<code>/setrarity ID редкость</code>\n\n"
    "🎤 <b>Артисты:</b>\n"
    "<code>/addartist Имя | описание</code> + фото\n"
    "<code>/artists</code> · <code>/delartist ID</code> · <code>/setartistcover Имя</code> + фото\n\n"
    "🎧 <b>Импорт:</b> <code>/spotify ссылка_с_deezer.com</code>\n\n"
    "🖼 <b>Прочее:</b>\n"
    "<code>/setwelcome</code> + медиа · <code>/setwelcome off</code>\n"
    "<code>/givecoins @ник 500</code>\n\n"
    "📢 <b>Каналы:</b>\n"
    "<code>/setchannel @канал</code> · <code>/setchannel2 @канал</code>\n"
    "<code>/setchreward 2000</code> · <code>/setchreward2 1500</code>"
)


# ───────────────────────── Telegram API ─────────────────────────

class TgError(Exception):
    pass


def tg(method, **params):
    data = json.dumps(params, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(API + method, data=data, headers={"Content-Type": "application/json"})
    timeout = int(params.get("timeout", 0)) + 30
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            res = json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            res = json.loads(e.read())
        except Exception:
            res = {"ok": False, "description": f"HTTP {e.code}"}
    if not res.get("ok"):
        raise TgError(res.get("description", "ошибка Telegram"))
    return res["result"]


def btn(text, data):
    return {"text": text, "callback_data": data}


def kb(rows):
    return {"inline_keyboard": rows}


def send(chat_id, text, markup=None):
    p = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    if markup:
        p["reply_markup"] = markup
    return tg("sendMessage", **p)


def send_long(chat_id, lines, markup=None):
    chunk, parts = "", []
    for line in lines:
        if len(chunk) + len(line) + 1 > 3800:
            parts.append(chunk)
            chunk = ""
        chunk += line + "\n"
    if chunk:
        parts.append(chunk)
    for i, p in enumerate(parts):
        last = i == len(parts) - 1
        send(chat_id, p, markup if (last and markup) else None)


def send_media(chat_id, kind, file_id, caption, markup=None):
    method = {"photo": "sendPhoto", "animation": "sendAnimation", "video": "sendVideo"}.get(kind)
    if file_id and method:
        p = {"chat_id": chat_id, kind: file_id, "caption": caption[:1024], "parse_mode": "HTML"}
        if markup:
            p["reply_markup"] = markup
        try:
            return tg(method, **p)
        except TgError:
            say("не удалось отправить медиа")
    return send(chat_id, caption, markup)


def answer_cb(cq_id, text=None, alert=False):
    p = {"callback_query_id": cq_id}
    if text:
        p["text"] = text
        p["show_alert"] = alert
    try:
        tg("answerCallbackQuery", **p)
    except TgError:
        pass


def edit_menu(cq, text, markup=None):
    msg = cq.get("message") or {}
    chat_id, mid = msg.get("chat", {}).get("id"), msg.get("message_id")
    if not chat_id or not mid:
        return
    is_media = any(k in msg for k in ("photo", "animation", "video", "document"))
    try:
        if is_media:
            tg("editMessageCaption", chat_id=chat_id, message_id=mid,
               caption=text[:1024], parse_mode="HTML", reply_markup=markup or kb([]))
        else:
            tg("editMessageText", chat_id=chat_id, message_id=mid, text=text,
               parse_mode="HTML", disable_web_page_preview=True, reply_markup=markup or kb([]))
    except TgError:
        pass


def edit_text(chat_id, message_id, text, markup=None):
    try:
        tg("editMessageText", chat_id=chat_id, message_id=message_id, text=text,
           parse_mode="HTML", disable_web_page_preview=True,
           reply_markup=markup if markup else kb([]))
    except TgError:
        pass


def clear_markup(chat_id, message_id):
    try:
        tg("editMessageReplyMarkup", chat_id=chat_id, message_id=message_id, reply_markup=kb([]))
    except TgError:
        pass


# ───────────────────────── БД ─────────────────────────

db = None


def init_db():
    global db
    if os.path.exists(DB_PATH):
        try:
            tmp = sqlite3.connect(DB_PATH)
            cols = [r[1] for r in tmp.execute("PRAGMA table_info(cards)")]
            tmp.close()
        except sqlite3.Error:
            cols = []
        if cols and "title" not in cols:
            os.replace(DB_PATH, DB_PATH + ".old_backup")
            say(f"старая база → {DB_PATH}.old_backup")
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY, username TEXT, name TEXT,
            coins INTEGER NOT NULL DEFAULT 0, last_claim INTEGER NOT NULL DEFAULT 0,
            equipped TEXT, joined INTEGER NOT NULL DEFAULT 0,
            pity_leg INTEGER NOT NULL DEFAULT 0, pity_epic INTEGER NOT NULL DEFAULT 0,
            open_streak INTEGER NOT NULL DEFAULT 0, last_open_day TEXT,
            referred_by INTEGER, ref_count INTEGER NOT NULL DEFAULT 0, ref_earned INTEGER NOT NULL DEFAULT 0,
            sub_tier TEXT, sub_until INTEGER NOT NULL DEFAULT 0,
            xp INTEGER NOT NULL DEFAULT 0, title TEXT,
            avatar_card INTEGER, warns INTEGER NOT NULL DEFAULT 0,
            trades_ok INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS cards(
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, artist TEXT NOT NULL,
            album TEXT NOT NULL, rarity TEXT NOT NULL, image TEXT,
            artist_id INTEGER,
            UNIQUE(title, artist, album)
        );
        CREATE TABLE IF NOT EXISTS artists(
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE,
            image TEXT, description TEXT, spotify_id TEXT, created INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS inventory(
            user_id INTEGER NOT NULL, card_id INTEGER NOT NULL, qty INTEGER NOT NULL,
            PRIMARY KEY(user_id, card_id)
        );
        CREATE TABLE IF NOT EXISTS trades(
            id INTEGER PRIMARY KEY AUTOINCREMENT, from_id INTEGER NOT NULL, to_id INTEGER NOT NULL,
            from_card INTEGER NOT NULL, to_card INTEGER NOT NULL, status TEXT NOT NULL, created INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS submissions(
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, title TEXT NOT NULL,
            artist TEXT NOT NULL, album TEXT NOT NULL, image TEXT NOT NULL,
            status TEXT NOT NULL, created INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS owned_cosmetics(
            user_id INTEGER NOT NULL, item TEXT NOT NULL, PRIMARY KEY(user_id, item)
        );
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS referrals(
            invited_id INTEGER PRIMARY KEY, referrer_id INTEGER NOT NULL,
            rewarded INTEGER NOT NULL DEFAULT 0, created INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS payments(
            charge_id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, tier TEXT NOT NULL,
            stars INTEGER NOT NULL, days INTEGER NOT NULL, created INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS channel_rewards(
            user_id INTEGER PRIMARY KEY, claimed INTEGER NOT NULL DEFAULT 0, created INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS channel2_rewards(
            user_id INTEGER PRIMARY KEY, claimed INTEGER NOT NULL DEFAULT 0, created INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS achievements(
            user_id INTEGER NOT NULL, code TEXT NOT NULL, got INTEGER NOT NULL,
            PRIMARY KEY(user_id, code)
        );
        CREATE TABLE IF NOT EXISTS quests(
            user_id INTEGER NOT NULL, day TEXT NOT NULL, code TEXT NOT NULL,
            progress INTEGER NOT NULL DEFAULT 0, target INTEGER NOT NULL,
            xp INTEGER NOT NULL DEFAULT 0, done INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(user_id, day, code)
        );
        CREATE TABLE IF NOT EXISTS friends(
            user_id INTEGER NOT NULL, friend_id INTEGER NOT NULL, status TEXT NOT NULL,
            created INTEGER NOT NULL, PRIMARY KEY(user_id, friend_id)
        );
    """)
    ensure_columns("users", {
        "pity_leg": "INTEGER NOT NULL DEFAULT 0",
        "pity_epic": "INTEGER NOT NULL DEFAULT 0",
        "open_streak": "INTEGER NOT NULL DEFAULT 0",
        "last_open_day": "TEXT",
        "referred_by": "INTEGER",
        "ref_count": "INTEGER NOT NULL DEFAULT 0",
        "ref_earned": "INTEGER NOT NULL DEFAULT 0",
        "sub_tier": "TEXT",
        "sub_until": "INTEGER NOT NULL DEFAULT 0",
        "xp": "INTEGER NOT NULL DEFAULT 0",
        "title": "TEXT",
        "avatar_card": "INTEGER",
        "warns": "INTEGER NOT NULL DEFAULT 0",
        "trades_ok": "INTEGER NOT NULL DEFAULT 0",
    })
    ensure_columns("cards", {"artist_id": "INTEGER"})
    db.commit()
    purge_demo()


def ensure_columns(table, cols):
    have = {r[1] for r in db.execute(f"PRAGMA table_info({table})")}
    for name, ddl in cols.items():
        if name not in have:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
    db.commit()


def full_name(u):
    name = " ".join(x for x in (u.get("first_name"), u.get("last_name")) if x)
    return name or str(u["id"])


def ensure_user(u):
    db.execute(
        "INSERT INTO users(user_id, username, name, joined) VALUES(?,?,?,?) "
        "ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, name=excluded.name",
        (u["id"], (u.get("username") or "").lower() or None, full_name(u), int(time.time())),
    )
    db.commit()


def get_user(uid):
    return db.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()


def get_setting(key):
    r = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return r["value"] if r else None


def set_setting(key, value):
    if value is None:
        db.execute("DELETE FROM settings WHERE key=?", (key,))
    else:
        db.execute("INSERT INTO settings(key, value) VALUES(?,?) "
                   "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
    db.commit()


def purge_demo():
    if get_setting("demo_purged"):
        return
    n = 0
    for t, a, al in DEMO_TRACKS:
        r = db.execute("SELECT id FROM cards WHERE title=? AND artist=? AND album=?", (t, a, al)).fetchone()
        if r:
            db.execute("DELETE FROM inventory WHERE card_id=?", (r["id"],))
            db.execute("DELETE FROM cards WHERE id=?", (r["id"],))
            n += 1
    db.commit()
    set_setting("demo_purged", "1")
    if n:
        say(f"удалено демо-треков: {n}")


def add_card(user_id, card_id, delta):
    db.execute("INSERT INTO inventory(user_id, card_id, qty) VALUES(?,?,?) "
               "ON CONFLICT(user_id, card_id) DO UPDATE SET qty = qty + ?",
               (user_id, card_id, delta, delta))
    db.execute("DELETE FROM inventory WHERE user_id=? AND card_id=? AND qty<=0", (user_id, card_id))


def qty_of(user_id, card_id):
    r = db.execute("SELECT qty FROM inventory WHERE user_id=? AND card_id=?", (user_id, card_id)).fetchone()
    return r["qty"] if r else 0


def get_card(card_id):
    return db.execute("SELECT * FROM cards WHERE id=?", (card_id,)).fetchone()


def get_artist(artist_id):
    return db.execute("SELECT * FROM artists WHERE id=?", (artist_id,)).fetchone()


def find_artist_by_name(name):
    return db.execute("SELECT * FROM artists WHERE name=? COLLATE NOCASE", (name,)).fetchone()


def ensure_artist(name, image=None, description=None, spotify_id=None):
    a = find_artist_by_name(name)
    if a:
        if image and not a["image"]:
            db.execute("UPDATE artists SET image=? WHERE id=?", (image, a["id"]))
            db.commit()
        return a["id"]
    cur = db.execute("INSERT INTO artists(name, image, description, spotify_id, created) "
                     "VALUES(?,?,?,?,?)", (name[:80], image, description, spotify_id, int(time.time())))
    db.commit()
    return cur.lastrowid


def title_of(c):
    if not c:
        return "<i>карточка удалена</i>"
    return f"{RARITIES[c['rarity']][1]} <b>{esc(c['title'])}</b> — {esc(c['artist'])} <i>({esc(c['album'])})</i>"


def badge(equipped):
    return COSMETICS[equipped][0] + " " if equipped in COSMETICS else ""


def who_label(user_id):
    u = get_user(user_id)
    if not u:
        return str(user_id)
    return u["name"] + (f" (@{u['username']})" if u["username"] else "")


def insert_card(title, artist, album, rarity, image, artist_id=None):
    try:
        cur = db.execute("INSERT INTO cards(title, artist, album, rarity, image, artist_id) "
                         "VALUES(?,?,?,?,?,?)",
                         (title[:80], artist[:80], album[:80], rarity, image, artist_id))
        db.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        db.rollback()
        return None


def is_admin(uid):
    return uid in ADMIN_IDS


def fmt_wait(sec):
    sec = max(0, int(sec))
    h, rem = divmod(sec, 3600)
    mnt = (rem + 59) // 60
    if mnt == 60:
        h, mnt = h + 1, 0
    return f"{h} ч {mnt} мин" if h else f"{mnt} мин"


def age_text(joined):
    days = max(0, int((time.time() - joined) // 86400)) if joined else 0
    y, rest = divmod(days, 365)
    mo, d = divmod(rest, 30)
    parts = []
    if y: parts.append(f"{y} г.")
    if mo: parts.append(f"{mo} мес.")
    if not parts: parts.append(f"{d} дн." if d else "меньше дня")
    return " ".join(parts)


def pct(a, b):
    return round(a * 100 / b) if b else 0


def today_str():
    return dt.datetime.utcnow().strftime("%Y-%m-%d")


def add_xp(uid, amount):
    db.execute("UPDATE users SET xp = xp + ? WHERE user_id=?", (amount, uid))


# ───────────────────────── Deezer ─────────────────────────

DZ_API = "https://api.deezer.com/"


class DeezerError(Exception):
    def __init__(self, msg, code=None):
        super().__init__(msg)
        self.code = code


def dz_get(path, **params):
    url = DZ_API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise DeezerError(f"HTTP {e.code}", e.code)
    except urllib.error.URLError as e:
        raise DeezerError(f"нет связи: {e.reason}")
    if isinstance(data, dict) and data.get("error"):
        err = data["error"]
        raise DeezerError(err.get("message", "ошибка Deezer"), err.get("code"))
    return data


def parse_artist_ref(text):
    m = re.search(r"deezer\.com/(?:[a-z]{2}/)?artist/(\d+)", text or "")
    if m:
        return m.group(1)
    m = re.search(r"^(\d+)$", (text or "").strip())
    if m:
        return m.group(1)
    return None


def deezer_collect(artist_id):
    art = dz_get(f"artist/{artist_id}")
    name = art.get("name") or "Unknown"
    art_img = art.get("picture_xl") or art.get("picture_big")
    albums, index = [], 0
    while index < 1000:
        res = dz_get(f"artist/{artist_id}/albums", limit=100, index=index)
        items = res.get("data") or []
        albums += items
        if len(items) < 100:
            break
        index += 100
    tracks, seen = [], set()
    for al in albums:
        album_name = al.get("title") or ""
        img = al.get("cover_xl") or al.get("cover_big") or art_img
        idx = 0
        while idx < 500:
            res = dz_get(f"album/{al['id']}/tracks", limit=100, index=idx)
            items = res.get("data") or []
            for t in items:
                title = (t.get("title") or "").strip()
                key = title.lower()
                if not key or key in seen:
                    continue
                contributors = t.get("contributors") or []
                if contributors:
                    ids = [str(c.get("id")) for c in contributors]
                    if str(artist_id) not in ids:
                        continue
                seen.add(key)
                tracks.append((title, album_name or title, img))
            if len(items) < 100:
                break
            idx += 100
    return name, art_img, tracks, len(albums)


def assign_rarities(seed_key, titles):
    order = sorted(titles, key=lambda t: hashlib.md5(f"{seed_key}|{t}".encode()).hexdigest())
    n = len(order)
    n_leg = max(1, round(n * RARITIES["legendary"][0] / 100)) if n else 0
    n_epic = round(n * RARITIES["epic"][0] / 100)
    n_rare = round(n * RARITIES["rare"][0] / 100)
    out = {}
    for i, t in enumerate(order):
        out[t] = ("legendary" if i < n_leg
                  else "epic" if i < n_leg + n_epic
                  else "rare" if i < n_leg + n_epic + n_rare
                  else "common")
    return out


def import_artist(artist_id):
    name, art_img, tracks, n_albums = deezer_collect(artist_id)
    artist_db_id = ensure_artist(name, image=art_img)
    rar = assign_rarities(artist_id, [t[0] for t in tracks])
    added = skipped = 0
    stats = {r: 0 for r in RARITIES}
    for title, album, img in tracks:
        if insert_card(title, name, album, rar[title], img, artist_db_id):
            added += 1
            stats[rar[title]] += 1
        else:
            skipped += 1
    return name, n_albums, added, skipped, stats


def cmd_spotify(m, args):
    chat_id = m["chat"]["id"]
    if not is_admin(m["from"]["id"]):
        send(chat_id, "Только для админа.")
        return
    q = args.strip()
    if not q:
        send(chat_id, IMPORT_HELP)
        return
    ref = parse_artist_ref(q)
    if ref:
        send(chat_id, "⏳ Импортирую… (может занять до минуты)")
        try:
            name, n_albums, added, skipped, stats = import_artist(ref)
        except DeezerError as e:
            send(chat_id, f"⚠️ Deezer: {esc(str(e))}")
            return
        lines = [
            f"✅ <b>{esc(name)}</b>: добавлено {added} треков из {n_albums} релизов"
            + (f" (уже были: {skipped})" if skipped else ""),
            " · ".join(f"{RARITIES[k][1]} {v}" for k, v in stats.items() if v),
        ]
        send(chat_id, "\n".join(lines))
        return
    try:
        res = dz_get("search/artist", q=q, limit=8)
    except DeezerError as e:
        send(chat_id, f"⚠️ Deezer: {esc(str(e))}")
        return
    items = res.get("data") or []
    if not items:
        send(chat_id, "Ничего не нашёл. Пришли ссылку с deezer.com")
        return
    rows = []
    for a in items[:8]:
        label = f"{a['name']} · {a.get('nb_album', '?')} альб."
        rows.append([btn(label[:60], f"dza:{a['id']}")])
    send(chat_id, "Найдено. Выбери артиста:", kb(rows))


def cb_deezer(cq, parts):
    msg = cq.get("message") or {}
    chat_id = msg.get("chat", {}).get("id", cq["from"]["id"])
    if parts[0] == "dza" and len(parts) == 2:
        answer_cb(cq["id"], "Импортирую…")
        edit_menu(cq, "⏳ Импортирую треки из Deezer…")
        try:
            name, n_albums, added, skipped, stats = import_artist(parts[1])
        except DeezerError as e:
            send(chat_id, f"⚠️ Deezer: {esc(str(e))}")
            return
        lines = [
            f"✅ <b>{esc(name)}</b>: добавлено {added} треков из {n_albums} релизов"
            + (f" (уже были: {skipped})" if skipped else ""),
            " · ".join(f"{RARITIES[k][1]} {v}" for k, v in stats.items() if v),
        ]
        send(chat_id, "\n".join(lines))


# ───────────────────────── АРТИСТЫ ─────────────────────────

def artist_text(a):
    lines = [f"🎤 <b>{esc(a['name'])}</b>", ""]
    if a["description"]:
        lines.append(esc(a["description"]))
        lines.append("")
    total = db.execute("SELECT COUNT(*) FROM cards WHERE artist_id=?", (a["id"],)).fetchone()[0]
    by_r = {}
    for r in db.execute("SELECT rarity, COUNT(*) n FROM cards WHERE artist_id=? GROUP BY rarity", (a["id"],)):
        by_r[r["rarity"]] = r["n"]
    lines.append(f"🎵 Треков: <b>{total}</b>")
    for k, v in RARITIES.items():
        if by_r.get(k):
            lines.append(f"{v[1]} {v[3]}: {by_r[k]}")
    return "\n".join(lines)


def cmd_addartist(m, args):
    chat_id = m["chat"]["id"]
    if not is_admin(m["from"]["id"]):
        send(chat_id, "Только для админа.")
        return
    p = [x.strip() for x in args.split("|", 1)]
    if not p or not p[0]:
        send(chat_id, "Формат: <code>/addartist Имя | описание</code> (можно с фото)")
        return
    name = p[0][:80]
    desc = p[1][:400] if len(p) > 1 else None
    image = photo_id_of(m)
    a = find_artist_by_name(name)
    if a:
        db.execute("UPDATE artists SET description=COALESCE(?, description), image=COALESCE(?, image) WHERE id=?",
                   (desc, image, a["id"]))
        db.commit()
        send(chat_id, f"✅ Артист обновлён: #{a['id']} {esc(name)}")
        return
    aid = ensure_artist(name, image=image, description=desc)
    send(chat_id, f"✅ Артист добавлен: #{aid} {esc(name)}")


def cmd_artists(m, args):
    chat_id = m["chat"]["id"]
    rows = db.execute(
        "SELECT a.id, a.name, (SELECT COUNT(*) FROM cards c WHERE c.artist_id=a.id) AS n "
        "FROM artists a ORDER BY a.name"
    ).fetchall()
    if not rows:
        send(chat_id, "Пока нет артистов. Добавь: <code>/addartist Имя</code> или <code>/spotify ссылка</code>")
        return
    buttons = [btn(f"{r['name'][:30]} · {r['n']}", f"ar:{r['id']}") for r in rows]
    rows_kb = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    send(chat_id, f"🎤 <b>Артисты ({len(rows)})</b>\n👇 Нажми на артиста", kb(rows_kb))


def cb_artist(cq, artist_id):
    a = get_artist(artist_id)
    msg = cq.get("message") or {}
    chat_id = msg.get("chat", {}).get("id", cq["from"]["id"])
    if not a:
        answer_cb(cq["id"], "Артист не найден.", True)
        return
    text = artist_text(a)
    markup = kb([[btn("◀ К артистам", "ar:list")]])
    if a["image"]:
        send_media(chat_id, "photo", a["image"], text, markup)
    else:
        send(chat_id, text, markup)
    answer_cb(cq["id"])


def cb_artists_list(cq):
    msg = cq.get("message") or {}
    chat_id = msg.get("chat", {}).get("id", cq["from"]["id"])
    rows = db.execute(
        "SELECT a.id, a.name, (SELECT COUNT(*) FROM cards c WHERE c.artist_id=a.id) AS n "
        "FROM artists a ORDER BY a.name"
    ).fetchall()
    if not rows:
        send(chat_id, "Пока нет артистов.")
        answer_cb(cq["id"])
        return
    buttons = [btn(f"{r['name'][:30]} · {r['n']}", f"ar:{r['id']}") for r in rows]
    rows_kb = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    edit_menu(cq, f"🎤 <b>Артисты ({len(rows)})</b>", kb(rows_kb))
    answer_cb(cq["id"])


def cmd_delartist(m, args):
    chat_id = m["chat"]["id"]
    if not is_admin(m["from"]["id"]):
        send(chat_id, "Только для админа.")
        return
    if not args.strip().isdigit():
        send(chat_id, "Формат: <code>/delartist ID</code>")
        return
    a = get_artist(int(args.strip()))
    if not a:
        send(chat_id, "Артист не найден.")
        return
    ids = [r["id"] for r in db.execute("SELECT id FROM cards WHERE artist_id=?", (a["id"],))]
    for cid in ids:
        db.execute("DELETE FROM inventory WHERE card_id=?", (cid,))
        db.execute("DELETE FROM cards WHERE id=?", (cid,))
    db.execute("DELETE FROM artists WHERE id=?", (a["id"],))
    db.commit()
    send(chat_id, f"🗑 Артист удалён: {esc(a['name'])} и {len(ids)} его треков.")


def cmd_setartistcover(m, args):
    chat_id = m["chat"]["id"]
    if not is_admin(m["from"]["id"]):
        send(chat_id, "Только для админа.")
        return
    name = args.strip()
    image = photo_id_of(m)
    if not name or not image:
        send(chat_id, "Формат: фото с подписью <code>/setartistcover Имя</code>")
        return
    a = find_artist_by_name(name)
    if not a:
        send(chat_id, "Артист не найден.")
        return
    db.execute("UPDATE artists SET image=? WHERE id=?", (image, a["id"]))
    db.commit()
    send(chat_id, f"🖼 Обложка обновлена: {esc(a['name'])}")


# ───────────────────────── РЕФЕРАЛЫ ─────────────────────────

def referral_link(uid):
    return f"https://t.me/{BOT_USERNAME}?start=ref_{uid}"


def process_referral(new_uid, ref_arg):
    if not ref_arg or not ref_arg.startswith("ref_"):
        return False, None
    try:
        referrer_id = int(ref_arg[4:])
    except ValueError:
        return False, None
    if referrer_id == new_uid:
        return False, None
    if db.execute("SELECT 1 FROM referrals WHERE invited_id=?", (new_uid,)).fetchone():
        return False, None
    ref_u = get_user(referrer_id)
    if not ref_u:
        return False, None
    db.execute("INSERT INTO referrals(invited_id, referrer_id, rewarded, created) VALUES(?,?,?,?)",
               (new_uid, referrer_id, REFERRAL_BONUS, int(time.time())))
    db.execute("UPDATE users SET coins = coins + ?, ref_count = ref_count + 1, "
               "ref_earned = ref_earned + ? WHERE user_id=?",
               (REFERRAL_BONUS, REFERRAL_BONUS, referrer_id))
    db.execute("UPDATE users SET referred_by=? WHERE user_id=?", (referrer_id, new_uid))
    db.commit()
    return True, referrer_id


def cmd_ref(m, args):
    uid, chat_id = m["from"]["id"], m["chat"]["id"]
    u = get_user(uid)
    link = referral_link(uid)
    invited = db.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id=?", (uid,)).fetchone()[0]
    earned = u["ref_earned"] or 0
    lines = [
        "🎁 <b>Рефералы</b>", "",
        f"За каждого друга по твоей ссылке — <b>+{REFERRAL_BONUS}</b> монет.",
        "", f"👥 Приглашено: <b>{invited}</b>",
        f"💰 Заработано: <b>{earned}</b>", "",
        "Твоя ссылка:", f"<code>{link}</code>",
    ]
    share_text = quote("Заходи в музыкальные карточки 🎧")
    markup = kb([
        [{"text": "📤 Поделиться", "url": f"https://t.me/share/url?url={quote(link)}&text={share_text}"}],
        [btn("🔄 Обновить", "ref:refresh")],
    ])
    send(chat_id, "\n".join(lines), markup)


# ───────────────────────── ПОДПИСКИ STARS ─────────────────────────

def is_subscribed(u):
    return bool(u and u["sub_until"] and u["sub_until"] > time.time())


def sub_multiplier(u):
    if not is_subscribed(u):
        return 1.0
    return SUB_PREMIUM_MULT if u["sub_tier"] == "premium" else SUB_BASIC_MULT


def sub_tier_label(tier):
    if tier == "premium":
        return f"💎 Premium ×{SUB_PREMIUM_MULT}"
    if tier == "basic":
        return f"💚 Basic ×{SUB_BASIC_MULT}"
    return "—"


def subscribe_text(uid):
    u = get_user(uid)
    lines = ["⭐ <b>Подписки</b>", ""]
    if is_subscribed(u):
        until = dt.datetime.fromtimestamp(u["sub_until"]).strftime("%d.%m.%Y")
        lines.append(f"🟢 Активна: <b>{sub_tier_label(u['sub_tier'])}</b> до {until}\n")
    lines.append(f"💚 <b>Basic</b> — {SUB_BASIC_STARS}⭐ / {SUB_DAYS} дней")
    lines.append(f"   Множитель: <b>×{SUB_BASIC_MULT}</b>\n")
    lines.append(f"💎 <b>Premium</b> — {SUB_PREMIUM_STARS}⭐ / {SUB_DAYS} дней")
    lines.append(f"   Множитель: <b>×{SUB_PREMIUM_MULT}</b>\n")
    lines.append("Множитель применяется к монетам за сбор.")
    return "\n".join(lines)


def cmd_subscribe(m, args):
    chat_id, uid = m["chat"]["id"], m["from"]["id"]
    markup = kb([
        [btn(f"💚 Basic · {SUB_BASIC_STARS}⭐", "sub:buy:basic")],
        [btn(f"💎 Premium · {SUB_PREMIUM_STARS}⭐", "sub:buy:premium")],
    ])
    send(chat_id, subscribe_text(uid), markup)


def send_stars_invoice(chat_id, uid, tier):
    if tier == "basic":
        stars, title, mult = SUB_BASIC_STARS, f"Basic ×{SUB_BASIC_MULT}", SUB_BASIC_MULT
    elif tier == "premium":
        stars, title, mult = SUB_PREMIUM_STARS, f"Premium ×{SUB_PREMIUM_MULT}", SUB_PREMIUM_MULT
    else:
        send(chat_id, "Неизвестный тариф.")
        return
    payload = f"sub|{tier}|{uid}|{int(time.time())}"
    try:
        tg("sendInvoice", chat_id=chat_id, title=title,
           description=f"Множитель монет ×{mult} на {SUB_DAYS} дней",
           payload=payload, currency="XTR",
           prices=[{"label": title, "amount": stars}])
    except TgError as e:
        say(f"sendInvoice fail: {e}")
        send(chat_id, "Не удалось создать счёт.")


def cb_subscribe(cq, action):
    uid = cq["from"]["id"]
    chat_id = (cq.get("message") or {}).get("chat", {}).get("id", uid)
    if action == "menu":
        markup = kb([
            [btn(f"💚 Basic · {SUB_BASIC_STARS}⭐", "sub:buy:basic")],
            [btn(f"💎 Premium · {SUB_PREMIUM_STARS}⭐", "sub:buy:premium")],
        ])
        edit_menu(cq, subscribe_text(uid), markup)
        answer_cb(cq["id"])
    elif action.startswith("buy:"):
        send_stars_invoice(chat_id, uid, action.split(":", 1)[1])
        answer_cb(cq["id"])
    else:
        answer_cb(cq["id"])


def on_pre_checkout(pcq):
    try:
        tg("answerPreCheckoutQuery", pre_checkout_query_id=pcq["id"], ok=True)
    except TgError as e:
        say(f"answerPreCheckoutQuery fail: {e}")


def on_successful_payment(m):
    sp = m["successful_payment"]
    uid = m["from"]["id"]
    chat_id = m["chat"]["id"]
    payload = sp.get("invoice_payload", "")
    charge = sp.get("telegram_payment_charge_id", "")
    amount = int(sp.get("total_amount", 0))
    if charge and db.execute("SELECT 1 FROM payments WHERE charge_id=?", (charge,)).fetchone():
        say(f"дубликат платежа {charge}")
        return
    parts = payload.split("|")
    tier = parts[1] if len(parts) >= 2 and parts[0] == "sub" else "premium"
    if tier not in ("basic", "premium"):
        tier = "premium"
    u = get_user(uid)
    now = int(time.time())
    active_now = is_subscribed(u)
    same_tier = active_now and u["sub_tier"] == tier
    new_until = (u["sub_until"] + SUB_DAYS * 86400) if same_tier else (now + SUB_DAYS * 86400)
    db.execute("UPDATE users SET sub_tier=?, sub_until=? WHERE user_id=?", (tier, new_until, uid))
    try:
        db.execute("INSERT INTO payments(charge_id, user_id, tier, stars, days, created) "
                   "VALUES(?,?,?,?,?,?)", (charge, uid, tier, amount, SUB_DAYS, now))
    except sqlite3.IntegrityError:
        pass
    db.commit()
    until_str = dt.datetime.fromtimestamp(new_until).strftime("%d.%m.%Y")
    send(chat_id, f"✅ <b>Оплата получена!</b>\n\nПодписка: <b>{sub_tier_label(tier)}</b>\n"
                  f"⭐ Оплачено: {amount} звёзд\n📅 До: <b>{until_str}</b>")
    for admin_id in ADMIN_IDS:
        try:
            send(admin_id, f"💰 <b>Новая подписка</b>\nИгрок: {esc(who_label(uid))}\n"
                           f"Тариф: {tier}\nЗвёзд: {amount}")
        except TgError:
            pass


# ───────────────────────── КАНАЛЫ ─────────────────────────

CH_SLOTS = {
    1: {"setting": "sub_channel",  "reward_setting": "ch_reward",  "table": "channel_rewards",
        "reward_default": CHANNEL_REWARD,  "label": "📢 Канал #1", "emoji": "📢"},
    2: {"setting": "sub_channel2", "reward_setting": "ch_reward2", "table": "channel2_rewards",
        "reward_default": CHANNEL2_REWARD, "label": "📣 Канал #2", "emoji": "📣"},
}


def ch_setting(slot):
    return get_setting(CH_SLOTS[slot]["setting"])


def ch_reward(slot=1):
    v = get_setting(CH_SLOTS[slot]["reward_setting"])
    try:
        return int(v) if v else CH_SLOTS[slot]["reward_default"]
    except (ValueError, TypeError):
        return CH_SLOTS[slot]["reward_default"]


def ch_url(channel):
    return channel if channel.startswith("http") else "https://t.me/" + channel.lstrip("@")


def ch_claimed(uid, slot):
    return bool(db.execute(f"SELECT 1 FROM {CH_SLOTS[slot]['table']} WHERE user_id=? AND claimed=1",
                           (uid,)).fetchone())


def ch_mark_claimed(uid, slot):
    db.execute(f"INSERT OR REPLACE INTO {CH_SLOTS[slot]['table']}(user_id, claimed, created) VALUES(?,1,?)",
               (uid, int(time.time())))


def check_channel_member(channel, uid):
    try:
        r = tg("getChatMember", chat_id=channel, user_id=uid)
    except TgError as e:
        say(f"getChatMember fail: {e}")
        return None
    status = r.get("status")
    if status in ("creator", "administrator", "member"):
        return True
    if status == "restricted":
        return bool(r.get("is_member"))
    return False


def channelsub_text(uid):
    active = [s for s in (1, 2) if ch_setting(s)]
    if not active:
        return "📢 <b>Подписка на каналы</b>\n\nРаздел не настроен.", None
    lines = ["📢 <b>Подписка на каналы</b>", ""]
    buttons = []
    for slot in active:
        cfg = CH_SLOTS[slot]
        reward = ch_reward(slot)
        got = ch_claimed(uid, slot)
        lines += ["━━━━━━━━━━━━━━━━━━", cfg["label"], f"Награда: <b>+{reward}</b> монет (один раз)"]
        lines.append("✅ награда получена" if got else "<i>Подпишись и нажми «Проверить»</i>")
        lines.append("")
        buttons.append([{"text": f"{cfg['emoji']} Перейти в #{slot}", "url": ch_url(ch_setting(slot))}])
        if got:
            buttons.append([btn(f"✅ #{slot} уже получено", "noop")])
        else:
            buttons.append([btn(f"✅ Проверить #{slot}", f"chsub:check:{slot}")])
    return "\n".join(lines), kb(buttons)


def cmd_channelsub(m, args):
    text, markup = channelsub_text(m["from"]["id"])
    send(m["chat"]["id"], text, markup)


def cb_channelsub(cq, slot):
    uid = cq["from"]["id"]
    chat_id = (cq.get("message") or {}).get("chat", {}).get("id", uid)
    channel = ch_setting(slot)
    if not channel:
        answer_cb(cq["id"], "Канал не настроен.", True)
        return
    if ch_claimed(uid, slot):
        answer_cb(cq["id"], "Уже получено 🙂", True)
        return
    ok = check_channel_member(channel, uid)
    if ok is None:
        answer_cb(cq["id"], "Не могу проверить. Бот админ канала?", True)
        return
    if not ok:
        answer_cb(cq["id"], "Ты ещё не подписан 😔", True)
        return
    reward = ch_reward(slot)
    db.execute("UPDATE users SET coins = coins + ? WHERE user_id=?", (reward, uid))
    ch_mark_claimed(uid, slot)
    db.commit()
    send(chat_id, f"🎉 <b>+{reward} монет</b> за подписку!")
    answer_cb(cq["id"], "Награда получена!")
    text, markup = channelsub_text(uid)
    edit_menu(cq, text, markup)


def _set_channel_cmd(chat_id, slot, args):
    a = (args or "").strip()
    cfg = CH_SLOTS[slot]
    if not a or a.lower() in ("off", "reset", "none"):
        set_setting(cfg["setting"], None)
        send(chat_id, f"{cfg['emoji']} {cfg['label']} отключён.")
        return
    set_setting(cfg["setting"], a)
    send(chat_id, f"✅ {cfg['label']} — <code>{esc(a)}</code>\n"
                  f"⚠️ Бот должен быть админом канала!\n"
                  f"Награда: <b>+{ch_reward(slot)}</b>")


def cmd_setchannel(m, args):
    if not is_admin(m["from"]["id"]):
        send(m["chat"]["id"], "Только для админа.")
        return
    _set_channel_cmd(m["chat"]["id"], 1, args)


def cmd_setchannel2(m, args):
    if not is_admin(m["from"]["id"]):
        send(m["chat"]["id"], "Только для админа.")
        return
    _set_channel_cmd(m["chat"]["id"], 2, args)


def _set_chreward_cmd(chat_id, slot, args):
    a = (args or "").strip()
    if not a.isdigit() or int(a) <= 0:
        send(chat_id, f"Формат: <code>/setchreward{'2' if slot == 2 else ''} 2000</code>")
        return
    set_setting(CH_SLOTS[slot]["reward_setting"], a)
    send(chat_id, f"✅ Награда за {CH_SLOTS[slot]['label']}: <b>+{a}</b>")


def cmd_setchreward(m, args):
    if not is_admin(m["from"]["id"]):
        send(m["chat"]["id"], "Только для админа.")
        return
    _set_chreward_cmd(m["chat"]["id"], 1, args)


def cmd_setchreward2(m, args):
    if not is_admin(m["from"]["id"]):
        send(m["chat"]["id"], "Только для админа.")
        return
    _set_chreward_cmd(m["chat"]["id"], 2, args)


# ───────────────────────── ДОСТИЖЕНИЯ ─────────────────────────

def user_stats(uid):
    total_game = db.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
    uniq = db.execute("SELECT COUNT(*) FROM inventory WHERE user_id=? AND qty>0", (uid,)).fetchone()[0]
    owned = db.execute("SELECT COALESCE(SUM(qty),0) FROM inventory WHERE user_id=?", (uid,)).fetchone()[0]
    by_rarity = {}
    for k in RARITIES:
        by_rarity[k] = db.execute(
            "SELECT COUNT(*) FROM inventory i JOIN cards c ON c.id=i.card_id "
            "WHERE i.user_id=? AND i.qty>0 AND c.rarity=?", (uid, k)).fetchone()[0]
    trades = db.execute("SELECT COUNT(*) FROM trades WHERE status='accepted' AND (from_id=? OR to_id=?)",
                        (uid, uid)).fetchone()[0]
    u = get_user(uid)
    return {"total_game": total_game, "uniq": uniq, "owned": owned,
            "by_rarity": by_rarity, "trades": trades, "streak": u["open_streak"] if u else 0}


def check_achievements(uid):
    s = user_stats(uid)
    have = {r["code"] for r in db.execute("SELECT code FROM achievements WHERE user_id=?", (uid,))}
    earned = []

    def give(code):
        if code not in have:
            db.execute("INSERT INTO achievements(user_id, code, got) VALUES(?,?,?)",
                       (uid, code, int(time.time())))
            earned.append(code)

    if s["uniq"] >= 1:    give("first")
    if s["uniq"] >= 10:   give("ten")
    if s["uniq"] >= 50:   give("fifty")
    if s["total_game"] and s["uniq"] * 2 >= s["total_game"]: give("half")
    if s["total_game"] and s["uniq"] >= s["total_game"]:     give("full")
    if s["by_rarity"].get("common", 0)    >= 10: give("c10")
    if s["by_rarity"].get("rare", 0)      >= 10: give("r10")
    if s["by_rarity"].get("epic", 0)      >= 5:  give("e5")
    if s["by_rarity"].get("legendary", 0) >= 1:  give("l1")
    if s["trades"] >= 1:  give("trade1")
    if s["streak"] >= 7:  give("fire7")
    if s["owned"]  >= 100: give("rich100")
    db.commit()
    return earned


def notify_achievements(chat_id, earned):
    for code in earned:
        e = ACHIEVEMENTS.get(code)
        if e:
            send(chat_id, f"🏅 <b>Новое достижение!</b>\n{e[0]} {e[1]} — {e[2]}")
    if earned:
        notify_quests(chat_id, progress_quest(chat_id, "ach1", 1))


def cmd_achievements(m, args):
    uid, chat_id = m["from"]["id"], m["chat"]["id"]
    rows = {r["code"]: r["got"] for r in db.execute(
        "SELECT code, got FROM achievements WHERE user_id=?", (uid,))}
    s = user_stats(uid)
    lines = [f"🏅 <b>Достижения</b>: {len(rows)}/{len(ACHIEVEMENTS)}\n"]
    for code, (emoji, name, desc) in ACHIEVEMENTS.items():
        if code in rows:
            when = dt.datetime.fromtimestamp(rows[code]).strftime("%d.%m.%y")
            lines.append(f"✅ {emoji} <b>{name}</b> — <i>{when}</i>")
        else:
            lines.append(f"🔒 {emoji} <b>{name}</b> — <i>{desc}</i>")
    lines += ["", f"📊 Уникальных: {s['uniq']}/{s['total_game']}",
              f"🎁 Экземпляров: {s['owned']}", f"🔥 Серия: {s['streak']} дн."]
    send_long(chat_id, lines)


# ───────────────────────── ТИТУЛЫ ─────────────────────────

def compute_titles(uid):
    s = user_stats(uid)
    have = set()
    ach = {r["code"] for r in db.execute("SELECT code FROM achievements WHERE user_id=?", (uid,))}
    if s["uniq"] >= 1:    have.add("newbie")
    if s["uniq"] >= 10:   have.add("meloman")
    if s["uniq"] >= 25:   have.add("collector")
    if s["uniq"] >= 50:   have.add("master")
    if s["total_game"] and s["uniq"] >= s["total_game"]: have.add("legend")
    if s["streak"] >= 7:  have.add("devoted")
    if s["trades"] >= 5:  have.add("trader")
    if s["owned"]  >= 100: have.add("rich")
    if len(ach) >= 5:     have.add("chosen")
    return have


def best_title(uid):
    have = compute_titles(uid)
    for code in TITLE_ORDER:
        if code in have:
            return code
    return None


def current_title(uid):
    u = get_user(uid)
    chosen = u["title"] if u else None
    have = compute_titles(uid)
    if chosen and chosen in have:
        return chosen
    return best_title(uid)


def title_str(uid):
    code = current_title(uid)
    if not code:
        return ""
    e, name, _ = TITLES[code]
    return f"{e} <b>{name}</b>"


def cmd_titles(m, args):
    uid, chat_id = m["from"]["id"], m["chat"]["id"]
    have = compute_titles(uid)
    cur = current_title(uid)
    lines = [f"🏷 <b>Титулы</b>: {len(have)}/{len(TITLES)}\n"]
    buttons = []
    for code in TITLE_ORDER:
        e, name, cond = TITLES[code]
        if code in have:
            mark = "✅" if code == cur else "🔓"
            lines.append(f"{mark} {e} <b>{name}</b>")
            buttons.append(btn(f"{e} {name}", f"ti:{code}"))
        else:
            lines.append(f"🔒 {e} <b>{name}</b> — <i>{cond}</i>")
    markup = kb([buttons[i:i + 2] for i in range(0, len(buttons), 2)])
    lines.append("")
    lines.append("Нажми титул, чтобы сделать его активным.")
    send_long(chat_id, lines, markup)


def cb_title(cq, code):
    uid = cq["from"]["id"]
    have = compute_titles(uid)
    if code not in have or code not in TITLES:
        answer_cb(cq["id"], "Титул ещё не открыт.", True)
        return
    db.execute("UPDATE users SET title=? WHERE user_id=?", (code, uid))
    db.commit()
    e, name, _ = TITLES[code]
    answer_cb(cq["id"], f"Активен: {e} {name}", True)


# ───────────────────────── КВЕСТЫ ─────────────────────────

def ensure_quests(uid):
    day = today_str()
    rows = db.execute("SELECT code FROM quests WHERE user_id=? AND day=?", (uid, day)).fetchall()
    if rows:
        return
    picks = random.sample(QUEST_POOL, 3)
    for code, emoji, desc, target, xp, bonus in picks:
        db.execute("INSERT OR IGNORE INTO quests(user_id, day, code, progress, target, xp, done) "
                   "VALUES(?,?,?,0,?,?,0)", (uid, day, code, target, xp))
    db.commit()


def quest_info(code):
    for c, e, d, t, xp, b in QUEST_POOL:
        if c == code:
            return {"emoji": e, "desc": d, "target": t, "xp": xp, "bonus": b}
    return None


def progress_quest(uid, code, amount=1):
    day = today_str()
    ensure_quests(uid)
    row = db.execute("SELECT * FROM quests WHERE user_id=? AND day=? AND code=?",
                     (uid, day, code)).fetchone()
    if not row or row["done"]:
        return []
    new_progress = row["progress"] + amount
    done = 1 if new_progress >= row["target"] else 0
    db.execute("UPDATE quests SET progress=?, done=? WHERE user_id=? AND day=? AND code=?",
               (new_progress, done, uid, day, code))
    if done:
        add_xp(uid, row["xp"])
    db.commit()
    if not done:
        return []
    info = quest_info(code)
    if info and info["bonus"] == "card":
        pool = db.execute("SELECT * FROM cards").fetchall()
        if pool:
            card = random.choice(pool)
            add_card(uid, card["id"], 1)
            db.commit()
    return [(code, info)]


def notify_quests(chat_id, completed):
    for code, info in completed:
        if not info:
            continue
        extra = " + 🎴 бонусная карточка!" if info["bonus"] == "card" else ""
        send(chat_id, f"🎯 <b>Квест выполнен!</b>\n{info['emoji']} {info['desc']} — "
                      f"+{info['xp']} XP{extra}")


def cmd_quests(m, args):
    uid, chat_id = m["from"]["id"], m["chat"]["id"]
    ensure_quests(uid)
    day = today_str()
    rows = db.execute("SELECT * FROM quests WHERE user_id=? AND day=? ORDER BY code",
                      (uid, day)).fetchall()
    xp = db.execute("SELECT xp FROM users WHERE user_id=?", (uid,)).fetchone()["xp"]
    lines = [f"🎯 <b>Ежедневные квесты</b>\n", f"⭐ XP: <code>{xp}</code>\n"]
    for r in rows:
        info = quest_info(r["code"])
        if not info:
            continue
        done = "✅" if r["done"] else "⏳"
        bd = min(r["progress"], r["target"])
        bar = "▰" * bd + "▱" * (r["target"] - bd)
        lines.append(f"{done} {info['emoji']} <b>{info['desc']}</b>")
        lines.append(f"    <code>{bar}</code> {bd}/{r['target']}  +{r['xp']} XP")
    send_long(chat_id, lines)


# ───────────────────────── ДРУЗЬЯ ─────────────────────────

def cmd_friends(m, args):
    uid, chat_id = m["from"]["id"], m["chat"]["id"]
    friends = db.execute("SELECT friend_id FROM friends WHERE user_id=? AND status='accepted'", (uid,)).fetchall()
    incoming = db.execute("SELECT user_id FROM friends WHERE friend_id=? AND status='pending'", (uid,)).fetchall()
    outgoing = db.execute("SELECT friend_id FROM friends WHERE user_id=? AND status='pending'", (uid,)).fetchall()
    lines = ["👥 <b>Друзья</b>\n"]
    if friends:
        lines.append("<b>Мои друзья:</b>")
        for r in friends:
            lines.append(f"• {esc(who_label(r['friend_id']))}")
    else:
        lines.append("У тебя пока нет друзей.")
    lines.append("")
    if incoming:
        lines.append("<b>Входящие:</b>")
        for r in incoming:
            lines.append(f"• {esc(who_label(r['user_id']))}")
        lines.append("")
    if outgoing:
        lines.append("<b>Исходящие:</b>")
        for r in outgoing:
            lines.append(f"• ⏳ {esc(who_label(r['friend_id']))}")
        lines.append("")
    lines.append("Добавить: <code>/addfriend @ник</code>")
    lines.append("Удалить: <code>/delfriend @ник</code>")
    send_long(chat_id, lines)


def cmd_addfriend(m, args):
    uid, chat_id = m["from"]["id"], m["chat"]["id"]
    arg = (args or "").strip()
    if not arg.startswith("@"):
        send(chat_id, "Формат: <code>/addfriend @ник</code>")
        return
    target = db.execute("SELECT * FROM users WHERE username=?", (arg[1:].lower(),)).fetchone()
    if not target:
        send(chat_id, "Не найден.")
        return
    if target["user_id"] == uid:
        send(chat_id, "Сам с собой 🙂")
        return
    rel = db.execute("SELECT status FROM friends WHERE user_id=? AND friend_id=?",
                     (uid, target["user_id"])).fetchone()
    if rel:
        send(chat_id, "Уже друзья." if rel["status"] == "accepted" else "Заявка уже отправлена.")
        return
    opp = db.execute("SELECT status FROM friends WHERE user_id=? AND friend_id=?",
                     (target["user_id"], uid)).fetchone()
    if opp and opp["status"] == "pending":
        db.execute("UPDATE friends SET status='accepted' WHERE user_id=? AND friend_id=?",
                   (target["user_id"], uid))
        db.execute("INSERT INTO friends(user_id, friend_id, status, created) VALUES(?,?,?,?)",
                   (uid, target["user_id"], "accepted", int(time.time())))
        db.commit()
        send(chat_id, f"✅ Теперь вы друзья с {esc(who_label(target['user_id']))}!")
        try:
            send(target["user_id"], f"✅ {esc(who_label(uid))} принял заявку!")
        except TgError:
            pass
        return
    db.execute("INSERT INTO friends(user_id, friend_id, status, created) VALUES(?,?,?,?)",
               (uid, target["user_id"], "pending", int(time.time())))
    db.commit()
    markup = kb([[btn("✅ Принять", f"f:y:{uid}"), btn("❌ Отклонить", f"f:n:{uid}")]])
    try:
        send(target["user_id"], f"👥 <b>{esc(who_label(uid))}</b> хочет добавить тебя в друзья.", markup)
    except TgError:
        send(chat_id, "Игрок не запускал бота.")
        return
    send(chat_id, "📨 Заявка отправлена.")


def cmd_delfriend(m, args):
    uid, chat_id = m["from"]["id"], m["chat"]["id"]
    arg = (args or "").strip()
    if not arg.startswith("@"):
        send(chat_id, "Формат: <code>/delfriend @ник</code>")
        return
    target = db.execute("SELECT * FROM users WHERE username=?", (arg[1:].lower(),)).fetchone()
    if not target:
        send(chat_id, "Не найден.")
        return
    db.execute("DELETE FROM friends WHERE user_id=? AND friend_id=?", (uid, target["user_id"]))
    db.execute("DELETE FROM friends WHERE user_id=? AND friend_id=?", (target["user_id"], uid))
    db.commit()
    send(chat_id, f"🗑 {esc(who_label(target['user_id']))} удалён из друзей.")


def cb_friend(cq, action, other_id):
    uid = cq["from"]["id"]
    if uid == other_id:
        answer_cb(cq["id"], "Это твоя заявка.", True)
        return
    if action == "a":
        msg = cq.get("message") or {}
        if msg.get("message_id") and msg.get("chat"):
            clear_markup(msg["chat"]["id"], msg["message_id"])
        opp = db.execute("SELECT status FROM friends WHERE user_id=? AND friend_id=?",
                         (other_id, uid)).fetchone()
        if opp and opp["status"] == "pending":
            db.execute("UPDATE friends SET status='accepted' WHERE user_id=? AND friend_id=?",
                       (other_id, uid))
            db.execute("INSERT INTO friends(user_id, friend_id, status, created) VALUES(?,?,?,?)",
                       (uid, other_id, "accepted", int(time.time())))
            db.commit()
            send(msg["chat"]["id"], f"✅ Теперь вы друзья с {esc(who_label(other_id))}!")
            try:
                send(other_id, f"✅ {esc(who_label(uid))} принял заявку!")
            except TgError:
                pass
            answer_cb(cq["id"])
            return
        exists = db.execute("SELECT status FROM friends WHERE user_id=? AND friend_id=?",
                            (uid, other_id)).fetchone()
        if exists and exists["status"] == "accepted":
            answer_cb(cq["id"], "Вы уже друзья.", True)
            return
        if not exists:
            db.execute("INSERT INTO friends(user_id, friend_id, status, created) VALUES(?,?,?,?)",
                       (uid, other_id, "pending", int(time.time())))
            db.commit()
        markup = kb([[btn("✅ Принять", f"f:y:{uid}"), btn("❌ Отклонить", f"f:n:{uid}")]])
        try:
            send(other_id, f"👥 <b>{esc(who_label(uid))}</b> хочет добавить тебя в друзья.", markup)
        except TgError:
            pass
        answer_cb(cq["id"], "Заявка отправлена")
        return
    rel = db.execute("SELECT status FROM friends WHERE user_id=? AND friend_id=?",
                     (other_id, uid)).fetchone()
    if not rel or rel["status"] != "pending":
        answer_cb(cq["id"], "Уже обработано.", True)
        return
    msg = cq.get("message") or {}
    chat_id, mid = msg.get("chat", {}).get("id"), msg.get("message_id")
    if action == "y":
        db.execute("UPDATE friends SET status='accepted' WHERE user_id=? AND friend_id=?",
                   (other_id, uid))
        ins = db.execute("SELECT 1 FROM friends WHERE user_id=? AND friend_id=?",
                         (uid, other_id)).fetchone()
        if not ins:
            db.execute("INSERT INTO friends(user_id, friend_id, status, created) VALUES(?,?,?,?)",
                       (uid, other_id, "accepted", int(time.time())))
        db.commit()
        if chat_id and mid:
            edit_text(chat_id, mid, f"✅ Теперь вы друзья с {esc(who_label(other_id))}.")
        try:
            send(other_id, f"✅ {esc(who_label(uid))} принял заявку!")
        except TgError:
            pass
    else:
        db.execute("DELETE FROM friends WHERE user_id=? AND friend_id=?", (other_id, uid))
        db.commit()
        if chat_id and mid:
            edit_text(chat_id, mid, f"❌ Заявка от {esc(who_label(other_id))} отклонена.")
        try:
            send(other_id, f"❌ {esc(who_label(uid))} отклонил заявку.")
        except TgError:
            pass
    answer_cb(cq["id"])


# ───────────────────────── РАМКИ / ПРОФИЛЬ ─────────────────────────

def frame_for(uid):
    u = db.execute("SELECT avatar_card FROM users WHERE user_id=?", (uid,)).fetchone()
    if not u or not u["avatar_card"]:
        return ""
    card = get_card(u["avatar_card"])
    if not card:
        return ""
    s = user_stats(uid)
    ach_count = db.execute("SELECT COUNT(*) FROM achievements WHERE user_id=?", (uid,)).fetchone()[0]
    if (s["total_game"] and s["uniq"] >= s["total_game"]
            and s["by_rarity"].get("legendary", 0) >= 2):
        return SPECIAL_FRAMES["rainbow"]
    if s["total_game"] and s["uniq"] >= s["total_game"]:
        return SPECIAL_FRAMES["diamond"]
    if s["streak"] >= 7:
        return SPECIAL_FRAMES["fire"]
    if card["rarity"] == "legendary" and ach_count >= 3:
        return SPECIAL_FRAMES["crown"]
    return FRAMES.get(card["rarity"], "")


def pity_left(count, threshold):
    return max(1, threshold - count)


def claim_info(last_claim, now=None):
    now = time.time() if now is None else now
    if not last_claim:
        return CLAIM_AMOUNT, 0, False
    el = now - last_claim
    if el < CLAIM_SECONDS:
        return 0, CLAIM_SECONDS - el, False
    maxed = el >= CLAIM_MAX_SECONDS
    el = min(el, CLAIM_MAX_SECONDS)
    steps = int((el - CLAIM_SECONDS) // STEP_SECONDS)
    nxt = 0 if maxed else STEP_SECONDS - ((el - CLAIM_SECONDS) % STEP_SECONDS)
    return CLAIM_AMOUNT + steps * CLAIM_BONUS, nxt, maxed


def max_claim_amount():
    return CLAIM_AMOUNT + CLAIM_BONUS * ((CLAIM_MAX_SECONDS - CLAIM_SECONDS) // STEP_SECONDS)


def profile_text(uid):
    u = get_user(uid)
    total_game = db.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
    uniq = db.execute("SELECT COUNT(*) FROM inventory WHERE user_id=? AND qty>0", (uid,)).fetchone()[0]
    owned_all = db.execute("SELECT COALESCE(SUM(qty),0) FROM inventory WHERE user_id=?", (uid,)).fetchone()[0]
    trades = db.execute("SELECT COUNT(*) FROM trades WHERE status='accepted' AND (from_id=? OR to_id=?)",
                        (uid, uid)).fetchone()[0]
    ach_count = db.execute("SELECT COUNT(*) FROM achievements WHERE user_id=?", (uid,)).fetchone()[0]
    friends_count = db.execute("SELECT COUNT(*) FROM friends WHERE user_id=? AND status='accepted'",
                               (uid,)).fetchone()[0]
    t_str = title_str(uid)
    xp = u["xp"] or 0
    fr = frame_for(uid)
    lines = [f"👤 <b>{badge(u['equipped'])}{esc(u['name'])}</b>, профиль:",
             f"🆔 <code>{uid}</code>"]
    if t_str:
        lines.append(f"🏷 Титул: {t_str}")
    if u["avatar_card"]:
        ac = get_card(u["avatar_card"])
        if ac:
            lines.append(f"{fr} Аватар: {title_of(ac)}")
    lines += ["",
              f"💰 Монеты: <b>{u['coins']}</b>",
              f"⭐ XP: <code>{xp}</code>",
              f"🏅 Достижений: <code>{ach_count}/{len(ACHIEVEMENTS)}</code>",
              f"👥 Друзей: <code>{friends_count}</code>",
              "",
              f"🎵 Коллекция: <b>{uniq}/{total_game}</b> ({pct(uniq, total_game)}%)",
              f"📦 С дубликатами: {owned_all}", ""]
    for k in RARITIES:
        tot = db.execute("SELECT COUNT(*) FROM cards WHERE rarity=?", (k,)).fetchone()[0]
        own = db.execute("SELECT COUNT(*) FROM inventory i JOIN cards c ON c.id=i.card_id "
                         "WHERE i.user_id=? AND i.qty>0 AND c.rarity=?", (uid, k)).fetchone()[0]
        lines.append(f"{RARITIES[k][1]} {RARITIES[k][3]}: {own}/{tot} ({pct(own, tot)}%)")
    lines.append("")
    if is_subscribed(u):
        until_str = dt.datetime.fromtimestamp(u["sub_until"]).strftime("%d.%m.%Y")
        lines.append(f"⭐ Подписка: {sub_tier_label(u['sub_tier'])} до {until_str}")
    for slot in (1, 2):
        if ch_setting(slot):
            got = ch_claimed(uid, slot)
            lines.append(f"{CH_SLOTS[slot]['emoji']} {CH_SLOTS[slot]['label']}: "
                         f"{'✅ награда' if got else 'не подписан'}")
    lines += [f"🎯 Гарант: 🟡 через {pity_left(u['pity_leg'], PITY_LEGENDARY)} · "
              f"🟣 через {pity_left(u['pity_epic'], PITY_EPIC)}",
              f"🎁 Друзей: <b>{u['ref_count'] or 0}</b>",
              f"🕰 В игре: {age_text(u['joined'])}",
              f"🤝 Обменов: {trades}"]
    return "\n".join(lines)


# ───────────────────────── КЛАВИАТУРЫ ─────────────────────────

def reply_kb(rows):
    return {"keyboard": [[{"text": t} for t in row] for row in rows],
            "resize_keyboard": True, "is_persistent": True}


CLAIM_LABEL = "💰 Забрать"
KEYBOARDS = {
    "main": [
        ["🎴 Карточки", "🎤 Артисты"],
        ["💰 Монеты", "🏆 Топ"],
        ["⭐ Подписка", "📢 Канал"],
        ["🎁 Рефералы", "👤 Профиль"],
        ["🎯 Квесты", "🏅 Достижения"],
        ["🏷 Титулы", "👥 Друзья"],
        ["❓ Помощь"],
    ],
    "cards": [["🎲 Открыть", "📚 Коллекция"], ["🔁 Обмен", "💡 Предложить"], ["◀ Назад"]],
    "open": [["🎲 Крутить"], ["◀ Назад"]],
    "shop": [["🛍 Магазин", "🚫 Снять значок"], ["◀ Назад"]],
    "coins": [[CLAIM_LABEL, "💳 Баланс"], ["◀ Назад"]],
    "admin": [["➕ Трек", "📋 Заявки"], ["🗂 Карточки", "💿 Помощь"],
              ["🎧 Deezer", "🎤 Артисты"], ["◀ Назад"]],
}
LABELS = {
    "🎴 Карточки": "g_cards", "💄 Косметика": "g_shop", "💰 Монеты": "g_coins",
    "🏆 Топ": "top", "👤 Профиль": "home", "❓ Помощь": "help", "🛠 Админ": "g_admin",
    "⭐ Подписка": "sub_menu", "📢 Канал": "chsub_menu", "🎁 Рефералы": "ref",
    "🎤 Артисты": "artists", "🎯 Квесты": "quests", "🏅 Достижения": "ach",
    "🏷 Титулы": "titles", "👥 Друзья": "friends",
    "◀ Назад": "back",
    "🎲 Открыть": "g_open", "📚 Коллекция": "coll", "🔁 Обмен": "trade", "💡 Предложить": "suggest",
    "🎲 Крутить": "open:random",
    "🛍 Магазин": "shop", "🚫 Снять значок": "unequip",
    CLAIM_LABEL: "claim", "💳 Баланс": "balance",
    "➕ Трек": "adm_add", "📋 Заявки": "adm_queue", "🗂 Карточки": "adm_list",
    "💿 Помощь": "adm_album", "🎧 Deezer": "adm_spotify",
}
ADMIN_ACTIONS = {"g_admin", "adm_add", "adm_queue", "adm_list", "adm_album", "adm_spotify"}
NAV = {}


def keyboard(uid, name):
    rows = [list(r) for r in KEYBOARDS[name]]
    if name == "main" and is_admin(uid):
        rows.append(["🛠 Админ"])
    return reply_kb(rows)


def goto(chat_id, uid, name, text, private=True):
    NAV[uid] = name
    send(chat_id, text, keyboard(uid, name) if private else None)


def send_home(chat_id, uid, private=True):
    NAV[uid] = "main"
    text = profile_text(uid)
    markup = keyboard(uid, "main") if private else None
    media = get_setting("welcome_media")
    if media:
        kind, _, fid = media.partition(":")
        send_media(chat_id, kind, fid, text, markup)
    else:
        send(chat_id, text, markup)


def cards_text(uid):
    u = get_user(uid)
    return (f"🎴 <b>Карточки</b>\n\nОткрытие: <b>{OPEN_COST}</b> монет\n"
            f"💰 Баланс: <b>{u['coins']}</b>")


def open_text(uid):
    u = get_user(uid)
    return (f"🎲 <b>Крутить?</b>\nЦена: {OPEN_COST} · баланс: {u['coins']}\n"
            f"🎯 Гарант: 🟡 через {pity_left(u['pity_leg'], PITY_LEGENDARY)} · "
            f"🟣 через {pity_left(u['pity_epic'], PITY_EPIC)}")


def coins_text(uid):
    u = get_user(uid)
    mult = sub_multiplier(u)
    base_amount = int(CLAIM_AMOUNT * mult)
    bonus = int(CLAIM_BONUS * mult)
    max_amount = int(max_claim_amount() * mult)
    if not u["last_claim"]:
        return (f"💰 <b>Монеты</b>\n\nБаланс: <b>{u['coins']}</b>\n\n"
                f"✅ Первый сбор: <b>{base_amount}</b> — забирай!\n\n"
                f"Далее +{bonus}/час, максимум {max_amount} за {CLAIM_MAX_SECONDS // 3600} ч.")
    el = time.time() - u["last_claim"]
    if el < CLAIM_SECONDS:
        return (f"💰 <b>Монеты</b>\n\nБаланс: <b>{u['coins']}</b>\n\n"
                f"⏳ Первые {base_amount} через {fmt_wait(CLAIM_SECONDS - el)}\n\n"
                f"Далее +{bonus}/час, максимум {max_amount} за {CLAIM_MAX_SECONDS // 3600} ч.")
    amount, nxt, maxed = claim_info(u["last_claim"])
    tail = (f"Максимум: {max_amount} за {CLAIM_MAX_SECONDS // 3600} ч.\n"
            f"Начисление: +{bonus}/час.\n\nОткрытие: {OPEN_COST}")
    if maxed:
        return (f"💰 <b>Монеты</b>\n\nБаланс: <b>{u['coins']}</b>\n\n"
                f"✅ Накоплено: <b>{amount}</b> (макс)\n🔒 Забери, чтобы копилось снова\n\n{tail}")
    return (f"💰 <b>Монеты</b>\n\nБаланс: <b>{u['coins']}</b>\n\n"
            f"✅ Накоплено: <b>{amount}</b>\n⏳ Ещё +{bonus} через {fmt_wait(nxt)}\n\n{tail}")


def shop_menu(uid):
    u = get_user(uid)
    owned = {r["item"] for r in db.execute("SELECT item FROM owned_cosmetics WHERE user_id=?", (uid,))}
    lines = ["💄 <b>Косметика</b>", "Значок рядом с именем.",
             f"💰 Баланс: <b>{u['coins']}</b>", ""]
    buttons = []
    for k, (emoji, name, price) in COSMETICS.items():
        if u["equipped"] == k:
            label = f"🟢{emoji}"
        elif k in owned:
            label = f"✅{emoji}"
        else:
            label = f"{emoji} {price}"
        lines.append(f"{emoji} {name} — {price}")
        buttons.append(btn(label, f"cs:{k}"))
    rows = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
    rows.append([btn("🚫 Снять значок", "cs:off")])
    return "\n".join(lines), kb(rows)


HELP = (
    "🎧 <b>Музыкальные карточки</b>\n\n"
    "🎴 Карточки · 📚 Коллекция · 🎲 Крутить\n"
    "🎤 Артисты · 🏆 Топ · 👤 Профиль\n"
    "💰 Монеты · ⭐ Подписка · 📢 Каналы\n"
    "🎁 Рефералы · 🎯 Квесты · 🏅 Достижения\n"
    "🏷 Титулы · 👥 Друзья\n\n"
    "/claim · /open · /cards · /artists · /ref\n"
    "/trade @ник мой_id чужой_id · /user @ник · /suggest\n\n"
    "🎧 Импорт треков: <code>/spotify ссылка_с_deezer.com</code>"
)


# ───────────────────────── МОНЕТЫ ─────────────────────────

def do_claim(uid):
    u = get_user(uid)
    amount, nxt, _maxed = claim_info(u["last_claim"])
    if amount <= 0:
        return False, 0, u["coins"], nxt
    db.execute("UPDATE users SET coins = coins + ?, last_claim = ? WHERE user_id = ?",
               (amount, int(time.time()), uid))
    db.commit()
    return True, amount, u["coins"] + amount, 0


def cmd_claim(m, args):
    ok, amount, coins, wait = do_claim(m["from"]["id"])
    if ok:
        send(m["chat"]["id"], f"✅ +{amount} монет! Баланс: <b>{coins}</b>")
    else:
        send(m["chat"]["id"], f"⏳ Подожди {fmt_wait(wait)}. Баланс: {coins}")


# ───────────────────────── ОТКРЫТИЕ ─────────────────────────

def do_open(uid, chat_id):
    u = get_user(uid)
    if u["coins"] < OPEN_COST:
        send(chat_id, f"💸 Нужно {OPEN_COST}, у тебя {u['coins']}.")
        return
    rars = [r[0] for r in db.execute("SELECT DISTINCT rarity FROM cards")]
    if not rars:
        send(chat_id, "Нет карточек.")
        return
    pl, pe = u["pity_leg"], u["pity_epic"]
    forced = None
    if pl >= PITY_LEGENDARY - 1 and "legendary" in rars:
        forced = "legendary"
    elif pe >= PITY_EPIC - 1 and "epic" in rars:
        forced = "epic"
    rarity = forced or random.choices(rars, weights=[RARITIES[r][0] for r in rars])[0]
    if rarity == "legendary":
        pl, pe = 0, 0
    elif rarity == "epic":
        pl, pe = pl + 1, 0
    else:
        pl, pe = pl + 1, pe + 1
    card = db.execute("SELECT * FROM cards WHERE rarity=? ORDER BY RANDOM() LIMIT 1", (rarity,)).fetchone()
    db.execute("UPDATE users SET coins = coins - ?, pity_leg = ?, pity_epic = ? WHERE user_id=?",
               (OPEN_COST, pl, pe, uid))
    add_card(uid, card["id"], 1)
    db.commit()
    qty = qty_of(uid, card["id"])
    balance = u["coins"] - OPEN_COST
    r = RARITIES[card["rarity"]]
    note = "🆕 Новая!" if qty == 1 else f"Дубликат ×{qty}"
    caption = (f"{r[1]} <b>{r[2]}</b>\n"
               f"🎵 {esc(card['title'])}\n👤 {esc(card['artist'])}\n💿 {esc(card['album'])}\n"
               f"ID: <code>{card['id']}</code>\n{note}\n"
               + ("🎯 Сработал гарант!\n" if forced else "")
               + f"💰 Баланс: {balance}\n"
               f"🎯 🟡 через {pity_left(pl, PITY_LEGENDARY)} · 🟣 через {pity_left(pe, PITY_EPIC)}")
    res = send_media(chat_id, "photo", card["image"], caption)
    img = card["image"]
    if img and img.startswith("http") and isinstance(res, dict) and res.get("photo"):
        db.execute("UPDATE cards SET image=? WHERE image=?", (res["photo"][-1]["file_id"], img))
        db.commit()
    q1 = progress_quest(uid, "open3", 1)
    q2 = progress_quest(uid, "open5", 1)
    q3 = progress_quest(uid, "qty5", 1)
    notify_quests(chat_id, q1 + q2 + q3)
    notify_achievements(chat_id, check_achievements(uid))


def cmd_open(m, args):
    uid, chat_id = m["from"]["id"], m["chat"]["id"]
    goto(chat_id, uid, "open", open_text(uid), m["chat"].get("type") == "private")


# ───────────────────────── КОЛЛЕКЦИЯ ─────────────────────────

CARD_CTX = {}


def cards_page(uid, rar, page):
    CARD_CTX[uid] = (rar, page)
    where, args = "i.user_id=?", [uid]
    if rar != "all":
        where += " AND c.rarity=?"
        args.append(rar)
    base = f"FROM inventory i JOIN cards c ON c.id=i.card_id WHERE {where}"
    n = db.execute(f"SELECT COUNT(*) {base}", args).fetchone()[0]
    pages = max(1, (n + PAGE - 1) // PAGE)
    page = min(max(page, 0), pages - 1)
    rows = db.execute(
        f"SELECT c.id, c.title, c.artist, c.album, c.rarity, i.qty {base} "
        f"ORDER BY {RARITY_ORDER_SQL.format(c='c.rarity')}, c.artist, c.title LIMIT ? OFFSET ?",
        args + [PAGE, page * PAGE],
    ).fetchall()
    uniq, qty = db.execute("SELECT COUNT(*), COALESCE(SUM(qty),0) FROM inventory WHERE user_id=?",
                           (uid,)).fetchone()
    flt = f"\nФильтр: {RARITIES[rar][1]} {RARITIES[rar][3]}" if rar != "all" else ""
    head = f"📚 <b>Коллекция</b>: {uniq} треков ({qty} шт.){flt}\n\n👇 Нажми на карточку"
    lines = [head, ""]
    if not rows:
        lines.append("Пусто.")

    def go(rr, p):
        return f"cp:{rr}:{p}"

    card_buttons = []
    for r in rows:
        e = RARITIES[r["rarity"]][1]
        label = f"{e} {r['title']} — {r['artist']} ×{r['qty']}"
        card_buttons.append([btn(label[:60], f"vc:{r['id']}")])
    nav = [btn("◀", go(rar, page - 1) if page > 0 else "noop"),
           btn(f"{page + 1}/{pages}", "noop"),
           btn("▶", go(rar, page + 1) if page < pages - 1 else "noop")]
    rar_row = [btn("Все", go("all", 0))] + [btn(v[1], go(k, 0)) for k, v in RARITIES.items()]
    return "\n".join(lines), kb([nav] + card_buttons + [rar_row])


def cmd_cards(m, args):
    text, markup = cards_page(m["from"]["id"], "all", 0)
    send(m["chat"]["id"], text, markup)


def cb_cards_page(cq, parts):
    if len(parts) != 3 or not parts[2].lstrip("-").isdigit():
        answer_cb(cq["id"])
        return
    rar, page = parts[1], int(parts[2])
    if rar != "all" and rar not in RARITIES:
        answer_cb(cq["id"])
        return
    text, markup = cards_page(cq["from"]["id"], rar, page)
    edit_menu(cq, text, markup)
    answer_cb(cq["id"])


def cb_view_card(cq, card_id):
    uid = cq["from"]["id"]
    msg = cq.get("message") or {}
    chat_id = msg.get("chat", {}).get("id", uid)
    card = get_card(card_id)
    if not card:
        answer_cb(cq["id"], "Не найдена.", True)
        return
    qty = qty_of(uid, card_id)
    if qty < 1:
        answer_cb(cq["id"], "У тебя нет такой.", True)
        return
    r = RARITIES[card["rarity"]]
    caption = (f"{r[1]} <b>{r[2]}</b>\n\n🎵 <b>{esc(card['title'])}</b>\n"
               f"👤 {esc(card['artist'])}\n💿 {esc(card['album'])}\n"
               f"ID: <code>{card['id']}</code>\n🎁 У тебя: ×{qty}")
    markup = kb([[btn("◀ К коллекции", "back_cards")]])
    send_media(chat_id, "photo", card["image"], caption, markup)
    answer_cb(cq["id"])


def cb_back_cards(cq):
    uid = cq["from"]["id"]
    msg = cq.get("message") or {}
    chat_id = msg.get("chat", {}).get("id", uid)
    rar, page = CARD_CTX.get(uid, ("all", 0))
    text, markup = cards_page(uid, rar, page)
    send(chat_id, text, markup)
    answer_cb(cq["id"])


# ───────────────────────── ТОП ─────────────────────────

def top_block(label, rarity):
    rows = db.execute(
        "SELECT u.user_id AS uid, u.name AS name, u.equipped AS eq, SUM(i.qty) AS n "
        "FROM inventory i JOIN cards c ON c.id=i.card_id JOIN users u ON u.user_id=i.user_id "
        "WHERE (? IS NULL OR c.rarity=?) GROUP BY u.user_id ORDER BY n DESC LIMIT 10",
        (rarity, rarity)).fetchall()
    lines = [f"<b>{label}</b>"]
    if not rows:
        lines.append("пока пусто")
    medals = ["🥇", "🥈", "🥉"]
    for i, r in enumerate(rows):
        mark = medals[i] if i < 3 else f"{i + 1}."
        nl = f'<a href="tg://user?id={r["uid"]}">{esc(r["name"])}</a>'
        lines.append(f"{mark} {badge(r['eq'])}{nl} — {r['n']}")
    lines.append("")
    return lines, rows


def cmd_top(m, args):
    chat_id = m["chat"]["id"]
    lines = ["🏆 <b>Рейтинги</b>\n"]
    buttons = []
    for label, rarity in [("Всего", None), ("⚪ Обычных", "common"), ("🟡 Легендарных", "legendary")]:
        blines, rows = top_block(label, rarity)
        lines += blines
        medals = ["🥇", "🥈", "🥉"]
        for i, r in enumerate(rows[:3]):
            nm = (r["name"] or "")[:16]
            buttons.append(btn(f"{medals[i]} {nm}", f"vp:{r['uid']}"))
    rows_kb = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
    send_long(chat_id, lines, kb(rows_kb) if rows_kb else None)


def cb_view_profile(cq, target_uid):
    uid = cq["from"]["id"]
    msg = cq.get("message") or {}
    chat_id = msg.get("chat", {}).get("id", uid)
    if target_uid == uid:
        answer_cb(cq["id"], "Это твой профиль 🙂", True)
        return
    if not get_user(target_uid):
        answer_cb(cq["id"], "Не найден.", True)
        return
    markup = kb([[btn("🔄 Обновить", f"vp:{target_uid}")]])
    send(chat_id, profile_text(target_uid), markup)
    answer_cb(cq["id"])


def cmd_view_user(m, args):
    chat_id = m["chat"]["id"]
    a = (args or "").strip()
    if not a:
        send(chat_id, "Формат: <code>/user @ник</code>")
        return
    if a.startswith("@"):
        u = db.execute("SELECT * FROM users WHERE username=?", (a[1:].lower(),)).fetchone()
    elif a.lstrip("-").isdigit():
        u = get_user(int(a))
    else:
        u = db.execute("SELECT * FROM users WHERE username=?", (a.lower(),)).fetchone()
    if not u:
        send(chat_id, "Не найден.")
        return
    if u["user_id"] == m["from"]["id"]:
        send(chat_id, "Это ты 🙂 /start")
        return
    send(chat_id, profile_text(u["user_id"]))


# ───────────────────────── КОСМЕТИКА ─────────────────────────

def cb_cosmetic(cq, item):
    uid = cq["from"]["id"]
    u = get_user(uid)
    toast = None
    if item == "off":
        db.execute("UPDATE users SET equipped=NULL WHERE user_id=?", (uid,))
        db.commit()
        toast = "Снято."
    elif item in COSMETICS:
        emoji, name, price = COSMETICS[item]
        has = db.execute("SELECT 1 FROM owned_cosmetics WHERE user_id=? AND item=?", (uid, item)).fetchone()
        if has:
            db.execute("UPDATE users SET equipped=? WHERE user_id=?", (item, uid))
            db.commit()
            toast = f"Надето: {emoji} {name}"
        elif u["coins"] < price:
            answer_cb(cq["id"], f"Нужно {price}, у тебя {u['coins']}.", True)
            return
        else:
            db.execute("UPDATE users SET coins=coins-?, equipped=? WHERE user_id=?", (price, item, uid))
            db.execute("INSERT INTO owned_cosmetics(user_id, item) VALUES(?,?)", (uid, item))
            db.commit()
            toast = f"Куплено: {emoji} {name}"
    text, markup = shop_menu(uid)
    edit_menu(cq, text, markup)
    answer_cb(cq["id"], toast)


def cmd_shop(m, args):
    text, markup = shop_menu(m["from"]["id"])
    send(m["chat"]["id"], text, markup)


# ───────────────────────── ОБМЕН ─────────────────────────

TRADE_USAGE = ("<code>/trade @ник мой_id чужой_id</code>\n"
               "или ответом: <code>/trade мой_id чужой_id</code>")


def trade_text(t):
    return (f"🔁 <b>{esc(who_label(t['from_id']))}</b> предлагает обмен:\n\n"
            f"Он отдаёт: {title_of(get_card(t['from_card']))}\n"
            f"Ты отдаёшь: {title_of(get_card(t['to_card']))}")


def cmd_trade(m, args):
    chat_id, me = m["chat"]["id"], m["from"]["id"]
    parts = args.split()
    reply_user = (m.get("reply_to_message") or {}).get("from")
    target = None
    if len(parts) == 2 and all(p.isdigit() for p in parts) and reply_user:
        target = get_user(reply_user["id"])
        my_card, their_card = int(parts[0]), int(parts[1])
    elif len(parts) == 3 and parts[0].startswith("@") and parts[1].isdigit() and parts[2].isdigit():
        target = db.execute("SELECT * FROM users WHERE username=?", (parts[0][1:].lower(),)).fetchone()
        my_card, their_card = int(parts[1]), int(parts[2])
    else:
        send(chat_id, TRADE_USAGE)
        return
    if my_card == their_card:
        send(chat_id, "Нельзя одну и ту же.")
        return
    if not target:
        send(chat_id, "Игрок не найден.")
        return
    if target["user_id"] == me:
        send(chat_id, "Нельзя с собой.")
        return
    if qty_of(me, my_card) < 1:
        send(chat_id, "У тебя нет карточки.")
        return
    if qty_of(target["user_id"], their_card) < 1:
        send(chat_id, "У него нет такой.")
        return
    cur = db.execute("INSERT INTO trades(from_id, to_id, from_card, to_card, status, created) "
                     "VALUES(?,?,?,?, 'pending', ?)",
                     (me, target["user_id"], my_card, their_card, int(time.time())))
    db.commit()
    tid = cur.lastrowid
    t = db.execute("SELECT * FROM trades WHERE id=?", (tid,)).fetchone()
    markup = kb([[btn("✅ Принять", f"t:y:{tid}"), btn("❌ Нет", f"t:n:{tid}")]])
    try:
        send(target["user_id"], trade_text(t), markup)
    except TgError:
        db.execute("UPDATE trades SET status='failed' WHERE id=?", (tid,))
        db.commit()
        send(chat_id, "Не доставить.")
        return
    send(chat_id, "📨 Отправлено.")


def cb_trade(cq, action, tid):
    t = db.execute("SELECT * FROM trades WHERE id=?", (tid,)).fetchone()
    if not t or t["status"] != "pending":
        answer_cb(cq["id"], "Неактуально.", True)
        return
    if cq["from"]["id"] != t["to_id"]:
        answer_cb(cq["id"], "Не для тебя.", True)
        return
    if time.time() - t["created"] > TRADE_TTL:
        status, line = "expired", "⌛ Истекло."
    elif action == "n":
        status, line = "declined", "❌ Отклонено."
    elif qty_of(t["from_id"], t["from_card"]) < 1 or qty_of(t["to_id"], t["to_card"]) < 1:
        status, line = "failed", "⚠️ Карточки уже нет."
    else:
        try:
            add_card(t["from_id"], t["from_card"], -1)
            add_card(t["to_id"], t["from_card"], 1)
            add_card(t["to_id"], t["to_card"], -1)
            add_card(t["from_id"], t["to_card"], 1)
            status, line = "accepted", "✅ Обмен выполнен!"
        except Exception:
            db.rollback()
            raise
    db.execute("UPDATE trades SET status=? WHERE id=?", (status, tid))
    if status == "accepted":
        db.execute("UPDATE users SET trades_ok = trades_ok + 1 WHERE user_id IN (?,?)",
                   (t["from_id"], t["to_id"]))
    db.commit()
    edit_menu(cq, trade_text(t) + f"\n\n{line}")
    answer_cb(cq["id"])
    notice = {"accepted": "✅ Твой обмен принят!", "declined": "❌ Отклонили.",
              "expired": "⌛ Истекло.", "failed": "⚠️ Не получилось."}[status]
    try:
        send(t["from_id"], notice)
    except TgError:
        pass
    if status == "accepted":
        notify_achievements(t["from_id"], check_achievements(t["from_id"]))
        notify_achievements(t["to_id"],   check_achievements(t["to_id"]))
        notify_quests(t["from_id"], progress_quest(t["from_id"], "trade1", 1))
        notify_quests(t["to_id"],   progress_quest(t["to_id"], "trade1", 1))


# ───────────────────────── СОСТОЯНИЯ ─────────────────────────

STATE = {}
TEXT_STEPS = ["title", "artist", "album"]
PROMPTS = {"title": "Название трека?", "artist": "Кто исполнитель?", "album": "Из какого альбома?"}


def rarity_rows(make):
    b = [btn(f"{v[1]} {v[2]}", make(k)) for k, v in RARITIES.items()]
    return [b[:2], b[2:]]


def cmd_cancel(m, args):
    STATE.pop(m["from"]["id"], None)
    send(m["chat"]["id"], "Отменено.")


def cmd_skip(m, args):
    st = STATE.get(m["from"]["id"])
    if st and st["flow"] == "add" and st["step"] == "photo":
        st["data"]["image"] = None
        st["step"] = "title"
        send(m["chat"]["id"], PROMPTS["title"])


def on_state(m, st):
    uid, chat_id = m["from"]["id"], m["chat"]["id"]
    flow, step, data = st["flow"], st["step"], st["data"]
    text = (m.get("text") or "").strip()
    if step == "photo":
        if m.get("photo"):
            data["image"] = m["photo"][-1]["file_id"]
            st["step"] = "title"
            send(chat_id, PROMPTS["title"])
        else:
            extra = " Без картинки — /skip." if flow == "add" else ""
            send(chat_id, f"Нужно фото.{extra} Отмена — /cancel.")
    elif step in TEXT_STEPS:
        if not text:
            send(chat_id, "Текстом. Отмена — /cancel.")
            return
        data[step] = text[:80]
        nxt = TEXT_STEPS.index(step) + 1
        if nxt < len(TEXT_STEPS):
            st["step"] = TEXT_STEPS[nxt]
            send(chat_id, PROMPTS[st["step"]])
        else:
            st["step"] = "rarity"
            send(chat_id, "Выбери редкость:", kb(rarity_rows(lambda k: f"ac:{k}")))
    elif step == "rarity":
        send(chat_id, "Выбери кнопкой выше.")


def cb_add_rarity(cq, rarity):
    uid = cq["from"]["id"]
    msg = cq.get("message") or {}
    chat_id, mid = msg.get("chat", {}).get("id", uid), msg.get("message_id")
    st = STATE.get(uid)
    if not st or st["flow"] != "add" or st["step"] != "rarity" or rarity not in RARITIES:
        answer_cb(cq["id"], "Неактуально.")
        return
    d = st["data"]
    STATE.pop(uid, None)
    aid = ensure_artist(d["artist"])
    cid = insert_card(d["title"], d["artist"], d["album"], rarity, d.get("image"), aid)
    if mid:
        clear_markup(chat_id, mid)
    if cid:
        send(chat_id, f"✅ Карточка #{cid}: {RARITIES[rarity][1]} {esc(d['title'])}")
    else:
        send(chat_id, "Уже есть.")
    answer_cb(cq["id"])


# ───────────────────────── ЗАЯВКИ ─────────────────────────

def start_suggest(uid, chat_id, chat_type):
    if chat_type != "private":
        send(chat_id, "Только в личке.")
        return
    n = db.execute("SELECT COUNT(*) FROM submissions WHERE user_id=? AND status='pending'", (uid,)).fetchone()[0]
    if n >= 3:
        send(chat_id, "Уже 3 заявки.")
        return
    STATE[uid] = {"flow": "sug", "step": "photo", "data": {}}
    send(chat_id, "🖼 Пришли обложку.\nОтмена — /cancel.")


def cmd_suggest(m, args):
    start_suggest(m["from"]["id"], m["chat"]["id"], m["chat"].get("type"))


def sub_caption(r):
    return (f"📥 <b>Заявка #{r['id']}</b>\n"
            f"Трек: {esc(r['title'])}\nИсполнитель: {esc(r['artist'])}\n"
            f"Альбом: {esc(r['album'])}\nОт: {esc(who_label(r['user_id']))}")


def send_submission(chat_id, r):
    markup = kb(rarity_rows(lambda k: f"sa:{r['id']}:{k}") + [[btn("❌ Отклонить", f"sr:{r['id']}")]])
    try:
        tg("sendPhoto", chat_id=chat_id, photo=r["image"],
           caption=sub_caption(r) + "\n\nВыбери редкость:", parse_mode="HTML", reply_markup=markup)
    except TgError as e:
        say(f"не отправить заявку: {e}")


def finish_suggest(uid, chat_id, d):
    cur = db.execute("INSERT INTO submissions(user_id, title, artist, album, image, status, created) "
                     "VALUES(?,?,?,?,?, 'pending', ?)",
                     (uid, d["title"], d["artist"], d["album"], d["image"], int(time.time())))
    db.commit()
    row = db.execute("SELECT * FROM submissions WHERE id=?", (cur.lastrowid,)).fetchone()
    send(chat_id, "📨 Отправлено на проверку.")
    for admin_id in ADMIN_IDS:
        send_submission(admin_id, row)


def cb_submission(cq, parts):
    approve = parts[0] == "sa"
    sub_id = int(parts[1])
    s = db.execute("SELECT * FROM submissions WHERE id=?", (sub_id,)).fetchone()
    if not s or s["status"] != "pending":
        answer_cb(cq["id"], "Уже обработано.", True)
        return
    if approve:
        rarity = parts[2] if len(parts) > 2 else ""
        if rarity not in RARITIES:
            answer_cb(cq["id"])
            return
        aid = ensure_artist(s["artist"])
        cid = insert_card(s["title"], s["artist"], s["album"], rarity, s["image"], aid)
        if cid:
            status, admin_line = "approved", f"✅ Одобрено: #{cid}"
            user_msg = f"🎉 Твой трек «{esc(s['title'])}» одобрен!"
        else:
            status, admin_line = "rejected", "⚠️ Уже есть."
            user_msg = f"«{esc(s['title'])}» уже есть."
    else:
        status, admin_line = "rejected", "❌ Отклонено"
        user_msg = f"😔 «{esc(s['title'])}» отклонили."
    db.execute("UPDATE submissions SET status=? WHERE id=?", (status, sub_id))
    db.commit()
    edit_menu(cq, sub_caption(s) + f"\n\n{admin_line}")
    try:
        send(s["user_id"], user_msg)
    except TgError:
        pass
    answer_cb(cq["id"])


# ───────────────────────── АДМИН ─────────────────────────

def panel_text():
    pending = db.execute("SELECT COUNT(*) FROM submissions WHERE status='pending'").fetchone()[0]
    n_cards = db.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
    n_users = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    n_artists = db.execute("SELECT COUNT(*) FROM artists").fetchone()[0]
    n_stars = db.execute("SELECT COALESCE(SUM(stars),0) FROM payments").fetchone()[0]
    ch1 = get_setting("sub_channel") or "—"
    ch2 = get_setting("sub_channel2") or "—"
    return (f"🛠 <b>Админ-панель</b>\n\n"
            f"👥 Игроков: {n_users}\n🎵 Карточек: {n_cards}\n🎤 Артистов: {n_artists}\n"
            f"📋 Заявок: {pending}\n⭐ Звёзд: {n_stars}\n"
            f"📢 Канал #1: <code>{esc(ch1)}</code>\n"
            f"📣 Канал #2: <code>{esc(ch2)}</code>")


def cmd_admin(m, args):
    if not is_admin(m["from"]["id"]):
        send(m["chat"]["id"], "Только для админа.")
        return
    goto(m["chat"]["id"], m["from"]["id"], "admin", panel_text(), m["chat"].get("type") == "private")


def admin_list_page(page):
    size = 20
    n = db.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
    pages = max(1, (n + size - 1) // size)
    page = min(max(page, 0), pages - 1)
    rows = db.execute("SELECT * FROM cards ORDER BY artist, album, title LIMIT ? OFFSET ?",
                      (size, page * size)).fetchall()
    lines = [f"🗂 <b>Все карточки ({n})</b>\n"]
    for r in rows:
        lines.append(f"<code>{r['id']}</code> {RARITIES[r['rarity']][1]} "
                     f"{esc(r['title'])} — {esc(r['artist'])} <i>({esc(r['album'])})</i>")
    lines.append("\nУдалить: <code>/delcard ID</code>")
    nav = [btn("◀", f"al:{page - 1}" if page > 0 else "noop"),
           btn(f"{page + 1}/{pages}", "noop"),
           btn("▶", f"al:{page + 1}" if page < pages - 1 else "noop")]
    return "\n".join(lines), kb([nav])


def admin_action(chat_id, uid, action):
    if action == "adm_add":
        STATE[uid] = {"flow": "add", "step": "photo", "data": {}}
        send(chat_id, "Отправь обложку.\nБез картинки — /skip, отмена — /cancel.")
    elif action == "adm_list":
        text, markup = admin_list_page(0)
        send(chat_id, text, markup)
    elif action == "adm_album":
        send(chat_id, ALBUM_HELP)
    elif action == "adm_spotify":
        send(chat_id, IMPORT_HELP)
    elif action == "adm_queue":
        rows = db.execute("SELECT * FROM submissions WHERE status='pending' ORDER BY id LIMIT 5").fetchall()
        if not rows:
            send(chat_id, "Заявок нет 🎉")
        for r in rows:
            send_submission(chat_id, r)


def cmd_clearcards(m, args):
    chat_id = m["chat"]["id"]
    if not is_admin(m["from"]["id"]):
        send(chat_id, "Только для админа.")
        return
    n = db.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
    send(chat_id, f"⚠️ Удалить <b>ВСЕ</b> карточки ({n})?",
         kb([[btn("🗑 Да", "cc:y"), btn("Отмена", "cc:n")]]))


def cb_clearcards(cq, answer):
    if answer == "y":
        db.execute("DELETE FROM inventory")
        db.execute("DELETE FROM cards")
        db.execute("DELETE FROM sqlite_sequence WHERE name='cards'")
        db.execute("UPDATE trades SET status='failed' WHERE status='pending'")
        db.commit()
        edit_menu(cq, "🗑 Все карточки удалены.")
    else:
        edit_menu(cq, "Отменено.")
    answer_cb(cq["id"])


def cmd_delcard(m, args):
    chat_id = m["chat"]["id"]
    if not is_admin(m["from"]["id"]):
        send(chat_id, "Только для админа.")
        return
    if not args.strip().isdigit():
        send(chat_id, "Формат: <code>/delcard ID</code>")
        return
    card = get_card(int(args.strip()))
    if not card:
        send(chat_id, "Нет такой.")
        return
    db.execute("DELETE FROM inventory WHERE card_id=?", (card["id"],))
    db.execute("DELETE FROM cards WHERE id=?", (card["id"],))
    db.commit()
    send(chat_id, f"🗑 Удалено: {title_of(card)}")


def photo_id_of(m):
    if m.get("photo"):
        return m["photo"][-1]["file_id"]
    rp = m.get("reply_to_message") or {}
    if rp.get("photo"):
        return rp["photo"][-1]["file_id"]
    return None


def cmd_addtrack(m, args):
    chat_id = m["chat"]["id"]
    if not is_admin(m["from"]["id"]):
        send(chat_id, "Только для админа.")
        return
    p = [x.strip() for x in args.split("|")]
    if len(p) < 4 or not all(p[:3]) or p[3].lower() not in RARITIES:
        send(chat_id, "Формат: <code>/addtrack Название | Артист | Альбом | редкость</code>")
        return
    aid = ensure_artist(p[1])
    cid = insert_card(p[0], p[1], p[2], p[3].lower(), photo_id_of(m), aid)
    send(chat_id, f"✅ Карточка #{cid}" if cid else "Уже есть.")


def cmd_addalbum(m, args):
    chat_id = m["chat"]["id"]
    if not is_admin(m["from"]["id"]):
        send(chat_id, "Только для админа.")
        return
    p = [x.strip() for x in args.split("|", 3)]
    if len(p) < 4 or not p[0] or not p[1] or p[2].lower() not in RARITIES:
        send(chat_id, ALBUM_HELP)
        return
    artist, album, default_r = p[0][:80], p[1][:80], p[2].lower()
    image = photo_id_of(m)
    aid = ensure_artist(artist, image=image)
    added = skipped = 0
    for raw in p[3].replace("\n", ";").split(";"):
        raw = raw.strip()
        if not raw:
            continue
        rarity = default_r
        mt = re.match(r"^(.*?)\s*\[(common|rare|epic|legendary)\]\s*$", raw, re.I)
        if mt:
            raw, rarity = mt.group(1).strip(), mt.group(2).lower()
        if insert_card(raw, artist, album, rarity, image, aid):
            added += 1
        else:
            skipped += 1
    send(chat_id, f"💿 {esc(artist)} — {esc(album)}: добавлено {added}"
                  + (f", уже были {skipped}" if skipped else ""))


def cmd_setcover(m, args):
    chat_id = m["chat"]["id"]
    if not is_admin(m["from"]["id"]):
        send(chat_id, "Только для админа.")
        return
    p = [x.strip() for x in args.split("|")]
    image = photo_id_of(m)
    if len(p) != 2 or not all(p) or not image:
        send(chat_id, "Формат: фото с <code>/setcover Артист | Альбом</code>")
        return
    cur = db.execute("UPDATE cards SET image=? WHERE artist=? COLLATE NOCASE AND album=? COLLATE NOCASE",
                     (image, p[0], p[1]))
    db.commit()
    send(chat_id, f"🖼 Обновлено у {cur.rowcount} треков.")


def cmd_delalbum(m, args):
    chat_id = m["chat"]["id"]
    if not is_admin(m["from"]["id"]):
        send(chat_id, "Только для админа.")
        return
    p = [x.strip() for x in args.split("|")]
    if len(p) != 2 or not all(p):
        send(chat_id, "Формат: <code>/delalbum Артист | Альбом</code>")
        return
    ids = [r["id"] for r in db.execute(
        "SELECT id FROM cards WHERE artist=? COLLATE NOCASE AND album=? COLLATE NOCASE",
        (p[0], p[1]))]
    for cid in ids:
        db.execute("DELETE FROM inventory WHERE card_id=?", (cid,))
        db.execute("DELETE FROM cards WHERE id=?", (cid,))
    db.commit()
    send(chat_id, f"🗑 Удалено: {len(ids)}")


def cmd_setwelcome(m, args):
    chat_id = m["chat"]["id"]
    if not is_admin(m["from"]["id"]):
        send(chat_id, "Только для админа.")
        return
    if args.strip().lower() == "off":
        set_setting("welcome_media", None)
        send(chat_id, "Убрано.")
        return
    for src in (m, m.get("reply_to_message") or {}):
        if src.get("animation"):
            media = ("animation", src["animation"]["file_id"])
        elif src.get("photo"):
            media = ("photo", src["photo"][-1]["file_id"])
        elif src.get("video"):
            media = ("video", src["video"]["file_id"])
        else:
            continue
        set_setting("welcome_media", f"{media[0]}:{media[1]}")
        send(chat_id, "✅ Обновлено.")
        return
    send(chat_id, "Отправь фото/гифку с <code>/setwelcome</code>. Убрать: off")


def cmd_givecoins(m, args):
    chat_id = m["chat"]["id"]
    if not is_admin(m["from"]["id"]):
        send(chat_id, "Только для админа.")
        return
    p = args.split()
    if len(p) != 2 or not p[0].startswith("@") or not p[1].lstrip("-").isdigit():
        send(chat_id, "Формат: <code>/givecoins @ник 500</code>")
        return
    u = db.execute("SELECT * FROM users WHERE username=?", (p[0][1:].lower(),)).fetchone()
    if not u:
        send(chat_id, "Не найден.")
        return
    new = max(0, u["coins"] + int(p[1]))
    db.execute("UPDATE users SET coins=? WHERE user_id=?", (new, u["user_id"]))
    db.commit()
    send(chat_id, f"💰 {esc(u['name'])}: {new}")


def cmd_setrarity(m, args):
    chat_id = m["chat"]["id"]
    if not is_admin(m["from"]["id"]):
        send(chat_id, "Только для админа.")
        return
    p = args.split()
    if len(p) != 2 or not p[0].isdigit() or p[1].lower() not in RARITIES:
        send(chat_id, "Формат: <code>/setrarity ID редкость</code>")
        return
    card = get_card(int(p[0]))
    if not card:
        send(chat_id, "Не найдено.")
        return
    db.execute("UPDATE cards SET rarity=? WHERE id=?", (p[1].lower(), card["id"]))
    db.commit()
    send(chat_id, f"✅ {title_of(get_card(card['id']))}")


# ───────────────────────── АВАТАР ─────────────────────────

def cmd_setavatar(m, args):
    uid, chat_id = m["from"]["id"], m["chat"]["id"]
    arg = (args or "").strip()
    if not arg.isdigit():
        send(chat_id, "Формат: <code>/setavatar ID</code>")
        return
    card_id = int(arg)
    if qty_of(uid, card_id) < 1:
        send(chat_id, "Нет такой карточки.")
        return
    card = get_card(card_id)
    if not card or not card["image"]:
        send(chat_id, "У карточки нет картинки.")
        return
    db.execute("UPDATE users SET avatar_card=? WHERE user_id=?", (card_id, uid))
    db.commit()
    fr = frame_for(uid)
    send(chat_id, f"{fr} ✅ Аватар: {title_of(card)}")


def cmd_delavatar(m, args):
    uid = m["from"]["id"]
    db.execute("UPDATE users SET avatar_card=NULL WHERE user_id=?", (uid,))
    db.commit()
    send(m["chat"]["id"], "🗑 Аватар снят.")


def cmd_avatar(m, args):
    uid, chat_id = m["from"]["id"], m["chat"]["id"]
    u = get_user(uid)
    if not u["avatar_card"]:
        send(chat_id, "Аватара нет. Формат: <code>/setavatar ID</code>")
        return
    card = get_card(u["avatar_card"])
    if not card:
        send(chat_id, "Карточка удалена.")
        return
    fr = frame_for(uid)
    send_media(chat_id, "photo", card["image"], f"{fr} Твой аватар: {title_of(card)}")


# ───────────────────────── КОМАНДЫ ─────────────────────────

def cmd_start(m, args):
    uid = m["from"]["id"]
    a = (args or "").strip()
    if a.startswith("ref_"):
        u = get_user(uid)
        if u and (time.time() - (u["joined"] or 0) < REFERRAL_MAX_AGE):
            ok, ref_id = process_referral(uid, a)
            if ok:
                ref_u = get_user(ref_id)
                cnt = (ref_u["ref_count"] if ref_u else 1)
                try:
                    send(ref_id, f"🎉 <b>Новый реферал!</b>\n💰 +{REFERRAL_BONUS}\n👥 Всего: {cnt}")
                except TgError:
                    pass
    send_home(m["chat"]["id"], uid, m["chat"].get("type") == "private")


def cmd_help(m, args):
    send(m["chat"]["id"], HELP)


COMMANDS = {
    "start": cmd_start, "menu": cmd_start, "profile": cmd_start,
    "help": cmd_help,
    "claim": cmd_claim, "open": cmd_open, "cards": cmd_cards,
    "shop": cmd_shop, "top": cmd_top,
    "ref": cmd_ref, "subscribe": cmd_subscribe, "channelsub": cmd_channelsub,
    "user": cmd_view_user, "trade": cmd_trade, "suggest": cmd_suggest,
    "quests": cmd_quests, "achievements": cmd_achievements, "titles": cmd_titles,
    "friends": cmd_friends, "addfriend": cmd_addfriend, "delfriend": cmd_delfriend,
    "avatar": cmd_avatar, "setavatar": cmd_setavatar, "delavatar": cmd_delavatar,
    "admin": cmd_admin,
    "delcard": cmd_delcard, "addtrack": cmd_addtrack, "addalbum": cmd_addalbum,
    "setcover": cmd_setcover, "delalbum": cmd_delalbum, "setwelcome": cmd_setwelcome,
    "givecoins": cmd_givecoins, "clearcards": cmd_clearcards,
    "spotify": cmd_spotify, "setrarity": cmd_setrarity,
    "artists": cmd_artists, "addartist": cmd_addartist, "delartist": cmd_delartist,
    "setartistcover": cmd_setartistcover,
    "setchannel": cmd_setchannel, "setchannel2": cmd_setchannel2,
    "setchreward": cmd_setchreward, "setchreward2": cmd_setchreward2,
}


def on_button(m, action):
    uid, chat_id = m["from"]["id"], m["chat"]["id"]
    chat_type = m["chat"].get("type")
    priv = chat_type == "private"
    if action in ADMIN_ACTIONS and not is_admin(uid):
        send(chat_id, "Только для админа.")
        return
    if action == "home":
        send_home(chat_id, uid, priv)
    elif action == "back":
        if NAV.get(uid) == "open":
            goto(chat_id, uid, "cards", cards_text(uid), priv)
        else:
            send_home(chat_id, uid, priv)
    elif action == "g_cards":
        goto(chat_id, uid, "cards", cards_text(uid), priv)
    elif action == "g_open":
        goto(chat_id, uid, "open", open_text(uid), priv)
    elif action == "open:random":
        do_open(uid, chat_id)
    elif action == "coll":
        cmd_cards(m, "")
    elif action == "trade":
        send(chat_id, TRADE_USAGE)
    elif action == "suggest":
        start_suggest(uid, chat_id, chat_type)
    elif action == "g_shop":
        goto(chat_id, uid, "shop", "💄 <b>Косметика</b>", priv)
        send(chat_id, *shop_menu(uid))
    elif action == "shop":
        send(chat_id, *shop_menu(uid))
    elif action == "unequip":
        db.execute("UPDATE users SET equipped=NULL WHERE user_id=?", (uid,))
        db.commit()
        send(chat_id, "Снято.")
    elif action == "g_coins":
        goto(chat_id, uid, "coins", coins_text(uid), priv)
    elif action == "claim":
        cmd_claim(m, "")
    elif action == "balance":
        send(chat_id, coins_text(uid))
    elif action == "top":
        cmd_top(m, "")
    elif action == "help":
        cmd_help(m, "")
    elif action == "ref":
        cmd_ref(m, "")
    elif action == "sub_menu":
        cmd_subscribe(m, "")
    elif action == "chsub_menu":
        cmd_channelsub(m, "")
    elif action == "artists":
        cmd_artists(m, "")
    elif action == "quests":
        cmd_quests(m, "")
    elif action == "ach":
        cmd_achievements(m, "")
    elif action == "titles":
        cmd_titles(m, "")
    elif action == "friends":
        cmd_friends(m, "")
    elif action == "g_admin":
        goto(chat_id, uid, "admin", panel_text(), priv)
    elif action in ADMIN_ACTIONS:
        admin_action(chat_id, uid, action)


def on_message(m):
    u = m.get("from")
    if not u or u.get("is_bot"):
        return
    ensure_user(u)
    if not STATE.get(u["id"]):
        q = progress_quest(u["id"], "msg5", 1)
        if q:
            notify_quests(m["chat"]["id"], q)
    body = (m.get("text") or m.get("caption") or "").strip()
    if body.startswith("/"):
        pieces = body.split(None, 1)
        args = pieces[1] if len(pieces) > 1 else ""
        cmd, _, suffix = pieces[0][1:].partition("@")
        cmd = cmd.lower()
        if suffix and BOT_USERNAME and suffix.lower() != BOT_USERNAME:
            return
        if cmd == "cancel":
            cmd_cancel(m, args)
        elif cmd == "skip":
            cmd_skip(m, args)
        elif cmd in COMMANDS:
            STATE.pop(u["id"], None)
            COMMANDS[cmd](m, args)
        return
    action = LABELS.get((m.get("text") or "").strip())
    if action:
        STATE.pop(u["id"], None)
        on_button(m, action)
        return
    st = STATE.get(u["id"])
    if st:
        on_state(m, st)


def on_callback(cq):
    ensure_user(cq["from"])
    parts = (cq.get("data") or "").split(":")
    kind = parts[0]
    uid = cq["from"]["id"]

    if kind == "chsub" and len(parts) == 3 and parts[1] == "check":
        try:
            slot = int(parts[2])
        except ValueError:
            answer_cb(cq["id"])
            return
        if slot in (1, 2):
            cb_channelsub(cq, slot)
        return
    if kind == "ar" and len(parts) == 2:
        if parts[1] == "list":
            cb_artists_list(cq)
        elif parts[1].isdigit():
            cb_artist(cq, int(parts[1]))
        return
    if kind == "vp" and len(parts) == 2 and parts[1].lstrip("-").isdigit():
        cb_view_profile(cq, int(parts[1]))
        return
    if kind == "vc" and len(parts) == 2 and parts[1].isdigit():
        cb_view_card(cq, int(parts[1]))
        return
    if kind == "back_cards":
        cb_back_cards(cq)
        return
    if kind == "ref" and len(parts) == 2 and parts[1] == "refresh":
        cmd_ref({"from": {"id": uid},
                 "chat": {"id": (cq.get("message") or {}).get("chat", {}).get("id", uid)}}, "")
        answer_cb(cq["id"])
        return
    if kind == "sub" and len(parts) >= 2:
        cb_subscribe(cq, ":".join(parts[1:]))
        return
    if kind == "ti" and len(parts) == 2 and parts[1] in TITLES:
        cb_title(cq, parts[1])
        return
    if kind == "dza":
        if not is_admin(uid):
            answer_cb(cq["id"], "Нет доступа.", True)
            return
        cb_deezer(cq, parts)
        return
    if kind == "cs" and len(parts) == 2:
        cb_cosmetic(cq, parts[1])
    elif kind == "cp":
        cb_cards_page(cq, parts)
    elif kind == "t" and len(parts) == 3 and parts[2].isdigit():
        cb_trade(cq, parts[1], int(parts[2]))
    elif kind == "f" and len(parts) == 3 and parts[2].lstrip("-").isdigit():
        cb_friend(cq, parts[1], int(parts[2]))
    elif kind in ("ak", "ac", "sa", "sr", "al", "cc"):
        if not is_admin(uid):
            answer_cb(cq["id"], "Нет доступа.", True)
            return
        if kind == "ac" and len(parts) == 2:
            cb_add_rarity(cq, parts[1])
        elif kind == "cc" and len(parts) == 2:
            cb_clearcards(cq, parts[1])
        elif kind in ("sa", "sr") and len(parts) >= 2 and parts[1].isdigit():
            cb_submission(cq, parts)
        elif kind == "al" and len(parts) == 2 and parts[1].lstrip("-").isdigit():
            text, markup = admin_list_page(int(parts[1]))
            edit_menu(cq, text, markup)
            answer_cb(cq["id"])
    else:
        answer_cb(cq["id"])


def handle_update(u):
    if "message" in u:
        m = u["message"]
        if m.get("successful_payment"):
            on_successful_payment(m)
            return
        on_message(m)
    elif "callback_query" in u:
        on_callback(u["callback_query"])
    elif "pre_checkout_query" in u:
        on_pre_checkout(u["pre_checkout_query"])


def main():
    global BOT_USERNAME
    init_db()
    say("▶ База готова")
    me = tg("getMe")
    BOT_USERNAME = (me.get("username") or "").lower()
    say(f"▶ Бот подключён: @{me.get('username')}")
    try:
        tg("deleteWebhook")
        tg("setMyCommands", commands=[
            {"command": "start", "description": "Профиль и меню"},
            {"command": "claim", "description": "Забрать монеты"},
            {"command": "open", "description": "Крутить карточку"},
            {"command": "cards", "description": "Моя коллекция"},
            {"command": "artists", "description": "Артисты"},
            {"command": "quests", "description": "Квесты"},
            {"command": "achievements", "description": "Достижения"},
            {"command": "titles", "description": "Титулы"},
            {"command": "friends", "description": "Друзья"},
            {"command": "shop", "description": "Косметика"},
            {"command": "ref", "description": "Рефералы"},
            {"command": "subscribe", "description": "Подписки ⭐"},
            {"command": "channelsub", "description": "Подписка на каналы"},
            {"command": "top", "description": "Рейтинги"},
            {"command": "help", "description": "Помощь"},
        ])
    except Exception as e:
        say(f"меню команд: {e}")
    say("▶ Слушаю сообщения")
    offset = None
    while True:
        params = {"timeout": 25, "allowed_updates": ["message", "callback_query", "pre_checkout_query"]}
        if offset:
            params["offset"] = offset
        try:
            updates = tg("getUpdates", **params)
        except TgError as e:
            say(f"getUpdates: {e}")
            time.sleep(5)
            continue
        except Exception as e:
            say(f"сеть: {e!r}")
            time.sleep(5)
            continue
        for u in updates:
            offset = u["update_id"] + 1
            try:
                handle_update(u)
            except Exception:
                say("❌ ошибка:\n" + traceback.format_exc())


if __name__ == "__main__":
    main()