import json
import os
import random
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = "8542959870:AAFaEvHTCmnE2yToaxO0f0vzoExRI-F_prY"
ADMIN_USERNAME = "@Matvatok"
FARM_COOLDOWN = 4

SHOP_ITEMS = {
    1: {"name": "🔔 Сигна от Kme_Dota", "price": 50, "description": "Сигна от Kme_Dota"},
    2: {"name": "👥 Сигна от Лсной братвы", "price": 100, "description": "Сигна от Лсной братвы"},  # ← 100 коинов!
    3: {"name": "👑 Модер в чате", "price": 150, "description": "Стать модератором в чате"},
    4: {"name": "🎮 Модер на твиче", "price": 200, "description": "Стать модератором на твиче"},
    5: {"name": "🎵 Трек про тебя", "price": 300, "description": "Заказать трек про себя"},
    6: {"name": "⚔️ Dota+", "price": 400, "description": "Получить Dota+ на месяц"}
}

# СИСТЕМА УРОВНЕЙ
LEVELS = [
    {"name": "👶 Рекрут", "max_coins": 100, "emoji": "👶"},
    {"name": "🛡️ Страж", "max_coins": 200, "emoji": "🛡️"},
    {"name": "⚔️ Рыцарь", "max_coins": 300, "emoji": "⚔️"},
    {"name": "👑 Титян", "max_coins": 400, "emoji": "👑"},
    {"name": "🔥 БОГ", "max_coins": float('inf'), "emoji": "🔥"}  # Для тех, у кого больше 400
]

def get_level_info(total_coins):
    """Определяет уровень игрока по количеству коинов"""
    for level in LEVELS:
        if total_coins <= level["max_coins"]:
            return level
    return LEVELS[-1]  # Если больше всех - возвращаем последний уровень

def calculate_level_progress(total_coins):
    """Рассчитывает прогресс до следующего уровня"""
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
        return current_level, None, 100  # Максимальный уровень
    
    # Прогресс в процентах
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
                'username': '',
                'display_name': '',
                'inventory': [],
                'total_farmed': 0,
                'farm_count': 0,
                'level': '👶 Рекрут'
            }
            self.save_data()
        
        # Обновляем уровень при каждом запросе
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
    
    def add_coins(self, user_id, amount):
        user = self.get_user(user_id)
        user['coins'] += amount
        user['total_farmed'] += amount
        user['farm_count'] += 1
        user['last_farm'] = datetime.now().isoformat()
        
        # Проверяем, повысился ли уровень
        old_level = user['level']
        level_info = get_level_info(user['total_farmed'])
        user['level'] = level_info['name']
        
        self.save_data()
        return user['coins'], old_level != user['level']
    
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
            'bought_at': datetime.now().isoformat()
        })
        self.save_data()
        return True, f"✅ Куплено: {item['name']} за {item['price']} коинов"

db = Database()

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = db.get_user(user.id)
    
    if user.username:
        db.data[str(user.id)]['username'] = user.username
    if user.full_name:
        db.data[str(user.id)]['display_name'] = user.full_name
    db.save_data()
    
    # Получаем информацию об уровне
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
    
    new_balance, level_up = db.add_coins(user_id, coins)
    
    # Получаем информацию об уровне после фарма
    user_data = db.get_user(user_id)
    current_level, next_level, progress = calculate_level_progress(user_data['total_farmed'])
    
    level_info = ""
    if level_up:
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

async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = db.get_user(user.id)
    
    last_time = user_data['last_farm']
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
            timer = f"⏳ До фарма: {hours:02d}:{minutes:02d}:{seconds:02d}\n"
        else:
            timer = "✅ Можно фармить! /farm\n"
    else:
        timer = "✅ Можно фармить! /farm\n"
    
    # Информация об уровне
    current_level, next_level, progress = calculate_level_progress(user_data['total_farmed'])
    
    level_text = f"{current_level['emoji']} Уровень: {current_level['name']}"
    if next_level:
        coins_needed = next_level['max_coins'] - user_data['total_farmed']
        level_text += f"\n📈 До {next_level['emoji']} {next_level['name']}: {coins_needed} коинов ({progress}%)"
    else:
        level_text += "\n🎉 Максимальный уровень достигнут!"
    
    text = f"""
👤 Игрок: {user.first_name}
{level_text}
💰 KMEкоинов: {user_data['coins']}
📊 Фармов: {user_data['farm_count']}
🏆 Всего заработано: {user_data['total_farmed']}

{timer}🛍️ Используйте /shop для покупки
    """
    await update.message.reply_text(text)

async def level_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для просмотра системы уровней"""
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
        # Определяем имя для отображения
        display_name = user_data.get('display_name', '')
        username = user_data.get('username', '')
        
        if display_name:
            name = display_name[:15]  # Обрезаем длинные имена
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
    else:
        text = "📦 ВАШ ИНВЕНТАРЬ 📦\n\n"
        
        for i, item in enumerate(user_data['inventory'], 1):
            bought_date = datetime.fromisoformat(item['bought_at']).strftime("%d.%m.%Y %H:%M")
            text += f"{i}. {item['name']}\n"
            text += f"   💰 Куплено за: {item['price']} коинов\n"
            text += f"   📅 Дата: {bought_date}\n\n"
        
        text += f"📊 Всего покупок: {len(user_data['inventory'])}"
    
    await update.message.reply_text(text)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = f"""
🆘 ПОМОЩЬ ПО KMEbot 🆘

📋 Основные команды:
/farm - получить коины (раз в {FARM_COOLDOWN} часа)
/balance - ваш баланс, уровень и статистика
/top - топ 5 игроков с уровнями
/shop - магазин товаров
/inventory - ваши покупки
/level - информация о системе уровней
/help - эта справка

🛍️ Товары в магазине:
1. 🔔 Сигна от Kme_Dota - 50 коинов
2. 👥 Сигна от Лсной братвы - 100 коинов (Лсная братва - это наши уважаемые и любимые Corzan, Kurbat_Go, Kme_dota)
3. 👑 Модер в чате - 150 коинов
4. 🎮 Модер на твиче - 200 коинов
5. 🎵 Трек про тебя - 300 коинов
6. ⚔️ Dota+ - 400 коинов

🛒 Как покупать:
/buy_1 - купить Сигну от Kme_Dota
/buy_2 - купить Сигну от Лсной братвы
/buy_3 - купить модера в чате
/buy_4 - купить модера на твиче
/buy_5 - купить трек про тебя
/buy_6 - купить Dota+

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

💬 Работа в чатах:
• В группе пишите: /farm@KmeFarmBot
• Или просто /farm (если бот администратор)
• Бот автоматически отвечает на упоминания

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
                f"📊 /balance - ваш баланс и уровень\n"
                f"🛍️ /shop - магазин"
            )

def main():
    print("=" * 50)
    print("🚀 ЗАПУСК KMEbot v4.0 (СИСТЕМА УРОВНЕЙ)")
    print("=" * 50)
    print(f"👥 Загружено игроков: {len(db.data)}")
    print(f"⏳ КД фарма: {FARM_COOLDOWN} часа")
    print(f"💰 Коинов за фарм: 1-5")
    print(f"🎲 Шанс +2: 10% | Шанс -1/-2: 8%")
    print(f"🛍️ Товаров в магазине: {len(SHOP_ITEMS)}")
    print(f"📊 Система уровней: {len(LEVELS)} уровня")
    print("=" * 50)
    print("✅ ПРИ ОБНОВЛЕНИИ КОДА ДАННЫЕ НЕ СБРОСЯТСЯ")
    print("📁 Файл kme_data.json сохраняется отдельно")
    print("=" * 50)
    
    try:
        app = Application.builder()\
            .token(TOKEN)\
            .get_updates_read_timeout(30)\
            .pool_timeout(30)\
            .build()
        
        app.add_handler(CommandHandler("start", start_cmd))
        app.add_handler(CommandHandler("farm", farm_cmd))
        app.add_handler(CommandHandler("balance", balance_cmd))
        app.add_handler(CommandHandler("top", top_cmd))
        app.add_handler(CommandHandler("shop", shop_cmd))
        app.add_handler(CommandHandler("inventory", inventory_cmd))
        app.add_handler(CommandHandler("help", help_cmd))
        app.add_handler(CommandHandler("level", level_cmd))
        
        # Все команды покупки
        for i in range(1, 7):
            app.add_handler(CommandHandler(f"buy_{i}", buy_cmd))
        
        app.add_handler(MessageHandler(
            filters.TEXT & filters.Entity("mention"),
            handle_mention
        ))
        
        print("✅ KMEbot запущен!")
        print("📱 Бот работает в ЛС и чатах")
        print("🏆 Добавлена система уровней")
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
