import asyncio
import os


from aiogram import Bot, Dispatcher, types

from dotenv import find_dotenv, load_dotenv
load_dotenv(find_dotenv())

from database.middleware import DataBaseSession
from database.engine import create_db, session_maker, drop_db

from handlers.user import user_router
from handlers.admin import admin_router

bot = Bot(token=os.getenv('TOKEN'))
bot.admin_ID = os.getenv('ADMIN')

dp = Dispatcher()
dp.include_router(admin_router)
dp.include_router(user_router)

from commands.bot_cmd import private


from loguru import logger
from notifiers.logging import NotificationHandler

# Конфигурирую  logger
LOG_FILE = 'logger/info.json'



async def on_startup():
    new_start = True
    if new_start:
        await drop_db()
        await create_db()
        try:
            os.remove(LOG_FILE)
        except ():
            print('Файла лога и так нет')

    logger.add(LOG_FILE, format='{extra[user_id]} {extra[name]} {extra[calc_id]} {time} {level} {message}',
               level='INFO',
               rotation='1 month',
               compression='zip',
               colorize=True,
               serialize=True
               )
    # прописываем параметры телеграм бота
    params = {
        'token': os.getenv('TOKEN'),
        'chat_id': os.getenv('ADMIN')
    }
    tg_handler = NotificationHandler("telegram", defaults=params)
    # добавляем в logger правило, что все логи уровня info и выше отсылаются в телегу
    logger.add(tg_handler, level="ERROR")


    print('Бот успешно запущен!')
    logger.info("Бот успешно запущен!", user_id=0, name='bot', calc_id=0)

async def on_shutdown():
    print('бот остановился')
    # logger.critical("Бот остановился!", user_id=0, name='bot', calc_id=0)



async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    dp.update.middleware(DataBaseSession(session_pool=session_maker))

    await bot.delete_webhook(drop_pending_updates=True)
    # await bot.delete_my_commands(scope=types.BotCommandScopeAllPrivateChats())
    await bot.set_my_commands(commands=private, scope=types.BotCommandScopeAllPrivateChats())
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


asyncio.run(main())
