from aiogram.types import BotCommand


private = [
    BotCommand(command='reset', description='Главное меню'),
    # BotCommand(command='calculation', description='Архив расчетов'),
    BotCommand(command='payment', description='Варианты оплаты'),
    BotCommand(command='question', description='Задать вопрос'),
    BotCommand(command='about', description='О программе'),
]