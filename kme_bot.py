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

# Система уровней
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
        # Исправленный путь для Bothost
        self.filename = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
        self.data = self.load_data()
        print(f"📁 База данных: {self.filename}")
    
    def load_data(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def save_data(self):
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except:
            print("⚠️ Не удалось сохранить базу данных")
    
    def get_user(self, user_id):
        user_id = str(user_id)
        if user_id not in self.data:
            self.data[user_id] = {
                'coins': 0,
                'last_farm': None,
                'username': '',
                'display_name': '',
                'inventory': [],
                'total_farmed': 0,
                'farm_count': 0,
                'admin_gifted': 0
            }
            self.save_data()
        return self.data[user_id]
    
    def can_farm(self, user_id):
        user = self.get_user(user_id)
        if not user['last_farm']:
            return True, "✅ Можно фармить!"
        
        last = datetime.fromisoformat(user['last_farm'])
        now = datetime.now()
        if now - last >= timedelta(hours=FARM_COOLDOWN):
            return True, "✅ Можно фармить!"
        else:
            wait = (last + timedelta(hours=FARM_COOLDOWN)) - now
            return False, f"⏳ Ждите {wait.seconds//3600:02d}:{(wait.seconds%3600)//60:02d}"
    
    def add_coins(self, user_id, amount, from_farm=True, from_admin=False):
        user = self.get_user(user_id)
        user['coins'] += amount
        if from_farm:
            user['total_farmed'] += amount
            user['farm_count'] += 1
            user['last_farm'] = datetime.now().isoformat()
        if from_admin:
            user['admin_gifted'] += amount
        self.save_data()
        return user['coins']
    
    def buy_item(self, user_id, item_id):
        user = self.get_user(user_id)
        if item_id not in SHOP_ITEMS:
            return False, "❌ Такого товара нет!"
        
        item = SHOP_ITEMS[item_id]
        if user['coins'] < item['price']:
            return False, f"❌ Недостаточно коинов!"
        
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
        if item_index >= len(user['inventory']):
            return False, "❌ Такого предмета нет!"
        
        item = user['inventory'][item_index]
        if item.get('exchanged', False):
            return False, "❌ Уже обменян!"
        
        user['inventory'][item_index]['exchanged'] = True
        user['inventory'][item_index]['exchanged_at'] = datetime.now().isoformat()
        self.save_data()
        return True, item
    
    def add_compensation_to_all(self, amount):
        for user_id in self.data:
            user = self.get_user(user_id)
            user['coins'] += amount
        self.save_data()
        return len(self.data)

db = Database()

# ========== КОМАНДЫ ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = db.get_user(user.id)
    if user.username:
        user_data['username'] = user.username
    db.save_data()
    
    await update.message.reply_text(
        f"👋 Привет, {user.first_name}!\n"
        f"💰 Баланс: {user_data['coins']} коинов\n"
        f"📊 Команды: /farm /balance /shop /help"
    )

async def farm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    can_farm, msg = db.can_farm(user.id)
    
    if not can_farm:
        await update.message.reply_text(msg)
        return
    
    coins = random.randint(0, 5)
    new_balance = db.add_coins(user.id, coins)
    
    await update.message.reply_text(
        f"💰 Фарм: {coins} коинов\n"
        f"🏦 Баланс: {new_balance}\n"
        f"⏳ Следующий через {FARM_COOLDOWN}ч"
    )

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = db.get_user(user.id)
    
    await update.message.reply_text(
        f"👤 {user.first_name}\n"
        f"💰 Коинсы: {user_data['coins']}\n"
        f"🏆 Всего: {user_data['total_farmed']}\n"
        f"📈 Фармов: {user_data['farm_count']}"
    )

async def shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "🛍️ МАГАЗИН:\n\n"
    for item_id, item in SHOP_ITEMS.items():
        text += f"{item_id}. {item['name']} - {item['price']} коинов\n"
        text += f"   /buy_{item_id}\n\n"
    
    user_data = db.get_user(update.effective_user.id)
    text += f"💰 Ваш баланс: {user_data['coins']} коинов"
    await update.message.reply_text(text)

async def buy_item(update: Update, context: ContextTypes.DEFAULT_TYPE, item_id: int):
    user = update.effective_user
    success, result = db.buy_item(user.id, item_id)
    await update.message.reply_text(result)

async def inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = db.get_user(user.id)
    
    if not user_data['inventory']:
        await update.message.reply_text("📦 Инвентарь пуст")
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
    
    await update.message.reply_text(
        "📦 ИНВЕНТАРЬ:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not db.data:
        await update.message.reply_text("📭 Нет игроков")
        return
    
    top_users = sorted(db.data.items(), key=lambda x: x[1]['total_farmed'], reverse=True)[:5]
    text = "🏆 ТОП 5:\n\n"
    
    for i, (user_id, user_data) in enumerate(top_users, 1):
        name = f"@{user_data.get('username', '')}" if user_data.get('username') else f"ID:{user_id[:6]}"
        text += f"{i}. {name} - {user_data['total_farmed']} коинов\n"
    
    await update.message.reply_text(text)

async def party(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("🎮 Формат: /party [ваш MMR]")
        return
    
    try:
        mmr = int(context.args[0])
        user = update.effective_user
        
        # Простая имитация поиска
        await update.message.reply_text(
            f"🎮 Поиск тимы Dota 2\n"
            f"👤 Игрок: {user.first_name}\n"
            f"📊 MMR: ~{mmr}\n\n"
            f"✅ Заявка отправлена!"
        )
    except:
        await update.message.reply_text("❌ Укажите число MMR")

# ========== АДМИН КОМАНДЫ ==========
def is_admin(user_id):
    return user_id == ADMIN_ID

async def give(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только для админа!")
        return
    
    if not update.message.reply_to_message or not context.args:
        await update.message.reply_text("❌ Ответьте на сообщение: /give [сумма]")
        return
    
    try:
        amount = int(context.args[0])
        target_user = update.message.reply_to_message.from_user
        new_balance = db.add_coins(target_user.id, amount, from_farm=False, from_admin=True)
        
        await update.message.reply_text(
            f"✅ Выдано {amount} коинов\n"
            f"👤 Игроку: {target_user.first_name}\n"
            f"💰 Новый баланс: {new_balance}"
        )
    except:
        await update.message.reply_text("❌ Ошибка!")

async def announce(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только для админа!")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Формат: /announce [текст]")
        return
    
    text = " ".join(context.args)
    await update.message.reply_text(f"📢 ОБЪЯВЛЕНИЕ:\n\n{text}")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только для админа!")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Формат: /broadcast [текст]")
        return
    
    text = " ".join(context.args)
    sent = 0
    
    for user_id in db.data:
        try:
            # В реальном боте здесь отправка сообщения
            sent += 1
        except:
            pass
    
    await update.message.reply_text(f"📢 Разослано {sent} игрокам")

async def compensation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только для админа!")
        return
    
    total = db.add_compensation_to_all(COMPENSATION_AMOUNT)
    
    await update.message.reply_text(
        f"💰 Компенсация выдана!\n"
        f"👥 Игроков: {total}\n"
        f"🎁 Каждому: {COMPENSATION_AMOUNT} коинов"
    )

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только для админа!")
        return
    
    keyboard = [
        [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton("💰 Компенсация", callback_data="comp")],
        [InlineKeyboardButton("📢 Рассылка", callback_data="broadcast")],
        [InlineKeyboardButton("❌ Закрыть", callback_data="close")]
    ]
    
    await update.message.reply_text(
        "👑 АДМИН ПАНЕЛЬ:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ========== ОБРАБОТЧИКИ КНОПОК ==========
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "close":
        await query.delete_message()
        return
    
    # Обработка инвентаря
    if query.data.startswith("view_"):
        await query.edit_message_text("✅ Предмет уже обменян")
    elif query.data.startswith("exchange_"):
        item_index = int(query.data.split("_")[1])
        user = query.from_user
        success, item = db.exchange_item(user.id, item_index)
        
        if success:
            await query.edit_message_text(f"🔄 {item['name']} отправлен на обмен!")
        else:
            await query.edit_message_text("❌ Ошибка обмена")
    
    # Обработка админ панели
    elif query.data == "stats":
        total_players = len(db.data)
        total_coins = sum(user['coins'] for user in db.data.values())
        await query.edit_message_text(
            f"📊 СТАТИСТИКА:\n"
            f"👥 Игроков: {total_players}\n"
            f"💰 Всего коинов: {total_coins}"
        )
    elif query.data == "comp":
        await query.edit_message_text("💰 Используйте /compensation")
    elif query.data == "broadcast":
        await query.edit_message_text("📢 Используйте /broadcast")

# ========== ЗАПУСК БОТА ==========
def main():
    print("=" * 50)
    print("🤖 KMEbot запускается...")
    print(f"👥 Игроков: {len(db.data)}")
    print(f"🎮 Уровней: {len(LEVELS)}")
    print(f"💰 Фарм: 0-5 коинов, {FARM_COOLDOWN}ч КД")
    print(f"👑 Админ ID: {ADMIN_ID}")
    print("=" * 50)
    
    app = Application.builder().token(TOKEN).build()
    
    # Основные команды
    commands = [
        ("start", start),
        ("farm", farm),
        ("balance", balance),
        ("shop", shop),
        ("inventory", inventory),
        ("top", top),
        ("party", party),
        ("help", start),  # Та же справка что и start
    ]
    
    for cmd, handler in commands:
        app.add_handler(CommandHandler(cmd, handler))
    
    # Покупка предметов
    for item_id in SHOP_ITEMS.keys():
        async def buy_handler(update, context, item_id=item_id):
            return await buy_item(update, context, item_id)
        app.add_handler(CommandHandler(f"buy_{item_id}", buy_handler))
    
    # Админ команды
    admin_commands = [
        ("admin", admin),
        ("give", give),
        ("announce", announce),
        ("broadcast", broadcast),
        ("compensation", compensation),
    ]
    
    for cmd, handler in admin_commands:
        app.add_handler(CommandHandler(cmd, handler))
    
    # Кнопки
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("✅ Бот запущен!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Бот остановлен")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
