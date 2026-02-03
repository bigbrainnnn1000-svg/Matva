import json
import os
import random
import time
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
import telegram.error

TOKEN = "8542959870:AAH7ECRyusZRDiULPWngvcjygQ9smi-cA3E"
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
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.filename = os.path.join(current_dir, filename)
        
        print(f"📁 База данных: {self.filename}")
        
        # НЕ создаем резервную копию при каждом запуске
        # self.create_backup()  # ЗАКОММЕНТИРОВАНО
        
        self.data = self.load_data()
        print(f"👥 Загружено игроков: {len(self.data)}")
    
    def create_backup(self):
        """ТОЛЬКО ДЛЯ РУЧНОГО ВЫЗОВА, НЕ ПРИ КАЖДОМ ЗАПУСКЕ"""
        if os.path.exists(self.filename):
            try:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_file = f"{self.filename}.backup_{timestamp}"
                with open(self.filename, 'r', encoding='utf-8') as src:
                    content = src.read()
                    if content.strip():
                        with open(backup_file, 'w', encoding='utf-8') as dst:
                            dst.write(content)
                        print(f"💾 Создана резервная копия: {backup_file}")
                        return backup_file
            except Exception as e:
                print(f"⚠️ Не удалось создать бэкап: {e}")
        return None
    
    def load_data(self):
        """ИСПРАВЛЕННЫЙ МЕТОД ЗАГРУЗКИ - НЕ СОЗДАЕТ НОВУЮ БАЗУ ПРИ ОШИБКАХ"""
        if not os.path.exists(self.filename):
            print("📝 Файл базы не найден, создаю новую...")
            return {}
        
        try:
            with open(self.filename, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                
            if not content:
                print("⚠️ Файл базы пустой")
                return {}
            
            data = json.loads(content)
            
            if not isinstance(data, dict):
                print("❌ Неверный формат базы данных")
                # ВОССТАНАВЛИВАЕМ ИЗ РЕЗЕРВНОЙ КОПИИ
                return self.try_load_backup()
            
            # Конвертируем старые данные - добавляем недостающие поля
            converted_count = 0
            for user_id, user_data in data.items():
                if 'last_active' not in user_data:
                    user_data['last_active'] = datetime.now().isoformat()
                    converted_count += 1
                if 'admin_gifted' not in user_data:
                    user_data['admin_gifted'] = 0
                    converted_count += 1
                if 'display_name' not in user_data:
                    user_data['display_name'] = ''
                if 'inventory' not in user_data:
                    user_data['inventory'] = []
                if 'total_farmed' not in user_data:
                    user_data['total_farmed'] = user_data.get('coins', 0)
                if 'farm_count' not in user_data:
                    user_data['farm_count'] = 0
            
            if converted_count > 0:
                print(f"🔄 Конвертировано {converted_count} профилей")
                self.save_data(data)  # Сохраняем обновленную структуру
            
            print(f"✅ Успешно загружено {len(data)} пользователей")
            return data
            
        except json.JSONDecodeError as e:
            print(f"❌ Ошибка JSON в файле БД: {e}")
            print("🔄 Пробую загрузить из резервной копии...")
            return self.try_load_backup()
        except Exception as e:
            print(f"❌ Ошибка загрузки БД: {e}")
            print("🔄 Пробую загрузить из резервной копии...")
            return self.try_load_backup()
    
    def try_load_backup(self):
        """ПОПЫТКА ЗАГРУЗКИ ИЗ РЕЗЕРВНОЙ КОПИИ"""
        import glob
        
        # Ищем последнюю резервную копию
        backup_files = glob.glob(f"{self.filename}.backup_*")
        if backup_files:
            latest_backup = max(backup_files, key=os.path.getctime)
            print(f"🔄 Загружаю из резервной копии: {latest_backup}")
            
            try:
                with open(latest_backup, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Восстанавливаем основную базу
                with open(self.filename, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                print(f"✅ База восстановлена из резервной копии: {len(data)} пользователей")
                return data
            except Exception as e:
                print(f"❌ Не удалось загрузить из резервной копии: {e}")
        
        print("⚠️ Резервные копии не найдены, создаю новую базу")
        return {}
    
    def save_data(self, data=None):
        if data is None:
            data = self.data
        
        try:
            # Сохраняем во временный файл
            temp_file = f"{self.filename}.temp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            # Перемещаем в основной файл
            os.replace(temp_file, self.filename)
            print(f"💾 База сохранена: {len(data)} пользователей")
        except Exception as e:
            print(f"❌ Ошибка сохранения БД: {e}")

    # Остальные методы остаются без изменений
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
                'admin_gifted': 0,
                'last_active': datetime.now().isoformat()
            }
            self.save_data()
        return self.data[user_id]
    
    def update_user(self, user_id, username="", display_name=""):
        user = self.get_user(user_id)
        if username:
            user['username'] = username
        if display_name:
            user['display_name'] = display_name
        user['last_active'] = datetime.now().isoformat()
        self.save_data()
    
    def can_farm(self, user_id):
        user = self.get_user(user_id)
        user['last_active'] = datetime.now().isoformat()
        
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
        user['last_active'] = datetime.now().isoformat()
        self.save_data()
        return user['coins']
    
    def buy_item(self, user_id, item_id):
        user = self.get_user(user_id)
        user['last_active'] = datetime.now().isoformat()
        
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
        user['last_active'] = datetime.now().isoformat()
        
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
            user['last_active'] = datetime.now().isoformat()
        self.save_data()
        return len(self.data)
    
    def get_user_level(self, total_coins):
        for level in LEVELS:
            if level["min_coins"] <= total_coins <= level["max_coins"]:
                return level
        return LEVELS[-1]
    
    def search_users(self, search_term):
        results = []
        search_term = search_term.lower()
        
        for user_id, user_data in self.data.items():
            username = user_data.get('username', '').lower()
            display_name = user_data.get('display_name', '').lower()
            
            if search_term in username or search_term in display_name:
                results.append((user_id, user_data))
        
        return results

# Добавляем команду для принудительного восстановления БД
async def force_restore(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только для админа!")
        return
    
    message = (
        f"🔄 <b>ПРИНУДИТЕЛЬНОЕ ВОССТАНОВЛЕНИЕ БАЗЫ</b>\n\n"
        f"📝 <b>Инструкция:</b>\n"
        f"1. Загрузите ваш файл kme_data.json\n"
        f"2. Напишите команду: /force_restore\n\n"
        f"⚠️ <b>Внимание:</b>\n"
        f"• Старая база будет сохранена как backup\n"
        f"• Бот перезагрузится\n"
    )
    
    await update.message.reply_text(message, parse_mode='HTML')

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик загруженных документов"""
    if not is_admin(update.effective_user.id):
        return
    
    document = update.message.document
    if document.file_name == 'kme_data.json' or document.file_name.endswith('.json'):
        try:
            # Скачиваем файл
            file = await document.get_file()
            downloaded = await file.download_to_drive('kme_data.json.restore')
            
            # Проверяем файл
            with open('kme_data.json.restore', 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    await update.message.reply_text("❌ Файл пустой!")
                    return
                
                data = json.loads(content)
                if not isinstance(data, dict):
                    await update.message.reply_text("❌ Неверный формат JSON!")
                    return
            
            # Создаем резервную копию текущей базы
            if os.path.exists('kme_data.json'):
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_file = f"kme_data.json.before_restore_{timestamp}"
                os.rename('kme_data.json', backup_file)
                await update.message.reply_text(f"💾 Текущая база сохранена как: {backup_file}")
            
            # Восстанавливаем базу
            os.rename('kme_data.json.restore', 'kme_data.json')
            
            global db
            db = Database()
            
            await update.message.reply_text(
                f"✅ <b>БАЗА ВОССТАНОВЛЕНА!</b>\n\n"
                f"👥 <b>Пользователей:</b> {len(db.data)}\n"
                f"💰 <b>Общая сумма коинов:</b> {sum(user['coins'] for user in db.data.values())}\n"
                f"📦 <b>Всего предметов:</b> {sum(len(user['inventory']) for user in db.data.values())}",
                parse_mode='HTML'
            )
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка восстановления: {e}")
    else:
        await update.message.reply_text("❌ Загрузите файл kme_data.json")

db = Database()

# Остальной код (все функции и main) остается БЕЗ ИЗМЕНЕНИЙ
# ... [весь остальной код остается как у вас] ...

def main():
    print("=" * 50)
    print("🤖 KMEbot запускается...")
    print(f"👥 Игроков: {len(db.data)}")
    print(f"🎮 Уровней: {len(LEVELS)}")
    print(f"💰 Фарм: 0-4 коинов, {FARM_COOLDOWN}ч КД")
    print(f"👑 Админ ID: {ADMIN_ID}")
    print("=" * 50)
    
    application = Application.builder().token(TOKEN).build()
    
    commands = [
        ("start", start),
        ("farm", farm),
        ("balance", balance),
        ("level", level),
        ("shop", shop),
        ("inventory", inventory),
        ("top", top),
        ("party", party),
        ("write", write),
        ("profile", profile),
        ("users", users),
        ("help", start),
        ("announce", announce),
        ("broadcast", broadcast),
        ("compensation", compensation),
        ("removeitem", removeitem),
        ("admin", admin),
        ("backup_db", backup_db),
        ("restore_db", restore_db),
        ("db_info", db_info),
        ("give", give),
        ("force_restore", force_restore),
    ]
    
    for cmd, handler in commands:
        application.add_handler(CommandHandler(cmd, handler))
    
    # Обработчик документов
    from telegram.ext import MessageHandler, filters
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    
    def create_buy_handler(item_id):
        async def handler(update, context):
            return await buy_item(update, context, item_id)
        return handler
    
    for item_id in SHOP_ITEMS.keys():
        application.add_handler(CommandHandler(f"buy_{item_id}", create_buy_handler(item_id)))
    
    application.add_handler(CallbackQueryHandler(button_handler))
    
    print("✅ Бот запущен!")
    print("\n📋 Инструкция по восстановлению старой БД:")
    print("1. Положите ваш старый файл kme_data.json в папку с ботом")
    print("2. Переименуйте его (например, в old_data.json)")
    print("3. Запустите бота")
    print("4. В админ-панели используйте /restore_db")
    print("5. Отправьте файл old_data.json как документ")
    print("=" * 50)
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
