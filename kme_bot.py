
import json
import os
import random
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler

TOKEN = "8542959870:AAHzEChit6gsHlLzxNEg-090lNpBZwItU2E"
ADMIN_ID = 6443845944
ADMIN_USERNAME = "@Matvatok"
FARM_COOLDOWN = 4
STEAL_COOLDOWN = 30
STEAL_AMOUNT = 10
STEAL_CHANCE = 50

# Система уровней (5 уровней)
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

# ========== ФУНКЦИИ УРОВНЕЙ ==========
def get_user_level(total_coins):
    """Определить уровень игрока по количеству коинов"""
    for level in LEVELS:
        if level["min_coins"] <= total_coins <= level["max_coins"]:
            return level
    return LEVELS[-1]

def get_level_progress(total_coins):
    """Получить прогресс до следующего уровня"""
    current_level = get_user_level(total_coins)
    
    if current_level["level"] == len(LEVELS):
        return current_level, None, 100, 0
    
    next_level = LEVELS[current_level["level"]]
    
    coins_in_current = total_coins - current_level["min_coins"]
    total_for_current = current_level["max_coins"] - current_level["min_coins"] + 1
    
    progress_percent = (coins_in_current / total_for_current) * 100 if total_for_current > 0 else 100
    coins_needed = next_level["min_coins"] - total_coins
    
    return current_level, next_level, int(progress_percent), coins_needed

class Database:
    def __init__(self, filename="kme_data.json"):
        self.filename = filename
        self.data = self.load_data()
    
    def load_data(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def save_data(self):
        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
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
                'steal_success': 0,
                'steal_failed': 0,
                'stolen_total': 0,
                'lost_total': 0,
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
        cooldown = timedelta(hours=FARM_COOLDOWN)
        
        if now - last >= cooldown:
            return True, "✅ Можно фармить!"
        else:
            wait = cooldown - (now - last)
            hours = int(wait.total_seconds() // 3600)
            minutes = int((wait.total_seconds() % 3600) // 60)
            seconds = int(wait.total_seconds() % 60)
            return False, f"⏳ Ждите {hours:02d}:{minutes:02d}:{seconds:02d}"
    
    def can_steal(self, user_id):
        user = self.get_user(user_id)
        if not user['last_steal']:
            return True, "✅ Можно красть!"
        
        last = datetime.fromisoformat(user['last_steal'])
        now = datetime.now()
        cooldown = timedelta(minutes=STEAL_COOLDOWN)
        
        if now - last >= cooldown:
            return True, "✅ Можно красть!"
        else:
            wait = cooldown - (now - last)
            minutes = int(wait.total_seconds() // 60)
            seconds = int(wait.total_seconds() % 60)
            return False, f"⏳ Ждите {minutes:02d}:{seconds:02d}"
    
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
    
    def remove_coins(self, user_id, amount):
        user = self.get_user(user_id)
        if user['coins'] < amount:
            return False, user['coins']
        user['coins'] -= amount
        self.save_data()
        return True, user['coins']
    
    def steal_attempt(self, thief_id, victim_id):
        thief = self.get_user(thief_id)
        victim = self.get_user(victim_id)
        
        if victim['coins'] < STEAL_AMOUNT:
            return False, "❌ У жертвы нет денег!", 0, 0
        
        thief['last_steal'] = datetime.now().isoformat()
        
        if random.randint(1, 100) <= STEAL_CHANCE:
            success = self.remove_coins(victim_id, STEAL_AMOUNT)
            if not success[0]:
                return False, "❌ Ошибка при краже!", 0, 0
            
            self.add_coins(thief_id, STEAL_AMOUNT, from_farm=False)
            thief['steal_success'] += 1
            thief['stolen_total'] += STEAL_AMOUNT
            victim['lost_total'] += STEAL_AMOUNT
            
            return True, f"✅ Успешно украдено {STEAL_AMOUNT} коинов!", STEAL_AMOUNT, 0
        else:
            thief['steal_failed'] += 1
            return False, "❌ Неудачная попытка кражи! Жертва заметила.", 0, 0
    
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
            'description': item['description'],
            'exchangeable': item['exchangeable'],
            'bought_at': datetime.now().isoformat(),
            'exchanged': False
        })
        self.save_data()
        return True, f"✅ Куплено: {item['name']} за {item['price']} коинов"
    
    def exchange_item(self, user_id, item_index):
        user = self.get_user(user_id)
        
        if item_index >= len(user['inventory']):
            return False, "❌ Такого предмета нет!"
        
        item = user['inventory'][item_index]
        
        if not item.get('exchangeable', True):
            return False, "❌ Этот предмет нельзя обменять!"
        
        if item.get('exchanged', False):
            return False, "❌ Этот предмет уже был обменян!"
        
        user['inventory'][item_index]['exchanged'] = True
        user['inventory'][item_index]['exchanged_at'] = datetime.now().isoformat()
        self.save_data()
        
        return True, item
    
    def remove_exchanged_item(self, user_id, item_index):
        user = self.get_user(user_id)
        
        if item_index >= len(user['inventory']):
            return False
        
        if not user['inventory'][item_index].get('exchanged', False):
            return False
        
        user['inventory'].pop(item_index)
        self.save_data()
        return True

db = Database()

def is_admin(user_id):
    return user_id == ADMIN_ID

# ========== КОМАНДА /PARTY (0-13000) ==========
async def party_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Поиск тимы Dota 2 по MMR"""
    user = update.effective_user
    
    if not context.args:
        await update.message.reply_text(
            "🎮 ПОИСК ТИМЫ DOTA 2\n\n"
            "✅ Напишите свой MMR: /party 2500\n\n"
            "📊 Примеры:\n"
            "/party 2500\n"
            "/party 5000\n"
            "/party 100\n\n"
            "🎯 Диапазон: от 0 до 13000\n\n"
            "📨 Сообщение будет разослано всем зарегистрированным игрокам!"
        )
        return
    
    try:
        mmr = int(context.args[0])
        
        if mmr < 0 or mmr > 13000:
            await update.message.reply_text("❌ MMR должен быть от 0 до 13000!")
            return
        
    except ValueError:
        await update.message.reply_text("❌ Введите число для MMR!")
        return
    
    user_name = f"@{user.username}" if user.username else user.first_name
    chat_title = update.message.chat.title if update.message.chat.title else "этот чат"
    
    broadcast_text = (
        f"🎮 ПОИСК ТИМЫ DOTA 2\n\n"
        f"👤 Ищет команду: {user_name}\n"
        f"📊 Примерный MMR: ~{mmr}\n\n"
        f"💬 Зайдите в чат '{chat_title}' и напишите {user_name}\n"
        f"📍 Чтобы узнать подробности и собраться на игру!"
    )
    
    total_players = len(db.data)
    notified = 0
    
    await update.message.reply_text(f"📢 Рассылка запущена... ({total_players} получателей)")
    
    for player_id, player_data in db.data.items():
        if player_id == str(user.id):
            continue
            
        try:
            await context.bot.send_message(
                chat_id=player_id,
                text=broadcast_text
            )
            notified += 1
        except:
            continue
    
    result = (
        f"✅ РАССЫЛКА ЗАВЕРШЕНА!\n\n"
        f"👤 Вы: {user_name}\n"
        f"📊 MMR: ~{mmr}\n\n"
        f"📨 Отправлено: {notified} игрокам\n"
        f"👥 Всего в базе: {total_players}\n\n"
        f"💬 Ждите ответа в чате '{chat_title}'!"
    )
    
    await update.message.reply_text(result)

# ========== КОМАНДА /LEVEL ==========
async def level_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать уровень игрока"""
    user = update.effective_user
    user_id = str(user.id)
    user_data = db.get_user(user_id)
    
    total_coins = user_data['total_farmed']
    current_level, next_level, progress, coins_needed = get_level_progress(total_coins)
    
    avg_farm = 2.5
    farms_needed = max(1, int(coins_needed / avg_farm)) if coins_needed > 0 else 0
    
    text = f"""
📊 УРОВЕНЬ ИГРОКА

👤 Игрок: {user.first_name}
💰 Всего заработано: {total_coins} коинов
🏆 Уровень: {current_level['name']}
📈 Прогресс: {progress}%
📊 Фармов: {user_data['farm_count']}
"""
    
    if next_level:
        text += f"""
🎯 ДО СЛЕДУЮЩЕГО УРОВНЯ:
{next_level['name']}
💰 Нужно коинов: {coins_needed}
🔄 Примерно фармов: {farms_needed}
⏰ При {FARM_COOLDOWN}ч КД: ~{farms_needed * FARM_COOLDOWN} часов
"""
    else:
        text += """
🎉 ВЫ ДОСТИГЛИ МАКСИМАЛЬНОГО УРОВНЯ!
🔥 Теперь вы Божество KMEbot!
"""
    
    text += "\n📋 СИСТЕМА УРОВНЕЙ:\n"
    for level in LEVELS:
        arrow = "➡️" if level["level"] == current_level["level"] else "  "
        text += f"{arrow} {level['name']}: {level['min_coins']}-{level['max_coins'] if level['max_coins'] < 1000000 else '∞'} коинов\n"
    
    await update.message.reply_text(text)

# ========== ОБНОВЛЁННЫЙ /BALANCE С УРОВНЕМ ==========
async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    user_data = db.get_user(user_id)
    
    total_coins = user_data['total_farmed']
    current_level, next_level, progress, coins_needed = get_level_progress(total_coins)
    
    farm_timer = ""
    if user_data['last_farm']:
        last = datetime.fromisoformat(user_data['last_farm'])
        now = datetime.now()
        cooldown = timedelta(hours=FARM_COOLDOWN)
        if now - last < cooldown:
            next_farm = last + cooldown
            wait = next_farm - now
            hours = int(wait.total_seconds() // 3600)
            minutes = int((wait.total_seconds() % 3600) // 60)
            farm_timer = f"⏳ До фарма: {hours:02d}:{minutes:02d}\n"
        else:
            farm_timer = "✅ Можно фармить! /farm\n"
    else:
        farm_timer = "✅ Можно фармить! /farm\n"
    
    text = f"""
👤 Игрок: {user.first_name}
💰 Текущие коины: {user_data['coins']}
🏆 Всего заработано: {total_coins}
📊 Уровень: {current_level['name']} ({progress}%)

🎯 Статистика:
📈 Фармов: {user_data['farm_count']}
✅ Успешных краж: {user_data['steal_success']}
❌ Провалов: {user_data['steal_failed']}
💰 Украдено: {user_data['stolen_total']}
💸 Потеряно: {user_data['lost_total']}

{farm_timer}
📈 Узнать подробнее об уровне: /level
"""
    
    await update.message.reply_text(text)

# ========== ОБНОВЛЁННЫЙ /START С УРОВНЯМИ ==========
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = db.get_user(user.id)
    
    if user.username:
        user_data['username'] = user.username
    if user.full_name:
        user_data['display_name'] = user.full_name
    db.save_data()
    
    total_coins = user_data['total_farmed']
    current_level, _, progress, _ = get_level_progress(total_coins)
    
    chat_type = update.message.chat.type
    
    if chat_type in ['group', 'supergroup']:
        text = f"""
👋 Привет, {user.first_name}!

📱 Я вижу ты в чате! Зайди ко мне в ЛС для полной регистрации:

1. 📩 Найди меня в списке чатов: @{(await context.bot.get_me()).username}
2. ✍️ Напиши мне: /start
3. ✅ Готово! Теперь ты в базе бота

📊 Твой уровень: {current_level['name']} ({progress}%)

🎮 После регистрации в ЛС ты сможешь:
• 📈 Смотреть свой уровень (/level)
• 💰 Получать коины от админа
• 🎯 Искать тиму по MMR (/party 2500)
• 🛍️ Покупать и обменивать предметы

💬 Пока можешь использовать в чате:
/farm - фармить коины (0-5 коинов)
/balance - баланс и уровень
/shop - магазин
/party ммр - искать команду (0-13000)
"""
    else:
        text = f"""
🎮 Добро пожаловать в KMEbot!

✅ Ты успешно зарегистрирован в базе бота!

👤 Игрок: {user.first_name}
💰 Текущие коины: {user_data['coins']}
🏆 Всего заработано: {total_coins}
📊 Уровень: {current_level['name']} ({progress}%)

📋 ОСНОВНЫЕ КОМАНДЫ:
/farm - получить коины (раз в {FARM_COOLDOWN}ч) 0-5 коинов
/balance - ваш баланс и статистика
/level - подробная информация об уровне
/top - топ игроков
/shop - магазин товаров
/inventory - ваши покупки с обменом
/help - помощь
/party ммр - искать команду Dota 2

📈 СИСТЕМА УРОВНЕЙ:
👶 Рекрут - 0-100 коинов
🛡️ Страж - 101-200 коинов
⚔️ Рыцарь - 201-300 коинов
👑 Титян - 301-400 коинов
🔥 Божество - 401+ коинов

🎮 ПОИСК ТИМЫ DOTA 2:
• /party 2500 - найдет тиму ~2500 MMR
• /party 5000 - найдет тиму ~5000 MMR
• Диапазон: 0-13000 MMR
"""
    
    await update.message.reply_text(text)

# ========== ОБНОВЛЁННЫЙ /FARM С УВЕДОМЛЕНИЕМ ОБ УРОВНЕ ==========
async def farm_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    
    can_farm, msg = db.can_farm(user_id)
    
    if not can_farm:
        await update.message.reply_text(msg)
        return
    
    coins = random.randint(0, 5)
    bonus_msg = ""
    emoji = "💰"
    
    chance = random.random()
    
    # 10% шанс на минус коин (увеличено)
    if chance < 0.10:
        bonus = 2
        coins += bonus
        bonus_msg = f"\n🎉 УДАЧА! +{bonus} коина!"
        emoji = "🎉"
    elif chance < 0.20:
        penalty = random.choice([-1, -2])
        original_coins = coins
        coins = max(0, coins + penalty)
        if penalty == -1:
            bonus_msg = f"\n😕 Неудача... -1 коин ({original_coins} → {coins})"
            emoji = "😕"
        else:
            bonus_msg = f"\n😞 Печаль... -2 коина ({original_coins} → {coins})"
            emoji = "😞"
    
    old_balance = db.get_user(user_id)['total_farmed']
    new_balance = db.add_coins(user_id, coins)
    
    old_level = get_user_level(old_balance)
    new_level = get_user_level(new_balance)
    
    level_up_msg = ""
    if old_level['level'] < new_level['level']:
        level_up_msg = f"\n\n🎊 УРОВЕНЬ ПОВЫШЕН! Теперь ты {new_level['name']}!"
    
    result = f"""
{emoji} Фарм завершен!

Получено: {coins} коинов{bonus_msg}
💰 Баланс: {db.get_user(user_id)['coins']}
🏆 Всего: {new_balance}
📊 Уровень: {new_level['name']}{level_up_msg}

⏳ Следующий через {FARM_COOLDOWN}ч
"""
    
    if coins == 0:
        result += "\n💡 Не расстраивайся! Пиши /level чтобы увидеть прогресс!"
    
    await update.message.reply_text(result)

# ========== КОМАНДА ПОКУПКИ ПРЕДМЕТА ==========
async def buy_item_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, item_id: int):
    """Покупка предмета из магазина"""
    user = update.effective_user
    user_id = str(user.id)
    
    success, result = db.buy_item(user_id, item_id)
    
    if success:
        item_name = SHOP_ITEMS[item_id]["name"]
        item_price = SHOP_ITEMS[item_id]["price"]
        user_data = db.get_user(user_id)
        
        text = f"""
✅ ПОКУПКА УСПЕШНА!

🎁 Предмет: {item_name}
💰 Стоимость: {item_price} коинов
💳 Баланс: {user_data['coins']} коинов

📦 Предмет добавлен в инвентарь!
🔄 Обменять: /inventory
🛍️ Купить ещё: /shop
"""
        
        if SHOP_ITEMS[item_id]["exchangeable"]:
            text += "\n⚠️ ВАЖНО: Для обмена предмета:\n1. Откройте /inventory\n2. Нажмите на предмет\n3. Подтвердите обмен\n4. Админ получит уведомление!"
    else:
        text = result
    
    await update.message.reply_text(text)

# ========== КОМАНДА ИНВЕНТАРЯ ==========
async def inventory_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    user_data = db.get_user(user_id)
    
    if not user_data['inventory']:
        await update.message.reply_text(
            "📦 Ваш инвентарь пуст\n"
            "🛍️ Посмотреть товары: /shop\n\n"
            "💡 Совет: Купите что-нибудь и обменяйте на услугу!"
        )
        return
    
    keyboard = []
    
    for i, item in enumerate(user_data['inventory']):
        item_name = item['name']
        bought_date = datetime.fromisoformat(item['bought_at']).strftime("%d.%m")
        
        if item.get('exchanged', False):
            status = f"✅ Обменян {datetime.fromisoformat(item.get('exchanged_at', '')).strftime('%d.%m')}"
            callback_data = f"inv_view_{i}"
        elif item.get('exchangeable', True):
            status = "🔄 ОБМЕНЯТЬ"
            callback_data = f"inv_exchange_{i}"
        else:
            status = "❌ Не обменивается"
            callback_data = f"inv_view_{i}"
        
        keyboard.append([InlineKeyboardButton(
            f"{i+1}. {item_name} ({bought_date}) - {status}",
            callback_data=callback_data
        )])
    
    keyboard.append([InlineKeyboardButton("❌ Закрыть", callback_data="inv_close")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = f"📦 ВАШ ИНВЕНТАРЬ ({len(user_data['inventory'])} предметов)\n🔄 Нажмите на предмет для обмена"
    await update.message.reply_text(text, reply_markup=reply_markup)

# ========== КОМАНДА МАГАЗИНА ==========
async def shop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = db.get_user(user.id)
    
    text = "🛍️ МАГАЗИН KMEbot\n\n"
    
    for item_id, item in SHOP_ITEMS.items():
        text += f"{item_id}. {item['name']}\n"
        text += f"   💰 {item['price']} коинов\n"
        text += f"   📝 {item['description']}\n"
        text += f"   🛒 /buy_{item_id}\n\n"
    
    total_coins = user_data['total_farmed']
    current_level = get_user_level(total_coins)
    
    text += f"💰 Ваш баланс: {user_data['coins']} коинов\n"
    text += f"🏆 Ваш уровень: {current_level['name']}\n"
    text += "🔄 Все предметы можно обменять на услуги!"
    
    await update.message.reply_text(text)

# ========== КОМАНДА ТОП ==========
async def top_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not db.data:
        await update.message.reply_text("📭 Пока нет игроков!")
        return
    
    top_users = sorted(
        db.data.items(),
        key=lambda x: x[1]['total_farmed'],
        reverse=True
    )[:5]
    
    text = "🏆 ТОП 5 ИГРОКОВ ПО УРОВНЮ 🏆\n\n"
    
    for i, (user_id, user_data) in enumerate(top_users, 1):
        username = user_data.get('username', '')
        if username:
            name = f"@{username}"
        else:
            name = user_data.get('display_name', f"ID:{user_id[:6]}")
        
        total_coins = user_data['total_farmed']
        level = get_user_level(total_coins)
        medal = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][i-1]
        
        text += f"{medal} {name}\n"
        text += f"   {level['name']} | {total_coins} коинов\n\n"
    
    text += "📈 Подними свой уровень: /farm и /level"
    await update.message.reply_text(text)

# ========== КОМАНДА ПОМОЩИ ==========
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = f"""
🆘 ПОМОЩЬ ПО KMEbot

📱 ВАЖНО: Для полного доступа напишите боту /start в ЛС!

📋 ОСНОВНЫЕ КОМАНДЫ:
/farm - коины каждые {FARM_COOLDOWN}ч (0-5 коинов)
/balance - ваш баланс и уровень
/level - подробная информация об уровне
/top - топ игроков по уровню
/shop - магазин товаров
/inventory - ваши покупки с обменом
/party ммр - искать команду Dota 2
/help - эта справка

📈 СИСТЕМА УРОВНЕЙ:
👶 Рекрут - 0-100 коинов
🛡️ Страж - 101-200 коинов
⚔️ Рыцарь - 201-300 коинов
👑 Титян - 301-400 коинов
🔥 Божество - 401+ коинов

🎮 ПОИСК ТИМЫ DOTA 2:
/party 2500 - разошлёт всем сообщение о поиске тимы
Диапазон MMR: 0-13000

👤 Создатель: {ADMIN_USERNAME}
"""
    await update.message.reply_text(text)

# ========== ИНВЕНТАРЬ КНОПКИ ОБРАБОТЧИК ==========
async def inventory_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    user_id = str(user.id)
    data = query.data
    
    if data == "inv_close":
        await query.delete_message()
        return
    
    elif data.startswith("inv_view_"):
        item_index = int(data.split("_")[2])
        user_data = db.get_user(user_id)
        
        if item_index >= len(user_data['inventory']):
            await query.answer("❌ Предмет не найден!", show_alert=True)
            return
        
        item = user_data['inventory'][item_index]
        bought_date = datetime.fromisoformat(item['bought_at']).strftime("%d.%m.%Y %H:%M")
        
        if item.get('exchanged', False):
            exchanged_date = datetime.fromisoformat(item.get('exchanged_at', '')).strftime("%d.%m.%Y %H:%M")
            status = f"✅ Обменян: {exchanged_date}"
        else:
            status = "🔄 Можно обменять"
        
        text = f"📦 {item['name']}\n💰 {item['price']} коинов\n📝 {item['description']}\n📅 {bought_date}\n📊 {status}"
        await query.edit_message_text(text)
        return
    
    elif data.startswith("inv_exchange_"):
        item_index = int(data.split("_")[2])
        
        success, result = db.exchange_item(user_id, item_index)
        
        if not success:
            await query.answer(result, show_alert=True)
            return
        
        item = result
        
        try:
            user_name = f"@{user.username}" if user.username else user.full_name
            item_name = item['name']
            
            admin_message = (
                f"🔔 НОВЫЙ ОБМЕН ПРЕДМЕТА!\n\n"
                f"🎁 Предмет: {item_name}\n"
                f"💰 Стоимость: {item['price']} коинов\n"
                f"👤 Игрок: {user_name} (ID: {user_id})\n"
                f"🕐 Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                f"⚠️ Не забудьте выполнить услугу!\n"
                f"✅ После выполнения удалите предмет:\n"
                f"/removeitem {user_id} {item_index}"
            )
            
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=admin_message
            )
        except Exception as e:
            print(f"Ошибка уведомления админа: {e}")
        
        await query.answer(f"✅ {item['name']} отправлен на обмен! Админ получил уведомление.", show_alert=True)
        
        user_data = db.get_user(user_id)
        
        if not user_data['inventory']:
            await query.edit_message_text("📦 Инвентарь пуст\n🛍️ /shop - купить что-то ещё")
            return
        
        keyboard = []
        for i, inv_item in enumerate(user_data['inventory']):
            item_name = inv_item['name']
            bought_date = datetime.fromisoformat(inv_item['bought_at']).strftime("%d.%m")
            
            if inv_item.get('exchanged', False):
                status = f"✅ Обменян {datetime.fromisoformat(inv_item.get('exchanged_at', '')).strftime('%d.%m')}"
                callback_data = f"inv_view_{i}"
            elif inv_item.get('exchangeable', True):
                status = "🔄 ОБМЕНЯТЬ"
                callback_data = f"inv_exchange_{i}"
            else:
                status = "❌ Не обменивается"
                callback_data = f"inv_view_{i}"
            
            keyboard.append([InlineKeyboardButton(
                f"{i+1}. {item_name} ({bought_date}) - {status}",
                callback_data=callback_data
            )])
        
        keyboard.append([InlineKeyboardButton("❌ Закрыть", callback_data="inv_close")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"📦 ВАШ ИНВЕНТАРЬ ({len(user_data['inventory'])} предметов)\n🔄 Нажмите на предмет для обмена",
            reply_markup=reply_markup
        )

# ========== АДМИН КОМАНДЫ ==========
async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Панель администратора"""
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ Эта команда только для администратора!")
        return
    
    text = f"""
👑 ПАНЕЛЬ АДМИНИСТРАТОРА

👥 Игроков в базе: {len(db.data)}
💰 Общий оборот: {sum(user['total_farmed'] for user in db.data.values())}
🔄 Предметов куплено: {sum(len(user['inventory']) for user in db.data.values())}

📊 КОМАНДЫ:
/stats - полная статистика
/give [ID] [сумма] - выдать коины
/removeitem [ID] [индекс] - удалить обменянный предмет

📈 СИСТЕМА:
Уровней: {len(LEVELS)}
Фарм: 0-5 коинов / {FARM_COOLDOWN}ч
Кража: {STEAL_AMOUNT} коинов / {STEAL_COOLDOWN}мин
Шанс кражи: {STEAL_CHANCE}%

👤 Админ: {ADMIN_USERNAME}
"""
    await update.message.reply_text(text)

async def give_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выдать коины игроку"""
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ Эта команда только для администратора!")
        return
    
    if len(context.args) != 2:
        await update.message.reply_text("❌ Формат: /give [ID] [сумма]\nПример: /give 123456789 100")
        return
    
    try:
        target_id = str(context.args[0])
        amount = int(context.args[1])
        
        if amount <= 0:
            await update.message.reply_text("❌ Сумма должна быть положительной!")
            return
        
        target_data = db.get_user(target_id)
        old_balance = target_data['coins']
        new_balance = db.add_coins(target_id, amount, from_farm=False, from_admin=True)
        
        username = target_data.get('username', '')
        display_name = target_data.get('display_name', f"ID:{target_id}")
        
        text = f"""
✅ КОИНЫ ВЫДАНЫ!

👤 Игрок: {f'@{username}' if username else display_name}
💰 Сумма: {amount} коинов
💳 Было: {old_balance}
💳 Стало: {new_balance}

📊 Всего выдано админом: {target_data['admin_gifted']}
"""
        
        await update.message.reply_text(text)
        
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=f"🎉 АДМИНИСТРАТОР ВЫДАЛ ВАМ {amount} КОИНОВ!\n💰 Баланс: {new_balance}"
            )
        except:
            pass
            
    except ValueError:
        await update.message.reply_text("❌ Неверный формат суммы!")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Полная статистика бота"""
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ Эта команда только для администратора!")
        return
    
    total_players = len(db.data)
    total_coins = sum(user['coins'] for user in db.data.values())
    total_farmed = sum(user['total_farmed'] for user in db.data.values())
    total_items = sum(len(user['inventory']) for user in db.data.values())
    
    level_counts = {level["level"]: 0 for level in LEVELS}
    
    for user_data in db.data.values():
        level = get_user_level(user_data['total_farmed'])
        level_counts[level["level"]] += 1
    
    top_players = sorted(
        db.data.items(),
        key=lambda x: x[1]['total_farmed'],
        reverse=True
    )[:3]
    
    text = f"""
📊 ПОЛНАЯ СТАТИСТИКА БОТА

👥 ИГРОКИ:
Всего: {total_players}
Активных: {sum(1 for user in db.data.values() if user['total_farmed'] > 0)}

💰 ЭКОНОМИКА:
Текущие коины: {total_coins}
Всего заработано: {total_farmed}
Выдано админом: {sum(user['admin_gifted'] for user in db.data.values())}

📈 УРОВНИ:
"""
    
    for level in LEVELS:
        count = level_counts[level["level"]]
        percentage = (count / total_players * 100) if total_players > 0 else 0
        text += f"{level['name']}: {count} ({percentage:.1f}%)\n"
    
    text += f"\n🎮 АКТИВНОСТЬ:\n"
    text += f"Фармов: {sum(user['farm_count'] for user in db.data.values())}\n"
    text += f"Краж: {sum(user['steal_success'] + user['steal_failed'] for user in db.data.values())}\n"
    text += f"Успешных краж: {sum(user['steal_success'] for user in db.data.values())}\n"
    text += f"Покупок: {total_items}\n"
    
    text += f"\n🏆 ТОП 3 ИГРОКА:\n"
    for i, (player_id, player_data) in enumerate(top_players, 1):
        username = player_data.get('username', '')
        name = f"@{username}" if username else player_data.get('display_name', f"ID:{player_id[:6]}")
        level = get_user_level(player_data['total_farmed'])
        text += f"{i}. {name} - {level['name']} ({player_data['total_farmed']} коинов)\n"
    
    text += f"\n🔄 Последнее обновление: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    
    await update.message.reply_text(text)

async def removeitem_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удалить обменянный предмет у игрока"""
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ Эта команда только для администратора!")
        return
    
    if len(context.args) != 2:
        await update.message.reply_text("❌ Формат: /removeitem [ID] [индекс]\nПример: /removeitem 123456789 0")
        return
    
    try:
        target_id = str(context.args[0])
        item_index = int(context.args[1])
        
        success = db.remove_exchanged_item(target_id, item_index)
        
        if success:
            target_data = db.get_user(target_id)
            username = target_data.get('username', '')
            display_name = target_data.get('display_name', f"ID:{target_id}")
            
            text = f"""
✅ ПРЕДМЕТ УДАЛЕН!

👤 Игрок: {f'@{username}' if username else display_name}
📦 Индекс предмета: {item_index}
🔄 Осталось предметов: {len(target_data['inventory'])}

💡 Предмет был помечен как обменянный и удален из инвентаря.
"""
            await update.message.reply_text(text)
            
            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text="✅ АДМИНИСТРАТОР ПОДТВЕРДИЛ ВЫПОЛНЕНИЕ УСЛУГИ!\n📦 Предмет удален из вашего инвентаря."
                )
            except:
                pass
        else:
            await update.message.reply_text("❌ Не удалось удалить предмет. Возможно:\n1. Предмет не существует\n2. Предмет не был обменян\n3. Неправильный индекс")
            
    except ValueError:
        await update.message.reply_text("❌ Неверный формат индекса!")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

# ========== ЗАПУСК БОТА ==========
def main():
    print("=" * 60)
    print("🚀 ЗАПУСК KMEbot v5.0 - УРОВНИ + ПОИСК ТИМЫ")
    print("=" * 60)
    print(f"👥 Игроков в базе: {len(db.data)}")
    print(f"📈 Уровней: {len(LEVELS)}")
    print(f"💰 Фарм: 0-5 коинов, {FARM_COOLDOWN}ч КД")
    print(f"🎮 Поиск тимы: /party MMR (0-13000)")
    print(f"🔄 Инвентарь с кнопками обмена")
    print(f"👑 Админ ID: {ADMIN_ID}")
    print("=" * 60)
    
    app = Application.builder().token(TOKEN).build()
    
    # Команды
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("farm", farm_cmd))
    app.add_handler(CommandHandler("balance", balance_cmd))
    app.add_handler(CommandHandler("level", level_cmd))
    app.add_handler(CommandHandler("top", top_cmd))
    app.add_handler(CommandHandler("shop", shop_cmd))
    app.add_handler(CommandHandler("inventory", inventory_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("party", party_cmd))
    
    # Обработчики покупки предметов
    for item_id in SHOP_ITEMS.keys():
        app.add_handler(CommandHandler(f"buy_{item_id}", 
                                      lambda update, context, item_id=item_id: buy_item_cmd(update, context, item_id)))
    
    # Обработчик инвентаря (кнопки)
    app.add_handler(CallbackQueryHandler(inventory_callback_handler, pattern="^inv_"))
    
    # Команды админа
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("give", give_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("removeitem", removeitem_cmd))
    
    print("✅ Бот запущен и готов к работе!")
    print("📊 Статистика: /stats - просмотр статистики бота")
    print("🎮 Поиск тимы: /party 2500 - пример использования")
    print("📈 Уровни: /level - информация об уровне")
    print("=" * 60)
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Бот остановлен пользователем")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()

