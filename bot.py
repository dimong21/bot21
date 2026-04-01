import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
import sqlite3
import random
import time
import threading
import re
from datetime import datetime, timedelta
import json
import os

class VKChatManager:
    def __init__(self, group_token, group_id):
        """Инициализация бота"""
        self.group_token = group_token
        self.group_id = group_id
        self.vk = vk_api.VkApi(token=group_token)
        self.longpoll = VkBotLongPoll(self.vk, group_id)
        self.vk_api = self.vk.get_api()
        
        # ========== СУПЕР-АДМИНЫ (кто может выдавать доступ к /agent) ==========
        # Только эти пользователи могут использовать /agent add/del и изменять права
        self.super_admins = [
            771565937,  # Замените на реальные ID
            # Добавьте сюда ID тех, кто может выдавать доступ к /agent
        ]
        
        # Курсы валют
        self.exchange_rates = {
            'usd_to_rub': 90.0,   # 1 USD = 90 RUB
            'eur_to_rub': 98.0,   # 1 EUR = 98 RUB
            'btc_to_usd': 60000,  # 1 BTC = 60000 USD
            'btc_to_rub': 5400000, # 1 BTC = 5.4M RUB
        }
        
        # Инициализация базы данных
        self.init_database()
        
        # Загрузка конфигурации
        self.config = self.load_config()
        
        # Загрузка курсов валют из конфига
        self.load_exchange_rates()
        
        # Префиксы команд
        self.prefixes = ['/', '!', '.']
        
        # Временные хранилища
        self.waiting_for_agent_id = {}
        self.sysinfo_target = {}
        
        # Руссификация команд
        self.commands = {
            'ban': ['/ban', '/бан', '!ban', '!бан', '.ban', '.бан'],
            'unban': ['/unban', '/разбан', '!unban', '!разбан', '.unban', '.разбан'],
            'mute': ['/mute', '/мут', '!mute', '!мут', '.mute', '.мут'],
            'unmute': ['/unmute', '/размут', '!unmute', '!размут', '.unmute', '.размут'],
            'warn': ['/warn', '/варн', '!warn', '!варн', '.warn', '.варн'],
            'kick': ['/kick', '/кик', '!kick', '!кик', '.kick', '.кик'],
            'ping': ['/ping', '/пинг', '!ping', '!пинг', '.ping', '.пинг'],
            'stats': ['/stats', '/статистика', '!stats', '!статистика', '.stats', '.статистика'],
            'balance': ['/balance', '/баланс', '!balance', '!баланс', '.balance', '.баланс'],
            'bonus': ['/bonus', '/бонус', '!bonus', '!бонус', '.bonus', '.бонус'],
            'transfer': ['/transfer', '/перевод', '!transfer', '!перевод', '.transfer', '.перевод'],
            'mine': ['/mine', '/майнинг', '!mine', '!майнинг', '.mine', '.майнинг'],
            'work': ['/work', '/работа', '!work', '!работа', '.work', '.работа'],
            'shop': ['/shop', '/магазин', '!shop', '!магазин', '.shop', '.магазин'],
            'buy': ['/buy', '/купить', '!buy', '!купить', '.buy', '.купить'],
            'roleslist': ['/roleslist', '/списокролей', '!roleslist', '!списокролей', '.roleslist', '.списокролей'],
            'setrole': ['/setrole', '/выдатьроль', '!setrole', '!выдатьроль', '.setrole', '.выдатьроль'],
            'addrole': ['/addrole', '/добавитьроль', '!addrole', '!добавитьроль', '.addrole', '.добавитьроль'],
            'editcmd': ['/editcmd', '/редактироватькоманду', '!editcmd', '!редактироватькоманду', '.editcmd', '.редактироватькоманду'],
            'filter': ['/filter', '/фильтр', '!filter', '!фильтр', '.filter', '.фильтр'],
            'invite': ['/invite', '/пригласить', '!invite', '!пригласить', '.invite', '.пригласить'],
            'chat_info': ['/chatinfo', '/инфобеседы', '!chatinfo', '!инфобеседы', '.chatinfo', '.инфобеседы'],
            'vip': ['/vip', '/вип', '!vip', '!вип', '.vip', '.вип'],
            'staff': ['/staff', '/персонал', '!staff', '!персонал', '.staff', '.персонал'],
            'say': ['/say', '/скажи', '!say', '!скажи', '.say', '.скажи'],
            'start': ['/start', '/старт', '!start', '!старт', '.start', '.старт'],
            'help': ['/help', '/помощь', '!help', '!помощь', '.help', '.помощь'],
            'report': ['/report', '/репорт', '!report', '!репорт', '.report', '.репорт'],
            'agent': ['/agent', '/агент', '!agent', '!агент', '.agent', '.агент'],
            'reports': ['/reports', '/репорты', '!reports', '!репорты', '.reports', '.репорты'],
            'botadmins': ['/botadmins', '/ботадмины', '!botadmins', '!ботадмины', '.botadmins', '.ботадмины'],
            'mutereports': ['/mutereports', '/мутрепорты', '!mutereports', '!мутрепорты', '.mutereports', '.мутрепорты'],
            'unmutereports': ['/unmutereports', '/размутрепорты', '!unmutereports', '!размутрепорты', '.unmutereports', '.размутрепорты'],
            'givemoney': ['/givemoney', '/выдатьденьги', '!givemoney', '!выдатьденьги', '.givemoney', '.выдатьденьги'],
            'givevip': ['/givevip', '/выдатьвип', '!givevip', '!выдатьвип', '.givevip', '.выдатьвип'],
            'sysban': ['/sysban', '/системныйбан', '!sysban', '!системныйбан', '.sysban', '.системныйбан'],
            'sysunban': ['/sysunban', '/системныйразбан', '!sysunban', '!системныйразбан', '.sysunban', '.системныйразбан'],
            'sysrole': ['/sysrole', '/системнаяроль', '!sysrole', '!системнаяроль', '.sysrole', '.системнаяроль'],
            'sysinfo': ['/sysinfo', '/системнаяинформация', '!sysinfo', '!системнаяинформация', '.sysinfo', '.системнаяинформация'],
            'snick': ['/snick', '/сетник', '!snick', '!сетник', '.snick', '.сетник'],
            'rnick': ['/rnick', '/делник', '!rnick', '!делник', '.rnick', '.делник'],
            'delkick': ['/delkick', '/делкик', '!delkick', '!делкик', '.delkick', '.делкик'],
            'nonames': ['/nonames', '/безников', '!nonames', '!безников', '.nonames', '.безников'],
            'ponicku': ['/ponicku', '/понику', '!ponicku', '!понику', '.ponicku', '.понику'],
            'slaves': ['/slaves', '/рабы', '!slaves', '!рабы', '.slaves', '.рабы'],
            'setrate': ['/setrate', '/установитькурс', '!setrate', '!установитькурс', '.setrate', '.установитькурс'],
            'rates': ['/rates', '/курсы', '!rates', '!курсы', '.rates', '.курсы'],
        }
        
        # Цены в магазине
        self.shop_items = {
            'vip1': {
                'name': '🌟 VIP статус I уровня', 
                'price': 5000, 
                'type': 'vip', 
                'level': 1,
                'benefits': {
                    'max_chats': 50,
                    'max_unions': 30,
                    'daily_say': 50
                }
            },
            'vip2': {
                'name': '💎 VIP статус II уровня', 
                'price': 15000, 
                'type': 'vip', 
                'level': 2,
                'benefits': {
                    'max_chats': 120,
                    'max_unions': 70,
                    'daily_say': 120
                }
            },
            'vip3': {
                'name': '👑 VIP статус III уровня', 
                'price': 35000, 
                'type': 'vip', 
                'level': 3,
                'benefits': {
                    'max_chats': 250,
                    'max_unions': 150,
                    'daily_say': 300
                }
            },
            'bitcoin_miner': {'name': '⛏️ Майнер биткойнов', 'price': 500, 'type': 'item', 'value': 'miner', 'hourly': 0.1},
        }
        
        # Магазин с инлайн кнопками
        self.inline_shop = {
            'phones': {
                'iPhone 15 Pro': 999,
                'iPhone 15 Pro Max': 1199,
                'Samsung Galaxy S24 Ultra': 1299,
                'Samsung Galaxy S24': 899,
                'Google Pixel 8 Pro': 999,
                'Google Pixel 8': 699,
                'Xiaomi 14 Ultra': 899,
                'Xiaomi 14 Pro': 699,
                'OnePlus 12': 749,
                'Nothing Phone 2': 599
            },
            'houses': {
                '🏠 Квартира-студия': 50000,
                '🏡 1-комнатная квартира': 100000,
                '🏘️ 2-комнатная квартира': 200000,
                '🏠 Загородный дом': 500000,
                '🏢 Пентхаус': 1000000,
                '🏰 Особняк': 5000000,
                '🏝️ Вилла на острове': 10000000
            },
            'clothes': {
                '👕 Футболка': 50,
                '👖 Джинсы': 100,
                '👔 Костюм': 500,
                '👟 Кроссовки': 150,
                '🧥 Пальто': 300,
                '🧢 Кепка': 30,
                '🧣 Шарф': 40,
                '🧤 Перчатки': 35,
                '👗 Платье': 250,
                '👘 Халат': 80
            },
            'items': {
                '💍 Кольцо': 200,
                '⌚ Часы': 500,
                '💎 Бриллиант': 1000,
                '🎮 Игровая приставка': 400,
                '📚 Книга': 30,
                '💻 Ноутбук': 800,
                '📱 Смартфон': 600,
                '🎧 Наушники': 100,
                '📷 Фотоаппарат': 450,
                '🚗 Машина': 5000
            }
        }
        
        # Эмодзи для статусов
        self.status_emojis = {
            'user': '👤',
            'moderator': '🛡️',
            'admin': '⚡',
            'owner': '👑'
        }
        
        # Подозрительные логи
        self.suspicious_logs = []
        
        print("🤖 Бот успешно запущен!")
    
    def load_exchange_rates(self):
        """Загрузка курсов валют из конфига"""
        try:
            with open('exchange_rates.json', 'r', encoding='utf-8') as f:
                saved_rates = json.load(f)
                self.exchange_rates.update(saved_rates)
        except:
            self.save_exchange_rates()
    
    def save_exchange_rates(self):
        """Сохранение курсов валют"""
        try:
            with open('exchange_rates.json', 'w', encoding='utf-8') as f:
                json.dump(self.exchange_rates, f, ensure_ascii=False, indent=4)
        except:
            pass
    
    def is_super_admin(self, user_id):
        """Проверка, является ли пользователь супер-админом (кто может выдавать доступ к /agent)"""
        return user_id in self.super_admins
    
    def init_database(self):
        """Инициализация базы данных"""
        self.conn = sqlite3.connect('vk_bot.db', check_same_thread=False)
        self.cursor = self.conn.cursor()
        
        # Таблица пользователей
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                name TEXT,
                role TEXT DEFAULT 'user',
                vip_level INTEGER DEFAULT 0,
                vip_until TEXT,
                balance REAL DEFAULT 0,
                bitcoin REAL DEFAULT 0,
                rubles REAL DEFAULT 0,
                dollars REAL DEFAULT 0,
                euros REAL DEFAULT 0,
                warns INTEGER DEFAULT 0,
                is_muted INTEGER DEFAULT 0,
                mute_until TEXT,
                work_cooldown TEXT,
                mine_cooldown TEXT,
                last_bonus TEXT,
                join_date TEXT,
                messages_count INTEGER DEFAULT 0,
                say_used_today INTEGER DEFAULT 0,
                last_say_reset TEXT,
                is_agent INTEGER DEFAULT 0,
                agent_number INTEGER DEFAULT 0,
                tickets_processed INTEGER DEFAULT 0,
                avg_rating REAL DEFAULT 0,
                reports_muted INTEGER DEFAULT 0,
                nickname TEXT DEFAULT '',
                sysban_level INTEGER DEFAULT 0,
                sysban_by INTEGER DEFAULT 0,
                sysban_reason TEXT DEFAULT '',
                sysban_date TEXT DEFAULT ''
            )
        ''')
        
        # Таблица бесед
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS chats (
                chat_id INTEGER PRIMARY KEY,
                chat_name TEXT,
                creator_id INTEGER DEFAULT 0,
                owner_id INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 0,
                activated_at TEXT,
                created_at TEXT,
                settings TEXT DEFAULT '{}'
            )
        ''')
        
        # Таблица объединений
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS unions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER,
                name TEXT,
                created_at TEXT,
                settings TEXT DEFAULT '{}'
            )
        ''')
        
        # Таблица бесед в объединениях
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS union_chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                union_id INTEGER,
                chat_id INTEGER,
                added_at TEXT,
                FOREIGN KEY (union_id) REFERENCES unions (id)
            )
        ''')
        
        # Таблица приглашений
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS invites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                user_id INTEGER,
                inviter_id INTEGER,
                invited_at TEXT,
                FOREIGN KEY (chat_id) REFERENCES chats (chat_id),
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                FOREIGN KEY (inviter_id) REFERENCES users (user_id)
            )
        ''')
        
        # Таблица для ролей и прав
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS roles (
                role_name TEXT PRIMARY KEY,
                permissions TEXT,
                priority INTEGER DEFAULT 0
            )
        ''')
        
        # Таблица для команды с приоритетами
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS command_permissions (
                command TEXT PRIMARY KEY,
                required_role TEXT,
                priority INTEGER DEFAULT 0
            )
        ''')
        
        # Таблица для фильтров слов по беседам
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_filters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                word TEXT,
                action TEXT DEFAULT 'warn',
                added_by INTEGER,
                added_at TEXT,
                UNIQUE(chat_id, word)
            )
        ''')
        
        # Таблица для инвентаря
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                item TEXT,
                quantity INTEGER DEFAULT 1,
                purchased_at TEXT
            )
        ''')
        
        # Таблица для логов действий
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                user_id INTEGER,
                action TEXT,
                target_id INTEGER,
                reason TEXT,
                created_at TEXT
            )
        ''')
        
        # Таблица для прав агентов
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS agent_permissions (
                user_id INTEGER PRIMARY KEY,
                permissions TEXT DEFAULT '{}'
            )
        ''')
        
        # Таблица для репортов
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                reporter_id INTEGER,
                message TEXT,
                chat_id INTEGER,
                status TEXT DEFAULT 'open',
                created_at TEXT,
                closed_at TEXT,
                closed_by INTEGER,
                rating INTEGER DEFAULT 0
            )
        ''')
        
        # Таблица для рабов
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS slaves (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER,
                slave_id INTEGER,
                level INTEGER DEFAULT 1,
                exp INTEGER DEFAULT 0,
                chains INTEGER DEFAULT 0,
                last_collect TEXT,
                bought_at TEXT,
                UNIQUE(owner_id, slave_id)
            )
        ''')
        
        # Добавление базовых ролей
        default_roles = [
            ('user', '{}', 0),
            ('moderator', '{"ban": true, "mute": true, "warn": true, "kick": true, "filter": true}', 40),
            ('admin', '{"ban": true, "mute": true, "warn": true, "kick": true, "setrole": true, "filter": true, "addrole": true}', 50),
            ('owner', '{"*": true}', 100)
        ]
        
        for role in default_roles:
            self.cursor.execute('INSERT OR IGNORE INTO roles (role_name, permissions, priority) VALUES (?, ?, ?)', role)
        
        self.conn.commit()
    
    def load_config(self):
        """Загрузка конфигурации"""
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            default_config = {
                'chat_id': 0,
                'mute_time': 5,
                'warning_limit': 3,
                'work_reward': [50, 200],
                'mine_reward': [0.1, 0.5],
                'bonus_reward': [100, 500],
                'filter_action': 'warn',
                'vip_benefits': {
                    1: {'max_chats': 50, 'max_unions': 30, 'daily_say': 50},
                    2: {'max_chats': 120, 'max_unions': 70, 'daily_say': 120},
                    3: {'max_chats': 250, 'max_unions': 150, 'daily_say': 300}
                }
            }
            with open('config.json', 'w', encoding='utf-8') as f:
                json.dump(default_config, f, ensure_ascii=False, indent=4)
            return default_config
    
    def convert_currency(self, amount, from_currency, to_currency):
        """Конвертация валют"""
        # Сначала конвертируем всё в рубли
        rub_amount = 0
        
        if from_currency == 'rub':
            rub_amount = amount
        elif from_currency == 'usd':
            rub_amount = amount * self.exchange_rates['usd_to_rub']
        elif from_currency == 'eur':
            rub_amount = amount * self.exchange_rates['eur_to_rub']
        elif from_currency == 'btc':
            rub_amount = amount * self.exchange_rates['btc_to_rub']
        
        # Конвертируем из рублей в нужную валюту
        if to_currency == 'rub':
            return rub_amount
        elif to_currency == 'usd':
            return rub_amount / self.exchange_rates['usd_to_rub']
        elif to_currency == 'eur':
            return rub_amount / self.exchange_rates['eur_to_rub']
        elif to_currency == 'btc':
            return rub_amount / self.exchange_rates['btc_to_rub']
        
        return amount
    
    def get_exchange_rates_info(self):
        """Получение информации о курсах валют"""
        info = "💱 **Текущие курсы валют:**\n"
        info += "━━━━━━━━━━━━━━━━━━━━━━\n"
        info += f"🇺🇸 1 USD = {self.exchange_rates['usd_to_rub']:.2f} RUB\n"
        info += f"🇪🇺 1 EUR = {self.exchange_rates['eur_to_rub']:.2f} RUB\n"
        info += f"₿ 1 BTC = {self.exchange_rates['btc_to_usd']:.0f} USD\n"
        info += f"₿ 1 BTC = {self.exchange_rates['btc_to_rub']:.0f} RUB\n\n"
        info += "🔧 Для изменения курса: /setrate [валюта] [курс]\n"
        info += "Доступные валюты: usd, eur, btc_usd, btc_rub"
        return info
    
    def set_exchange_rate(self, admin_id, currency, rate):
        """Установка курса валюты"""
        if not self.is_agent(admin_id):
            return False, "❌ Вы не являетесь агентом!"
        
        # Все агенты могут менять курс (как и просили)
        if currency == 'usd':
            self.exchange_rates['usd_to_rub'] = float(rate)
            self.exchange_rates['btc_to_rub'] = self.exchange_rates['btc_to_usd'] * float(rate)
        elif currency == 'eur':
            self.exchange_rates['eur_to_rub'] = float(rate)
        elif currency == 'btc_usd':
            self.exchange_rates['btc_to_usd'] = float(rate)
            self.exchange_rates['btc_to_rub'] = float(rate) * self.exchange_rates['usd_to_rub']
        elif currency == 'btc_rub':
            self.exchange_rates['btc_to_rub'] = float(rate)
            self.exchange_rates['btc_to_usd'] = float(rate) / self.exchange_rates['usd_to_rub']
        else:
            return False, "❌ Неверная валюта! Доступны: usd, eur, btc_usd, btc_rub"
        
        self.save_exchange_rates()
        self.log_action(admin_id, 'set_rate', 0, f"{currency} = {rate}")
        return True, f"✅ Курс {currency} установлен: {rate}"
    
    def create_inline_keyboard(self, buttons, inline=True):
        """Создание инлайн клавиатуры"""
        keyboard = {
            "inline": inline,
            "buttons": []
        }
        
        row = []
        for button in buttons:
            row.append({
                "action": {
                    "type": "text",
                    "label": button['text']
                },
                "color": button.get('color', 'primary')
            })
            
            if len(row) == 2 or button == buttons[-1]:
                keyboard['buttons'].append(row)
                row = []
        
        return json.dumps(keyboard, ensure_ascii=False)
    
    def create_start_keyboard(self):
        """Создание клавиатуры для /start"""
        return self.create_inline_keyboard([
            {'text': '🚀 Активировать бота', 'color': 'primary'}
        ])
    
    def create_staff_keyboard(self):
        """Создание клавиатуры для /staff"""
        return self.create_inline_keyboard([
            {'text': '👥 Показать с никами', 'color': 'primary'}
        ])
    
    def create_shop_keyboard(self):
        """Создание клавиатуры для магазина"""
        return self.create_inline_keyboard([
            {'text': '📱 Телефоны', 'color': 'primary'},
            {'text': '🏠 Дома', 'color': 'primary'},
            {'text': '👕 Одежда', 'color': 'primary'},
            {'text': '🎁 Вещи', 'color': 'primary'},
            {'text': '💎 VIP Статусы', 'color': 'positive'},
            {'text': '⛏️ Майнер BTC', 'color': 'primary'}
        ])
    
    def create_phones_keyboard(self):
        """Создание клавиатуры для телефонов"""
        buttons = []
        for phone, price in self.inline_shop['phones'].items():
            buttons.append({'text': f"📱 {phone} - {price}$", 'color': 'primary'})
        return self.create_inline_keyboard(buttons)
    
    def create_houses_keyboard(self):
        """Создание клавиатуры для домов"""
        buttons = []
        for house, price in self.inline_shop['houses'].items():
            buttons.append({'text': f"{house} - {price}$", 'color': 'primary'})
        return self.create_inline_keyboard(buttons)
    
    def create_clothes_keyboard(self):
        """Создание клавиатуры для одежды"""
        buttons = []
        for clothes, price in self.inline_shop['clothes'].items():
            buttons.append({'text': f"{clothes} - {price}$", 'color': 'primary'})
        return self.create_inline_keyboard(buttons)
    
    def create_items_keyboard(self):
        """Создание клавиатуры для вещей"""
        buttons = []
        for item, price in self.inline_shop['items'].items():
            buttons.append({'text': f"{item} - {price}$", 'color': 'primary'})
        return self.create_inline_keyboard(buttons)
    
    def create_vip_keyboard(self):
        """Создание клавиатуры для VIP"""
        return self.create_inline_keyboard([
            {'text': '🌟 VIP I - 5000₽', 'color': 'positive'},
            {'text': '💎 VIP II - 15000₽', 'color': 'positive'},
            {'text': '👑 VIP III - 35000₽', 'color': 'positive'}
        ])
    
    def create_slave_keyboard(self):
        """Создание клавиатуры для системы рабов"""
        return self.create_inline_keyboard([
            {'text': '💰 Собрать прибыль', 'color': 'positive'},
            {'text': '🔗 Надеть цепи', 'color': 'primary'},
            {'text': '⬆️ Прокачать рабов', 'color': 'primary'},
            {'text': '🆓 Выкупиться', 'color': 'negative'}
        ], inline=False)
    
    def create_agent_keyboard(self, target_id, current_permissions=None):
        """Создание клавиатуры для управления доступами агента"""
        if current_permissions is None:
            self.cursor.execute('SELECT permissions FROM agent_permissions WHERE user_id = ?', (target_id,))
            result = self.cursor.fetchone()
            if result:
                current_permissions = json.loads(result[0])
            else:
                current_permissions = {}
        
        buttons = []
        perms = [
            ('reports', 'Доступ к /reports'),
            ('agent', 'Доступ к /agent'),
            ('givemoney', 'Выдача денег'),
            ('givevip', 'Выдача VIP'),
            ('sysban', 'Системный бан'),
            ('sysrole', 'Системная роль'),
            ('sysinfo', 'Системная информация'),
            ('botadmins', 'Список агентов'),
            ('snick', 'Установка ника'),
            ('rnick', 'Удаление ника'),
            ('delkick', 'Кик забаненных'),
            ('mutereports', 'Мут репортов'),
            ('unmutereports', 'Размут репортов')
        ]
        
        for perm, name in perms:
            status = "✅" if current_permissions.get(perm, False) else "❌"
            buttons.append({'text': f"{status} {name}", 'color': 'primary'})
        
        return self.create_inline_keyboard(buttons)
    
    def create_sysban_keyboard(self):
        """Создание клавиатуры для системного бана"""
        return self.create_inline_keyboard([
            {'text': '1️⃣ Стадия 1 - Полный ЧС', 'color': 'negative'},
            {'text': '2️⃣ Стадия 2 - Запрет команд', 'color': 'negative'},
            {'text': '3️⃣ Стадия 3 - Слив денег', 'color': 'negative'},
            {'text': '4️⃣ Стадия 4 - Анулировать аккаунт', 'color': 'negative'},
            {'text': 'ℹ️ Информация о стадиях', 'color': 'primary'}
        ])
    
    def create_sysinfo_keyboard(self, target_id):
        """Создание клавиатуры для sysinfo"""
        self.sysinfo_target[target_id] = True
        return self.create_inline_keyboard([
            {'text': '1️⃣ Информация о пользователе', 'color': 'primary'},
            {'text': '2️⃣ В каких чатах пользователь', 'color': 'primary'},
            {'text': '3️⃣ В каких чатах владелец', 'color': 'primary'},
            {'text': 'ℹ️ Что означают цифры', 'color': 'secondary'}
        ])
    
    def activate_chat(self, chat_id, user_id):
        """Активация беседы"""
        try:
            self.cursor.execute('SELECT is_active FROM chats WHERE chat_id = ?', (chat_id,))
            result = self.cursor.fetchone()
            
            if result and result[0] == 1:
                self.send_message("❌ Беседа уже активирована!", chat_id)
                return False, "❌ Беседа уже активирована!"
            
            current_time = datetime.now().isoformat()
            
            # Проверяем существование беседы
            self.cursor.execute('SELECT * FROM chats WHERE chat_id = ?', (chat_id,))
            chat = self.cursor.fetchone()
            
            if chat:
                self.cursor.execute('''
                    UPDATE chats 
                    SET is_active = 1, activated_at = ?, owner_id = ?
                    WHERE chat_id = ?
                ''', (current_time, user_id, chat_id))
            else:
                self.cursor.execute('''
                    INSERT INTO chats (chat_id, chat_name, owner_id, is_active, activated_at, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (chat_id, f"Chat_{chat_id}", user_id, 1, current_time, current_time))
            
            self.conn.commit()
            
            welcome_msg = (
                "✅ **Беседа активирована!**\n"
                f"👑 Владелец беседы: [id{user_id}|]\n"
                "🎉 Удачного использования бота!\n\n"
                "📋 **Список команд:** /help\n"
                "❓ **Вопросы по боту:** /report"
            )
            
            self.send_message(welcome_msg, chat_id)
            return True, "✅ Беседа успешно активирована!"
            
        except Exception as e:
            print(f"❌ Ошибка активации: {e}")
            error_msg = f"❌ Ошибка активации: {str(e)[:100]}"
            self.send_message(error_msg, chat_id)
            return False, error_msg
    
    def send_message(self, message, chat_id=None, user_id=None, keyboard=None):
        """Отправка сообщения"""
        try:
            params = {
                'random_id': random.randint(1, 1000000),
                'message': message
            }
            
            if user_id:
                params['user_id'] = user_id
            elif chat_id:
                params['chat_id'] = chat_id
            
            if keyboard:
                params['keyboard'] = keyboard
            
            self.vk_api.messages.send(**params)
            return True
        except Exception as e:
            print(f"❌ Ошибка отправки сообщения: {e}")
            return False
    
    def get_or_create_chat(self, chat_id):
        """Получение или создание беседы в БД"""
        self.cursor.execute('SELECT * FROM chats WHERE chat_id = ?', (chat_id,))
        chat = self.cursor.fetchone()
        
        if not chat:
            try:
                current_time = datetime.now().isoformat()
                self.cursor.execute('''
                    INSERT INTO chats (chat_id, chat_name, owner_id, is_active, created_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (chat_id, f"Chat_{chat_id}", 0, 0, current_time))
                self.conn.commit()
            except Exception as e:
                print(f"⚠️ Ошибка создания беседы в БД: {e}")
            
            return self.get_or_create_chat(chat_id)
        
        return chat
    
    def get_user(self, user_id):
        """Получение информации о пользователе"""
        self.cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = self.cursor.fetchone()
        
        if not user:
            try:
                user_info = self.vk_api.users.get(user_ids=user_id)[0]
                name = f"{user_info['first_name']} {user_info['last_name']}"
            except:
                name = f"User_{user_id}"
            
            current_time = datetime.now().isoformat()
            self.cursor.execute('''
                INSERT INTO users (user_id, name, join_date, messages_count, say_used_today, last_say_reset)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, name, current_time, 0, 0, current_time))
            self.conn.commit()
            return self.get_user(user_id)
        
        return user
    
    def get_vip_benefits(self, vip_level):
        """Получение преимуществ VIP статуса"""
        benefits = self.config['vip_benefits'].get(vip_level, {'max_chats': 0, 'max_unions': 0, 'daily_say': 0})
        next_level = vip_level + 1
        next_benefits = self.config['vip_benefits'].get(next_level, None)
        return benefits, next_benefits
    
    def get_role_display_name(self, role_name):
        """Получение отображаемого имени роли"""
        self.cursor.execute('SELECT role_name FROM roles WHERE role_name = ?', (role_name,))
        role = self.cursor.fetchone()
        
        if role:
            return role[0]
        
        default_names = {
            'user': 'Пользователь',
            'moderator': 'Модератор',
            'admin': 'Администратор',
            'owner': 'Владелец'
        }
        
        return default_names.get(role_name, role_name)
    
    def get_user_stats_detailed(self, user_id, chat_id=None):
        """Детальная статистика пользователя"""
        user = self.get_user(user_id)
        
        inviter_info = ""
        if chat_id:
            self.cursor.execute('''
                SELECT inviter_id FROM invites 
                WHERE chat_id = ? AND user_id = ?
                ORDER BY invited_at DESC LIMIT 1
            ''', (chat_id, user_id))
            inviter = self.cursor.fetchone()
            
            if inviter and inviter[0]:
                inviter_info = f"👫 Пригласил(а): @id{inviter[0]}"
        
        # Если пользователь агент, показываем специальную статистику
        if user[20] == 1:  # is_agent
            agent_number = user[21] or 0
            tickets_processed = user[22] or 0
            avg_rating = user[23] or 0
            
            stats = (
                f"👑 **Агент поддержки №{agent_number}**\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🔧 Рассмотрено тикетов: {tickets_processed}\n"
                f"🅰️ Средняя оценка ответов: {avg_rating:.1f}/5 ⭐\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
            )
        else:
            stats = f"🔍 Информация о пользователе:\n━━━━━━━━━━━━━━━━━━━━━━\n"
        
        # Базовая роль
        base_role = user[2]
        if base_role.startswith('vip'):
            base_role = 'user'
        
        status_emoji = self.status_emojis.get(base_role, '👤')
        status_text = {
            'user': 'Пользователь',
            'moderator': 'Модератор',
            'admin': 'Администратор',
            'owner': 'Владелец'
        }.get(base_role, 'Пользователь')
        
        stats += f"{status_emoji} Статус: {status_text}\n"
        stats += f"⚠ Предупреждений: {user[10]}/{self.config['warning_limit']}\n"
        
        # Никнейм
        nickname = user[24] or user[1]
        stats += f"📄 Никнейм: {nickname}\n"
        
        # Мут
        if user[11] == 1 and user[12]:
            try:
                mute_until = datetime.fromisoformat(user[12])
                if mute_until > datetime.now():
                    stats += f"🚧 Блокировка чата: до {mute_until.strftime('%d.%m.%Y %H:%M')}\n"
                else:
                    stats += f"🚧 Блокировка чата: нет\n"
            except:
                stats += f"🚧 Блокировка чата: нет\n"
        else:
            stats += f"🚧 Блокировка чата: нет\n"
        
        # Дата появления
        if user[16]:
            try:
                join_date = datetime.fromisoformat(user[16])
                stats += f"📅 Дата появления: {join_date.strftime('%d.%m.%Y %H:%M')}\n\n"
            except:
                stats += f"📅 Дата появления: Неизвестно\n\n"
        else:
            stats += f"📅 Дата появления: Неизвестно\n\n"
        
        stats += f"📋 Глобальная информация:\n"
        
        # VIP статус
        if user[3] > 0:
            vip_names = {
                1: '🌟 VIP I уровня',
                2: '💎 VIP II уровня',
                3: '👑 VIP III уровня'
            }
            vip_display_name = vip_names.get(user[3], f'VIP {user[3]} уровня')
            stats += f"💎 VIP статус: {vip_display_name}\n"
            if user[4]:
                try:
                    vip_until = datetime.fromisoformat(user[4])
                    stats += f"💎 Действует до: {vip_until.strftime('%d.%m.%Y %H:%M')}\n"
                except:
                    pass
        
        stats += f"✍ Сообщений отправлено: {user[17]}\n"
        
        if inviter_info:
            stats += f"{inviter_info}\n"
        
        stats += f"⚙ ID: {user_id}\n"
        
        return stats
    
    def get_vip_info(self, user_id):
        """Получение информации о VIP статусе"""
        user = self.get_user(user_id)
        
        if user[3] == 0:
            return "❌ У вас нет VIP статуса! Используйте /shop для покупки."
        
        benefits, next_benefits = self.get_vip_benefits(user[3])
        
        self.cursor.execute('SELECT COUNT(*) FROM unions WHERE owner_id = ?', (user_id,))
        unions_count = self.cursor.fetchone()[0]
        
        if user[19]:
            try:
                last_reset = datetime.fromisoformat(user[19])
                if datetime.now().date() > last_reset.date():
                    self.cursor.execute('UPDATE users SET say_used_today = 0, last_say_reset = ? WHERE user_id = ?', 
                                      (datetime.now().isoformat(), user_id))
                    self.conn.commit()
                    say_used = 0
                else:
                    say_used = user[18] if user[18] else 0
            except:
                say_used = 0
        else:
            say_used = 0
        
        vip_until = None
        if user[4]:
            try:
                vip_until = datetime.fromisoformat(user[4])
            except:
                pass
        
        vip_names = {
            1: '🌟 VIP I уровня',
            2: '💎 VIP II уровня',
            3: '👑 VIP III уровня'
        }
        vip_display_name = vip_names.get(user[3], f'VIP {user[3]} уровня')
        
        info = f"✨ **{vip_display_name}**\n"
        info += f"💎 Уровень: {user[3]}\n\n"
        info += f"📊 **Ваши возможности:**\n"
        info += f"━━━━━━━━━━━━━━━━━━\n"
        info += f"🏢 Можно создать объединений: {benefits['max_unions'] - unions_count}/{benefits['max_unions']}\n"
        info += f"💬 В каждое объединение можно добавить: {benefits['max_chats']} бесед\n"
        info += f"📢 Команд !скажи на сегодня: {say_used}/{benefits['daily_say']}\n\n"
        
        if next_benefits:
            info += f"🔮 **Следующий уровень VIP {user[3] + 1}:**\n"
            info += f"💬 {next_benefits['max_chats']} бесед, "
            info += f"🏢 {next_benefits['max_unions']} объединений, "
            info += f"📢 {next_benefits['daily_say']} команд !скажи\n\n"
        
        if vip_until:
            info += f"⏰ Статус действует до: {vip_until.strftime('%d.%m.%Y %H:%M')}"
        
        return info
    
    def get_staff_list(self):
        """Получение списка персонала"""
        staff_roles = ['moderator', 'admin', 'owner']
        staff_list = []
        
        for role in staff_roles:
            self.cursor.execute('SELECT user_id, name FROM users WHERE role = ?', (role,))
            users = self.cursor.fetchall()
            
            for user_id, name in users:
                staff_list.append({
                    'id': user_id,
                    'name': name,
                    'role': role
                })
        
        return staff_list
    
    def get_roles_list(self):
        """Получение списка всех ролей"""
        self.cursor.execute('''
            SELECT role_name, priority FROM roles 
            ORDER BY priority DESC
        ''')
        return self.cursor.fetchall()
    
    def add_custom_role(self, admin_id, role_name, priority):
        """Добавление пользовательской роли"""
        if not self.check_permission(admin_id, 'addrole'):
            return False, "❌ У вас нет прав для создания ролей!"
        
        try:
            self.cursor.execute('''
                INSERT INTO roles (role_name, permissions, priority)
                VALUES (?, ?, ?)
            ''', (role_name, json.dumps({}), priority))
            self.conn.commit()
            
            self.status_emojis[role_name] = '👤'
            
            return True, f"✅ Роль '{role_name}' создана! Приоритет: {priority}"
        except sqlite3.IntegrityError:
            return False, f"❌ Роль '{role_name}' уже существует!"
    
    def set_user_role(self, admin_id, user_id, role, chat_id):
        """Выдача роли пользователю"""
        if not self.check_permission(admin_id, 'setrole'):
            return False, "❌ У вас нет прав для выдачи ролей!"
        
        self.cursor.execute('SELECT * FROM roles WHERE role_name = ?', (role,))
        if not self.cursor.fetchone():
            return False, f"❌ Роли '{role}' не существует! Доступные роли: /roleslist"
        
        self.cursor.execute('UPDATE users SET role = ? WHERE user_id = ?', (role, user_id))
        self.conn.commit()
        
        return True, f"✅ Пользователю [id{user_id}|] выдана роль {role}"
    
    def check_permission(self, user_id, command):
        """Проверка прав на выполнение команды"""
        user = self.get_user(user_id)
        role = user[2]
        
        self.cursor.execute('SELECT required_role, priority FROM command_permissions WHERE command = ?', (command,))
        cmd_config = self.cursor.fetchone()
        
        if cmd_config:
            required_role = cmd_config[0]
            required_priority = cmd_config[1]
        else:
            mod_commands = ['ban', 'mute', 'warn', 'kick', 'setrole', 'filter', 'addrole']
            if command in mod_commands:
                required_role = 'moderator'
                required_priority = 40
            else:
                required_role = 'user'
                required_priority = 0
        
        self.cursor.execute('SELECT priority FROM roles WHERE role_name = ?', (role,))
        user_priority = self.cursor.fetchone()
        
        if not user_priority:
            return False
        
        return user_priority[0] >= required_priority
    
    def add_balance(self, user_id, currency, amount):
        """Добавление валюты"""
        user = self.get_user(user_id)
        
        currency_map = {
            'rub': (7, 'rubles'),
            'usd': (8, 'dollars'),
            'eur': (9, 'euros'),
            'btc': (6, 'bitcoin')
        }
        
        if currency in currency_map:
            idx, name = currency_map[currency]
            new_amount = (user[idx] or 0) + amount
            self.cursor.execute(f'UPDATE users SET {name} = ? WHERE user_id = ?', (new_amount, user_id))
            self.conn.commit()
            return True
        return False
    
    def daily_bonus(self, user_id):
        """Ежедневный бонус"""
        user = self.get_user(user_id)
        
        if user[15]:
            try:
                last_bonus = datetime.fromisoformat(user[15])
                if datetime.now() - last_bonus < timedelta(days=1):
                    return False, "🎁 Бонус можно получить раз в 24 часа!"
            except:
                pass
        
        bonus = random.randint(*self.config['bonus_reward'])
        self.add_balance(user_id, 'rub', bonus)
        
        self.cursor.execute('UPDATE users SET last_bonus = ? WHERE user_id = ?', (datetime.now().isoformat(), user_id))
        self.conn.commit()
        
        return True, f"🎉 Вы получили бонус: {bonus} ₽"
    
    def mine_bitcoin(self, user_id):
        """Майнинг биткойнов"""
        user = self.get_user(user_id)
        
        if user[14]:
            try:
                last_mine = datetime.fromisoformat(user[14])
                if datetime.now() - last_mine < timedelta(hours=1):
                    return False, "⛏️ Майнинг доступен раз в час!"
            except:
                pass
        
        self.cursor.execute('SELECT * FROM inventory WHERE user_id = ? AND item = "miner"', (user_id,))
        has_miner = self.cursor.fetchone()
        
        if has_miner:
            reward = random.uniform(0.5, 2.0)
        else:
            reward = random.uniform(*self.config['mine_reward'])
        
        self.add_balance(user_id, 'btc', reward)
        
        self.cursor.execute('UPDATE users SET mine_cooldown = ? WHERE user_id = ?', (datetime.now().isoformat(), user_id))
        self.conn.commit()
        
        return True, f"⛏️ Вы намайнили {reward:.8f} BTC"
    
    def work(self, user_id):
        """Работа"""
        user = self.get_user(user_id)
        
        if user[13]:
            try:
                last_work = datetime.fromisoformat(user[13])
                if datetime.now() - last_work < timedelta(minutes=30):
                    return False, "💼 Работа доступна раз в 30 минут!"
            except:
                pass
        
        reward = random.randint(*self.config['work_reward'])
        self.add_balance(user_id, 'rub', reward)
        
        self.cursor.execute('UPDATE users SET work_cooldown = ? WHERE user_id = ?', (datetime.now().isoformat(), user_id))
        self.conn.commit()
        
        return True, f"💼 Вы заработали {reward} ₽"
    
    def buy_vip(self, user_id, level=1):
        """Покупка VIP статуса"""
        user = self.get_user(user_id)
        vip_key = f'vip{level}'
        
        if vip_key not in self.shop_items:
            return False, "❌ Такого VIP статуса не существует!"
        
        price = self.shop_items[vip_key]['price']
        
        if user[7] >= price:
            self.cursor.execute('UPDATE users SET rubles = rubles - ? WHERE user_id = ?', (price, user_id))
            
            vip_until = (datetime.now() + timedelta(days=30)).isoformat()
            role = f'vip{level}'
            
            self.cursor.execute('''
                UPDATE users 
                SET vip_level = ?, vip_until = ?, role = ?
                WHERE user_id = ?
            ''', (level, vip_until, role, user_id))
            
            self.conn.commit()
            
            return True, f"✅ Поздравляем! Вы приобрели {self.shop_items[vip_key]['name']} на 30 дней!"
        
        return False, f"❌ Недостаточно средств! Нужно {price} ₽"
    
    def buy_item(self, user_id, item_name, price=None):
        """Покупка предмета из магазина"""
        user = self.get_user(user_id)
        
        # Проверяем цену из inline_shop если не указана
        if price is None:
            for category in self.inline_shop.values():
                if item_name in category:
                    price = category[item_name]
                    break
        
        if price is None:
            return False, "❌ Товар не найден!"
        
        if user[8] >= price:  # dollars
            self.cursor.execute('UPDATE users SET dollars = dollars - ? WHERE user_id = ?', (price, user_id))
            self.cursor.execute('''
                INSERT INTO inventory (user_id, item, quantity, purchased_at)
                VALUES (?, ?, 1, ?)
            ''', (user_id, item_name, datetime.now().isoformat()))
            self.conn.commit()
            return True, f"✅ Вы купили {item_name} за {price}$!"
        
        return False, f"❌ Недостаточно средств! Нужно {price}$"
    
    def transfer_money(self, user_id, target_id, currency, amount):
        """Перевод денег"""
        user = self.get_user(user_id)
        target = self.get_user(target_id)
        
        currency_map = {
            'rub': (7, 'rubles'),
            'usd': (8, 'dollars'),
            'eur': (9, 'euros'),
            'btc': (6, 'bitcoin')
        }
        
        if currency not in currency_map:
            return False, "❌ Неверная валюта! Доступны: rub, usd, eur, btc"
        
        idx, name = currency_map[currency]
        
        if user[idx] < amount:
            return False, f"❌ Недостаточно средств!"
        
        self.cursor.execute(f'UPDATE users SET {name} = {name} - ? WHERE user_id = ?', (amount, user_id))
        self.cursor.execute(f'UPDATE users SET {name} = {name} + ? WHERE user_id = ?', (amount, target_id))
        self.conn.commit()
        
        self.log_action(user_id, 'transfer', target_id, f"{amount} {currency.upper()}")
        return True, f"✅ Переведено {amount} {currency.upper()} пользователю [id{target_id}|]"
    
    # ==================== АГЕНТСКАЯ СИСТЕМА ====================
    
    def is_agent(self, user_id):
        """Проверка, является ли пользователь агентом"""
        self.cursor.execute('SELECT is_agent FROM users WHERE user_id = ?', (user_id,))
        result = self.cursor.fetchone()
        return result and result[0] == 1
    
    def get_agent_number(self, user_id):
        """Получение номера агента"""
        self.cursor.execute('SELECT agent_number FROM users WHERE user_id = ?', (user_id,))
        result = self.cursor.fetchone()
        return result[0] if result else 0
    
    def has_agent_permission(self, user_id, permission):
        """Проверка прав агента"""
        if not self.is_agent(user_id):
            return False
        
        # Для всех агентов даем доступ ко всем командам, кроме /agent (управление агентами)
        # Управление агентами только у супер-админов
        if permission == 'agent':
            return self.is_super_admin(user_id)
        
        # Остальные команды доступны всем агентам
        # Но проверяем, есть ли у агента это право в БД (если нет - даем по умолчанию)
        self.cursor.execute('SELECT permissions FROM agent_permissions WHERE user_id = ?', (user_id,))
        result = self.cursor.fetchone()
        
        if result:
            perms = json.loads(result[0])
            # Если право не указано в БД, даем доступ по умолчанию (True)
            return perms.get(permission, True)
        
        # Если нет записи о правах, даем доступ по умолчанию
        return True
    
    def add_agent(self, admin_id, user_id):
        """Добавление агента - ТОЛЬКО ДЛЯ СУПЕР-АДМИНОВ"""
        if not self.is_super_admin(admin_id):
            return False, "❌ У вас нет прав для добавления агентов! Только супер-админы могут это делать."
        
        if self.is_agent(user_id):
            return False, "❌ Пользователь уже является агентом!"
        
        # Получаем следующий номер агента
        self.cursor.execute('SELECT MAX(agent_number) FROM users WHERE is_agent = 1')
        result = self.cursor.fetchone()
        next_number = (result[0] or 0) + 1
        
        self.cursor.execute('''
            UPDATE users 
            SET is_agent = 1, agent_number = ?, tickets_processed = 0, avg_rating = 0, reports_muted = 0
            WHERE user_id = ?
        ''', (next_number, user_id))
        
        # Добавляем права по умолчанию (все доступны)
        self.cursor.execute('''
            INSERT OR IGNORE INTO agent_permissions (user_id, permissions)
            VALUES (?, ?)
        ''', (user_id, json.dumps({
            'reports': True,
            'givemoney': True,
            'givevip': True,
            'sysban': True,
            'sysrole': True,
            'sysinfo': True,
            'botadmins': True,
            'snick': True,
            'rnick': True,
            'delkick': True,
            'mutereports': True,
            'unmutereports': True
        })))
        
        self.conn.commit()
        
        self.log_action(admin_id, 'add_agent', user_id, f"Добавлен агент #{next_number}")
        return True, f"✅ Агент #{next_number} добавлен!"
    
    def del_agent(self, admin_id, user_id):
        """Удаление агента - ТОЛЬКО ДЛЯ СУПЕР-АДМИНОВ"""
        if not self.is_super_admin(admin_id):
            return False, "❌ У вас нет прав для удаления агентов! Только супер-админы могут это делать."
        
        if not self.is_agent(user_id):
            return False, "❌ Пользователь не является агентом!"
        
        self.cursor.execute('''
            UPDATE users 
            SET is_agent = 0, agent_number = 0
            WHERE user_id = ?
        ''', (user_id,))
        
        self.cursor.execute('DELETE FROM agent_permissions WHERE user_id = ?', (user_id,))
        self.conn.commit()
        
        self.log_action(admin_id, 'del_agent', user_id, "Удален агент")
        return True, f"✅ Агент удален!"
    
    def update_agent_permissions(self, admin_id, target_id, permission, value):
        """Обновление прав агента - ТОЛЬКО ДЛЯ СУПЕР-АДМИНОВ"""
        if not self.is_super_admin(admin_id):
            return False, "❌ У вас нет прав для изменения прав агентов! Только супер-админы могут это делать."
        
        if not self.is_agent(target_id):
            return False, "❌ Пользователь не является агентом!"
        
        self.cursor.execute('SELECT permissions FROM agent_permissions WHERE user_id = ?', (target_id,))
        result = self.cursor.fetchone()
        
        if result:
            perms = json.loads(result[0])
        else:
            perms = {}
        
        perms[permission] = value
        
        self.cursor.execute('''
            INSERT OR REPLACE INTO agent_permissions (user_id, permissions)
            VALUES (?, ?)
        ''', (target_id, json.dumps(perms)))
        
        self.conn.commit()
        
        status = "включен" if value else "отключен"
        return True, f"✅ Доступ к {permission} {status} для агента #{self.get_agent_number(target_id)}!"
    
    def get_agent_info(self, admin_id, target_id):
        """Получение информации о доступах агента - ТОЛЬКО ДЛЯ СУПЕР-АДМИНОВ"""
        if not self.is_super_admin(admin_id):
            return "❌ У вас нет прав для просмотра информации об агентах!"
        
        if not self.is_agent(target_id):
            return f"❌ Пользователь [id{target_id}|] не является агентом!"
        
        self.cursor.execute('SELECT permissions FROM agent_permissions WHERE user_id = ?', (target_id,))
        result = self.cursor.fetchone()
        
        perms = json.loads(result[0]) if result else {}
        
        agent_number = self.get_agent_number(target_id)
        
        info = f"🔐 **Доступы агента #{agent_number}**\n"
        info += f"━━━━━━━━━━━━━━━━━━━━━━\n"
        info += f"👤 [id{target_id}|]\n\n"
        
        perm_names = {
            'reports': 'Доступ к /reports',
            'agent': 'Управление агентами',
            'givemoney': 'Выдача денег',
            'givevip': 'Выдача VIP',
            'sysban': 'Системный бан',
            'sysrole': 'Системная роль',
            'sysinfo': 'Системная информация',
            'botadmins': 'Список агентов',
            'snick': 'Установка ника',
            'rnick': 'Удаление ника',
            'delkick': 'Кик забаненных',
            'mutereports': 'Мут репортов',
            'unmutereports': 'Размут репортов'
        }
        
        for perm_key, perm_name in perm_names.items():
            status = "✅" if perms.get(perm_key, True) else "❌"
            info += f"{status} {perm_name}\n"
        
        return info
    
    def get_all_agents(self):
        """Получение списка всех агентов"""
        self.cursor.execute('''
            SELECT user_id, name, agent_number, tickets_processed, avg_rating 
            FROM users 
            WHERE is_agent = 1
            ORDER BY agent_number ASC
        ''')
        return self.cursor.fetchall()
    
    def get_bot_admins(self, admin_id):
        """Получение списка агентов - доступно всем агентам"""
        if not self.is_agent(admin_id):
            return "❌ Вы не являетесь агентом!"
        
        agents = self.get_all_agents()
        
        if not agents:
            return "📋 Список агентов пуст."
        
        info = "👑 **Список агентов поддержки**\n"
        info += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for agent_id, name, agent_number, tickets, rating in agents:
            # Получаем права агента
            self.cursor.execute('SELECT permissions FROM agent_permissions WHERE user_id = ?', (agent_id,))
            result = self.cursor.fetchone()
            perms = json.loads(result[0]) if result else {}
            
            # Определяем ранг агента
            if tickets >= 100:
                rank = "🏆 Элитный"
            elif tickets >= 50:
                rank = "⭐ Опытный"
            elif tickets >= 20:
                rank = "📈 Развивающийся"
            else:
                rank = "🆕 Новичок"
            
            info += f"**#{agent_number}** {rank}\n"
            info += f"👤 [id{agent_id}|{name}]\n"
            info += f"📊 Тикетов: {tickets} | Рейтинг: {rating:.1f}⭐\n"
            
            # Показываем основные права
            has_reports = "📝" if perms.get('reports', True) else "🔇"
            has_sysban = "🔨" if perms.get('sysban', True) else "⚙️"
            has_givemoney = "💰" if perms.get('givemoney', True) else "💵"
            
            info += f"Права: {has_reports} {has_sysban} {has_givemoney}\n"
            info += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        return info
    
    # ==================== СИСТЕМА РЕПОРТОВ ====================
    
    def add_report(self, user_id, reporter_id, message, chat_id=None):
        """Добавление репорта"""
        user = self.get_user(user_id)
        
        # Проверка на мут репортов
        if user[24] == 1:  # reports_muted
            return False, "❌ Вы не можете отправлять репорты!"
        
        current_time = datetime.now().isoformat()
        self.cursor.execute('''
            INSERT INTO reports (user_id, reporter_id, message, chat_id, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, reporter_id, message, chat_id or 0, current_time))
        self.conn.commit()
        
        report_id = self.cursor.lastrowid
        
        # Уведомляем агентов с доступом reports
        self.notify_agents(report_id, user_id, message)
        
        return True, f"✅ Репорт #{report_id} отправлен!"
    
    def notify_agents(self, report_id, user_id, message):
        """Уведомление агентов о новом репорте"""
        # Уведомляем всех агентов (у них есть доступ по умолчанию)
        self.cursor.execute('''
            SELECT user_id FROM users WHERE is_agent = 1 AND reports_muted = 0
        ''')
        agents = self.cursor.fetchall()
        
        report_text = f"📝 **Новый репорт #{report_id}**\n"
        report_text += f"👤 От пользователя: [id{user_id}|]\n"
        report_text += f"💬 Сообщение: {message[:200]}\n"
        report_text += f"🔧 Для ответа используйте /reports в ЛС бота"
        
        for agent in agents:
            self.send_message(report_text, user_id=agent[0])
    
    def get_open_reports(self):
        """Получение открытых репортов"""
        self.cursor.execute('''
            SELECT * FROM reports 
            WHERE status = 'open'
            ORDER BY created_at DESC
        ''')
        return self.cursor.fetchall()
    
    def get_report_info(self, report_id):
        """Получение информации о репорте"""
        self.cursor.execute('SELECT * FROM reports WHERE id = ?', (report_id,))
        report = self.cursor.fetchone()
        
        if not report:
            return "❌ Репорт не найден!"
        
        report_id, user_id, reporter_id, message, chat_id, status, created_at, closed_at, closed_by, rating = report
        
        info = f"📋 **Репорт #{report_id}**\n"
        info += f"━━━━━━━━━━━━━━━━━━━━━━\n"
        info += f"👤 Пользователь: [id{user_id}|]\n"
        info += f"📝 Репорт от: [id{reporter_id}|]\n"
        info += f"💬 Сообщение: {message}\n"
        info += f"📅 Создан: {created_at}\n"
        info += f"🔘 Статус: {'✅ Открыт' if status == 'open' else '❌ Закрыт'}\n"
        
        if status == 'closed':
            info += f"🔒 Закрыт: {closed_at}\n"
            info += f"👨‍💼 Кем: [id{closed_by}|]\n"
            info += f"⭐ Оценка: {rating}/5\n"
        
        if chat_id and chat_id != 0:
            info += f"💬 Беседа: {chat_id}\n"
        
        return info
    
    def close_report(self, agent_id, report_id, rating=5):
        """Закрытие репорта"""
        if not self.is_agent(agent_id):
            return False, "❌ Вы не являетесь агентом поддержки!"
        
        self.cursor.execute('SELECT * FROM reports WHERE id = ? AND status = "open"', (report_id,))
        report = self.cursor.fetchone()
        
        if not report:
            return False, "❌ Репорт не найден или уже закрыт!"
        
        current_time = datetime.now().isoformat()
        
        self.cursor.execute('''
            UPDATE reports 
            SET status = 'closed', closed_at = ?, closed_by = ?, rating = ?
            WHERE id = ?
        ''', (current_time, agent_id, rating, report_id))
        
        # Обновляем статистику агента
        self.cursor.execute('''
            UPDATE users 
            SET tickets_processed = tickets_processed + 1,
                avg_rating = (avg_rating * tickets_processed + ?) / (tickets_processed + 1)
            WHERE user_id = ?
        ''', (rating, agent_id))
        
        self.conn.commit()
        
        self.log_action(agent_id, 'close_report', report[1], f"Репорт #{report_id}, оценка {rating}")
        
        # Уведомляем пользователя
        self.send_message(f"✅ Ваш репорт #{report_id} закрыт! Оценка: {rating}/5 ⭐", user_id=report[1])
        
        return True, f"✅ Репорт #{report_id} закрыт!"
    
    def get_agent_stats(self, agent_id):
        """Получение статистики агента"""
        if not self.is_agent(agent_id):
            return "❌ Вы не являетесь агентом!"
        
        user = self.get_user(agent_id)
        agent_number = user[21] or 0
        tickets = user[22] or 0
        rating = user[23] or 0
        
        self.cursor.execute('SELECT permissions FROM agent_permissions WHERE user_id = ?', (agent_id,))
        result = self.cursor.fetchone()
        perms = json.loads(result[0]) if result else {}
        
        # Статистика по репортам
        self.cursor.execute('SELECT COUNT(*) FROM reports WHERE closed_by = ?', (agent_id,))
        closed_by_me = self.cursor.fetchone()[0]
        
        self.cursor.execute('SELECT AVG(rating) FROM reports WHERE closed_by = ? AND rating > 0', (agent_id,))
        my_avg_rating = self.cursor.fetchone()[0] or 0
        
        self.cursor.execute('SELECT COUNT(*) FROM reports WHERE status = "open"')
        open_reports = self.cursor.fetchone()[0]
        
        stats = f"👑 **Статистика агента #{agent_number}**\n"
        stats += f"━━━━━━━━━━━━━━━━━━━━━━\n"
        stats += f"📊 Всего обработано: {tickets}\n"
        stats += f"⭐ Средний рейтинг: {rating:.1f}/5\n"
        stats += f"🔧 Закрыто мной: {closed_by_me}\n"
        stats += f"🎯 Мой средний рейтинг: {my_avg_rating:.1f}/5\n"
        stats += f"📋 Открытых репортов: {open_reports}\n\n"
        
        stats += f"🔐 **Мои права:**\n"
        
        perm_names = {
            'reports': 'Доступ к репортам',
            'agent': 'Управление агентами',
            'givemoney': 'Выдача денег',
            'givevip': 'Выдача VIP',
            'sysban': 'Системный бан',
            'sysrole': 'Системная роль',
            'sysinfo': 'Системная информация',
            'botadmins': 'Список агентов'
        }
        
        for perm_key, perm_name in perm_names.items():
            status = "✅" if perms.get(perm_key, True) else "❌"
            stats += f"{status} {perm_name}\n"
        
        return stats
    
    def handle_reports_in_dm(self, user_id, text):
        """Обработка репортов в личных сообщениях"""
        if not self.is_agent(user_id):
            self.send_message("❌ У вас нет доступа к этой команде!", user_id=user_id)
            return
        
        parts = text.lower().split()
        
        if len(parts) >= 2:
            if parts[1] == 'list':
                reports = self.get_open_reports()
                if reports:
                    msg = "📋 **Открытые репорты:**\n━━━━━━━━━━━━━━━━━━\n"
                    for report in reports[:10]:
                        report_id, user_id_reporter, reporter_id, rep_message, chat_id, status, created_at, closed_at, closed_by, rating = report
                        msg += f"**#{report_id}** | от [id{user_id_reporter}|]\n"
                        msg += f"💬 {rep_message[:50]}...\n"
                        msg += f"📅 {created_at[:16]}\n"
                        msg += f"➡️ /reports close {report_id} [оценка]\n━━━━━━━━━━━━━━━━━━\n"
                    
                    if len(reports) > 10:
                        msg += f"\n... и еще {len(reports) - 10} репортов"
                    
                    self.send_message(msg, user_id=user_id)
                else:
                    self.send_message("✅ Нет открытых репортов!", user_id=user_id)
                return
            
            elif parts[1] == 'close':
                if len(parts) >= 3:
                    try:
                        report_id = int(parts[2])
                        rating = int(parts[3]) if len(parts) > 3 else 5
                        if rating < 1 or rating > 5:
                            rating = 5
                        success, msg = self.close_report(user_id, report_id, rating)
                        self.send_message(msg, user_id=user_id)
                    except ValueError:
                        self.send_message("❌ Использование: /reports close [id] [оценка 1-5]", user_id=user_id)
                else:
                    self.send_message("❌ Использование: /reports close [id] [оценка 1-5]", user_id=user_id)
                return
            
            elif parts[1] == 'info':
                if len(parts) >= 3:
                    try:
                        report_id = int(parts[2])
                        info = self.get_report_info(report_id)
                        self.send_message(info, user_id=user_id)
                    except ValueError:
                        self.send_message("❌ Использование: /reports info [id]", user_id=user_id)
                else:
                    self.send_message("❌ Использование: /reports info [id]", user_id=user_id)
                return
            
            elif parts[1] == 'stats':
                stats = self.get_agent_stats(user_id)
                self.send_message(stats, user_id=user_id)
                return
        
        help_text = (
            "📋 **Система репортов**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Доступные команды:\n\n"
            "• /reports list - Список открытых репортов\n"
            "• /reports close [id] [оценка] - Закрыть репорт\n"
            "• /reports info [id] - Информация о репорте\n"
            "• /reports stats - Моя статистика\n\n"
            "Оценка: 1-5 ⭐ (по умолчанию 5)"
        )
        self.send_message(help_text, user_id=user_id)
    
    # ==================== СИСТЕМНЫЕ КОМАНДЫ ====================
    
    def log_action(self, user_id, action, target_id=None, reason=None):
        """Логирование действий"""
        current_time = datetime.now().isoformat()
        self.cursor.execute('''
            INSERT INTO logs (chat_id, user_id, action, target_id, reason, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (0, user_id, action, target_id, reason, current_time))
        self.conn.commit()
        
        # Сохраняем подозрительные действия
        suspicious_actions = ['sysban', 'sysunban', 'sysrole', 'givemoney', 'givevip', 'add_agent', 'del_agent', 'set_rate']
        if action in suspicious_actions:
            log_entry = {
                'time': current_time,
                'user': user_id,
                'action': action,
                'target': target_id,
                'reason': reason
            }
            self.suspicious_logs.append(log_entry)
            self.save_suspicious_logs()
    
    def save_suspicious_logs(self):
        """Сохранение подозрительных логов в файл"""
        try:
            with open('suspicious_logs.json', 'w', encoding='utf-8') as f:
                json.dump(self.suspicious_logs[-100:], f, ensure_ascii=False, indent=4)
        except:
            pass
    
    def get_logs(self, limit=100):
        """Получение последних логов"""
        self.cursor.execute('''
            SELECT * FROM logs 
            ORDER BY id DESC 
            LIMIT ?
        ''', (limit,))
        return self.cursor.fetchall()
    
    def sysban_user(self, admin_id, user_id, level, reason=None):
        """Системный бан пользователя"""
        if not self.is_agent(admin_id):
            return False, "❌ Вы не являетесь агентом!"
        
        level = int(level)
        if level not in [1, 2, 3, 4]:
            return False, "❌ Неверная стадия бана! Доступны: 1, 2, 3, 4"
        
        current_time = datetime.now().isoformat()
        
        # Выполняем действия в зависимости от стадии
        if level == 4:
            # Анулировать аккаунт
            self.cursor.execute('''
                UPDATE users 
                SET role = 'user', vip_level = 0, 
                    bitcoin = 0, rubles = 0, dollars = 0, euros = 0,
                    is_agent = 0, agent_number = 0, nickname = '',
                    sysban_level = ?
                WHERE user_id = ?
            ''', (level, user_id))
            self.cursor.execute('DELETE FROM agent_permissions WHERE user_id = ?', (user_id,))
        elif level == 3:
            # Слив денег
            self.cursor.execute('''
                UPDATE users 
                SET bitcoin = 0, rubles = 0, dollars = 0, euros = 0,
                    sysban_level = ?
                WHERE user_id = ?
            ''', (level, user_id))
        else:
            self.cursor.execute('''
                UPDATE users 
                SET sysban_level = ?, sysban_by = ?, sysban_reason = ?, sysban_date = ?
                WHERE user_id = ?
            ''', (level, admin_id, reason or "Не указана", current_time, user_id))
        
        self.conn.commit()
        
        self.log_action(admin_id, 'sysban', user_id, f"Стадия {level}: {reason}")
        
        level_names = {
            1: "1️⃣ Полный ЧС бота - нет доступа к боту, кикает из бесед",
            2: "2️⃣ Запрет доступа к командам - не кикает, но не дает пользоваться командами",
            3: "3️⃣ Слив денег - обнуление баланса + полный ЧС",
            4: "4️⃣ Анулировать аккаунт - снятие агента, денег, сброс данных"
        }
        
        return True, f"✅ Пользователь [id{user_id}|] забанен!\n{level_names[level]}\nПричина: {reason or 'Не указана'}"
    
    def sysunban_user(self, admin_id, user_id):
        """Системный разбан пользователя"""
        if not self.is_agent(admin_id):
            return False, "❌ Вы не являетесь агентом!"
        
        self.cursor.execute('''
            UPDATE users 
            SET sysban_level = 0, sysban_by = 0, sysban_reason = '', sysban_date = ''
            WHERE user_id = ?
        ''', (user_id,))
        
        self.conn.commit()
        
        self.log_action(admin_id, 'sysunban', user_id, "Разбан")
        return True, f"✅ Пользователь [id{user_id}|] разбанен!"
    
    def sysrole_user(self, admin_id, user_id, role, chat_id):
        """Системная выдача роли в беседе"""
        if not self.is_agent(admin_id):
            return False, "❌ Вы не являетесь агентом!"
        
        self.cursor.execute('SELECT * FROM roles WHERE role_name = ?', (role,))
        if not self.cursor.fetchone():
            return False, f"❌ Роли '{role}' не существует!"
        
        try:
            # Выдаем роль в беседе через VK API
            self.vk_api.messages.editChat(
                chat_id=chat_id,
                member_id=user_id,
                role=role
            )
            
            self.log_action(admin_id, 'sysrole', user_id, f"Роль {role} в беседе {chat_id}")
            return True, f"✅ Пользователю [id{user_id}|] выдана роль {role} в беседе!"
        except Exception as e:
            return False, f"❌ Ошибка выдачи роли: {str(e)}"
    
    def sysinfo_user(self, admin_id, user_id):
        """Получение системной информации о пользователе"""
        if not self.is_agent(admin_id):
            return "❌ Вы не являетесь агентом!"
        
        user = self.get_user(user_id)
        
        in_blacklist = user[25] > 0  # sysban_level
        
        info = f"📋 **Системная информация о [id{user_id}|]**\n"
        info += f"━━━━━━━━━━━━━━━━━━━━━━\n"
        info += f"🔒 В ЧС бота: {'✅ Да' if in_blacklist else '❌ Нет'}\n"
        
        if in_blacklist:
            level_names = {
                1: "Полный ЧС бота",
                2: "Запрет доступа к командам",
                3: "Слив денег",
                4: "Анулирование аккаунта"
            }
            info += f"├─ Стадия: {level_names.get(user[25], user[25])}\n"
            info += f"├─ Кто занёс: [id{user[26]}|]\n"
            info += f"└─ Причина: {user[27] or 'Не указана'}\n"
        
        # Чаты, где пользователь
        self.cursor.execute('SELECT chat_id FROM chats WHERE owner_id = ?', (user_id,))
        owner_chats = self.cursor.fetchall()
        
        self.cursor.execute('''
            SELECT DISTINCT chat_id FROM invites WHERE user_id = ?
        ''', (user_id,))
        user_chats = self.cursor.fetchall()
        
        info += f"\n🏢 В каких чатах пользователь: {len(user_chats)}\n"
        for chat in user_chats[:5]:
            info += f"├─ Беседа {chat[0]}\n"
        
        if len(user_chats) > 5:
            info += f"└─ и еще {len(user_chats) - 5} чатов...\n"
        
        info += f"\n👑 В каких чатах владелец: {len(owner_chats)}\n"
        for chat in owner_chats[:5]:
            info += f"├─ Беседа {chat[0]}\n"
        
        if len(owner_chats) > 5:
            info += f"└─ и еще {len(owner_chats) - 5} чатов...\n"
        
        return info
    
    def get_sysinfo_help(self):
        """Информация о цифрах в sysinfo"""
        return (
            "ℹ️ **Что означают цифры в sysinfo:**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "1️⃣ - Информация о пользователе\n"
            "   • Статус в ЧС бота\n"
            "   • Кто занёс и причина\n"
            "   • Базовая информация\n\n"
            "2️⃣ - В каких чатах пользователь\n"
            "   • Список бесед, где находится пользователь\n"
            "   • По данным приглашений\n\n"
            "3️⃣ - В каких чатах владелец\n"
            "   • Список бесед, где пользователь является владельцем\n\n"
            "4️⃣ - Эта справка"
        )
    
    def get_user_chats(self, admin_id, user_id):
        """Получение списка чатов пользователя"""
        if not self.is_agent(admin_id):
            return "❌ Вы не являетесь агентом!"
        
        self.cursor.execute('''
            SELECT DISTINCT chat_id FROM invites WHERE user_id = ?
        ''', (user_id,))
        chats = self.cursor.fetchall()
        
        if not chats:
            return f"📋 Пользователь [id{user_id}|] не состоит ни в одной беседе бота."
        
        info = f"📋 **Чаты, где состоит [id{user_id}|]:**\n"
        info += f"━━━━━━━━━━━━━━━━━━━━━━\n"
        for chat in chats:
            info += f"├─ Беседа {chat[0]}\n"
        
        return info
    
    def get_owner_chats(self, admin_id, user_id):
        """Получение списка чатов, где пользователь владелец"""
        if not self.is_agent(admin_id):
            return "❌ Вы не являетесь агентом!"
        
        self.cursor.execute('SELECT chat_id FROM chats WHERE owner_id = ?', (user_id,))
        chats = self.cursor.fetchall()
        
        if not chats:
            return f"📋 Пользователь [id{user_id}|] не является владельцем ни одной беседы."
        
        info = f"👑 **Чаты, где [id{user_id}|] владелец:**\n"
        info += f"━━━━━━━━━━━━━━━━━━━━━━\n"
        for chat in chats:
            info += f"├─ Беседа {chat[0]}\n"
        
        return info
    
    def set_nickname(self, admin_id, user_id, nickname):
        """Установка ника пользователю"""
        if not self.is_agent(admin_id):
            return False, "❌ Вы не являетесь агентом!"
        
        self.cursor.execute('UPDATE users SET nickname = ? WHERE user_id = ?', (nickname, user_id))
        self.conn.commit()
        
        self.log_action(admin_id, 'set_nickname', user_id, nickname)
        return True, f"✅ Пользователю [id{user_id}|] установлен ник: {nickname}"
    
    def remove_nickname(self, admin_id, user_id):
        """Удаление ника пользователя"""
        if not self.is_agent(admin_id):
            return False, "❌ Вы не являетесь агентом!"
        
        self.cursor.execute('UPDATE users SET nickname = "" WHERE user_id = ?', (user_id,))
        self.conn.commit()
        
        self.log_action(admin_id, 'remove_nickname', user_id, "Удален ник")
        return True, f"✅ Ник пользователя [id{user_id}|] удален!"
    
    def kick_banned_accounts(self, admin_id):
        """Кик заблокированных аккаунтов"""
        if not self.is_agent(admin_id):
            return False, "❌ Вы не являетесь агентом!"
        
        self.cursor.execute('SELECT user_id FROM users WHERE sysban_level = 1 OR sysban_level = 3')
        banned_users = self.cursor.fetchall()
        
        kicked_count = 0
        for user in banned_users:
            try:
                self.cursor.execute('SELECT chat_id FROM chats WHERE is_active = 1')
                chats = self.cursor.fetchall()
                
                for chat in chats:
                    try:
                        self.vk_api.messages.removeChatUser(
                            chat_id=chat[0],
                            user_id=user[0]
                        )
                        kicked_count += 1
                    except:
                        pass
            except:
                pass
        
        self.log_action(admin_id, 'kick_banned', 0, f"Кикнуто {kicked_count} аккаунтов")
        return True, f"✅ Кикнуто заблокированных аккаунтов: {kicked_count}"
    
    def get_users_without_nicknames(self):
        """Получение списка пользователей без ников"""
        self.cursor.execute('''
            SELECT user_id, name FROM users 
            WHERE (nickname = '' OR nickname IS NULL) AND is_agent = 0
        ''')
        return self.cursor.fetchall()
    
    def get_users_by_nickname_part(self, part):
        """Получение пользователей по части ника"""
        self.cursor.execute('''
            SELECT user_id, name, nickname FROM users 
            WHERE nickname LIKE ? AND nickname != '' AND is_agent = 0
        ''', (f'%{part}%',))
        return self.cursor.fetchall()
    
    def mute_reports(self, admin_id, user_id):
        """Мут репортов для пользователя"""
        if not self.is_agent(admin_id):
            return False, "❌ Вы не являетесь агентом!"
        
        self.cursor.execute('UPDATE users SET reports_muted = 1 WHERE user_id = ?', (user_id,))
        self.conn.commit()
        
        self.log_action(admin_id, 'mute_reports', user_id, "Мут репортов")
        return True, f"✅ Пользователь [id{user_id}|] замучен на репорты!"
    
    def unmute_reports(self, admin_id, user_id):
        """Размут репортов для пользователя"""
        if not self.is_agent(admin_id):
            return False, "❌ Вы не являетесь агентом!"
        
        self.cursor.execute('UPDATE users SET reports_muted = 0 WHERE user_id = ?', (user_id,))
        self.conn.commit()
        
        self.log_action(admin_id, 'unmute_reports', user_id, "Размут репортов")
        return True, f"✅ Пользователь [id{user_id}|] размучен на репорты!"
    
    def give_money(self, admin_id, user_id, currency, amount):
        """Выдача денег"""
        if not self.is_agent(admin_id):
            return False, "❌ Вы не являетесь агентом!"
        
        currency_map = {
            'rub': 'rubles',
            'usd': 'dollars',
            'eur': 'euros',
            'btc': 'bitcoin'
        }
        
        if currency not in currency_map:
            return False, "❌ Неверная валюта! Доступны: rub, usd, eur, btc"
        
        self.cursor.execute(f'UPDATE users SET {currency_map[currency]} = {currency_map[currency]} + ? WHERE user_id = ?', 
                           (amount, user_id))
        self.conn.commit()
        
        self.log_action(admin_id, 'give_money', user_id, f"{amount} {currency.upper()}")
        return True, f"✅ Пользователю [id{user_id}|] выдано {amount} {currency.upper()}"
    
    def give_vip(self, admin_id, user_id, level):
        """Выдача VIP"""
        if not self.is_agent(admin_id):
            return False, "❌ Вы не являетесь агентом!"
        
        if level not in [1, 2, 3]:
            return False, "❌ Неверный уровень VIP! Доступны: 1, 2, 3"
        
        vip_until = (datetime.now() + timedelta(days=30)).isoformat()
        
        self.cursor.execute('''
            UPDATE users 
            SET vip_level = ?, vip_until = ?, role = ?
            WHERE user_id = ?
        ''', (level, vip_until, f'vip{level}', user_id))
        
        self.conn.commit()
        
        self.log_action(admin_id, 'give_vip', user_id, f"VIP {level}")
        return True, f"✅ Пользователю [id{user_id}|] выдан VIP {level} уровня на 30 дней!"
    
    # ==================== СИСТЕМА РАБОВ ====================
    
    def handle_slave_system(self, user_id, action):
        """Обработка системы рабов"""
        if action == "collect":
            self.cursor.execute('''
                SELECT slave_id, level, last_collect FROM slaves 
                WHERE owner_id = ?
            ''', (user_id,))
            slaves = self.cursor.fetchall()
            
            if not slaves:
                return "❌ У вас нет рабов!"
            
            total_income = 0
            current_time = datetime.now()
            
            for slave_id, level, last_collect in slaves:
                if last_collect:
                    try:
                        last = datetime.fromisoformat(last_collect)
                        hours_passed = (current_time - last).total_seconds() / 3600
                        if hours_passed > 24:
                            hours_passed = 24
                    except:
                        hours_passed = 0
                else:
                    hours_passed = 0
                
                income = level * 10 * hours_passed
                total_income += income
                
                self.cursor.execute('''
                    UPDATE slaves SET last_collect = ? 
                    WHERE owner_id = ? AND slave_id = ?
                ''', (current_time.isoformat(), user_id, slave_id))
            
            if total_income > 0:
                self.add_balance(user_id, 'rub', total_income)
                self.conn.commit()
                return f"💰 Собрано прибыли: {total_income:.2f} ₽"
            else:
                return "⏰ Нет прибыли для сбора! Подождите немного."
        
        elif action == "buyout":
            self.cursor.execute('SELECT owner_id, level FROM slaves WHERE slave_id = ?', (user_id,))
            owner = self.cursor.fetchone()
            
            if not owner:
                return "❌ Вы не являетесь рабом!"
            
            owner_id, level = owner
            buyout_price = 5000 * level
            
            user = self.get_user(user_id)
            if user[7] >= buyout_price:
                self.add_balance(user_id, 'rub', -buyout_price)
                self.add_balance(owner_id, 'rub', buyout_price)
                
                self.cursor.execute('DELETE FROM slaves WHERE slave_id = ?', (user_id,))
                self.conn.commit()
                
                return f"✅ Вы выкупились за {buyout_price:.0f} ₽!"
            else:
                return f"❌ Недостаточно средств! Нужно {buyout_price:.0f} ₽"
        
        elif action == "chains":
            self.cursor.execute('''
                UPDATE slaves SET chains = chains + 1 
                WHERE owner_id = ? AND chains < 5
            ''', (user_id,))
            self.conn.commit()
            
            if self.cursor.rowcount > 0:
                return "🔗 Цепи надеты! Раб будет приносить на 20% больше прибыли."
            else:
                return "❌ Нет рабов или достигнут максимум цепей (5)!"
        
        elif action == "upgrade":
            self.cursor.execute('''
                SELECT slave_id, level, exp FROM slaves WHERE owner_id = ?
            ''', (user_id,))
            slaves = self.cursor.fetchall()
            
            if not slaves:
                return "❌ У вас нет рабов!"
            
            upgrade_cost = 1000 * len(slaves)
            user = self.get_user(user_id)
            
            if user[7] >= upgrade_cost:
                self.add_balance(user_id, 'rub', -upgrade_cost)
                
                for slave_id, level, exp in slaves:
                    new_exp = exp + 100
                    if new_exp >= level * 100:
                        new_level = level + 1
                        self.cursor.execute('''
                            UPDATE slaves 
                            SET level = ?, exp = 0 
                            WHERE owner_id = ? AND slave_id = ?
                        ''', (new_level, user_id, slave_id))
                    else:
                        self.cursor.execute('''
                            UPDATE slaves 
                            SET exp = ? 
                            WHERE owner_id = ? AND slave_id = ?
                        ''', (new_exp, user_id, slave_id))
                
                self.conn.commit()
                return f"⬆️ Рабы прокачаны! Стоимость: {upgrade_cost:.0f} ₽"
            else:
                return f"❌ Недостаточно средств! Нужно {upgrade_cost:.0f} ₽"
        
        return "❌ Неизвестное действие!"
    
    # ==================== ОСНОВНОЙ ОБРАБОТЧИК ====================
    
    def handle_message(self, event):
        """Обработка сообщений"""
        if event.type == VkBotEventType.MESSAGE_NEW:
            message = event.object.message
            
            chat_id = None
            if message.get('peer_id', 0) > 2000000000:
                chat_id = message['peer_id'] - 2000000000
                print(f"📨 Сообщение в беседе {chat_id}: {message.get('text', '')[:50]}")
            else:
                # Личные сообщения боту
                user_id = message['from_id']
                text = message.get('text', '')
                
                # Обработка репортов в ЛС
                if text.lower() in self.commands['reports']:
                    self.handle_reports_in_dm(user_id, text)
                return
            
            if chat_id:
                self.get_or_create_chat(chat_id)
            
            if 'text' in message:
                text = message['text'].lower()
                user_id = message['from_id']
                
                # Проверка системного бана
                user = self.get_user(user_id)
                if user[25] in [1, 2, 3]:
                    if user[25] == 1 or user[25] == 3:
                        if text not in self.commands['report']:
                            self.send_message("❌ Вы находитесь в ЧС бота. Обратитесь в поддержку.", chat_id)
                            return
                    elif user[25] == 2:
                        if text not in self.commands['report'] and not any(text in cmd_list for cmd_list in self.commands.values()):
                            self.send_message("❌ Вам запрещен доступ к командам.", chat_id)
                            return
                
                # Команда /start
                if text in self.commands['start']:
                    success, msg = self.activate_chat(chat_id, message['from_id'])
                    return
                
                # Проверка активации беседы
                self.cursor.execute('SELECT is_active FROM chats WHERE chat_id = ?', (chat_id,))
                result = self.cursor.fetchone()
                
                if not result or result[0] == 0:
                    if text not in self.commands['start']:
                        error_msg = "❌ Беседа не активирована! Введите /start для активации."
                        self.send_message(error_msg, chat_id)
                    return
                
                # ========== КОМАНДЫ ДЛЯ АГЕНТОВ (доступны всем агентам) ==========
                
                # Команда /rates - просмотр курсов валют
                if text in self.commands['rates']:
                    info = self.get_exchange_rates_info()
                    self.send_message(info, chat_id)
                    return
                
                # Команда /setrate - установка курса валют
                if text in self.commands['setrate'] and self.is_agent(user_id):
                    parts = text.split()
                    if len(parts) >= 3:
                        currency = parts[1]
                        try:
                            rate = float(parts[2])
                            success, msg = self.set_exchange_rate(user_id, currency, rate)
                            self.send_message(msg, chat_id)
                        except ValueError:
                            self.send_message("❌ Курс должен быть числом!", chat_id)
                    else:
                        self.send_message("❌ Использование: /setrate [валюта] [курс]\nДоступные валюты: usd, eur, btc_usd, btc_rub", chat_id)
                    return
                
                # Команда /agent - управление агентами (только для супер-админов)
                if text in self.commands['agent'] and self.is_super_admin(user_id):
                    parts = text.split()
                    if len(parts) >= 3:
                        if parts[1] == 'add':
                            try:
                                target_id = int(parts[2])
                                success, msg = self.add_agent(user_id, target_id)
                                self.send_message(msg, chat_id)
                            except ValueError:
                                self.send_message("❌ Неверный ID!", chat_id)
                        elif parts[1] == 'del':
                            try:
                                target_id = int(parts[2])
                                success, msg = self.del_agent(user_id, target_id)
                                self.send_message(msg, chat_id)
                            except ValueError:
                                self.send_message("❌ Неверный ID!", chat_id)
                        elif parts[1] == 'info':
                            try:
                                target_id = int(parts[2])
                                info = self.get_agent_info(user_id, target_id)
                                self.send_message(info, chat_id)
                            except ValueError:
                                self.send_message("❌ Неверный ID!", chat_id)
                        else:
                            self.send_message("❌ Неизвестная подкоманда! Доступны: add, del, info", chat_id)
                    else:
                        self.send_message("🔧 **Управление агентами**\n\nИспользование:\n/agent add [id] - добавить агента\n/agent del [id] - удалить агента\n/agent info [id] - информация об агенте", chat_id)
                    return
                
                # Команда /agent для обычных агентов (без прав управления)
                elif text in self.commands['agent'] and self.is_agent(user_id) and not self.is_super_admin(user_id):
                    self.send_message("🔒 У вас нет прав для управления агентами. Только супер-админы могут добавлять/удалять агентов.", chat_id)
                    return
                
                # Команда /botadmins - список агентов
                if text in self.commands['botadmins'] and self.is_agent(user_id):
                    info = self.get_bot_admins(user_id)
                    self.send_message(info, chat_id)
                    return
                
                # Системные команды для агентов (доступны всем агентам)
                if text in self.commands['givemoney'] and self.is_agent(user_id):
                    parts = text.split()
                    if len(parts) >= 4:
                        try:
                            target_id = int(parts[1])
                            currency = parts[2]
                            amount = float(parts[3])
                            success, msg = self.give_money(user_id, target_id, currency, amount)
                            self.send_message(msg, chat_id)
                        except ValueError:
                            self.send_message("❌ Использование: /givemoney [id] [валюта] [сумма]", chat_id)
                    else:
                        self.send_message("❌ Использование: /givemoney [id] [валюта] [сумма]", chat_id)
                    return
                
                if text in self.commands['givevip'] and self.is_agent(user_id):
                    parts = text.split()
                    if len(parts) >= 3:
                        try:
                            target_id = int(parts[1])
                            level = int(parts[2])
                            success, msg = self.give_vip(user_id, target_id, level)
                            self.send_message(msg, chat_id)
                        except ValueError:
                            self.send_message("❌ Использование: /givevip [id] [уровень]", chat_id)
                    else:
                        self.send_message("❌ Использование: /givevip [id] [уровень]", chat_id)
                    return
                
                if text in self.commands['sysban'] and self.is_agent(user_id):
                    parts = text.split()
                    if len(parts) >= 3:
                        try:
                            target_id = int(parts[1])
                            level = int(parts[2])
                            reason = ' '.join(parts[3:]) if len(parts) > 3 else None
                            success, msg = self.sysban_user(user_id, target_id, level, reason)
                            self.send_message(msg, chat_id)
                        except ValueError:
                            self.send_message("❌ Использование: /sysban [id] [стадия] [причина]", chat_id)
                    else:
                        keyboard = self.create_sysban_keyboard()
                        self.send_message("Выберите стадию бана:", chat_id, keyboard=keyboard)
                    return
                
                if text in self.commands['sysunban'] and self.is_agent(user_id):
                    parts = text.split()
                    if len(parts) >= 2:
                        try:
                            target_id = int(parts[1])
                            success, msg = self.sysunban_user(user_id, target_id)
                            self.send_message(msg, chat_id)
                        except ValueError:
                            self.send_message("❌ Использование: /sysunban [id]", chat_id)
                    else:
                        self.send_message("❌ Использование: /sysunban [id]", chat_id)
                    return
                
                if text in self.commands['sysrole'] and self.is_agent(user_id):
                    parts = text.split()
                    if len(parts) >= 3:
                        try:
                            target_id = int(parts[1])
                            role = parts[2]
                            success, msg = self.sysrole_user(user_id, target_id, role, chat_id)
                            self.send_message(msg, chat_id)
                        except ValueError:
                            self.send_message("❌ Использование: /sysrole [id] [роль]", chat_id)
                    else:
                        self.send_message("❌ Использование: /sysrole [id] [роль]", chat_id)
                    return
                
                if text in self.commands['sysinfo'] and self.is_agent(user_id):
                    parts = text.split()
                    if len(parts) >= 2:
                        try:
                            target_id = int(parts[1])
                            info = self.sysinfo_user(user_id, target_id)
                            self.send_message(info, chat_id)
                        except ValueError:
                            self.send_message("❌ Использование: /sysinfo [id]", chat_id)
                    else:
                        self.send_message("❌ Использование: /sysinfo [id]", chat_id)
                    return
                
                if text in self.commands['snick'] and self.is_agent(user_id):
                    parts = text.split()
                    if len(parts) >= 3:
                        try:
                            target_id = int(parts[1])
                            nickname = ' '.join(parts[2:])
                            success, msg = self.set_nickname(user_id, target_id, nickname)
                            self.send_message(msg, chat_id)
                        except ValueError:
                            self.send_message("❌ Использование: /snick [id] [ник]", chat_id)
                    else:
                        self.send_message("❌ Использование: /snick [id] [ник]", chat_id)
                    return
                
                if text in self.commands['rnick'] and self.is_agent(user_id):
                    parts = text.split()
                    if len(parts) >= 2:
                        try:
                            target_id = int(parts[1])
                            success, msg = self.remove_nickname(user_id, target_id)
                            self.send_message(msg, chat_id)
                        except ValueError:
                            self.send_message("❌ Использование: /rnick [id]", chat_id)
                    else:
                        self.send_message("❌ Использование: /rnick [id]", chat_id)
                    return
                
                if text in self.commands['delkick'] and self.is_agent(user_id):
                    success, msg = self.kick_banned_accounts(user_id)
                    self.send_message(msg, chat_id)
                    return
                
                if text in self.commands['nonames'] and self.is_agent(user_id):
                    users = self.get_users_without_nicknames()
                    if users:
                        msg = "📋 **Список пользователей без ников:**\n━━━━━━━━━━━━━━━━━━\n"
                        for user_id, name in users[:20]:
                            msg += f"• [id{user_id}|{name}]\n"
                        if len(users) > 20:
                            msg += f"\n... и еще {len(users) - 20} пользователей"
                        self.send_message(msg, chat_id)
                    else:
                        self.send_message("✅ Все пользователи имеют ники!", chat_id)
                    return
                
                if text in self.commands['ponicku'] and self.is_agent(user_id):
                    parts = text.split()
                    if len(parts) >= 2:
                        search = parts[1]
                        users = self.get_users_by_nickname_part(search)
                        if users:
                            msg = f"📋 **Пользователи с частью '{search}' в нике:**\n━━━━━━━━━━━━━━━━━━\n"
                            for user_id, name, nickname in users[:20]:
                                msg += f"• [id{user_id}|{name}] - ник: {nickname}\n"
                            if len(users) > 20:
                                msg += f"\n... и еще {len(users) - 20} пользователей"
                            self.send_message(msg, chat_id)
                        else:
                            self.send_message(f"❌ Пользователи с частью '{search}' в нике не найдены.", chat_id)
                    else:
                        self.send_message("❌ Использование: /ponicku [часть ника]", chat_id)
                    return
                
                if text in self.commands['mutereports'] and self.is_agent(user_id):
                    parts = text.split()
                    if len(parts) >= 2:
                        try:
                            target_id = int(parts[1])
                            success, msg = self.mute_reports(user_id, target_id)
                            self.send_message(msg, chat_id)
                        except ValueError:
                            self.send_message("❌ Использование: /mutereports [id]", chat_id)
                    else:
                        self.send_message("❌ Использование: /mutereports [id]", chat_id)
                    return
                
                if text in self.commands['unmutereports'] and self.is_agent(user_id):
                    parts = text.split()
                    if len(parts) >= 2:
                        try:
                            target_id = int(parts[1])
                            success, msg = self.unmute_reports(user_id, target_id)
                            self.send_message(msg, chat_id)
                        except ValueError:
                            self.send_message("❌ Использование: /unmutereports [id]", chat_id)
                    else:
                        self.send_message("❌ Использование: /unmutereports [id]", chat_id)
                    return
                
                # ========== ОБЫЧНЫЕ КОМАНДЫ (для всех) ==========
                
                if text in self.commands['help']:
                    help_msg = (
                        "📋 **Список команд:**\n"
                        "━━━━━━━━━━━━━━━━━━━━━━\n"
                        "👤 **Пользовательские:**\n"
                        "• /stats - Ваша статистика\n"
                        "• /balance - Ваш баланс\n"
                        "• /work - Работа\n"
                        "• /mine - Майнинг BTC\n"
                        "• /bonus - Ежедневный бонус\n"
                        "• /vip - Информация о VIP\n"
                        "• /shop - Магазин\n"
                        "• /transfer [id] [валюта] [сумма] - Перевод\n"
                        "• /slaves - Система рабов\n\n"
                        "🛡️ **Модерация:**\n"
                        "• /ban [id] - Бан пользователя\n"
                        "• /mute [id] [минуты] - Мут\n"
                        "• /warn [id] - Варн\n"
                        "• /filter add [слово] [действие] - Добавить фильтр\n"
                        "• /filter list - Список фильтров\n\n"
                        "💎 **VIP команды:**\n"
                        "• !скажи [текст] - Сказать от имени бота\n\n"
                        "🔧 **Для администраторов:**\n"
                        "• /setrole [id] [роль] - Выдать роль\n"
                        "• /addrole [название] [приоритет] - Добавить роль\n"
                        "• /roleslist - Список ролей\n"
                        "• /editcmd [команда] [приоритет] [роль] - Настройка прав\n\n"
                        "💱 **Курсы валют:**\n"
                        "• /rates - Текущие курсы\n\n"
                        "📌 **Все команды работают с префиксами: / ! .**"
                    )
                    self.send_message(help_msg, chat_id)
                    return
                
                if text in self.commands['report']:
                    parts = text.split(maxsplit=1)
                    if len(parts) > 1:
                        report_text = parts[1]
                        success, msg = self.add_report(user_id, user_id, report_text, chat_id)
                        self.send_message(msg, chat_id)
                    else:
                        self.send_message("❌ Использование: /report [текст вопроса/проблемы]", chat_id)
                    return
                
                if text in self.commands['transfer']:
                    parts = text.split()
                    if len(parts) >= 4:
                        try:
                            target_id = int(parts[1])
                            currency = parts[2]
                            amount = float(parts[3])
                            success, msg = self.transfer_money(user_id, target_id, currency, amount)
                            self.send_message(msg, chat_id)
                        except ValueError:
                            self.send_message("❌ Использование: /transfer [id] [валюта] [сумма]", chat_id)
                    else:
                        self.send_message("❌ Использование: /transfer [id] [валюта] [сумма]\nДоступные валюты: rub, usd, eur, btc", chat_id)
                    return
                
                if text in self.commands['slaves']:
                    keyboard = self.create_slave_keyboard()
                    self.send_message("🔄 **Система рабов**\n\nВыберите действие:", chat_id, keyboard=keyboard)
                    return
                
                if text in self.commands['ping']:
                    start_time = time.time()
                    self.send_message("🏓 Понг!", chat_id)
                    response_time = (time.time() - start_time) * 1000
                    self.send_message(f"⏱️ Время ответа: {response_time:.2f} мс", chat_id)
                    return
                
                if text in self.commands['stats']:
                    stats = self.get_user_stats_detailed(user_id, chat_id)
                    self.send_message(stats, chat_id)
                    return
                
                if text in self.commands['vip']:
                    vip_info = self.get_vip_info(user_id)
                    keyboard = self.create_inline_keyboard([
                        {'text': '💎 Купить VIP', 'color': 'primary'}
                    ])
                    self.send_message(vip_info, chat_id, keyboard=keyboard)
                    return
                
                if text in self.commands['staff']:
                    staff = self.get_staff_list()
                    if staff:
                        staff_text = "👥 **Персонал сервера:**\n━━━━━━━━━━━━━━━━━━\n"
                        for member in staff:
                            role_emoji = self.status_emojis.get(member['role'], '👤')
                            staff_text += f"{role_emoji} [id{member['id']}|{member['name']}] - {member['role'].upper()}\n"
                        keyboard = self.create_staff_keyboard()
                        self.send_message(staff_text, chat_id, keyboard=keyboard)
                    else:
                        self.send_message("👥 Персонал отсутствует.", chat_id)
                    return
                
                if text in self.commands['roleslist']:
                    roles = self.get_roles_list()
                    if roles:
                        roles_text = "📋 **Список ролей:**\n━━━━━━━━━━━━━━━━━━\n"
                        for role_name, priority in roles:
                            role_display = self.get_role_display_name(role_name)
                            roles_text += f"• {role_display} - приоритет: {priority}\n"
                        self.send_message(roles_text, chat_id)
                    else:
                        self.send_message("📋 Роли не найдены.", chat_id)
                    return
                
                if text in self.commands['addrole']:
                    parts = text.split()
                    if len(parts) >= 3:
                        role_name = parts[1]
                        try:
                            priority = int(parts[2])
                            success, msg = self.add_custom_role(user_id, role_name, priority)
                            self.send_message(msg, chat_id)
                        except ValueError:
                            self.send_message("❌ Приоритет должен быть числом!", chat_id)
                    else:
                        self.send_message("❌ Использование: /addrole [название] [приоритет]", chat_id)
                    return
                
                if text in self.commands['setrole']:
                    parts = text.split()
                    if len(parts) >= 3:
                        try:
                            target_id = int(parts[1])
                            role = parts[2]
                            success, msg = self.set_user_role(user_id, target_id, role, chat_id)
                            self.send_message(msg, chat_id)
                        except ValueError:
                            self.send_message("❌ ID должен быть числом!", chat_id)
                    else:
                        self.send_message("❌ Использование: /setrole [id] [роль]", chat_id)
                    return
                
                if text in self.commands['balance']:
                    user = self.get_user(user_id)
                    balance_msg = f"💰 **Ваш баланс:**\n━━━━━━━━━━━━━━━━━━\n"
                    balance_msg += f"🇷🇺 Рубли: {user[7]:.2f} ₽\n"
                    balance_msg += f"🇺🇸 Доллары: {user[8]:.2f} $\n"
                    balance_msg += f"🇪🇺 Евро: {user[9]:.2f} €\n"
                    balance_msg += f"₿ Биткойны: {user[6]:.8f} BTC"
                    self.send_message(balance_msg, chat_id)
                    return
                
                if text in self.commands['bonus']:
                    success, msg = self.daily_bonus(user_id)
                    self.send_message(msg, chat_id)
                    return
                
                if text in self.commands['mine']:
                    success, msg = self.mine_bitcoin(user_id)
                    self.send_message(msg, chat_id)
                    return
                
                if text in self.commands['work']:
                    success, msg = self.work(user_id)
                    self.send_message(msg, chat_id)
                    return
                
                if text in self.commands['shop']:
                    shop_text = "🛒 **Магазин**\n━━━━━━━━━━━━━━━━━━\n"
                    shop_text += "📱 Телефоны\n🏠 Дома\n👕 Одежда\n🎁 Вещи\n💎 VIP Статусы\n⛏️ Майнер BTC\n\n"
                    shop_text += "💰 Валюта: Доллары ($)\n\n"
                    shop_text += "Выберите категорию:"
                    keyboard = self.create_shop_keyboard()
                    self.send_message(shop_text, chat_id, keyboard=keyboard)
                    return
                
                if text in self.commands['buy']:
                    parts = text.split()
                    if len(parts) >= 2:
                        item = parts[1]
                        if item == 'vip1':
                            success, msg = self.buy_vip(user_id, 1)
                            self.send_message(msg, chat_id)
                        elif item == 'vip2':
                            success, msg = self.buy_vip(user_id, 2)
                            self.send_message(msg, chat_id)
                        elif item == 'vip3':
                            success, msg = self.buy_vip(user_id, 3)
                            self.send_message(msg, chat_id)
                        elif item == 'miner':
                            success, msg = self.buy_item(user_id, 'bitcoin_miner', 500)
                            self.send_message(msg, chat_id)
                        else:
                            self.send_message("❌ Неизвестный товар! Используйте /shop", chat_id)
                    else:
                        self.send_message("❌ Использование: /buy [товар]", chat_id)
                    return
                
                if text in self.commands['chat_info']:
                    chat = self.get_or_create_chat(chat_id)
                    info = f"📊 **Информация о беседе**\n━━━━━━━━━━━━━━━━━━\n"
                    info += f"💬 Название: {chat[1]}\n"
                    info += f"🆔 ID: {chat[0]}\n"
                    info += f"🔘 Статус: {'✅ Активна' if chat[3] == 1 else '❌ Не активирована'}\n"
                    self.send_message(info, chat_id)
                    return
    
    def handle_callback_query(self, event):
        """Обработка нажатий на инлайн кнопки"""
        if event.type == VkBotEventType.MESSAGE_EVENT:
            payload = event.object.payload
            user_id = event.object.user_id
            peer_id = event.object.peer_id
            
            if 'payload' in payload:
                data = payload['payload']
                
                # Обработка изменения прав агента (только для супер-админов)
                if data.startswith('agent_perm_') and self.is_super_admin(user_id):
                    parts = data.split('_')
                    if len(parts) >= 4:
                        target_id = int(parts[2])
                        permission = parts[3]
                        current_value = parts[4] == 'true' if len(parts) > 4 else False
                        
                        new_value = not current_value
                        success, msg = self.update_agent_permissions(user_id, target_id, permission, new_value)
                        
                        # Обновляем клавиатуру
                        keyboard = self.create_agent_keyboard(target_id)
                        self.send_message(msg, user_id=user_id, keyboard=keyboard)
                
                # Обработка выбора стадии бана
                elif data.startswith('sysban_stage_'):
                    stage = int(data.split('_')[2])
                    stage_info = (
                        f"**Стадия {stage}:**\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    )
                    if stage == 1:
                        stage_info += "1️⃣ Полный ЧС бота\n"
                        stage_info += "• Нет доступа к боту\n"
                        stage_info += "• Кикает при добавлении в беседу\n"
                        stage_info += "• Ссылка на ВК с именем в ЧС бота\n\n"
                    elif stage == 2:
                        stage_info += "2️⃣ Запрет доступа к командам\n"
                        stage_info += "• Не кикает из беседы\n"
                        stage_info += "• Не дает пользоваться командами бота\n\n"
                    elif stage == 3:
                        stage_info += "3️⃣ Слив денег\n"
                        stage_info += "• То же, что полный ЧС бота\n"
                        stage_info += "• Обнуление баланса\n\n"
                    elif stage == 4:
                        stage_info += "4️⃣ Анулировать аккаунт\n"
                        stage_info += "• Снятие агента\n"
                        stage_info += "• Снятие всех денег\n"
                        stage_info += "• Сброс всех данных\n\n"
                    
                    stage_info += "Используйте: /sysban [id] [стадия] [причина]"
                    self.send_message(stage_info, user_id=user_id)
                
                # Обработка выбора опции в sysinfo
                elif data.startswith('sysinfo_opt_'):
                    option = int(data.split('_')[2])
                    if user_id in self.sysinfo_target:
                        target_id = self.sysinfo_target[user_id]
                        if option == 1:
                            info = self.sysinfo_user(user_id, target_id)
                        elif option == 2:
                            info = self.get_user_chats(user_id, target_id)
                        elif option == 3:
                            info = self.get_owner_chats(user_id, target_id)
                        elif option == 4:
                            info = self.get_sysinfo_help()
                        self.send_message(info, user_id=user_id)
                
                # Обработка покупок в магазине
                elif data.startswith('shop_'):
                    category = data.split('_')[1]
                    if category == 'phones':
                        keyboard = self.create_phones_keyboard()
                        self.send_message("📱 **Выберите телефон:**", user_id=user_id, keyboard=keyboard)
                    elif category == 'houses':
                        keyboard = self.create_houses_keyboard()
                        self.send_message("🏠 **Выберите дом:**", user_id=user_id, keyboard=keyboard)
                    elif category == 'clothes':
                        keyboard = self.create_clothes_keyboard()
                        self.send_message("👕 **Выберите одежду:**", user_id=user_id, keyboard=keyboard)
                    elif category == 'items':
                        keyboard = self.create_items_keyboard()
                        self.send_message("🎁 **Выберите вещь:**", user_id=user_id, keyboard=keyboard)
                    elif category == 'vip':
                        keyboard = self.create_vip_keyboard()
                        self.send_message("💎 **Выберите VIP статус:**\n\n🌟 VIP I - 5000₽\n💎 VIP II - 15000₽\n👑 VIP III - 35000₽\n\nДействует 30 дней", user_id=user_id, keyboard=keyboard)
                    elif category == 'miner':
                        success, msg = self.buy_item(user_id, 'Майнер биткойнов', 500)
                        self.send_message(msg, user_id=user_id)
                
                # Обработка покупки конкретного товара
                elif data.startswith('buy_'):
                    item = data.split('_', 1)[1]
                    if item in self.inline_shop['phones']:
                        price = self.inline_shop['phones'][item]
                        success, msg = self.buy_item(user_id, item, price)
                        self.send_message(msg, user_id=user_id)
                    elif item in self.inline_shop['houses']:
                        price = self.inline_shop['houses'][item]
                        success, msg = self.buy_item(user_id, item, price)
                        self.send_message(msg, user_id=user_id)
                    elif item in self.inline_shop['clothes']:
                        price = self.inline_shop['clothes'][item]
                        success, msg = self.buy_item(user_id, item, price)
                        self.send_message(msg, user_id=user_id)
                    elif item in self.inline_shop['items']:
                        price = self.inline_shop['items'][item]
                        success, msg = self.buy_item(user_id, item, price)
                        self.send_message(msg, user_id=user_id)
                    elif item.startswith('vip'):
                        level = int(item[3:])
                        success, msg = self.buy_vip(user_id, level)
                        self.send_message(msg, user_id=user_id)
                
                # Обработка действий с рабами
                elif data.startswith('slave_'):
                    action = data.split('_')[1]
                    result = self.handle_slave_system(user_id, action)
                    self.send_message(result, user_id=user_id)
                
                # Обработка показа ников в /staff
                elif data == 'show_nicks':
                    staff = self.get_staff_list()
                    if staff:
                        staff_text = "👥 **Персонал (с никами):**\n━━━━━━━━━━━━━━━━━━\n"
                        for member in staff:
                            user = self.get_user(member['id'])
                            nickname = user[24] or member['name']
                            role_emoji = self.status_emojis.get(member['role'], '👤')
                            staff_text += f"{role_emoji} [id{member['id']}|{nickname}] - {member['role'].upper()}\n"
                        self.send_message(staff_text, user_id=user_id)
                    else:
                        self.send_message("👥 Персонал отсутствует.", user_id=user_id)
    
    def run(self):
        """Запуск бота"""
        print("🤖 Бот начал работу. Ожидание сообщений...")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("💡 Бот готов к работе!")
        print("💬 Добавьте бота в беседу и введите /start")
        
        for event in self.longpoll.listen():
            try:
                if event.type == VkBotEventType.MESSAGE_NEW:
                    self.handle_message(event)
                elif event.type == VkBotEventType.MESSAGE_EVENT:
                    self.handle_callback_query(event)
            except Exception as e:
                print(f"❌ Ошибка обработки события: {e}")
                import traceback
                traceback.print_exc()


if __name__ == "__main__":
    GROUP_TOKEN = "vk1.a.KA15ljp23_4l6s3DomdeTkkE7DHmsflVzVWGMjBm7kzWm0eOATiZI_LTGXlzC2nnRHx3fcgjVivrqwUq5WUQN-7tfecpSfGfjjrhprbxh9B7WdUgpZ9sgKo5bYpLSzKmuahc3Ylf3Zysct7yvMch0FGoECKYe6gSGBerNJKsDIbAlndr9HzLcMojM7ePA5GdkZUCA4ICcV7ttTSHnqZUzQ"
    GROUP_ID = 237250582
       
    bot = VKChatManager(GROUP_TOKEN, GROUP_ID)
    bot.run()