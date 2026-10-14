import datetime as dt, hashlib, html, json, os, random, re, sqlite3, sys, time, traceback
import urllib.error, urllib.parse, urllib.request
from urllib.parse import quote

LOG = "bot_debug.log"

def say(msg):
    line = f"{dt.datetime.now():%d.%m %H:%M:%S} {msg}"
    try:
        import resource
        line += f" [{resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024} МБ]"
    except: pass
    print(line, flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as f: f.write(line + "\n")
    except: pass

def _eh(t, v, tb):
    say("❌ " + "".join(traceback.format_exception(t, v, tb)))
sys.excepthook = _eh
say("▶ app.py запущен")

def load_env():
    base = os.path.dirname(os.path.abspath(__file__))
    for p in (os.path.join(base, ".env"), ".env"):
        if os.path.isfile(p):
            with open(p, encoding="utf-8-sig") as f:
                for l in f:
                    l = l.strip()
                    if l and not l.startswith("#") and "=" in l:
                        k, v = l.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
            return
load_env()

TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not TOKEN:
    say("❌ BOT_TOKEN не найден"); sys.exit(1)
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x.lstrip("-").isdigit()}
DB_PATH = os.getenv("DB_PATH", "music.db")

def env_int(k, d): return int(os.getenv(k, str(d)))
def env_float(k, d): return float(os.getenv(k, str(d)))

CLAIM_AMOUNT = env_int("CLAIM_AMOUNT", 450)
CLAIM_SECONDS = int(env_float("CLAIM_HOURS", 2) * 3600)
CLAIM_BONUS = env_int("CLAIM_BONUS", 200)
CLAIM_MAX_SECONDS = max(CLAIM_SECONDS, int(env_float("CLAIM_MAX_HOURS", 8) * 3600))
STEP = 3600
PITY_L = env_int("PITY_LEGENDARY", 50)
PITY_E = env_int("PITY_EPIC", 15)
OPEN_COST = env_int("OPEN_COST", 300)
REF_BONUS = env_int("REFERRAL_BONUS", 1000)
REF_AGE = 600
SUB_B_STARS = env_int("SUB_BASIC_STARS", 150)
SUB_P_STARS = env_int("SUB_PREMIUM_STARS", 250)
SUB_DAYS = env_int("SUB_DAYS", 30)
SUB_B_MULT = env_float("SUB_BASIC_MULT", 1.5)
SUB_P_MULT = env_float("SUB_PREMIUM_MULT", 2.0)
MEGA_STARS = env_int("MEGA_STARS", 35)
MEGA_COINS = env_int("MEGA_COINS", 10000)
CH1_R = env_int("CHANNEL_REWARD", 2000)
CH2_R = env_int("CHANNEL2_REWARD", 1500)
TRADE_TTL = 86400
PAGE = 12
API = f"https://api.telegram.org/bot{TOKEN}/"
BOT_USERNAME = ""
esc = html.escape

RARITIES = {
    "common": (68, "⚪", "Обычный", "Обычные"),
    "rare": (22, "🔵", "Редкий", "Редкие"),
    "epic": (7, "🟣", "Эпический", "Эпические"),
    "legendary": (3, "🟡", "Легендарный", "Легендарные"),
}
RARITY_SQL = "CASE {c} WHEN 'legendary' THEN 0 WHEN 'epic' THEN 1 WHEN 'rare' THEN 2 ELSE 3 END"

COSMETICS = {
    "note": ("🎵", "Нотка", 500), "mic": ("🎤", "Микрофон", 1000),
    "vinyl": ("💿", "Винил", 1500), "fire": ("🔥", "Огонь", 2500),
    "crown": ("👑", "Корона", 5000),
}
FRAMES = {"common": "⬜️", "rare": "🟩", "epic": "🟪", "legendary": "🟧"}
SPECIAL = {"crown": "👑", "fire": "🔥", "diamond": "💎", "rainbow": "🌈"}

ACH = {
    "first": ("🎵", "Первая карточка", "Собрать 1"),
    "ten": ("🎶", "Десятка", "10 уникальных"),
    "fifty": ("💿", "Полтинник", "50 уникальных"),
    "half": ("🏆", "Половина", "50%"),
    "full": ("👑", "Коллекционер", "100%"),
    "c10": ("⚪", "Обычный день", "10 common"),
    "r10": ("🟢", "Редкий улов", "10 rare"),
    "e5": ("🟣", "Эпик-ловец", "5 epic"),
    "l1": ("🟠", "Легенда", "1 legendary"),
    "trade1": ("🤝", "Первый обмен", "Обмен"),
    "fire7": ("🔥", "Марафонец", "7 дней"),
    "rich100": ("💎", "Богач", "100 шт"),
}
TITLES = {
    "newbie": ("🎤", "Новичок", "1 карточка"),
    "meloman": ("🎶", "Меломан", "10"),
    "collector": ("💿", "Коллекционер", "25"),
    "master": ("🏆", "Мастер", "50"),
    "legend": ("👑", "Легенда", "Все"),
    "devoted": ("🔥", "Преданный", "7 дней"),
    "trader": ("🤝", "Торговец", "5 обменов"),
    "expert": ("🎧", "Знаток", "5+ в 4 жанрах"),
    "rich": ("💎", "Богач", "100"),
    "chosen": ("🌟", "Избранный", "5 достижений"),
}
TITLE_ORDER = ["chosen","legend","master","collector","meloman","devoted","trader","rich","expert","newbie"]
DEMO = [('bad guy','Billie Eilish','When We All Fall Asleep, Where Do We Go?'),('Levitating','Dua Lipa','Future Nostalgia'),('Someone Like You','Adele','21'),('Shape of You','Ed Sheeran','÷ (Divide)'),('Blinding Lights','The Weeknd','After Hours'),('Smells Like Teen Spirit','Nirvana','Nevermind')]
QUESTS = [
    ("open3","🎴","Открой 3 карточки",3,30,"card"),
    ("qty5","🎁","Собери 5 экземпляров",5,25,None),
    ("trade1","🤝","Соверши 1 обмен",1,50,None),
    ("ach1","🏅","Получи достижение",1,25,None),
    ("msg5","💬","Отправь 5 сообщений",5,20,None),
    ("open5","🔥","Открой 5 карточек",5,60,"card"),
]

# ── Telegram API ──
class TgErr(Exception): pass

def tg(method, **params):
    data = json.dumps(params, ensure_ascii=False).encode()
    req = urllib.request.Request(API + method, data=data, headers={"Content-Type":"application/json"})
    t = int(params.get("timeout", 0)) + 30
    try:
        with urllib.request.urlopen(req, timeout=t) as r: res = json.loads(r.read())
    except urllib.error.HTTPError as e:
        try: res = json.loads(e.read())
        except: res = {"ok": False, "description": f"HTTP {e.code}"}
    if not res.get("ok"): raise TgErr(res.get("description", "tg error"))
    return res["result"]

def btn(t, d): return {"text": t, "callback_data": d}
def kb(rows): return {"inline_keyboard": rows}

def send(cid, text, markup=None):
    p = {"chat_id": cid, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    if markup: p["reply_markup"] = markup
    return tg("sendMessage", **p)

def send_long(cid, lines, markup=None):
    c = ""; parts = []
    for l in lines:
        if len(c) + len(l) + 1 > 3800: parts.append(c); c = ""
        c += l + "\n"
    if c: parts.append(c)
    for i, p in enumerate(parts):
        send(cid, p, markup if (i == len(parts)-1 and markup) else None)

def send_media(cid, kind, fid, cap, markup=None):
    m = {"photo":"sendPhoto","animation":"sendAnimation","video":"sendVideo"}.get(kind)
    if fid and m:
        p = {"chat_id":cid, kind:fid, "caption":cap[:1024], "parse_mode":"HTML"}
        if markup: p["reply_markup"] = markup
        try: return tg(m, **p)
        except TgErr: say("media fail")
    return send(cid, cap, markup)

def answer_cb(cqid, text=None, alert=False):
    p = {"callback_query_id": cqid}
    if text: p["text"] = text; p["show_alert"] = alert
    try: tg("answerCallbackQuery", **p)
    except TgErr: pass

def edit_menu(cq, text, markup=None):
    msg = cq.get("message") or {}
    cid, mid = msg.get("chat",{}).get("id"), msg.get("message_id")
    if not cid or not mid: return
    is_m = any(k in msg for k in ("photo","animation","video","document"))
    try:
        if is_m: tg("editMessageCaption", chat_id=cid, message_id=mid, caption=text[:1024], parse_mode="HTML", reply_markup=markup or kb([]))
        else: tg("editMessageText", chat_id=cid, message_id=mid, text=text, parse_mode="HTML", disable_web_page_preview=True, reply_markup=markup or kb([]))
    except TgErr: pass

def edit_text(cid, mid, text, markup=None):
    try: tg("editMessageText", chat_id=cid, message_id=mid, text=text, parse_mode="HTML", disable_web_page_preview=True, reply_markup=markup or kb([]))
    except TgErr: pass

def clear_kb(cid, mid):
    try: tg("editMessageReplyMarkup", chat_id=cid, message_id=mid, reply_markup=kb([]))
    except TgErr: pass

# ── DB ──
db = None

def init_db():
    global db
    if os.path.exists(DB_PATH):
        try:
            tmp = sqlite3.connect(DB_PATH)
            cols = [r[1] for r in tmp.execute("PRAGMA table_info(cards)")]
            tmp.close()
            if cols and "title" not in cols:
                os.replace(DB_PATH, DB_PATH + ".old")
                say("старая база → .old")
        except: pass
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY, username TEXT, name TEXT,
      coins INTEGER DEFAULT 0, last_claim INTEGER DEFAULT 0, equipped TEXT, joined INTEGER DEFAULT 0,
      pity_leg INTEGER DEFAULT 0, pity_epic INTEGER DEFAULT 0, open_streak INTEGER DEFAULT 0,
      last_open_day TEXT, referred_by INTEGER, ref_count INTEGER DEFAULT 0, ref_earned INTEGER DEFAULT 0,
      sub_tier TEXT, sub_until INTEGER DEFAULT 0, xp INTEGER DEFAULT 0, title TEXT,
      avatar_card INTEGER, warns INTEGER DEFAULT 0, trades_ok INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS cards(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
      artist TEXT NOT NULL, album TEXT NOT NULL, rarity TEXT NOT NULL, image TEXT, artist_id INTEGER,
      UNIQUE(title, artist, album));
    CREATE TABLE IF NOT EXISTS artists(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE,
      image TEXT, description TEXT, spotify_id TEXT, created INTEGER);
    CREATE TABLE IF NOT EXISTS inventory(user_id INTEGER, card_id INTEGER, qty INTEGER,
      PRIMARY KEY(user_id, card_id));
    CREATE TABLE IF NOT EXISTS trades(id INTEGER PRIMARY KEY AUTOINCREMENT, from_id INTEGER, to_id INTEGER,
      from_card INTEGER, to_card INTEGER, status TEXT, created INTEGER);
    CREATE TABLE IF NOT EXISTS submissions(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
      title TEXT, artist TEXT, album TEXT, image TEXT, status TEXT, created INTEGER);
    CREATE TABLE IF NOT EXISTS owned_cosmetics(user_id INTEGER, item TEXT, PRIMARY KEY(user_id, item));
    CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
    CREATE TABLE IF NOT EXISTS referrals(invited_id INTEGER PRIMARY KEY, referrer_id INTEGER,
      rewarded INTEGER DEFAULT 0, created INTEGER);
    CREATE TABLE IF NOT EXISTS payments(charge_id TEXT PRIMARY KEY, user_id INTEGER, tier TEXT,
      stars INTEGER, days INTEGER, created INTEGER);
    CREATE TABLE IF NOT EXISTS channel_rewards(user_id INTEGER PRIMARY KEY, claimed INTEGER DEFAULT 0, created INTEGER);
    CREATE TABLE IF NOT EXISTS channel2_rewards(user_id INTEGER PRIMARY KEY, claimed INTEGER DEFAULT 0, created INTEGER);
    CREATE TABLE IF NOT EXISTS achievements(user_id INTEGER, code TEXT, got INTEGER, PRIMARY KEY(user_id, code));
    CREATE TABLE IF NOT EXISTS quests(user_id INTEGER, day TEXT, code TEXT, progress INTEGER DEFAULT 0,
      target INTEGER, xp INTEGER DEFAULT 0, done INTEGER DEFAULT 0, PRIMARY KEY(user_id, day, code));
    CREATE TABLE IF NOT EXISTS friends(user_id INTEGER, friend_id INTEGER, status TEXT, created INTEGER,
      PRIMARY KEY(user_id, friend_id));
    CREATE TABLE IF NOT EXISTS promocodes(code TEXT PRIMARY KEY, reward INTEGER,
      uses_left INTEGER DEFAULT -1, created INTEGER);
    CREATE TABLE IF NOT EXISTS promocode_uses(user_id INTEGER, code TEXT, used_at INTEGER,
      PRIMARY KEY(user_id, code));
    """)
    db.execute("INSERT OR IGNORE INTO promocodes(code, reward, uses_left, created) VALUES(?,?,?,?)",
               ("PIZDEC", 20000, -1, int(time.time())))
    db.commit()
    purge_demo()

def ensure_cols(table, cols):
    have = {r[1] for r in db.execute(f"PRAGMA table_info({table})")}
    for n, ddl in cols.items():
        if n not in have: db.execute(f"ALTER TABLE {table} ADD COLUMN {n} {ddl}")
    db.commit()

def purge_demo():
    if get_setting("demo_purged"): return
    for t, a, al in DEMO:
        r = db.execute("SELECT id FROM cards WHERE title=? AND artist=? AND album=?", (t,a,al)).fetchone()
        if r:
            db.execute("DELETE FROM inventory WHERE card_id=?", (r["id"],))
            db.execute("DELETE FROM cards WHERE id=?", (r["id"],))
    db.commit(); set_setting("demo_purged", "1")

def full_name(u):
    n = " ".join(x for x in (u.get("first_name"), u.get("last_name")) if x)
    return n or str(u["id"])

def ensure_user(u):
    db.execute("INSERT INTO users(user_id, username, name, joined) VALUES(?,?,?,?) "
               "ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, name=excluded.name",
               (u["id"], (u.get("username") or "").lower() or None, full_name(u), int(time.time())))
    db.commit()

def get_user(uid): return db.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
def get_setting(k):
    r = db.execute("SELECT value FROM settings WHERE key=?", (k,)).fetchone()
    return r["value"] if r else None

def set_setting(k, v):
    if v is None: db.execute("DELETE FROM settings WHERE key=?", (k,))
    else: db.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, v))
    db.commit()

def add_card(uid, cid, d):
    db.execute("INSERT INTO inventory(user_id, card_id, qty) VALUES(?,?,?) "
               "ON CONFLICT(user_id, card_id) DO UPDATE SET qty=qty+?", (uid, cid, d, d))
    db.execute("DELETE FROM inventory WHERE user_id=? AND card_id=? AND qty<=0", (uid, cid))

def qty_of(uid, cid):
    r = db.execute("SELECT qty FROM inventory WHERE user_id=? AND card_id=?", (uid, cid)).fetchone()
    return r["qty"] if r else 0

def get_card(cid): return db.execute("SELECT * FROM cards WHERE id=?", (cid,)).fetchone()
def get_artist(aid): return db.execute("SELECT * FROM artists WHERE id=?", (aid,)).fetchone()
def find_artist(n): return db.execute("SELECT * FROM artists WHERE name=? COLLATE NOCASE", (n,)).fetchone()

def ensure_artist(name, image=None, desc=None, spid=None):
    a = find_artist(name)
    if a:
        if image and not a["image"]:
            db.execute("UPDATE artists SET image=? WHERE id=?", (image, a["id"])); db.commit()
        return a["id"]
    cur = db.execute("INSERT INTO artists(name, image, description, spotify_id, created) VALUES(?,?,?,?,?)",
                     (name[:80], image, desc, spid, int(time.time())))
    db.commit(); return cur.lastrowid

def title_of(c):
    if not c: return "<i>удалена</i>"
    return f"{RARITIES[c['rarity']][1]} <b>{esc(c['title'])}</b> — {esc(c['artist'])} <i>({esc(c['album'])})</i>"

def badge(e): return COSMETICS[e][0] + " " if e in COSMETICS else ""

def who(uid):
    u = get_user(uid)
    if not u: return str(uid)
    return u["name"] + (f" (@{u['username']})" if u["username"] else "")

def insert_card(t, a, al, r, img, aid=None):
    try:
        cur = db.execute("INSERT INTO cards(title,artist,album,rarity,image,artist_id) VALUES(?,?,?,?,?,?)",
                         (t[:80], a[:80], al[:80], r, img, aid))
        db.commit(); return cur.lastrowid
    except sqlite3.IntegrityError:
        db.rollback(); return None

def is_admin(uid): return uid in ADMIN_IDS

def fmt_wait(s):
    s = max(0, int(s)); h, r = divmod(s, 3600); m = (r+59)//60
    if m == 60: h, m = h+1, 0
    return f"{h} ч {m} мин" if h else f"{m} мин"

def age_text(j):
    d = max(0, int((time.time()-j)//86400)) if j else 0
    y, r = divmod(d, 365); mo, dd = divmod(r, 30)
    parts = []
    if y: parts.append(f"{y} г.")
    if mo: parts.append(f"{mo} мес.")
    if not parts: parts.append(f"{dd} дн." if dd else "меньше дня")
    return " ".join(parts)

def pct(a, b): return round(a*100/b) if b else 0
def today(): return dt.datetime.utcnow().strftime("%Y-%m-%d")
def add_xp(uid, n): db.execute("UPDATE users SET xp=xp+? WHERE user_id=?", (n, uid))

# ── Deezer ──
DZ = "https://api.deezer.com/"
class DzErr(Exception):
    def __init__(self, m, c=None): super().__init__(m); self.code = c

def dz_get(path, **params):
    url = DZ + path + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r: data = json.loads(r.read())
    except urllib.error.HTTPError as e: raise DzErr(f"HTTP {e.code}", e.code)
    except urllib.error.URLError as e: raise DzErr(f"нет связи: {e.reason}")
    if isinstance(data, dict) and data.get("error"):
        raise DzErr(data["error"].get("message", "ошибка"), data["error"].get("code"))
    return data

def parse_ref(t):
    m = re.search(r"deezer\.com/(?:[a-z]{2}/)?artist/(\d+)", t or "")
    if m: return m.group(1)
    m = re.search(r"^(\d+)$", (t or "").strip())
    return m.group(1) if m else None

def dz_collect(aid):
    art = dz_get(f"artist/{aid}")
    name = art.get("name") or "?"
    img = art.get("picture_xl") or art.get("picture_big")
    albums, idx = [], 0
    while idx < 1000:
        res = dz_get(f"artist/{aid}/albums", limit=100, index=idx)
        items = res.get("data") or []; albums += items
        if len(items) < 100: break
        idx += 100
    tracks, seen = [], set()
    for al in albums:
        an = al.get("title") or ""
        im = al.get("cover_xl") or al.get("cover_big") or img
        i = 0
        while i < 500:
            res = dz_get(f"album/{al['id']}/tracks", limit=100, index=i)
            items = res.get("data") or []
            for t in items:
                ti = (t.get("title") or "").strip()
                k = ti.lower()
                if not k or k in seen: continue
                cs = t.get("contributors") or []
                if cs and str(aid) not in [str(c.get("id")) for c in cs]: continue
                seen.add(k); tracks.append((ti, an or ti, im))
            if len(items) < 100: break
            i += 100
    return name, img, tracks, len(albums)

def assign_rar(seed, titles):
    order = sorted(titles, key=lambda t: hashlib.md5(f"{seed}|{t}".encode()).hexdigest())
    n = len(order)
    nl = max(1, round(n * RARITIES["legendary"][0] / 100)) if n else 0
    ne = round(n * RARITIES["epic"][0] / 100)
    nr = round(n * RARITIES["rare"][0] / 100)
    out = {}
    for i, t in enumerate(order):
        out[t] = ("legendary" if i < nl else "epic" if i < nl+ne else "rare" if i < nl+ne+nr else "common")
    return out

def import_artist(aid):
    name, img, tracks, na = dz_collect(aid)
    dbid = ensure_artist(name, image=img)
    rar = assign_rar(aid, [t[0] for t in tracks])
    added = skipped = 0; stats = {r: 0 for r in RARITIES}
    for t, al, im in tracks:
        if insert_card(t, name, al, rar[t], im, dbid):
            added += 1; stats[rar[t]] += 1
        else: skipped += 1
    return name, na, added, skipped, stats

IMPORT_HELP = ("🎧 <b>Импорт Deezer</b>\n\n"
               "<code>/spotify ссылка_с_deezer.com</code>\n"
               "или <code>/spotify имя артиста</code>")

def cmd_spotify(m, args):
    cid = m["chat"]["id"]
    if not is_admin(m["from"]["id"]): send(cid, "Только админ."); return
    q = args.strip()
    if not q: send(cid, IMPORT_HELP); return
    ref = parse_ref(q)
    if ref:
        send(cid, "⏳ Импортирую…")
        try: name, na, added, skipped, stats = import_artist(ref)
        except DzErr as e: send(cid, f"⚠️ {esc(str(e))}"); return
        send(cid, f"✅ <b>{esc(name)}</b>: {added} из {na} релизов\n"
                  + " · ".join(f"{RARITIES[k][1]}{v}" for k, v in stats.items() if v))
        return
    try: res = dz_get("search/artist", q=q, limit=8)
    except DzErr as e: send(cid, f"⚠️ {esc(str(e))}"); return
    items = res.get("data") or []
    if not items: send(cid, "Не нашёл."); return
    rows = [[btn(f"{a['name'][:40]} · {a.get('nb_album','?')}", f"dza:{a['id']}")] for a in items[:8]]
    send(cid, "Выбери:", kb(rows))

def cb_deezer(cq, parts):
    cid = (cq.get("message") or {}).get("chat",{}).get("id", cq["from"]["id"])
    if parts[0] == "dza" and len(parts) == 2:
        answer_cb(cq["id"], "Импортирую…"); edit_menu(cq, "⏳ Импорт…")
        try: name, na, added, skipped, stats = import_artist(parts[1])
        except DzErr as e: send(cid, f"⚠️ {esc(str(e))}"); return
        send(cid, f"✅ <b>{esc(name)}</b>: {added} из {na}\n" + " · ".join(f"{RARITIES[k][1]}{v}" for k,v in stats.items() if v))

# ── АРТИСТЫ ──
def artist_text(a):
    lines = [f"🎤 <b>{esc(a['name'])}</b>", ""]
    if a["description"]: lines += [esc(a["description"]), ""]
    t = db.execute("SELECT COUNT(*) FROM cards WHERE artist_id=?", (a["id"],)).fetchone()[0]
    by_r = {}
    for r in db.execute("SELECT rarity, COUNT(*) n FROM cards WHERE artist_id=? GROUP BY rarity", (a["id"],)):
        by_r[r["rarity"]] = r["n"]
    lines.append(f"🎵 Треков: <b>{t}</b>")
    for k, v in RARITIES.items():
        if by_r.get(k): lines.append(f"{v[1]} {v[3]}: {by_r[k]}")
    return "\n".join(lines)

def photo_of(m):
    if m.get("photo"): return m["photo"][-1]["file_id"]
    rp = m.get("reply_to_message") or {}
    if rp.get("photo"): return rp["photo"][-1]["file_id"]
    return None

def cmd_addartist(m, args):
    cid = m["chat"]["id"]
    if not is_admin(m["from"]["id"]): send(cid, "Только админ."); return
    p = [x.strip() for x in args.split("|", 1)]
    if not p or not p[0]: send(cid, "Формат: <code>/addartist Имя | описание</code>"); return
    name = p[0][:80]; desc = p[1][:400] if len(p) > 1 else None
    img = photo_of(m); a = find_artist(name)
    if a:
        db.execute("UPDATE artists SET description=COALESCE(?,description), image=COALESCE(?,image) WHERE id=?", (desc, img, a["id"]))
        db.commit(); send(cid, f"✅ Обновлён: #{a['id']} {esc(name)}"); return
    aid = ensure_artist(name, image=img, desc=desc)
    send(cid, f"✅ Добавлен: #{aid} {esc(name)}")

def cmd_artists(m, args):
    cid = m["chat"]["id"]
    rows = db.execute("SELECT a.id, a.name, (SELECT COUNT(*) FROM cards c WHERE c.artist_id=a.id) n FROM artists a ORDER BY a.name").fetchall()
    if not rows: send(cid, "Нет артистов. /addartist или /spotify"); return
    bs = [btn(f"{r['name'][:30]} · {r['n']}", f"ar:{r['id']}") for r in rows]
    send(cid, f"🎤 <b>Артисты ({len(rows)})</b>", kb([bs[i:i+2] for i in range(0, len(bs), 2)]))

def cb_artist(cq, aid):
    a = get_artist(aid)
    cid = (cq.get("message") or {}).get("chat",{}).get("id", cq["from"]["id"])
    if not a: answer_cb(cq["id"], "Нет.", True); return
    markup = kb([[btn("◀ Артисты", "ar:list")]])
    if a["image"]: send_media(cid, "photo", a["image"], artist_text(a), markup)
    else: send(cid, artist_text(a), markup)
    answer_cb(cq["id"])

def cb_artists_list(cq):
    cid = (cq.get("message") or {}).get("chat",{}).get("id", cq["from"]["id"])
    rows = db.execute("SELECT a.id, a.name, (SELECT COUNT(*) FROM cards c WHERE c.artist_id=a.id) n FROM artists a ORDER BY a.name").fetchall()
    if not rows: send(cid, "Пусто"); answer_cb(cq["id"]); return
    bs = [btn(f"{r['name'][:30]} · {r['n']}", f"ar:{r['id']}") for r in rows]
    edit_menu(cq, f"🎤 <b>Артисты ({len(rows)})</b>", kb([bs[i:i+2] for i in range(0, len(bs), 2)]))
    answer_cb(cq["id"])

def cmd_delartist(m, args):
    cid = m["chat"]["id"]
    if not is_admin(m["from"]["id"]): send(cid, "Только админ."); return
    if not args.strip().isdigit(): send(cid, "/delartist ID"); return
    a = get_artist(int(args.strip()))
    if not a: send(cid, "Нет."); return
    ids = [r["id"] for r in db.execute("SELECT id FROM cards WHERE artist_id=?", (a["id"],))]
    for c in ids:
        db.execute("DELETE FROM inventory WHERE card_id=?", (c,))
        db.execute("DELETE FROM cards WHERE id=?", (c,))
    db.execute("DELETE FROM artists WHERE id=?", (a["id"],)); db.commit()
    send(cid, f"🗑 {esc(a['name'])} и {len(ids)} треков")

def cmd_setartistcover(m, args):
    cid = m["chat"]["id"]
    if not is_admin(m["from"]["id"]): send(cid, "Только админ."); return
    name = args.strip(); img = photo_of(m)
    if not name or not img: send(cid, "Формат: фото с <code>/setartistcover Имя</code>"); return
    a = find_artist(name)
    if not a: send(cid, "Не найден."); return
    db.execute("UPDATE artists SET image=? WHERE id=?", (img, a["id"])); db.commit()
    send(cid, f"🖼 {esc(a['name'])}")

# ── ПРОМОКОДЫ ──
def cmd_promo(m, args):
    uid, cid = m["from"]["id"], m["chat"]["id"]
    code = (args or "").strip().upper()
    if not code: send(cid, "🎟 /promo КОД"); return
    p = db.execute("SELECT * FROM promocodes WHERE code=?", (code,)).fetchone()
    if not p: send(cid, "❌ Нет такого."); return
    if p["uses_left"] == 0: send(cid, "❌ Исчерпан."); return
    if db.execute("SELECT 1 FROM promocode_uses WHERE user_id=? AND code=?", (uid, code)).fetchone():
        send(cid, "❌ Уже использовал."); return
    db.execute("UPDATE users SET coins=coins+? WHERE user_id=?", (p["reward"], uid))
    db.execute("INSERT INTO promocode_uses(user_id,code,used_at) VALUES(?,?,?)", (uid, code, int(time.time())))
    if p["uses_left"] > 0: db.execute("UPDATE promocodes SET uses_left=uses_left-1 WHERE code=?", (code,))
    db.commit()
    bal = db.execute("SELECT coins FROM users WHERE user_id=?", (uid,)).fetchone()[0]
    send(cid, f"🎟 <b>Активирован!</b>\n💰 +{p['reward']}\nБаланс: <b>{bal}</b>")

def cmd_addpromo(m, args):
    cid = m["chat"]["id"]
    if not is_admin(m["from"]["id"]): send(cid, "Только админ."); return
    p = args.split()
    if len(p) < 2 or not p[1].isdigit(): send(cid, "/addpromo КОД 5000 [кол]"); return
    code = p[0].strip().upper(); rw = int(p[1])
    uses = int(p[2]) if len(p) > 2 and p[2].lstrip("-").isdigit() else -1
    db.execute("INSERT INTO promocodes(code,reward,uses_left,created) VALUES(?,?,?,?) "
               "ON CONFLICT(code) DO UPDATE SET reward=excluded.reward, uses_left=excluded.uses_left",
               (code, rw, uses, int(time.time())))
    db.commit()
    send(cid, f"✅ {code}: +{rw}, активаций: {'∞' if uses < 0 else uses}")

def cmd_delpromo(m, args):
    cid = m["chat"]["id"]
    if not is_admin(m["from"]["id"]): send(cid, "Только админ."); return
    code = (args or "").strip().upper()
    if not code: send(cid, "/delpromo КОД"); return
    r = db.execute("DELETE FROM promocodes WHERE code=?", (code,)); db.commit()
    send(cid, f"🗑 {code}" if r.rowcount else "Не найден.")

def cmd_promos(m, args):
    cid = m["chat"]["id"]
    if not is_admin(m["from"]["id"]): send(cid, "Только админ."); return
    rows = db.execute("SELECT * FROM promocodes ORDER BY created DESC").fetchall()
    if not rows: send(cid, "Пусто"); return
    lines = ["🎟 <b>Промокоды</b>\n"]
    for r in rows:
        used = db.execute("SELECT COUNT(*) FROM promocode_uses WHERE code=?", (r["code"],)).fetchone()[0]
        lines.append(f"<code>{esc(r['code'])}</code> +{r['reward']} · использован: {used}"
                     + ("" if r["uses_left"] < 0 else f" · осталось: {r['uses_left']}"))
    send_long(cid, lines)

# ── РЕФЕРАЛЫ ──
def ref_link(uid): return f"https://t.me/{BOT_USERNAME}?start=ref_{uid}"

def process_ref(new_uid, arg):
    if not arg or not arg.startswith("ref_"): return False, None
    try: rid = int(arg[4:])
    except ValueError: return False, None
    if rid == new_uid: return False, None
    if db.execute("SELECT 1 FROM referrals WHERE invited_id=?", (new_uid,)).fetchone(): return False, None
    if not get_user(rid): return False, None
    db.execute("INSERT INTO referrals(invited_id,referrer_id,rewarded,created) VALUES(?,?,?,?)",
               (new_uid, rid, REF_BONUS, int(time.time())))
    db.execute("UPDATE users SET coins=coins+?, ref_count=ref_count+1, ref_earned=ref_earned+? WHERE user_id=?",
               (REF_BONUS, REF_BONUS, rid))
    db.execute("UPDATE users SET referred_by=? WHERE user_id=?", (rid, new_uid))
    db.commit(); return True, rid

def cmd_ref(m, args):
    uid, cid = m["from"]["id"], m["chat"]["id"]
    u = get_user(uid); link = ref_link(uid)
    invited = db.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id=?", (uid,)).fetchone()[0]
    lines = ["🎁 <b>Рефералы</b>", "",
             f"За друга — <b>+{REF_BONUS}</b> монет", "",
             f"👥 Приглашено: <b>{invited}</b>",
             f"💰 Заработано: <b>{u['ref_earned'] or 0}</b>", "",
             "Твоя ссылка:", f"<code>{link}</code>"]
    st = quote("Заходи 🎧")
    markup = kb([
        [{"text": "📤 Поделиться", "url": f"https://t.me/share/url?url={quote(link)}&text={st}"}],
        [btn("🔄 Обновить", "ref:refresh")]])
    send(cid, "\n".join(lines), markup)

# ── STARS + МЕГА ──
def is_sub(u): return bool(u and u["sub_until"] and u["sub_until"] > time.time())

def sub_mult(u):
    if not is_sub(u): return 1.0
    return SUB_P_MULT if u["sub_tier"] == "premium" else SUB_B_MULT

def sub_label(t):
    if t == "premium": return f"💎 Premium ×{SUB_P_MULT}"
    if t == "basic": return f"💚 Basic ×{SUB_B_MULT}"
    return "—"

def subscribe_text(uid):
    u = get_user(uid)
    lines = ["⭐ <b>Подписки и донаты</b>", ""]
    if is_sub(u):
        until = dt.datetime.fromtimestamp(u["sub_until"]).strftime("%d.%m.%Y")
        lines.append(f"🟢 Активна: <b>{sub_label(u['sub_tier'])}</b> до {until}\n")
    lines += [f"💚 <b>Basic</b> — {SUB_B_STARS}⭐ / {SUB_DAYS}д · ×{SUB_B_MULT}",
              f"💎 <b>Premium</b> — {SUB_P_STARS}⭐ / {SUB_DAYS}д · ×{SUB_P_MULT}",
              "",
              f"💥 <b>МЕЕЕЕГАСУПЕРАКЦИИИЯ!!!!!!!</b>",
              f"   <b>{MEGA_COINS}</b> монет за <b>{MEGA_STARS}</b>⭐ — сразу! 🐶🔥"]
    return "\n".join(lines)

def sub_kb():
    return kb([
        [btn(f"💚 Basic · {SUB_B_STARS}⭐", "sub:buy:basic")],
        [btn(f"💎 Premium · {SUB_P_STARS}⭐", "sub:buy:premium")],
        [btn(f"💥 МЕЕЕЕГАСУПЕРАКЦИИИЯ!!!!!!! · {MEGA_STARS}⭐", "sub:buy:mega")]])

def cmd_subscribe(m, args):
    cid, uid = m["chat"]["id"], m["from"]["id"]
    send(cid, subscribe_text(uid), sub_kb())

def send_invoice(cid, uid, tier):
    if tier == "basic":
        stars, title = SUB_B_STARS, f"Basic ×{SUB_B_MULT}"
        desc = f"Множитель ×{SUB_B_MULT} на {SUB_DAYS}д"
    elif tier == "premium":
        stars, title = SUB_P_STARS, f"Premium ×{SUB_P_MULT}"
        desc = f"Множитель ×{SUB_P_MULT} на {SUB_DAYS}д"
    elif tier == "mega":
        stars, title = MEGA_STARS, f"💥 МЕГА · {MEGA_COINS} монет"
        desc = f"{MEGA_COINS} монет сразу! 🐶🔥"
    else: send(cid, "?"); return
    payload = f"sub|{tier}|{uid}|{int(time.time())}"
    try: tg("sendInvoice", chat_id=cid, title=title, description=desc, payload=payload,
            currency="XTR", prices=[{"label": title, "amount": stars}])
    except TgErr as e: say(f"sendInvoice: {e}"); send(cid, "Ошибка счёта")

def cb_sub(cq, action):
    uid = cq["from"]["id"]
    cid = (cq.get("message") or {}).get("chat",{}).get("id", uid)
    if action == "menu":
        edit_menu(cq, subscribe_text(uid), sub_kb()); answer_cb(cq["id"])
    elif action.startswith("buy:"):
        send_invoice(cid, uid, action.split(":",1)[1]); answer_cb(cq["id"])
    else: answer_cb(cq["id"])

def on_pre_checkout(p):
    try: tg("answerPreCheckoutQuery", pre_checkout_query_id=p["id"], ok=True)
    except TgErr: pass

def on_paid(m):
    sp = m["successful_payment"]; uid = m["from"]["id"]; cid = m["chat"]["id"]
    payload = sp.get("invoice_payload", ""); charge = sp.get("telegram_payment_charge_id","")
    amount = int(sp.get("total_amount", 0))
    if charge and db.execute("SELECT 1 FROM payments WHERE charge_id=?", (charge,)).fetchone():
        return
    parts = payload.split("|")
    tier = parts[1] if len(parts) >= 2 and parts[0] == "sub" else "premium"
    if tier not in ("basic","premium","mega"): tier = "premium"

    if tier == "mega":
        db.execute("UPDATE users SET coins=coins+? WHERE user_id=?", (MEGA_COINS, uid))
        try:
            db.execute("INSERT INTO payments(charge_id,user_id,tier,stars,days,created) VALUES(?,?,?,?,?,?)",
                       (charge, uid, tier, amount, 0, int(time.time())))
        except sqlite3.IntegrityError: pass
        db.commit()
        bal = db.execute("SELECT coins FROM users WHERE user_id=?", (uid,)).fetchone()[0]
        send(cid, f"💥 <b>МЕЕЕЕГАСУПЕРАКЦИИИЯ АКТИВИРОВАНА!!!!!!!</b>\n\n"
                  f"💰 +<b>{MEGA_COINS}</b> монет\n🐶 Охае, даттебаё, сабака кракена!\n💳 Баланс: <b>{bal}</b>\n\n"
                  f"Крути на все! 🔥🎴")
        for a in ADMIN_IDS:
            try: send(a, f"💥 МЕГА-ПОКУПКА\n{esc(who(uid))}\n+{MEGA_COINS} за {amount}⭐")
            except TgErr: pass
        return

    u = get_user(uid); now = int(time.time())
    same = is_sub(u) and u["sub_tier"] == tier
    new_until = (u["sub_until"] + SUB_DAYS*86400) if same else (now + SUB_DAYS*86400)
    db.execute("UPDATE users SET sub_tier=?, sub_until=? WHERE user_id=?", (tier, new_until, uid))
    try:
        db.execute("INSERT INTO payments(charge_id,user_id,tier,stars,days,created) VALUES(?,?,?,?,?,?)",
                   (charge, uid, tier, amount, SUB_DAYS, now))
    except sqlite3.IntegrityError: pass
    db.commit()
    until = dt.datetime.fromtimestamp(new_until).strftime("%d.%m.%Y")
    send(cid, f"✅ Оплата!\n{sub_label(tier)}\n⭐ {amount}\n📅 {until}")
    for a in ADMIN_IDS:
        try: send(a, f"💰 Подписка\n{esc(who(uid))}\n{tier}\n{amount}⭐")
        except TgErr: pass

# ── КАНАЛЫ ──
CH = {
    1: {"set": "sub_channel", "rw": "ch_reward", "tbl": "channel_rewards", "def": CH1_R, "lbl": "📢 Канал #1", "e": "📢"},
    2: {"set": "sub_channel2", "rw": "ch_reward2", "tbl": "channel2_rewards", "def": CH2_R, "lbl": "📣 Канал #2", "e": "📣"},
}

def ch_set(s): return get_setting(CH[s]["set"])

def ch_rw(s=1):
    v = get_setting(CH[s]["rw"])
    try: return int(v) if v else CH[s]["def"]
    except: return CH[s]["def"]

def ch_url(c): return c if c.startswith("http") else "https://t.me/" + c.lstrip("@")

def ch_claimed(uid, s):
    return bool(db.execute(f"SELECT 1 FROM {CH[s]['tbl']} WHERE user_id=? AND claimed=1", (uid,)).fetchone())

def ch_mark(uid, s):
    db.execute(f"INSERT OR REPLACE INTO {CH[s]['tbl']}(user_id,claimed,created) VALUES(?,1,?)", (uid, int(time.time())))

def ch_check(channel, uid):
    try: r = tg("getChatMember", chat_id=channel, user_id=uid)
    except TgErr as e: say(f"getChatMember: {e}"); return None
    st = r.get("status")
    if st in ("creator","administrator","member"): return True
    if st == "restricted": return bool(r.get("is_member"))
    return False

def chs_text(uid):
    act = [s for s in (1,2) if ch_set(s)]
    if not act: return "📢 <b>Подписка на каналы</b>\n\nНе настроено.", None
    lines = ["📢 <b>Подписка на каналы</b>", ""]
    bs = []
    for s in act:
        c = CH[s]; rw = ch_rw(s); got = ch_claimed(uid, s)
        lines += ["━━━━━━━━━━━━━━━━━━", c["lbl"], f"Награда: <b>+{rw}</b> (один раз)"]
        lines.append("✅ получена" if got else "<i>Подпишись и проверь</i>")
        lines.append("")
        bs.append([{"text": f"{c['e']} Перейти в #{s}", "url": ch_url(ch_set(s))}])
        if got: bs.append([btn(f"✅ #{s} получено", "noop")])
        else: bs.append([btn(f"✅ Проверить #{s}", f"chsub:check:{s}")])
    return "\n".join(lines), kb(bs)

def cmd_channelsub(m, args):
    t, mk = chs_text(m["from"]["id"]); send(m["chat"]["id"], t, mk)

def cb_chsub(cq, slot):
    uid = cq["from"]["id"]; cid = (cq.get("message") or {}).get("chat",{}).get("id", uid)
    ch = ch_set(slot)
    if not ch: answer_cb(cq["id"], "Не настроен.", True); return
    if ch_claimed(uid, slot): answer_cb(cq["id"], "Уже 🙂", True); return
    ok = ch_check(ch, uid)
    if ok is None: answer_cb(cq["id"], "Бот админ канала?", True); return
    if not ok: answer_cb(cq["id"], "Не подписан 😔", True); return
    rw = ch_rw(slot)
    db.execute("UPDATE users SET coins=coins+? WHERE user_id=?", (rw, uid))
    ch_mark(uid, slot); db.commit()
    send(cid, f"🎉 <b>+{rw} монет</b>!"); answer_cb(cq["id"], "Получено!")
    t, mk = chs_text(uid); edit_menu(cq, t, mk)

def _set_ch(cid, slot, args):
    a = (args or "").strip(); c = CH[slot]
    if not a or a.lower() in ("off","reset","none"):
        set_setting(c["set"], None); send(cid, f"{c['e']} {c['lbl']} отключён."); return
    set_setting(c["set"], a)
    send(cid, f"✅ {c['lbl']} — <code>{esc(a)}</code>\n⚠️ Бот должен быть админом!\nНаграда: +{ch_rw(slot)}")

def cmd_setchannel(m, args):
    if not is_admin(m["from"]["id"]): send(m["chat"]["id"], "Только админ."); return
    _set_ch(m["chat"]["id"], 1, args)

def cmd_setchannel2(m, args):
    if not is_admin(m["from"]["id"]): send(m["chat"]["id"], "Только админ."); return
    _set_ch(m["chat"]["id"], 2, args)

def _set_rw(cid, slot, args):
    a = (args or "").strip()
    if not a.isdigit() or int(a) <= 0: send(cid, f"/setchreward{'2' if slot==2 else ''} 2000"); return
    set_setting(CH[slot]["rw"], a); send(cid, f"✅ {CH[slot]['lbl']}: +{a}")

def cmd_setchreward(m, args):
    if not is_admin(m["from"]["id"]): send(m["chat"]["id"], "Только админ."); return
    _set_rw(m["chat"]["id"], 1, args)

def cmd_setchreward2(m, args):
    if not is_admin(m["from"]["id"]): send(m["chat"]["id"], "Только админ."); return
    _set_rw(m["chat"]["id"], 2, args)

# ── ДОСТИЖЕНИЯ ──
def user_stats(uid):
    tg_total = db.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
    uniq = db.execute("SELECT COUNT(*) FROM inventory WHERE user_id=? AND qty>0", (uid,)).fetchone()[0]
    owned = db.execute("SELECT COALESCE(SUM(qty),0) FROM inventory WHERE user_id=?", (uid,)).fetchone()[0]
    by_r = {k: db.execute("SELECT COUNT(*) FROM inventory i JOIN cards c ON c.id=i.card_id "
                          "WHERE i.user_id=? AND i.qty>0 AND c.rarity=?", (uid, k)).fetchone()[0]
            for k in RARITIES}
    trades = db.execute("SELECT COUNT(*) FROM trades WHERE status='accepted' AND (from_id=? OR to_id=?)",
                        (uid, uid)).fetchone()[0]
    u = get_user(uid)
    return {"tg": tg_total, "uniq": uniq, "owned": owned, "by_r": by_r, "trades": trades,
            "streak": u["open_streak"] if u else 0}

def check_ach(uid):
    s = user_stats(uid)
    have = {r["code"] for r in db.execute("SELECT code FROM achievements WHERE user_id=?", (uid,))}
    earned = []
    def g(c):
        if c not in have:
            db.execute("INSERT INTO achievements(user_id,code,got) VALUES(?,?,?)", (uid, c, int(time.time())))
            earned.append(c)
    if s["uniq"] >= 1: g("first")
    if s["uniq"] >= 10: g("ten")
    if s["uniq"] >= 50: g("fifty")
    if s["tg"] and s["uniq"]*2 >= s["tg"]: g("half")
    if s["tg"] and s["uniq"] >= s["tg"]: g("full")
    if s["by_r"].get("common",0) >= 10: g("c10")
    if s["by_r"].get("rare",0) >= 10: g("r10")
    if s["by_r"].get("epic",0) >= 5: g("e5")
    if s["by_r"].get("legendary",0) >= 1: g("l1")
    if s["trades"] >= 1: g("trade1")
    if s["streak"] >= 7: g("fire7")
    if s["owned"] >= 100: g("rich100")
    db.commit(); return earned

def notify_ach(cid, earned):
    for c in earned:
        e = ACH.get(c)
        if e: send(cid, f"🏅 <b>Достижение!</b>\n{e[0]} {e[1]} — {e[2]}")
    if earned: notify_quests(cid, prog_quest(cid, "ach1", 1))

def cmd_ach(m, args):
    uid, cid = m["from"]["id"], m["chat"]["id"]
    rows = {r["code"]: r["got"] for r in db.execute("SELECT code, got FROM achievements WHERE user_id=?", (uid,))}
    s = user_stats(uid)
    lines = [f"🏅 <b>Достижения</b>: {len(rows)}/{len(ACH)}\n"]
    for c, (e, n, d) in ACH.items():
        if c in rows:
            w = dt.datetime.fromtimestamp(rows[c]).strftime("%d.%m.%y")
            lines.append(f"✅ {e} <b>{n}</b> — <i>{w}</i>")
        else: lines.append(f"🔒 {e} <b>{n}</b> — <i>{d}</i>")
    lines += ["", f"📊 {s['uniq']}/{s['tg']}", f"🎁 {s['owned']}", f"🔥 {s['streak']} дн."]
    send_long(cid, lines)

# ── ТИТУЛЫ ──
def compute_titles(uid):
    s = user_stats(uid)
    have = set()
    ach = {r["code"] for r in db.execute("SELECT code FROM achievements WHERE user_id=?", (uid,))}
    if s["uniq"] >= 1: have.add("newbie")
    if s["uniq"] >= 10: have.add("meloman")
    if s["uniq"] >= 25: have.add("collector")
    if s["uniq"] >= 50: have.add("master")
    if s["tg"] and s["uniq"] >= s["tg"]: have.add("legend")
    if s["streak"] >= 7: have.add("devoted")
    if s["trades"] >= 5: have.add("trader")
    if s["owned"] >= 100: have.add("rich")
    if len(ach) >= 5: have.add("chosen")
    return have

def best_title(uid):
    have = compute_titles(uid)
    for c in TITLE_ORDER:
        if c in have: return c
    return None

def current_title(uid):
    u = get_user(uid); ch = u["title"] if u else None
    have = compute_titles(uid)
    if ch and ch in have: return ch
    return best_title(uid)

def title_str(uid):
    c = current_title(uid)
    if not c: return ""
    e, n, _ = TITLES[c]; return f"{e} <b>{n}</b>"

def cmd_titles(m, args):
    uid, cid = m["from"]["id"], m["chat"]["id"]
    have = compute_titles(uid); cur = current_title(uid)
    lines = [f"🏷 <b>Титулы</b>: {len(have)}/{len(TITLES)}\n"]
    bs = []
    for c in TITLE_ORDER:
        e, n, cond = TITLES[c]
        if c in have:
            mk = "✅" if c == cur else "🔓"
            lines.append(f"{mk} {e} <b>{n}</b>")
            bs.append(btn(f"{e} {n}", f"ti:{c}"))
        else: lines.append(f"🔒 {e} <b>{n}</b> — <i>{cond}</i>")
    lines += ["", "Нажми — активировать"]
    send_long(cid, lines, kb([bs[i:i+2] for i in range(0, len(bs), 2)]))

def cb_title(cq, code):
    uid = cq["from"]["id"]
    if code not in compute_titles(uid) or code not in TITLES:
        answer_cb(cq["id"], "Не открыт.", True); return
    db.execute("UPDATE users SET title=? WHERE user_id=?", (code, uid)); db.commit()
    e, n, _ = TITLES[code]; answer_cb(cq["id"], f"✅ {e} {n}", True)

# ── КВЕСТЫ ──
def ensure_quests(uid):
    day = today()
    if db.execute("SELECT code FROM quests WHERE user_id=? AND day=?", (uid, day)).fetchall(): return
    for c, e, d, t, xp, b in random.sample(QUESTS, 3):
        db.execute("INSERT OR IGNORE INTO quests(user_id,day,code,progress,target,xp,done) VALUES(?,?,?,0,?,?,0)",
                   (uid, day, c, t, xp))
    db.commit()

def quest_info(c):
    for cc, e, d, t, xp, b in QUESTS:
        if cc == c: return {"e": e, "d": d, "t": t, "xp": xp, "b": b}
    return None

def prog_quest(uid, code, amt=1):
    day = today(); ensure_quests(uid)
    r = db.execute("SELECT * FROM quests WHERE user_id=? AND day=? AND code=?", (uid, day, code)).fetchone()
    if not r or r["done"]: return []
    np = r["progress"] + amt
    done = 1 if np >= r["target"] else 0
    db.execute("UPDATE quests SET progress=?, done=? WHERE user_id=? AND day=? AND code=?",
               (np, done, uid, day, code))
    if done: add_xp(uid, r["xp"])
    db.commit()
    if not done: return []
    info = quest_info(code)
    if info and info["b"] == "card":
        pool = db.execute("SELECT * FROM cards").fetchall()
        if pool: add_card(uid, random.choice(pool)["id"], 1); db.commit()
    return [(code, info)]

def notify_quests(cid, done):
    for c, info in done:
        if not info: continue
        ex = " + 🎴!" if info["b"] == "card" else ""
        send(cid, f"🎯 <b>Квест выполнен!</b>\n{info['e']} {info['d']} — +{info['xp']} XP{ex}")

def cmd_quests(m, args):
    uid, cid = m["from"]["id"], m["chat"]["id"]
    ensure_quests(uid); day = today()
    rows = db.execute("SELECT * FROM quests WHERE user_id=? AND day=? ORDER BY code", (uid, day)).fetchall()
    xp = db.execute("SELECT xp FROM users WHERE user_id=?", (uid,)).fetchone()["xp"]
    lines = ["🎯 <b>Ежедневные квесты</b>", f"⭐ XP: <code>{xp}</code>", ""]
    for r in rows:
        info = quest_info(r["code"])
        if not info: continue
        s = "✅" if r["done"] else "⏳"
        bd = min(r["progress"], r["target"])
        bar = "▰"*bd + "▱"*(r["target"]-bd)
        lines += [f"{s} {info['e']} <b>{info['d']}</b>", f"    <code>{bar}</code> {bd}/{r['target']}"]
    send_long(cid, lines)

# ── ДРУЗЬЯ ──
def cmd_friends(m, args):
    uid, cid = m["from"]["id"], m["chat"]["id"]
    f = db.execute("SELECT friend_id FROM friends WHERE user_id=? AND status='accepted'", (uid,)).fetchall()
    inc = db.execute("SELECT user_id FROM friends WHERE friend_id=? AND status='pending'", (uid,)).fetchall()
    out = db.execute("SELECT friend_id FROM friends WHERE user_id=? AND status='pending'", (uid,)).fetchall()
    lines = ["👥 <b>Друзья</b>", ""]
    if f:
        lines.append("<b>Друзья:</b>")
        for r in f: lines.append(f"• {esc(who(r['friend_id']))}")
    else: lines.append("Пусто.")
    lines.append("")
    if inc:
        lines.append("<b>Входящие:</b>")
        for r in inc: lines.append(f"• {esc(who(r['user_id']))}")
        lines.append("")
    if out:
        lines.append("<b>Исходящие:</b>")
        for r in out: lines.append(f"• ⏳ {esc(who(r['friend_id']))}")
        lines.append("")
    lines += ["<code>/addfriend @ник</code>", "<code>/delfriend @ник</code>"]
    send_long(cid, lines)

def cmd_addfriend(m, args):
    uid, cid = m["from"]["id"], m["chat"]["id"]
    a = (args or "").strip()
    if not a.startswith("@"): send(cid, "/addfriend @ник"); return
    t = db.execute("SELECT * FROM users WHERE username=?", (a[1:].lower(),)).fetchone()
    if not t: send(cid, "Нет"); return
    if t["user_id"] == uid: send(cid, "С собой 🙂"); return
    r = db.execute("SELECT status FROM friends WHERE user_id=? AND friend_id=?", (uid, t["user_id"])).fetchone()
    if r: send(cid, "Уже друзья." if r["status"]=="accepted" else "Уже отправлено."); return
    opp = db.execute("SELECT status FROM friends WHERE user_id=? AND friend_id=?", (t["user_id"], uid)).fetchone()
    if opp and opp["status"] == "pending":
        db.execute("UPDATE friends SET status='accepted' WHERE user_id=? AND friend_id=?", (t["user_id"], uid))
        db.execute("INSERT INTO friends(user_id,friend_id,status,created) VALUES(?,?,?,?)",
                   (uid, t["user_id"], "accepted", int(time.time())))
        db.commit(); send(cid, f"✅ Друзья с {esc(who(t['user_id']))}!")
        try: send(t["user_id"], f"✅ {esc(who(uid))} принял!")
        except TgErr: pass
        return
    db.execute("INSERT INTO friends(user_id,friend_id,status,created) VALUES(?,?,?,?)",
               (uid, t["user_id"], "pending", int(time.time())))
    db.commit()
    mk = kb([[btn("✅ Принять", f"f:y:{uid}"), btn("❌ Отклонить", f"f:n:{uid}")]])
    try: send(t["user_id"], f"👥 <b>{esc(who(uid))}</b> хочет в друзья", mk)
    except TgErr: send(cid, "Не получилось"); return
    send(cid, "📨 Отправлено.")

def cmd_delfriend(m, args):
    uid, cid = m["from"]["id"], m["chat"]["id"]
    a = (args or "").strip()
    if not a.startswith("@"): send(cid, "/delfriend @ник"); return
    t = db.execute("SELECT * FROM users WHERE username=?", (a[1:].lower(),)).fetchone()
    if not t: send(cid, "Нет"); return
    db.execute("DELETE FROM friends WHERE user_id=? AND friend_id=?", (uid, t["user_id"]))
    db.execute("DELETE FROM friends WHERE user_id=? AND friend_id=?", (t["user_id"], uid))
    db.commit(); send(cid, f"🗑 {esc(who(t['user_id']))} удалён.")

def cb_friend(cq, action, other):
    uid = cq["from"]["id"]
    if uid == other: answer_cb(cq["id"], "Твоя.", True); return
    if action == "a":
        msg = cq.get("message") or {}
        if msg.get("message_id") and msg.get("chat"): clear_kb(msg["chat"]["id"], msg["message_id"])
        opp = db.execute("SELECT status FROM friends WHERE user_id=? AND friend_id=?", (other, uid)).fetchone()
        if opp and opp["status"] == "pending":
            db.execute("UPDATE friends SET status='accepted' WHERE user_id=? AND friend_id=?", (other, uid))
            db.execute("INSERT INTO friends(user_id,friend_id,status,created) VALUES(?,?,?,?)", (uid, other, "accepted", int(time.time())))
            db.commit(); send(msg["chat"]["id"], f"✅ Друзья с {esc(who(other))}!")
            try: send(other, f"✅ {esc(who(uid))} принял!")
            except TgErr: pass
            answer_cb(cq["id"]); return
        ex = db.execute("SELECT status FROM friends WHERE user_id=? AND friend_id=?", (uid, other)).fetchone()
        if ex and ex["status"] == "accepted": answer_cb(cq["id"], "Уже друзья.", True); return
        if not ex:
            db.execute("INSERT INTO friends(user_id,friend_id,status,created) VALUES(?,?,?,?)", (uid, other, "pending", int(time.time())))
            db.commit()
        mk = kb([[btn("✅ Принять", f"f:y:{uid}"), btn("❌ Отклонить", f"f:n:{uid}")]])
        try: send(other, f"👥 <b>{esc(who(uid))}</b> хочет в друзья", mk)
        except TgErr: pass
        answer_cb(cq["id"], "Отправлено"); return
    r = db.execute("SELECT status FROM friends WHERE user_id=? AND friend_id=?", (other, uid)).fetchone()
    if not r or r["status"] != "pending": answer_cb(cq["id"], "Уже обработано.", True); return
    msg = cq.get("message") or {}; cid, mid = msg.get("chat",{}).get("id"), msg.get("message_id")
    if action == "y":
        db.execute("UPDATE friends SET status='accepted' WHERE user_id=? AND friend_id=?", (other, uid))
        if not db.execute("SELECT 1 FROM friends WHERE user_id=? AND friend_id=?", (uid, other)).fetchone():
            db.execute("INSERT INTO friends(user_id,friend_id,status,created) VALUES(?,?,?,?)", (uid, other, "accepted", int(time.time())))
        db.commit()
        if cid and mid: edit_text(cid, mid, f"✅ Друзья с {esc(who(other))}.")
        try: send(other, f"✅ {esc(who(uid))} принял!")
        except TgErr: pass
    else:
        db.execute("DELETE FROM friends WHERE user_id=? AND friend_id=?", (other, uid)); db.commit()
        if cid and mid: edit_text(cid, mid, f"❌ Заявка от {esc(who(other))} отклонена.")
        try: send(other, f"❌ {esc(who(uid))} отклонил.")
        except TgErr: pass
    answer_cb(cq["id"])

# ── РАМКИ / ПРОФИЛЬ ──
def frame_for(uid):
    u = db.execute("SELECT avatar_card FROM users WHERE user_id=?", (uid,)).fetchone()
    if not u or not u["avatar_card"]: return ""
    card = get_card(u["avatar_card"])
    if not card: return ""
    s = user_stats(uid)
    ach = db.execute("SELECT COUNT(*) FROM achievements WHERE user_id=?", (uid,)).fetchone()[0]
    if s["tg"] and s["uniq"] >= s["tg"] and s["by_r"].get("legendary",0) >= 2: return SPECIAL["rainbow"]
    if s["tg"] and s["uniq"] >= s["tg"]: return SPECIAL["diamond"]
    if s["streak"] >= 7: return SPECIAL["fire"]
    if card["rarity"] == "legendary" and ach >= 3: return SPECIAL["crown"]
    return FRAMES.get(card["rarity"], "")

def pity_left(c, t): return max(1, t - c)

def claim_info(lc, now=None):
    now = time.time() if now is None else now
    if not lc: return CLAIM_AMOUNT, 0, False
    el = now - lc
    if el < CLAIM_SECONDS: return 0, CLAIM_SECONDS - el, False
    maxed = el >= CLAIM_MAX_SECONDS
    el = min(el, CLAIM_MAX_SECONDS)
    steps = int((el - CLAIM_SECONDS) // STEP)
    nxt = 0 if maxed else STEP - ((el - CLAIM_SECONDS) % STEP)
    return CLAIM_AMOUNT + steps * CLAIM_BONUS, nxt, maxed

def max_claim(): return CLAIM_AMOUNT + CLAIM_BONUS * ((CLAIM_MAX_SECONDS - CLAIM_SECONDS) // STEP)

def profile_text(uid):
    u = get_user(uid)
    tg = db.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
    uniq = db.execute("SELECT COUNT(*) FROM inventory WHERE user_id=? AND qty>0", (uid,)).fetchone()[0]
    owned = db.execute("SELECT COALESCE(SUM(qty),0) FROM inventory WHERE user_id=?", (uid,)).fetchone()[0]
    tr = db.execute("SELECT COUNT(*) FROM trades WHERE status='accepted' AND (from_id=? OR to_id=?)", (uid, uid)).fetchone()[0]
    ach = db.execute("SELECT COUNT(*) FROM achievements WHERE user_id=?", (uid,)).fetchone()[0]
    fr = db.execute("SELECT COUNT(*) FROM friends WHERE user_id=? AND status='accepted'", (uid,)).fetchone()[0]
    lines = [f"👤 <b>{badge(u['equipped'])}{esc(u['name'])}</b>", f"🆔 <code>{uid}</code>"]
    ts = title_str(uid)
    if ts: lines.append(f"🏷 {ts}")
    if u["avatar_card"]:
        ac = get_card(u["avatar_card"])
        if ac: lines.append(f"{frame_for(uid)} {title_of(ac)}")
    lines += ["", f"💰 <b>{u['coins']}</b>", f"⭐ XP: <code>{u['xp'] or 0}</code>",
              f"🏅 {ach}/{len(ACH)}", f"👥 Друзей: {fr}",
              "", f"🎵 Коллекция: <b>{uniq}/{tg}</b> ({pct(uniq, tg)}%)", f"📦 Дубли: {owned}", ""]
    for k in RARITIES:
        tot = db.execute("SELECT COUNT(*) FROM cards WHERE rarity=?", (k,)).fetchone()[0]
        own = db.execute("SELECT COUNT(*) FROM inventory i JOIN cards c ON c.id=i.card_id "
                         "WHERE i.user_id=? AND i.qty>0 AND c.rarity=?", (uid, k)).fetchone()[0]
        lines.append(f"{RARITIES[k][1]} {RARITIES[k][3]}: {own}/{tot} ({pct(own,tot)}%)")
    lines.append("")
    if is_sub(u):
        until = dt.datetime.fromtimestamp(u["sub_until"]).strftime("%d.%m.%Y")
        lines.append(f"⭐ {sub_label(u['sub_tier'])} до {until}")
    for s in (1,2):
        if ch_set(s):
            got = ch_claimed(uid, s)
            lines.append(f"{CH[s]['e']} {CH[s]['lbl']}: {'✅' if got else 'не подписан'}")
    lines += [f"🎯 Гарант: 🟡 через {pity_left(u['pity_leg'], PITY_L)}, 🟣 через {pity_left(u['pity_epic'], PITY_E)}",
              f"🎁 Приглашено: {u['ref_count'] or 0}",
              f"🕰 {age_text(u['joined'])}",
              f"🤝 Обменов: {tr}"]
    return "\n".join(lines)

# ── КЛАВИАТУРЫ ──
def reply_kb(rows):
    return {"keyboard": [[{"text": t} for t in row] for row in rows], "resize_keyboard": True, "is_persistent": True}

CLAIM_LBL = "💰 Забрать"
KBS = {
    "main": [["🎴 Карточки", "🎤 Артисты"], ["💰 Монеты", "🏆 Топ"], ["⭐ Подписка", "📢 Канал"],
             ["🎁 Рефералы", "👤 Профиль"], ["🎯 Квесты", "🏅 Достижения"],
             ["🏷 Титулы", "👥 Друзья"], ["❓ Помощь"]],
    "cards": [["🎲 Открыть", "📚 Коллекция"], ["🔁 Обмен", "💡 Предложить"], ["◀ Назад"]],
    "open": [["🎲 Крутить"], ["◀ Назад"]],
    "shop": [["🛍 Магазин", "🚫 Снять значок"], ["◀ Назад"]],
    "coins": [[CLAIM_LBL, "💳 Баланс"], ["◀ Назад"]],
    "admin": [["➕ Трек", "📋 Заявки"], ["🗂 Карточки", "💿 Помощь"], ["🎧 Deezer", "🎤 Артисты"],
              ["🎟 Промокоды", "◀ Назад"]],
}
LABELS = {
    "🎴 Карточки":"g_cards","💄 Косметика":"g_shop","💰 Монеты":"g_coins","🏆 Топ":"top",
    "👤 Профиль":"home","❓ Помощь":"help","🛠 Админ":"g_admin","⭐ Подписка":"sub_menu",
    "📢 Канал":"chsub_menu","🎁 Рефералы":"ref","🎤 Артисты":"artists","🎯 Квесты":"quests",
    "🏅 Достижения":"ach","🏷 Титулы":"titles","👥 Друзья":"friends","◀ Назад":"back",
    "🎲 Открыть":"g_open","📚 Коллекция":"coll","🔁 Обмен":"trade","💡 Предложить":"suggest",
    "🎲 Крутить":"open:random","🛍 Магазин":"shop","🚫 Снять значок":"unequip",
    CLAIM_LBL:"claim","💳 Баланс":"balance","➕ Трек":"adm_add","📋 Заявки":"adm_queue",
    "🗂 Карточки":"adm_list","💿 Помощь":"adm_album","🎧 Deezer":"adm_spotify","🎟 Промокоды":"promos_menu",
}
ADMIN_ACTIONS = {"g_admin","adm_add","adm_queue","adm_list","adm_album","adm_spotify","promos_menu"}
NAV = {}

def keyboard(uid, name):
    rows = [list(r) for r in KBS[name]]
    if name == "main" and is_admin(uid): rows.append(["🛠 Админ"])
    return reply_kb(rows)

def goto(cid, uid, name, text, priv=True):
    NAV[uid] = name
    send(cid, text, keyboard(uid, name) if priv else None)

def send_home(cid, uid, priv=True):
    NAV[uid] = "main"
    text = profile_text(uid)
    markup = keyboard(uid, "main") if priv else None
    media = get_setting("welcome_media")
    if media:
        k, _, fid = media.partition(":"); send_media(cid, k, fid, text, markup)
    else: send(cid, text, markup)

def cards_text(uid):
    u = get_user(uid)
    return f"🎴 <b>Карточки</b>\nЦена: <b>{OPEN_COST}</b>\n💰 {u['coins']}"

def open_text(uid):
    u = get_user(uid)
    return (f"🎲 Крутить? Цена: {OPEN_COST} · баланс: {u['coins']}\n"
            f"🎯 🟡 {pity_left(u['pity_leg'], PITY_L)} · 🟣 {pity_left(u['pity_epic'], PITY_E)}")

def coins_text(uid):
    u = get_user(uid); mult = sub_mult(u)
    ba = int(CLAIM_AMOUNT * mult); bn = int(CLAIM_BONUS * mult); mx = int(max_claim() * mult)
    if not u["last_claim"]:
        return f"💰 <b>Монеты</b>\nБаланс: <b>{u['coins']}</b>\n✅ Первый сбор: <b>{ba}</b>"
    el = time.time() - u["last_claim"]
    if el < CLAIM_SECONDS:
        return f"💰 <b>Монеты</b>\nБаланс: <b>{u['coins']}</b>\n⏳ Через {fmt_wait(CLAIM_SECONDS-el)} — {ba}"
    amt, nxt, mxed = claim_info(u["last_claim"])
    tail = f"Далее +{bn}/час, макс {mx}"
    if mxed: return f"💰 <b>Монеты</b>\nБаланс: <b>{u['coins']}</b>\n✅ <b>{amt}</b> (макс)\n{tail}"
    return f"💰 <b>Монеты</b>\nБаланс: <b>{u['coins']}</b>\n✅ <b>{amt}</b>\n⏳ +{bn} через {fmt_wait(nxt)}"

def shop_menu(uid):
    u = get_user(uid)
    owned = {r["item"] for r in db.execute("SELECT item FROM owned_cosmetics WHERE user_id=?", (uid,))}
    lines = ["💄 <b>Косметика</b>", f"💰 {u['coins']}", ""]
    bs = []
    for k, (e, n, p) in COSMETICS.items():
        if u["equipped"] == k: lbl = f"🟢{e}"
        elif k in owned: lbl = f"✅{e}"
        else: lbl = f"{e} {p}"
        lines.append(f"{e} {n} — {p}")
        bs.append(btn(lbl, f"cs:{k}"))
    rows = [bs[i:i+3] for i in range(0, len(bs), 3)] + [[btn("🚫 Снять", "cs:off")]]
    return "\n".join(lines), kb(rows)

HELP = ("🎧 <b>Музыкальные карточки</b>\n\n"
        "/claim · /open · /cards · /artists · /ref\n"
        "/promo КОД · /trade · /user @ник · /suggest\n\n"
        "🎧 Импорт: <code>/spotify ссылка_deezer.com</code>")

# ── МОНЕТЫ ──
def do_claim(uid):
    u = get_user(uid); amt, nxt, _ = claim_info(u["last_claim"])
    if amt <= 0: return False, 0, u["coins"], nxt
    db.execute("UPDATE users SET coins=coins+?, last_claim=? WHERE user_id=?", (amt, int(time.time()), uid))
    db.commit(); return True, amt, u["coins"] + amt, 0

def cmd_claim(m, args):
    ok, amt, coins, w = do_claim(m["from"]["id"])
    if ok: send(m["chat"]["id"], f"✅ +{amt}! Баланс: <b>{coins}</b>")
    else: send(m["chat"]["id"], f"⏳ {fmt_wait(w)}. Баланс: {coins}")

# ── ОТКРЫТИЕ ──
def do_open(uid, cid):
    u = get_user(uid)
    if u["coins"] < OPEN_COST: send(cid, f"💸 {OPEN_COST} нужно"); return
    rars = [r[0] for r in db.execute("SELECT DISTINCT rarity FROM cards")]
    if not rars: send(cid, "Нет карточек"); return
    pl, pe = u["pity_leg"], u["pity_epic"]; forced = None
    if pl >= PITY_L - 1 and "legendary" in rars: forced = "legendary"
    elif pe >= PITY_E - 1 and "epic" in rars: forced = "epic"
    rar = forced or random.choices(rars, weights=[RARITIES[r][0] for r in rars])[0]
    if rar == "legendary": pl, pe = 0, 0
    elif rar == "epic": pl, pe = pl+1, 0
    else: pl, pe = pl+1, pe+1
    card = db.execute("SELECT * FROM cards WHERE rarity=? ORDER BY RANDOM() LIMIT 1", (rar,)).fetchone()
    db.execute("UPDATE users SET coins=coins-?, pity_leg=?, pity_epic=? WHERE user_id=?", (OPEN_COST, pl, pe, uid))
    add_card(uid, card["id"], 1); db.commit()
    qty = qty_of(uid, card["id"]); bal = u["coins"] - OPEN_COST
    r = RARITIES[card["rarity"]]
    note = "🆕!" if qty == 1 else f"×{qty}"
    cap = (f"{r[1]} <b>{r[2]}</b>\n🎵 {esc(card['title'])}\n👤 {esc(card['artist'])}\n"
           f"💿 {esc(card['album'])}\nID: <code>{card['id']}</code>\n{note}\n"
           + ("🎯 Гарант!\n" if forced else "")
           + f"💰 {bal}\n🎯 🟡 {pity_left(pl,PITY_L)} · 🟣 {pity_left(pe,PITY_E)}")
    res = send_media(cid, "photo", card["image"], cap)
    img = card["image"]
    if img and img.startswith("http") and isinstance(res, dict) and res.get("photo"):
        db.execute("UPDATE cards SET image=? WHERE image=?", (res["photo"][-1]["file_id"], img)); db.commit()
    for q in ("open3","open5","qty5"):
        notify_quests(cid, prog_quest(uid, q, 1))
    notify_ach(cid, check_ach(uid))

def cmd_open(m, args):
    goto(m["chat"]["id"], m["from"]["id"], "open", open_text(m["from"]["id"]), m["chat"].get("type")=="private")

# ── КОЛЛЕКЦИЯ ──
CTX = {}

def cards_page(uid, rar, page):
    CTX[uid] = (rar, page)
    where, args = "i.user_id=?", [uid]
    if rar != "all": where += " AND c.rarity=?"; args.append(rar)
    base = f"FROM inventory i JOIN cards c ON c.id=i.card_id WHERE {where}"
    n = db.execute(f"SELECT COUNT(*) {base}", args).fetchone()[0]
    pages = max(1, (n+PAGE-1)//PAGE); page = min(max(page,0), pages-1)
    rows = db.execute(f"SELECT c.id,c.title,c.artist,c.album,c.rarity,i.qty {base} "
                      f"ORDER BY {RARITY_SQL.format(c='c.rarity')}, c.artist LIMIT ? OFFSET ?",
                      args + [PAGE, page*PAGE]).fetchall()
    uniq, qty = db.execute("SELECT COUNT(*), COALESCE(SUM(qty),0) FROM inventory WHERE user_id=?", (uid,)).fetchone()
    flt = f" · {RARITIES[rar][1]}" if rar != "all" else ""
    lines = [f"📚 <b>Коллекция</b>: {uniq} треков ({qty} шт.){flt}", "", "👇 Нажми на карточку"]
    if not rows: lines.append("Пусто.")
    def go(rr, p): return f"cp:{rr}:{p}"
    cbs = []
    for r in rows:
        e = RARITIES[r["rarity"]][1]
        cbs.append([btn(f"{e} {r['title']} — {r['artist']} ×{r['qty']}"[:60], f"vc:{r['id']}")])
    nav = [btn("◀", go(rar, page-1) if page > 0 else "noop"),
           btn(f"{page+1}/{pages}", "noop"),
           btn("▶", go(rar, page+1) if page < pages-1 else "noop")]
    rr = [btn("Все", go("all",0))] + [btn(v[1], go(k,0)) for k,v in RARITIES.items()]
    return "\n".join(lines), kb([nav] + cbs + [rr])

def cmd_cards(m, args):
    t, mk = cards_page(m["from"]["id"], "all", 0); send(m["chat"]["id"], t, mk)

def cb_cards_page(cq, parts):
    if len(parts) != 3 or not parts[2].lstrip("-").isdigit(): answer_cb(cq["id"]); return
    rar, page = parts[1], int(parts[2])
    if rar != "all" and rar not in RARITIES: answer_cb(cq["id"]); return
    t, mk = cards_page(cq["from"]["id"], rar, page); edit_menu(cq, t, mk); answer_cb(cq["id"])

def cb_view_card(cq, cid):
    uid = cq["from"]["id"]; msg = cq.get("message") or {}
    chat_id = msg.get("chat",{}).get("id", uid)
    card = get_card(cid)
    if not card: answer_cb(cq["id"], "Нет.", True); return
    q = qty_of(uid, cid)
    if q < 1: answer_cb(cq["id"], "У тебя нет.", True); return
    r = RARITIES[card["rarity"]]
    cap = (f"{r[1]} <b>{r[2]}</b>\n\n🎵 <b>{esc(card['title'])}</b>\n👤 {esc(card['artist'])}\n"
           f"💿 {esc(card['album'])}\nID: <code>{card['id']}</code>\n🎁 ×{q}")
    send_media(chat_id, "photo", card["image"], cap, kb([[btn("◀", "back_cards")]]))
    answer_cb(cq["id"])

def cb_back_cards(cq):
    uid = cq["from"]["id"]; msg = cq.get("message") or {}
    chat_id = msg.get("chat",{}).get("id", uid)
    rar, page = CTX.get(uid, ("all",0))
    t, mk = cards_page(uid, rar, page); send(chat_id, t, mk); answer_cb(cq["id"])

# ── ТОП ──
def top_block(label, rar):
    rows = db.execute(
        "SELECT u.user_id uid, u.name name, u.equipped eq, SUM(i.qty) n "
        "FROM inventory i JOIN cards c ON c.id=i.card_id JOIN users u ON u.user_id=i.user_id "
        "WHERE (? IS NULL OR c.rarity=?) GROUP BY u.user_id ORDER BY n DESC LIMIT 10",
        (rar, rar)).fetchall()
    lines = [f"<b>{label}</b>"]
    if not rows: lines.append("пусто")
    med = ["🥇","🥈","🥉"]
    for i, r in enumerate(rows):
        m = med[i] if i < 3 else f"{i+1}."
        nl = f'<a href="tg://user?id={r["uid"]}">{esc(r["name"])}</a>'
        lines.append(f"{m} {badge(r['eq'])}{nl} — {r['n']}")
    lines.append("")
    return lines, rows

def cmd_top(m, args):
    cid = m["chat"]["id"]; lines = ["🏆 <b>Рейтинги</b>\n"]; bs = []
    for lbl, rar in [("Всего",None),("⚪",  "common"),("🟡","legendary")]:
        bl, rows = top_block(lbl, rar); lines += bl
        for i, r in enumerate(rows[:3]):
            bs.append(btn(f"{['🥇','🥈','🥉'][i]} {(r['name'] or '')[:16]}", f"vp:{r['uid']}"))
    send_long(cid, lines, kb([bs[i:i+3] for i in range(0, len(bs), 3)]) if bs else None)

def cb_view_profile(cq, tgt):
    uid = cq["from"]["id"]; cid = (cq.get("message") or {}).get("chat",{}).get("id", uid)
    if tgt == uid: answer_cb(cq["id"], "Твой 🙂", True); return
    if not get_user(tgt): answer_cb(cq["id"], "Нет.", True); return
    send(cid, profile_text(tgt), kb([[btn("🔄", f"vp:{tgt}")]])); answer_cb(cq["id"])

def cmd_view_user(m, args):
    cid = m["chat"]["id"]; a = (args or "").strip()
    if not a: send(cid, "/user @ник"); return
    if a.startswith("@"): u = db.execute("SELECT * FROM users WHERE username=?", (a[1:].lower(),)).fetchone()
    elif a.lstrip("-").isdigit(): u = get_user(int(a))
    else: u = db.execute("SELECT * FROM users WHERE username=?", (a.lower(),)).fetchone()
    if not u: send(cid, "Нет"); return
    if u["user_id"] == m["from"]["id"]: send(cid, "Это ты 🙂 /start"); return
    send(cid, profile_text(u["user_id"]))

# ── КОСМЕТИКА ──
def cb_cosmetic(cq, item):
    uid = cq["from"]["id"]; u = get_user(uid); t = None
    if item == "off":
        db.execute("UPDATE users SET equipped=NULL WHERE user_id=?", (uid,)); db.commit(); t = "Снято."
    elif item in COSMETICS:
        e, n, p = COSMETICS[item]
        has = db.execute("SELECT 1 FROM owned_cosmetics WHERE user_id=? AND item=?", (uid, item)).fetchone()
        if has:
            db.execute("UPDATE users SET equipped=? WHERE user_id=?", (item, uid)); db.commit(); t = f"Надето: {e}"
        elif u["coins"] < p: answer_cb(cq["id"], f"Нужно {p}", True); return
        else:
            db.execute("UPDATE users SET coins=coins-?, equipped=? WHERE user_id=?", (p, item, uid))
            db.execute("INSERT INTO owned_cosmetics(user_id,item) VALUES(?,?)", (uid, item))
            db.commit(); t = f"Куплено: {e}"
    text, mk = shop_menu(uid); edit_menu(cq, text, mk); answer_cb(cq["id"], t)

def cmd_shop(m, args):
    t, mk = shop_menu(m["from"]["id"]); send(m["chat"]["id"], t, mk)

# ── ОБМЕН ──
TRADE_USAGE = "<code>/trade @ник мой чужой</code> или ответом <code>/trade мой чужой</code>"

def trade_text(t):
    return (f"🔁 <b>{esc(who(t['from_id']))}</b>:\n\nОн отдаёт: {title_of(get_card(t['from_card']))}\n"
            f"Ты отдаёшь: {title_of(get_card(t['to_card']))}")

def cmd_trade(m, args):
    cid, me = m["chat"]["id"], m["from"]["id"]
    p = args.split(); rp = (m.get("reply_to_message") or {}).get("from"); tgt = None
    if len(p) == 2 and all(x.isdigit() for x in p) and rp:
        tgt = get_user(rp["id"]); mc, tc = int(p[0]), int(p[1])
    elif len(p) == 3 and p[0].startswith("@") and p[1].isdigit() and p[2].isdigit():
        tgt = db.execute("SELECT * FROM users WHERE username=?", (p[0][1:].lower(),)).fetchone()
        mc, tc = int(p[1]), int(p[2])
    else: send(cid, TRADE_USAGE); return
    if mc == tc: send(cid, "Одинаковые."); return
    if not tgt: send(cid, "Игрок не найден."); return
    if tgt["user_id"] == me: send(cid, "С собой."); return
    if qty_of(me, mc) < 1: send(cid, "Нет у тебя."); return
    if qty_of(tgt["user_id"], tc) < 1: send(cid, "Нет у него."); return
    cur = db.execute("INSERT INTO trades(from_id,to_id,from_card,to_card,status,created) VALUES(?,?,?,?,'pending',?)",
                     (me, tgt["user_id"], mc, tc, int(time.time())))
    db.commit(); tid = cur.lastrowid
    t = db.execute("SELECT * FROM trades WHERE id=?", (tid,)).fetchone()
    mk = kb([[btn("✅ Принять", f"t:y:{tid}"), btn("❌ Нет", f"t:n:{tid}")]])
    try: send(tgt["user_id"], trade_text(t), mk)
    except TgErr:
        db.execute("UPDATE trades SET status='failed' WHERE id=?", (tid,)); db.commit()
        send(cid, "Не доставить."); return
    send(cid, "📨 Отправлено.")

def cb_trade(cq, action, tid):
    t = db.execute("SELECT * FROM trades WHERE id=?", (tid,)).fetchone()
    if not t or t["status"] != "pending": answer_cb(cq["id"], "Неактуально.", True); return
    if cq["from"]["id"] != t["to_id"]: answer_cb(cq["id"], "Не для тебя.", True); return
    if time.time() - t["created"] > TRADE_TTL: st, line = "expired", "⌛ Истекло."
    elif action == "n": st, line = "declined", "❌ Отклонено."
    elif qty_of(t["from_id"], t["from_card"]) < 1 or qty_of(t["to_id"], t["to_card"]) < 1:
        st, line = "failed", "⚠️ Карточка пропала."
    else:
        try:
            add_card(t["from_id"], t["from_card"], -1); add_card(t["to_id"], t["from_card"], 1)
            add_card(t["to_id"], t["to_card"], -1); add_card(t["from_id"], t["to_card"], 1)
            st, line = "accepted", "✅ Обмен выполнен!"
        except Exception: db.rollback(); raise
    db.execute("UPDATE trades SET status=? WHERE id=?", (st, tid))
    if st == "accepted":
        db.execute("UPDATE users SET trades_ok=trades_ok+1 WHERE user_id IN (?,?)", (t["from_id"], t["to_id"]))
    db.commit()
    edit_menu(cq, trade_text(t) + f"\n\n{line}"); answer_cb(cq["id"])
    notice = {"accepted":"✅ Принят!","declined":"❌ Отклонили.","expired":"⌛ Истекло.","failed":"⚠️ Нет."}[st]
    try: send(t["from_id"], notice)
    except TgErr: pass
    if st == "accepted":
        notify_ach(t["from_id"], check_ach(t["from_id"]))
        notify_ach(t["to_id"], check_ach(t["to_id"]))
        notify_quests(t["from_id"], prog_quest(t["from_id"], "trade1", 1))
        notify_quests(t["to_id"], prog_quest(t["to_id"], "trade1", 1))

# ── СОСТОЯНИЯ ──
STATE = {}
TSTEPS = ["title","artist","album"]
PROMPTS = {"title":"Название трека?","artist":"Кто исполнитель?","album":"Из какого альбома?"}

def rarity_rows(make):
    b = [btn(f"{v[1]} {v[2]}", make(k)) for k, v in RARITIES.items()]
    return [b[:2], b[2:]]

def cmd_cancel(m, args):
    STATE.pop(m["from"]["id"], None); send(m["chat"]["id"], "Отменено.")

def cmd_skip(m, args):
    st = STATE.get(m["from"]["id"])
    if st and st["flow"] == "add" and st["step"] == "photo":
        st["data"]["image"] = None; st["step"] = "title"; send(m["chat"]["id"], PROMPTS["title"])

def on_state(m, st):
    uid, cid = m["from"]["id"], m["chat"]["id"]
    flow, step, d = st["flow"], st["step"], st["data"]
    text = (m.get("text") or "").strip()
    if step == "photo":
        if m.get("photo"):
            d["image"] = m["photo"][-1]["file_id"]; st["step"] = "title"; send(cid, PROMPTS["title"])
        else:
            ex = " /skip без картинки." if flow == "add" else ""
            send(cid, f"Нужно фото.{ex} /cancel")
    elif step in TSTEPS:
        if not text: send(cid, "Текстом. /cancel"); return
        d[step] = text[:80]
        nxt = TSTEPS.index(step) + 1
        if nxt < len(TSTEPS): st["step"] = TSTEPS[nxt]; send(cid, PROMPTS[st["step"]])
        else:
            if flow == "add":
                st["step"] = "rarity"; send(cid, "Редкость:", kb(rarity_rows(lambda k: f"ac:{k}")))
            else:
                STATE.pop(uid, None); finish_suggest(uid, cid, d)
    elif step == "rarity": send(cid, "Кнопкой выше.")

def cb_add_rarity(cq, rar):
    uid = cq["from"]["id"]; msg = cq.get("message") or {}
    cid, mid = msg.get("chat",{}).get("id", uid), msg.get("message_id")
    st = STATE.get(uid)
    if not st or st["flow"] != "add" or st["step"] != "rarity" or rar not in RARITIES:
        answer_cb(cq["id"], "?"); return
    d = st["data"]; STATE.pop(uid, None)
    aid = ensure_artist(d["artist"])
    cid2 = insert_card(d["title"], d["artist"], d["album"], rar, d.get("image"), aid)
    if mid: clear_kb(cid, mid)
    if cid2: send(cid, f"✅ #{cid2}: {RARITIES[rar][1]} {esc(d['title'])}")
    else: send(cid, "Уже есть.")
    answer_cb(cq["id"])

# ── ЗАЯВКИ ──
def start_suggest(uid, cid, ctype):
    if ctype != "private": send(cid, "Только в ЛС."); return
    n = db.execute("SELECT COUNT(*) FROM submissions WHERE user_id=? AND status='pending'", (uid,)).fetchone()[0]
    if n >= 3: send(cid, "Уже 3 заявки."); return
    STATE[uid] = {"flow": "sug", "step": "photo", "data": {}}
    send(cid, "🖼 Пришли обложку. /cancel")

def cmd_suggest(m, args):
    start_suggest(m["from"]["id"], m["chat"]["id"], m["chat"].get("type"))

def sub_cap(r):
    return (f"📥 <b>Заявка #{r['id']}</b>\nТрек: {esc(r['title'])}\nИсполнитель: {esc(r['artist'])}\n"
            f"Альбом: {esc(r['album'])}\nОт: {esc(who(r['user_id']))}")

def send_sub(cid, r):
    mk = kb(rarity_rows(lambda k: f"sa:{r['id']}:{k}") + [[btn("❌ Отклонить", f"sr:{r['id']}")]])
    try: tg("sendPhoto", chat_id=cid, photo=r["image"], caption=sub_cap(r) + "\n\nРедкость:",
           parse_mode="HTML", reply_markup=mk)
    except TgErr as e: say(f"sub fail: {e}")

def finish_suggest(uid, cid, d):
    cur = db.execute("INSERT INTO submissions(user_id,title,artist,album,image,status,created) VALUES(?,?,?,?,?,'pending',?)",
                     (uid, d["title"], d["artist"], d["album"], d["image"], int(time.time())))
    db.commit()
    row = db.execute("SELECT * FROM submissions WHERE id=?", (cur.lastrowid,)).fetchone()
    send(cid, "📨 Отправлено на проверку.")
    for a in ADMIN_IDS: send_sub(a, row)

def cb_sub(cq, parts):
    approve = parts[0] == "sa"; sid = int(parts[1])
    s = db.execute("SELECT * FROM submissions WHERE id=?", (sid,)).fetchone()
    if not s or s["status"] != "pending":
        answer_cb(cq["id"], "Уже обработано.", True)
        msg = cq.get("message") or {}
        if msg.get("chat") and msg.get("message_id"): clear_kb(msg["chat"]["id"], msg["message_id"])
        return
    if approve:
        rar = parts[2] if len(parts) > 2 else ""
        if rar not in RARITIES: answer_cb(cq["id"]); return
        aid = ensure_artist(s["artist"])
        cid2 = insert_card(s["title"], s["artist"], s["album"], rar, s["image"], aid)
        if cid2:
            st, al = "approved", f"✅ #{cid2}"
            um = f"🎉 «{esc(s['title'])}» одобрен!"
        else:
            st, al = "rejected", "⚠️ Уже есть."
            um = f"«{esc(s['title'])}» уже есть."
    else:
        st, al = "rejected", "❌ Отклонено"
        um = f"😔 «{esc(s['title'])}» отклонили."
    db.execute("UPDATE submissions SET status=? WHERE id=?", (st, sid)); db.commit()
    edit_menu(cq, sub_cap(s) + f"\n\n{al}")
    try: send(s["user_id"], um)
    except TgErr: pass
    answer_cb(cq["id"])

# ── АДМИН ──
def panel_text():
    p = db.execute("SELECT COUNT(*) FROM submissions WHERE status='pending'").fetchone()[0]
    c = db.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
    u = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    a = db.execute("SELECT COUNT(*) FROM artists").fetchone()[0]
    pr = db.execute("SELECT COUNT(*) FROM promocodes").fetchone()[0]
    st = db.execute("SELECT COALESCE(SUM(stars),0) FROM payments").fetchone()[0]
    return (f"🛠 <b>Админ</b>\n\n👥 {u}\n🎵 {c}\n🎤 {a}\n🎟 {pr}\n📋 {p}\n⭐ {st}\n"
            f"📢 #1: <code>{esc(get_setting('sub_channel') or '—')}</code>\n"
            f"📣 #2: <code>{esc(get_setting('sub_channel2') or '—')}</code>")

def cmd_admin(m, args):
    if not is_admin(m["from"]["id"]): send(m["chat"]["id"], "Только админ."); return
    goto(m["chat"]["id"], m["from"]["id"], "admin", panel_text(), m["chat"].get("type")=="private")

def admin_list_page(page):
    size = 20
    n = db.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
    pages = max(1, (n+size-1)//size); page = min(max(page,0), pages-1)
    rows = db.execute("SELECT * FROM cards ORDER BY artist,album,title LIMIT ? OFFSET ?", (size, page*size)).fetchall()
    lines = [f"🗂 <b>Карточки ({n})</b>", ""]
    for r in rows:
        lines.append(f"<code>{r['id']}</code> {RARITIES[r['rarity']][1]} {esc(r['title'])} — {esc(r['artist'])}")
    lines.append("\n/delcard ID")
    nav = [btn("◀", f"al:{page-1}" if page>0 else "noop"),
           btn(f"{page+1}/{pages}", "noop"),
           btn("▶", f"al:{page+1}" if page<pages-1 else "noop")]
    return "\n".join(lines), kb([nav])

def admin_action(cid, uid, action):
    if action == "adm_add":
        STATE[uid] = {"flow": "add", "step": "photo", "data": {}}
        send(cid, "Обложку. /skip /cancel")
    elif action == "adm_list":
        t, mk = admin_list_page(0); send(cid, t, mk)
    elif action == "adm_album": send(cid, ALBUM_HELP)
    elif action == "adm_spotify": send(cid, IMPORT_HELP)
    elif action == "adm_queue":
        rows = db.execute("SELECT * FROM submissions WHERE status='pending' ORDER BY id LIMIT 5").fetchall()
        if not rows: send(cid, "Заявок нет 🎉")
        for r in rows: send_sub(cid, r)
    elif action == "promos_menu":
        send(cid, "🎟 <b>Промокоды</b>\n\n/addpromo КОД 5000 [кол]\n/delpromo КОД\n/promos")

def cmd_clearcards(m, args):
    cid = m["chat"]["id"]
    if not is_admin(m["from"]["id"]): send(cid, "Только админ."); return
    n = db.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
    send(cid, f"⚠️ Удалить всё ({n})?", kb([[btn("🗑 Да","cc:y"), btn("Отмена","cc:n")]]))

def cb_clearcards(cq, a):
    if a == "y":
        db.execute("DELETE FROM inventory"); db.execute("DELETE FROM cards")
        db.execute("DELETE FROM sqlite_sequence WHERE name='cards'")
        db.execute("UPDATE trades SET status='failed' WHERE status='pending'")
        db.commit(); edit_menu(cq, "🗑 Удалено.")
    else: edit_menu(cq, "Отменено.")
    answer_cb(cq["id"])

def cmd_delcard(m, args):
    cid = m["chat"]["id"]
    if not is_admin(m["from"]["id"]): send(cid, "Только админ."); return
    if not args.strip().isdigit(): send(cid, "/delcard ID"); return
    c = get_card(int(args.strip()))
    if not c: send(cid, "Нет."); return
    db.execute("DELETE FROM inventory WHERE card_id=?", (c["id"],))
    db.execute("DELETE FROM cards WHERE id=?", (c["id"],)); db.commit()
    send(cid, f"🗑 {title_of(c)}")

def cmd_addtrack(m, args):
    cid = m["chat"]["id"]
    if not is_admin(m["from"]["id"]): send(cid, "Только админ."); return
    p = [x.strip() for x in args.split("|")]
    if len(p) < 4 or not all(p[:3]) or p[3].lower() not in RARITIES:
        send(cid, "/addtrack Название | Артист | Альбом | редкость"); return
    aid = ensure_artist(p[1])
    cid2 = insert_card(p[0], p[1], p[2], p[3].lower(), photo_of(m), aid)
    send(cid, f"✅ #{cid2}" if cid2 else "Уже есть.")

ALBUM_HELP = ("💿 <code>/addalbum Артист | Альбом | редкость | трек1; трек2 [epic]</code> + фото\n"
              "<code>/setcover Артист | Альбом</code> + фото\n"
              "<code>/delalbum Артист | Альбом</code> · <code>/delcard ID</code> · <code>/clearcards</code>\n"
              "<code>/addartist Имя | описание</code> + фото\n"
              "<code>/artists</code> · <code>/delartist ID</code>\n"
              "<code>/setwelcome</code> + медиа · off\n"
              "<code>/givecoins @ник 500</code>\n"
              "<code>/spotify ссылка_deezer.com</code>")

def cmd_addalbum(m, args):
    cid = m["chat"]["id"]
    if not is_admin(m["from"]["id"]): send(cid, "Только админ."); return
    p = [x.strip() for x in args.split("|", 3)]
    if len(p) < 4 or not p[0] or not p[1] or p[2].lower() not in RARITIES:
        send(cid, ALBUM_HELP); return
    a, al, dr = p[0][:80], p[1][:80], p[2].lower()
    img = photo_of(m); aid = ensure_artist(a, image=img)
    added = skip = 0
    for raw in p[3].replace("\n",";").split(";"):
        raw = raw.strip()
        if not raw: continue
        rar = dr
        mt = re.match(r"^(.*?)\s*\[(common|rare|epic|legendary)\]\s*$", raw, re.I)
        if mt: raw, rar = mt.group(1).strip(), mt.group(2).lower()
        if insert_card(raw, a, al, rar, img, aid): added += 1
        else: skip += 1
    send(cid, f"💿 {esc(a)} — {esc(al)}: +{added}" + (f", дубли: {skip}" if skip else ""))

def cmd_setcover(m, args):
    cid = m["chat"]["id"]
    if not is_admin(m["from"]["id"]): send(cid, "Только админ."); return
    p = [x.strip() for x in args.split("|")]; img = photo_of(m)
    if len(p) != 2 or not all(p) or not img: send(cid, "/setcover Артист | Альбом + фото"); return
    cur = db.execute("UPDATE cards SET image=? WHERE artist=? COLLATE NOCASE AND album=? COLLATE NOCASE", (img, p[0], p[1]))
    db.commit(); send(cid, f"🖼 {cur.rowcount} треков.")

def cmd_delalbum(m, args):
    cid = m["chat"]["id"]
    if not is_admin(m["from"]["id"]): send(cid, "Только админ."); return
    p = [x.strip() for x in args.split("|")]
    if len(p) != 2 or not all(p): send(cid, "/delalbum Артист | Альбом"); return
    ids = [r["id"] for r in db.execute("SELECT id FROM cards WHERE artist=? COLLATE NOCASE AND album=? COLLATE NOCASE", (p[0], p[1]))]
    for c in ids:
        db.execute("DELETE FROM inventory WHERE card_id=?", (c,))
        db.execute("DELETE FROM cards WHERE id=?", (c,))
    db.commit(); send(cid, f"🗑 {len(ids)}")

def cmd_setwelcome(m, args):
    cid = m["chat"]["id"]
    if not is_admin(m["from"]["id"]): send(cid, "Только админ."); return
    if args.strip().lower() == "off": set_setting("welcome_media", None); send(cid, "Убрано."); return
    for src in (m, m.get("reply_to_message") or {}):
        if src.get("animation"): media = ("animation", src["animation"]["file_id"])
        elif src.get("photo"): media = ("photo", src["photo"][-1]["file_id"])
        elif src.get("video"): media = ("video", src["video"]["file_id"])
        else: continue
        set_setting("welcome_media", f"{media[0]}:{media[1]}"); send(cid, "✅ Обновлено."); return
    send(cid, "Фото/гифка с /setwelcome. off — убрать.")

def cmd_givecoins(m, args):
    cid = m["chat"]["id"]
    if not is_admin(m["from"]["id"]): send(cid, "Только админ."); return
    p = args.split()
    if len(p) != 2 or not p[0].startswith("@") or not p[1].lstrip("-").isdigit():
        send(cid, "/givecoins @ник 500"); return
    u = db.execute("SELECT * FROM users WHERE username=?", (p[0][1:].lower(),)).fetchone()
    if not u: send(cid, "Нет."); return
    new = max(0, u["coins"] + int(p[1]))
    db.execute("UPDATE users SET coins=? WHERE user_id=?", (new, u["user_id"])); db.commit()
    send(cid, f"💰 {esc(u['name'])}: {new}")

def cmd_setrarity(m, args):
    cid = m["chat"]["id"]
    if not is_admin(m["from"]["id"]): send(cid, "Только админ."); return
    p = args.split()
    if len(p) != 2 or not p[0].isdigit() or p[1].lower() not in RARITIES:
        send(cid, "/setrarity ID редкость"); return
    c = get_card(int(p[0]))
    if not c: send(cid, "Нет."); return
    db.execute("UPDATE cards SET rarity=? WHERE id=?", (p[1].lower(), c["id"])); db.commit()
    send(cid, f"✅ {title_of(get_card(c['id']))}")

# ── АВАТАР ──
def cmd_setavatar(m, args):
    uid, cid = m["from"]["id"], m["chat"]["id"]
    a = (args or "").strip()
    if not a.isdigit(): send(cid, "/setavatar ID"); return
    ci = int(a)
    if qty_of(uid, ci) < 1: send(cid, "Нет такой."); return
    c = get_card(ci)
    if not c or not c["image"]: send(cid, "Нет картинки."); return
    db.execute("UPDATE users SET avatar_card=? WHERE user_id=?", (ci, uid)); db.commit()
    send(cid, f"{frame_for(uid)} ✅ {title_of(c)}")

def cmd_delavatar(m, args):
    uid = m["from"]["id"]
    db.execute("UPDATE users SET avatar_card=NULL WHERE user_id=?", (uid,)); db.commit()
    send(m["chat"]["id"], "🗑 Снят.")

def cmd_avatar(m, args):
    uid, cid = m["from"]["id"], m["chat"]["id"]
    u = get_user(uid)
    if not u["avatar_card"]: send(cid, "/setavatar ID"); return
    c = get_card(u["avatar_card"])
    if not c: send(cid, "Удалена."); return
    send_media(cid, "photo", c["image"], f"{frame_for(uid)} {title_of(c)}")

# ── КОМАНДЫ ──
def cmd_start(m, args):
    uid = m["from"]["id"]; a = (args or "").strip()
    if a.startswith("ref_"):
        u = get_user(uid)
        if u and (time.time() - (u["joined"] or 0) < REF_AGE):
            ok, rid = process_ref(uid, a)
            if ok:
                ru = get_user(rid); cnt = (ru["ref_count"] if ru else 1)
                try: send(rid, f"🎉 Реферал!\n💰 +{REF_BONUS}\n👥 {cnt}")
                except TgErr: pass
    send_home(m["chat"]["id"], uid, m["chat"].get("type")=="private")

def cmd_help(m, args): send(m["chat"]["id"], HELP)

COMMANDS = {
    "start": cmd_start, "menu": cmd_start, "profile": cmd_start, "help": cmd_help,
    "claim": cmd_claim, "open": cmd_open, "cards": cmd_cards, "shop": cmd_shop, "top": cmd_top,
    "ref": cmd_ref, "subscribe": cmd_subscribe, "channelsub": cmd_channelsub,
    "user": cmd_view_user, "trade": cmd_trade, "suggest": cmd_suggest,
    "quests": cmd_quests, "achievements": cmd_ach, "titles": cmd_titles,
    "friends": cmd_friends, "addfriend": cmd_addfriend, "delfriend": cmd_delfriend,
    "avatar": cmd_avatar, "setavatar": cmd_setavatar, "delavatar": cmd_delavatar,
    "admin": cmd_admin, "delcard": cmd_delcard, "addtrack": cmd_addtrack, "addalbum": cmd_addalbum,
    "setcover": cmd_setcover, "delalbum": cmd_delalbum, "setwelcome": cmd_setwelcome,
    "givecoins": cmd_givecoins, "clearcards": cmd_clearcards,
    "spotify": cmd_spotify, "setrarity": cmd_setrarity,
    "artists": cmd_artists, "addartist": cmd_addartist, "delartist": cmd_delartist,
    "setartistcover": cmd_setartistcover,
    "setchannel": cmd_setchannel, "setchannel2": cmd_setchannel2,
    "setchreward": cmd_setchreward, "setchreward2": cmd_setchreward2,
    "promo": cmd_promo, "addpromo": cmd_addpromo, "delpromo": cmd_delpromo, "promos": cmd_promos,
}

def on_button(m, action):
    uid, cid = m["from"]["id"], m["chat"]["id"]
    priv = m["chat"].get("type") == "private"
    if action in ADMIN_ACTIONS and not is_admin(uid): send(cid, "Только админ."); return
    if action == "home": send_home(cid, uid, priv)
    elif action == "back":
        if NAV.get(uid) == "open": goto(cid, uid, "cards", cards_text(uid), priv)
        else: send_home(cid, uid, priv)
    elif action == "g_cards": goto(cid, uid, "cards", cards_text(uid), priv)
    elif action == "g_open": goto(cid, uid, "open", open_text(uid), priv)
    elif action == "open:random": do_open(uid, cid)
    elif action == "coll": cmd_cards(m, "")
    elif action == "trade": send(cid, TRADE_USAGE)
    elif action == "suggest": start_suggest(uid, cid, m["chat"].get("type"))
    elif action == "g_shop":
        goto(cid, uid, "shop", "💄 <b>Косметика</b>", priv); send(cid, *shop_menu(uid))
    elif action == "shop": send(cid, *shop_menu(uid))
    elif action == "unequip":
        db.execute("UPDATE users SET equipped=NULL WHERE user_id=?", (uid,)); db.commit(); send(cid, "Снято.")
    elif action == "g_coins": goto(cid, uid, "coins", coins_text(uid), priv)
    elif action == "claim": cmd_claim(m, "")
    elif action == "balance": send(cid, coins_text(uid))
    elif action == "top": cmd_top(m, "")
    elif action == "help": cmd_help(m, "")
    elif action == "ref": cmd_ref(m, "")
    elif action == "sub_menu": cmd_subscribe(m, "")
    elif action == "chsub_menu": cmd_channelsub(m, "")
    elif action == "artists": cmd_artists(m, "")
    elif action == "quests": cmd_quests(m, "")
    elif action == "ach": cmd_ach(m, "")
    elif action == "titles": cmd_titles(m, "")
    elif action == "friends": cmd_friends(m, "")
    elif action == "g_admin": goto(cid, uid, "admin", panel_text(), priv)
    elif action in ADMIN_ACTIONS: admin_action(cid, uid, action)

def on_message(m):
    u = m.get("from")
    if not u or u.get("is_bot"): return
    ensure_user(u)
    if not STATE.get(u["id"]):
        q = prog_quest(u["id"], "msg5", 1)
        if q: notify_quests(m["chat"]["id"], q)
    body = (m.get("text") or m.get("caption") or "").strip()
    if body.startswith("/"):
        p = body.split(None, 1); args = p[1] if len(p) > 1 else ""
        cmd, _, suf = p[0][1:].partition("@"); cmd = cmd.lower()
        if suf and BOT_USERNAME and suf.lower() != BOT_USERNAME: return
        if cmd == "cancel": cmd_cancel(m, args)
        elif cmd == "skip": cmd_skip(m, args)
        elif cmd in COMMANDS:
            STATE.pop(u["id"], None); COMMANDS[cmd](m, args)
        return
    act = LABELS.get((m.get("text") or "").strip())
    if act:
        STATE.pop(u["id"], None); on_button(m, act); return
    st = STATE.get(u["id"])
    if st: on_state(m, st)

def on_callback(cq):
    ensure_user(cq["from"])
    parts = (cq.get("data") or "").split(":")
    kind = parts[0]; uid = cq["from"]["id"]

    if kind == "chsub" and len(parts) == 3 and parts[1] == "check":
        try: s = int(parts[2])
        except: answer_cb(cq["id"]); return
        if s in (1,2): cb_chsub(cq, s)
        return
    if kind == "ar" and len(parts) == 2:
        if parts[1] == "list": cb_artists_list(cq)
        elif parts[1].isdigit(): cb_artist(cq, int(parts[1]))
        return
    if kind == "vp" and len(parts) == 2 and parts[1].lstrip("-").isdigit():
        cb_view_profile(cq, int(parts[1])); return
    if kind == "vc" and len(parts) == 2 and parts[1].isdigit():
        cb_view_card(cq, int(parts[1])); return
    if kind == "back_cards": cb_back_cards(cq); return
    if kind == "ref" and len(parts) == 2 and parts[1] == "refresh":
        cmd_ref({"from": {"id": uid}, "chat": {"id": (cq.get("message") or {}).get("chat",{}).get("id", uid)}}, "")
        answer_cb(cq["id"]); return
    if kind == "sub" and len(parts) >= 2: cb_sub(cq, ":".join(parts[1:])); return
    if kind == "ti" and len(parts) == 2 and parts[1] in TITLES: cb_title(cq, parts[1]); return
    if kind == "dza":
        if not is_admin(uid): answer_cb(cq["id"], "Нет доступа.", True); return
        cb_deezer(cq, parts); return
    if kind == "cs" and len(parts) == 2: cb_cosmetic(cq, parts[1])
    elif kind == "cp": cb_cards_page(cq, parts)
    elif kind == "t" and len(parts) == 3 and parts[2].isdigit(): cb_trade(cq, parts[1], int(parts[2]))
    elif kind == "f" and len(parts) == 3 and parts[2].lstrip("-").isdigit(): cb_friend(cq, parts[1], int(parts[2]))
    elif kind in ("ak","ac","sa","sr","al","cc"):
        if not is_admin(uid): answer_cb(cq["id"], "Нет доступа.", True); return
        if kind == "ac" and len(parts) == 2: cb_add_rarity(cq, parts[1])
        elif kind == "cc" and len(parts) == 2: cb_clearcards(cq, parts[1])
        elif kind in ("sa","sr") and len(parts) >= 2 and parts[1].isdigit(): cb_sub(cq, parts)
        elif kind == "al" and len(parts) == 2 and parts[1].lstrip("-").isdigit():
            t, mk = admin_list_page(int(parts[1])); edit_menu(cq, t, mk); answer_cb(cq["id"])
    else: answer_cb(cq["id"])

def handle_update(u):
    if "message" in u:
        m = u["message"]
        if m.get("successful_payment"): on_paid(m); return
        on_message(m)
    elif "callback_query" in u: on_callback(u["callback_query"])
    elif "pre_checkout_query" in u: on_pre_checkout(u["pre_checkout_query"])

def main():
    global BOT_USERNAME
    init_db()
    say("▶ База готова")
    me = tg("getMe"); BOT_USERNAME = (me.get("username") or "").lower()
    say(f"▶ Бот: @{me.get('username')}")
    try:
        tg("deleteWebhook")
        tg("setMyCommands", commands=[
            {"command": "start", "description": "Меню"},
            {"command": "claim", "description": "Монеты"},
            {"command": "open", "description": "Крутить"},
            {"command": "cards", "description": "Коллекция"},
            {"command": "artists", "description": "Артисты"},
            {"command": "promo", "description": "Промокод"},
            {"command": "quests", "description": "Квесты"},
            {"command": "achievements", "description": "Достижения"},
            {"command": "titles", "description": "Титулы"},
            {"command": "friends", "description": "Друзья"},
            {"command": "shop", "description": "Косметика"},
            {"command": "ref", "description": "Рефералы"},
            {"command": "subscribe", "description": "Подписки и донаты"},
            {"command": "channelsub", "description": "Подписка на каналы"},
            {"command": "top", "description": "Рейтинги"},
            {"command": "help", "description": "Помощь"},
        ])
    except Exception as e: say(f"menu: {e}")
    say("▶ Слушаю")
    offset = None
    while True:
        p = {"timeout": 25, "allowed_updates": ["message","callback_query","pre_checkout_query"]}
        if offset: p["offset"] = offset
        try: updates = tg("getUpdates", **p)
        except TgErr as e: say(f"getUpdates: {e}"); time.sleep(5); continue
        except Exception as e: say(f"сеть: {e!r}"); time.sleep(5); continue
        for u in updates:
            offset = u["update_id"] + 1
            try: handle_update(u)
            except Exception: say("❌ " + traceback.format_exc())

if __name__ == "__main__":
    main()
