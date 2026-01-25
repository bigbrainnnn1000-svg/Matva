import json
import os
import random
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler

TOKEN = "8542959870:AAH7ECRyusZRDiULPWngvcjygQ9smi-cA3E"
ADMIN_ID = 6443845944
FARM_COOLDOWN = 4
COMPENSATION_AMOUNT = 15

LEVELS = [
    {"level": 1, "name": "👶 Рекрут", "min_coins": 0, "max_coins": 100},
    {"level": 2, "name": "🛡️ Страж", "min_coins": 101, "max_coins": 200},
    {"level": 3, "name": "⚔️ Рыцарь", "min_coins": 201, "max_coins": 300},
    {"level": 4, "name": "👑 Титян", "min_coins": 301, "max_coins": 400},
    {"level": 5, "name": "🔥 Божество", "min_coins": 401, "max_coins": 1000000}
]

SHOP_ITEMS = {
    1: {"name": "🔔 Сигна от Kme_Dota", "price": 50, "description": "Сигна от Kme_Dota", "exchangeable": True},
    2: {"name": "👥 Сигна от Лсной братвы", "price": 100, "description": "Сигна от Лсной братвы", "exchangeable": True},
    3: {"name": "👑 Модер в чате", "price": 150, "description": "Стать модератором в чате", "exchangeable": True},
    4: {"name": "🎮 Модер на твиче", "price": 200, "description": "Стать модератором на твиче", "exchangeable": True},
    5: {"name": "🎵 Трек про тебя", "price": 300, "description": "Заказать трек про себя", "exchangeable": True},
    6: {"name": "⚔️ Dota+", "price": 400, "description": "Получить Dota+ на месяц", "exchangeable": True}
}

class Database:
    def __init__(self, filename="kme_data.json"):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.filename = os.path.join(current_dir, filename)
        
        # Создаем резервную копию при запуске
        self.create_backup()
        
        self.data = self.load_data()
        print(f"📁 База данных: {self.filename}")
        print(f"👥 Загружено игроков: {len(self.data)}")
    
    def create_backup(self):
        if os.path.exists(self.filename):
            try:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_file = f"{self.filename}.backup_{timestamp}"
                with open(self.filename, 'r', encoding='utf-8') as src:
                    content = src.read()
                    if content.strip():
                        with open(backup_file, 'w', encoding='utf-8') as dst:
                            dst.write(content)
                        print(f"💾 Создана резервная копия: {backup_file}")
            except Exception as e:
                print(f"⚠️ Не удалось создать бэкап: {e}")
    
    def load_data(self):
        if not os.path.exists(self.filename):
            print("📝 Файл базы не найден, создаю новую...")
            return {}
        
        try:
            with open(self.filename, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                
            if not content:
                print("⚠️ Файл базы пустой")
                return {}
            
            data = json.loads(content)
            
            if not isinstance(data, dict):
                print("❌ Неверный формат базы данных")
                return {}
            
            # Конвертируем старые данные
            for user_id, user_data in data.items():
                if 'last_active' not in user_data:
                    user_data['last_active'] = datetime.now().isoformat()
            
            print(f"✅ Успешно загружено {len(data)} пользователей")
            return data
            
        except json.JSONDecodeError as e:
            print(f"❌ Ошибка JSON в файле БД: {e}")
            print("💡 База НЕ перезаписана, проверьте файл kme_data.json")
            return {}
        except Exception as e:
            print(f"❌ Ошибка загрузки БД: {e}")
            print("💡 База НЕ перезаписана, сохраняется старая")
            return {}
    
    def save_data(self):
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            print(f"💾 База сохранена: {len(self.data)} пользователей")
        except Exception as e:
            print(f"❌ Ошибка сохранения БД: {e}")
    
    def get_user(self, user_id):
        user_id = str(user_id)
        if user_id not in self.data:
            print(f"👤 Новый пользователь: {user_id}")
            self.data[user_id] = {
                'coins': 0,
                'last_farm': None,
                'username': '',
                'display_name': '',
                'inventory': [],
                'total_farmed': 0,
                'farm_count': 0,
                'admin_gifted': 0,
                'last_active': datetime.now().isoformat()
            }
            self.save_data()
        return self.data[user_id]
    
    def update_user(self, user_id, username="", display_name=""):
        user = self.get_user(user_id)
        if username:
            user['username'] = username
        if display_name:
            user['display_name'] = display_name
        user['last_active'] = datetime.now().isoformat()
        self.save_data()
    
    def can_farm(self, user_id):
        user = self.get_user(user_id)
        user['last_active'] = datetime.now().isoformat()
        
        if not user['last_farm']:
            return True, "✅ Можно фармить!"
        
        last = datetime.fromisoformat(user['last_farm'])
        now = datetime.now()
        
        if now - last >= timedelta(hours=FARM_COOLDOWN):
            return True, "✅ Можно фармить!"
        else:
            wait = (last + timedelta(hours=FARM_COOLDOWN)) - now
            hours = wait.seconds // 3600
            minutes = (wait.seconds % 3600) // 60
            return False, f"⏳ Ждите {hours:02d}:{minutes:02d}"
    
    def add_coins(self, user_id, amount, from_farm=True, from_admin=False):
        user = self.get_user(user_id)
        user['coins'] += amount
        if from_farm:
            user['total_farmed'] += amount
            user['farm_count'] += 1
            user['last_farm'] = datetime.now().isoformat()
        if from_admin:
            user['admin_gifted'] += amount
        user['last_active'] = datetime.now().isoformat()
        self.save_data()
        return user['coins']
    
    def buy_item(self, user_id, item_id):
        user = self.get_user(user_id)
        user['last_active'] = datetime.now().isoformat()
        
        if item_id not in SHOP_ITEMS:
            return False, "❌ Такого товара нет!"
        
        item = SHOP_ITEMS[item_id]
        if user['coins'] < item['price']:
            return False, f"❌ Недостаточно коинов! Нужно {item['price']}, есть {user['coins']}"
        
        user['coins'] -= item['price']
        user['inventory'].append({
            'id': item_id,
            'name': item['name'],
            'price': item['price'],
            'bought_at': datetime.now().isoformat(),
            'exchanged': False
        })
        self.save_data()
        return True, f"✅ Куплено: {item['name']}"
    
    def exchange_item(self, user_id, item_index):
        user = self.get_user(user_id)
        user['last_active'] = datetime.now().isoformat()
        
        if item_index >= len(user['inventory']):
            return False, "❌ Такого предмета нет!"
        
        item = user['inventory'][item_index]
        if item.get('exchanged', False):
            return False, "❌ Уже обменян!"
        
        user['inventory'][item_index]['exchanged'] = True
        user['inventory'][item_index]['exchanged_at'] = datetime.now().isoformat()
        self.save_data()
        return True, item
    
    def remove_item(self, user_id, item_index):
        user = self.get_user(user_id)
        if item_index >= len(user['inventory']):
            return False, "❌ Такого предмета нет!"
        
        removed_item = user['inventory'].pop(item_index)
        self.save_data()
        return True, removed_item
    
    def add_compensation_to_all(self, amount):
        for user_id in self.data:
            user = self.get_user(user_id)
            user['coins'] += amount
            user['last_active'] = datetime.now().isoformat()
        self.save_data()
        return len(self.data)
    
    def get_user_level(self, total_coins):
        for level in LEVELS:
            if level["min_coins"] <= total_coins <= level["max_coins"]:
                return level
        return LEVELS[-1]
    
    def search_users(self, search_term):
        results = []
        search_term = search_term.lower()
        
        for user_id, user_data in self.data.items():
            username = user_data.get('username', '').lower()
            display_name = user_data.get('display_name', '').lower()
            
            if search_term in username or search_term in display_name:
                results.append((user_id, user_data))
        
        return results

db = Database()

async def send_exchange_notification(context, user_id, item):
    user_data = db.get_user(user_id)
    
    user_name = f"@{user_data.get('username', '')}" if user_data.get('username') else f"ID:{user_id}"
    display_name = user_data.get('display_name', 'Неизвестно')
    
    message = (
        f"🔔 НОВЫЙ ОБМЕН ПРЕДМЕТА!\n\n"
        f"🎁 Предмет: {item['name']}\n"
        f"💰 Стоимость: {item['price']} коинов\n"
        f"👤 Игрок: {user_name}\n"
        f"📝 Имя: {display_name}\n"
        f"🆔 ID: {user_id}\n\n"
        f"⚠️ Не забудьте выполнить услугу!\n"
        f"✅ После выполнения удалите предмет:\n"
        f"/removeitem {user_id} {len(user_data['inventory'])-1}"
    )
    
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=message)
        print(f"📨 Уведомление об обмене отправлено админу: {user_id} -> {item['name']}")
    except Exception as e:
        print(f"❌ Ошибка отправки уведомления админу: {e}")

async def send_party_announcement(context, user_id, mmr):
    user = await context.bot.get_chat(user_id)
    user_data = db.get_user(user_id)
    level = db.get_user_level(user_data['total_farmed'])
    
    message = (
        "🎮════════════════════════════════════🎮\n\n"
        f"🔍 <b>НОВЫЙ ИГРОК ИЩЕТ ТИМУ!</b>\n\n"
        f"👤 <b>Игрок:</b> {user.first_name}\n"
    )
    
    if user.last_name:
        message += f"👤 <b>Фамилия:</b> {user.last_name}\n"
    
    if user.username:
        message += f"📱 <b>Telegram:</b> @{user.username}\n"
    
    message += (
        f"📊 <b>MMR:</b> <code>{mmr}</code>\n"
        f"🆔 <b>ID:</b> <code>{user_id}</code>\n\n"
    )
    
    if user_data['display_name']:
        message += f"📝 <b>Имя в боте:</b> {user_data['display_name']}\n"
    
    message += (
        f"💰 <b>Баланс:</b> {user_data['coins']} коинов\n"
        f"🏆 <b>Уровень:</b> {level['name']}\n\n"
        "────────────────────────────────────\n\n"
        f"💬 <b>Как связаться:</b>\n"
    )
    
    if user.username:
        message += f"1. 📨 Написать в Telegram: @{user.username}\n"
        message += f"2. 🤖 Написать в боте: /write {user_id}\n"
    else:
        message += f"📨 Написать в боте: /write {user_id}\n"
    
    message += "\n🎮════════════════════════════════════🎮"
    
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=message,
            parse_mode='HTML'
        )
        print(f"📢 Объявление о поиске тимы отправлено: {user_id} (MMR: {mmr})")
    except Exception as e:
        print(f"❌ Ошибка отправки объявления: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.update_user(user.id, user.username, user.full_name)
    user_data = db.get_user(user.id)
    level = db.get_user_level(user_data['total_farmed'])
    
    message = (
        "✨════════════════════════════════════✨\n\n"
        f"🎮 <b>Добро пожаловать, {user.first_name}!</b>\n\n"
        f"💰 <b>Баланс:</b> {user_data['coins']} коинов\n"
        f"🏆 <b>Уровень:</b> {level['name']}\n\n"
        "📋 <b>Основные команды:</b>\n\n"
        "• /farm - Фармить коины\n"
        "• /balance - Ваш баланс\n"
        "• /level - Ваш уровень\n"
        "• /shop - Магазин предметов\n"
        "• /inventory - Ваш инвентарь\n"
        "• /party [MMR] - Найти тиму\n"
        "• /top - Топ игроков\n"
        "• /profile - Ваш профиль\n"
        "• /users - Поиск игроков\n"
        "• /help - Помощь\n\n"
        "✨════════════════════════════════════✨"
    )
    
    await update.message.reply_text(message, parse_mode='HTML')

async def farm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.update_user(user.id)
    can_farm, msg = db.can_farm(user.id)
    
    if not can_farm:
        await update.message.reply_text(f"❌ {msg}")
        return
    
    coins = random.randint(0, 5)
    new_balance = db.add_coins(user.id, coins)
    
    farm_messages = [
        f"💰 Вы нашли {coins} коинов!",
        f"🎰 Вам повезло! +{coins} коинов",
        f"⚡ Быстрый фарм: {coins} коинов",
        f"💎 Добыто: {coins} коинов",
        f"🎯 Точно в цель! {coins} коинов"
    ]
    
    message = (
        "🔄════════════════════════════════════🔄\n\n"
        f"✅ {random.choice(farm_messages)}\n\n"
        f"💰 <b>Получено:</b> {coins} коинов\n"
        f"🏦 <b>Баланс:</b> {new_balance} коинов\n"
        f"⏰ <b>Следующий фарм:</b> через {FARM_COOLDOWN}ч\n\n"
        "🔄════════════════════════════════════🔄"
    )
    
    await update.message.reply_text(message, parse_mode='HTML')

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.update_user(user.id)
    user_data = db.get_user(user.id)
    level = db.get_user_level(user_data['total_farmed'])
    
    message = (
        "💰════════════════════════════════════💰\n\n"
        f"👤 <b>Игрок:</b> {user.first_name}\n\n"
        f"💳 <b>Коинсы:</b> {user_data['coins']}\n"
        f"🏆 <b>Всего заработано:</b> {user_data['total_farmed']}\n"
        f"📈 <b>Уровень:</b> {level['name']}\n"
        f"🔄 <b>Фармов:</b> {user_data['farm_count']}\n"
        f"🎁 <b>Подарков от админа:</b> {user_data['admin_gifted']}\n\n"
        "💰════════════════════════════════════💰"
    )
    
    await update.message.reply_text(message, parse_mode='HTML')

async def level(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.update_user(user.id)
    user_data = db.get_user(user.id)
    current_level = db.get_user_level(user_data['total_farmed'])
    
    next_level = None
    for i, level in enumerate(LEVELS):
        if level["min_coins"] <= user_data['total_farmed'] <= level["max_coins"]:
            if i + 1 < len(LEVELS):
                next_level = LEVELS[i + 1]
            break
    
    message = (
        "🏆════════════════════════════════════🏆\n\n"
        f"👤 <b>Игрок:</b> {user.first_name}\n"
        f"🎯 <b>Текущий уровень:</b> {current_level['name']}\n"
        f"💰 <b>Всего заработано:</b> {user_data['total_farmed']} коинов\n\n"
    )
    
    if next_level:
        need = next_level['min_coins'] - user_data['total_farmed']
        message += f"📈 <b>До следующего уровня:</b> {need} коинов\n\n"
    
    message += "🏆════════════════════════════════════🏆"
    
    await update.message.reply_text(message, parse_mode='HTML')

async def shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.update_user(user.id)
    user_data = db.get_user(user.id)
    
    message = (
        "🛍️════════════════════════════════════🛍️\n\n"
        f"🏪 <b>МАГАЗИН ПРЕДМЕТОВ</b>\n\n"
    )
    
    for item_id, item in SHOP_ITEMS.items():
        message += (
            f"{item_id}. <b>{item['name']}</b>\n"
            f"   💰 Цена: {item['price']} коинов\n"
            f"   📝 {item['description']}\n"
            f"   🛒 <code>/buy_{item_id}</code>\n\n"
        )
    
    message += (
        f"💵 <b>Ваш баланс:</b> {user_data['coins']} коинов\n\n"
        "🛍️════════════════════════════════════🛍️"
    )
    
    await update.message.reply_text(message, parse_mode='HTML')

async def buy_item(update: Update, context: ContextTypes.DEFAULT_TYPE, item_id: int):
    user = update.effective_user
    db.update_user(user.id)
    success, result = db.buy_item(user.id, item_id)
    user_data = db.get_user(user.id)
    
    if success:
        message = (
            "🎉════════════════════════════════════🎉\n\n"
            f"✅ <b>ПОКУПКА УСПЕШНА!</b>\n\n"
            f"🎁 <b>Предмет:</b> {result}\n"
            f"💳 <b>Новый баланс:</b> {user_data['coins']} коинов\n\n"
            f"📦 Предмет добавлен в инвентарь\n"
            f"🔧 Используйте /inventory чтобы обменять\n\n"
            "🎉════════════════════════════════════🎉"
        )
        await update.message.reply_text(message, parse_mode='HTML')
    else:
        await update.message.reply_text(f"❌ {result}")

async def inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.update_user(user.id)
    user_data = db.get_user(user.id)
    
    if not user_data['inventory']:
        message = (
            "📦════════════════════════════════════📦\n\n"
            f"🗑️ <b>Инвентарь пуст</b>\n\n"
            f"🛍️ Зайдите в магазин /shop\n\n"
            "📦════════════════════════════════════📦"
        )
        await update.message.reply_text(message, parse_mode='HTML')
        return
    
    keyboard = []
    for i, item in enumerate(user_data['inventory']):
        btn_text = f"{i+1}. {item['name']}"
        if item.get('exchanged', False):
            btn_text += " ✅"
            callback = f"view_{i}"
        else:
            btn_text += " 🔄"
            callback = f"exchange_{i}"
        
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=callback)])
    
    keyboard.append([InlineKeyboardButton("❌ Закрыть", callback_data="close")])
    
    message = (
        "📦════════════════════════════════════📦\n\n"
        f"🎒 <b>ВАШ ИНВЕНТАРЬ</b>\n\n"
        f"👤 <b>Игрок:</b> {user.first_name}\n"
        f"📊 <b>Предметов:</b> {len(user_data['inventory'])}\n\n"
        f"💡 Нажмите на предмет для обмена\n\n"
        "📦════════════════════════════════════📦"
    )
    
    await update.message.reply_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not db.data:
        await update.message.reply_text("📭 Нет игроков")
        return
    
    top_users = sorted(db.data.items(), key=lambda x: x[1]['total_farmed'], reverse=True)[:10]
    
    message = (
        "🏆════════════════════════════════════🏆\n\n"
        f"👑 <b>ТОП-10 ИГРОКОВ</b>\n\n"
    )
    
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    for i, (user_id, user_data) in enumerate(top_users):
        if i < len(medals):
            medal = medals[i]
        else:
            medal = f"{i+1}."
        
        if user_data.get('username'):
            name = f"@{user_data['username']}"
        elif user_data.get('display_name'):
            name = user_data['display_name'][:15]
            if len(user_data['display_name']) > 15:
                name += "..."
        else:
            name = f"ID:{user_id[:6]}"
        
        level = db.get_user_level(user_data['total_farmed'])
        
        message += (
            f"{medal} <b>{name}</b>\n"
            f"   💰 {user_data['total_farmed']} коинов | {level['name']}\n"
        )
        
        if i < len(top_users) - 1:
            message += "\n"
    
    message += "\n🏆════════════════════════════════════🏆"
    
    await update.message.reply_text(message, parse_mode='HTML')

async def party(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.update_user(user.id)
    
    if not context.args:
        message = (
            "🎮════════════════════════════════════🎮\n\n"
            f"🎯 <b>ПОИСК ТИМЫ ДЛЯ DOTA 2</b>\n\n"
            f"📝 <b>Использование:</b>\n"
            f"<code>/party [ваш MMR]</code>\n\n"
            f"📋 <b>Пример:</b>\n"
            f"<code>/party 4500</code>\n\n"
            f"🎮════════════════════════════════════🎮"
        )
        await update.message.reply_text(message, parse_mode='HTML')
        return
    
    try:
        mmr = int(context.args[0])
        await send_party_announcement(context, user.id, mmr)
        
        message = (
            "✅════════════════════════════════════✅\n\n"
            f"🎮 <b>ЗАЯВКА ПРИНЯТА!</b>\n\n"
            f"👤 <b>Игрок:</b> {user.first_name}\n"
            f"📊 <b>MMR:</b> {mmr}\n\n"
            f"📨 Админ получил вашу заявку\n"
            f"👥 Скоро поможем найти тиму!\n\n"
            "✅════════════════════════════════════✅"
        )
        
        await update.message.reply_text(message, parse_mode='HTML
        
    except ValueError:
        await update.message.reply_text("❌ Укажите число MMR")

async def write(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.update_user(user.id)
    
    if len(context.args) < 2:
        message = (
            "✍️════════════════════════════════════✍️\n\n"
            f"📨 <b>НАПИСАТЬ ИГРОКУ</b>\n\n"
            f"📝 <b>Использование:</b>\n"
            f"<code>/write [ID_игрока] [сообщение]</code>\n\n"
            f"📋 <b>Пример:</b>\n"
            f"<code>/write 6443845944 Привет, ищешь тиму?</code>\n\n"
            "✍️════════════════════════════════════✍️"
        )
        await update.message.reply_text(message, parse_mode='HTML')
        return
    
    try:
        target_id = int(context.args[0])
        message_text = " ".join(context.args[1:])
        
        receiver_message = (
            "📨════════════════════════════════════📨\n\n"
            f"💌 <b>ВАМ ПРИШЛО СООБЩЕНИЕ!</b>\n\n"
            f"👤 <b>От:</b> {user.first_name}\n"
        )
        
        if user.username:
            receiver_message += f"📱 <b>Telegram:</b> @{user.username}\n"
        
        receiver_message += f"🆔 <b>ID:</b> {user.id}\n\n"
        receiver_message += f"💬 <b>Сообщение:</b>\n<code>{message_text}</code>\n\n"
        receiver_message += "📨════════════════════════════════════📨"
        
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=receiver_message,
                parse_mode='HTML'
            )
            
            confirmation = (
                "✅════════════════════════════════════✅\n\n"
                f"📨 <b>СООБЩЕНИЕ ОТПРАВЛЕНО!</b>\n\n"
                f"👤 <b>Игроку с ID:</b> {target_id}\n"
                f"💬 <b>Ваше сообщение:</b>\n<code>{message_text}</code>\n\n"
                "✅════════════════════════════════════✅"
            )
            
            await update.message.reply_text(confirmation, parse_mode='HTML')
            
        except Exception as e:
            await update.message.reply_text(
                f"❌ Не удалось отправить сообщение. Игрок может заблокировать бота."
            )
            
    except ValueError:
        await update.message.reply_text("❌ ID должен быть числом")

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.update_user(user.id)
    user_data = db.get_user(user.id)
    level = db.get_user_level(user_data['total_farmed'])
    
    last_active = datetime.fromisoformat(user_data['last_active'])
    hours_ago = (datetime.now() - last_active).seconds // 3600
    
    message = (
        "👤════════════════════════════════════👤\n\n"
        f"📋 <b>ПРОФИЛЬ ИГРОКА</b>\n\n"
        f"👤 <b>Имя:</b> {user.first_name}\n"
    )
    
    if user.username:
        message += f"📱 <b>Telegram:</b> @{user.username}\n"
    
    if user_data['display_name']:
        message += f"📝 <b>Имя в боте:</b> {user_data['display_name']}\n"
    
    message += (
        f"🆔 <b>ID:</b> <code>{user.id}</code>\n"
        f"⏰ <b>Был активен:</b> {hours_ago} ч. назад\n\n"
        f"💰 <b>Баланс:</b> {user_data['coins']} коинов\n"
        f"🏆 <b>Уровень:</b> {level['name']}\n"
        f"📈 <b>Всего заработано:</b> {user_data['total_farmed']} коинов\n"
        f"🔄 <b>Фармов:</b> {user_data['farm_count']}\n"
        f"📦 <b>Предметов в инвентаре:</b> {len(user_data['inventory'])}\n\n"
        "👤════════════════════════════════════👤"
    )
    
    await update.message.reply_text(message, parse_mode='HTML')

async def users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.update_user(user.id)
    
    if not context.args:
        total_users = len(db.data)
        active_today = 0
        
        for user_data in db.data.values():
            last_active = datetime.fromisoformat(user_data['last_active'])
            if (datetime.now() - last_active).days == 0:
                active_today += 1
        
        message = (
            "👥════════════════════════════════════👥\n\n"
            f"📊 <b>СТАТИСТИКА ПОЛЬЗОВАТЕЛЕЙ</b>\n\n"
            f"👥 <b>Всего игроков:</b> {total_users}\n"
            f"🟢 <b>Активных сегодня:</b> {active_today}\n\n"
            f"🔍 <b>Поиск игроков:</b>\n"
            f"<code>/users [имя или username]</code>\n\n"
            f"📋 <b>Пример:</b>\n"
            f"<code>/users matvei</code>\n"
            f"<code>/users @username</code>\n\n"
            "👥════════════════════════════════════👥"
        )
        
        await update.message.reply_text(message, parse_mode='HTML')
        return
    
    search_term = " ".join(context.args)
    results = db.search_users(search_term)
    
    if not results:
        message = (
            "🔍════════════════════════════════════🔍\n\n"
            f"❌ <b>НИЧЕГО НЕ НАЙДЕНО</b>\n\n"
            f"🔍 <b>Поиск:</b> {search_term}\n\n"
            f"💡 Попробуйте другое имя или username\n\n"
            "🔍════════════════════════════════════🔍"
        )
        await update.message.reply_text(message, parse_mode='HTML')
        return
    
    message = (
        "🔍════════════════════════════════════🔍\n\n"
        f"✅ <b>НАЙДЕНО {len(results)} ИГРОКОВ</b>\n\n"
        f"🔍 <b>Поиск:</b> {search_term}\n\n"
    )
    
    for i, (user_id, user_data) in enumerate(results[:10], 1):
        if user_data.get('username'):
            name = f"@{user_data['username']}"
        elif user_data.get('display_name'):
            name = user_data['display_name'][:15]
            if len(user_data['display_name']) > 15:
                name += "..."
        else:
            name = f"ID:{user_id[:6]}"
        
        level = db.get_user_level(user_data['total_farmed'])
        
        message += (
            f"{i}. <b>{name}</b>\n"
            f"   🆔 ID: <code>{user_id}</code>\n"
            f"   💰 {user_data['coins']} коинов | {level['name']}\n"
        )
        
        if i < min(len(results), 10):
            message += "\n"
    
    if len(results) > 10:
        message += f"\n📄 ... и еще {len(results) - 10} игроков\n"
    
    message += "\n🔍════════════════════════════════════🔍"
    
    await update.message.reply_text(message, parse_mode='HTML')

def is_admin(user_id):
    return user_id == ADMIN_ID

async def give(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только для админа!")
        return
    
    if not update.message.reply_to_message or not context.args:
        message = (
            "💰════════════════════════════════════💰\n\n"
            f"🎁 <b>ВЫДАЧА КОИНОВ</b>\n\n"
            f"📝 <b>Использование:</b>\n"
            f"1. Ответьте на сообщение игрока\n"
            f"2. Напишите: <code>/give [сумма]</code>\n\n"
            f"📋 <b>Пример:</b>\n"
            f"<code>/give 100</code>\n\n"
            "💰════════════════════════════════════💰"
        )
        await update.message.reply_text(message, parse_mode='HTML')
        return
    
    try:
        amount = int(context.args[0])
        target_user = update.message.reply_to_message.from_user
        new_balance = db.add_coins(target_user.id, amount, from_farm=False, from_admin=True)
        
        message = (
            "✅════════════════════════════════════✅\n\n"
            f"🎁 <b>КОИНЫ ВЫДАНЫ!</b>\n\n"
            f"👤 <b>Игроку:</b> {target_user.first_name}\n"
            f"💰 <b>Сумма:</b> {amount} коинов\n"
            f"💳 <b>Новый баланс:</b> {new_balance} коинов\n\n"
            "✅════════════════════════════════════✅"
        )
        
        await update.message.reply_text(message, parse_mode='HTML')
        
    except:
        await update.message.reply_text("❌ Ошибка! Укажите число")

async def announce(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только для админа!")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Формат: /announce [текст]")
        return
    
    text = " ".join(context.args)
    message = (
        "📢════════════════════════════════════📢\n\n"
        f"📣 <b>ОБЪЯВЛЕНИЕ ОТ АДМИНА</b>\n\n"
        f"{text}\n\n"
        "📢════════════════════════════════════📢"
    )
    await update.message.reply_text(message, parse_mode='HTML')

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только для админа!")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Формат: /broadcast [текст]")
        return
    
    text = " ".join(context.args)
    message = (
        "📨════════════════════════════════════📨\n\n"
        f"📣 <b>СООБЩЕНИЕ ОТ АДМИНА</b>\n\n"
        f"{text}\n\n"
        "📨════════════════════════════════════📨"
    )
    
    sent = 0
    failed = 0
    
    for user_id in db.data:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode='HTML'
            )
            sent += 1
        except:
            failed += 1
    
    result = (
        "📊════════════════════════════════════📊\n\n"
        f"📨 <b>РАССЫЛКА ЗАВЕРШЕНА</b>\n\n"
        f"✅ <b>Отправлено:</b> {sent} игрокам\n"
        f"❌ <b>Не отправлено:</b> {failed} игрокам\n\n"
        "📊════════════════════════════════════📊"
    )
    
    await update.message.reply_text(result, parse_mode='HTML')

async def compensation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только для админа!")
        return
    
    total = db.add_compensation_to_all(COMPENSATION_AMOUNT)
    
    message = (
        "🎁════════════════════════════════════🎁\n\n"
        f"💰 <b>КОМПЕНСАЦИЯ ВЫДАНА!</b>\n\n"
        f"👥 <b>Игроков:</b> {total}\n"
        f"🎁 <b>Каждому:</b> {COMPENSATION_AMOUNT} коинов\n"
        f"💰 <b>Всего выдано:</b> {total * COMPENSATION_AMOUNT} коинов\n\n"
        "🎁════════════════════════════════════🎁"
    )
    
    await update.message.reply_text(message, parse_mode='HTML')

async def removeitem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только для админа!")
        return
    
    if len(context.args) != 2:
        message = (
            "🗑️════════════════════════════════════🗑️\n\n"
            f"❌ <b>УДАЛЕНИЕ ПРЕДМЕТА</b>\n\n"
            f"📝 <b>Использование:</b>\n"
            f"<code>/removeitem [ID_игрока] [номер_предмета]</code>\n\n"
            f"📋 <b>Пример:</b>\n"
            f"<code>/removeitem 6443845944 0</code>\n\n"
            "🗑️════════════════════════════════════🗑️"
        )
        await update.message.reply_text(message, parse_mode='HTML')
        return
    
    try:
        user_id = int(context.args[0])
        item_index = int(context.args[1])
        
        success, item = db.remove_item(user_id, item_index)
        
        if success:
            user_data = db.get_user(user_id)
            user_name = f"@{user_data.get('username', '')}" if user_data.get('username') else f"ID:{user_id}"
            
            message = (
                "✅════════════════════════════════════✅\n\n"
                f"🗑️ <b>ПРЕДМЕТ УДАЛЕН!</b>\n\n"
                f"🎁 <b>Предмет:</b> {item['name']}\n"
                f"👤 <b>От игрока:</b> {user_name}\n"
                f"💰 <b>Стоимость:</b> {item['price']} коинов\n\n"
                "✅════════════════════════════════════✅"
            )
            
            await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text("❌ Не удалось удалить предмет")
            
    except (ValueError, IndexError):
        await update.message.reply_text("❌ Ошибка! Проверьте ID и номер предмета")

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только для админа!")
        return
    
    total_players = len(db.data)
    total_coins = sum(user['coins'] for user in db.data.values())
    total_items = sum(len(user['inventory']) for user in db.data.values())
    
    message = (
        "👑════════════════════════════════════👑\n\n"
        f"⚙️ <b>АДМИН ПАНЕЛЬ</b>\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"👥 Игроков: {total_players}\n"
        f"💰 Всего коинов: {total_coins}\n"
        f"📦 Предметов: {total_items}\n\n"
    )
    
    keyboard = [
        [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton("💰 Компенсация", callback_data="comp")],
        [InlineKeyboardButton("📢 Рассылка", callback_data="broadcast")],
        [InlineKeyboardButton("❌ Закрыть", callback_data="close")]
    ]
    
    await update.message.reply_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def backup_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только для админа!")
        return
    
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f"kme_data.json.backup_{timestamp}"
        
        with open('kme_data.json', 'r', encoding='utf-8') as src:
            with open(backup_file, 'w', encoding='utf-8') as dst:
                dst.write(src.read())
        
        message = (
            "💾════════════════════════════════════💾\n\n"
            f"✅ <b>РЕЗЕРВНАЯ КОПИЯ СОЗДАНА!</b>\n\n"
            f"📁 <b>Файл:</b> {backup_file}\n"
            f"👥 <b>Пользователей:</b> {len(db.data)}\n"
            f"📊 <b>Размер:</b> {os.path.getsize(backup_file)} байт\n\n"
            "💾════════════════════════════════════💾"
        )
        
        await update.message.reply_text(message, parse_mode='HTML')
        
        with open(backup_file, 'rb') as f:
            await update.message.reply_document(
                document=f,
                filename=backup_file
            )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка создания бэкапа: {e}")

async def restore_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только для админа!")
        return
    
    if not update.message.document:
        message = (
            "🔄════════════════════════════════════🔄\n\n"
            f"📥 <b>ВОССТАНОВЛЕНИЕ БАЗЫ ДАННЫХ</b>\n\n"
            f"📝 <b>Использование:</b>\n"
            f"1. Отправьте файл kme_data.json\n"
            f"2. Напишите команду: /restore_db\n\n"
            f"⚠️ <b>Внимание:</b> Старая база будет сохранена как backup\n"
            "🔄════════════════════════════════════🔄"
        )
        await update.message.reply_text(message, parse_mode='HTML')
        return
    
    try:
        file = await update.message.document.get_file()
        
        if os.path.exists('kme_data.json'):
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            old_backup = f"kme_data.json.old_{timestamp}"
            os.rename('kme_data.json', old_backup)
        
        await file.download_to_drive('kme_data.json')
        
        global db
        db = Database()
        
        message = (
            "✅════════════════════════════════════✅\n\n"
            f"🔄 <b>БАЗА ДАННЫХ ВОССТАНОВЛЕНА!</b>\n\n"
            f"👥 <b>Пользователей загружено:</b> {len(db.data)}\n"
            f"💾 <b>Старая база сохранена:</b> {old_backup}\n\n"
        )
        
        top_users = sorted(db.data.items(), key=lambda x: x[1]['coins'], reverse=True)[:3]
        for i, (user_id, user_data) in enumerate(top_users, 1):
            name = f"@{user_data.get('username', '')}" if user_data.get('username') else f"ID:{user_id[:6]}"
            message += f"{i}. {name} - {user_data['coins']} коинов\n"
        
        message += "\n✅════════════════════════════════════✅"
        
        await update.message.reply_text(message, parse_mode='HTML')
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка восстановления: {e}")

async def db_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только для админа!")
        return
    
    import glob
    db_files = glob.glob("kme_data.json*")
    
    message = (
        "📊════════════════════════════════════📊\n\n"
        f"🗃️ <b>ИНФОРМАЦИЯ О БАЗЕ ДАННЫХ</b>\n\n"
    )
    
    for db_file in sorted(db_files):
        if os.path.exists(db_file):
            size = os.path.getsize(db_file)
            modified = datetime.fromtimestamp(os.path.getmtime(db_file)).strftime('%d.%m.%Y %H:%M')
            
            if db_file == "kme_data.json":
                message += f"📁 <b>Основная база:</b> {db_file}\n"
                message += f"   📏 Размер: {size} байт\n"
                message += f"   ⏰ Изменена: {modified}\n"
                message += f"   👥 Пользователей: {len(db.data)}\n\n"
            else:
                message += f"📁 Резервная: {db_file}\n"
                message += f"   📏 Размер: {size} байт\n"
                message += f"   ⏰ Изменена: {modified}\n\n"
    
    message += (
        f"💡 <b>Команды:</b>\n"
        f"• /backup_db - Создать резервную копию\n"
        f"• /restore_db - Восстановить из файла\n"
        f"• /db_info - Эта информация\n\n"
        "📊════════════════════════════════════📊"
    )
    
    await update.message.reply_text(message, parse_mode='HTML')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "close":
        await query.delete_message()
        return
    
    if query.data.startswith("view_"):
        await query.edit_message_text("✅ Предмет уже обменян")
    
    elif query.data.startswith("exchange_"):
        item_index = int(query.data.split("_")[1])
        user = query.from_user
        db.update_user(user.id)
        success, item = db.exchange_item(user.id, item_index)
        
        if success:
            message = (
                "🔄════════════════════════════════════🔄\n\n"
                f"✅ <b>ПРЕДМЕТ ОТПРАВЛЕН НА ОБМЕН!</b>\n\n"
                f"🎁 <b>Предмет:</b> {item['name']}\n"
                f"💰 <b>Стоимость:</b> {item['price']} коинов\n\n"
                f"📨 Админ получил уведомление\n"
                f"⏳ Скоро свяжемся для выполнения\n\n"
                "🔄════════════════════════════════════🔄"
            )
            
            await query.edit_message_text(message, parse_mode='HTML')
            await send_exchange_notification(context, user.id, item)
            
        else:
            await query.edit_message_text("❌ Ошибка обмена")
    
    elif query.data == "stats":
        total_players = len(db.data)
        total_coins = sum(user['coins'] for user in db.data.values())
        total_items = sum(len(user['inventory']) for user in db.data.values())
        total_farmed = sum(user['total_farmed'] for user in db.data.values())
        
        message = (
            "📊════════════════════════════════════📊\n\n"
            f"📈 <b>ПОДРОБНАЯ СТАТИСТИКА</b>\n\n"
            f"👥 <b>Игроков:</b> {total_players}\n"
            f"💰 <b>Всего коинов:</b> {total_coins}\n"
            f"🎯 <b>Всего заработано:</b> {total_farmed}\n"
            f"📦 <b>Предметов куплено:</b> {total_items}\n\n"
            "📊════════════════════════════════════📊"
        )
        
        await query.edit_message_text(message, parse_mode='HTML')
        
    elif query.data == "comp":
        await query.edit_message_text(
            "💰 Используйте команду:\n<code>/compensation</code>",
            parse_mode='HTML'
        )
    elif query.data == "broadcast":
        await query.edit_message_text(
            "📢 Используйте команду:\n<code>/broadcast [текст]</code>",
            parse_mode='HTML'
        )

def main():
    print("=" * 50)
    print("🤖 KMEbot запускается...")
    print(f"👥 Игроков: {len(db.data)}")
    print(f"🎮 Уровней: {len(LEVELS)}")
    print(f"💰 Фарм: 0-5 коинов, {FARM_COOLDOWN}ч КД")
    print(f"👑 Админ ID: {ADMIN_ID}")
    print("=" * 50)
    
    app = Application.builder().token(TOKEN).build()
    
    commands = [
        ("start", start),
        ("farm", farm),
        ("balance", balance),
        ("level", level),
        ("shop", shop),
        ("inventory", inventory),
        ("top", top),
        ("party", party),
        ("write", write),
        ("profile", profile),
        ("users", users),
        ("help", start),
    ]
    
    for cmd, handler in commands:
        app.add_handler(CommandHandler(cmd, handler))
    
    def create_buy_handler(item_id):
        async def handler(update, context):
            return await buy_item(update, context, item_id)
        return handler
    
    for item_id in SHOP_ITEMS.keys():
        app.add_handler(CommandHandler(f"buy_{item_id}", create_buy_handler(item_id)))
    
    admin_commands = [
        ("admin", admin),
        ("give", give),
        ("announce", announce),
        ("broadcast", bro

