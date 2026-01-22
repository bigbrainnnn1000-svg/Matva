import json
import os
import random
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters

TOKEN = "8542959870:AAHzEChit6gsHlLzxNEg-090lNpBZwItU2E"
ADMIN_ID = 6443845944
ADMIN_USERNAME = "@Matvatok"
FARM_COOLDOWN = 4
STEAL_COOLDOWN = 30
STEAL_AMOUNT = 10
STEAL_SUCCESS_CHANCE = 40  # 40% шанс успеха
STEAL_FAIL_CHANCE = 60     # 60% шанс провала

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
                'total_earned': 0,  # Всего заработано (фарм + кража + админ)
                'farm_count': 0,
                'steal_success': 0,
                'steal_failed': 0,
                'stolen_total': 0,
                'lost_total': 0,
                'admin_gifted': 0
            }
            self.save_data()
        return self.data[user_id]
    
    def update_total_earned(self, user_id):
        """Обновить общее количество заработанных коинов"""
        user = self.get_user(user_id)
        user['total_earned'] = user['total_farmed'] + user['stolen_total'] + user['admin_gifted']
        self.save_data()
        return user['total_earned']
    
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
    
    def add_coins(self, user_id, amount, from_farm=True, from_admin=False, from_steal=False):
        user = self.get_user(user_id)
        user['coins'] += amount
        
        if from_farm:
            user['total_farmed'] += amount
            user['farm_count'] += 1
            user['last_farm'] = datetime.now().isoformat()
        
        if from_admin:
            user['admin_gifted'] += amount
        
        if from_steal:
            user['stolen_total'] += amount
        
        # Обновляем общий заработок
        self.update_total_earned(user_id)
        
        self.save_data()
        return user['coins']
    
    def remove_coins(self, user_id, amount, from_steal_fail=False):
        user = self.get_user(user_id)
        if user['coins'] < amount:
            return False, user['coins']
        
        user['coins'] -= amount
        
        if from_steal_fail:
            user['lost_total'] += amount
        
        self.save_data()
        return True, user['coins']
    
    def steal_from_user(self, thief_id, victim_username=None, victim_id=None):
        """Кража у конкретного пользователя (по юзернейму или ID)"""
        thief = self.get_user(thief_id)
        
        # Проверяем, есть ли у вора достаточно коинов
        if thief['coins'] < STEAL_AMOUNT:
            return False, f"❌ У вас недостаточно коинов для кражи! Нужно минимум {STEAL_AMOUNT} коинов.", 0, 0
        
        # Проверяем кулдаун
        can_steal, msg = self.can_steal(thief_id)
        if not can_steal:
            return False, f"⏳ {msg}", 0, 0
        
        # Находим жертву
        victim_data = None
        victim_id_found = None
        
        if victim_id:
            # Поиск по ID
            victim_id_found = str(victim_id)
            if victim_id_found in self.data:
                victim_data = self.data[victim_id_found]
        elif victim_username:
            # Поиск по юзернейму (без @)
            username_search = victim_username.lower().replace('@', '')
            for uid, user_data in self.data.items():
                if user_data.get('username', '').lower() == username_search:
                    victim_data = user_data
                    victim_id_found = uid
                    break
        
        if not victim_data:
            return False, f"❌ Игрок не найден! Убедитесь, что он зарегистрирован в боте (/start)", 0, 0
        
        if victim_id_found == thief_id:
            return False, "❌ Нельзя красть у самого себя!", 0, 0
        
        if victim_data['coins'] < STEAL_AMOUNT:
            return False, f"❌ У выбранного игрока нет {STEAL_AMOUNT} коинов!", 0, 0
        
        # Обновляем время последней кражи
        thief['last_steal'] = datetime.now().isoformat()
        
        # 40% шанс успеха, 60% шанс провала
        roll = random.randint(1, 100)
        
        if roll <= STEAL_SUCCESS_CHANCE:  # Успешная кража (40%)
            # Забираем у жертвы
            success = self.remove_coins(victim_id_found, STEAL_AMOUNT)
            if not success[0]:
                return False, "❌ Ошибка при краже!", 0, 0
            
            # Даем вору
            self.add_coins(thief_id, STEAL_AMOUNT, from_farm=False, from_steal=True)
            thief['steal_success'] += 1
            
            victim_name = victim_data.get('username', '')
            if victim_name:
                victim_name = f"@{victim_name}"
            else:
                victim_name = victim_data.get('display_name', f"ID:{victim_id_found[:6]}")
            
            return True, f"✅ Вы успешно украли {STEAL_AMOUNT} коинов у {victim_name}!", STEAL_AMOUNT, 0
        
        else:  # Провальная кража (60%)
            # Забираем у вора
            success = self.remove_coins(thief_id, STEAL_AMOUNT, from_steal_fail=True)
            if not success[0]:
                return False, "❌ Ошибка при краже!", 0, 0
            
            # Даем жертве (компенсация)
            self.add_coins(victim_id_found, STEAL_AMOUNT, from_farm=False)
            thief['steal_failed'] += 1
            
            victim_name = victim_data.get('username', '')
            if victim_name:
                victim_name = f"@{victim_name}"
            else:
                victim_name = victim_data.get('display_name', f"ID:{victim_id_found[:6]}")
            
            return False, f"❌ Вас заметили! {victim_name} забрал у вас {STEAL_AMOUNT} коинов в качестве компенсации.", 0, STEAL_AMOUNT
    
    def steal_random(self, thief_id):
        """Кража у случайного игрока"""
        thief = self.get_user(thief_id)
        
        # Проверяем, есть ли у вора достаточно коинов
        if thief['coins'] < STEAL_AMOUNT:
            return False, f"❌ У вас недостаточно коинов для кражи! Нужно минимум {STEAL_AMOUNT} коинов.", 0, 0
        
        # Проверяем кулдаун
        can_steal, msg = self.can_steal(thief_id)
        if not can_steal:
            return False, f"⏳ {msg}", 0, 0
        
        # Получаем список всех пользователей кроме вора
        potential_victims = [uid for uid in self.data.keys() if uid != thief_id]
        
        if not potential_victims:
            return False, "❌ В базе нет других игроков!", 0, 0
        
        # Выбираем случайную жертву
        victim_id = random.choice(potential_victims)
        victim = self.get_user(victim_id)
        
        if victim['coins'] < STEAL_AMOUNT:
            return False, f"❌ У выбранной жертвы нет {STEAL_AMOUNT} коинов!", 0, 0
        
        # Обновляем время последней кражи
        thief['last_steal'] = datetime.now().isoformat()
        
        # 40% шанс успеха, 60% шанс провала
        roll = random.randint(1, 100)
        
        if roll <= STEAL_SUCCESS_CHANCE:  # Успешная кража (40%)
            # Забираем у жертвы
            success = self.remove_coins(victim_id, STEAL_AMOUNT)
            if not success[0]:
                return False, "❌ Ошибка при краже!", 0, 0
            
            # Даем вору
            self.add_coins(thief_id, STEAL_AMOUNT, from_farm=False, from_steal=True)
            thief['steal_success'] += 1
            
            victim_name = victim.get('username', '')
            if victim_name:
                victim_name = f"@{victim_name}"
            else:
                victim_name = victim.get('display_name', f"ID:{victim_id[:6]}")
            
            return True, f"✅ Вы успешно украли {STEAL_AMOUNT} коинов у {victim_name}!", STEAL_AMOUNT, 0
        
        else:  # Провальная кража (60%)
            # Забираем у вора
            success = self.remove_coins(thief_id, STEAL_AMOUNT, from_steal_fail=True)
            if not success[0]:
                return False, "❌ Ошибка при краже!", 0, 0
            
            # Даем жертве (компенсация)
            self.add_coins(victim_id, STEAL_AMOUNT, from_farm=False)
            thief['steal_failed'] += 1
            
            victim_name = victim.get('username', '')
            if victim_name:
                victim_name = f"@{victim_name}"
            else:
                victim_name = victim.get('display_name', f"ID:{victim_id[:6]}")
            
            return False, f"❌ Вас заметили! {victim_name} забрал у вас {STEAL_AMOUNT} коинов в качестве компенсации.", 0, STEAL_AMOUNT
    
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

# ========== КОМАНДА /STEAL (РАЗНЫЕ ВАРИАНТЫ) ==========
async def steal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Кража коинов (рандомная или у конкретного игрока)"""
    user = update.effective_user
    user_id = str(user.id)
    
    # Проверяем минимальный баланс
    user_data = db.get_user(user_id)
    if user_data['coins'] < STEAL_AMOUNT:
        await update.message.reply_text(
            f"❌ У вас недостаточно коинов для кражи!\n"
            f"💰 Нужно минимум: {STEAL_AMOUNT} коинов\n"
            f"💳 Ваш баланс: {user_data['coins']} коинов\n\n"
            f"💡 Совет: Используйте /farm чтобы заработать больше!"
        )
        return
    
    # Проверяем кулдаун
    can_steal, msg = db.can_steal(user_id)
    if not can_steal:
        await update.message.reply_text(
            f"⏳ КРАЖА НЕДОСТУПНА\n\n"
            f"{msg}\n\n"
            f"💰 Стоимость кражи: {STEAL_AMOUNT} коинов\n"
            f"🎯 Шанс успеха: {STEAL_SUCCESS_CHANCE}%\n"
            f"⚠️ Шанс провала: {STEAL_FAIL_CHANCE}%\n"
            f"📊 Статистика ваших краж:\n"
            f"✅ Успешных: {user_data['steal_success']}\n"
            f"❌ Провалов: {user_data['steal_failed']}"
        )
        return
    
    # Если указан аргумент - кража у конкретного игрока
    if context.args:
        target = context.args[0].replace('@', '')
        
        # Проверяем, является ли аргумент числом (ID)
        if target.isdigit():
            success, result, stolen, lost = db.steal_from_user(user_id, victim_id=target)
        else:
            success, result, stolen, lost = db.steal_from_user(user_id, victim_username=target)
    else:
        # Рандомная кража
        waiting_msg = await update.message.reply_text(
            f"🎭 ПОДГОТОВКА К КРАЖЕ...\n\n"
            f"🔍 Ищем подходящую жертву...\n"
            f"💰 Ставка: {STEAL_AMOUNT} коинов\n"
            f"🎲 Шанс успеха: {STEAL_SUCCESS_CHANCE}%\n"
            f"⚠️ Шанс провала: {STEAL_FAIL_CHANCE}%"
        )
        
        await asyncio.sleep(2)
        success, result, stolen, lost = db.steal_random(user_id)
        
        if "недостаточно" in result.lower():
            await waiting_msg.edit_text(result)
            return
    
    # Обновляем данные пользователя
    user_data = db.get_user(user_id)
    
    if success:
        # Успешная кража
        response_text = (
            f"✅ КРАЖА УСПЕШНА!\n\n"
            f"{result}\n\n"
            f"💰 Ваш баланс: {user_data['coins']} коинов\n"
            f"📊 Статистика краж:\n"
            f"✅ Успешных: {user_data['steal_success']}\n"
            f"❌ Провалов: {user_data['steal_failed']}\n"
            f"💎 Украдено всего: {user_data['stolen_total']} коинов\n\n"
            f"⏳ Следующая кража через {STEAL_COOLDOWN} минут\n"
            f"💡 Используйте /balance для полной статистики"
        )
    else:
        if "недостаточно" in result.lower():
            response_text = result
        else:
            # Провальная кража
            response_text = (
                f"❌ КРАЖА ПРОВАЛЕНА!\n\n"
                f"{result}\n\n"
                f"💰 Ваш баланс: {user_data['coins']} коинов\n"
                f"📊 Статистика краж:\n"
                f"✅ Успешных: {user_data['steal_success']}\n"
                f"❌ Провалов: {user_data['steal_failed']}\n"
                f"💸 Потеряно всего: {user_data['lost_total']} коинов\n\n"
                f"⏳ Следующая кража через {STEAL_COOLDOWN} минут\n"
                f"💡 Используйте /farm чтобы восстановить потери"
            )
    
    if context.args:
        await update.message.reply_text(response_text)
    else:
        await waiting_msg.edit_text(response_text)

# ========== КОМАНДА /TOP (С ПОДСЧЕТОМ ВСЕХ ДОХОДОВ) ==========
async def top_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not db.data:
        await update.message.reply_text("📭 Пока нет игроков! Станьте первым - /start")
        return
    
    # Получаем топ игроков по total_earned (фарм + кража + админ)
    top_users = sorted(
        db.data.items(),
        key=lambda x: x[1].get('total_earned', 0),
        reverse=True
    )[:10]  # Показываем топ-10
    
    text = "🏆 ТОП ИГРОКОВ ПО ОБЩЕМУ ДОХОДУ 🏆\n\n"
    text += "📊 В подсчете учитывается:\n• Фарм коинов (/farm)\n• Успешные кражи (/steal)\n• Выданные админом коины\n\n"
    
    for i, (user_id, user_data) in enumerate(top_users, 1):
        username = user_data.get('username', '')
        if username:
            name = f"@{username}"
        else:
            name = user_data.get('display_name', f"ID:{user_id[:6]}")
        
        total_earned = user_data.get('total_earned', 0)
        level = get_user_level(total_earned)
        
        # Выбираем эмодзи для места
        if i == 1:
            medal = "👑"
        elif i == 2:
            medal = "🥈"
        elif i == 3:
            medal = "🥉"
        else:
            medal = f"{i}."
        
        # Детальная статистика доходов
        farm_income = user_data.get('total_farmed', 0)
        steal_income = user_data.get('stolen_total', 0)
        admin_income = user_data.get('admin_gifted', 0)
        
        text += f"{medal} {name}\n"
        text += f"   {level['name']} | Всего: {total_earned} коинов\n"
        text += f"   📈 Фарм: {farm_income} | 🎭 Кража: {steal_income} | 👑 Админ: {admin_income}\n\n"
    
    text += "📈 Хотите попасть в топ?\n"
    text += "/farm - фармить коины\n"
    text += "/steal @username - красть у других\n"
    text += "/level - отслеживать прогресс"
    
    await update.message.reply_text(text)

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
    old_total = target_data.get('total_earned', 0)
    new_balance = db.add_coins(target_user_id, amount, from_farm=False, from_admin=True)
    
    # Формируем имя для отображения
    if target_user.username:
        target_name = f"@{target_user.username}"
    else:
        target_name = target_user.first_name
    
    # Проверяем повышение уровня
    old_level = get_user_level(old_total)
    new_level = get_user_level(db.get_user(target_user_id)['total_earned'])
    level_up_msg = ""
    if old_level['level'] < new_level['level']:
        level_up_msg = f"\n🎊 Уровень повышен: {old_level['name']} → {new_level['name']}!"
    
    # ОТВЕТ АДМИНУ
    result_admin = (
        f"✅ ВЫДАНО {amount} КОИНОВ!\n\n"
        f"👤 Игрок: {target_name}\n"
        f"💰 Баланс: {new_balance} коинов\n"
        f"🏆 Всего заработано: {db.get_user(target_user_id)['total_earned']} коинов\n"
        f"   📈 Фарм: {target_data['total_farmed']}\n"
        f"   🎭 Кража: {target_data['stolen_total']}\n"
        f"   👑 Админ: {target_data['admin_gifted'] + amount}"
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
                f"• /steal @username - красть коины у других ({STEAL_SUCCESS_CHANCE}% шанс)\n"
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
    
    total_earned = user_data.get('total_earned', 0)
    current_level, next_level, progress, coins_needed = get_level_progress(total_earned)
    
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
    
    # Проверяем кулдаун на кражу
    steal_timer = ""
    can_steal, steal_msg = db.can_steal(user_id)
    if can_steal:
        steal_timer = f"✅ Можно красть! /steal (@username или без)\n"
    else:
        if "Ждите" in steal_msg:
            steal_timer = f"⏳ {steal_msg}\n"
    
    text = f"""
👤 Игрок: {user_name}
💰 Текущие коины: {user_data['coins']}
🏆 Всего заработано: {total_earned} коинов
📊 Уровень: {current_level['name']} ({progress}%)

📈 ИСТОЧНИКИ ДОХОДА:
👨‍🌾 Фарм: {user_data['total_farmed']} коинов
🎭 Кража: {user_data['stolen_total']} коинов
👑 Админ: {user_data['admin_gifted']} коинов

🎯 СТАТИСТИКА:
📈 Фармов: {user_data['farm_count']}
✅ Успешных краж: {user_data['steal_success']}
❌ Провалов краж: {user_data['steal_failed']}
💸 Потеряно: {user_data['lost_total']} коинов

{farm_timer}{steal_timer}
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
    
    total_earned = user_data.get('total_earned', 0)
    current_level, next_level, progress, coins_needed = get_level_progress(total_earned)
    
    avg_farm = 2.5
    farms_needed = max(1, int(coins_needed / avg_farm)) if coins_needed > 0 else 0
    
    text = f"""
📊 УРОВЕНЬ ИГРОКА

👤 Игрок: {user_name}
💰 Всего заработано: {total_earned} коинов
🏆 Уровень: {current_level['name']}
📈 Прогресс: {progress}%

📊 СТАТИСТИКА:
📈 Фармов: {user_data['farm_count']}
🎭 Краж: {user_data['steal_success'] + user_data['steal_failed']}
✅ Успешных: {user_data['steal_success']}
❌ Провалов: {user_data['steal_failed']}

📈 ДОХОДЫ:
👨‍🌾 Фарм: {user_data['total_farmed']} коинов
🎭 Кража: {user_data['stolen_total']} коинов
👑 Админ: {user_data['admin_gifted']} коинов
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
    
    old_balance = db.get_user(user_id)['total_earned']
    new_balance = db.add_coins(user_id, coins)
    
    old_level = get_user_level(old_balance)
    new_level = get_user_level(db.get_user(user_id)['total_earned'])
    
    level_up_msg = ""
    if old_level['level'] < new_level['level']:
        level_up_msg = f"\n\n🎊 УРОВЕНЬ ПОВЫШЕН! Теперь ты {new_level['name']}!"
    
    result = f"""
{emoji} Фарм завершен!

Получено: {coins} коинов{bonus_msg}
💰 Баланс: {db.get_user(user_id)['coins']}
🏆 Всего: {db.get_user(user_id)['total_earned']}
📊 Уровень: {new_level['name']}{level_up_msg}

⏳ Следующий через {FARM_COOLDOWN}ч
"""
    
    if coins == 0:
        result += "\n💡 Не расстраивайся! Попробуй /steal @username или пиши /level чтобы увидеть прогресс!"
    
    await update.message.reply_text(result)

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
    chat_title = update.message.chat.title if update.message.chat.title else "этом чате"
    
    broadcast_text = (
        f"🎮 ПОИСК ТИМЫ DOTA 2\n\n"
        f"👤 Ищет команду: {user_name}\n"
        f"📊 Примерный MMR: ~{mmr}\n\n"
        f"💬 Зайдите в чат '{chat_title}' и напишите {user_name}\n"
        f"📍 Чтобы узнать подробности и собраться на игру!\n\n"
        f"⚡ Хотите тоже искать команду?\n"
        f"Зарегистрируйтесь в боте: /start"
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
        f"💬 Ждите ответа в чате '{chat_title}'!\n"
        f"⚡ Не забывайте регистрироваться в боте: /start"
    )
    
    await update.message.reply_text(result)

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
            "/broadcast Обновление бота! Теперь кража {STEAL_SUCCESS_CHANCE}% шанс\n\n"
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

# ========== ОСТАЛЬНЫЕ КОМАНДЫ ==========
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = db.get_user(user.id)
    
    if user.username:
        user_data['username'] = user.username
    if user.full_name:
        user_data['display_name'] = user.full_name
    db.save_data()
    
    total_earned = user_data.get('total_earned', 0)
    current_level, _, progress, _ = get_level_progress(total_earned)
    
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
• 🎭 Красть коины у других (/steal @username)
• 🎯 Искать тиму по MMR (/party 2500)
• 🛍️ Покупать и обменивать предметы
• 🏆 Бороться за место в топе (/top)

💬 Пока можешь использовать в чате:
/farm - фармить коины (0-5 коинов)
/steal @username - красть коины ({STEAL_SUCCESS_CHANCE}% шанс)
/balance - баланс и уровень
/shop - магазин
/party ммр - искать команду (0-13000)
/top - посмотреть топ игроков
"""
    else:
        text = f"""
🎮 Добро пожаловать в KMEbot!

✅ Ты успешно зарегистрирован в базе бота!

👤 Игрок: {user.first_name}
💰 Текущие коины: {user_data['coins']}
🏆 Всего заработано: {total_earned} коинов
📊 Уровень: {current_level['name']} ({progress}%)

📋 ОСНОВНЫЕ КОМАНДЫ:
/farm - получить коины (раз в {FARM_COOLDOWN}ч) 0-5 коинов
/steal @username - красть коины у других ({STEAL_SUCCESS_CHANCE}% шанс, {STEAL_COOLDOWN}мин КД)
/balance - ваш баланс и статистика
/level - подробная информация об уровне
/top - топ игроков по общему доходу
/shop - магазин товаров
/inventory - ваши покупки с обменом
/help - помощь
/party ммр - искать команду Dota 2

🎭 КОМАНДА /steal:
• Ставка: {STEAL_AMOUNT} коинов
• Шанс успеха: {STEAL_SUCCESS_CHANCE}%
• Шанс провала: {STEAL_FAIL_CHANCE}%
• КД: {STEAL_COOLDOWN} минут
• Успех: +{STEAL_AMOUNT} коинов
• Провал: -{STEAL_AMOUNT} коинов

🏆 ТОП ИГРОКОВ:
• Учитывает все доходы: фарм, кража, админ
• /top - посмотреть текущий рейтинг

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
    
    total_earned = user_data.get('total_earned', 0)
    current_level = get_user_level(total_earned)
    
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
/steal @username - кража коинов у других ({STEAL_SUCCESS_CHANCE}% шанс, {STEAL_COOLDOWN}мин КД)
/balance - ваш баланс и статистика (админ может ответить на сообщение игрока)
/level - информация об уровне (админ может ответить на сообщение игрока)
/top - топ игроков по общему доходу
/shop - магазин товаров
/inventory - ваши покупки с обменом
/party ммр - искать команду Dota 2
/help - эта справка

🎭 КОМАНДА /steal:
• Ставка: {STEAL_AMOUNT} коинов
• Шанс успеха: {STEAL_SUCCESS_CHANCE}%
• Шанс провала: {STEAL_FAIL_CHANCE}%
• КД: {STEAL_COOLDOWN} минут
• Успех: +{STEAL_AMOUNT} коинов у выбранного игрока
• Провал: -{STEAL_AMOUNT} коинов (отдаете жертве)

🏆 ТОП ИГРОКОВ (/top):
• Учитывает ВСЕ доходы: фарм + кража + админ
• Показывает детальную статистику каждого игрока

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

📢 КОМАНДА /broadcast (только для админа):
/broadcast Ваше сообщение - рассылка всем игрокам

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
    
    total_earned_all = sum(user.get('total_earned', 0) for user in db.data.values())
    
    text = f"""
👑 ПАНЕЛЬ АДМИНИСТРАТОРА

👥 Игроков в базе: {len(db.data)}
💰 Общий оборот: {total_earned_all} коинов
🔄 Предметов куплено: {sum(len(user['inventory']) for user in db.data.values())}

📊 КОМАНДЫ:
/broadcast [текст] - рассылка всем игрокам
/stats - полная статистика
/give [сумма] - выдать коины (ответить на сообщение игрока)
/removeitem [ID] [индекс] - удалить обменянный предмет
/balance - баланс игрока (ответить на сообщение)
/level - уровень игрока (ответить на сообщение)

📈 СИСТЕМА:
Уровней: {len(LEVELS)}
Фарм: 0-5 коинов / {FARM_COOLDOWN}ч
Кража: {STEAL_AMOUNT} коинов / {STEAL_COOLDOWN}мин
Шанс кражи: {STEAL_SUCCESS_CHANCE}% успех / {STEAL_FAIL_CHANCE}% провал

👤 Админ: {ADMIN_USERNAME}
"""
    await update.message.reply_text(text)

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Полная статистика бота"""
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ Эта команда только для администратора!")
        return
    
    total_players = len(db.data)
    total_coins = sum(user['coins'] for user in db.data.values())
    total_earned_all = sum(user.get('total_earned', 0) for user in db.data.values())
    total_farmed = sum(user['total_farmed'] for user in db.data.values())
    total_stolen = sum(user['stolen_total'] for user in db.data.values())
    total_admin = sum(user['admin_gifted'] for user in db.data.values())
    total_items = sum(len(user['inventory']) for user in db.data.values())
    
    level_counts = {level["level"]: 0 for level in LEVELS}
    
    for user_data in db.data.values():
        level = get_user_level(user_data.get('total_earned', 0))
        level_counts[level["level"]] += 1
    
    top_players = sorted(
        db.data.items(),
        key=lambda x: x[1].get('total_earned', 0),
        reverse=True
    )[:5]
    
    text = f"""
📊 ПОЛНАЯ СТАТИСТИКА БОТА

👥 ИГРОКИ:
Всего: {total_players}
Активных: {sum(1 for user in db.data.values() if user.get('total_earned', 0) > 0)}

💰 ЭКОНОМИКА:
Текущие коины: {total_coins}
Всего заработано: {total_earned_all}
Из них:
👨‍🌾 Фарм: {total_farmed} ({total_farmed/total_earned_all*100:.1f}%)
🎭 Кража: {total_stolen} ({total_stolen/total_earned_all*100:.1f}%)
👑 Админ: {total_admin} ({total_admin/total_earned_all*100:.1f}%)

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
    text += f"Провалов краж: {sum(user['steal_failed'] for user in db.data.values())}\n"
    text += f"Покупок: {total_items}\n"
    
    text += f"\n🏆 ТОП 5 ИГРОКА:\n"
    for i, (player_id, player_data) in enumerate(top_players, 1):
        username = player_data.get('username', '')
        name = f"@{username}" if username else player_data.get('display_name', f"ID:{player_id[:6]}")
        total_earned = player_data.get('total_earned', 0)
        level = get_user_level(total_earned)
        
        farm = player_data.get('total_farmed', 0)
        steal = player_data.get('stolen_total', 0)
        admin = player_data.get('admin_gifted', 0)
        
        text += f"{i}. {name} - {level['name']} ({total_earned} коинов)\n"
        text += f"   👨‍🌾{farm} 🎭{steal} 👑{admin}\n"
    
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
    print("🚀 ЗАПУСК KMEbot v7.0 - УЛУЧШЕННАЯ СИСТЕМА")
    print("=" * 60)
    print(f"👥 Игроков в базе: {len(db.data)}")
    print(f"📈 Уровней: {len(LEVELS)}")
    print(f"💰 Фарм: 0-5 коинов, {FARM_COOLDOWN}ч КД")
    print(f"🎭 Кража: {STEAL_AMOUNT} коинов, {STEAL_COOLDOWN}мин КД")
    print(f"   ✅ Успех: {STEAL_SUCCESS_CHANCE}% | ❌ Провал: {STEAL_FAIL_CHANCE}%")
    print(f"📢 Рассылка: /broadcast для админа")
    print(f"🎮 Поиск тимы: /party MMR (0-13000)")
    print(f"🔄 Инвентарь с кнопками обмена")
    print(f"👑 Админ ID: {ADMIN_ID}")
    print("=" * 60)
    print("💎 КОМАНДЫ ПРИ ОТВЕТЕ НА СООБЩЕНИЕ:")
    print("✅ /give [сумма] - выдать коины игроку")
    print("✅ /balance - показать баланс игрока")
    print("✅ /level - показать уровень игрока")
    print("=" * 60)
    print("🎭 УЛУЧШЕННАЯ КОМАНДА /steal:")
    print(f"• /steal @username - кража у конкретного игрока")
    print(f"• /steal - рандомная кража")
    print(f"• Ставка: {STEAL_AMOUNT} коинов")
    print(f"• Шанс: {STEAL_SUCCESS_CHANCE}% успех / {STEAL_FAIL_CHANCE}% провал")
    print(f"• КД: {STEAL_COOLDOWN} минут")
    print("=" * 60)
    print("🏆 УЛУЧШЕННЫЙ ТОП (/top):")
    print("• Учитывает ВСЕ доходы: фарм + кража + админ")
    print("• Показывает детальную статистику каждого игрока")
    print("=" * 60)
    
    app = Application.builder().token(TOKEN).build()
    
    # Команды
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("farm", farm_cmd))
    app.add_handler(CommandHandler("steal", steal_cmd))
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
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("removeitem", removeitem_cmd))
    
    print("✅ Бот запущен и готов к работе!")
    print("📢 Рассылка: /broadcast Привет всем! - для теста")
    print("🎭 Кража: /steal @username - испытайте удачу")
    print("🏆 Топ: /top - смотрите свой рейтинг")
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
