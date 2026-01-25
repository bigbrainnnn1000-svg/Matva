import json
import os
import random
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler

# ⚠️ ПРОВЕРЬ ТОКЕН!
TOKEN = "8542959870:AAH7ECRyusZRDiULPWngvcjygQ9smi-cA3E"  # Или твой новый токен
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
        # Для Bothost используем абсолютный путь
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.filename = os.path.join(current_dir, filename)
        self.data = self.load_data()
        print(f"📁 База данных: {self.filename}")
        print(f"👥 Загружено игроков: {len(self.data)}")
    
    def load_data(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ Ошибка загрузки БД: {e}")
                return {}
        
        print("📝 Создаю новую базу данных...")
        return {}
    
    def save_data(self):
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            print("💾 База данных сохранена")
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
        self.save_data()
        return user['coins']
    
    def buy_item(self, user_id, item_id):
        user = self.get_user(user_id)
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
        self.save_data()
        return len(self.data)

db = Database()

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
async def send_exchange_notification(context, user_id, item):
    """Отправляет уведомление админу об обмене"""
    user_data = db.get_user(user_id)
    
    # Получаем информацию о пользователе
    user_name = f"@{user_data.get('username', '')}" if user_data.get('username') else f"ID:{user_id}"
    display_name = user_data.get('display_name', 'Неизвестно')
    
    # Формируем сообщение
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

# ========== КОМАНДЫ ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = db.get_user(user.id)
    if user.username:
        user_data['username'] = user.username
    if user.full_name:
        user_data['display_name'] = user.full_name
    db.save_data()
    
    await update.message.reply_text(
        f"👋 Привет, {user.first_name}!\n"
        f"💰 Баланс: {user_data['coins']} коинов\n"
        f"📊 Команды: /farm /balance /level /shop /help"
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

async def level(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = db.get_user(user.id)
    
    # Определяем уровень
    current_level = None
    for level in LEVELS:
        if level["min_coins"] <= user_data['total_farmed'] <= level["max_coins"]:
            current_level = level
            break
    
    if not current_level:
        current_level = LEVELS[-1]
    
    await update.message.reply_text(
        f"📊 УРОВЕНЬ\n"
        f"👤 {user.first_name}\n"
        f"🏆 {current_level['name']}\n"
        f"💰 Всего заработано: {user_data['total_farmed']}"
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
    """Команда поиска тимы - публикуется как объявление"""
    if not context.args:
        await update.message.reply_text("🎮 Формат: /party [ваш MMR]")
        return
    
    try:
        mmr = int(context.args[0])
        user = update.effective_user
        
        # Получаем username пользователя
        user_data = db.get_user(user.id)
        username = user_data.get('username', '')
        
        # Формируем красивое объявление
        announcement = (
            f"🎮 ОБЪЯВЛЕНИЕ О ПОИСКЕ ТИМЫ\n\n"
            f"👤 Игрок: {user.first_name}\n"
            f"📊 MMR: ~{mmr}\n"
        )
        
        if username:
            announcement += f"📱 Контакт: @{username}\n"
        
        announcement += f"🆔 ID: {user.id}\n\n"
        announcement += f"✅ Ищет тиму для игры в Dota 2!"
        
        # Отправляем объявление в тот же чат
        await update.message.reply_text(announcement)
        
        # Также отправляем подтверждение пользователю
        await context.bot.send_message(
            chat_id=user.id,
            text=f"✅ Ваша заявка на поиск тимы опубликована!\nMMR: {mmr}"
        )
        
    except ValueError:
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
            await context.bot.send_message(chat_id=user_id, text=text)
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

async def removeitem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаляет обменянный предмет (только для админа)"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только для админа!")
        return
    
    if len(context.args) != 2:
        await update.message.reply_text("❌ Формат: /removeitem [user_id] [item_index]")
        return
    
    try:
        user_id = int(context.args[0])
        item_index = int(context.args[1])
        
        success, item = db.remove_item(user_id, item_index)
        
        if success:
            user_data = db.get_user(user_id)
            user_name = f"@{user_data.get('username', '')}" if user_data.get('username') else f"ID:{user_id}"
            
            await update.message.reply_text(
                f"✅ Предмет удален!\n"
                f"🎁 {item['name']}\n"
                f"👤 От игрока: {user_name}"
            )
        else:
            await update.message.reply_text("❌ Не удалось удалить предмет")
            
    except (ValueError, IndexError):
        await update.message.reply_text("❌ Ошибка! Проверьте ID и индекс")

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
            # Обновляем сообщение
            await query.edit_message_text(f"🔄 {item['name']} отправлен на обмен!")
            
            # Отправляем уведомление админу
            await send_exchange_notification(context, user.id, item)
            
            # Отправляем подтверждение пользователю в ЛС
            try:
                await context.bot.send_message(
                    chat_id=user.id,
                    text=f"✅ Ваш предмет '{item['name']}' отправлен на обмен!\n"
                         f"С вами свяжется администратор для выполнения услуги."
                )
            except:
                pass  # Пользователь может заблокировать бота
            
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
        ("level", level),
        ("shop", shop),
        ("inventory", inventory),
        ("top", top),
        ("party", party),
        ("help", start),
    ]
    
    for cmd, handler in commands:
        app.add_handler(CommandHandler(cmd, handler))
    
    # Покупка предметов
    def create_buy_handler(item_id):
        async def handler(update, context):
            return await buy_item(update, context, item_id)
        return handler
    
    for item_id in SHOP_ITEMS.keys():
        app.add_handler(CommandHandler(f"buy_{item_id}", create_buy_handler(item_id)))
    
    # Админ команды
    admin_commands = [
        ("admin", admin),
        ("give", give),
        ("announce", announce),
        ("broadcast", broadcast),
        ("compensation", compensation),
        ("removeitem", removeitem),
    ]
    
    for cmd, handler in admin_commands:
        app.add_handler(CommandHandler(cmd, handler))
    
    # Кнопки
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("✅ Бот запущен!")
    print("📱 Напишите боту /start в Telegram")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Бот остановлен")
    except Exception as e:
        print(f"❌ Ошибка запуска: {e}")
        import traceback
        traceback.print_exc()
