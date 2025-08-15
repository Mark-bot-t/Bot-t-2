import asyncio
import json
import subprocess
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# Получаем токен из переменных окружения
TOKEN = os.getenv("TOKEN")

if not TOKEN:
    raise ValueError("TOKEN environment variable is required")

bot = Bot(token=TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer("Привет! Я Линкорез — пришли ссылку на YouTube плейлист, и я нарежу его на отдельные видео.")

@dp.message()
async def handle_playlist(message: types.Message):
    playlist_url = message.text.strip()
    if "youtube.com/playlist" not in playlist_url:
        await message.answer("❌ Это не похоже на ссылку на плейлист YouTube.")
        return

    await message.answer("🔍 Получаю список видео...")

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
            return

        # Получаем список видео
        result = subprocess.run(
            ["yt-dlp", "--flat-playlist", "--dump-json", playlist_url],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30  # Таймаут 30 секунд
        )

        if result.returncode != 0:
            await message.answer(f"❌ Ошибка при обработке плейлиста: {result.stderr}")
            return

        video_count = 0
        for line in result.stdout.splitlines():
            if line.strip():  # Пропускаем пустые строки
                try:
                    data = json.loads(line)
                    if "id" in data:
                        video_url = f"https://www.youtube.com/watch?v={data['id']}"
                        await message.answer(video_url)
                        await message.answer("———————————")
                        video_count += 1
                except json.JSONDecodeError:
                    continue  # Пропускаем строки, которые не являются JSON

        if video_count == 0:
            await message.answer("❌ Видео в плейлисте не найдено.")
        else:
            await message.answer(f"✅ Найдено {video_count} видео!")

    except subprocess.TimeoutExpired:
        await message.answer("❌ Превышено время ожидания. Попробуйте еще раз.")
    except Exception as e:
        await message.answer(f"❌ Произошла ошибка: {str(e)}")

async def main():
    print("Бот запускается...")
    try:
        await dp.start_polling(bot)
    except Exception as e:
        print(f"Ошибка при запуске бота: {e}")

if __name__ == "__main__":
    asyncio.run(main())
