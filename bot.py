import asyncio
import sqlite3
import random
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.utils import get_random_id
import threading
from queue import Queue
import os

class Database:
    """Синхронный слой базы данных с асинхронной оберткой"""
    
    def __init__(self, db_path: str = 'apex_chat_manager.db'):
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self.lock = threading.Lock()
        
    def connect(self):
        """Синхронное подключение к БД"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        
    def close(self):
        """Закрытие соединения"""
        if self.conn:
            self.conn.close()
    
    def execute(self, query: str, params: tuple = ()):
        """Синхронное выполнение запроса"""
        with self.lock:
            self.cursor.execute(query, params)
            self.conn.commit()
            return self.cursor
    
    def fetchone(self, query: str, params: tuple = ()):
        """Синхронное получение одной записи"""
        with self.lock:
            self.cursor.execute(query, params)
            return self.cursor.fetchone()
    
    def fetchall(self, query: str, params: tuple = ()):
        """Синхронное получение всех записей"""
        with self.lock:
            self.cursor.execute(query, params)
            return self.cursor.fetchall()
    
    async def execute_async(self, query: str, params: tuple = ()):
        """Асинхронное выполнение запроса"""
        return await asyncio.to_thread(self.execute, query, params)
    
    async def fetchone_async(self, query: str, params: tuple = ()):
        """Асинхронное получение одной записи"""
        return await asyncio.to_thread(self.fetchone, query, params)
    
    async def fetchall_async(self, query: str, params: tuple = ()):
        """Асинхронное получение всех записей"""
        return await asyncio.to_thread(self.fetchall, query, params)

class ApexChatManager:
    def __init__(self, token: str, group_id: int):
        self.token = token
        self.group_id = group_id
        self.vk_session = vk_api.VkApi(token=token)
        self.vk = self.vk_session.get_api()
        self.longpoll = VkBotLongPoll(self.vk_session, group_id)
        
        # Префиксы команд
        self.prefixes = ['/', '.', '!', '-', '+']
        
        # Уровни доступа к командам (0-100)
        self.command_levels = {
            # Уровень 100 - только владелец бота
            'sysrestart': 100, 'editcmd': 100, 'sysban': 100, 'sysunban': 100,
            'gban': 90, 'gmute': 90, 'grole': 90,
            # Уровень 80 - главные админы
            'agent': 80, 'sysrole': 80,
            # Уровень 70 - админы чата
            'ban': 70, 'unban': 70, 'mute': 70, 'unmute': 70,
            'warn': 70, 'unwarn': 70, 'role': 70, 'rr': 70,
            # Уровень 60 - модераторы
            'newrole': 60,
            # Уровень 50 - агенты поддержки
            'quest': 50, 'ticket': 50,
            # Уровень 0 - все пользователи
            'balance': 0, 'stats': 0, 'prof': 0, 'shop': 0, 'buy': 0,
            'work': 0, 'infoquest': 0, 'report': 0, 'top': 0, 'mtop': 0,
            'exchange': 0, 'mine': 0, 'upgrademine': 0, 'snick': 0, 'rnick': 0,
            'slave': 0, 'slaves': 0, 'workslave': 0, 'sellslave': 0, 'chains': 0,
            'ping': 0, 'botstats': 0, 'help': 0
        }
        
        # Инициализация базы данных
        self.db = Database()
        self.db.connect()
        
        # Запуск фоновых задач
        self.background_tasks = []
        
    def init_db(self):
        """Инициализация базы данных"""
        # Пользователи
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                first_name TEXT,
                last_name TEXT,
                rubles INTEGER DEFAULT 1000,
                dollars INTEGER DEFAULT 0,
                euros INTEGER DEFAULT 0,
                bitcoins REAL DEFAULT 0,
                rating INTEGER DEFAULT 0,
                warns INTEGER DEFAULT 0,
                vip_status TEXT DEFAULT 'Нет',
                vip_until TEXT,
                invited_by INTEGER,
                mining_level INTEGER DEFAULT 1,
                mining_speed REAL DEFAULT 0.1,
                last_mining TEXT,
                level INTEGER DEFAULT 1,
                exp INTEGER DEFAULT 0
            )
        ''')
        
        # Чаты
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS chats (
                id INTEGER PRIMARY KEY,
                name TEXT,
                settings TEXT DEFAULT '{}'
            )
        ''')
        
        # Баны
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS bans (
                user_id INTEGER,
                chat_id INTEGER,
                reason TEXT,
                banned_by INTEGER,
                banned_at TEXT,
                until TEXT,
                PRIMARY KEY (user_id, chat_id)
            )
        ''')
        
        # Муты
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS mutes (
                user_id INTEGER,
                chat_id INTEGER,
                until TEXT,
                muted_by INTEGER,
                PRIMARY KEY (user_id, chat_id)
            )
        ''')
        
        # Роли
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS roles (
                user_id INTEGER,
                chat_id INTEGER,
                role TEXT,
                level INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, chat_id)
            )
        ''')
        
        # Доступные роли
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS available_roles (
                chat_id INTEGER,
                role_name TEXT,
                required_level INTEGER DEFAULT 0,
                PRIMARY KEY (chat_id, role_name)
            )
        ''')
        
        # Агенты
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS agents (
                user_id INTEGER PRIMARY KEY,
                agent_number INTEGER,
                permissions TEXT DEFAULT '{}'
            )
        ''')
        
        # Квесты
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS quests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                description TEXT,
                reward_type TEXT,
                reward_amount INTEGER,
                status TEXT DEFAULT 'pending',
                assigned_to INTEGER,
                assigned_by INTEGER
            )
        ''')
        
        # Тикеты
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                user_id INTEGER,
                type TEXT,
                description TEXT,
                status TEXT DEFAULT 'open',
                agent_id INTEGER,
                created_at TEXT
            )
        ''')
        
        # Магазин
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS shop_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT,
                name TEXT,
                price_type TEXT,
                price INTEGER,
                description TEXT
            )
        ''')
        
        # Статистика сообщений
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS message_stats (
                user_id INTEGER,
                chat_id INTEGER,
                messages INTEGER DEFAULT 0,
                stickers INTEGER DEFAULT 0,
                bad_words INTEGER DEFAULT 0,
                date TEXT,
                PRIMARY KEY (user_id, chat_id, date)
            )
        ''')
        
        # Рабы
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS slaves (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER,
                slave_id INTEGER,
                name TEXT,
                level INTEGER DEFAULT 1,
                exp INTEGER DEFAULT 0,
                work_type TEXT DEFAULT 'miner',
                chains INTEGER DEFAULT 0,
                price INTEGER,
                bought_at TEXT,
                last_work TEXT,
                UNIQUE(owner_id, slave_id)
            )
        ''')
        
        # Системные баны
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS sys_bans (
                user_id INTEGER PRIMARY KEY,
                reason TEXT,
                banned_by INTEGER,
                banned_at TEXT
            )
        ''')
        
        # Никнеймы
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS nicknames (
                user_id INTEGER,
                chat_id INTEGER,
                nickname TEXT,
                PRIMARY KEY (user_id, chat_id)
            )
        ''')
        
        # Команды
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS commands (
                name TEXT PRIMARY KEY,
                level INTEGER DEFAULT 0,
                enabled INTEGER DEFAULT 1
            )
        ''')
        
        # Загрузка уровней команд
        rows = self.db.fetchall('SELECT name, level FROM commands')
        for row in rows:
            self.command_levels[row[0]] = row[1]
    
    async def get_user(self, user_id: int, chat_id: int = None) -> Dict:
        """Получение данных пользователя"""
        user = await self.db.fetchone_async('SELECT * FROM users WHERE id = ?', (user_id,))
        
        if not user:
            await self.db.execute_async('''
                INSERT INTO users (id, last_mining)
                VALUES (?, ?)
            ''', (user_id, datetime.now().isoformat()))
            
            user = await self.db.fetchone_async('SELECT * FROM users WHERE id = ?', (user_id,))
        
        # Получение роли в чате
        role = None
        role_level = 0
        if chat_id:
            role_data = await self.db.fetchone_async(
                'SELECT role, level FROM roles WHERE user_id = ? AND chat_id = ?',
                (user_id, chat_id)
            )
            if role_data:
                role = role_data[0]
                role_level = role_data[1]
        
        # Проверка агента
        agent = await self.db.fetchone_async('SELECT agent_number FROM agents WHERE user_id = ?', (user_id,))
        
        return {
            'id': user[0],
            'first_name': user[1] or "Неизвестно",
            'last_name': user[2] or "",
            'rubles': user[3],
            'dollars': user[4],
            'euros': user[5],
            'bitcoins': user[6],
            'rating': user[7],
            'warns': user[8],
            'vip_status': user[9],
            'vip_until': user[10],
            'invited_by': user[11],
            'mining_level': user[12],
            'mining_speed': user[13],
            'last_mining': user[14],
            'level': user[15],
            'exp': user[16],
            'role': role,
            'role_level': role_level,
            'is_agent': bool(agent),
            'agent_number': agent[0] if agent else None
        }
    
    async def check_permission(self, user_id: int, chat_id: int, command: str) -> bool:
        """Проверка прав доступа к команде"""
        # Проверка системного бана
        sys_ban = await self.db.fetchone_async('SELECT 1 FROM sys_bans WHERE user_id = ?', (user_id,))
        if sys_ban:
            return False
        
        # Проверка бана в чате
        ban = await self.db.fetchone_async(
            'SELECT 1 FROM bans WHERE user_id = ? AND chat_id = ?',
            (user_id, chat_id)
        )
        if ban:
            return False
        
        required_level = self.command_levels.get(command, 0)
        
        # Уровень 0 доступен всем
        if required_level == 0:
            return True
        
        # Получение уровня пользователя
        user_level = await self.get_user_level(user_id, chat_id)
        
        return user_level >= required_level
    
    async def get_user_level(self, user_id: int, chat_id: int) -> int:
        """Получение уровня пользователя в чате"""
        # Проверка на владельца бота
        if user_id in self.get_bot_owners():
            return 100
        
        # Проверка на агента
        agent = await self.db.fetchone_async('SELECT 1 FROM agents WHERE user_id = ?', (user_id,))
        if agent:
            return 50
        
        # Проверка роли
        role = await self.db.fetchone_async(
            'SELECT level FROM roles WHERE user_id = ? AND chat_id = ?',
            (user_id, chat_id)
        )
        if role:
            return role[0]
        
        # Проверка администратора ВК
        if await self.is_vk_admin(user_id, chat_id):
            return 70
        
        return 0
    
    def get_bot_owners(self) -> List[int]:
        """Получение списка владельцев бота"""
        # Здесь нужно добавить ID владельцев
        return [123456789]  # Замените на реальные ID
    
    async def is_vk_admin(self, user_id: int, chat_id: int) -> bool:
        """Проверка администратора ВКонтакте"""
        try:
            members = await asyncio.to_thread(
                self.vk.messages.getConversationMembers,
                peer_id=chat_id
            )
            for member in members['items']:
                if member['member_id'] == user_id:
                    if member.get('is_admin') or member.get('is_owner'):
                        return True
            return False
        except:
            return False
    
    async def send_message(self, peer_id: int, message: str, keyboard=None, attachment=None):
        """Отправка сообщения"""
        await asyncio.to_thread(
            self.vk.messages.send,
            peer_id=peer_id,
            message=message,
            keyboard=keyboard.get_keyboard() if keyboard else None,
            attachment=attachment,
            random_id=get_random_id()
        )
    
    # ==================== КОМАНДЫ ====================
    
    async def cmd_help(self, event, user_id: int, chat_id: int, args: List[str]):
        """Помощь по командам"""
        help_text = """📚 **Apex × Чат-менеджер**

🔗 **Сообщество:** https://vk.com/apexchatmanager

📖 **Полный список команд:** https://vk.com/apexchatmanager

**Основные команды:**
🎮 **Игровые:** /balance, /shop, /buy, /mine, /slave
⚙️ **Модерация:** /ban, /mute, /warn, /role
👥 **Профиль:** /stats, /prof, /top
🎫 **Поддержка:** /ticket, /report, /staff
📊 **Статистика:** /ping, /botstats, /mtop

💡 **Для просмотра всех команд используйте ссылку выше!**"""
        
        await self.send_message(chat_id, help_text)
    
    async def cmd_editcmd(self, event, user_id: int, chat_id: int, args: List[str]):
        """Редактирование уровня доступа команды"""
        if not await self.check_permission(user_id, chat_id, 'editcmd'):
            await self.send_message(chat_id, "❌ У вас нет прав для этой команды!")
            return
        
        if len(args) < 2:
            await self.send_message(
                chat_id,
                "❌ Использование: /editcmd [команда] [уровень (0-100)]"
            )
            return
        
        command = args[0].lower()
        try:
            level = int(args[1])
            if level < 0 or level > 100:
                raise ValueError
        except:
            await self.send_message(chat_id, "❌ Уровень должен быть числом от 0 до 100!")
            return
        
        # Обновление уровня команды
        await self.db.execute_async(
            'INSERT OR REPLACE INTO commands (name, level) VALUES (?, ?)',
            (command, level)
        )
        
        self.command_levels[command] = level
        
        await self.send_message(
            chat_id,
            f"✅ Команда {command} теперь доступна с уровнем {level}"
        )
    
    async def cmd_newrole(self, event, user_id: int, chat_id: int, args: List[str]):
        """Создание новой роли"""
        if not await self.check_permission(user_id, chat_id, 'newrole'):
            await self.send_message(chat_id, "❌ У вас нет прав для этой команды!")
            return
        
        if len(args) < 2:
            await self.send_message(
                chat_id,
                "❌ Использование: /newrole [название] [уровень (0-100)]"
            )
            return
        
        role_name = args[0]
        try:
            level = int(args[1])
            if level < 0 or level > 100:
                raise ValueError
        except:
            await self.send_message(chat_id, "❌ Уровень должен быть числом от 0 до 100!")
            return
        
        # Добавление роли
        await self.db.execute_async(
            'INSERT OR REPLACE INTO available_roles (chat_id, role_name, required_level) VALUES (?, ?, ?)',
            (chat_id, role_name, level)
        )
        
        await self.send_message(
            chat_id,
            f"✅ Создана новая роль: {role_name} (уровень {level})"
        )
    
    async def cmd_role(self, event, user_id: int, chat_id: int, args: List[str]):
        """Выдача роли пользователю"""
        if not await self.check_permission(user_id, chat_id, 'role'):
            await self.send_message(chat_id, "❌ У вас нет прав для этой команды!")
            return
        
        if len(args) < 2:
            await self.send_message(
                chat_id,
                "❌ Использование: /role [пользователь] [роль]"
            )
            return
        
        target_id = await self.get_user_id_from_mention(args[0])
        role_name = args[1]
        
        # Получение уровня роли
        role_data = await self.db.fetchone_async(
            'SELECT required_level FROM available_roles WHERE chat_id = ? AND role_name = ?',
            (chat_id, role_name)
        )
        
        if not role_data:
            await self.send_message(chat_id, f"❌ Роль {role_name} не существует!")
            return
        
        role_level = role_data[0]
        
        # Выдача роли
        await self.db.execute_async(
            'INSERT OR REPLACE INTO roles (user_id, chat_id, role, level) VALUES (?, ?, ?, ?)',
            (target_id, chat_id, role_name, role_level)
        )
        
        await self.send_message(
            chat_id,
            f"✅ Пользователю [id{target_id}|] выдана роль: {role_name}"
        )
    
    async def cmd_ping(self, event, user_id: int, chat_id: int, args: List[str]):
        """Пинг бота"""
        start = time.time()
        await self.send_message(chat_id, "🏓 Понг!")
        end = time.time()
        print(f"Ping: {end - start} сек")
    
    async def cmd_botstats(self, event, user_id: int, chat_id: int, args: List[str]):
        """Статистика бота"""
        users_count = await self.db.fetchone_async('SELECT COUNT(*) FROM users')
        chats_count = await self.db.fetchone_async('SELECT COUNT(*) FROM chats')
        
        stats_text = f"""📊 **Статистика Apex × Чат-менеджер**

👥 Пользователей: {users_count[0]}
💬 Чатов: {chats_count[0]}
⚡ Версия: 2.0.0
🕒 Статус: 🟢 Работает

🔗 Сообщество: https://vk.com/apexchatmanager"""
        
        await self.send_message(chat_id, stats_text)
    
    # ==================== СИСТЕМА РАБОВ ====================
    
    async def cmd_slave(self, event, user_id: int, chat_id: int, args: List[str]):
        """Покупка раба"""
        if len(args) < 1:
            await self.send_message(
                chat_id,
                "❌ Использование: /slave [пользователь] [цена]\nИли: /slave list - список рабов"
            )
            return
        
        if args[0].lower() == 'list':
            await self.show_slaves_list(user_id, chat_id)
            return
        
        if len(args) < 2:
            await self.send_message(chat_id, "❌ Укажите цену!")
            return
        
        try:
            slave_id = await self.get_user_id_from_mention(args[0])
            price = int(args[1])
        except:
            await self.send_message(chat_id, "❌ Неверный формат!")
            return
        
        if slave_id == user_id:
            await self.send_message(chat_id, "❌ Нельзя купить самого себя!")
            return
        
        user_data = await self.get_user(user_id, chat_id)
        
        if user_data['rubles'] < price:
            await self.send_message(chat_id, f"❌ Недостаточно средств! Нужно {price} ₽")
            return
        
        # Проверка, не является ли пользователь уже рабом
        existing = await self.db.fetchone_async(
            'SELECT 1 FROM slaves WHERE slave_id = ?',
            (slave_id,)
        )
        if existing:
            await self.send_message(chat_id, "❌ Этот пользователь уже является чьим-то рабом!")
            return
        
        # Получение информации о пользователе
        try:
            user_info = await asyncio.to_thread(self.vk.users.get, user_ids=slave_id)
            slave_name = f"{user_info[0]['first_name']} {user_info[0]['last_name']}"
        except:
            slave_name = f"Пользователь {slave_id}"
        
        # Покупка раба
        await self.db.execute_async('''
            INSERT INTO slaves (owner_id, slave_id, name, price, bought_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, slave_id, slave_name, price, datetime.now().isoformat()))
        
        await self.db.execute_async(
            'UPDATE users SET rubles = rubles - ? WHERE id = ?',
            (price, user_id)
        )
        
        await self.send_message(
            chat_id,
            f"✅ Вы купили раба {slave_name} за {price} ₽!\n"
            f"Используйте /workslave чтобы заставить работать\n"
            f"/chains чтобы надеть цепи\n"
            f"/sellslave чтобы продать"
        )
    
    async def show_slaves_list(self, user_id: int, chat_id: int):
        """Показать список рабов"""
        slaves = await self.db.fetchall_async(
            'SELECT * FROM slaves WHERE owner_id = ?',
            (user_id,)
        )
        
        if not slaves:
            await self.send_message(chat_id, "📭 У вас нет рабов! Купите раба через /slave [пользователь] [цена]")
            return
        
        text = "🔗 **Ваши рабы:**\n\n"
        for i, slave in enumerate(slaves, 1):
            slave_id = slave[2]
            name = slave[3]
            level = slave[4]
            work_type = slave[6]
            chains = slave[7]
            price = slave[8]
            
            chain_emoji = "⛓️" * min(chains, 5) if chains else "🔗"
            
            text += f"{i}. {name}\n"
            text += f"   🧬 Уровень: {level} | Работа: {work_type}\n"
            text += f"   {chain_emoji} Цепи: {chains}\n"
            text += f"   💰 Цена: {price} ₽\n\n"
        
        await self.send_message(chat_id, text)
    
    async def cmd_workslave(self, event, user_id: int, chat_id: int, args: List[str]):
        """Заставить раба работать"""
        if len(args) < 1:
            await self.send_message(
                chat_id,
                "❌ Использование: /workslave [имя_раба] [тип_работы]\n"
                "Типы работ: miner, farmer, builder, merchant"
            )
            return
        
        slave_name = args[0]
        work_type = args[1] if len(args) > 1 else 'miner'
        
        # Поиск раба
        slave = await self.db.fetchone_async(
            'SELECT * FROM slaves WHERE owner_id = ? AND name LIKE ?',
            (user_id, f'%{slave_name}%')
        )
        
        if not slave:
            await self.send_message(chat_id, "❌ Раб не найден!")
            return
        
        slave_id = slave[0]
        slave_user_id = slave[2]
        slave_level = slave[4]
        slave_chains = slave[7]
        
        # Проверка времени последней работы
        last_work = slave[10]
        if last_work:
            last_time = datetime.fromisoformat(last_work)
            if datetime.now() - last_time < timedelta(hours=1):
                remaining = 3600 - (datetime.now() - last_time).total_seconds()
                await self.send_message(
                    chat_id,
                    f"⏰ Раб устал! Отдых {int(remaining/60)} минут"
                )
                return
        
        # Заработок в зависимости от типа работы и уровня
        earnings = {
            'miner': 50 + slave_level * 10,
            'farmer': 40 + slave_level * 8,
            'builder': 60 + slave_level * 12,
            'merchant': 80 + slave_level * 15
        }
        
        earn = earnings.get(work_type, 50) * (1 - slave_chains * 0.1)
        earn = max(10, int(earn))
        
        # Обновление опыта раба
        exp_gain = random.randint(10, 30)
        new_exp = slave[5] + exp_gain
        
        if new_exp >= slave_level * 100:
            new_level = slave_level + 1
            await self.db.execute_async(
                'UPDATE slaves SET level = ?, exp = ? WHERE id = ?',
                (new_level, new_exp - slave_level * 100, slave_id)
            )
            level_up_text = f"\n✨ Раб повысил уровень до {new_level}!"
        else:
            await self.db.execute_async(
                'UPDATE slaves SET exp = ? WHERE id = ?',
                (new_exp, slave_id)
            )
            level_up_text = ""
        
        # Обновление баланса владельца
        await self.db.execute_async(
            'UPDATE users SET rubles = rubles + ? WHERE id = ?',
            (earn, user_id)
        )
        
        # Обновление времени работы
        await self.db.execute_async(
            'UPDATE slaves SET last_work = ?, work_type = ? WHERE id = ?',
            (datetime.now().isoformat(), work_type, slave_id)
        )
        
        await self.send_message(
            chat_id,
            f"⛏️ Раб {slave[3]} работал как {work_type}\n"
            f"💰 Заработано: {earn} ₽\n"
            f"📈 Опыт: +{exp_gain}{level_up_text}"
        )
    
    async def cmd_sellslave(self, event, user_id: int, chat_id: int, args: List[str]):
        """Продажа раба"""
        if len(args) < 2:
            await self.send_message(
                chat_id,
                "❌ Использование: /sellslave [имя_раба] [цена]"
            )
            return
        
        slave_name = args[0]
        try:
            price = int(args[1])
        except:
            await self.send_message(chat_id, "❌ Неверная цена!")
            return
        
        # Поиск раба
        slave = await self.db.fetchone_async(
            'SELECT * FROM slaves WHERE owner_id = ? AND name LIKE ?',
            (user_id, f'%{slave_name}%')
        )
        
        if not slave:
            await self.send_message(chat_id, "❌ Раб не найден!")
            return
        
        slave_id = slave[0]
        
        # Обновление цены
        await self.db.execute_async(
            'UPDATE slaves SET price = ? WHERE id = ?',
            (price, slave_id)
        )
        
        await self.send_message(
            chat_id,
            f"💰 Раб {slave[3]} выставлен на продажу за {price} ₽!\n"
            f"Купить может любой командой /slave [пользователь] [цена]"
        )
    
    async def cmd_chains(self, event, user_id: int, chat_id: int, args: List[str]):
        """Надеть цепи на раба"""
        if len(args) < 2:
            await self.send_message(
                chat_id,
                "❌ Использование: /chains [имя_раба] [количество]"
            )
            return
        
        slave_name = args[0]
        try:
            chains = int(args[1])
            if chains < 0 or chains > 10:
                raise ValueError
        except:
            await self.send_message(chat_id, "❌ Количество цепей должно быть от 0 до 10!")
            return
        
        # Поиск раба
        slave = await self.db.fetchone_async(
            'SELECT * FROM slaves WHERE owner_id = ? AND name LIKE ?',
            (user_id, f'%{slave_name}%')
        )
        
        if not slave:
            await self.send_message(chat_id, "❌ Раб не найден!")
            return
        
        slave_id = slave[0]
        old_chains = slave[7]
        
        if chains > old_chains:
            cost = (chains - old_chains) * 500
            user_data = await self.get_user(user_id, chat_id)
            
            if user_data['rubles'] < cost:
                await self.send_message(
                    chat_id,
                    f"❌ Недостаточно средств! Нужно {cost} ₽ для покупки цепей"
                )
                return
            
            await self.db.execute_async(
                'UPDATE users SET rubles = rubles - ? WHERE id = ?',
                (cost, user_id)
            )
        
        # Обновление цепей
        await self.db.execute_async(
            'UPDATE slaves SET chains = ? WHERE id = ?',
            (chains, slave_id)
        )
        
        chain_emoji = "⛓️" * min(chains, 5) if chains else "🔗"
        
        await self.send_message(
            chat_id,
            f"{chain_emoji} У раба {slave[3]} теперь {chains} цепей!\n"
            f"Эффективность работы снижена на {chains * 10}%"
        )
    
    # ==================== ЭКОНОМИКА ====================
    
    async def cmd_balance(self, event, user_id: int, chat_id: int, args: List[str]):
        """Просмотр баланса"""
        target_id = user_id
        if args:
            target_id = await self.get_user_id_from_mention(args[0])
        
        user_data = await self.get_user(target_id, chat_id)
        
        text = f"""💼 **Баланс** [id{target_id}|]

💰 **Валюты:**
   • Рубли: {user_data['rubles']} ₽
   • Доллары: {user_data['dollars']} $
   • Евро: {user_data['euros']} €
   • Биткоины: {user_data['bitcoins']:.8f} ₿

⭐ **Рейтинг:** {user_data['rating']}
🎚 **Уровень:** {user_data['level']}
💎 **VIP:** {user_data['vip_status']}

🏭 **Майнинг:** Ур. {user_data['mining_level']} ({user_data['mining_speed']} BTC/ч)"""
        
        await self.send_message(chat_id, text)
    
    async def cmd_stats(self, event, user_id: int, chat_id: int, args: List[str]):
        """Статистика пользователя"""
        target_id = user_id
        if args:
            target_id = await self.get_user_id_from_mention(args[0])
        
        user_data = await self.get_user(target_id, chat_id)
        
        # Получение информации о пользователе
        try:
            user_info = await asyncio.to_thread(self.vk.users.get, user_ids=target_id)
            first_name = user_info[0]['first_name']
            last_name = user_info[0]['last_name']
        except:
            first_name = user_data['first_name']
            last_name = user_data['last_name']
        
        # Статистика сообщений
        today = datetime.now().strftime('%Y-%m-%d')
        stats = await self.db.fetchone_async('''
            SELECT messages, bad_words FROM message_stats
            WHERE user_id = ? AND chat_id = ? AND date = ?
        ''', (target_id, chat_id, today))
        
        messages_today = stats[0] if stats else 0
        bad_words_today = stats[1] if stats else 0
        
        # Агентская информация
        agent_text = ""
        if user_data['is_agent']:
            agent_text = f"\n🐩 Агент поддержки №{user_data['agent_number']}"
        
        # Проверка бана
        ban = await self.db.fetchone_async(
            'SELECT 1 FROM bans WHERE user_id = ? AND chat_id = ?',
            (target_id, chat_id)
        )
        
        text = f"""🔍 **Информация о пользователе:**

🗣 Статус: {user_data['role'] or 'Участник'}{agent_text}
📊 Сообщений сегодня: {messages_today}
⚠ Предупреждений: {user_data['warns']}/3
📄 Никнейм: {first_name} {last_name}
🚧 Блокировка: {'Да' if ban else 'Нет'}

📋 **Глобальная информация:**
💎 VIP статус: {user_data['vip_status']}
🎚 Уровень: {user_data['level']}
⭐ Рейтинг: {user_data['rating']}
👫 Пригласил: {user_data['invited_by'] or 'Никто'}
⚙ ID: {target_id}"""
        
        await self.send_message(chat_id, text)
    
    async def cmd_top(self, event, user_id: int, chat_id: int, args: List[str]):
        """Топ пользователей"""
        category = args[0].lower() if args else 'money'
        
        if category == 'money' or category == 'деньги':
            rows = await self.db.fetchall_async('''
                SELECT id, rubles + dollars*80 + euros*90 + bitcoins*5000000 as total
                FROM users
                ORDER BY total DESC
                LIMIT 10
            ''')
        elif category == 'bitcoin' or category == 'биткоин':
            rows = await self.db.fetchall_async('''
                SELECT id, bitcoins
                FROM users
                ORDER BY bitcoins DESC
                LIMIT 10
            ''')
        elif category == 'rating' or category == 'рейтинг':
            rows = await self.db.fetchall_async('''
                SELECT id, rating
                FROM users
                ORDER BY rating DESC
                LIMIT 10
            ''')
        else:
            rows = await self.db.fetchall_async('''
                SELECT id, level
                FROM users
                ORDER BY level DESC
                LIMIT 10
            ''')
        
        text = f"🏆 **Топ {category}:**\n\n"
        for i, row in enumerate(rows, 1):
            user_id_top = row[0]
            value = row[1]
            
            try:
                user_info = await asyncio.to_thread(self.vk.users.get, user_ids=user_id_top)
                name = f"{user_info[0]['first_name']} {user_info[0]['last_name']}"
            except:
                name = f"Пользователь {user_id_top}"
            
            if category in ['bitcoin', 'биткоин']:
                text += f"{i}. {name} — {value:.8f} BTC\n"
            else:
                text += f"{i}. {name} — {value:.2f}\n"
        
        await self.send_message(chat_id, text)
    
    async def cmd_mine(self, event, user_id: int, chat_id: int, args: List[str]):
        """Майнинг биткоинов"""
        user_data = await self.get_user(user_id, chat_id)
        
        if user_data['last_mining']:
            last_time = datetime.fromisoformat(user_data['last_mining'])
            now = datetime.now()
            hours_passed = (now - last_time).total_seconds() / 3600
            
            if hours_passed < 1:
                remaining = 3600 - (now - last_time).total_seconds()
                await self.send_message(
                    chat_id,
                    f"⛏️ Майнинг доступен через {int(remaining/60)} минут!"
                )
                return
            
            earned = user_data['mining_speed'] * hours_passed
        else:
            earned = user_data['mining_speed']
        
        # Обновление баланса
        await self.db.execute_async('''
            UPDATE users SET bitcoins = bitcoins + ?, last_mining = ?
            WHERE id = ?
        ''', (earned, datetime.now().isoformat(), user_id))
        
        await self.send_message(
            chat_id,
            f"⛏️ Вы намайнили {earned:.8f} BTC!\n"
            f"💰 Текущий баланс: {user_data['bitcoins'] + earned:.8f} BTC"
        )
    
    async def cmd_shop(self, event, user_id: int, chat_id: int, args: List[str]):
        """Магазин"""
        keyboard = VkKeyboard(inline=True)
        keyboard.add_button("🚘 Транспорт", color=VkKeyboardColor.PRIMARY)
        keyboard.add_button("🏢 Недвижимость", color=VkKeyboardColor.PRIMARY)
        keyboard.add_line()
        keyboard.add_button("📱 Телефоны", color=VkKeyboardColor.SECONDARY)
        keyboard.add_button("💻 Компьютеры", color=VkKeyboardColor.SECONDARY)
        keyboard.add_line()
        keyboard.add_button("🎖 Рейтинг", color=VkKeyboardColor.POSITIVE)
        
        text = """🛒 **Apex Shop**

🚘 **Транспорт:**
   — 🚗 автомобили (1000₽)
   — 🚁 вертолеты (5000₽)
   — ✈ самолеты (10000₽)

🏢 **Недвижимость:**
   — 🏡 дом (15000₽)

📌 **Остальное:**
   — 🎖 рейтинг (100₽ за 1 ед.)

📥 Для покупки: /buy [категория] [номер]"""
        
        await self.send_message(chat_id, text, keyboard)
    
    # ==================== ВСПОМОГАТЕЛЬНЫЕ ====================
    
    async def get_user_id_from_mention(self, mention: str) -> int:
        """Получение ID пользователя из упоминания"""
        if mention.startswith('[id') and '|' in mention:
            try:
                return int(mention.split('|')[0].replace('[id', ''))
            except:
                pass
        
        if mention.isdigit():
            return int(mention)
        
        return 0
    
    async def update_message_stats(self, user_id: int, chat_id: int, text: str):
        """Обновление статистики сообщений"""
        today = datetime.now().strftime('%Y-%m-%d')
        
        await self.db.execute_async('''
            INSERT INTO message_stats (user_id, chat_id, messages, date)
            VALUES (?, ?, 1, ?)
            ON CONFLICT(user_id, chat_id, date) DO UPDATE SET
            messages = messages + 1
        ''', (user_id, chat_id, today))
        
        # Обновление опыта
        await self.db.execute_async('''
            UPDATE users SET exp = exp + 1
            WHERE id = ?
        ''', (user_id,))
        
        # Проверка повышения уровня
        user = await self.db.fetchone_async('SELECT level, exp FROM users WHERE id = ?', (user_id,))
        
        if user and user[1] >= user[0] * 100:
            new_level = user[0] + 1
            await self.db.execute_async(
                'UPDATE users SET level = ?, exp = 0 WHERE id = ?',
                (new_level, user_id)
            )
            await self.send_message(chat_id, f"🎉 Поздравляем! Вы достигли {new_level} уровня!")
    
    async def handle_command(self, event, text: str, user_id: int, chat_id: int):
        """Обработка команд"""
        # Проверка мута
        mute = await self.db.fetchone_async(
            'SELECT until FROM mutes WHERE user_id = ? AND chat_id = ?',
            (user_id, chat_id)
        )
        if mute and datetime.fromisoformat(mute[0]) > datetime.now():
            return
        
        # Поиск команды
        for prefix in self.prefixes:
            if text.startswith(prefix):
                cmd = text[len(prefix):].lower().split()[0] if text[len(prefix):] else None
                args = text[len(prefix):].split()[1:] if len(text[len(prefix):].split()) > 1 else []
                
                if not cmd:
                    return
                
                # Проверка прав
                if not await self.check_permission(user_id, chat_id, cmd):
                    await self.send_message(chat_id, "❌ У вас нет прав для этой команды!")
                    return
                
                # Вызов команды
                commands = {
                    'help': self.cmd_help,
                    'editcmd': self.cmd_editcmd,
                    'newrole': self.cmd_newrole,
                    'role': self.cmd_role,
                    'slave': self.cmd_slave,
                    'workslave': self.cmd_workslave,
                    'sellslave': self.cmd_sellslave,
                    'chains': self.cmd_chains,
                    'balance': self.cmd_balance,
                    'баланс': self.cmd_balance,
                    'stats': self.cmd_stats,
                    'стата': self.cmd_stats,
                    'top': self.cmd_top,
                    'топ': self.cmd_top,
                    'mine': self.cmd_mine,
                    'майнинг': self.cmd_mine,
                    'ping': self.cmd_ping,
                    'пинг': self.cmd_ping,
                    'botstats': self.cmd_botstats,
                    'статабота': self.cmd_botstats,
                    'shop': self.cmd_shop,
                    'магазин': self.cmd_shop,
                }
                
                if cmd in commands:
                    await commands[cmd](event, user_id, chat_id, args)
                return
    
    async def run(self):
        """Запуск бота"""
        self.init_db()
        print("🤖 Apex × Чат-менеджер запущен!")
        print("🔗 Сообщество: https://vk.com/apexchatmanager")
        print("📊 База данных: SQLite (синхронная с асинхронной оберткой)")
        
        for event in self.longpoll.listen():
            if event.type == VkBotEventType.MESSAGE_NEW:
                if event.obj.text:
                    await self.handle_command(
                        event,
                        event.obj.text,
                        event.obj.from_id,
                        event.obj.peer_id
                    )
                    await self.update_message_stats(
                        event.obj.from_id,
                        event.obj.peer_id,
                        event.obj.text
                    )

# Запуск
if __name__ == "__main__":
    TOKEN = "vk1.a.KA15ljp23_4l6s3DomdeTkkE7DHmsflVzVWGMjBm7kzWm0eOATiZI_LTGXlzC2nnRHx3fcgjVivrqwUq5WUQN-7tfecpSfGfjjrhprbxh9B7WdUgpZ9sgKo5bYpLSzKmuahc3Ylf3Zysct7yvMch0FGoECKYe6gSGBerNJKsDIbAlndr9HzLcMojM7ePA5GdkZUCA4ICcV7ttTSHnqZUzQ"
    GROUP_ID = 237250582  # ID группы
    
    bot = ApexChatManager(TOKEN, GROUP_ID)
    asyncio.run(bot.run())
