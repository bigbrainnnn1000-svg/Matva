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
COMPENSATION_AMOUNT = 15  # Количество коинов для компенсации

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
        cooldown = timedelta(hours=FARM_COOLDOWN)
        
        if now - last >= cooldown:
            return True, "✅ Можно фармить!"
        else:
            wait = cooldown - (now - last)
            hours = int(wait.total_seconds() // 3600)
            minutes = int((wait.total_seconds() % 3600) // 60)
            seconds = int(wait.total_seconds() % 60)
            return False, f"⏳ Ждите {hours:02d}:{minutes:02d}:{seconds:02d}"
    
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
    
    def add_compensation_to_all(self, amount):
        """Выдать компенсацию всем игрокам в базе"""
        compensation_data = {
            'date': datetime.now().isoformat(),
            'amount': amount,
            'total_players': len(self.data)
        }
        
        for user_id in self.data:
            user = self.get_user(user_id)
            user['coins'] += amount
            if 'compensations' not in user:
                user['compensations'] = []
            user['compensations'].append(compensation_data)
        
        self.save_data()
        return len(self.data)

db = Database()

def is_admin(user_id):
    return user_id == ADMIN_ID

# ========== КОМАНДА /ANNOUNCE (ДЛЯ ПУБЛИЧНЫХ ОБЪЯВЛЕНИЙ В ЧАТЕ) ==========
async def announce_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Публичное объявление в чате"""
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ Только для админа!")
        return
    
    if not context.args:
        await update.message.reply_text(
            "📢 КОМАНДА ДЛЯ ПУБЛИЧНЫХ ОБЪЯВЛЕНИЙ\n\n"
            "✅ Формат: /announce [текст]\n\n"
            "📝 Примеры:\n"
            "/announce Внимание! Новый ивент скоро!\n"
            "/announce Технические работы 20:00-22:00\n\n"
            "⚠️ Сообщение будет отправлено в текущий чат для всех участников!"
        )
        return
    
    message_text = " ".join(context.args)
    
    if len(message_text) < 3:
        await update.message.reply_text("❌ Сообщение слишком короткое!")
        return
    
    admin_name = f"@{user.username}" if user.username else user.first_name
    chat_title = update.message.chat.title if update.message.chat.title else "чат"
    
    full_message = (
        f"📢 ОБЪЯВЛЕНИЕ ОТ АДМИНИСТРАТОРА\n\n"
        f"👤 От: {admin_name}\n"
        f"📍 Чат: {chat_title}\n\n"
        f"💬 Сообщение:\n{message_text}\n\n"
        f"🏆 KMEbot | /help - помощь"
    )
    
    await update.message.reply_text(full_message)

# ========== КОМАНДА /COMPENSATION (АДМИН ПАНЕЛЬ) ==========
async def compensation_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выдать компенсацию всем игрокам"""
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ Только для админа!")
        return
    
    # Создаем клавиатуру с подтверждением
    keyboard = [
        [
            InlineKeyboardButton("✅ ВЫДАТЬ ВСЕМ", callback_data="comp_confirm"),
            InlineKeyboardButton("❌ ОТМЕНА", callback_data="comp_cancel")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"💰 ВЫДАЧА КОМПЕНСАЦИИ ВСЕМ ИГРОКАМ\n\n"
        f"👥 Игроков в базе: {len(db.data)}\n"
        f"💰 Сумма каждому: {COMPENSATION_AMOUNT} коинов\n"
        f"🎁 Всего будет выдано: {len(db.data) * COMPENSATION_AMOUNT} коинов\n\n"
        f"⚠️ Подтвердите действие:",
        reply_markup=reply_markup
    )

# ========== ОБРАБОТЧИК КНОПОК КОМПЕНСАЦИИ ==========
async def compensation_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    
    if not is_admin(user.id):
        await query.answer("❌ Только для админа!", show_alert=True)
        return
    
    if query.data == "comp_cancel":
        await query.edit_message_text("❌ Выдача компенсации отменена")
        return
    
    elif query.data == "comp_confirm":
        total_players = len(db.data)
        if total_players == 0:
            await query.edit_message_text("❌ В базе нет игроков!")
            return
        
        # Выдаем компенсацию всем
        total_compensated = db.add_compensation_to_all(COMPENSATION_AMOUNT)
        
        # Отправляем уведомления всем игрокам
        admin_name = f"@{user.username}" if user.username else user.first_name
        successful = 0
        failed = 0
        
        for player_id in db.data:
            try:
                player_data = db.get_user(player_id)
                current_balance = player_data['coins']
                
                await context.bot.send_message(
                    chat_id=player_id,
                    text=(
                        f"🎉 ВЫ ПОЛУЧИЛИ КОМПЕНСАЦИЮ!\n\n"
                        f"💰 +{COMPENSATION_AMOUNT} KMEкоинов\n"
                        f"🏦 Ваш баланс: {current_balance}\n"
                        f"👤 От администратора: {admin_name}\n\n"
                        f"💬 Спасибо за участие в проекте!\n"
                        f"🎮 Желаем удачи в развитии!"
                    )
                )
                successful += 1
            except:
                failed += 1
        
        result_text = (
            f"✅ КОМПЕНСАЦИЯ ВЫДАНА!\n\n"
            f"📊 Результаты:\n"
            f"👥 Всего игроков: {total_players}\n"
            f"💰 Выдано каждому: {COMPENSATION_AMOUNT} коинов\n"
            f"🎁 Общая сумма: {total_players * COMPENSATION_AMOUNT} коинов\n\n"
            f"📨 Уведомления:\n"
            f"✅ Получили: {successful} игроков\n"
            f"❌ Не получили: {failed} игроков\n\n"
            f"⏰ Время выдачи: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
        
        await query.edit_message_text(result_text)

# ========== КОМАНДА /BROADCAST (ТОЛЬКО ДЛЯ АДМИНА) ==========
async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Рассылка сообщения всем игрокам"""
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ Только для админа!")
        return
    
    if not context.args:
        await update.message.reply_text(
            "📢 РАССЫЛКА СООБЩЕНИЙ\n\n"
            "✅ Формат: /broadcast Ваш текст сообщения\n\n"
            "📝 Примеры:\n"
            "/broadcast Всем привет! Новый ивент скоро!\n"
            "/broadcast Обновление бота! Добавлена команда /party\n\n"
            "⚠️ Сообщение будет отправлено ВСЕМ игрокам в базе!\n"
            "👥 Игроков в базе: " + str(len(db.data))
        )
        return
    
    message_text = " ".join(context.args)
    
    if len(message_text) < 3:
        await update.message.reply_text("❌ Сообщение слишком короткое!")
        return
    
    total_players = len(db.data)
    if total_players == 0:
        await update.message.reply_text("❌ В базе нет игроков!")
        return
    
    admin_name = f"@{user.username}" if user.username else user.first_name
    
    full_message = (
        f"📢 ОБЪЯВЛЕНИЕ ОТ АДМИНИСТРАТОРА\n\n"
        f"👤 От: {admin_name}\n\n"
        f"💬 Сообщение:\n{message_text}\n\n"
        f"🏆 KMEbot | /help - помощь"
    )
    
    await update.message.reply_text(f"📢 Рассылка запущена... Ожидайте итогов!")
    
    successful = 0
    failed = 0
    
    for player_id in db.data.keys():
        try:
            await context.bot.send_message(
                chat_id=player_id,
                text=full_message
            )
            successful += 1
        except:
            failed += 1
    
    result = (
        f"✅ РАССЫЛКА ЗАВЕРШЕНА!\n\n"
        f"📊 Статистика:\n"
        f"✅ Успешно: {successful} игроков\n"
        f"❌ Не удалось: {failed} игроков\n"
        f"👥 Всего в базе: {total_players}\n\n"
        f"💬 Ваше сообщение:\n\"{message_text[:100]}{'...' if len(message_text) > 100 else ''}\""
    )
    
    await update.message.reply_text(result)

# ========== КОМАНДА /GIVE (РАБОТАЕТ ПРИ ОТВЕТЕ НА СООБЩЕНИЕ) ==========
async def give_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ Только для админа!")
        return
    
    # ПРОВЕРКА: Должен быть ответ на сообщение
    if not update.message.reply_to_message:
        await update.message.reply_text(
            "❌ Нужно ответить на сообщение игрока!\n\n"
            "✅ КАК ВЫДАТЬ КОИНЫ:\n"
            "1. Найди сообщение игрока в чате\n"
            "2. Ответь на него (Reply)\n"
            "3. Напиши: /give 100\n\n"
            "Пример:\n"
            "Игрок: 'Привет!'\n"
            "Ты: (ответить) /give 50\n\n"
            "💰 Бот автоматически найдёт игрока и выдаст коины!"
        )
        return
    
    # ПРОВЕРКА: Должно быть количество коинов
    if not context.args:
        await update.message.reply_text(
            "❌ Укажите количество коинов!\n"
            "✅ Формат: /give 100\n"
            "✅ Пример: /give 50"
        )
        return
    
    try:
        amount = int(context.args[0])
        if amount <= 0:
            await update.message.reply_text("❌ Количество должно быть больше 0!")
            return
        if amount > 10000:
            await update.message.reply_text("❌ Максимум 10,000 коинов за раз!")
            return
    except:
        await update.message.reply_text("❌ Неправильное количество! Введите число.")
        return
    
    # ПОЛУЧАЕМ ИГРОКА ИЗ СООБЩЕНИЯ
    target_user = update.message.reply_to_message.from_user
    target_user_id = str(target_user.id)
    
    # СОХРАНЯЕМ ИГРОКА В БАЗЕ (если его нет)
    target_data = db.get_user(target_user_id)
    
    # Сохраняем данные игрока
    if target_user.username and not target_data.get('username'):
        target_data['username'] = target_user.username
    if target_user.full_name and not target_data.get('display_name'):
        target_data['display_name'] = target_user.full_name
    db.save_data()
    
    # ВЫДАЁМ КОИНЫ
    old_total = target_data['total_farmed']
    new_balance = db.add_coins(target_user_id, amount, from_farm=False, from_admin=True)
    
    # Формируем имя для отображения
    if target_user.username:
        target_name = f"@{target_user.username}"
    else:
        target_name = target_user.first_name
    
    # Проверяем повышение уровня
    old_level = get_user_level(old_total)
    new_level = get_user_level(new_balance)
    level_up_msg = ""
    if old_level['level'] < new_level['level']:
        level_up_msg = f"\n🎊 Уровень повышен: {old_level['name']} → {new_level['name']}!"
    
    # ОТВЕТ АДМИНУ
    result_admin = (
        f"✅ ВЫДАНО {amount} КОИНОВ!\n\n"
        f"👤 Игрок: {target_name}\n"
        f"💰 Баланс: {new_balance} коинов\n"
        f"🏆 Всего заработано: {old_total + amount}"
        f"{level_up_msg}"
    )
    
    # УВЕДОМЛЕНИЕ ИГРОКУ (в ЛС)
    try:
        await context.bot.send_message(
            chat_id=target_user_id,
            text=(
                f"🎉 АДМИН ВЫДАЛ ВАМ КОИНЫ!\n\n"
                f"💰 +{amount} KMEкоинов\n"
                f"🏦 Ваш баланс: {new_balance}\n"
                f"📊 Уровень: {new_level['name']}"
                f"{level_up_msg}\n\n"
                f"💬 Используйте:\n"
                f"• /farm - фармить коины\n"
                f"• /level - информация об уровне\n"
                f"• /shop - магазин\n"
                f"• /balance - проверить баланс"
            )
        )
        result_admin += "\n\n📨 Игрок получил уведомление в ЛС!"
    except:
        result_admin += "\n\n⚠️ Не удалось отправить уведомление игроку"
    
    await update.message.reply_text(result_admin)

# ========== КОМАНДА /BALANCE ДЛЯ ДРУГОГО ИГРОКА (ОТВЕТ НА СООБЩЕНИЕ) ==========
async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Если есть ответ на сообщение и отправитель - админ
    if update.message.reply_to_message and is_admin(update.effective_user.id):
        target_user = update.message.reply_to_message.from_user
        user_id = str(target_user.id)
        user_name = f"@{target_user.username}" if target_user.username else target_user.first_name
    else:
        target_user = update.effective_user
        user_id = str(target_user.id)
        user_name = target_user.first_name
    
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
👤 Игрок: {user_name}
💰 Текущие коины: {user_data['coins']}
🏆 Всего заработано: {total_coins}
📊 Уровень: {current_level['name']} ({progress}%)

📈 Статистика:
📈 Фармов: {user_data['farm_count']}
🎁 От админа: {user_data['admin_gifted']} коинов

{farm_timer}
📈 Подробнее об уровне: /level
"""
    
    await update.message.reply_text(text)

# ========== КОМАНДА /LEVEL ДЛЯ ДРУГОГО ИГРОКА (ОТВЕТ НА СООБЩЕНИЕ) ==========
async def level_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать уровень игрока (можно для себя или для другого при ответе)"""
    # Если есть ответ на сообщение и отправитель - админ
    if update.message.reply_to_message and is_admin(update.effective_user.id):
        target_user = update.message.reply_to_message.from_user
        user_id = str(target_user.id)
        user_name = f"@{target_user.username}" if target_user.username else target_user.first_name
    else:
        target_user = update.effective_user
        user_id = str(target_user.id)
        user_name = target_user.first_name
    
    user_data = db.get_user(user_id)
    
    total_coins = user_data['total_farmed']
    current_level, next_level, progress, coins_needed = get_level_progress(total_coins)
    
    avg_farm = 2.5
    farms_needed = max(1, int(coins_needed / avg_farm)) if coins_needed > 0 else 0
    
    text = f"""
📊 УРОВЕНЬ ИГРОКА

👤 Игрок: {user_name}
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

# ========== КОМАНДА /FARM (ТОЛЬКО ДЛЯ СЕБЯ) ==========
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
        result += "\n💡 Не расстраивайся! Попробуй снова через 4 часа или пиши /level чтобы увидеть прогресс!"
    
    await update.message.reply_text(result)

# ========== КОМАНДА /TOP (РАБОТАЕТ БЕЗ ОТВЕТА) ==========
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

# ========== КОМАНДА /PARTY ==========
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
    chat_title = update.message.chat.title if update.message.chat.title else "этой чат"
    
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

# ========== ОСТАЛЬНЫЕ КОМАНДЫ ==========
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

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = f"""
🆘 ПОМОЩЬ ПО KMEbot

📱 ВАЖНО: Для полного доступа напишите боту /start в ЛС!

📋 ОСНОВНЫЕ КОМАНДЫ:
/farm - коины каждые {FARM_COOLDOWN}ч (0-5 коинов)
/balance - ваш баланс и уровень (админ может ответить на сообщение игрока)
/level - информация об уровне (админ может ответить на сообщение игрока)
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

💰 КОМАНДА /give (только для админа):
1. Ответьте на сообщение игрока
2. Напишите: /give 100
3. Бот выдаст коины и уведомит игрока

📢 КОМАНДЫ АДМИНА:
/announce [текст] - объявление в чат
/broadcast [текст] - рассылка всем игрокам
/compensation - выдать компенсацию всем игрокам

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
    
    # Создаем клавиатуру для админ панели
    keyboard = [
        [
            InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
            InlineKeyboardButton("💰 Компенсация", callback_data="admin_comp")
        ],
        [
            InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast"),
            InlineKeyboardButton("📝 Объявление", callback_data="admin_announce")
        ],
        [
            InlineKeyboardButton("🛍️ Управление", callback_data="admin_manage"),
            InlineKeyboardButton("❌ Закрыть", callback_data="admin_close")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = f"""
👑 ПАНЕЛЬ АДМИНИСТРАТОРА

👥 Игроков в базе: {len(db.data)}
💰 Общий оборот: {sum(user['total_farmed'] for user in db.data.values())}
🔄 Предметов куплено: {sum(len(user['inventory']) for user in db.data.values())}

📊 Выберите действие:
"""
    await update.message.reply_text(text, reply_markup=reply_markup)

# ========== ОБРАБОТЧИК КНОПОК АДМИН ПАНЕЛИ ==========
async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    
    if not is_admin(user.id):
        await query.answer("❌ Только для админа!", show_alert=True)
        return
    
    if query.data == "admin_close":
        await query.delete_message()
        return
    
    elif query.data == "admin_stats":
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
        text += f"Покупок: {total_items}\n"
        
        text += f"\n🏆 ТОП 3 ИГРОКА:\n"
        for i, (player_id, player_data) in enumerate(top_players, 1):
            username = player_data.get('username', '')
            name = f"@{username}" if username else player_data.get('display_name', f"ID:{player_id[:6]}")
            level = get_user_level(player_data['total_farmed'])
            text += f"{i}. {name} - {level['name']} ({player_data['total_farmed']} коинов)\n"
        
        text += f"\n🔄 Последнее обновление: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        
        await query.edit_message_text(text)
        
        # Возвращаем кнопку назад
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Выберите действие:", reply_markup=reply_markup)
    
    elif query.data == "admin_comp":
        text = f"""
💰 ВЫДАЧА КОМПЕНСАЦИИ ВСЕМ ИГРОКАМ

👥 Игроков в базе: {len(db.data)}
💰 Сумма каждому: {COMPENSATION_AMOUNT} коинов
🎁 Всего будет выдано: {len(db.data) * COMPENSATION_AMOUNT} коинов

✅ Команда: /compensation
"""
        await query.edit_message_text(text)
        
        # Возвращаем кнопку назад
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Выберите действие:", reply_markup=reply_markup)
    
    elif query.data == "admin_broadcast":
        text = """
📢 РАССЫЛКА СООБЩЕНИЙ ВСЕМ ИГРОКАМ

✅ Формат: /broadcast [текст сообщения]

📝 Пример:
/broadcast Всем привет! Новый ивент скоро!

⚠️ Сообщение будет отправлено ВСЕМ игрокам в базе!
"""
        await query.edit_message_text(text)
        
        # Возвращаем кнопку назад
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Выберите действие:", reply_markup=reply_markup)
    
    elif query.data == "admin_announce":
        text = """
📢 ПУБЛИЧНОЕ ОБЪЯВЛЕНИЕ В ЧАТЕ

✅ Формат: /announce [текст сообщения]

📝 Пример:
/announce Внимание! Технические работы 20:00-22:00

⚠️ Сообщение будет отправлено в текущий чат для всех участников!
"""
        await query.edit_message_text(text)
        
        # Возвращаем кнопку назад
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Выберите действие:", reply_markup=reply_markup)
    
    elif query.data == "admin_manage":
        text = """
🛍️ УПРАВЛЕНИЕ ПРЕДМЕТАМИ

✅ Команды:
/give [сумма] - выдать коины игроку (ответить на сообщение)
/removeitem [ID] [индекс] - удалить обменянный предмет
/balance - баланс игрока (ответить на сообщение)
/level - уровень игрока (ответить на сообщение)
"""
        await query.edit_message_text(text)
        
        # Возвращаем кнопку назад
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Выберите действие:", reply_markup=reply_markup)
    
    elif query.data == "admin_back":
        # Возвращаем к основной админ панели
        keyboard = [
            [
                InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
                InlineKeyboardButton("💰 Компенсация", callback_data="admin_comp")
            ],
            [
                InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast"),
                InlineKeyboardButton("📝 Объявление", callback_data="admin_announce")
            ],
            [
                InlineKeyboardButton("🛍️ Управление", callback_data="admin_manage"),
                InlineKeyboardButton("❌ Закрыть", callback_data="admin_close")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = f"""
👑 ПАНЕЛЬ АДМИНИСТРАТОРА

👥 Игроков в базе: {len(db.data)}
💰 Общий оборот: {sum(user['total_farmed'] for user in db.data.values())}
🔄 Предметов куплено: {sum(len(user['inventory']) for user in db.data.values())}

📊 Выберите действие:
"""
        await query.edit_message_text(text, reply_markup=reply_markup)

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
    print("🚀 ЗАПУСК KMEbot v7.0 - БЕЗ КРАЖИ + АДМИН ПАНЕЛЬ")
    print("=" * 60)
    print(f"👥 Игроков в базе: {len(db.data)}")
    print(f"📈 Уровней: {len(LEVELS)}")
    print(f"💰 Фарм: 0-5 коинов, {FARM_COOLDOWN}ч КД")
    print(f"🎁 Компенсация: {COMPENSATION_AMOUNT} коинов каждому")
    print(f"📢 Рассылка: /broadcast для админа")
    print(f"📝 Объявления: /announce для чата")
    print(f"🎮 Поиск тимы: /party MMR (0-13000)")
    print(f"🔄 Инвентарь с кнопками обмена")
    print(f"👑 Админ ID: {ADMIN_ID}")
    print("=" * 60)
    print("💎 КОМАНДЫ ПРИ ОТВЕТЕ НА СООБЩЕНИЕ:")
    print("✅ /give [сумма] - выдать коины игроку")
    print("✅ /balance - показать баланс игрока")
    print("✅ /level - показать уровень игрока")
    print("=" * 60)
    print("👑 АДМИН ПАНЕЛЬ КОМАНДЫ:")
    print("• /admin - панель управления")
    print("• /compensation - выдать компенсацию всем")
    print("• /announce - объявление в чат")
    print("• /broadcast - рассылка всем игрокам")
    print("• /stats - полная статистика")
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
    app.add_handler(CommandHandler("announce", announce_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app.add_handler(CommandHandler("compensation", compensation_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("removeitem", removeitem_cmd))
    
    # Обработчики кнопок админ панели и компенсации
    app.add_handler(CallbackQueryHandler(admin_callback_handler, pattern="^admin_"))
    app.add_handler(CallbackQueryHandler(compensation_callback_handler, pattern="^comp_"))
    
    print("✅ Бот запущен и готов к работе!")
    print("👑 Админ панель: /admin - для управления")
    print("📢 Объявление: /announce Привет всем! - для теста")
    print("💰 Компенсация: /compensation - выдать всем по 15 коинов")
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
