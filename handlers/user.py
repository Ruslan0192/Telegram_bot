import datetime
import os

from aiogram import F, types, Router, Bot
from aiogram.enums import ContentType
from aiogram.filters import Command, StateFilter, CommandStart
from aiogram.types import  FSInputFile
from aiogram.utils.formatting import as_marked_section
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from loguru import logger

from word.temp_word import read_doc, write_doc

from database.orm_query import *

from keyboards.inline import get_callback_btns
from keyboards.reply import get_keyboard

from filters.chat_types import ChatTypeFilter, IsUser

user_router = Router()
user_router.message.filter(ChatTypeFilter(["private"]), IsUser())

AMONT = 10000

USER_KB_MAIN = get_keyboard(
    "Начать расчет",
    "Архив расчетов",
    "О стоимости",
    "Задать вопрос",
    "О программе",
    placeholder="Что вас интересует?",
    sizes=(1, 2, 2)
)


class All_state(StatesGroup):
    # Состояния бота
    question_state = State()        # ожидание вопроса
    calculation_state = State()     # выбор расчета
    choose_param_state = State()    # выбор параметра
    enter_param_state = State()     # ввод параметра
    pay_state = State()             # режим оплаты


@user_router.message(CommandStart())
async def start_cmd(message: types.Message, session: AsyncSession):
    await message.answer(f'Привет {message.from_user.first_name}, я виртуальный помощник! '
                         f'\n Добро пожаловать в службу какого-то расчета!')
    await message.answer_photo('AgACAgIAAxkBAAIUxmajZJYfXoykRSYL4CMcay88CPC6AAKF3jEb4HQYSYh1HWLkWqMJAQADAgADcwADNQQ',
                                 reply_markup=USER_KB_MAIN)
    # проверка на наличие пользователя
    result = await orm_get_user(session=session, user_id=message.from_user.id)


    if result == None:
    # запись нового пользователя
        await orm_add_user(session=session,
                           user_id=message.from_user.id,
                           name=message.from_user.first_name)
        logger.info("Новый пользователь",
                    user_id=message.from_user.id,
                    name=message.from_user.first_name,
                    calc_id=0 )
    else:
        logger.info("Пользователь вошел в бот",
                    user_id=message.from_user.id,
                    name=message.from_user.first_name,
                    calc_id=0 )




# ********************************************************************************************
@user_router.message(F.text == "Вернуться на главное меню")
@user_router.message(Command("reset"))
async def btn_new_calc(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer('Главное меню', reply_markup=USER_KB_MAIN)

@user_router.message(F.text.lower() == "о программе")
@user_router.message(Command("about"))
async def about_cmd(message: types.Message):
    await message.answer("Программа, в рамках дипломного проекта, "
                         "производит расчеты по формулам из файла, "
                         "записывает в базу данных PostgreSQL и "
                         "после оплаты файл расчета предоставляет пользователю.\n"
                         "Разработчик: Руслан Салмин",  reply_markup=USER_KB_MAIN)

@user_router.message(F.text.lower() == "о стоимости")
@user_router.message(Command("payment"))
async def payment_cmd(message: types.Message):

    text = as_marked_section(
        "Стоимость услуги: 100 рублей без НДС.\nВарианты оплаты:",
        "Картой",
        "Переводом SBP",
        marker="✅",
    )
    await message.answer(text.as_html(), reply_markup=USER_KB_MAIN)

@user_router.message(F.text.lower() == "задать вопрос")
@user_router.message(Command("question"))
async def question_cmd(message: types.Message, state: FSMContext):
    await message.answer("Какой у вас вопрос?",
                         reply_markup=get_keyboard(
                             "Вернуться на главное меню",
                             placeholder="Вопрос администратору",)
                         )
    await state.set_state(All_state.question_state)

@user_router.message(All_state.question_state)
async def question_mode(message: types.Message, state: FSMContext, bot: Bot):
    id_message_user = message.message_id
    await bot.send_message(chat_id=os.getenv('ADMIN'),
                           text=f'От пользователя {message.from_user.first_name} '
                                f'пришло сообщение: {message.text}',
                           reply_markup=get_callback_btns(
                               btns={"ответить": f"answer_{message.from_user.id}_{id_message_user}",
                                      }
                           )
                           )


    await message.answer('Сообщение отправлено', reply_markup=USER_KB_MAIN)
    await state.clear()



# блок архива расчетов
# ******************************************************************************************
@user_router.message(StateFilter(None), F.text == "Архив расчетов")
async def calculation_cmd(message: types.Message, state: FSMContext, session:AsyncSession):
    await list_calculation(message, state, session)


async def list_calculation(message: types.Message, state: FSMContext, session: AsyncSession):

    result = await orm_get_calculations(session=session, user_id=message.from_user.id)
    if len(result) == 0:
        await message.answer("Расчеты отсутствуют", reply_markup=USER_KB_MAIN)
        return

    # добавляю id пользователя поскольку не совпадает с callback
    await state.set_data({'user_id':message.from_user.id})
    await state.update_data({'user_name':message.from_user.first_name})

    for calc in result:
        date_create = calc.created.strftime("%d-%m-%Y_%H-%M")
        name_btn = f'Расчет от {date_create}'
        if calc.payments == None:
            message_save = await message.answer(
                                                name_btn,
                                                reply_markup=get_callback_btns(
                                                    btns={"оплатить": f"pay_{calc.id}",
                                                          "удалить": f"delete_{calc.id}", }, )
                                            )
        else:
            message_save = await message.answer(
                                                name_btn,
                                                reply_markup=get_callback_btns(
                                                    btns={"загрузить файл": f"get_{calc.id}"})
                                            )
        # await state.update_data({calc.id: message_save})  #сохраняю сообщения для возможного удаления
        # сохраняю параметры для возможного удаления кнопки или создания нового сообщения
        await state.update_data({calc.id: [True,  # сообщение из inline /callback
                                           date_create,  # дата создания расчета
                                           message_save]  # кнопка/сообщение для удаления
                                 })

    text_choose = await message.answer("Выберите расчет",
                                       reply_markup=get_keyboard(
                                           "Вернуться на главное меню",
                                           placeholder="выберите расчет"
                                            )
                                       )
    # для последующего сохранения  сообщения Выберите расчет
    await state.update_data({'text_choose': text_choose})

    await state.set_state(All_state.calculation_state)




@user_router.callback_query(All_state.calculation_state, F.data.startswith("delete_"))
async def del_calc(callback: types.CallbackQuery, state: FSMContext,  session: AsyncSession):
    id_calc = int(callback.data.split("_")[-1])

    data = await state.get_data()
    data_calc = data[id_calc]
    # calc.id: [True,  # сообщение из inline /callback
    #             calc.created,  # дата создания расчета
    #             message_save]  # кнопка/сообщение для удаления

    # удаление записи из БД
    await orm_delete_calculation(session=session, id_calc=id_calc)
    await callback.message.answer('Расчет удален')

    # удаляю сообщение с кнопкой
    button = data_calc[2]
    await button.delete()

    #удаляю сообщение  Выберите расчет
    button = data["text_choose"]
    await button.delete()
    data.pop('text_choose')


    #проверка на наличие расчетов
    user_id = data['user_id']
    result = await orm_get_calculations(session=session, user_id=user_id)
    if len(result) == 0:
        await callback.message.answer("Расчеты отсутствуют", reply_markup=USER_KB_MAIN)
        await state.clear()

    else:
        text_choose = await callback.message.answer("Выберите расчет",
                                           reply_markup=get_keyboard(
                                               "Вернуться на главное меню",
                                               placeholder="выберите расчет"
                                           )
                                           )
        # для последующего сохранения  сообщения Выберите расчет
        await state.update_data({'text_choose': text_choose})


@user_router.callback_query(F.data.startswith("get_"))
async def get_calc_callback(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext):
    id_calc = int(callback.data.split("_")[-1])
    await procedure_get_calc(callback.message, session, state, id_calc, True)


# блок ввода нового расчета
# ******************************************************************************************
#  начинаем новый расчет, все значения переменных по 0
@user_router.message(StateFilter(None),F.text.lower() == "начать расчет")
async def start_calc(message: types.Message, state: FSMContext):
    await message.answer("Введите значения параметров",
                         reply_markup=get_keyboard(
                             "Закончить расчет",
                             "Вернуться на главное меню",
                             placeholder="выберите параметр",
                             sizes=(1, 1)
                         )
                         )

    #создаю список словарей всех переменных
    list_param = read_doc()
    list_param = list_param[0]
    count_param = len(list_param)

    # создаю список словарей в переменной state
    await state.clear()
    for i in range(count_param):
        key = list_param[i]
        save_message = await message.answer(
            key,
            reply_markup = get_callback_btns(
                btns={"ввести значение": f"change_{key}",},)
        )
        await state.update_data({key: None})
        key_btn = f"_btn_{key}"
        await state.update_data({key_btn: save_message})

    await state.set_state(All_state.choose_param_state)

@user_router.callback_query(All_state.choose_param_state, F.data.startswith("change_"))
async def change_param(callback: types.CallbackQuery, state: FSMContext):
    param = callback.data.split("_")[-1]
    await state.update_data({'_param': param})

    await callback.answer(param)
    mess_param = await callback.message.answer(param, reply_markup=get_keyboard(
                                     "Закончить расчет",
                                     "Вернуться на главное меню",
                                     placeholder=f"Введите параметр {param}",
                                     sizes=(1, 1)
                                    )
                                  )
    await state.update_data({'_mess_param': mess_param})
    await state.set_state(All_state.enter_param_state)

@user_router.message(All_state.enter_param_state)
async def save_param(message: types.Message, state: FSMContext):
    await state.set_state(All_state.choose_param_state)
    data = await state.get_data()
    param = data['_param']
    value = float(message.text)
    try:
        value = float(message.text)
    except ValueError:
        await message.answer(f"Введите корректное значение параметра {param}",
                             reply_markup=get_keyboard(
                                     "Вернуться на главное меню",
                                     placeholder=f"выберите параметр",
                                                        )
                             )
        return
    if (param == 'b') & (value == 0):
        await message.answer(f"Параметр 'b' не должен быть равен 0",
                             reply_markup=get_keyboard(
                                     "Вернуться на главное меню",
                                     placeholder=f"выберите параметр",
                                                        )
                             )
        return

    await message.answer(f"Значение параметра {param}={message.text}",
                                    reply_markup=get_keyboard(
                                     "Закончить расчет",
                                     "Вернуться на главное меню",
                                     placeholder=f"выберите параметр",
                                     sizes=(1, 1))
                         )
    # обновление значения параметра
    await state.update_data({param: value})


    key_btn = f"_btn_{param}"
    button = data[key_btn]
    await button.edit_text(f'{param} = {message.text}')

    #удаление сообщения параметра
    mess_param = data['_mess_param']
    await mess_param.delete()




# запись значений в базу
@user_router.message(F.text.lower() == "закончить расчет")
async def write_param_bd(message: types.Message, state: FSMContext, session: AsyncSession):

    # переписываю словарь с учтем необходимых параметров для БД
    data = await state.get_data()
    data_db ={}
    for key,value in data.items():
        if key[0] != '_':
            data_db.update({key:value})

    try:
        data_db['id_user'] = message.from_user.id # добавляю id пользователя
        calculation_id = await orm_add_calculation(session=session, data=data_db)

        await message.answer("Для получения файла расчета, необходимо произвести оплату",
                             reply_markup=get_keyboard(
                             "Оплатить",
                             "Вернуться на главное меню",
                             placeholder="",
                             sizes=(1,1)
                            )
                         )
        # сохраняю для платежей
        await state.set_data({'calculation_id':calculation_id})
        await state.update_data({'user_id':message.from_user.id})

        # сохраняю параметры для  создания нового сообщения или записи в БД и лог
        current_date = datetime.datetime.now()
        date_create = current_date.strftime("%d-%m-%Y_%H-%M")

        await state.update_data({'user_name': message.from_user.first_name})
        await state.update_data({calculation_id: [False,  # сообщение из reply
                                           date_create,  # дата создания расчета
                                           0]  # кнопка/сообщение для удаления
                                 })

        logger.info("Пользователь закончил расчет",
                    user_id=message.from_user.id,
                    name=message.from_user.first_name,
                    calc_id=calculation_id)

    except:
        await message.answer("Определены не все переменные!",
                             reply_markup=get_keyboard(
                                 "Закончить расчет",
                                 "Вернуться на главное меню",
                                 placeholder=f"выберите параметр",
                                 sizes=(1, 1))
                             )




# блок оплаты
# *****************************************************************************************

@user_router.callback_query(F.data.startswith("pay_"))
async def pay_mode_callback(callback: types.CallbackQuery, state: FSMContext,  bot: Bot):
    calculation_id = int(callback.data.split("_")[-1])
    await state.update_data({'calculation_id': calculation_id})

    await pay_yookassa(callback.message, bot, state)

@user_router.message(F.text == "Оплатить")
async def pay_mode_message(message: types.Message, state: FSMContext, bot: Bot):
    await pay_yookassa(message, bot, state)

async def pay_yookassa(message, bot: Bot, state: FSMContext):
    data = await state.get_data()
    user_id = data['user_id']


    await message.answer("Внимание! \nОплата производится в тестовом режиме! \n"
                         "Для оплаты используйте данные тестовой карты: 1111 1111 1111 1026, 12/22, CVC 000.\n\n"
                         "Стоимость услуги составляет 100 рублей."
                         )

    current_datetime = datetime.datetime.now()
    str_current_datetime = current_datetime.strftime("_%d-%m-%Y_%H-%M")
    send_payload = str(user_id) + str_current_datetime

    await bot.send_invoice(chat_id=user_id,
                              title="расчет",
                              description="оплата за услуги",
                              payload=send_payload,
                              provider_token='381764678:TEST:90862',
                              currency='RUB',
                              prices=[{'label': 'расчет', 'amount': AMONT}],
                              need_phone_number=True,
                              need_email=True)

    await message.answer("Нажмите кнопку заплатить",
                         reply_markup=get_keyboard("Вернуться на главное меню",)
                         )


@user_router.pre_checkout_query(lambda query: True)
async def pre_checkout_query(pre_checkout_q: types.PreCheckoutQuery) -> None:
    await pre_checkout_q.answer(ok=True)


@user_router.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment(message: types.Message, state: FSMContext, session: AsyncSession) -> None:

    payment_info = str(message.successful_payment.telegram_payment_charge_id)

    data = await state.get_data()
    calculation_id = data['calculation_id']

    # сумму платежа преобразовываю, для отображения копеек
    payment = float(AMONT)/100
    # записываю квитанцию в БД
    await orm_add_payment(session, calculation_id, payment, payment_info)

    data_calc = data[calculation_id]

    if data_calc[0]:
        await list_calculation(message, state, session)
    else:
        await message.answer("Платеж прошел!",
                             reply_markup=get_keyboard(
                                 "Загрузить файл",
                                 "Вернуться на главное меню",
                                 sizes=(1, 1))
                             )
    logger.info("Пользователь оплатил расчет",
                user_id=message.from_user.id,
                name=message.from_user.first_name,
                calc_id=calculation_id)


@user_router.message(F.text == "Загрузить файл")
async def get_calc_reply(message: types.Message, session: AsyncSession, state: FSMContext):
    await state.update_data({'user_id':message.from_user.id})
    data = await state.get_data()
    calculation_id = data['calculation_id']
    await procedure_get_calc(message, session, state, calculation_id, True)


async def procedure_get_calc(message, session: AsyncSession, state: FSMContext, id_calc: int, user_rout: bool):
    # процедура передачи данных расчета для записи в файл
    # и отправка файла пользователю с последующим удалением
    # загружаю из базы все
    result = await orm_get_calculation(session, id_calc)
    calc_bd = result[0]


    # загружаю из файла все
    temp_list_param_all = read_doc()
    # создаю списки
    temp_list_param = temp_list_param_all[0]  # вводимые параметры
    temp_list_param_all = temp_list_param_all[1]  # все переменные

    # записываю значения вводимых переменных в словарь
    dict_param = {}
    for param in temp_list_param:
        value_bd = eval(f'calc_bd.{param}')
        dict_param.update({param: value_bd})

    # создаю обобщенный словарь с вычисляемыми элементами
    dict_param_all = dict_param

    list_param_raz = list(temp_list_param_all - dict_param.keys())  # список расcчитываемых параметров
    count_dict_param_raz = len(list_param_raz)

    for i in range(count_dict_param_raz):
        dict_param_all.update({list_param_raz[i]: None})

    # для наименования файла, достаю дату создания
    # calc.id: [True,  # сообщение из inline /callback
    #             calc.created,  # дата создания расчета
    #             message_save]  # кнопка/сообщение для удаления
    data = await state.get_data()

    data_calc = data[id_calc]
    calc_date_create = data_calc[1]


    # записываю файл
    dir_save, name_file_calc = await write_doc(dict_param_all, id_calc, calc_date_create)


    if user_rout:
    #  продолжение для  user_router

        # отправляю файл
        doc_file = FSInputFile(path=name_file_calc)
        await message.answer_document(doc_file, caption='Файл расчета',
                                      reply_markup=get_keyboard(
                                       "Вернуться на главное меню",
                                    ))

        # удаляю файл и каталог
        os.remove(name_file_calc)
        os.rmdir(dir_save)

        if data_calc[0]:
        # удаляю сообщение выбора этого расчета inline
            mess_param = data_calc[2]
            await mess_param.delete()

        logger.info("Для пользователя создан файл расчета",
                    user_id=data['user_id'],
                    name=data['user_name'],
                    calc_id=id_calc)
    else:
        return dir_save, name_file_calc


@user_router.message(All_state.choose_param_state)
async def any_com_calc(message: types.Message):
    await message.answer('Я не знаю такую команду. Выберите параметр!',
                                         reply_markup=get_keyboard(
                                             "Закончить расчет",
                                             "Вернуться на главное меню",
                                             placeholder="выберите параметр",
                                             sizes=(1, 1)

                                         )
                         )

@user_router.message(All_state.calculation_state)
async def any_com_calc(message: types.Message):
    await message.answer('Я не знаю такую команду. Выберите расчет!',
                                         reply_markup=get_keyboard(
                                             "Вернуться на главное меню",
                                              placeholder = "выберите расчет"
                                         )
                         )



@user_router.message()
async def any_com(message: types.Message, state: FSMContext):
    await message.answer('Я не знаю такую команду. Выберите команду!', reply_markup=USER_KB_MAIN)
    await state.clear()



