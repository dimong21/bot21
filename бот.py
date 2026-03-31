import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
import sqlite3
import time
import re
import json
import threading
import random
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

# ========== НАСТРОЙКИ ==========
TOKEN = "vk1.a.KA15ljp23_4l6s3DomdeTkkE7DHmsflVzVWGMjBm7kzWm0eOATiZI_LTGXlzC2nnRHx3fcgjVivrqwUq5WUQN-7tfecpSfGfjjrhprbxh9B7WdUgpZ9sgKo5bYpLSzKmuahc3Ylf3Zysct7yvMch0FGoECKYe6gSGBerNJKsDIbAlndr9HzLcMojM7ePA5GdkZUCA4ICcV7ttTSHnqZUzQ"
GROUP_ID = 237250582
ADMIN_IDS = [771565937]
WARN_LIMIT = 3
WEB_PORT = 8080
# ================================

vk_session = vk_api.VkApi(token=TOKEN)
vk = vk_session.get_api()
longpoll = VkLongPoll(vk_session)

# ========== СТАТИСТИКА ==========
stats = {
    'start_time': time.time(),
    'request_times': [],
    'command_times': [],
}

def add_request_time(t):
    stats['request_times'].append(t)
    if len(stats['request_times']) > 100:
        stats['request_times'] = stats['request_times'][-100:]

def add_command_time(t):
    stats['command_times'].append(t)
    if len(stats['command_times']) > 100:
        stats['command_times'] = stats['command_times'][-100:]

# ========== БАЗА ДАННЫХ ==========
DB_PATH = '/app/data/chat_manager.db'
os.makedirs('/app/data', exist_ok=True)

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

# Создание всех таблиц
c.execute('''CREATE TABLE IF NOT EXISTS users
             (user_id INTEGER, chat_id INTEGER, role_name TEXT, mute_until INTEGER, warns INTEGER, banned INTEGER)''')
c.execute('''CREATE TABLE IF NOT EXISTS roles
             (role_name TEXT PRIMARY KEY, permissions TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS bans
             (user_id INTEGER, chat_id INTEGER, reason TEXT, banned_at INTEGER)''')
c.execute('''CREATE TABLE IF NOT EXISTS economy
             (user_id INTEGER, chat_id INTEGER, rubles INTEGER, dollars INTEGER, euros INTEGER, country TEXT, messages INTEGER, last_bonus INTEGER)''')
c.execute('''CREATE TABLE IF NOT EXISTS slaves
             (owner_id INTEGER, slave_id INTEGER, chat_id INTEGER, price INTEGER, chained INTEGER, PRIMARY KEY (owner_id, slave_id, chat_id))''')
c.execute('''CREATE TABLE IF NOT EXISTS chains
             (user_id INTEGER, chat_id INTEGER, count INTEGER)''')
c.execute('''CREATE TABLE IF NOT EXISTS agents
             (user_id INTEGER PRIMARY KEY)''')
c.execute('''CREATE TABLE IF NOT EXISTS quests
             (quest_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, description TEXT, rubles INTEGER, dollars INTEGER, euros INTEGER, active INTEGER)''')
c.execute('''CREATE TABLE IF NOT EXISTS completed_quests
             (user_id INTEGER, quest_id INTEGER, chat_id INTEGER, completed_at INTEGER)''')
c.execute('''CREATE TABLE IF NOT EXISTS tickets
             (ticket_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, chat_id INTEGER, text TEXT, status TEXT, answer TEXT, created_at INTEGER)''')
c.execute('''CREATE TABLE IF NOT EXISTS chats
             (chat_id INTEGER PRIMARY KEY, active INTEGER, owner_id INTEGER, activated_at INTEGER)''')
c.execute('''CREATE TABLE IF NOT EXISTS message_stats
             (user_id INTEGER, chat_id INTEGER, count INTEGER, last_message INTEGER)''')
c.execute('''CREATE TABLE IF NOT EXISTS shop_items
             (item_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, price_rub INTEGER, price_dol INTEGER, price_eur INTEGER, description TEXT)''')

# Добавляем стандартные предметы
c.execute("SELECT COUNT(*) FROM shop_items")
if c.fetchone()[0] == 0:
    items = [
        ("Цепи (защита раба)", 1000, 10, 5, "Защищает раба от продажи"),
        ("VIP-статус (7 дней)", 5000, 50, 25, "Даёт VIP-статус на 7 дней"),
    ]
    for name, rub, dol, eur, desc in items:
        c.execute("INSERT INTO shop_items (name, price_rub, price_dol, price_eur, description) VALUES (?, ?, ?, ?, ?)",
                  (name, rub, dol, eur, desc))

# Добавляем недостающие колонки
try:
    c.execute("ALTER TABLE users ADD COLUMN joined_at INTEGER")
except:
    pass
try:
    c.execute("ALTER TABLE users ADD COLUMN invited_by INTEGER")
except:
    pass
try:
    c.execute("ALTER TABLE economy ADD COLUMN vip_until INTEGER")
except:
    pass
try:
    c.execute("ALTER TABLE tickets ADD COLUMN answered_by INTEGER")
except:
    pass
conn.commit()

# ========== ИНИЦИАЛИЗАЦИЯ РОЛЕЙ ==========
def init_roles():
    default_roles = {
        "user": {"mute": 0, "ban": 0, "warn": 0, "addrole": 0, "unmute": 0, "unban": 0, "unwarn": 0, "editcmd": 0},
        "moderator": {"mute": 1, "ban": 1, "warn": 1, "addrole": 0, "unmute": 1, "unban": 1, "unwarn": 1, "editcmd": 0},
        "admin": {"mute": 1, "ban": 1, "warn": 1, "addrole": 1, "unmute": 1, "unban": 1, "unwarn": 1, "editcmd": 1}
    }
    for role, perms in default_roles.items():
        c.execute("INSERT OR IGNORE INTO roles (role_name, permissions) VALUES (?, ?)", (role, json.dumps(perms)))
    conn.commit()

init_roles()

# ========== ФУНКЦИИ РАБОТЫ С РОЛЯМИ ==========
def get_role_permissions(role_name):
    c.execute("SELECT permissions FROM roles WHERE role_name=?", (role_name,))
    row = c.fetchone()
    if row:
        return json.loads(row[0])
    return {}

def add_role(role_name, permissions=None):
    if permissions is None:
        permissions = {p: 0 for p in ["mute", "ban", "warn", "addrole", "unmute", "unban", "unwarn", "editcmd"]}
    c.execute("INSERT OR REPLACE INTO roles (role_name, permissions) VALUES (?, ?)", (role_name, json.dumps(permissions)))
    conn.commit()

def delete_role(role_name):
    c.execute("SELECT COUNT(*) FROM users WHERE role_name=?", (role_name,))
    if c.fetchone()[0] > 0:
        return False
    c.execute("DELETE FROM roles WHERE role_name=?", (role_name,))
    conn.commit()
    return True

def set_role_permission(role_name, perm_name, value):
    perms = get_role_permissions(role_name)
    if perm_name in perms:
        perms[perm_name] = int(value)
        c.execute("UPDATE roles SET permissions=? WHERE role_name=?", (json.dumps(perms), role_name))
        conn.commit()
        return True
    return False

def get_user_role(user_id, chat_id):
    c.execute("SELECT role_name FROM users WHERE user_id=? AND chat_id=?", (user_id, chat_id))
    row = c.fetchone()
    if row:
        return row[0]
    set_user_role(user_id, chat_id, "user")
    return "user"

def set_user_role(user_id, chat_id, role_name):
    c.execute("INSERT OR REPLACE INTO users (user_id, chat_id, role_name, mute_until, warns, banned) VALUES (?, ?, ?, ?, ?, ?)",
              (user_id, chat_id, role_name, 0, 0, 0))
    conn.commit()

def has_permission(user_id, chat_id, permission):
    if user_id in ADMIN_IDS:
        return True
    role = get_user_role(user_id, chat_id)
    perms = get_role_permissions(role)
    return perms.get(permission, 0) == 1

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
def add_user(user_id, chat_id):
    c.execute("SELECT * FROM users WHERE user_id=? AND chat_id=?", (user_id, chat_id))
    if not c.fetchone():
        c.execute("INSERT INTO users (user_id, chat_id, role_name, mute_until, warns, banned) VALUES (?, ?, ?, ?, ?, ?)",
                  (user_id, chat_id, "user", 0, 0, 0))
        conn.commit()

def get_user_data(user_id, chat_id):
    add_user(user_id, chat_id)
    c.execute("SELECT role_name, mute_until, warns, banned FROM users WHERE user_id=? AND chat_id=?", (user_id, chat_id))
    return c.fetchone()

def update_user(user_id, chat_id, role_name=None, mute_until=None, warns=None, banned=None):
    if role_name is not None:
        c.execute("UPDATE users SET role_name=? WHERE user_id=? AND chat_id=?", (role_name, user_id, chat_id))
    if mute_until is not None:
        c.execute("UPDATE users SET mute_until=? WHERE user_id=? AND chat_id=?", (mute_until, user_id, chat_id))
    if warns is not None:
        c.execute("UPDATE users SET warns=? WHERE user_id=? AND chat_id=?", (warns, user_id, chat_id))
    if banned is not None:
        c.execute("UPDATE users SET banned=? WHERE user_id=? AND chat_id=?", (banned, user_id, chat_id))
    conn.commit()

def is_muted(user_id, chat_id):
    add_user(user_id, chat_id)
    mute_until = get_user_data(user_id, chat_id)[1]
    if mute_until and int(time.time()) < mute_until:
        return True
    if mute_until and int(time.time()) >= mute_until:
        update_user(user_id, chat_id, mute_until=0)
    return False

def is_banned(user_id, chat_id):
    add_user(user_id, chat_id)
    return get_user_data(user_id, chat_id)[3] == 1

def add_warn(user_id, chat_id, reason=""):
    add_user(user_id, chat_id)
    warns = get_user_data(user_id, chat_id)[2] + 1
    update_user(user_id, chat_id, warns=warns)
    if warns >= WARN_LIMIT:
        ban_user(user_id, chat_id, reason=f"Превышен лимит варнов ({WARN_LIMIT})")
        return f"Пользователь получил {warns}/{WARN_LIMIT} варнов и был забанен."
    else:
        return f"Пользователь получил варн ({warns}/{WARN_LIMIT}). Причина: {reason}"

def ban_user(user_id, chat_id, reason=""):
    add_user(user_id, chat_id)
    update_user(user_id, chat_id, banned=1, mute_until=0)
    c.execute("INSERT INTO bans (user_id, chat_id, reason, banned_at) VALUES (?, ?, ?, ?)",
              (user_id, chat_id, reason, int(time.time())))
    conn.commit()
    try:
        vk.messages.removeChatUser(chat_id=chat_id, user_id=user_id)
    except:
        pass
    return f"Пользователь забанен. Причина: {reason}"

def unban_user(user_id, chat_id):
    update_user(user_id, chat_id, banned=0)
    c.execute("DELETE FROM bans WHERE user_id=? AND chat_id=?", (user_id, chat_id))
    conn.commit()
    return f"Пользователь разбанен."

def mute_user(user_id, chat_id, duration_minutes):
    mute_until = int(time.time()) + duration_minutes * 60
    update_user(user_id, chat_id, mute_until=mute_until)
    return f"Пользователь замьючен на {duration_minutes} мин."

def unmute_user(user_id, chat_id):
    update_user(user_id, chat_id, mute_until=0)
    return f"Мут снят."

def get_user_link(user_id):
    return f"https://vk.com/id{user_id}"

def send_message(chat_id, message, reply_to=None, keyboard=None):
    start = time.time()
    params = {
        'peer_id': chat_id,
        'message': message,
        'random_id': 0,
        'reply_to': reply_to
    }
    if keyboard:
        params['keyboard'] = keyboard.get_keyboard()
    vk.messages.send(**params)
    add_request_time((time.time() - start) * 1000)

def kick_banned_user(user_id, chat_id):
    if is_banned(user_id, chat_id):
        try:
            vk.messages.removeChatUser(chat_id=chat_id, user_id=user_id)
            send_message(chat_id, f"Пользователь {get_user_link(user_id)} забанен и был удалён из беседы.")
        except:
            pass

def get_user_joined(user_id, chat_id):
    c.execute("SELECT joined_at, invited_by FROM users WHERE user_id=? AND chat_id=?", (user_id, chat_id))
    row = c.fetchone()
    if row:
        return row
    return (None, None)

def get_vip_status(user_id, chat_id):
    eco = get_economy(user_id, chat_id)
    vip_until = eco[6] if len(eco) > 6 else 0
    if vip_until and vip_until > int(time.time()):
        return True, vip_until
    return False, None

def get_user_name(user_id):
    try:
        user = vk.users.get(user_ids=user_id)[0]
        return f"{user['first_name']} {user['last_name']}"
    except:
        return f"id{user_id}"

# ========== ЭКОНОМИКА ==========
def get_economy(user_id, chat_id):
    c.execute("SELECT rubles, dollars, euros, country, messages, last_bonus, vip_until FROM economy WHERE user_id=? AND chat_id=?", (user_id, chat_id))
    row = c.fetchone()
    if not row:
        c.execute("INSERT INTO economy (user_id, chat_id, rubles, dollars, euros, country, messages, last_bonus, vip_until) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                  (user_id, chat_id, 0, 0, 0, "Не выбрана", 0, 0, 0))
        conn.commit()
        return (0, 0, 0, "Не выбрана", 0, 0, 0)
    return row

def update_economy(user_id, chat_id, rubles=None, dollars=None, euros=None, country=None, messages=None, last_bonus=None, vip_until=None):
    current = get_economy(user_id, chat_id)
    rub = current[0] if rubles is None else rubles
    dol = current[1] if dollars is None else dollars
    eur = current[2] if euros is None else euros
    cnt = current[3] if country is None else country
    msg = current[4] if messages is None else messages
    lb = current[5] if last_bonus is None else last_bonus
    vip = current[6] if vip_until is None else vip_until
    c.execute("UPDATE economy SET rubles=?, dollars=?, euros=?, country=?, messages=?, last_bonus=?, vip_until=? WHERE user_id=? AND chat_id=?",
              (rub, dol, eur, cnt, msg, lb, vip, user_id, chat_id))
    conn.commit()

def add_message_count(user_id, chat_id):
    c.execute("UPDATE economy SET messages = messages + 1 WHERE user_id=? AND chat_id=?", (user_id, chat_id))
    c.execute("UPDATE message_stats SET count = count + 1, last_message = ? WHERE user_id=? AND chat_id=?", (int(time.time()), user_id, chat_id))
    if c.rowcount == 0:
        c.execute("INSERT INTO message_stats (user_id, chat_id, count, last_message) VALUES (?, ?, ?, ?)",
                  (user_id, chat_id, 1, int(time.time())))
    conn.commit()

def get_message_top(chat_id, limit=10):
    c.execute("SELECT user_id, count FROM message_stats WHERE chat_id=? ORDER BY count DESC LIMIT ?", (chat_id, limit))
    return c.fetchall()

# ========== РАБЫ ==========
def buy_slave(owner_id, slave_id, chat_id, price):
    c.execute("SELECT * FROM slaves WHERE slave_id=? AND chat_id=?", (slave_id, chat_id))
    if c.fetchone():
        return False, "Этот пользователь уже является чьим-то рабом."
    if owner_id == slave_id:
        return False, "Нельзя купить самого себя."
    rub = get_economy(owner_id, chat_id)[0]
    if rub < price:
        return False, f"Недостаточно рублей. Нужно {price}."
    update_economy(owner_id, chat_id, rubles=rub - price)
    c.execute("INSERT INTO slaves (owner_id, slave_id, chat_id, price, chained) VALUES (?, ?, ?, ?, ?)",
              (owner_id, slave_id, chat_id, price, 0))
    conn.commit()
    return True, f"Вы купили пользователя [id{slave_id}|] за {price} рублей."

def sell_slave(owner_id, slave_id, chat_id):
    c.execute("SELECT price, chained FROM slaves WHERE owner_id=? AND slave_id=? AND chat_id=?", (owner_id, slave_id, chat_id))
    row = c.fetchone()
    if not row:
        return False, "Этот пользователь не ваш раб."
    price, chained = row
    if chained:
        return False, "Раб защищён цепями и не может быть продан."
    refund = int(price * 0.7)
    update_economy(owner_id, chat_id, rubles=get_economy(owner_id, chat_id)[0] + refund)
    c.execute("DELETE FROM slaves WHERE owner_id=? AND slave_id=? AND chat_id=?", (owner_id, slave_id, chat_id))
    conn.commit()
    return True, f"Вы продали раба и получили {refund} рублей."

def add_chain(user_id, chat_id):
    c.execute("SELECT count FROM chains WHERE user_id=? AND chat_id=?", (user_id, chat_id))
    row = c.fetchone()
    if row:
        new_count = row[0] + 1
        c.execute("UPDATE chains SET count=? WHERE user_id=? AND chat_id=?", (new_count, user_id, chat_id))
    else:
        new_count = 1
        c.execute("INSERT INTO chains (user_id, chat_id, count) VALUES (?, ?, ?)", (user_id, chat_id, 1))
    conn.commit()
    return new_count

def protect_slave(owner_id, slave_id, chat_id):
    c.execute("SELECT chained FROM slaves WHERE owner_id=? AND slave_id=? AND chat_id=?", (owner_id, slave_id, chat_id))
    row = c.fetchone()
    if not row:
        return False, "Это не ваш раб."
    if row[0]:
        return False, "Раб уже защищён цепями."
    c.execute("SELECT count FROM chains WHERE user_id=? AND chat_id=?", (owner_id, chat_id))
    chains = c.fetchone()
    if not chains or chains[0] == 0:
        return False, "У вас нет цепей. Купите их в магазине."
    c.execute("UPDATE chains SET count = count - 1 WHERE user_id=? AND chat_id=?", (owner_id, chat_id))
    c.execute("UPDATE slaves SET chained=1 WHERE owner_id=? AND slave_id=? AND chat_id=?", (owner_id, slave_id, chat_id))
    conn.commit()
    return True, "Раб защищён цепями."

# ========== АГЕНТЫ ==========
def is_agent(user_id):
    c.execute("SELECT 1 FROM agents WHERE user_id=?", (user_id,))
    return c.fetchone() is not None

def add_agent(user_id):
    c.execute("INSERT OR IGNORE INTO agents (user_id) VALUES (?)", (user_id,))
    conn.commit()

def remove_agent(user_id):
    c.execute("DELETE FROM agents WHERE user_id=?", (user_id,))
    conn.commit()

# ========== КВЕСТЫ ==========
def get_active_quests():
    c.execute("SELECT quest_id, name, description, rubles, dollars, euros FROM quests WHERE active=1")
    return c.fetchall()

def complete_quest(user_id, quest_id, chat_id):
    c.execute("SELECT 1 FROM completed_quests WHERE user_id=? AND quest_id=? AND chat_id=?", (user_id, quest_id, chat_id))
    if c.fetchone():
        return False, "Вы уже выполняли этот квест."
    c.execute("SELECT rubles, dollars, euros FROM quests WHERE quest_id=?", (quest_id,))
    rub, dol, eur = c.fetchone()
    eco = get_economy(user_id, chat_id)
    update_economy(user_id, chat_id, rubles=eco[0]+rub, dollars=eco[1]+dol, euros=eco[2]+eur)
    c.execute("INSERT INTO completed_quests (user_id, quest_id, chat_id, completed_at) VALUES (?, ?, ?, ?)",
              (user_id, quest_id, chat_id, int(time.time())))
    conn.commit()
    return True, f"Квест выполнен! Награда: {rub} руб., {dol} дол., {eur} евро."

# ========== ТИКЕТЫ ==========
def create_ticket(user_id, chat_id, text):
    c.execute("INSERT INTO tickets (user_id, chat_id, text, status, created_at) VALUES (?, ?, ?, ?, ?)",
              (user_id, chat_id, text, "open", int(time.time())))
    conn.commit()
    return c.lastrowid

def get_open_tickets():
    c.execute("SELECT ticket_id, user_id, chat_id, text, created_at FROM tickets WHERE status='open'")
    return c.fetchall()

def answer_ticket(ticket_id, answer_text, admin_id):
    c.execute("UPDATE tickets SET status='closed', answer=?, answered_by=? WHERE ticket_id=?", (answer_text, admin_id, ticket_id))
    conn.commit()
    c.execute("SELECT user_id, chat_id FROM tickets WHERE ticket_id=?", (ticket_id,))
    user_id, chat_id = c.fetchone()
    send_message(chat_id, f"Ответ на ваш тикет #{ticket_id}:\n{answer_text}")
    return True

# ========== АКТИВАЦИЯ БЕСЕДЫ ==========
def is_chat_active(chat_id):
    c.execute("SELECT active FROM chats WHERE chat_id=?", (chat_id,))
    row = c.fetchone()
    return row and row[0] == 1

def activate_chat(chat_id, user_id):
    c.execute("INSERT OR REPLACE INTO chats (chat_id, active, owner_id, activated_at) VALUES (?, ?, ?, ?)",
              (chat_id, 1, user_id, int(time.time())))
    conn.commit()

def get_inactive_chats_info():
    c.execute("SELECT chat_id, owner_id, activated_at FROM chats WHERE active=0")
    return c.fetchall()

# ========== МАГАЗИН ==========
def get_shop_items():
    c.execute("SELECT item_id, name, price_rub, price_dol, price_eur, description FROM shop_items")
    return c.fetchall()

def buy_item(user_id, chat_id, item_id):
    c.execute("SELECT name, price_rub, price_dol, price_eur FROM shop_items WHERE item_id=?", (item_id,))
    row = c.fetchone()
    if not row:
        return False, "Товар не найден."
    name, pr, pd, pe = row
    eco = get_economy(user_id, chat_id)
    if pr > 0 and eco[0] >= pr:
        update_economy(user_id, chat_id, rubles=eco[0]-pr)
        if name == "Цепи (защита раба)":
            add_chain(user_id, chat_id)
            return True, f"Вы купили {name}."
        elif name == "VIP-статус (7 дней)":
            return True, f"Вы купили {name}. VIP-статус активирован на 7 дней."
        else:
            return True, f"Вы купили {name}."
    else:
        return False, f"Недостаточно рублей. Нужно {pr}."

# ========== БОНУС ==========
def give_daily_bonus(user_id, chat_id):
    eco = get_economy(user_id, chat_id)
    last = eco[5]
    now = int(time.time())
    if now - last < 86400:
        return False, f"Бонус можно получить через {86400 - (now - last)} секунд."
    bonus = random.randint(100, 500)
    update_economy(user_id, chat_id, rubles=eco[0]+bonus, last_bonus=now)
    return True, f"Вы получили ежедневный бонус {bonus} рублей!"

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ КОМАНД ==========
def get_target_user(event, text):
    match = re.search(r'\[id(\d+)\|', text)
    if match:
        return int(match.group(1))
    numbers = re.findall(r'\b(\d+)\b', text)
    if numbers:
        return int(numbers[0])
    if hasattr(event, 'reply_message') and event.reply_message:
        return event.reply_message['from_id']
    return None

# ========== INLINE-МЕНЮ ==========
def send_roles_menu(chat_id, user_id):
    keyboard = VkKeyboard(inline=True)
    c.execute("SELECT role_name FROM roles")
    roles = [row[0] for row in c.fetchall()]
    for role in roles:
        keyboard.add_button(role.capitalize(), color=VkKeyboardColor.PRIMARY, payload={"cmd": "role_menu", "role": role})
        keyboard.add_line()
    vk.messages.send(peer_id=chat_id, random_id=0, message="Выберите роль для редактирования прав:", keyboard=keyboard.get_keyboard())

def send_permissions_menu(chat_id, role_name):
    perms = get_role_permissions(role_name)
    keyboard = VkKeyboard(inline=True)
    for perm, val in perms.items():
        color = VkKeyboardColor.POSITIVE if val else VkKeyboardColor.SECONDARY
        keyboard.add_button(f"{perm}: {'вкл' if val else 'выкл'}", color=color, payload={"cmd": "toggle_perm", "role": role_name, "perm": perm})
        keyboard.add_line()
    keyboard.add_button("Назад", color=VkKeyboardColor.NEGATIVE, payload={"cmd": "back_to_roles"})
    vk.messages.send(peer_id=chat_id, random_id=0, message=f"Права роли {role_name}:", keyboard=keyboard.get_keyboard())

# ========== ВЕБ-СЕРВЕР ==========
class HelpHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/help':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            help_text = """
            <html>
            <head><title>Чат менеджер</title></head>
            <body>
            <h1>Список команд</h1>
            <ul>
                <li><b>!mute @пользователь &lt;время&gt;</b> – замутить (время: 5m, 2h, 1d)</li>
                <li><b>!unmute @пользователь</b> – снять мут</li>
                <li><b>!ban @пользователь [причина]</b> – забанить и кикнуть</li>
                <li><b>!unban @пользователь</b> – разбанить</li>
                <li><b>!warn @пользователь [причина]</b> – выдать предупреждение</li>
                <li><b>!unwarn @пользователь</b> – снять предупреждение</li>
                <li><b>!addrole &lt;название&gt;</b> – создать новую роль</li>
                <li><b>!delrole &lt;название&gt;</b> – удалить роль</li>
                <li><b>!editcmd &lt;роль&gt; &lt;право&gt; &lt;0/1&gt;</b> – разрешить/запретить команду</li>
                <li><b>!setrole @пользователь &lt;роль&gt;</b> – назначить роль</li>
                <li><b>!roles</b> – список ролей</li>
                <li><b>/stats [@пользователь]</b> – информация о пользователе</li>
                <li><b>/mtop</b> – топ по сообщениям</li>
                <li><b>/баланс</b> – баланс в рублях</li>
                <li><b>/евро</b> – баланс в евро</li>
                <li><b>/доллар</b> – баланс в долларах</li>
                <li><b>/страна [название]</b> – установить страну</li>
                <li><b>/раб @пользователь</b> – информация о рабе</li>
                <li><b>/купитьраба @пользователь &lt;цена&gt;</b> – купить раба</li>
                <li><b>/продатьраба @пользователь</b> – продать раба</li>
                <li><b>/цепи @пользователь</b> – защитить раба цепями</li>
                <li><b>/agent</b> – список агентов. /agent menu – меню управления правами</li>
                <li><b>/quest</b> – список квестов</li>
                <li><b>/репорт &lt;текст&gt;</b> – создать тикет</li>
                <li><b>/ответ &lt;id&gt; &lt;текст&gt;</b> – ответить на тикет</li>
                <li><b>/start</b> – активировать текущую беседу</li>
                <li><b>/магазин</b> – список товаров</li>
                <li><b>/бонус</b> – получить ежедневный бонус</li>
                <li><b>/пинг</b> – статистика работы бота</li>
                <li><b>/help</b> – эта страница</li>
            </ul>
            </body>
            </html>
            """
            self.wfile.write(help_text.encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

def start_web_server():
    server = HTTPServer(('0.0.0.0', WEB_PORT), HelpHandler)
    server.serve_forever()

web_thread = threading.Thread(target=start_web_server, daemon=True)
web_thread.start()

# ========== ОБРАБОТЧИК КОМАНД ==========
def handle_command(event, text):
    user_id = event.user_id
    chat_id = event.peer_id
    if chat_id <= 2000000000:
        return

    if is_banned(user_id, chat_id):
        try:
            vk.messages.delete(message_ids=[event.message_id], delete_for_all=1)
        except:
            pass
        return

    if is_muted(user_id, chat_id):
        try:
            vk.messages.delete(message_ids=[event.message_id], delete_for_all=1)
            send_message(chat_id, f"{get_user_link(user_id)}, вы замьючены и не можете писать в чат.", reply_to=event.message_id)
        except:
            pass
        return

    add_message_count(user_id, chat_id)

    parts = text.split()
    if not parts:
        return
    command = parts[0].lower()

    # ===== СТАТИСТИКА =====
    if command in ["/stats", "/стата"]:
        target = get_target_user(event, text) or user_id
        eco = get_economy(target, chat_id)
        user_data = get_user_data(target, chat_id)
        joined_info = get_user_joined(target, chat_id)
        joined_at = joined_info[0]
        invited_by = joined_info[1]
        msg_count = eco[4]
        vip_status, vip_until = get_vip_status(target, chat_id)
        is_agent_flag = is_agent(target)
        tickets_answered = 0
        if is_agent_flag:
            c.execute("SELECT COUNT(*) FROM tickets WHERE answered_by=?", (target,))
            tickets_answered = c.fetchone()[0]
        name = get_user_name(target)
        banned_status = "да" if user_data[3] else "нет"
        joined_str = datetime.fromtimestamp(joined_at).strftime("%d.%m.%Y %H:%M") if joined_at else "неизвестно"
        inviter_str = f"[id{invited_by}|]" if invited_by else "неизвестно"
        vip_str = "да" if vip_status else "нет"
        if vip_status:
            vip_str += f" (до {datetime.fromtimestamp(vip_until).strftime('%d.%m.%Y')})"

        msg = f"🔍 Информация о [id{target}|{name}]:\n\n"
        msg += f"🗣 Статус: {user_data[0]}\n"
        if is_agent_flag:
            msg += f"🐩 Агент поддержки (обработано тикетов: {tickets_answered})\n"
        msg += f"⚠ Предупреждений: {user_data[2]}/{WARN_LIMIT}\n"
        msg += f"🚧 Блокировка чата: {banned_status}\n"
        msg += f"📅 Дата появления в чате: {joined_str}\n"
        msg += f"💎 VIP статус: {vip_str}\n"
        msg += f"✍ Сообщений отправлено: {msg_count}\n"
        msg += f"👫 Пригласил(а): {inviter_str}\n"
        msg += f"⚙ ID: {target}\n"
        msg += f"💰 Баланс: {eco[0]} руб., {eco[1]} дол., {eco[2]} евро"
        send_message(chat_id, msg, reply_to=event.message_id)

    elif command in ["/mtop", "/топ"]:
        top = get_message_top(chat_id, 10)
        if not top:
            send_message(chat_id, "Нет данных.", reply_to=event.message_id)
            return
        msg = "Топ по сообщениям:\n"
        for i, (uid, cnt) in enumerate(top, 1):
            msg += f"{i}. [id{uid}|] - {cnt} сообщений\n"
        send_message(chat_id, msg, reply_to=event.message_id)

    # ===== ЭКОНОМИКА =====
    elif command in ["/баланс", "/balance"]:
        eco = get_economy(user_id, chat_id)
        send_message(chat_id, f"Ваш баланс: {eco[0]} руб.", reply_to=event.message_id)

    elif command in ["/евро", "/euro"]:
        eco = get_economy(user_id, chat_id)
        send_message(chat_id, f"Ваш баланс: {eco[2]} евро.", reply_to=event.message_id)

    elif command in ["/доллар", "/dollar"]:
        eco = get_economy(user_id, chat_id)
        send_message(chat_id, f"Ваш баланс: {eco[1]} долларов.", reply_to=event.message_id)

    elif command in ["/страна", "/country"]:
        if len(parts) < 2:
            eco = get_economy(user_id, chat_id)
            send_message(chat_id, f"Ваша страна: {eco[3]}", reply_to=event.message_id)
        else:
            country = " ".join(parts[1:])
            update_economy(user_id, chat_id, country=country)
            send_message(chat_id, f"Страна установлена: {country}", reply_to=event.message_id)

    elif command in ["/бонус", "/bonus"]:
        res, msg = give_daily_bonus(user_id, chat_id)
        send_message(chat_id, msg, reply_to=event.message_id)

    # ===== РАБЫ =====
    elif command == "/раб":
        target = get_target_user(event, text)
        if not target:
            send_message(chat_id, "Укажите пользователя.", reply_to=event.message_id)
            return
        c.execute("SELECT owner_id, price, chained FROM slaves WHERE slave_id=? AND chat_id=?", (target, chat_id))
        slave_info = c.fetchone()
        if slave_info:
            owner_id, price, chained = slave_info
            status = "защищён цепями" if chained else "не защищён"
            send_message(chat_id, f"[id{target}|] является рабом [id{owner_id}|] (цена: {price}, {status})", reply_to=event.message_id)
        else:
            send_message(chat_id, f"[id{target}|] не является рабом.", reply_to=event.message_id)

    elif command == "/купитьраба":
        if len(parts) < 3:
            send_message(chat_id, "Использование: /купитьраба @пользователь цена", reply_to=event.message_id)
            return
        target = get_target_user(event, text)
        if not target:
            send_message(chat_id, "Пользователь не найден.", reply_to=event.message_id)
            return
        try:
            price = int(parts[2])
        except:
            send_message(chat_id, "Цена должна быть числом.", reply_to=event.message_id)
            return
        res, msg = buy_slave(user_id, target, chat_id, price)
        send_message(chat_id, msg, reply_to=event.message_id)

    elif command == "/продатьраба":
        target = get_target_user(event, text)
        if not target:
            send_message(chat_id, "Укажите пользователя.", reply_to=event.message_id)
            return
        res, msg = sell_slave(user_id, target, chat_id)
        send_message(chat_id, msg, reply_to=event.message_id)

    elif command == "/цепи":
        target = get_target_user(event, text)
        if not target:
            send_message(chat_id, "Укажите раба.", reply_to=event.message_id)
            return
        res, msg = protect_slave(user_id, target, chat_id)
        send_message(chat_id, msg, reply_to=event.message_id)

    # ===== АГЕНТЫ =====
    elif command == "/agent":
        if len(parts) == 1:
            c.execute("SELECT user_id FROM agents")
            agents = c.fetchall()
            if agents:
                msg = "Агенты:\n" + "\n".join(f"[id{uid[0]}|]" for uid in agents)
            else:
                msg = "Агентов нет."
            send_message(chat_id, msg, reply_to=event.message_id)
            return
        sub = parts[1].lower()
        if sub == "add":
            if not has_permission(user_id, chat_id, "editcmd"):
                send_message(chat_id, "Недостаточно прав.", reply_to=event.message_id)
                return
            target = get_target_user(event, text)
            if not target:
                send_message(chat_id, "Укажите пользователя.", reply_to=event.message_id)
                return
            add_agent(target)
            send_message(chat_id, f"Агент [id{target}|] добавлен.", reply_to=event.message_id)
        elif sub == "del":
            if not has_permission(user_id, chat_id, "editcmd"):
                send_message(chat_id, "Недостаточно прав.", reply_to=event.message_id)
                return
            target = get_target_user(event, text)
            if not target:
                send_message(chat_id, "Укажите пользователя.", reply_to=event.message_id)
                return
            remove_agent(target)
            send_message(chat_id, f"Агент [id{target}|] удалён.", reply_to=event.message_id)
        elif sub == "info":
            target = get_target_user(event, text) or user_id
            if is_agent(target):
                send_message(chat_id, f"[id{target}|] является агентом.", reply_to=event.message_id)
            else:
                send_message(chat_id, f"[id{target}|] не является агентом.", reply_to=event.message_id)
        elif sub == "menu":
            if not has_permission(user_id, chat_id, "editcmd"):
                send_message(chat_id, "Недостаточно прав.", reply_to=event.message_id)
                return
            send_roles_menu(chat_id, user_id)
        else:
            send_message(chat_id, "Неизвестная подкоманда. Используйте: /agent add/del/info/menu", reply_to=event.message_id)

    # ===== КВЕСТЫ =====
    elif command == "/quest":
        quests = get_active_quests()
        if not quests:
            send_message(chat_id, "Нет активных квестов.", reply_to=event.message_id)
            return
        msg = "Доступные квесты:\n"
        for qid, name, desc, rub, dol, eur in quests:
            msg += f"{qid}. {name} – {desc} (награда: {rub} руб., {dol} дол., {eur} евро)\n"
        send_message(chat_id, msg, reply_to=event.message_id)

    elif command == "/infoquest":
        if len(parts) < 2:
            send_message(chat_id, "Использование: /infoquest <id>", reply_to=event.message_id)
            return
        try:
            qid = int(parts[1])
        except:
            send_message(chat_id, "ID должен быть числом.", reply_to=event.message_id)
            return
        c.execute("SELECT name, description, rubles, dollars, euros FROM quests WHERE quest_id=?", (qid,))
        quest = c.fetchone()
        if not quest:
            send_message(chat_id, "Квест не найден.", reply_to=event.message_id)
            return
        name, desc, rub, dol, eur = quest
        msg = f"Квест {qid}: {name}\n{desc}\nНаграда: {rub} руб., {dol} дол., {eur} евро."
        send_message(chat_id, msg, reply_to=event.message_id)

    # ===== ТИКЕТЫ =====
    elif command in ["/репорт", "/report"]:
        if len(parts) < 2:
            send_message(chat_id, "Использование: /репорт текст", reply_to=event.message_id)
            return
        ticket_text = " ".join(parts[1:])
        ticket_id = create_ticket(user_id, chat_id, ticket_text)
        send_message(chat_id, f"Тикет #{ticket_id} создан. Ожидайте ответа.", reply_to=event.message_id)

    elif command in ["/ответ", "/answer"]:
        if len(parts) < 3:
            send_message(chat_id, "Использование: /ответ <id> текст", reply_to=event.message_id)
            return
        try:
            ticket_id = int(parts[1])
        except:
            send_message(chat_id, "ID должен быть числом.", reply_to=event.message_id)
            return
        answer_text = " ".join(parts[2:])
        if not (has_permission(user_id, chat_id, "editcmd") or is_agent(user_id)):
            send_message(chat_id, "Недостаточно прав.", reply_to=event.message_id)
            return
        answer_ticket(ticket_id, answer_text, user_id)
        send_message(chat_id, f"Ответ на тикет #{ticket_id} отправлен.", reply_to=event.message_id)

    # ===== АДМИН-КОМАНДЫ =====
    elif command == "/рассылка":
        if not has_permission(user_id, chat_id, "editcmd"):
            send_message(chat_id, "Недостаточно прав.", reply_to=event.message_id)
            return
        if len(parts) < 2:
            send_message(chat_id, "Использование: /рассылка текст", reply_to=event.message_id)
            return
        msg = " ".join(parts[1:])
        c.execute("SELECT chat_id FROM chats WHERE active=1")
        chats = c.fetchall()
        for (cid,) in chats:
            try:
                send_message(cid, msg)
                time.sleep(0.1)
            except:
                pass
        send_message(chat_id, "Рассылка выполнена.", reply_to=event.message_id)

    elif command == "/givemoney":
        if not has_permission(user_id, chat_id, "editcmd"):
            send_message(chat_id, "Недостаточно прав.", reply_to=event.message_id)
            return
        target = get_target_user(event, text)
        if not target or len(parts) < 3:
            send_message(chat_id, "Использование: /givemoney @пользователь сумма", reply_to=event.message_id)
            return
        try:
            amount = int(parts[2])
        except:
            send_message(chat_id, "Сумма должна быть числом.", reply_to=event.message_id)
            return
        eco = get_economy(target, chat_id)
        update_economy(target, chat_id, rubles=eco[0]+amount)
        send_message(chat_id, f"Выдано {amount} руб. [id{target}|].", reply_to=event.message_id)

    elif command == "/givevip":
        if not has_permission(user_id, chat_id, "editcmd"):
            send_message(chat_id, "Недостаточно прав.", reply_to=event.message_id)
            return
        target = get_target_user(event, text)
        if not target:
            send_message(chat_id, "Укажите пользователя.", reply_to=event.message_id)
            return
        vip_until = int(time.time()) + 7 * 86400
        update_economy(target, chat_id, vip_until=vip_until)
        send_message(chat_id, f"VIP выдан [id{target}|] на 7 дней.", reply_to=event.message_id)

    elif command == "/getbotstats":
        if not has_permission(user_id, chat_id, "editcmd"):
            send_message(chat_id, "Недостаточно прав.", reply_to=event.message_id)
            return
        c.execute("SELECT COUNT(*) FROM chats WHERE active=1")
        active_chats = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM slaves")
        total_slaves = c.fetchone()[0]
        msg = f"Активных бесед: {active_chats}\nВсего пользователей в БД: {total_users}\nВсего рабов: {total_slaves}"
        send_message(chat_id, msg, reply_to=event.message_id)

    elif command == "/start":
        if is_chat_active(chat_id):
            send_message(chat_id, "Беседа уже активирована.", reply_to=event.message_id)
            return
        activate_chat(chat_id, user_id)
        send_message(chat_id, f"✅ Беседа активирована! Владелец: [id{user_id}|].\nИспользуйте /help для списка команд.", reply_to=event.message_id)

    elif command == "/магазин":
        items = get_shop_items()
        if not items:
            send_message(chat_id, "Магазин пуст.", reply_to=event.message_id)
            return
        msg = "Магазин:\n"
        for item_id, name, pr, pd, pe, desc in items:
            msg += f"{item_id}. {name} – {pr} руб. (или {pd} дол., {pe} евро)\n   {desc}\n"
        send_message(chat_id, msg, reply_to=event.message_id)

    elif command in ["/пинг", "/ping"]:
        uptime_seconds = int(time.time() - stats['start_time'])
        uptime_str = ""
        days = uptime_seconds // 86400
        hours = (uptime_seconds % 86400) // 3600
        minutes = (uptime_seconds % 3600) // 60
        seconds = uptime_seconds % 60
        if days > 0:
            uptime_str += f"{days} дн. "
        if hours > 0 or days > 0:
            uptime_str += f"{hours} ч. "
        uptime_str += f"{minutes} мин. {seconds} сек."

        avg_req = sum(stats['request_times']) / len(stats['request_times']) if stats['request_times'] else 0
        avg_cmd = sum(stats['command_times']) / len(stats['command_times']) if stats['command_times'] else 0
        msg = f"📊 Статистика бота\n⏱ Uptime: {uptime_str}\n📨 Среднее время запроса: {avg_req:.2f} мс\n⚙ Среднее время команды: {avg_cmd:.2f} мс"
        send_message(chat_id, msg, reply_to=event.message_id)

    elif command == "/help":
        help_url = f"http://127.0.0.1:{WEB_PORT}/help"
        send_message(chat_id, f"Список команд: {help_url}", reply_to=event.message_id)

    # ===== СТАРЫЕ КОМАНДЫ =====
    elif command == "!editcmd":
        if not has_permission(user_id, chat_id, "editcmd"):
            send_message(chat_id, "Недостаточно прав.", reply_to=event.message_id)
            return
        if len(parts) < 4:
            send_message(chat_id, "Использование: !editcmd <роль> <право> <0/1>", reply_to=event.message_id)
            return
        role_name = parts[1].lower()
        perm_name = parts[2].lower()
        value = parts[3]
        if value not in ['0', '1']:
            send_message(chat_id, "Значение должно быть 0 или 1.", reply_to=event.message_id)
            return
        if set_role_permission(role_name, perm_name, value):
            send_message(chat_id, f"Право {perm_name} для роли {role_name} установлено в {value}.", reply_to=event.message_id)
        else:
            send_message(chat_id, "Неверное название права или роли.", reply_to=event.message_id)

    elif command == "!mute":
        if not has_permission(user_id, chat_id, "mute"):
            send_message(chat_id, "Недостаточно прав.", reply_to=event.message_id)
            return
        if len(parts) < 3:
            send_message(chat_id, "Использование: !mute @пользователь <время>[m/h/d]", reply_to=event.message_id)
            return
        mention = re.search(r'\[id(\d+)\|', text)
        if not mention:
            send_message(chat_id, "Упомяните пользователя.", reply_to=event.message_id)
            return
        target_id = int(mention.group(1))
        time_str = parts[2]
        duration = 0
        if time_str.endswith('m'):
            duration = int(time_str[:-1])
        elif time_str.endswith('h'):
            duration = int(time_str[:-1]) * 60
        elif time_str.endswith('d'):
            duration = int(time_str[:-1]) * 1440
        else:
            send_message(chat_id, "Некорректный формат времени.", reply_to=event.message_id)
            return
        if duration <= 0:
            send_message(chat_id, "Время должно быть положительным.", reply_to=event.message_id)
            return
        response = mute_user(target_id, chat_id, duration)
        send_message(chat_id, response, reply_to=event.message_id)

    elif command == "!unmute":
        if not has_permission(user_id, chat_id, "unmute"):
            send_message(chat_id, "Недостаточно прав.", reply_to=event.message_id)
            return
        mention = re.search(r'\[id(\d+)\|', text)
        if not mention:
            send_message(chat_id, "Упомяните пользователя.", reply_to=event.message_id)
            return
        target_id = int(mention.group(1))
        response = unmute_user(target_id, chat_id)
        send_message(chat_id, response, reply_to=event.message_id)

    elif command == "!ban":
        if not has_permission(user_id, chat_id, "ban"):
            send_message(chat_id, "Недостаточно прав.", reply_to=event.message_id)
            return
        mention = re.search(r'\[id(\d+)\|', text)
        if not mention:
            send_message(chat_id, "Упомяните пользователя.", reply_to=event.message_id)
            return
        target_id = int(mention.group(1))
        reason = " ".join(parts[2:]) if len(parts) > 2 else "Не указана"
        response = ban_user(target_id, chat_id, reason)
        send_message(chat_id, response, reply_to=event.message_id)

    elif command == "!unban":
        if not has_permission(user_id, chat_id, "unban"):
            send_message(chat_id, "Недостаточно прав.", reply_to=event.message_id)
            return
        mention = re.search(r'\[id(\d+)\|', text)
        if not mention:
            send_message(chat_id, "Упомяните пользователя.", reply_to=event.message_id)
            return
        target_id = int(mention.group(1))
        response = unban_user(target_id, chat_id)
        send_message(chat_id, response, reply_to=event.message_id)

    elif command == "!warn":
        if not has_permission(user_id, chat_id, "warn"):
            send_message(chat_id, "Недостаточно прав.", reply_to=event.message_id)
            return
        mention = re.search(r'\[id(\d+)\|', text)
        if not mention:
            send_message(chat_id, "Упомяните пользователя.", reply_to=event.message_id)
            return
        target_id = int(mention.group(1))
        reason = " ".join(parts[2:]) if len(parts) > 2 else "Не указана"
        response = add_warn(target_id, chat_id, reason)
        send_message(chat_id, response, reply_to=event.message_id)

    elif command == "!unwarn":
        if not has_permission(user_id, chat_id, "unwarn"):
            send_message(chat_id, "Недостаточно прав.", reply_to=event.message_id)
            return
        mention = re.search(r'\[id(\d+)\|', text)
        if not mention:
            send_message(chat_id, "Упомяните пользователя.", reply_to=event.message_id)
            return
        target_id = int(mention.group(1))
        add_user(target_id, chat_id)
        warns = get_user_data(target_id, chat_id)[2]
        if warns > 0:
            update_user(target_id, chat_id, warns=warns-1)
            send_message(chat_id, f"Количество варнов уменьшено. Теперь: {warns-1}", reply_to=event.message_id)
        else:
            send_message(chat_id, "У пользователя нет варнов.", reply_to=event.message_id)

    elif command == "!addrole":
        if not has_permission(user_id, chat_id, "addrole"):
            send_message(chat_id, "Недостаточно прав.", reply_to=event.message_id)
            return
        if len(parts) < 2:
            send_message(chat_id, "Использование: !addrole <название>", reply_to=event.message_id)
            return
        role_name = parts[1].lower()
        if role_name in ["user", "moderator", "admin"]:
            send_message(chat_id, "Нельзя переопределить стандартные роли.", reply_to=event.message_id)
            return
        add_role(role_name)
        send_message(chat_id, f"Роль '{role_name}' создана.", reply_to=event.message_id)

    elif command == "!delrole":
        if not has_permission(user_id, chat_id, "addrole"):
            send_message(chat_id, "Недостаточно прав.", reply_to=event.message_id)
            return
        if len(parts) < 2:
            send_message(chat_id, "Использование: !delrole <название>", reply_to=event.message_id)
            return
        role_name = parts[1].lower()
        if role_name in ["user", "moderator", "admin"]:
            send_message(chat_id, "Нельзя удалить стандартную роль.", reply_to=event.message_id)
            return
        if delete_role(role_name):
            send_message(chat_id, f"Роль '{role_name}' удалена.", reply_to=event.message_id)
        else:
            send_message(chat_id, "Нельзя удалить роль, пока есть пользователи с ней.", reply_to=event.message_id)

    elif command == "!setrole":
        if not has_permission(user_id, chat_id, "addrole"):
            send_message(chat_id, "Недостаточно прав.", reply_to=event.message_id)
            return
        if len(parts) < 3:
            send_message(chat_id, "Использование: !setrole @пользователь <роль>", reply_to=event.message_id)
            return
        mention = re.search(r'\[id(\d+)\|', text)
        if not mention:
            send_message(chat_id, "Упомяните пользователя.", reply_to=event.message_id)
            return
        target_id = int(mention.group(1))
        role_name = parts[2].lower()
        c.execute("SELECT role_name FROM roles WHERE role_name=?", (role_name,))
        if not c.fetchone():
            send_message(chat_id, "Роль не существует.", reply_to=event.message_id)
            return
        set_user_role(target_id, chat_id, role_name)
        send_message(chat_id, f"Пользователю назначена роль {role_name}.", reply_to=event.message_id)

    elif command == "!roles":
        c.execute("SELECT role_name, permissions FROM roles")
        roles = c.fetchall()
        if not roles:
            send_message(chat_id, "Нет ролей.", reply_to=event.message_id)
            return
        msg = "Роли и права:\n"
        for role_name, perms_json in roles:
            perms = json.loads(perms_json)
            perms_str = ", ".join([f"{k}:{v}" for k, v in perms.items()])
            msg += f"{role_name}: {perms_str}\n"
        send_message(chat_id, msg, reply_to=event.message_id)

# ========== ОСНОВНОЙ ЦИКЛ ==========
def main():
    print("🤖 Бот запущен!")
    print(f"📊 Веб-сервер на порту {WEB_PORT}")
    print("🔄 Ожидание сообщений...")
    print("💡 При добавлении бота в беседу будет отправлено приветствие")
    
    last_ping = time.time()
    
    while True:
        try:
            for event in longpoll.listen():
                if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                    text = event.text.strip()
                    if text:
                        start = time.time()
                        handle_command(event, text)
                        add_command_time((time.time() - start) * 1000)
                
                elif event.type == VkEventType.USER_JOIN:
                    chat_id = event.peer_id
                    user_id = event.user_id
                    
                    # Проверяем, это бот добавлен или пользователь
                    if user_id == -GROUP_ID or user_id == int(str(GROUP_ID)):
                        # Бота добавили в беседу
                        print(f"✅ Бот добавлен в беседу {chat_id}")
                        
                        # Создаём клавиатуру с кнопкой "НАЧАТЬ"
                        keyboard = VkKeyboard(one_time=True)
                        keyboard.add_button("НАЧАТЬ", color=VkKeyboardColor.POSITIVE)
                        
                        # Отправляем приветствие
                        welcome_msg = "🤖 Привет! Я бот-менеджер чата.\n\n"
                        welcome_msg += "⚠️ Для корректной работы мне нужны права администратора!\n"
                        welcome_msg += "🔧 Пожалуйста, выдайте мне права:\n"
                        welcome_msg += "• Управление сообщениями\n"
                        welcome_msg += "• Удаление сообщений\n"
                        welcome_msg += "• Исключение участников\n\n"
                        welcome_msg += "✅ После выдачи прав нажмите кнопку НАЧАТЬ или напишите /start"
                        
                        send_message(chat_id, welcome_msg, keyboard=keyboard)
                    else:
                        # Обычный пользователь зашёл в беседу
                        if is_banned(user_id, chat_id):
                            kick_banned_user(user_id, chat_id)
                        else:
                            c.execute("SELECT 1 FROM users WHERE user_id=? AND chat_id=?", (user_id, chat_id))
                            if not c.fetchone():
                                add_user(user_id, chat_id)
                                now = int(time.time())
                                c.execute("UPDATE users SET joined_at=? WHERE user_id=? AND chat_id=?", (now, user_id, chat_id))
                                conn.commit()
                
                elif event.type == VkEventType.MESSAGE_EVENT:
                    if event.payload:
                        payload = json.loads(event.payload)
                        
                        # Обработка нажатия кнопки "НАЧАТЬ"
                        if payload.get("cmd") == "start":
                            chat_id = event.peer_id
                            user_id = event.user_id
                            
                            if is_chat_active(chat_id):
                                send_message(chat_id, "✅ Беседа уже активирована!")
                            else:
                                activate_chat(chat_id, user_id)
                                send_message(chat_id, f"✅ Беседа активирована! Владелец: [id{user_id}|].\nИспользуйте /help для списка команд.")
                            
                            vk.messages.sendMessageEventAnswer(
                                event_id=event.event_id,
                                peer_id=event.peer_id,
                                user_id=event.user_id,
                                event_data=json.dumps({"type": "show_snackbar", "text": "Активация выполнена!"})
                            )
                        elif payload.get("cmd") == "give_vip":
                            target_id = payload.get("user_id")
                            if target_id:
                                vip_until = int(time.time()) + 7 * 86400
                                update_economy(target_id, event.peer_id, vip_until=vip_until)
                                send_message(event.peer_id, f"VIP выдан [id{target_id}|] на 7 дней.")
                            else:
                                send_message(event.peer_id, "Ошибка: пользователь не указан.")
                            vk.messages.sendMessageEventAnswer(
                                event_id=event.event_id,
                                peer_id=event.peer_id,
                                user_id=event.user_id,
                                event_data=json.dumps({"type": "show_snackbar", "text": "Выдано!"})
                            )
                        elif payload.get("cmd") == "role_menu":
                            role = payload.get("role")
                            send_permissions_menu(event.peer_id, role)
                        elif payload.get("cmd") == "toggle_perm":
                            role = payload.get("role")
                            perm = payload.get("perm")
                            perms = get_role_permissions(role)
                            new_val = 1 if not perms.get(perm, 0) else 0
                            set_role_permission(role, perm, new_val)
                            send_permissions_menu(event.peer_id, role)
                        elif payload.get("cmd") == "back_to_roles":
                            send_roles_menu(event.peer_id, event.user_id)
                
                # Keepalive
                if time.time() - last_ping > 5:
                    print(".", end="", flush=True)
                    last_ping = time.time()
                    
        except Exception as e:
            print(f"\n❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()
            print("🔄 Перезапуск через 5 секунд...")
            time.sleep(5)
            continue

if __name__ == "__main__":
    main()
