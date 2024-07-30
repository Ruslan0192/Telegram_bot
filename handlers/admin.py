import json
import os
import datetime


import pandas as pd

from aiogram import F, Router, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import FSInputFile
from aiogram.utils.formatting import as_marked_section

from filters.chat_types import ChatTypeFilter, IsAdmin
from keyboards.inline import get_callback_btns

from keyboards.reply import get_keyboard

from database.orm_query import *
from handlers.user import procedure_get_calc

admin_router = Router()
admin_router.message.filter(ChatTypeFilter(["private"]), IsAdmin())

ADMIN_KB = get_keyboard(
    "Главное меню",
    "Пользователи",
    sizes=(1,1)
)

class All_state(StatesGroup):
    # Состояния бота
    question_state = State()        #ожидание ответа
    user_state = State()


@admin_router.message(CommandStart())
async def start_cmd(message: types.Message):
    await message.answer("Привет администратор, я виртуальный помощник", reply_markup=ADMIN_KB)


# ********************************************************************************************
@admin_router.message(F.text == "Вернуться на главное меню")
@admin_router.message(Command("reset"))
async def btn_new_calc(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer('Главное меню', reply_markup=ADMIN_KB)


@admin_router.message(Command("about"))
async def about_cmd(message: types.Message):
    await message.answer("Программа, в рамках дипломного проекта, "
                         "производит расчеты по формулам из файла, "
                         "записывает в базу данных PostgreSQL и "
                         "после оплаты файл расчета предоставляет пользователю.\n"
                         "Разработчик: Руслан Салмин",  reply_markup=ADMIN_KB)



@admin_router.message(Command("payment"))
async def payment_cmd(message: types.Message):

    text = as_marked_section(
        "Стоимость услуги: 100 рублей без НДС.\nВарианты оплаты:",
        "Картой",
        "Переводом SBP",
        marker="✅",
    )
    await message.answer(text.as_html(),  reply_markup=ADMIN_KB)


@admin_router.message(Command("question"))
async def question_cmd(message: types.Message, state: FSMContext):
    await message.answer("У вас есть вопрос к себе?",  reply_markup=ADMIN_KB)
    await state.set_state(All_state.question_state)


@admin_router.callback_query(F.data.startswith("answer_"))
async def answer(callback: types.CallbackQuery, state: FSMContext):
    id_message = int(callback.data.split("_")[-1])
    id_user = int(callback.data.split("_")[1])
    await state.set_data({'id_message': id_message})
    await state.update_data({'id_user': id_user})

    await callback.message.answer("Напишите ответ")

    await state.set_state(All_state.question_state)


@admin_router.message(All_state.question_state)
async def question_user(message: types.Message, state: FSMContext):
    data = await state.get_data()
    id_message = data['id_message']
    id_user = data['id_user']

    await message.send_copy(chat_id=id_user, reply_to_message_id=id_message)
    await message.answer("Ответ отправлен", reply_markup=ADMIN_KB)

    await state.clear()


@admin_router.message(F.text == "Пользователи")
async def users(message: types.Message, state: FSMContext,  session: AsyncSession):

    await message.answer(
        "Системные данные",
        reply_markup=get_callback_btns(
            btns={"выбрать": f"show_0",
                  }, )
    )

    result = await orm_get_users(session)

    if len(result) == 0:
        await message.answer("Пользователи отсутствуют", reply_markup=ADMIN_KB)
        return


    for user in result:
        context_message =f'{user.name}, id: {user.user_id_tel}'
        await message.answer(
            context_message,
            reply_markup=get_callback_btns(
                btns={"показать": f"show_{user.user_id_tel}",
                      "загрузить": f"load_{user.user_id_tel}",
                      }, )
        )
    await state.set_state(All_state.user_state)




@admin_router.callback_query(All_state.user_state, F.data.startswith("show_"))
async def user_log(callback: types.CallbackQuery, state: FSMContext,  session: AsyncSession):
    user_id = int(callback.data.split("_")[-1])
    if user_id == 0:
        await callback.message.answer(text=f'Действия бота:',
                                      reply_markup=ADMIN_KB)
    else:
        await callback.message.answer(text=f'Действия пользователя id{user_id}:',
                                  reply_markup=ADMIN_KB)

    await state.set_data({'user_id': user_id})

    # загружаем структуру логов
    with open("logger/info.json", "r", encoding='UTF-8') as file_log:
        data_json = []
        for line_file in file_log.readlines():
            log = json.loads(line_file)
            data_json.append(log)

    str_answer = ''
    number_meesage = 0
    for log in data_json:
        number_meesage += 1
        record = log['record']
        extra = record['extra'] # 'extra': {'calc_id': 0, 'name': 'bot', 'user_id': 0},
        if extra['user_id'] == user_id:
            await state.update_data({'name': extra['name']})

            time = record['time']
            time = time['repr']
            time = time[:-6]
            time_obj = datetime.datetime.strptime(time, '%Y-%m-%d %H:%M:%S.%f')
            date_create = time_obj.strftime("%d-%m-%Y_%H-%M")


            str_answer = f"{date_create}\n{record['message']}"

            calc_id = extra['calc_id']

            if calc_id == 0:
                await callback.message.answer(text=str_answer)
            else:
                if record['message'] == "Пользователь оплатил расчет":
                    message_save = await callback.message.answer(
                                        str_answer,
                                        reply_markup=get_callback_btns(
                                            btns={"посмотреть платеж": f"payment_{number_meesage}",
                                                  }, )
                                    )
                else:
                    message_save = await callback.message.answer(
                                        str_answer,
                                        reply_markup=get_callback_btns(
                                            btns={"посмотреть файл": f"file_{number_meesage}",
                                                  }, )
                                    )
                # для замены кнопки на сообщение
                await state.update_data({number_meesage: [calc_id, str_answer, message_save]})

    if str_answer == '':
        await callback.message.answer('нет записей')


@admin_router.callback_query(All_state.user_state, F.data.startswith("load_"))
async def user_load(callback: types.CallbackQuery, state: FSMContext,  session: AsyncSession):
    user_id = int(callback.data.split("_")[-1])
    # загружаем структуру логов
    with open("logger/info.json", "r", encoding='UTF-8') as file_log:
        data_json = []
        for line_file in file_log.readlines():
            log = json.loads(line_file)
            data_json.append(log)

    # преобразование из отдельных json записей в  datafreim pandas
    list_date = []
    list_message = []
    list_id_calc = []
    list_payment =[]
    list_payment_id = []
    list_payment_date = []
    for log in data_json:
        record = log['record']
        extra = record['extra']  # 'extra': {'calc_id': 0, 'name': 'bot', 'user_id': 0},
        if extra['user_id'] == user_id:
            await state.update_data({'name': extra['name']})

            time = record['time']
            time = time['repr']
            time = time[:-6]
            time_obj = datetime.datetime.strptime(time, '%Y-%m-%d %H:%M:%S.%f')
            date_create = time_obj.strftime("%d-%m-%Y_%H-%M")
            list_date.append(date_create)

            list_message.append(record['message'])

            if extra['calc_id'] == 0:
                list_payment.append(' ')
                list_payment_id.append(' ')
                list_payment_date.append(' ')
                list_id_calc.append(' ')
            else:
                list_id_calc.append(extra['calc_id'])
                result = await orm_get_calculation(session, extra['calc_id'])
                result = result[0]

                list_payment.append(result.payments)
                list_payment_id.append(result.payment_id)
                list_payment_date.append(result.updated)



    data = {'дата': list_date,
            'сообщение': list_message,
            'id расчета': list_id_calc,
            'дата платежа': list_payment_date,
            'номер платежа': list_payment_id,
            'сумма платежа, руб': list_payment
            }

    # запись файла
    df = pd.DataFrame(data)
    name_file_log = f'log_user_{user_id}.xlsx'
    df.to_excel(name_file_log)
    xls_file = FSInputFile(path=name_file_log)
    await callback.message.answer_document(xls_file, caption='Файл выписки из журнала логирования',
                                           reply_markup=ADMIN_KB
                                           )
    # удаляю файл
    os.remove(name_file_log)


@admin_router.callback_query(All_state.user_state, F.data.startswith("payment_"))
async def payment(callback: types.CallbackQuery, state: FSMContext,  session: AsyncSession):
    number_message = int(callback.data.split("_")[-1])

    # меняю кнопку inline на сообщение
    data = await state.get_data()
    btn_inline = data[number_message]
    calc_id = btn_inline[0]
    str_answer = btn_inline[1]
    message_save = btn_inline[2]
    await message_save.edit_text(str_answer)


    result = await orm_get_calculation(session, calc_id)

    calc_bd = result[0]
    payment_id = calc_bd.payment_id
    payments = calc_bd.payments
    date_payment = calc_bd.updated
    date_create = date_payment.strftime("%d-%m-%Y_%H-%M")


    await callback.message.answer(text=f'Платеж {payment_id} на сумму {payments} рублей принят {date_create}',
                                  reply_markup=ADMIN_KB)


@admin_router.callback_query(All_state.user_state, F.data.startswith("file_"))
async def file_calc(callback: types.CallbackQuery, state: FSMContext,  session: AsyncSession):
    number_message = int(callback.data.split("_")[-1])

    # меняю кнопку inline на сообщение
    data = await state.get_data()
    btn_inline = data[number_message]
    calc_id = btn_inline[0]
    str_answer = btn_inline[1]
    message_save = btn_inline[2]
    await message_save.edit_text(str_answer)


    result = await orm_get_calculation(session, calc_id)
    calc_bd = result[0]
    payment_id = calc_bd.payment_id
    payments = calc_bd.payments
    date_payment = calc_bd.updated
    # date_payment = date_payment[:-16]
    date_create = date_payment.strftime("%d-%m-%Y_%H-%M")

    await state.update_data({calc_id: [True,  # сообщение из inline /callback
                                       date_create,  # дата создания расчета
                                       message_save]  # кнопка/сообщение для удаления
                             })


    # процедура передачи данных расчета для записи в файл
    dir_save, name_file_calc = await procedure_get_calc(callback.message, session, state, calc_id, False)


    # отправляю файл
    doc_file = FSInputFile(path=name_file_calc)
    await callback.message.answer_document(doc_file, caption='Файл расчета',
                                                    reply_markup=ADMIN_KB
                                           )
    # удаляю файл и каталог
    os.remove(name_file_calc)
    os.rmdir(dir_save)



