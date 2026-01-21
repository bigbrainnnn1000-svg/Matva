import json
import os
import random
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = "8542959870:AAFaEvHTCmnE2yToaxO0f0vzoExRI-F_prY"
ADMIN_ID = 6443845944
ADMIN_USERNAME = "@Matvatok"
FARM_COOLDOWN = 4

SHOP_ITEMS = {
    1: {"name": "🔔 Сигна от Kme_Dota", "price": 50, "description": "Сигна от Kme_Dota"},
    2: {"name": "👥 Сигна от Лсной братвы", "price": 100, "description": "Сигна от Лсной братвы"},
    3: {"name": "👑 Модер в чате", "price": 150, "description": "Стать модератором в чате"},
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
                'display_name': '',
                'inventory': [],
                'total_farmed': 0,
                'farm_count': 0
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
            return False, f"⏳ Ждите {hours}ч {minutes}м"
    
    def add_coins(self, user_id, amount, from_farm=True):
        user = self.get_user(user_id)
        user['coins'] += amount
        if from_farm:
            user['total_farmed'] += amount
            user['farm_count'] += 1
            user['last_farm'] = datetime.now().isoformat()
        self.save_data()
        return user['coins']
    
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

def is_admin(user_id):
    return user_id == ADMIN_ID

# ========== КОМАНДА /GIVE (ОТВЕТ НА СООБЩЕНИЕ) ==========
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
    new_balance = db.add_coins(target_user_id, amount, from_farm=False)
    
    # Формируем имя для отображения
    if target_user.username:
        target_name = f"@{target_user.username}"
    else:
        target_name = target_user.first_name
    
    # ОТВЕТ АДМИНУ
    result_admin = (
        f"✅ ВЫДАНО {amount} КОИНОВ!\n\n"
        f"👤 Игрок: {target_name}\n"
        f"💰 Баланс: {new_balance} коинов\n"
        f"🏆 Всего выдано: {target_data['total_farmed'] + amount}"
    )
    
    # УВЕДОМЛЕНИЕ ИГРОКУ (в ЛС)
    try:
        await context.bot.send_message(
            chat_id=target_user_id,
            text=(
                f"🎉 АДМИН ВЫДАЛ ВАМ КОИНЫ!\n\n"
                f"💰 +{amount} KMEкоинов\n"
                f"🏦 Ваш баланс: {new_balance}\n\n"
                f"💬 Используйте:\n"
                f"• /farm - фармить коины\n"
                f"• /shop - магазин\n"
                f"• /balance - проверить баланс"
            )
        )
        result_admin += "\n\n📨 Игрок получил уведомление в ЛС!"
    except:
        result_admin += "\n\n⚠️ Не удалось отправить уведомление игроку"
    
    await update.message.reply_text(result_admin)

# ========== ОСНОВНЫЕ КОМАНДЫ ==========
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = db.get_user(user.id)
    
    # Сохраняем данные пользователя
    if user.username:
        user_data['username'] = user.username
    if user.full_name:
        user_data['display_name'] = user.full_name
    db.save_data()
    
    text = f"""
🎮 KMEbot - Игровой бот с коинами!

👤 Игрок: {user.first_name}
💰 Баланс: {user_data['coins']} KMEкоинов
📊 Фармов: {user_data['farm_count']}
🏆 Всего заработано: {user_data['total_farmed']}

📋 Команды:
/farm - получить коины (раз в {FARM_COOLDOWN} часа)
/balance - проверить баланс
/top - топ игроков
/shop - магазин товаров
/inventory - ваши покупки
/help - помощь

💎 Как получить коины от админа:
Админ отвечает на ваше сообщение и пишет:
/give 100

🎯 Шансы фарма:
• 1-5 коинов (обычно)
• 🎉 +2 коина (10% шанс)
• 😕 -1/-2 коина (8% шанс)
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
        bonus_msg = f"\n🎉 УДАЧА! +{bonus} коина!"
        emoji = "🎉"
    elif chance < 0.18:
        penalty = random.choice([-1, -2])
        original_coins = coins
        coins = max(0, coins + penalty)
        if penalty == -1:
            bonus_msg = f"\n😕 Неудача... -1 коин ({original_coins} → {coins})"
            emoji = "😕"
        else:
            bonus_msg = f"\n😞 Печаль... -2 коина ({original_coins} → {coins})"
            emoji = "😞"
    
    new_balance = db.add_coins(user_id, coins)
    
    result = f"""
{emoji} Фарм завершен!

Получено: {coins} KMEкоинов{bonus_msg}
💰 Новый баланс: {new_balance}
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

{timer}🛍️ /shop - магазин
    """
    await update.message.reply_text(text)

async def top_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not db.data:
        await update.message.reply_text("📭 Пока нет игроков!")
        return
    
    top_users = sorted(
        db.data.items(),
        key=lambda x: x[1].get('total_farmed', 0),
        reverse=True
    )[:5]
    
    text = "🏆 ТОП 5 ИГРОКОВ 🏆\n\n"
    
    for i, (user_id, user_data) in enumerate(top_users, 1):
        username = user_data.get('username', '')
        if username:
            name = f"@{username}"
        else:
            name = user_data.get('display_name', f"Игрок {user_id[-4:]}")
        
        coins = user_data.get('total_farmed', 0)
        medal = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][i-1]
        text += f"{medal} {name}: {coins} коинов\n"
    
    await update.message.reply_text(text)

async def shop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = db.get_user(user.id)
    
    text = "🛍️ МАГАЗИН KMEbot\n\n"
    
    for item_id, item in SHOP_ITEMS.items():
        text += f"{item_id}. {item['name']}\n"
        text += f"   💰 {item['price']} KMEкоинов\n"
        text += f"   📝 {item['description']}\n"
        text += f"   🛒 /buy_{item_id}\n\n"
    
    text += f"💰 Ваш баланс: {user_data['coins']} KMEкоинов\n"
    text += "🛒 Для покупки напишите /buy_номер"
    
    await update.message.reply_text(text)

async def buy_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    command = update.message.text
    
    try:
        item_id = int(command.split('_')[1])
    except:
        await update.message.reply_text(
            "❌ Неправильный формат!\n"
            "✅ /buy_номер\n"
            "📝 Пример: /buy_1\n"
            "🛍️ Товары: /shop"
        )
        return
    
    success, message = db.buy_item(user.id, item_id)
    
    if success:
        user_data = db.get_user(user.id)
        message += f"\n💰 Остаток: {user_data['coins']} коинов"
    
    await update.message.reply_text(message)

async def inventory_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = db.get_user(user.id)
    
    if not user_data['inventory']:
        text = "📦 Ваш инвентарь пуст\n🛍️ /shop"
    else:
        text = "📦 ВАШ ИНВЕНТАРЬ\n\n"
        
        for i, item in enumerate(user_data['inventory'], 1):
            bought_date = datetime.fromisoformat(item['bought_at']).strftime("%d.%m.%Y %H:%M")
            text += f"{i}. {item['name']}\n"
            text += f"   💰 Цена: {item['price']} коинов\n"
            text += f"   📅 Дата: {bought_date}\n\n"
        
        text += f"📊 Всего покупок: {len(user_data['inventory'])}"
    
    await update.message.reply_text(text)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = f"""
🆘 ПОМОЩЬ ПО KMEbot

📋 Команды:
/farm - получить коины (раз в {FARM_COOLDOWN} часа)
/balance - ваш баланс
/top - топ игроков
/shop - магазин товаров
/inventory - ваши покупки
/help - эта справка

🎯 Шансы фарма:
• Базово: 1-5 коинов
• 🎉 УДАЧА (+2 коина): 10%
• 😕 НЕУДАЧА (-1/-2 коина): 8%

🛍️ Товары:
1. 🔔 Сигна от Kme_Dota - 50 коинов
2. 👥 Сигна от Лсной братвы - 100 коинов
3. 👑 Модер в чате - 150 коинов

💰 Как получить коины от админа:
Админ отвечает на ваше сообщение командой:
/give 100

💬 Работа в чатах:
В группе пишите команды как обычно:
/farm, /balance, /shop

👤 Создатель: {ADMIN_USERNAME}
    """
    await update.message.reply_text(text)

# ========== ЗАПУСК БОТА ==========
def main():
    print("=" * 50)
    print("🚀 ЗАПУСК KMEbot (РЕЖИМ ОТВЕТА НА СООБЩЕНИЯ)")
    print("=" * 50)
    print(f"👥 Игроков: {len(db.data)}")
    print(f"⏳ КД фарма: {FARM_COOLDOWN} часа")
    print(f"💰 Коинов за фарм: 1-5")
    print(f"🎉 Шанс +2: 10% | 😕 Шанс -1/-2: 8%")
    print(f"👑 Админ ID: {ADMIN_ID}")
    print("=" * 50)
    print("💎 КОМАНДА /give РАБОТАЕТ ТОЛЬКО:")
    print("✅ Ответить на сообщение игрока + /give 100")
    print("=" * 50)
    
    try:
        app = Application.builder().token(TOKEN).build()
        
        app.add_handler(CommandHandler("start", start_cmd))
        app.add_handler(CommandHandler("farm", farm_cmd))
        app.add_handler(CommandHandler("balance", balance_cmd))
        app.add_handler(CommandHandler("top", top_cmd))
        app.add_handler(CommandHandler("shop", shop_cmd))
        app.add_handler(CommandHandler("inventory", inventory_cmd))
        app.add_handler(CommandHandler("help", help_cmd))
        app.add_handler(CommandHandler("give", give_cmd))
        
        app.add_handler(CommandHandler("buy_1", buy_cmd))
        app.add_handler(CommandHandler("buy_2", buy_cmd))
        app.add_handler(CommandHandler("buy_3", buy_cmd))
        
        print("✅ Бот запущен!")
        print("⏳ Ожидание сообщений...")
        print("=" * 50)
        
        app.run_polling()
        
    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        input("Нажми Enter для выхода...")

if __name__ == "__main__":
    main()
