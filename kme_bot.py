import json
import os
import random
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler

TOKEN = "8542959870:AAFaEvHTCmnE2yToaxO0f0vzoExRI-F_prY"
ADMIN_ID = 6443845944
ADMIN_USERNAME = "@Matvatok"
FARM_COOLDOWN = 4  # часа
STEAL_COOLDOWN = 30  # минут между кражами
STEAL_AMOUNT = 10   # коинов за кражу
STEAL_CHANCE = 50   # 50% шанс успеха

SHOP_ITEMS = {
    1: {"name": "🔔 Сигна от Kme_Dota", "price": 50, "description": "Сигна от Kme_Dota"},
    2: {"name": "👥 Сигна от Лсной братвы", "price": 100, "description": "Сигна от Лсной братвы"},
    3: {"name": "👑 Модер в чате", "price": 150, "description": "Стать модератором в чате"},
    4: {"name": "🎮 Модер на твиче", "price": 200, "description": "Стать модератором на твиче"},
    5: {"name": "🎵 Трек про тебя", "price": 300, "description": "Заказать трек про себя"},
    6: {"name": "⚔️ Dota+", "price": 400, "description": "Получить Dota+ на месяц"}
}

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
        
        # Проверяем что у жертвы есть деньги
        if victim['coins'] < STEAL_AMOUNT:
            return False, "❌ У жертвы нет денег!", 0, 0
        
        # Обновляем время кражи у вора
        thief['last_steal'] = datetime.now().isoformat()
        
        # Шанс 50%
        if random.randint(1, 100) <= STEAL_CHANCE:
            # Успешная кража
            success = self.remove_coins(victim_id, STEAL_AMOUNT)
            if not success[0]:
                return False, "❌ Ошибка при краже!", 0, 0
            
            # Добавляем вору
            self.add_coins(thief_id, STEAL_AMOUNT, from_farm=False)
            
            # Статистика
            thief['steal_success'] += 1
            thief['stolen_total'] += STEAL_AMOUNT
            victim['lost_total'] += STEAL_AMOUNT
            
            return True, f"✅ Успешно украдено {STEAL_AMOUNT} коинов!", STEAL_AMOUNT, 0
        else:
            # Неудачная кража
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
            'bought_at': datetime.now().isoformat()
        })
        self.save_data()
        return True, f"✅ Куплено: {item['name']} за {item['price']} коинов"

db = Database()

def is_admin(user_id):
    return user_id == ADMIN_ID

# ========== АДМИН ПАНЕЛЬ ==========
async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только для админа!")
        return
    
    keyboard = [
        [InlineKeyboardButton("💰 Выдать коины", callback_data="admin_give")],
        [InlineKeyboardButton("📊 Статистика бота", callback_data="admin_stats")],
        [InlineKeyboardButton("👤 Найти игрока", callback_data="admin_find")],
        [InlineKeyboardButton("📢 Рассылка всем", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🗑️ Удалить игрока", callback_data="admin_delete")],
        [InlineKeyboardButton("❌ Закрыть", callback_data="admin_close")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "👑 АДМИН ПАНЕЛЬ KMEbot\n\n"
        "Выберите действие:",
        reply_markup=reply_markup
    )

async def admin_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ Нет доступа!")
        return
    
    data = query.data
    
    if data == "admin_give":
        await query.edit_message_text(
            "💰 ВЫДАЧА КОИНОВ\n\n"
            "✅ ЛУЧШИЙ СПОСОБ:\n"
            "1. Ответьте на сообщение игрока\n"
            "2. Напишите: /give 100\n\n"
            "✅ ЧЕРЕЗ USERNAME:\n"
            "/give @username 100\n\n"
            "✅ ЧЕРЕЗ ID:\n"
            "/give 123456789 100\n\n"
            "📊 Игрок получит уведомление в ЛС"
        )
    
    elif data == "admin_stats":
        total_users = len(db.data)
        total_coins = sum(user['coins'] for user in db.data.values())
        total_farmed = sum(user['total_farmed'] for user in db.data.values())
        total_gifted = sum(user.get('admin_gifted', 0) for user in db.data.values())
        
        # Топ-3 игрока
        top_users = sorted(
            db.data.items(),
            key=lambda x: x[1]['total_farmed'],
            reverse=True
        )[:3]
        
        top_text = "🏆 ТОП-3 ИГРОКА:\n"
        for i, (user_id, user_data) in enumerate(top_users, 1):
            name = user_data.get('username', f"ID:{user_id[:6]}")
            coins = user_data['total_farmed']
            top_text += f"{i}. @{name}: {coins} коинов\n"
        
        await query.edit_message_text(
            f"📊 СТАТИСТИКА БОТА\n\n"
            f"👥 Всего игроков: {total_users}\n"
            f"💰 Всего коинов: {total_coins}\n"
            f"🏆 Всего заработано: {total_farmed}\n"
            f"🎁 Выдано админом: {total_gifted}\n\n"
            f"{top_text}"
        )
    
    elif data == "admin_find":
        await query.edit_message_text(
            "👤 ПОИСК ИГРОКА\n\n"
            "Формат: /find @username\n"
            "Или: /find 123456789\n\n"
            "Пример:\n"
            "/find @shicds1\n"
            "/find 6443845944\n\n"
            "📌 Покажет баланс и статистику"
        )
    
    elif data == "admin_broadcast":
        await query.edit_message_text(
            "📢 РАССЫЛКА ВСЕМ\n\n"
            "Формат: /broadcast ваш_текст\n\n"
            "Пример:\n"
            "/broadcast Привет! Новая функция в боте!\n\n"
            "⚠️ Сообщение получат ВСЕ зарегистрированные игроки"
        )
    
    elif data == "admin_delete":
        await query.edit_message_text(
            "🗑️ УДАЛЕНИЕ ИГРОКА\n\n"
            "Формат: /delete @username\n"
            "Или: /delete 123456789\n\n"
            "Пример:\n"
            "/delete @username\n"
            "/delete 123456789\n\n"
            "⚠️ Удалит все данные игрока безвозвратно!"
        )
    
    elif data == "admin_close":
        await query.delete_message()

# ========== КОМАНДА /GIVE ==========
async def give_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только для админа!")
        return
    
    # СПОСОБ 1: Ответ на сообщение
    if update.message.reply_to_message:
        if not context.args:
            await update.message.reply_text("❌ Укажите количество: /give 100")
            return
        
        try:
            amount = int(context.args[0])
            if amount <= 0:
                await update.message.reply_text("❌ Число должно быть больше 0!")
                return
        except:
            await update.message.reply_text("❌ Введите число!")
            return
        
        target_user = update.message.reply_to_message.from_user
        target_user_id = str(target_user.id)
        target_data = db.get_user(target_user_id)
        
        # Сохраняем данные если их нет
        if target_user.username and not target_data.get('username'):
            target_data['username'] = target_user.username
        if target_user.full_name and not target_data.get('display_name'):
            target_data['display_name'] = target_user.full_name
        db.save_data()
        
        new_balance = db.add_coins(target_user_id, amount, from_farm=False, from_admin=True)
        
        # Формируем ответ
        target_name = f"@{target_user.username}" if target_user.username else target_user.first_name
        
        result = (
            f"✅ ВЫДАНО {amount} КОИНОВ!\n\n"
            f"👤 Игрок: {target_name}\n"
            f"💰 Баланс: {new_balance}\n"
            f"🎁 Всего выдано: {target_data['admin_gifted'] + amount}"
        )
        
        # Уведомляем игрока
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=(
                    f"🎉 АДМИН ВЫДАЛ ВАМ КОИНЫ!\n\n"
                    f"💰 +{amount} KMEкоинов\n"
                    f"🏦 Баланс: {new_balance}\n\n"
                    f"💬 Используйте /shop для покупок"
                )
            )
            result += "\n\n📨 Игрок получил уведомление!"
        except:
            result += "\n\n⚠️ Не удалось уведомить игрока"
        
        await update.message.reply_text(result)
        return
    
    # СПОСОБ 2: Через аргументы
    if len(context.args) != 2:
        await update.message.reply_text(
            "❌ Неправильный формат!\n\n"
            "✅ СПОСОБ 1 (лучший):\n"
            "Ответьте на сообщение + /give 100\n\n"
            "✅ СПОСОБ 2:\n"
            "/give @username 100\n"
            "Или: /give 123456789 100"
        )
        return
    
    target = context.args[0]
    try:
        amount = int(context.args[1])
        if amount <= 0:
            await update.message.reply_text("❌ Число должно быть больше 0!")
            return
    except:
        await update.message.reply_text("❌ Введите число!")
        return
    
    # Поиск игрока
    target_user_id = None
    target_name = target
    
    if target.isdigit():
        if target in db.data:
            target_user_id = target
            target_name = f"ID:{target[:6]}"
    else:
        username = target.lstrip('@').lower()
        for uid, user_data in db.data.items():
            if user_data.get('username', '').lower() == username:
                target_user_id = uid
                target_name = f"@{user_data['username']}"
                break
    
    if not target_user_id:
        await update.message.reply_text(f"❌ Игрок {target} не найден!")
        return
    
    new_balance = db.add_coins(target_user_id, amount, from_farm=False, from_admin=True)
    
    await update.message.reply_text(
        f"✅ Выдано {amount} коинов!\n"
        f"👤 Игрок: {target_name}\n"
        f"💰 Баланс: {new_balance}"
    )

# ========== КОМАНДА /STEAL ==========
async def steal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    
    # Проверка КД
    can_steal, msg = db.can_steal(user_id)
    if not can_steal:
        await update.message.reply_text(msg)
        return
    
    if not context.args:
        await update.message.reply_text(
            "🎯 КОМАНДА КРАЖИ\n\n"
            "✅ Формат: /steal @username\n"
            "Пример: /steal @shicds1\n\n"
            f"💰 Сумма: {STEAL_AMOUNT} коинов\n"
            f"🎲 Шанс: {STEAL_CHANCE}%\n"
            f"⏳ КД: {STEAL_COOLDOWN} минут\n\n"
            "⚠️ Можно красть у любого зарегистрированного игрока"
        )
        return
    
    target = context.args[0]
    
    # Поиск жертвы
    victim_id = None
    victim_name = target
    
    if target.isdigit():
        if target in db.data and target != user_id:
            victim_id = target
    else:
        username = target.lstrip('@').lower()
        for uid, user_data in db.data.items():
            if user_data.get('username', '').lower() == username and uid != user_id:
                victim_id = uid
                victim_name = f"@{user_data['username']}"
                break
    
    if not victim_id:
        await update.message.reply_text("❌ Цель не найдена или нельзя красть у себя!")
        return
    
    # Пытаемся украсть
    success, message, stolen, lost = db.steal_attempt(user_id, victim_id)
    
    thief_data = db.get_user(user_id)
    
    if success:
        result = (
            f"🎯 УСПЕШНАЯ КРАЖА!\n\n"
            f"👤 Жертва: {victim_name}\n"
            f"💰 Украдено: {stolen} коинов\n"
            f"🏦 Ваш баланс: {thief_data['coins']}\n"
            f"📊 Успешных краж: {thief_data['steal_success']}\n\n"
            f"⏳ Следующая попытка через {STEAL_COOLDOWN} минут"
        )
    else:
        result = (
            f"🎯 НЕУДАЧНАЯ КРАЖА\n\n"
            f"👤 Жертва: {victim_name}\n"
            f"❌ {message}\n"
            f"🏦 Ваш баланс: {thief_data['coins']}\n"
            f"📊 Неудачных попыток: {thief_data['steal_failed']}\n\n"
            f"⏳ Следующая попытка через {STEAL_COOLDOWN} минут"
        )
    
    await update.message.reply_text(result)

# ========== ДРУГИЕ АДМИН КОМАНДЫ ==========
async def find_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только для админа!")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Укажите игрока: /find @username")
        return
    
    target = context.args[0]
    found_users = []
    
    if target.isdigit():
        if target in db.data:
            found_users.append((target, db.data[target]))
    else:
        username = target.lstrip('@').lower()
        for uid, user_data in db.data.items():
            if username in user_data.get('username', '').lower():
                found_users.append((uid, user_data))
    
    if not found_users:
        await update.message.reply_text("❌ Игрок не найден!")
        return
    
    result = "👤 НАЙДЕННЫЕ ИГРОКИ:\n\n"
    
    for uid, user_data in found_users[:3]:  # Показываем первые 3
        username = user_data.get('username', 'Нет username')
        display_name = user_data.get('display_name', 'Нет имени')
        coins = user_data['coins']
        total_farmed = user_data['total_farmed']
        admin_gifted = user_data.get('admin_gifted', 0)
        
        result += f"👤 @{username}\n"
        result += f"🆔 ID: {uid}\n"
        result += f"👁️ Имя: {display_name}\n"
        result += f"💰 Баланс: {coins}\n"
        result += f"🏆 Заработано: {total_farmed}\n"
        result += f"🎁 От админа: {admin_gifted}\n"
        result += f"📊 Фармов: {user_data['farm_count']}\n"
        result += "─" * 20 + "\n"
    
    await update.message.reply_text(result)

async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только для админа!")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Укажите текст: /broadcast Ваш текст")
        return
    
    message = ' '.join(context.args)
    total_users = len(db.data)
    sent = 0
    failed = 0
    
    await update.message.reply_text(f"📢 Рассылка начата... ({total_users} получателей)")
    
    for user_id in db.data.keys():
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"📢 ОТ АДМИНА:\n\n{message}"
            )
            sent += 1
        except:
            failed += 1
    
    await update.message.reply_text(
        f"📢 РАССЫЛКА ЗАВЕРШЕНА\n\n"
        f"✅ Отправлено: {sent}\n"
        f"❌ Не отправлено: {failed}\n"
        f"👥 Всего получателей: {total_users}"
    )

async def delete_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только для админа!")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Укажите игрока: /delete @username")
        return
    
    target = context.args[0]
    deleted = False
    
    if target.isdigit() and target in db.data:
        del db.data[target]
        db.save_data()
        deleted = True
        target_name = f"ID:{target[:6]}"
    else:
        username = target.lstrip('@').lower()
        for uid, user_data in db.data.items():
            if user_data.get('username', '').lower() == username:
                del db.data[uid]
                db.save_data()
                deleted = True
                target_name = f"@{user_data['username']}"
                break
    
    if deleted:
        await update.message.reply_text(f"✅ Игрок {target_name} удалён!")
    else:
        await update.message.reply_text("❌ Игрок не найден!")

# ========== ОСНОВНЫЕ КОМАНДЫ ==========
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = db.get_user(user.id)
    
    # Сохраняем данные
    if user.username:
        user_data['username'] = user.username
    if user.full_name:
        user_data['display_name'] = user.full_name
    db.save_data()
    
    text = f"""
🎮 Добро пожаловать в KMEbot!

👤 Игрок: {user.first_name}
💰 Баланс: {user_data['coins']} коинов
📊 Фармов: {user_data['farm_count']}
🏆 Всего заработано: {user_data['total_farmed']}

📋 ОСНОВНЫЕ КОМАНДЫ:
/farm - получить коины (раз в {FARM_COOLDOWN}ч)
/steal @user - украсть {STEAL_AMOUNT} коинов
/balance - ваш баланс и статистика
/top - топ игроков
/shop - магазин товаров
/inventory - ваши покупки
/help - помощь

🎯 КОМАНДА КРАЖИ:
• /steal @username
• Украсть {STEAL_AMOUNT} коинов
• Шанс успеха: {STEAL_CHANCE}%
• КД: {STEAL_COOLDOWN} минут

💎 КАК ПОЛУЧИТЬ КОИНЫ ОТ АДМИНА:
Админ отвечает на ваше сообщение и пишет:
/give 100
    """
    await update.message.reply_text(text)

async def farm_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    
    can_farm, msg = db.can_farm(user_id)
    if not can_farm:
        await update.message.reply_text(msg)
        return
    
    coins = random.randint(1, 5)
    bonus_msg = ""
    emoji = "💰"
    
    chance = random.random()
    if chance < 0.10:
        coins += 2
        bonus_msg = f"\n🎉 УДАЧА! +2 коина!"
        emoji = "🎉"
    elif chance < 0.18:
        penalty = random.choice([-1, -2])
        original = coins
        coins = max(0, coins + penalty)
        bonus_msg = f"\n😕 Неудача... -{abs(penalty)} коин ({original} → {coins})"
        emoji = "😕"
    
    new_balance = db.add_coins(user_id, coins)
    
    result = f"""
{emoji} Фарм завершен!

Получено: {coins} коинов{bonus_msg}
💰 Баланс: {new_balance}
🏆 Всего: {db.get_user(user_id)['total_farmed']}

⏳ Следующий через {FARM_COOLDOWN}ч
    """
    await update.message.reply_text(result)

async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    user_data = db.get_user(user_id)
    
    # Время до фарма
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
    
    # Время до кражи
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
            steal_timer = "✅ Можно красть! /steal @user\n"
    else:
        steal_timer = "✅ Можно красть! /steal @user\n"
    
    text = f"""
👤 Игрок: {user.first_name}
💰 Коин: {user_data['coins']}
📊 Фармов: {user_data['farm_count']}
🏆 Всего: {user_data['total_farmed']}

🎯 Статистика кражи:
✅ Успешно: {user_data['steal_success']}
❌ Провалов: {user_data['steal_failed']}
💰 Украдено: {user_data['stolen_total']}
💸 Потеряно: {user_data['lost_total']}

{farm_timer}{steal_timer}🛍️ /shop - магазин
    """
    await update.message.reply_text(text)

async def top_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not db.data:
        await update.message.reply_text("📭 Нет игроков!")
        return
    
    top_users = sorted(
        db.data.items(),
        key=lambda x: x[1]['total_farmed'],
        reverse=True
    )[:5]
    
    text = "🏆 ТОП 5 ИГРОКОВ 🏆\n\n"
    
    for i, (user_id, user_data) in enumerate(top_users, 1):
        username = user_data.get('username', '')
        if username:
            name = f"@{username}"
        else:
            name = user_data.get('display_name', f"ID:{user_id[:6]}")
        
        coins = user_data['total_farmed']
        medal = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][i-1]
        text += f"{medal} {name}: {coins} коинов\n"
    
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
    
    text += f"💰 Ваш баланс: {user_data['coins']} коинов\n"
    text += "🛒 Для покупки напишите /buy_номер"
    
    await update.message.reply_text(text)

async def buy_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    command = update.message.text
    
    try:
        item_id = int(command.split('_')[1])
    except:
        await update.message.reply_text("❌ Неправильный формат! /buy_номер")
        return
    
    success, msg = db.buy_item(str(user.id), item_id)
    
    if success:
        user_data = db.get_user(str(user.id))
        msg += f"\n💰 Остаток: {user_data['coins']} коинов"
    
    await update.message.reply_text(msg)

async def inventory_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = db.get_user(str(update.effective_user.id))
    
    if not user_data['inventory']:
        await update.message.reply_text("📦 Инвентарь пуст\n🛍️ /shop")
        return
    
    text = "📦 ВАШ ИНВЕНТАРЬ\n\n"
    
    for i, item in enumerate(user_data['inventory'], 1):
        date = datetime.fromisoformat(item['bought_at']).strftime("%d.%m")
        text += f"{i}. {item['name']}\n"
        text += f"   💰 Цена: {item['price']} коинов\n"
        text += f"   📝 {item['description']}\n"
        text += f"   📅 Куплено: {date}\n\n"
    
    text += f"📊 Всего покупок: {len(user_data['inventory'])}"
    await update.message.reply_text(text)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = f"""
🆘 ПОМОЩЬ ПО KMEbot

📋 ОСНОВНЫЕ КОМАНДЫ:
/farm - коины каждые {FARM_COOLDOWN}ч
/steal @user - украсть {STEAL_AMOUNT} коинов
/balance - ваш баланс и статистика
/top - топ игроков
/shop - магазин товаров
/inventory - ваши покупки
/help - эта справка

🎯 КОМАНДА КРАЖИ:
• /steal @username
• Шанс успеха: {STEAL_CHANCE}%
• КД: {STEAL_COOLDOWN} минут
• Сумма: {STEAL_AMOUNT} коинов

🛍️ ТОВАРЫ В МАГАЗИНЕ:
1. 🔔 Сигна от Kme_Dota - 50 коинов
2. 👥 Сигна от Лсной братвы - 100 коинов
3. 👑 Модер в чате - 150 коинов
4. 🎮 Модер на твиче - 200 коинов
5. 🎵 Трек про тебя - 300 коинов
6. ⚔️ Dota+ - 400 коинов

💰 КАК ПОЛУЧИТЬ КОИНЫ ОТ АДМИНА:
Админ отвечает на ваше сообщение и пишет:
/give 100

👑 АДМИН-КОМАНДЫ (только для создателя):
/admin - панель администратора
/give @user N - выдать коины
/find @user - найти игрока
/broadcast текст - рассылка всем
/delete @user - удалить игрока

👤 Создатель: {ADMIN_USERNAME}
    """
    await update.message.reply_text(text)

# ========== ЗАПУСК БОТА ==========
def main():
    print("=" * 50)
    print("🚀 ЗАПУСК KMEbot v3.0")
    print("=" * 50)
    print(f"👥 Игроков: {len(db.data)}")
    print(f"⏳ Фарм: 1-5 коинов, {FARM_COOLDOWN}ч КД")
    print(f"🎯 Кража: {STEAL_AMOUNT} коинов, {STEAL_CHANCE}% шанс, {STEAL_COOLDOWN}мин КД")
    print(f"🛍️ Товаров: {len(SHOP_ITEMS)} (включая Dota+ и Трек)")
    print(f"👑 Админ ID: {ADMIN_ID}")
    print("=" * 50)
    print("✅ ВСЁ РАБОТАЕТ:")
    print("• /give (ответ на сообщение)")
    print("• /steal @user")
    print("• Полная админ-панель /admin")
    print("=" * 50)
    
    app = Application.builder().token(TOKEN).build()
    
    # Основные команды
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("farm", farm_cmd))
    app.add_handler(CommandHandler("steal", steal_cmd))
    app.add_handler(CommandHandler("balance", balance_cmd))
    app.add_handler(CommandHandler("top", top_cmd))
    app.add_handler(CommandHandler("shop", shop_cmd))
    app.add_handler(CommandHandler("inventory", inventory_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    
    # Админ команды
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("give", give_cmd))
    app.add_handler(CommandHandler("find", find_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app.add_handler(CommandHandler("delete", delete_cmd))
    
    # Кнопки админ-панели
    app.add_handler(CallbackQueryHandler(admin_button_handler, pattern="^admin_"))
    
    # Команды покупки
    for i in range(1, 7):
        app.add_handler(CommandHandler(f"buy_{i}", buy_cmd))
    
    print("✅ Бот запущен!")
    print("🛑 Ctrl+C для остановки")
    print("=" * 50)
    
    app.run_polling()

if __name__ == "__main__":
    main()
