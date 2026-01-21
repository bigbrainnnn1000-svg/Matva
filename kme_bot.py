import json
import os
import random
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ТОКЕН (ЗАМЕНИЛ НА НОВЫЙ, СТАРЫЙ БЫЛ СКОМПРОМЕТИРОВАН)
TOKEN = "8542959870:AAFaEvHTCmnE2yToaxO0f0vzoExRI-F_prY"
ADMIN_USERNAME = "@Matvatok"
FARM_COOLDOWN = 4

SHOP_ITEMS = {
    1: {"name": "Модер в чате", "price": 150, "description": "Стать модератором в чате"},
    2: {"name": "Модер на твиче", "price": 200, "description": "Стать модератором на твиче"},
    3: {"name": "Dota+", "price": 300, "description": "Получить Dota+ на месяц"}
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
                'username': '',
                'inventory': [],
                'total_farmed': 0,
                'farm_count': 0
            }
            self.save_data()
        return self.data[user_id]
    
    def can_farm(self, user_id):
        user = self.get_user(user_id)
        if not user['last_farm']:
            return True, "Можно фармить!"
        
        last = datetime.fromisoformat(user['last_farm'])
        now = datetime.now()
        cooldown = timedelta(hours=FARM_COOLDOWN)
        
        if now - last >= cooldown:
            return True, "Можно фармить!"
        else:
            wait = cooldown - (now - last)
            hours = int(wait.total_seconds() // 3600)
            minutes = int((wait.total_seconds() % 3600) // 60)
            return False, f"Ждите {hours}ч {minutes}м"
    
    def add_coins(self, user_id, amount):
        user = self.get_user(user_id)
        user['coins'] += amount
        user['total_farmed'] += amount
        user['farm_count'] += 1
        user['last_farm'] = datetime.now().isoformat()
        self.save_data()
        return user['coins']
    
    def buy_item(self, user_id, item_id):
        user = self.get_user(user_id)
        
        if item_id not in SHOP_ITEMS:
            return False, "Такого товара нет!"
        
        item = SHOP_ITEMS[item_id]
        
        if user['coins'] < item['price']:
            return False, f"Недостаточно коинов! Нужно {item['price']}, а у вас {user['coins']}"
        
        user['coins'] -= item['price']
        user['inventory'].append({
            'id': item_id,
            'name': item['name'],
            'price': item['price'],
            'bought_at': datetime.now().isoformat()
        })
        self.save_data()
        return True, f"Куплено: {item['name']} за {item['price']} коинов"

db = Database()

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = db.get_user(user.id)
    
    if user.username:
        db.data[str(user.id)]['username'] = user.username
        db.save_data()
    
    text = f"""
🎮 Добро пожаловать в KMEbot! 🎮

👤 Игрок: {user.first_name}
💰 Баланс: {user_data['coins']} KMEкоинов
📊 Фармов: {user_data['farm_count']}
🏆 Всего заработано: {user_data['total_farmed']}

📋 Основные команды:
/farm - получить коины (раз в {FARM_COOLDOWN} часа)
/balance - проверить баланс
/top - топ игроков (5 лучших)
/shop - магазин товаров
/inventory - ваши покупки
/help - помощь

🎲 НОВАЯ СИСТЕМА ФАРМА:
• Базово: 1-5 коинов
• 🎉 УДАЧА (+2 коина): 10%
• 😕 НЕУДАЧА (-1 или -2 коина): 8%
• 👍 Старый бонус (+1): 2%

💬 РАБОТА В ЧАТАХ:
• В группе пишите: /farm@имябота
• Или просто /farm (если бот администратор)
    """
    await update.message.reply_text(text)

async def farm_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    can_farm, msg = db.can_farm(user_id)
    
    if not can_farm:
        await update.message.reply_text(msg)
        return
    
    # Базовое количество коинов
    coins = random.randint(1, 5)
    bonus_msg = ""
    emoji = "💰"
    
    # НОВЫЕ ШАНСЫ:
    chance = random.random()  # число от 0 до 1
    
    if chance < 0.10:  # 10% шанс на +2 коина
        bonus = 2
        coins += bonus
        bonus_msg = f"\n🎉 УДАЧА! +{bonus} дополнительных коина!"
        emoji = "🎉"
    elif chance < 0.18:  # 8% шанс на штраф (10% + 8% = 18%)
        penalty = random.choice([-1, -2])
        original_coins = coins
        coins = max(0, coins + penalty)  # Не уходим в минус
        if penalty == -1:
            bonus_msg = f"\n😕 НЕУДАЧА... -1 коин ({original_coins} → {coins})"
            emoji = "😕"
        else:
            bonus_msg = f"\n😞 ПЕЧАЛЬ... -2 коина ({original_coins} → {coins})"
            emoji = "😞"
    elif chance < 0.20:  # 2% шанс на +1 коин (старый бонус)
        bonus = 1
        coins += bonus
        bonus_msg = f"\n👍 БОНУС! +{bonus} коин!"
        emoji = "👍"
    
    new_balance = db.add_coins(user_id, coins)
    
    result = f"""
{emoji} Фарм завершен! {emoji}

Получено: {coins} KMEкоинов{bonus_msg}
💰 Новый баланс: {new_balance} KMEкоинов
🏆 Всего заработано: {db.get_user(user_id)['total_farmed']}

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
            timer = f"⏳ До фарма: {hours}ч {minutes}м\n"
        else:
            timer = "✅ Можно фармить! /farm\n"
    else:
        timer = "✅ Можно фармить! /farm\n"
    
    text = f"""
👤 Игрок: {user.first_name}
💰 KMEкоинов: {user_data['coins']}
📊 Фармов: {user_data['farm_count']}
🏆 Всего заработано: {user_data['total_farmed']}

{timer}🛍️ Используйте /shop для покупки
    """
    await update.message.reply_text(text)

async def top_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not db.data:
        await update.message.reply_text("Пока нет игроков!")
        return
    
    top_users = sorted(
        db.data.items(),
        key=lambda x: x[1].get('total_farmed', 0),
        reverse=True
    )[:5]
    
    text = "🏆 ТОП 5 ИГРОКОВ KMEbot 🏆\n\n"
    
    for i, (user_id, user_data) in enumerate(top_users, 1):
        username = user_data.get('username', f'Игрок{user_id[-4:]}')
        if not username.startswith('@'):
            username = f"@{username}" if username else f"Игрок{user_id[-4:]}"
        
        coins = user_data.get('total_farmed', 0)
        medal = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][i-1]
        text += f"{medal} {username}: {coins} коинов\n"
    
    await update.message.reply_text(text)

async def shop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = db.get_user(user.id)
    
    text = "🛍️ МАГАЗИН KMEbot 🛍️\n\n"
    
    for item_id, item in SHOP_ITEMS.items():
        text += f"🔸 {item_id}. {item['name']}\n"
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
            text += f"📦 {i}. {item['name']}\n"
            text += f"   💰 Куплено за: {item['price']} коинов\n"
            text += f"   📅 Дата: {bought_date}\n\n"
        
        text += f"📊 Всего покупок: {len(user_data['inventory'])}"
    
    await update.message.reply_text(text)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = f"""
🆘 ПОМОЩЬ ПО KMEbot 🆘

📋 Основные команды:
/farm - получить коины (раз в {FARM_COOLDOWN} часа)
/balance - ваш баланс и статистика
/top - топ 5 игроков
/shop - магазин товаров
/inventory - ваши покупки
/help - эта справка

🛍️ Товары в магазине:
1. 🛡️ Модер в чате - 150 коинов
2. 🎮 Модер на твиче - 200 коинов  
3. ⚔️ Dota+ - 300 коинов

🛒 Как покупать:
/buy_1 - купить модера в чате
/buy_2 - купить модера на твиче
/buy_3 - купить Dota+

🎲 НОВАЯ СИСТЕМА ФАРМА:
• Базово: 1-5 коинов
• 🎉 УДАЧА (+2 коина): 10% шанс
• 😕 НЕУДАЧА (-1 или -2 коина): 8% шанс
• 👍 Старый бонус (+1): 2% шанс

💬 РАБОТА В ЧАТАХ:
• В группе пишите: /farm@имябота
• Или просто /farm (если бот администратор)
• Бот автоматически отвечает на упоминания

📊 Статистика:
• Все данные сохраняются
• Топ игроков обновляется в реальном времени
• Инвентарь хранится постоянно

👤 Создатель: {ADMIN_USERNAME}
❓ Проблемы/предложения: пишите {ADMIN_USERNAME}
    """
    await update.message.reply_text(text)

# Обработчик для сообщений в чатах
async def handle_mention(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.text:
        # Проверяем, упомянут ли бот
        if context.bot.username and f"@{context.bot.username}" in update.message.text:
            await update.message.reply_text(
                f"👋 Да, я здесь, {update.effective_user.first_name}!\n"
                f"💬 Используйте команды:\n"
                f"💰 /farm - получить коины\n"
                f"📊 /balance - ваш баланс\n"
                f"🛍️ /shop - магазин"
            )

def main():
    print("=" * 50)
    print("🚀 ЗАПУСК KMEbot v2.0 (ОБНОВЛЁННЫЙ)")
    print("=" * 50)
    print(f"👥 Загружено игроков: {len(db.data)}")
    print(f"⏳ КД фарма: {FARM_COOLDOWN} часа")
    print(f"💰 Коинов за фарм: 1-5")
    print(f"🎉 Шанс +2: 10% | 😕 Шанс -1/-2: 8%")
    print(f"🛍️ Товаров в магазине: {len(SHOP_ITEMS)}")
    print("=" * 50)
    
    try:
        # Важное изменение для работы в группах:
        app = Application.builder()\
            .token(TOKEN)\
            .get_updates_read_timeout(30)\
            .pool_timeout(30)\
            .build()
        
        # Команды (работают и в ЛС, и в группах)
        app.add_handler(CommandHandler("start", start_cmd))
        app.add_handler(CommandHandler("farm", farm_cmd))
        app.add_handler(CommandHandler("balance", balance_cmd))
        app.add_handler(CommandHandler("top", top_cmd))
        app.add_handler(CommandHandler("shop", shop_cmd))
        app.add_handler(CommandHandler("inventory", inventory_cmd))
        app.add_handler(CommandHandler("help", help_cmd))
        
        # Команды покупки
        app.add_handler(CommandHandler("buy_1", buy_cmd))
        app.add_handler(CommandHandler("buy_2", buy_cmd))
        app.add_handler(CommandHandler("buy_3", buy_cmd))
        
        # Обработчик упоминаний в чатах (для реакции на @имябота)
        app.add_handler(MessageHandler(
            filters.TEXT & filters.Entity("mention"),
            handle_mention
        ))
        
        print("✅ KMEbot запущен!")
        print("📱 Бот работает в ЛС и чатах")
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

