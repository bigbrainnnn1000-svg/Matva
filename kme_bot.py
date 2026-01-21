import json
import os
import random
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

TOKEN = "8542959870:AAHzEChit6gsHlLzxNEg-090lNpBZwItU2E"
ADMIN_ID = 6443845944
ADMIN_USERNAME = "@Matvatok"
FARM_COOLDOWN = 4
STEAL_COOLDOWN = 10  # 10 минут для кражи
STEAL_AMOUNT = 5     # 5 коинов за кражу

SHOP_ITEMS = {
    1: {"name": "🔔 Сигна от Kme_Dota", "price": 50, "description": "Сигна от Kme_Dota", "exchangeable": True},
    2: {"name": "👥 Сигна от Лсной братвы", "price": 100, "description": "Сигна от Лсной братвы", "exchangeable": True},
    3: {"name": "👑 Модер в чате", "price": 150, "description": "Стать модератором в чате", "exchangeable": True},
    4: {"name": "🎮 Модер на твиче", "price": 200, "description": "Стать модератором на твиче", "exchangeable": True},
    5: {"name": "🎵 Трек про тебя", "price": 300, "description": "Заказать трек про себя", "exchangeable": True},
    6: {"name": "⚔️ Dota+", "price": 400, "description": "Получить Dota+ на месяц", "exchangeable": True}
}

LEVELS = [
    {"name": "👶 Рекрут", "max_coins": 100, "emoji": "👶"},
    {"name": "🛡️ Страж", "max_coins": 200, "emoji": "🛡️"},
    {"name": "⚔️ Рыцарь", "max_coins": 300, "emoji": "⚔️"},
    {"name": "👑 Титян", "max_coins": 400, "emoji": "👑"},
    {"name": "🔥 БОГ", "max_coins": float('inf'), "emoji": "🔥"}
]

def get_level_info(total_coins):
    for level in LEVELS:
        if total_coins <= level["max_coins"]:
            return level
    return LEVELS[-1]

def calculate_level_progress(total_coins):
    current_level = None
    next_level = None
    
    for i, level in enumerate(LEVELS):
        if total_coins <= level["max_coins"]:
            current_level = level
            if i < len(LEVELS) - 1:
                next_level = LEVELS[i + 1]
            break
    
    if not current_level:
        current_level = LEVELS[-1]
    
    if not next_level:
        return current_level, None, 100
    
    prev_max = 0
    if LEVELS.index(current_level) > 0:
        prev_max = LEVELS[LEVELS.index(current_level) - 1]["max_coins"]
    
    progress = ((total_coins - prev_max) / (current_level["max_coins"] - prev_max)) * 100
    return current_level, next_level, min(100, int(progress))

class Database:
    def __init__(self, filename="kme_data.json"):
        self.filename = filename
        self.data = self.load_data()
        print(f"📊 Загружено пользователей: {len(self.data)}")
    
    def load_data(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ Ошибка загрузки данных: {e}")
                backup_name = f"{self.filename}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                os.rename(self.filename, backup_name)
                print(f"📁 Создан бэкап: {backup_name}")
                return {}
        else:
            print("📁 Файл данных не найден, создаю новый")
            return {}
    
    def save_data(self):
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"❌ Ошибка сохранения: {e}")
    
    def get_user(self, user_id):
        user_id = str(user_id)
        if user_id not in self.data:
            self.data[user_id] = {
                'coins': 0,
                'last_farm': None,
                'last_steal': None,
                'username': '',
                'display_name': '',
                'inventory': [],
                'total_farmed': 0,
                'farm_count': 0,
                'steal_count': 0,
                'stolen_coins': 0,
                'lost_coins': 0,
                'level': '👶 Рекрут'
            }
            self.save_data()
        
        user = self.data[user_id]
        level_info = get_level_info(user['total_farmed'])
        user['level'] = level_info['name']
        
        return user
    
    def can_farm(self, user_id):
        user = self.get_user(user_id)
        if not user['last_farm']:
            return True, "✅ Можно фармить!"
        
        last = datetime.fromisoformat(user['last_farm'])
        now = datetime.now()
        cooldown = timedelta(hours=FARM_COOLDOWN)
        
        if now - last >= cooldown:
            return True, "✅ Можно фармить!"
        else:
            wait = cooldown - (now - last)
            hours = int(wait.total_seconds() // 3600)
            minutes = int((wait.total_seconds() % 3600) // 60)
            seconds = int(wait.total_seconds() % 60)
            return False, f"⏳ До фарма: {hours:02d}:{minutes:02d}:{seconds:02d}"
    
    def can_steal(self, user_id):
        user = self.get_user(user_id)
        if not user['last_steal']:
            return True, "✅ Можно пытаться украсть!"
        
        last = datetime.fromisoformat(user['last_steal'])
        now = datetime.now()
        cooldown = timedelta(minutes=STEAL_COOLDOWN)
        
        if now - last >= cooldown:
            return True, "✅ Можно пытаться украсть!"
        else:
            wait = cooldown - (now - last)
            minutes = int(wait.total_seconds() // 60)
            seconds = int(wait.total_seconds() % 60)
            return False, f"⏳ До кражи: {minutes:02d}:{seconds:02d}"
    
    def add_coins(self, user_id, amount, from_farm=True):
        user = self.get_user(user_id)
        user['coins'] += amount
        if from_farm:
            user['total_farmed'] += amount
            user['farm_count'] += 1
            user['last_farm'] = datetime.now().isoformat()
        
        level_info = get_level_info(user['total_farmed'])
        user['level'] = level_info['name']
        
        self.save_data()
        return user['coins'], user['level']
    
    def steal_coins(self, thief_id, victim_id):
        thief = self.get_user(thief_id)
        victim = self.get_user(victim_id)
        
        # Проверяем что у жертвы есть коины
        if victim['coins'] < STEAL_AMOUNT:
            return False, "У жертвы недостаточно коинов для кражи!"
        
        # 50/50 шанс
        if random.random() < 0.5:  # Успешная кража
            # Забираем у жертвы
            victim['coins'] -= STEAL_AMOUNT
            victim['lost_coins'] += STEAL_AMOUNT
            
            # Отдаем вору
            thief['coins'] += STEAL_AMOUNT
            thief['stolen_coins'] += STEAL_AMOUNT
            thief['steal_count'] += 1
            
            # Обновляем время кражи
            thief['last_steal'] = datetime.now().isoformat()
            
            self.save_data()
            return True, f"✅ Успешная кража! Украдено {STEAL_AMOUNT} коинов."
        else:  # Неудачная кража
            thief['last_steal'] = datetime.now().isoformat()
            self.save_data()
            return False, "❌ Неудачная попытка кражи! Жертва заметила."
    
    def buy_item(self, user_id, item_id):
        user = self.get_user(user_id)
        
        if item_id not in SHOP_ITEMS:
            return False, "❌ Такого товара нет!"
        
        item = SHOP_ITEMS[item_id]
        
        if user['coins'] < item['price']:
            return False, f"❌ Недостаточно коинов! Нужно {item['price']}, а у вас {user['coins']}"
        
        user['coins'] -= item['price']
        user['inventory'].append({
            'id': item_id,
            'name': item['name'],
            'price': item['price'],
            'bought_at': datetime.now().isoformat(),
            'exchangeable': item.get('exchangeable', True),
            'exchanged': False
        })
        self.save_data()
        return True, f"✅ Куплено: {item['name']} за {item['price']} коинов"
    
    def exchange_item(self, user_id, item_index):
        user = self.get_user(user_id)
        
        if item_index < 0 or item_index >= len(user['inventory']):
            return False, "❌ Такого предмета нет в инвентаре!"
        
        item = user['inventory'][item_index]
        
        if not item.get('exchangeable', True):
            return False, "❌ Этот предмет нельзя обменять!"
        
        if item.get('exchanged', False):
            return False, "❌ Этот предмет уже был обменян!"
        
        # Помечаем как обменянный
        user['inventory'][item_index]['exchanged'] = True
        user['inventory'][item_index]['exchanged_at'] = datetime.now().isoformat()
        self.save_data()
        
        return True, item

db = Database()

# ========== ПАНЕЛЬ АДМИНА ==========
def is_admin(user_id):
    return user_id == ADMIN_ID

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ У вас нет доступа к админ-панели!")
        return
    
    keyboard = [
        [InlineKeyboardButton("💰 Выдать коины", callback_data="admin_give_coins")],
        [InlineKeyboardButton("📊 Статистика бота", callback_data="admin_stats")],
        [InlineKeyboardButton("👥 Поиск игрока", callback_data="admin_find_user")],
        [InlineKeyboardButton("🔄 Сбросить КД игрока", callback_data="admin_reset_cd")],
        [InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton("❌ Закрыть панель", callback_data="admin_close")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "👑 ПАНЕЛЬ АДМИНИСТРАТОРА KMEbot\n\n"
        "Выберите действие:",
        reply_markup=reply_markup
    )

async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ У вас нет доступа!")
        return
    
    data = query.data
    
    if data == "admin_give_coins":
        await query.edit_message_text(
            "💰 ВЫДАЧА КОИНОВ\n\n"
            "Формат: /give @username количество\n"
            "Пример: /give @Matvatok 100\n\n"
            "Или: /give user_id количество\n"
            "Пример: /give 123456789 100"
        )
    
    elif data == "admin_stats":
        total_players = len(db.data)
        total_coins = sum(user.get('coins', 0) for user in db.data.values())
        total_farmed = sum(user.get('total_farmed', 0) for user in db.data.values())
        
        await query.edit_message_text(
            f"📊 СТАТИСТИКА БОТА\n\n"
            f"👥 Игроков: {total_players}\n"
            f"💰 Всего коинов: {total_coins}\n"
            f"🏆 Всего заработано: {total_farmed}\n"
            f"🎮 Всего фармов: {sum(user.get('farm_count', 0) for user in db.data.values())}\n"
            f"🛍️ Всего покупок: {sum(len(user.get('inventory', [])) for user in db.data.values())}"
        )
    
    elif data == "admin_find_user":
        await query.edit_message_text(
            "👥 ПОИСК ИГРОКА\n\n"
            "Формат: /find @username\n"
            "Или: /find user_id\n\n"
            "Примеры:\n"
            "/find @Matvatok\n"
            "/find 123456789"
        )
    
    elif data == "admin_reset_cd":
        await query.edit_message_text(
            "🔄 СБРОС КД ИГРОКА\n\n"
            "Формат: /resetcd @username\n"
            "Или: /resetcd user_id\n\n"
            "Сбросит время фарма и кражи."
        )
    
    elif data == "admin_broadcast":
        await query.edit_message_text(
            "📢 РАССЫЛКА\n\n"
            "Формат: /broadcast текст_сообщения\n\n"
            "Пример: /broadcast Привет всем! Новая функция!"
        )
    
    elif data == "admin_close":
        await query.delete_message()

# ========== АДМИН КОМАНДЫ ==========
async def give_coins_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ У вас нет доступа!")
        return
    
    if len(context.args) != 2:
        await update.message.reply_text(
            "❌ Неправильный формат!\n"
            "✅ Используйте: /give @username количество\n"
            "Пример: /give @Matvatok 100"
        )
        return
    
    target = context.args[0]
    try:
        amount = int(context.args[1])
        if amount <= 0:
            await update.message.reply_text("❌ Количество должно быть положительным!")
            return
    except:
        await update.message.reply_text("❌ Неправильное количество коинов!")
        return
    
    # Поиск пользователя
    target_user_id = None
    target_username = ""
    
    # Если это user_id
    if target.isdigit():
        target_user_id = target
    else:
        # Ищем по username (без @)
        username = target.lstrip('@')
        for user_id, user_data in db.data.items():
            if user_data.get('username', '').lower() == username.lower():
                target_user_id = user_id
                target_username = user_data.get('username', '')
                break
    
    if not target_user_id or target_user_id not in db.data:
        await update.message.reply_text("❌ Пользователь не найден!")
        return
    
    # Выдаем коины
    new_balance, level = db.add_coins(target_user_id, amount, from_farm=False)
    
    target_name = target_username or target_user_id
    await update.message.reply_text(
        f"✅ Успешно!\n"
        f"💰 Выдано {amount} коинов пользователю {target_name}\n"
        f"🏦 Новый баланс: {new_balance}\n"
        f"📊 Уровень: {level}"
    )

async def find_user_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ У вас нет доступа!")
        return
    
    if not context.args:
        await update.message.reply_text(
            "❌ Не указан пользователь!\n"
            "✅ Используйте: /find @username\n"
            "Или: /find user_id"
        )
        return
    
    target = context.args[0]
    
    # Поиск пользователя
    found_users = []
    
    if target.isdigit():  # Поиск по user_id
        if target in db.data:
            user_data = db.data[target]
            found_users.append((target, user_data))
    else:  # Поиск по username
        username = target.lstrip('@').lower()
        for user_id, user_data in db.data.items():
            if username in user_data.get('username', '').lower():
                found_users.append((user_id, user_data))
    
    if not found_users:
        await update.message.reply_text("❌ Пользователь не найден!")
        return
    
    # Формируем информацию о найденных пользователях
    result = "👥 НАЙДЕННЫЕ ПОЛЬЗОВАТЕЛИ:\n\n"
    
    for user_id, user_data in found_users[:5]:  # Ограничиваем 5 результатами
        username = user_data.get('username', 'Нет username')
        display_name = user_data.get('display_name', 'Нет имени')
        coins = user_data.get('coins', 0)
        total_farmed = user_data.get('total_farmed', 0)
        level = user_data.get('level', '👶 Рекрут')
        
        result += f"ID: {user_id}\n"
        result += f"Username: @{username if username != 'Нет username' else 'нет'}\n"
        result += f"Имя: {display_name}\n"
        result += f"💰 Коины: {coins}\n"
        result += f"🏆 Всего: {total_farmed}\n"
        result += f"📊 Уровень: {level}\n"
        result += "─" * 20 + "\n"
    
    await update.message.reply_text(result)

async def reset_cd_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ У вас нет доступа!")
        return
    
    if not context.args:
        await update.message.reply_text(
            "❌ Не указан пользователь!\n"
            "✅ Используйте: /resetcd @username\n"
            "Или: /resetcd user_id"
        )
        return
    
    target = context.args[0]
    
    # Поиск пользователя
    target_user_id = None
    
    if target.isdigit():
        if target in db.data:
            target_user_id = target
    else:
        username = target.lstrip('@').lower()
        for user_id, user_data in db.data.items():
            if user_data.get('username', '').lower() == username:
                target_user_id = user_id
                break
    
    if not target_user_id:
        await update.message.reply_text("❌ Пользователь не найден!")
        return
    
    # Сбрасываем КД
    db.data[target_user_id]['last_farm'] = None
    db.data[target_user_id]['last_steal'] = None
    db.save_data()
    
    await update.message.reply_text(f"✅ КД сброшено для пользователя {target}")

# ========== ОСНОВНЫЕ КОМАНДЫ ==========
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = db.get_user(user.id)
    
    # Сохраняем информацию о пользователе
    if user.username:
        db.data[str(user.id)]['username'] = user.username
    if user.full_name:
        db.data[str(user.id)]['display_name'] = user.full_name
    db.save_data()
    
    current_level, next_level, progress = calculate_level_progress(user_data['total_farmed'])
    level_text = f"{current_level['emoji']} {current_level['name']}"
    
    if next_level:
        level_text += f"\n📈 Прогресс: {progress}% до {next_level['emoji']} {next_level['name']}"
    else:
        level_text += "\n🎉 Максимальный уровень достигнут!"
    
    text = f"""
🎮 Добро пожаловать в KMEbot!

👤 Игрок: {user.first_name}
{level_text}
💰 Баланс: {user_data['coins']} KMEкоинов
📊 Фармов: {user_data['farm_count']}
🏆 Всего заработано: {user_data['total_farmed']}

📋 Основные команды:
/farm - получить коины (раз в {FARM_COOLDOWN} часа)
/steal - попытаться украсть 5 коинов (раз в {STEAL_COOLDOWN} мин)
/balance - проверить баланс и уровень
/top - топ игроков (5 лучших)
/shop - магазин товаров
/inventory - ваши покупки
/help - помощь
/level - информация о системе уровней

🎲 Система фарма:
• Базово: 1-5 коинов
• 🎉 УДАЧА (+2 коина): 10%
• 😕 НЕУДАЧА (-1 или -2 коина): 8%
• 👍 Старый бонус (+1): 2%

🎯 НОВАЯ ФУНКЦИЯ:
• /steal - попытка украсть 5 коинов у другого игрока
• Шанс успеха: 50/50
• КД: {STEAL_COOLDOWN} минут
    """
    await update.message.reply_text(text)

async def farm_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    can_farm, msg = db.can_farm(user_id)
    
    if not can_farm:
        await update.message.reply_text(msg)
        return
    
    coins = random.randint(1, 5)
    bonus_msg = ""
    emoji = "💰"
    
    chance = random.random()
    
    if chance < 0.10:
        bonus = 2
        coins += bonus
        bonus_msg = f"\n🎉 УДАЧА! +{bonus} дополнительных коина!"
        emoji = "🎉"
    elif chance < 0.18:
        penalty = random.choice([-1, -2])
        original_coins = coins
        coins = max(0, coins + penalty)
        if penalty == -1:
            bonus_msg = f"\n😕 НЕУДАЧА... -1 коин ({original_coins} → {coins})"
            emoji = "😕"
        else:
            bonus_msg = f"\n😞 ПЕЧАЛЬ... -2 коина ({original_coins} → {coins})"
            emoji = "😞"
    elif chance < 0.20:
        bonus = 1
        coins += bonus
        bonus_msg = f"\n👍 БОНУС! +{bonus} коин!"
        emoji = "👍"
    
    new_balance, level = db.add_coins(user_id, coins)
    
    # Получаем информацию об уровне
    user_data = db.get_user(user_id)
    current_level, next_level, progress = calculate_level_progress(user_data['total_farmed'])
    
    level_info = ""
    if user_data['level'] != level:
        level_info = f"\n🎊 УРОВЕНЬ ПОВЫШЕН! Теперь ты {current_level['emoji']} {current_level['name']}!"
    else:
        level_info = f"\n{current_level['emoji']} Уровень: {current_level['name']}"
        if next_level:
            level_info += f" ({progress}% до {next_level['name']})"
    
    result = f"""
{emoji} Фарм завершен! {emoji}

Получено: {coins} KMEкоинов{bonus_msg}
💰 Новый баланс: {new_balance} KMEкоинов
🏆 Всего заработано: {user_data['total_farmed']}
{level_info}

⏳ Следующий фарм через {FARM_COOLDOWN} часа!
    """
    await update.message.reply_text(result)

async def steal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    # Проверяем КД
    can_steal, msg = db.can_steal(user_id)
    
    if not can_steal:
        await update.message.reply_text(msg)
        return
    
    # Нужен target (кому красть)
    if not context.args:
        await update.message.reply_text(
            "❌ Укажите цель для кражи!\n"
            "✅ Используйте: /steal @username\n"
            "Пример: /steal @Matvatok\n\n"
            "⚠️ Шанс успеха: 50/50\n"
            f"💰 Сумма кражи: {STEAL_AMOUNT} коинов\n"
            f"⏳ КД: {STEAL_COOLDOWN} минут"
        )
        return
    
    target = context.args[0]
    
    # Поиск цели
    target_user_id = None
    target_username = ""
    
    if target.isdigit():
        if target in db.data:
            target_user_id = target
            target_username = db.data[target].get('username', target)
    else:
        username = target.lstrip('@').lower()
        for uid, user_data in db.data.items():
            if user_data.get('username', '').lower() == username:
                target_user_id = uid
                target_username = user_data.get('username', username)
                break
    
    if not target_user_id:
        await update.message.reply_text("❌ Цель не найдена!")
        return
    
    # Нельзя красть у себя
    if target_user_id == str(user_id):
        await update.message.reply_text("❌ Нельзя красть у самого себя!")
        return
    
    # Пытаемся украсть
    success, message = db.steal_coins(str(user_id), target_user_id)
    
    if success:
        # Получаем имена для уведомления
        thief_name = f"@{user.username}" if user.username else user.first_name
        victim_data = db.get_user(target_user_id)
        victim_name = f"@{victim_data.get('username', '')}" if victim_data.get('username') else f"Игрок {target_user_id[-4:]}"
        
        # Уведомляем вора
        result = f"""
🎯 ПОПЫТКА КРАЖИ

{message}
🎯 Жертва: {victim_name}
💰 Украдено: {STEAL_AMOUNT} коинов
🏦 Твой баланс: {db.get_user(user_id)['coins']} коинов
⏳ Следующая кража через {STEAL_COOLDOWN} минут
        """
        
        # Уведомляем жертву (если есть username)
        if victim_data.get('username'):
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=f"⚠️ ВНИМАНИЕ!\n{thief_name} украл у вас {STEAL_AMOUNT} коинов!\n🏦 Ваш баланс: {victim_data['coins']} коинов"
                )
            except:
                pass  # Если бот заблокирован или нет прав
    else:
        result = f"""
🎯 ПОПЫТКА КРАЖИ

{message}
🎯 Цель: {target}
💰 Сумма: {STEAL_AMOUNT} коинов
⏳ Следующая попытка через {STEAL_COOLDOWN} минут
        """
    
    await update.message.reply_text(result)

async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = db.get_user(user.id)
    
    # Таймер фарма
    last_time = user_data['last_farm']
    farm_timer = ""
    if last_time:
        last = datetime.fromisoformat(last_time)
        now = datetime.now()
        cooldown = timedelta(hours=FARM_COOLDOWN)
        
        if now - last < cooldown:
            next_farm = last + cooldown
            wait = next_farm - now
            hours = int(wait.total_seconds() // 3600)
            minutes = int((wait.total_seconds() % 3600) // 60)
            seconds = int(wait.total_seconds() % 60)
            farm_timer = f"⏳ До фарма: {hours:02d}:{minutes:02d}:{seconds:02d}\n"
        else:
            farm_timer = "✅ Можно фармить! /farm\n"
    else:
        farm_timer = "✅ Можно фармить! /farm\n"
    
    # Таймер кражи
    steal_timer = ""
    if user_data.get('last_steal'):
        last = datetime.fromisoformat(user_data['last_steal'])
        now = datetime.now()
        cooldown = timedelta(minutes=STEAL_COOLDOWN)
        
        if now - last < cooldown:
            next_steal = last + cooldown
            wait = next_steal - now
            minutes = int(wait.total_seconds() // 60)
            seconds = int(wait.total_seconds() % 60)
            steal_timer = f"⏳ До кражи: {minutes:02d}:{seconds:02d}\n"
        else:
            steal_timer = "✅ Можно красть! /steal @username\n"
    else:
        steal_timer = "✅ Можно красть! /steal @username\n"
    
    # Информация об уровне
    current_level, next_level, progress = calculate_level_progress(user_data['total_farmed'])
    
    level_text = f"{current_level['emoji']} Уровень: {current_level['name']}"
    if next_level:
        coins_needed = next_level['max_coins'] - user_data['total_farmed']
        level_text += f"\n📈 До {next_level['emoji']} {next_level['name']}: {coins_needed} коинов ({progress}%)"
    else:
        level_text += "\n🎉 Максимальный уровень достигнут!"
    
    # Статистика кражи
    steal_stats = ""
    if user_data.get('steal_count', 0) > 0:
        steal_stats = f"\n🎯 Кражи: {user_data['steal_count']} попыток"
        steal_stats += f"\n💰 Украдено: {user_data.get('stolen_coins', 0)} коинов"
        steal_stats += f"\n💸 Потеряно: {user_data.get('lost_coins', 0)} коинов"
    
    text = f"""
👤 Игрок: {user.first_name}
{level_text}
💰 KMEкоинов: {user_data['coins']}
📊 Фармов: {user_data['farm_count']}
🏆 Всего заработано: {user_data['total_farmed']}
{steal_stats}

{farm_timer}{steal_timer}🛍️ Используйте /shop для покупки
    """
    await update.message.reply_text(text)

async def level_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """
📊 СИСТЕМА УРОВНЕЙ KMEbot:

Уровни определяются по общему количеству заработанных коинов:

👶 Рекрут - 0-100 коинов
🛡️ Страж - 101-200 коинов
⚔️ Рыцарь - 201-300 коинов  
👑 Титян - 301-400 коинов
🔥 БОГ - 401+ коинов

Чем больше фармишь - тем выше уровень!
Уровень отображается в:
• /start
• /balance  
• /farm (при повышении)
• /top

🎯 Цель: достичь уровня БОГ! 🏆
    """
    await update.message.reply_text(text)

async def top_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not db.data:
        await update.message.reply_text("Пока нет игроков!")
        return
    
    # Получаем топ-5 по total_farmed
    top_users = sorted(
        db.data.items(),
        key=lambda x: x[1].get('total_farmed', 0),
        reverse=True
    )[:5]
    
    text = "🏆 ТОП 5 ИГРОКОВ KMEbot 🏆\n\n"
    
    for i, (user_id, user_data) in enumerate(top_users, 1):
        # Получаем имя для отображения
        username = user_data.get('username', '')
        display_name = user_data.get('display_name', '')
        
        if display_name:
            name = display_name[:15]
        elif username:
            name = f"@{username}"
        else:
            name = f"Игрок {user_id[-4:]}"
        
        coins = user_data.get('total_farmed', 0)
        level_info = get_level_info(coins)
        medal = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][i-1]
        
        text += f"{medal} {level_info['emoji']} {name}\n"
        text += f"   💰 {coins} коинов | {level_info['name']}\n\n"
    
    await update.message.reply_text(text)

async def shop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = db.get_user(user.id)
    
    text = "🛍️ МАГАЗИН KMEbot 🛍️\n\n"
    
    for item_id, item in SHOP_ITEMS.items():
        text += f"{item_id}. {item['name']}\n"
        text += f"   💰 Цена: {item['price']} KMEкоинов\n"
        text += f"   📝 {item['description']}\n"
        text += f"   🛒 Команда: /buy_{item_id}\n\n"
    
    text += f"💰 Ваш баланс: {user_data['coins']} KMEкоинов\n"
    text += f"🛒 Для покупки напишите /buy_номер\n"
    text += f"📝 Пример: /buy_1"
    
    await update.message.reply_text(text)

async def buy_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    command = update.message.text
    
    try:
        item_id = int(command.split('_')[1])
    except:
        await update.message.reply_text(
            "❌ Неправильный формат!\n"
            "✅ Используйте: /buy_номер\n"
            "📝 Пример: /buy_1\n"
            "🛍️ Посмотреть товары: /shop"
        )
        return
    
    success, message = db.buy_item(user.id, item_id)
    
    if success:
        user_data = db.get_user(user.id)
        message = f"✅ {message}\n💰 Остаток: {user_data['coins']} KMEкоинов"
    else:
        message = f"❌ {message}"
    
    await update.message.reply_text(message)

async def inventory_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = db.get_user(user.id)
    
    if not user_data['inventory']:
        text = "📦 Ваш инвентарь пуст\n🛍️ Загляните в магазин: /shop"
        await update.message.reply_text(text)
        return
    
    # Создаем инлайн-клавиатуру для инвентаря
    keyboard = []
    
    for i, item in enumerate(user_data['inventory']):
        item_name = item['name']
        bought_date = datetime.fromisoformat(item['bought_at']).strftime("%d.%m")
        
        if item.get('exchanged', False):
            status = "✅ Обменян"
            callback_data = f"none_{i}"
        elif item.get('exchangeable', True):
            status = "🔄 Обменять"
            callback_data = f"exchange_{i}"
        else:
            status = "❌ Не обменивается"
            callback_data = f"none_{i}"
        
        keyboard.append([InlineKeyboardButton(
            f"{i+1}. {item_name} ({bought_date}) - {status}",
            callback_data=callback_data
        )])
    
    keyboard.append([InlineKeyboardButton("❌ Закрыть", callback_data="inv_close")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = f"📦 ВАШ ИНВЕНТАРЬ ({len(user_data['inventory'])} предметов)\n\n"
    text += "Нажмите на предмет для обмена"
    
    await update.message.reply_text(text, reply_markup=reply_markup)

async def inventory_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = str(query.from_user.id)
    
    if data == "inv_close":
        await query.delete_message()
        return
    
    if data.startswith("exchange_"):
        item_index = int(data.split("_")[1])
        
        success, result = db.exchange_item(user_id, item_index)
        
        if success:
            item = result
            item_name = item['name']
            
            # Получаем информацию о пользователе для уведомления админа
            user_data = db.get_user(user_id)
            username = user_data.get('username', '')
            display_name = user_data.get('display_name', query.from_user.first_name)
            
            user_display = f"@{username}" if username else display_name
            
            # Уведомляем пользователя
            await query.edit_message_text(
                f"✅ ПРЕДМЕТ ОБМЕНЯН!\n\n"
                f"🎁 {item_name}\n"
                f"👤 Вы: {user_display}\n\n"
                f"📢 Администратор получил уведомление и свяжется с вами!"
            )
            
            # Уведомляем админа
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"🔔 НОВЫЙ ОБМЕН ПРЕДМЕТА!\n\n"
                         f"🎁 Предмет: {item_name}\n"
                         f"👤 Игрок: {user_display} (ID: {user_id})\n"
                         f"🕐 Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                         f"⚠️ Не забудьте выполнить услугу!"
                )
            except:
                pass  # Если админ не найден
            
        else:
            await query.answer(result, show_alert=True)
    
    elif data.startswith("none_"):
        await query.answer("Этот предмет нельзя обменять или уже обменян!", show_alert=True)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = f"""
🆘 ПОМОЩЬ ПО KMEbot 🆘

📋 Основные команды:
/farm - получить коины (раз в {FARM_COOLDOWN} часа)
/steal @username - украсть 5 коинов (раз в {STEAL_COOLDOWN} мин, 50/50 шанс)
/balance - ваш баланс, уровень и статистика
/top - топ 5 игроков с уровнями
/shop - магазин товаров
/inventory - ваши покупки с обменом
/level - информация о системе уровней
/help - эта справка

🛍️ Товары в магазине:
1. 🔔 Сигна от Kme_Dota - 50 коинов
2. 👥 Сигна от Лсной братвы - 100 коинов
3. 👑 Модер в чате - 150 коинов
4. 🎮 Модер на твиче - 200 коинов
5. 🎵 Трек про тебя - 300 коинов
6. ⚔️ Dota+ - 400 коинов

🔄 ОБМЕН ПРЕДМЕТОВ:
• Купленные предметы можно обменять в /inventory
• При обмене администратор получит уведомление
• Предмет пропадает из инвентаря после обмена
• Администратор свяжется для выполнения услуги

📊 СИСТЕМА УРОВНЕЙ:
• 👶 Рекрут - 0-100 коинов
• 🛡️ Страж - 101-200 коинов
• ⚔️ Рыцарь - 201-300 коинов
• 👑 Титян - 301-400 коинов
• 🔥 БОГ - 401+ коинов

🎲 Система фарма:
• Базово: 1-5 коинов
• 🎉 УДАЧА (+2 коина): 10% шанс
• 😕 НЕУДАЧА (-1 или -2 коина): 8% шанс
• 👍 Старый бонус (+1): 2% шанс

🎯 Система кражи:
• /steal @username - попытка украсть 5 коинов
• Шанс успеха: 50/50
• При успехе: вы +5 коинов, жертва -5 коинов
• При провале: ничего не происходит
• КД: {STEAL_COOLDOWN} минут

💬 Работа в чатах:
• В группе пишите: /farm@KmeFarmBot
• Или просто /farm (если бот администратор)
• Бот автоматически отвечает на упоминания

👑 АДМИН-КОМАНДЫ (только для создателя):
/admin - панель администратора
/give @username количество - выдать коины
/find @username - найти игрока
/resetcd @username - сбросить КД игрока

👤 Создатель: {ADMIN_USERNAME}
❓ Проблемы/предложения: пишите {ADMIN_USERNAME}
    """
    await update.message.reply_text(text)

async def handle_mention(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.text:
        if context.bot.username and f"@{context.bot.username}" in update.message.text:
            await update.message.reply_text(
                f"👋 Да, я здесь, {update.effective_user.first_name}!\n"
                f"💬 Используйте команды:\n"
                f"💰 /farm - получить коины\n"
                f"🎯 /steal @username - украсть коины\n"
                f"📊 /balance - ваш баланс и уровень\n"
                f"🛍️ /shop - магазин"
            )

def main():
    print("=" * 50)
    print("🚀 ЗАПУСК KMEbot v5.0 (АДМИН-ПАНЕЛЬ + КРАЖА)")
    print("=" * 50)
    print(f"👥 Загружено игроков: {len(db.data)}")
    print(f"⏳ КД фарма: {FARM_COOLDOWN} часа")
    print(f"🎯 КД кражи: {STEAL_COOLDOWN} минут")
    print(f"💰 Коинов за фарм: 1-5 | За кражу: {STEAL_AMOUNT}")
    print(f"🛍️ Товаров в магазине: {len(SHOP_ITEMS)}")
    print(f"📊 Система уровней: {len(LEVELS)} уровня")
    print("=" * 50)
    print("👑 АДМИН ПАНЕЛЬ: /admin")
    print(f"👤 АДМИН ID: {ADMIN_ID}")
    print("✅ ПРИ ОБНОВЛЕНИИ КОДА ДАННЫЕ НЕ СБРОСЯТСЯ")
    print("=" * 50)
    
    try:
        app = Application.builder()\
            .token(TOKEN)\
            .get_updates_read_timeout(30)\
            .pool_timeout(30)\
            .build()
        
        # Основные команды
        app.add_handler(CommandHandler("start", start_cmd))
        app.add_handler(CommandHandler("farm", farm_cmd))
        app.add_handler(CommandHandler("steal", steal_cmd))
        app.add_handler(CommandHandler("balance", balance_cmd))
        app.add_handler(CommandHandler("top", top_cmd))
        app.add_handler(CommandHandler("shop", shop_cmd))
        app.add_handler(CommandHandler("inventory", inventory_cmd))
        app.add_handler(CommandHandler("help", help_cmd))
        app.add_handler(CommandHandler("level", level_cmd))
        
        # Админ команды
        app.add_handler(CommandHandler("admin", admin_panel))
        app.add_handler(CommandHandler("give", give_coins_cmd))
        app.add_handler(CommandHandler("find", find_user_cmd))
        app.add_handler(CommandHandler("resetcd", reset_cd_cmd))
        
        # Команды покупки
        for i in range(1, 7):
            app.add_handler(CommandHandler(f"buy_{i}", buy_cmd))
        
        # Обработчики инлайн-кнопок
        app.add_handler(CallbackQueryHandler(admin_callback_handler, pattern="^admin_"))
        app.add_handler(CallbackQueryHandler(inventory_callback_handler, pattern="^(exchange_|none_|inv_)"))
        
        app.add_handler(MessageHandler(
            filters.TEXT & filters.Entity("mention"),
            handle_mention
        ))
        
        print("✅ KMEbot запущен!")
        print("👑 Админ-панель доступна по команде /admin")
        print("🎯 Добавлена система кражи /steal")
        print("🔄 Добавлен обмен предметов в инвентаре")
        print("🔧 Для остановки нажмите Ctrl+C")
        print("=" * 50)
        
        app.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        input("Нажми Enter для выхода...")

if __name__ == "__main__":
    main()

