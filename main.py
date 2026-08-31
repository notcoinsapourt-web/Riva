import asyncio
import os

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")

async def main():
    if not TOKEN:
        print("BOT_TOKEN is not configured")
        return
    bot = Bot(TOKEN)
    dp = Dispatcher()
    print("Persian Shop started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
