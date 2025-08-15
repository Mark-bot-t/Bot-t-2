import asyncio
import json
import subprocess
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# Получаем токен из переменных окружения
TOKEN = os.getenv("TOKEN")

if not TOKEN:
    raise ValueError("TOKEN environment variable is required")

# Создаем хранилище для состояний
storage = MemoryStorage()
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=storage)

# Определяем состояния для диалогового окна
class PlaylistSettings(StatesGroup):
    waiting_for_url = State()
    waiting_for_start = State()
    waiting_for_end = State()
    waiting_for_reverse = State()
    waiting_for_batch_size = State()

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer(
        "🎵 Привет! Я Линкорез — бот для разрезания YouTube плейлистов на отдельные видео.\n\n"
        "Команды:\n"
        "/cut - начать настройку параметров плейлиста\n"
        "/quick - быстро обработать плейлист (все видео)\n"
        "/help - показать справку"
    )

@dp.message(Command("help"))
async def help_cmd(message: types.Message):
    await message.answer(
        "📋 Справка по командам:\n\n"
        "🔧 /cut - настроить параметры:\n"
        "   • Номер первого видео\n"
        "   • Номер последнего видео  \n"
        "   • Обратный порядок\n"
        "   • Размер пакета для отправки\n\n"
        "⚡ /quick - быстро получить все видео\n\n"
        "💡 Просто пришли ссылку на плейлист для быстрой обработки"
    )

@dp.message(Command("quick"))
async def quick_cmd(message: types.Message, state: FSMContext):
    await message.answer("🔗 Пришли ссылку на YouTube плейлист для быстрой обработки:")
    await state.set_state(PlaylistSettings.waiting_for_url)
    await state.update_data(is_quick=True)

@dp.message(Command("cut"))
async def cut_cmd(message: types.Message, state: FSMContext):
    await message.answer("🔗 Пришли ссылку на YouTube плейлист:")
    await state.set_state(PlaylistSettings.waiting_for_url)
    await state.update_data(is_quick=False)

@dp.message(PlaylistSettings.waiting_for_url)
async def process_url(message: types.Message, state: FSMContext):
    playlist_url = message.text.strip()
    if "youtube.com/playlist" not in playlist_url and "youtu.be/" not in playlist_url:
        await message.answer("❌ Это не похоже на ссылку на YouTube плейлист. Попробуй еще раз:")
        return

    await state.update_data(playlist_url=playlist_url)
    data = await state.get_data()
    
    if data.get("is_quick", False):
        # Быстрая обработка с настройками по умолчанию
        await process_playlist(message, state, {
            "start": 1,
            "end": 999999,
            "reverse": False,
            "batch_size": 50
        })
    else:
        # Переходим к настройке параметров
        await message.answer(
            "⚙️ Настроим параметры плейлиста:\n\n"
            "📍 С какого видео начать? (введи номер или 1 для начала):"
        )
        await state.set_state(PlaylistSettings.waiting_for_start)

@dp.message(PlaylistSettings.waiting_for_start)
async def process_start(message: types.Message, state: FSMContext):
    try:
        start_num = int(message.text.strip())
        if start_num < 1:
            await message.answer("❌ Номер должен быть больше 0. Попробуй еще раз:")
            return
        
        await state.update_data(start=start_num)
        await message.answer(
            f"✅ Начнем с видео #{start_num}\n\n"
            "🔚 До какого видео обрабатывать? (введи номер или 0 для всех видео):"
        )
        await state.set_state(PlaylistSettings.waiting_for_end)
    except ValueError:
        await message.answer("❌ Введи число. Попробуй еще раз:")

@dp.message(PlaylistSettings.waiting_for_end)
async def process_end(message: types.Message, state: FSMContext):
    try:
        end_num = int(message.text.strip())
        if end_num < 0:
            await message.answer("❌ Номер не может быть отрицательным. Попробуй еще раз:")
            return
        
        if end_num == 0:
            end_num = 999999
            
        data = await state.get_data()
        start_num = data.get("start", 1)
        
        if end_num < start_num and end_num != 999999:
            await message.answer(f"❌ Конечное видео ({end_num}) не может быть меньше начального ({start_num}). Попробуй еще раз:")
            return
        
        await state.update_data(end=end_num)
        await message.answer(
            f"✅ Обработаем видео с #{start_num} по #{end_num if end_num != 999999 else 'последнее'}\n\n"
            "🔄 В каком порядке выводить видео?\n"
            "Отправь:\n"
            "• 0 - как в плейлисте\n"
            "• 1 - в обратном порядке"
        )
        await state.set_state(PlaylistSettings.waiting_for_reverse)
    except ValueError:
        await message.answer("❌ Введи число. Попробуй еще раз:")

@dp.message(PlaylistSettings.waiting_for_reverse)
async def process_reverse(message: types.Message, state: FSMContext):
    text = message.text.strip()
    if text not in ["0", "1"]:
        await message.answer("❌ Введи 0 (обычный порядок) или 1 (обратный порядок):")
        return
    
    reverse = text == "1"
    await state.update_data(reverse=reverse)
    
    await message.answer(
        f"✅ Порядок: {'обратный' if reverse else 'как в плейлисте'}\n\n"
        "📦 Сколько видео отправлять за раз?\n"
        "(рекомендуется 20-50, введи число):"
    )
    await state.set_state(PlaylistSettings.waiting_for_batch_size)

@dp.message(PlaylistSettings.waiting_for_batch_size)
async def process_batch_size(message: types.Message, state: FSMContext):
    try:
        batch_size = int(message.text.strip())
        if batch_size < 1 or batch_size > 100:
            await message.answer("❌ Размер пакета должен быть от 1 до 100. Попробуй еще раз:")
            return
        
        data = await state.get_data()
        settings = {
            "start": data["start"],
            "end": data["end"],
            "reverse": data["reverse"],
            "batch_size": batch_size
        }
        
        # Показываем итоговые настройки
        await message.answer(
            f"📋 Итоговые настройки:\n"
            f"• Видео: с #{settings['start']} по #{settings['end'] if settings['end'] != 999999 else 'последнее'}\n"
            f"• Порядок: {'обратный' if settings['reverse'] else 'как в плейлисте'}\n"
            f"• Пакет: {batch_size} видео за раз\n\n"
            f"🚀 Начинаю обработку..."
        )
        
        await process_playlist(message, state, settings)
        
    except ValueError:
        await message.answer("❌ Введи число. Попробуй еще раз:")

async def process_playlist(message: types.Message, state: FSMContext, settings: dict):
    data = await state.get_data()
    playlist_url = data["playlist_url"]
    
    await message.answer("🔍 Получаю список видео... (это может занять время для больших плейлистов)")

    try:
        # Проверяем наличие yt-dlp
        result = subprocess.run(
            ["yt-dlp", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if result.returncode != 0:
            await message.answer("❌ Ошибка: yt-dlp не установлен на сервере.")
            await state.clear()
            return

        await message.answer("⏳ Обрабатываю плейлист...")

        # Формируем команду с параметрами
        cmd = ["yt-dlp", "--flat-playlist", "--dump-json"]
        
        if settings["start"] > 1:
            cmd.extend(["--playlist-start", str(settings["start"])])
            
        if settings["end"] != 999999:
            cmd.extend(["--playlist-end", str(settings["end"])])
            
        if settings["reverse"]:
            cmd.append("--playlist-reverse")
            
        cmd.append("--ignore-errors")
        cmd.append(playlist_url)

        # Выполняем команду
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120  # Увеличен таймаут для больших плейлистов
        )

        if result.returncode != 0:
            await message.answer(f"❌ Ошибка при обработке плейлиста: {result.stderr}")
            await state.clear()
            return

        video_count = 0
        batch_size = settings["batch_size"]
        
        for line in result.stdout.splitlines():
            if line.strip():  # Пропускаем пустые строки
                try:
                    data_json = json.loads(line)
                    if "id" in data_json:
                        video_url = f"https://www.youtube.com/watch?v={data_json['id']}"
                        title = data_json.get("title", "Без названия")
                        
                        # Отправляем ссылку и название (если есть)
                        await message.answer(f"🎬 {title}")
                        await message.answer(video_url)
                        await message.answer("———————————")
                        video_count += 1
                        
                        # Промежуточные уведомления и паузы
                        if video_count % batch_size == 0:
                            await message.answer(f"📊 Отправлено {video_count} видео...")
                            await asyncio.sleep(1)  # Пауза 1 секунда
                            
                except json.JSONDecodeError:
                    continue  # Пропускаем строки, которые не являются JSON

        if video_count == 0:
            await message.answer("❌ Видео в указанном диапазоне не найдено.")
        else:
            await message.answer(f"✅ Готово! Обработано {video_count} видео!")
            
    except subprocess.TimeoutExpired:
        await message.answer("❌ Превышено время ожидания. Плейлист слишком большой или сервер перегружен.")
    except Exception as e:
        await message.answer(f"❌ Произошла ошибка: {str(e)}")
    finally:
        await state.clear()

# Обработка обычных сообщений (для быстрой обработки)
@dp.message()
async def handle_message(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state:
        return  # Если мы в состоянии диалога, не обрабатываем как обычное сообщение
    
    playlist_url = message.text.strip()
    if "youtube.com/playlist" in playlist_url or "youtu.be/" in playlist_url:
        await state.update_data(playlist_url=playlist_url, is_quick=True)
        await process_playlist(message, state, {
            "start": 1,
            "end": 999999,
            "reverse": False,
            "batch_size": 50
        })
    else:
        await message.answer(
            "❌ Это не похоже на ссылку на YouTube плейлист.\n\n"
            "Используй команды:\n"
            "• /cut - настроить параметры\n"
            "• /quick - быстрая обработка\n"
            "• /help - справка"
        )

async def set_bot_commands():
    """Устанавливаем команды в меню бота"""
    commands = [
        types.BotCommand(command="start", description="🏠 Главная - информация о боте"),
        types.BotCommand(command="cut", description="⚙️ Настроить параметры плейлиста"),
        types.BotCommand(command="quick", description="⚡ Быстро получить все видео"),
        types.BotCommand(command="help", description="📋 Справка по командам")
    ]
    await bot.set_my_commands(commands)

async def main():
    print("Бот запускается...")
    try:
        # Устанавливаем команды в меню
        await set_bot_commands()
        print("Команды меню установлены")
        
        await dp.start_polling(bot)
    except Exception as e:
        print(f"Ошибка при запуске бота: {e}")

if __name__ == "__main__":
    asyncio.run(main())
