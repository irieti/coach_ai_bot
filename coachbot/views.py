from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.ext import (
    CallbackContext,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    CallbackQueryHandler,
)
from telegram.ext import Application
from django.db import models
import openai
from .models import Coach, Client, Exercise, TrainingProgram, MuscleGroup
from fpdf import FPDF
from typing import Dict, List, Optional
import re
import logging
from asgiref.sync import sync_to_async
from openai import OpenAI, OpenAIError
import os
from telegram import BotCommand
from . import settings
from dotenv import load_dotenv

load_dotenv()


MAIN_MENU = 1
CHOOSING_ACTION = 2
CLIENT_SELECTION = 3
SELECT_CLIENT_ACTION = 4
EXISTING_CLIENT = 5
CLIENT_NAME = 6
CLIENT_WEIGHT = 7
CLIENT_ACTIVITY_LEVEL = 8
CLIENT_GOAL = 9
CLIENT_YES_PRODUCTS = 10
CLIENT_NO_PRODUCTS = 11
CLIENT_ALLERGIES = 12
MENU_CREATED = 13
CONTRACT_CREATED = 14
CLIENT_CHOICE = 15
CLIENT_ACTION = 16
CLIENT_ACTIVITY_LEVEL_CHOICE = 17
CLIENT_CALORIES = 18
CREATING_PLAN = 19
CHOOSING_GOAL = 20
CREATING_TRAINING = 21
TRAINING_LEVEL = 22
MENU_OPTIONS = 23
EDIT_MENU = 24
EDIT_MENU_ITEM = 25
EDIT_PLAN_COMMENT = 27
CREATING_RESPONSE = 28
GENERATE_RESPONSE = 29
CLIENT_SURNAME = 30
CHOOSING_MUSCLE_GROUP = 31
PLAN_HANDLER = 32
TRAINING_WEEK = 33
DOWNLOAD_PDF = 34
SOCIAL_MEDIA = 35
CONTENT_GOAL = 36
CONTENT_PROMPT = 37
CONTENT_PROMPT_HANDLER = 38
CONTENT_SALES = 39
CONTENT_CHANGE = 40
TEXT_PROMPT_HANDLER = 41
TEXT_CHANGE = 42
TEXT_GENERATION = 43


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

BOT_TOKEN = os.getenv("BOT_TOKEN")


question = ""

messages = [
    {
        "role": "system",
        "content": "You are the nutritionist",
    }
]


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


async def set_bot_commands(application):
    commands = [
        BotCommand("menu", "Главное меню"),
    ]
    await application.bot.set_my_commands(commands)


@sync_to_async
def get_or_create_coach(telegram_id, name):
    try:
        coach, created = Coach.objects.get_or_create(
            telegram_id=telegram_id, defaults={"name": name}
        )
        return coach, created
    except Exception as e:
        raise e


async def start(update: Update, context: CallbackContext):
    logger.info("Команда /start вызвана пользователем: %s", update.message.from_user.id)

    telegram_id = update.message.from_user.id
    name = update.message.from_user.first_name or "Anonymous"
    context.user_data["telegram_id"] = telegram_id

    try:
        coach, created = await get_or_create_coach(telegram_id, name)
        if created:
            logger.info(f"Created new coach: {coach.name} (ID: {coach.telegram_id})")
        else:
            logger.info(f"Coach already exists: {coach.name} (ID: {coach.telegram_id})")
    except Exception as e:
        logger.error(f"Error creating coach: {e}")
        await update.message.reply_text("Произошла ошибка при сохранении данных.")
        return

    # Inline кнопки для меню внутри сообщения
    inline_keyboard = [
        [InlineKeyboardButton("Создать меню для клиента", callback_data="1")],
        [InlineKeyboardButton("Создать тренировочную программу", callback_data="2")],
        [InlineKeyboardButton("Создать договор", callback_data="3")],
        [InlineKeyboardButton("Создать идеи для контента", callback_data="4")],
        [InlineKeyboardButton("Написать текст/сценарий", callback_data="5")],
    ]
    inline_reply_markup = InlineKeyboardMarkup(inline_keyboard)

    # Reply кнопки для клавиатуры, которая появится снизу
    reply_keyboard = [[KeyboardButton("Меню")]]  # Кнопка "Меню" для клавиатуры снизу

    # Отправка текста с inline клавиатурой и reply клавиатурой
    await update.message.reply_text(
        "Привет! Я бот, который может создавать программы для твоих клиентов, контент для продвижени, а еще я обладаю большой базой знаний для тренеров. Дисклеймер: не забывай, что бот может допускать ошибки, проверяй информацию, прежде чем дать ее клиенту. Выбери нужное действие из меню.",
        reply_markup=inline_reply_markup,  # Inline клавиатура
    )

    return CHOOSING_ACTION


async def main_menu(update: Update, context):
    keyboard = [
        [InlineKeyboardButton("Создать меню для клиента", callback_data="1")],
        [InlineKeyboardButton("Создать тренировочную программу", callback_data="2")],
        [InlineKeyboardButton("Создать договор", callback_data="3")],
        [InlineKeyboardButton("Создать идеи для контента", callback_data="4")],
        [InlineKeyboardButton("Написать текст/сценарий", callback_data="5")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Что ты хочешь сделать?", reply_markup=reply_markup)

    return CHOOSING_ACTION


async def choosing_action(update: Update, context: CallbackContext):
    telegram_id = context.user_data.get("telegram_id")
    query = update.callback_query
    await query.answer()
    user_choice = query.data
    context.user_data["menu_action"] = user_choice

    if user_choice in ["1", "2", "3"]:
        keyboard = [
            [InlineKeyboardButton("Выбрать клиента", callback_data="choose_client")],
            [
                InlineKeyboardButton(
                    "Добавить нового клиента", callback_data="add_client"
                )
            ],
            [InlineKeyboardButton("Назад в меню", callback_data="back")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Выберите действие:", reply_markup=reply_markup)
        return CLIENT_CHOICE

    elif user_choice == "4":
        coach = await sync_to_async(Coach.objects.get)(telegram_id=telegram_id)
        if coach.field:
            await query.edit_message_text("В какую соц.сеть будем делать контент?")
            return CONTENT_GOAL
        else:
            await query.edit_message_text(
                "Расскажи, тренером в каком направлении ты являешься, чтобы мы смогли подобрать подходяший контент-план?"
            )
            return SOCIAL_MEDIA

    elif user_choice == "5":
        await query.edit_message_text(
            "На какую тему будем делать текст? Постарайся подробно описать, что ты хочешь донести этим текстом, какую мысль или идею, а я помогу тебе со всем остальным!"
        )
        return TEXT_GENERATION

    else:
        await query.edit_message_text("Неверный выбор. Попробуй еще раз.")
        return CHOOSING_ACTION


async def client_choice(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    user_choice = query.data

    context.user_data["client_action"] = user_choice

    if user_choice == "choose_client":
        await query.edit_message_text(
            "Введите имя клиента, чтобы выбрать из существующих:"
        )
        return CLIENT_NAME

    elif user_choice == "add_client":
        await query.edit_message_text("Введите имя нового клиента:")
        return CLIENT_NAME

    elif user_choice == "back":
        return MAIN_MENU

    else:
        await query.edit_message_text("Неверный выбор. Попробуй еще раз.")
        return CLIENT_CHOICE


async def client_name(update: Update, context: CallbackContext):
    client_name = update.message.text.strip()
    action = context.user_data.get("client_action")

    if action == "choose_client":
        clients = await sync_to_async(Client.objects.filter)(
            name__icontains=client_name
        )

        if await sync_to_async(clients.exists)():
            keyboard = [
                [
                    InlineKeyboardButton(
                        f"{client.name} {client.surname}",
                        callback_data=f"select_{client.id}",
                    ),
                ]
                for client in await sync_to_async(list)(clients)
            ]
            await update.message.reply_text(
                f"Нашел следующих клиентов с именем '{client_name}':",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            return CLIENT_SELECTION
        else:
            await update.message.reply_text(
                "Клиенты с таким именем не найдены. Попробуйте снова."
            )
            return CLIENT_NAME

    elif action == "add_client":
        telegram_id = update.message.from_user.id
        name = update.message.from_user.first_name or "Anonymous"

        try:
            coach, created = await sync_to_async(Coach.objects.get_or_create)(
                telegram_id=telegram_id, defaults={"name": name}
            )
            new_client = await sync_to_async(Client.objects.create)(
                name=client_name, coach=coach
            )

            context.user_data["selected_client"] = new_client
            await update.message.reply_text(
                f"Клиент {new_client.name} успешно добавлен! Введите фамилию клиента:"
            )
            return CLIENT_SURNAME
        except Exception as e:
            await update.message.reply_text("Произошла ошибка при добавлении клиента.")
            logger.error(f"Ошибка создания клиента: {e}")
            return CLIENT_CHOICE

    else:
        await update.message.reply_text("Ошибка при выборе действия. Попробуйте снова.")
        return CLIENT_CHOICE


async def client_selection(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    selected_client_id = query.data.split("_", 1)[1]
    logger.info(f"Пользователь выбрал клиента с ID: {selected_client_id}")

    telegram_id = query.from_user.id
    name = query.from_user.first_name or "Anonymous"
    logger.info(f"Telegram ID тренера: {telegram_id}, Имя тренера: {name}")

    try:
        coach = await sync_to_async(Coach.objects.get)(
            telegram_id=telegram_id, name=name
        )
        logger.info(f"Тренер найден: {coach}")

        client = await sync_to_async(Client.objects.get)(
            id=selected_client_id, coach=coach
        )

        if client:
            logger.info(f"Клиент найден: {client}")
            context.user_data["selected_client"] = client
            logger.info(f"context.user_data обновлен: {context.user_data}")
            plan_type = await client_action(update, context)
            print(f"plan_type: {plan_type}")
            if plan_type == "training":
                keyboard = [
                    [
                        InlineKeyboardButton(
                            "Начальный уровень", callback_data="beginner"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "Средний уровень", callback_data="intermediate"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "Продвинутый уровень", callback_data="advanced"
                        )
                    ],
                    [InlineKeyboardButton("Назад", callback_data="back")],
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.callback_query.edit_message_text(
                    "Для какого уровня подготовки будет тренировка?",
                    reply_markup=reply_markup,
                )
                return TRAINING_WEEK
            elif plan_type == "menu":
                prompt = await creating_plan(update, context)
                if prompt:
                    response = await generate_response(update, context)
                    if response:
                        keyboard = [
                            [
                                InlineKeyboardButton(
                                    "Редактировать", callback_data="edit_menu"
                                )
                            ],
                            [
                                InlineKeyboardButton(
                                    "Скачать в PDF", callback_data="download_pdf"
                                )
                            ],
                            [
                                InlineKeyboardButton(
                                    "Назад в меню", callback_data="back"
                                )
                            ],
                        ]
                        reply_markup = InlineKeyboardMarkup(keyboard)

                        await update.callback_query.edit_message_text(
                            text=f"Вот ваш персонализированный план:\n\n{response}\n\n"
                            "Что вы хотели бы сделать с планом?",
                            reply_markup=reply_markup,
                            parse_mode="HTML",
                        )
                        return MENU_OPTIONS

        else:
            logger.warning("Клиент с введенным ID не найден.")
            if query.message:
                await query.message.reply_text("Клиент не найден. Попробуйте снова.")
            return CLIENT_NAME
    except Coach.DoesNotExist:
        logger.error("Тренер не найден.")
        if query.message:
            await query.message.reply_text("Тренер не найден.")
        return CHOOSING_ACTION
    except Exception as e:
        logger.error(f"Произошла ошибка при обработке запроса: {e}")
        if query.message:
            await query.message.reply_text("Произошла ошибка при обработке запроса.")
        return CHOOSING_ACTION


async def plan_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    if query:
        try:
            await query.answer()
            if query.data == "back":
                return MAIN_MENU
            else:
                muscle_group = query.data
                context.user_data["muscle_group"] = muscle_group
        except Exception as e:
            logger.error(f"Произошла ошибка при обработке запроса: {e}")
            await query.message.reply_text("Произошла ошибка при обработке запроса.")
            return CHOOSING_MUSCLE_GROUP

    prompt = await creating_plan(update, context)
    if prompt:
        response = await generate_response(update, context)
        if response:
            keyboard = [
                [InlineKeyboardButton("Редактировать", callback_data="edit_menu")],
                [InlineKeyboardButton("Скачать в PDF", callback_data="download_pdf")],
                [InlineKeyboardButton("Назад в меню", callback_data="back")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.message.reply_text(
                text=f"Вот ваш персонализированный план:\n\n{response}\n\n"
                "Что вы хотели бы сделать с планом?",
                reply_markup=reply_markup,
                parse_mode="HTML",
            )
            return MENU_OPTIONS


async def client_surname(update: Update, context: CallbackContext):
    client = context.user_data.get("selected_client")
    client.surname = update.message.text.strip()
    client.save()
    await update.message.reply_text(f"Введите вес клиента:")
    return CLIENT_WEIGHT


async def client_weight(update: Update, context: CallbackContext):
    try:
        weight = float(update.message.text.strip())
        selected_client = context.user_data["selected_client"]
        selected_client.weight = weight
        await sync_to_async(selected_client.save)()

        await update.message.reply_text(
            "Вес сохранен! Теперь укажите уровень активности клиента:"
        )

        keyboard = [
            [InlineKeyboardButton("Низкий", callback_data="1.2")],
            [InlineKeyboardButton("Средний", callback_data="1.3")],
            [InlineKeyboardButton("Высокий", callback_data="1.4")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "Выберите уровень активности клиента:", reply_markup=reply_markup
        )
        return CLIENT_ACTIVITY_LEVEL_CHOICE

    except ValueError:
        await update.message.reply_text("Пожалуйста, введите вес в числовом формате.")
        return CLIENT_WEIGHT


async def client_activity_level_choice(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    activity_level = query.data
    selected_client = context.user_data["selected_client"]
    selected_client.activity_level = activity_level
    await sync_to_async(selected_client.save)()

    keyboard = [
        [InlineKeyboardButton("Похудение", callback_data="похудение")],
        [InlineKeyboardButton("Набор массы", callback_data="набор массы")],
        [InlineKeyboardButton("Тонус", callback_data="тонус")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.reply_text(
        "Теперь выберите цель клиента:", reply_markup=reply_markup
    )
    return CLIENT_GOAL


# Обработка цели клиента
async def client_goal(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    goal = query.data
    selected_client = context.user_data["selected_client"]
    selected_client.goal = goal
    await sync_to_async(selected_client.save)()

    await query.message.reply_text(
        "Есть ли у клиента аллергии? Введите продукты через запятую или напишите прочерк, если их нет:"
    )
    return CLIENT_ALLERGIES


async def client_allergies(update: Update, context: CallbackContext):
    allergies = update.message.text.strip()
    selected_client = context.user_data["selected_client"]
    selected_client.allergies = allergies
    await sync_to_async(selected_client.save)()

    await update.message.reply_text(
        "Какие продукты обязательно должны присутствовать в рационе? Введите продукты через запятую или напишите прочерк:"
    )
    return CLIENT_YES_PRODUCTS


async def client_yes_products(update: Update, context: CallbackContext):
    yes_products = update.message.text.strip()
    selected_client = context.user_data["selected_client"]

    logger.info(f"Получены продукты, которые должны быть в рационе: {yes_products}")

    selected_client.yes_products = yes_products
    await sync_to_async(selected_client.save)()

    logger.info(f"Данные о продуктах клиента {selected_client.name} успешно сохранены.")
    await update.message.reply_text(
        "Какие продукты НЕ должны присутствовать в рационе? Введите продукты через запятую или напишите прочерк:"
    )

    return CLIENT_NO_PRODUCTS


async def client_no_products(update: Update, context: CallbackContext):
    no_products = update.message.text.strip().lower()
    selected_client = context.user_data["selected_client"]

    logger.info(f"Получены продукты, которые не могут быть в рационе: {no_products}")

    selected_client.no_products = no_products
    await sync_to_async(selected_client.save)()

    logger.info(
        f"Данные о запрещенных продуктах для клиента {selected_client.name} успешно сохранены."
    )
    await client_calories(update, context)

    return CLIENT_CALORIES


async def client_calories(update: Update, context: CallbackContext):
    selected_client = context.user_data["selected_client"]

    weight = selected_client.weight

    activity_level = selected_client.activity_level
    goal = selected_client.goal

    calories = 24 * weight * float(activity_level)
    if goal == "похудение":
        calories = calories - (calories * 0.25)
    elif goal == "набор массы":
        calories = calories + (calories * 0.25)
    if calories < 1200:
        calories = 1200

    proteins = 1.5 * weight
    fats = 1 * weight
    carbs = 1.7 * weight

    selected_client.calories = calories
    selected_client.proteins = proteins
    selected_client.fats = fats
    selected_client.carbs = carbs
    await sync_to_async(selected_client.save)()

    client_info = (
        f"Информация о клиенте:\n"
        f"Имя: {selected_client.name}\n"
        f"Вес: {weight} кг\n"
        f"Цель: {goal.capitalize()}\n"
        f"Уровень активности: {activity_level.capitalize()}\n"
        f"Аллергии: {selected_client.allergies}\n"
        f"Продукты, которые обязательно должны быть в рационе: {selected_client.yes_products}\n"
        f"Продукты, которые не могут быть в рационе: {selected_client.no_products}\n"
        f"Суточная норма калорий: {calories} ккал\n"
        f"Суточная норма белка: {proteins} г\n"
        f"Суточная норма жиров: {fats} г\n"
        f"Суточная норма углеводов: {carbs} г\n"
    )

    await update.message.reply_text(client_info)

    plan_type = await client_action(update, context)
    if plan_type:
        context.user_data["plan_type"] = plan_type
        prompt = await creating_plan(update, context)
        if prompt:
            response = await generate_response(update, context)
            if response:
                keyboard = [
                    [InlineKeyboardButton("Редактировать", callback_data="edit_menu")],
                    [
                        InlineKeyboardButton(
                            "Скачать в PDF", callback_data="download_pdf"
                        )
                    ],
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await update.callback_query.edit_message_text(
                    text=f"Вот ваш персонализированный план:\n\n{response}\n\n"
                    "Что вы хотели бы сделать с планом?",
                    reply_markup=reply_markup,
                )
                return MENU_OPTIONS


async def client_action(update: Update, context: CallbackContext):
    logger.info(f"client action function has started")
    query = update.callback_query
    await query.answer()

    selected_client = context.user_data["selected_client"]
    menu_action = context.user_data.get("menu_action", None)

    if menu_action == "1":
        context.user_data["client"] = selected_client
        context.user_data["plan_type"] = "menu"
        plan_type = "menu"
        return plan_type

    elif menu_action == "2":
        context.user_data["plan_type"] = "training"
        plan_type = "training"
        return plan_type

    elif menu_action == "3":
        if query.message:
            await query.message.reply_text(
                f"Создаем договор для клиента {selected_client.name}."
            )
        return CONTRACT_CREATED
    else:
        logger.error("Неизвестное действие в меню.")
        if query.message:
            await query.message.reply_text("Произошла ошибка, попробуйте снова.")
        return CHOOSING_ACTION


############################## NUTRITION PLAN #####################################


async def generate_response(update: Update, context: CallbackContext):
    prompt = context.user_data.get("prompt")
    """Универсальная функция для обращения к OpenAI."""
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)

        response = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model="gpt-3.5-turbo",
        )

        ChatGPT_reply = response.choices[0].message.content

        messages.append({"role": "assistant", "content": ChatGPT_reply})

        context.user_data["response"] = ChatGPT_reply

        response = ChatGPT_reply

        return response

    except Exception as e:
        logger.error(f"Error in generate_response: {e}")
        if update.callback_query:
            await update.callback_query.message.reply_text(
                "Произошла ошибка при генерации ответа. Попробуйте снова."
            )
        else:
            await update.message.reply_text(
                "Произошла ошибка при генерации ответа. Попробуйте снова."
            )
        return CHOOSING_ACTION


async def creating_plan(update: Update, context: CallbackContext):
    logger.info(f"Startint grating_plan function")

    plan_type = context.user_data.get("plan_type")
    """Создание меню или программы тренировок."""
    try:
        selected_client = context.user_data.get("selected_client")
        if not selected_client:
            await update.message.reply_text(
                "Данные клиента не найдены. Попробуйте снова."
            )
            return CHOOSING_ACTION

        prompt = ""

        if plan_type == "menu":
            prompt = (
                f"Создайте персонализированное меню для клиента с такими данными:\n"
                f"Имя: {selected_client.name}\n"
                f"Вес: {selected_client.weight} кг\n"
                f"Цель: {selected_client.goal}\n"
                f"Калории: {selected_client.calories} ккал\n"
                f"Белки: {selected_client.proteins} г\n"
                f"Жиры: {selected_client.fats} г\n"
                f"Углеводы: {selected_client.carbs} г\n"
                f"Включить в рацион: {selected_client.yes_products}\n"
                f"Исключить из рациона: {selected_client.no_products}\n"
                f"Аллергии: {selected_client.allergies if selected_client.allergies else 'Отсутствуют'}\n"
                "Предложите 3 варианта рациона на неделю, разделив его на завтрак, обед, полдник и ужин.\n"
                "Меню должно быть в формате маркеров (пункты меню), строго в соответствии с примером ниже, включая граммы для каждого продукта:\n"
                "Пример: \n"
                "<b>Вариант 1:</b> - <b>Завтрак:</b> омлет с овощами (2 яйца), овсянка с ягодами (100 г)\n"
                "- <b>Обед:</b> куриная грудка (150 г) с рисом (100 г) и овощами (150 г)\n"
                "- <b>Полдник:</b> яблоко (1 шт.), миндаль (20 г)\n"
                "- <b>Ужин:</b> рыба на пару (150 г) с картофелем (200 г)\n"
                "- <b>Вариант 2:...</b>\n"
            )
        elif plan_type == "training":
            training_goal = context.user_data.get("training_goal")
            level = context.user_data.get("training_level")
            muscle_group = context.user_data.get("muscle_group")
            week = context.user_data.get("week")

            exercises = await sync_to_async(list)(
                Exercise.objects.filter(difficulty=level)
            )
            exercise_list = ", ".join([exercise.title for exercise in exercises])
            prompt = (
                f"Создай персонализированную программу тренировок для клиента на неделю ({week} тренировок в неделю) с целью {training_goal} и акцентом на {muscle_group} для уровня подготовки {level} на неделю, используя упражнения из {exercise_list} (4-6 упражнений в тренировке) и учитывая анкету {selected_client} ({selected_client.weight}, {selected_client.goal}, {selected_client.activity_level}).Тренировочный план должен быть в формате маркеров (пункты меню), строго в соответствии с примером ниже ( зависимости от количества дней). Не добавляй никаких комментариев от себя конце. Выдели заголовки и названия упражнений жирным шрифтом в формате телеграма\n"
                "Пример: <b>День первый:</b>\n"
                "<b>{exercise.title}-{exercise.reps}x{exercise.sets}</b>\n"
                "<b>Описание:</b> {exercise.description}\n"
                "<b>Техника выполнения:</b> {exercise.technique}\n"
                "<b>День второй:</b>...\n"
            )

        logger.info(f"Prompt для {plan_type}: {prompt}")
        context.user_data["plan_type"] = plan_type
        context.user_data["prompt"] = prompt
        prompt = prompt
        return prompt

    except Exception as e:
        logger.error(f"Error in creating_plan: {e}")
        await update.callback_query.edit_message_text(
            "Произошла ошибка при создании плана. Попробуйте снова."
        )
        return CHOOSING_ACTION


async def menu_options(update: Update, context: CallbackContext):
    """Handle menu options after plan generation."""
    logger.info("Starting menu_options function")
    query = update.callback_query
    await query.answer()

    plan_type = context.user_data.get("plan_type")
    logger.info(f"Plan type from context: {plan_type}")

    user_choice = query.data
    logger.info(f"User choice from callback: {user_choice}")

    try:
        if user_choice == "back":
            return MAIN_MENU

        if user_choice == "edit_menu":
            logger.info("User chose to edit menu")
            await query.message.reply_text("Введите ваши пожелания по изменению плана:")
            return EDIT_PLAN_COMMENT

        elif user_choice == "download_pdf":
            try:
                print("download_pdf function has started")
                plan_type = context.user_data.get("plan_type")
                query = update.callback_query
                await query.answer()

                plan = context.user_data.get("response")
                selected_client = context.user_data["selected_client"]
                print(f"Plan: {plan}")

                if not plan:
                    await query.message.reply_text("План не найден.")
                    return MENU_OPTIONS

                file_path = generate_plan_pdf(
                    plan_text=plan,
                    client_name=selected_client.name,
                    filename=f"{plan_type}_{selected_client.name}.pdf",
                )

                if file_path:
                    with open(file_path, "rb") as file:
                        await query.message.reply_document(
                            document=file, filename=file_path
                        )
                        return MAIN_MENU
                else:
                    await query.message.reply_text("Возникла ошибка при создании PDF.")
                    return MAIN_MENU

            except Exception as e:
                print(f"Error in download_plan_pdf: {str(e)}")
                await query.message.reply_text(
                    "Произошла ошибка при обработке запроса."
                )
                return MAIN_MENU

        else:
            logger.warning(f"Unknown menu option: {user_choice}")
            await query.message.reply_text("Неизвестный выбор. Попробуйте снова.")
            return MENU_OPTIONS

    except Exception as e:
        logger.error(f"Error in menu_options: {e}")
        await query.message.reply_text("Произошла ошибка. Попробуйте снова.")
        return CHOOSING_ACTION


async def edit_plan_comment(update: Update, context: CallbackContext):
    plan_type = context.user_data.get("plan_type")
    if not plan_type:
        await update.message.reply_text("План для редактирования не найден.")
        return MAIN_MENU

    user_comment = update.message.text
    if not user_comment:
        await update.message.reply_text(
            "Пожалуйста, введите текст с вашими пожеланиями."
        )
        return MENU_OPTIONS

    plan = context.user_data.get("response")
    if not plan:
        await update.message.reply_text("План не найден. Попробуйте снова.")
        return MENU_OPTIONS

    context.user_data["edit_comment"] = user_comment

    prompt = (
        f"Вот текущий план для клиента: '{plan}'. "
        f"На основе следующего комментария обнови план: '{user_comment}'."
    )
    context.user_data["prompt"] = prompt

    response = await generate_response(update, context)
    if response:
        keyboard = [
            [InlineKeyboardButton("Редактировать", callback_data="edit_menu")],
            [InlineKeyboardButton("Скачать в PDF", callback_data="download_pdf")],
            [InlineKeyboardButton("Назад в меню", callback_data="back")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.callback_query.edit_message_text(
            text=f"Вот ваш персонализированный план:\n\n{response}\n\n"
            "Что вы хотели бы сделать с планом?",
            reply_markup=reply_markup,
        )
        return MENU_OPTIONS


class PlanPDF(FPDF):
    def __init__(self, client_name: str):
        # Initialize with unicode support and font subsetting
        super().__init__()
        # Enable unicode subsetting
        self.unifontsubset = True
        self.client_name = client_name
        self.set_auto_page_break(auto=True, margin=15)

        # Set the font path - using a relative path is safer
        font_path = os.path.join(os.path.dirname(__file__), "static", "fonts")

        # Add DejaVu fonts with Unicode support
        self.add_font(
            "DejaVu",
            style="",
            fname=os.path.join(font_path, "DejaVuSansCondensed.ttf"),
            uni=True,
        )
        self.add_font(
            "DejaVu",
            style="B",
            fname=os.path.join(font_path, "DejaVuSansCondensed-Bold.ttf"),
            uni=True,
        )
        # Set default font
        self.set_font("DejaVu", size=12)

    def header(self):
        self.set_y(10)

        # Gradient title colors
        colors = [
            (88, 43, 232),  # Purple
            (199, 56, 209),  # Pink
            (249, 89, 89),  # Coral
        ]

        title = f"{self.client_name}"
        title_width = self.get_string_width(title)
        start_x = (210 - title_width) / 2

        self.set_font("DejaVu", "B", 24)

        # Draw gradient title
        segment_width = title_width / (len(colors) - 1)
        for i in range(len(colors) - 1):
            self.set_text_color(*colors[i])
            segment = title[
                int(i * len(title) / (len(colors) - 1)) : int(
                    (i + 1) * len(title) / (len(colors) - 1)
                )
            ]
            self.text(start_x + (i * segment_width), 20, segment)

        self.ln(20)

    def footer(self):
        self.set_y(-15)
        self.set_font("DejaVu", "", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"Страница {self.page_no()}", align="C")

    def add_section_title(self, title: str):
        """Add a section title with proper formatting"""
        self.set_font("DejaVu", "B", 14)
        self.set_text_color(88, 43, 232)
        self.cell(0, 10, title, ln=True)
        self.ln(5)

    def add_content_line(self, text: str, indent: bool = False):
        """Add a line of content with proper formatting"""
        self.set_text_color(0, 0, 0)
        self.set_font("DejaVu", "", 12)

        if indent:
            self.cell(10)  # Add indent

        self.multi_cell(0, 6, text)
        self.ln(2)


def parse_html_tags(text: str) -> tuple[str, bool]:
    """Parse HTML-style bold tags and return clean text and whether it was bold"""
    is_bold = False
    if "<b>" in text and "</b>" in text:
        is_bold = True
        text = text.replace("<b>", "").replace("</b>", "")
    return text, is_bold


def generate_plan_pdf(
    plan_text: str, client_name: str, filename: str = "plan.pdf"
) -> str:
    """
    Generate PDF from plan text (either meal or training plan)

    Args:
        plan_text: Raw plan text with HTML-style formatting
        client_name: Name of the client
        filename: Output filename
    """
    try:
        pdf = PlanPDF(client_name)
        pdf.add_page()

        # Split plan into lines and process each line
        lines = plan_text.strip().split("\n")
        current_section = ""

        for line in lines:
            if not line.strip():
                continue

            text, is_bold = parse_html_tags(line)

            # Check if this is a new section (variant or day)
            if text.startswith("Вариант") or text.startswith("День"):
                current_section = text
                pdf.add_section_title(text)
                continue

            # Handle meal plan format
            if ":" in text:
                # Split into title and content
                title_part, content_part = text.split(":", 1)

                # Add title (e.g., "Завтрак", "Обед", etc.)
                pdf.set_font("DejaVu", "B", 12)
                pdf.set_text_color(0, 0, 0)
                pdf.cell(0, 6, f"{title_part.strip()}:", ln=True)

                # Add content
                pdf.set_font("DejaVu", "", 12)
                pdf.multi_cell(0, 6, content_part.strip())
                pdf.ln(2)
            else:
                # For lines without colon (like exercise descriptions)
                pdf.add_content_line(text, indent=True)

        pdf.output(filename)
        return filename

    except Exception as e:
        print(f"Error generating PDF: {str(e)}")
        raise


async def download_plan_pdf(update: Update, context: CallbackContext):
    try:
        print("download_pdf function has started")
        plan_type = context.user_data.get("plan_type")
        query = update.callback_query
        await query.answer()

        plan = context.user_data.get(plan_type)
        selected_client = context.user_data["selected_client"]
        print(f"Plan: {plan}")

        if not plan:
            await query.message.reply_text("План не найден.")
            return MENU_OPTIONS

        file_path = generate_plan_pdf(
            plan_text=plan,
            client_name=selected_client.name,
            filename=f"{plan_type}_{selected_client.name}.pdf",
        )

        if file_path:
            with open(file_path, "rb") as file:
                await query.message.reply_document(document=file, filename=file_path)
            return MAIN_MENU
        else:
            await query.message.reply_text("Возникла ошибка при создании PDF.")
            return MAIN_MENU

    except Exception as e:
        print(f"Error in download_plan_pdf: {str(e)}")
        await query.message.reply_text("Произошла ошибка при обработке запроса.")
        return MAIN_MENU


############################## NUTRITION PLAN #####################################


############################## TRAINING PLAN ###################################


async def training_week(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    if query.data == "back":
        return MAIN_MENU
    else:

        level = query.data
        context.user_data["training_level"] = level

        await query.edit_message_text(f"Сколько тренировок в неделю? (1-7 в числах):")
        return CHOOSING_GOAL


async def handle_training_goal(update: Update, context: CallbackContext):
    try:
        week = int(update.message.text.strip())
        context.user_data["week"] = week
    except ValueError:
        await update.message.reply_text(
            "Пожалуйста, введите число для количества недель."
        )
        return TRAINING_WEEK

    keyboard = [
        [InlineKeyboardButton("Набор массы", callback_data="muscle_gain")],
        [InlineKeyboardButton("Снижение веса", callback_data="weight_loss")],
        [InlineKeyboardButton("Укрепление мышц", callback_data="muscle_toning")],
        [InlineKeyboardButton("Реабилитация", callback_data="rehabilitation")],
        [InlineKeyboardButton("Назад в меню", callback_data="back")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"Выберите на что сделать акцент в тренировках на неделю:",
        reply_markup=reply_markup,
    )
    return CHOOSING_MUSCLE_GROUP


async def handle_muscle_group(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    if query.data == "back":
        return MAIN_MENU

    else:

        goal = query.data
        context.user_data["training_goal"] = goal

        keyboard = [
            [InlineKeyboardButton("Грудные мышцы", callback_data="chest")],
            [InlineKeyboardButton("Ноги", callback_data="legs")],
            [InlineKeyboardButton("Спина", callback_data="back")],
            [InlineKeyboardButton("Ягодицы", callback_data="butt")],
            [InlineKeyboardButton("Пресс", callback_data="abdominal")],
            [InlineKeyboardButton("Плечи", callback_data="shoulders")],
            [InlineKeyboardButton("Все тело", callback_data="full_body")],
            [InlineKeyboardButton("Назад в меню", callback_data="back")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"Вы выбрали цель тренировки: {goal.replace('_', ' ').capitalize()}.\n"
            "Теперь выберите группу мышц, на которую хотите сделать акцент:",
            reply_markup=reply_markup,
        )
        return PLAN_HANDLER


############################## TRAINING PLAN ###################################

############################## CONTENT CREATION ###################################


async def social_media(update: Update, context: CallbackContext):
    field = update.message.text.strip()
    telegram_id = context.user_data.get("telegram_id")
    coach = await sync_to_async(Coach.objects.get)(telegram_id=telegram_id)
    coach.field = field
    context.user_data["field"] = field
    await update.message.reply_text("В какую соц.сеть будем делать контент-план?")
    return CONTENT_GOAL


async def content_goal(update: Update, context: CallbackContext):
    social_media = update.message.text.strip()
    context.user_data["social_media"] = social_media
    keyboard = [
        [
            InlineKeyboardButton(
                "Привлечение новых подписчиков", callback_data="followers"
            )
        ],
        [InlineKeyboardButton("Продажа продукта/услуги", callback_data="sales")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Какая осноная цель у твоего контента на ближайшие 2-3 недели?",
        reply_markup=reply_markup,
    )
    return CONTENT_PROMPT


async def content_prompt(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    content_goal = query.data
    field = context.user_data.get("field")
    social_media = context.user_data.get("social_media")
    context.user_data["content_goal"] = content_goal

    if content_goal == "followers":
        prompt = f"Ты маркетолог для тренеров. Перечисли 5-7 основных болей потенциальных клиентов для тренера по направлению {field}, а затем создай подробный контент-план на 2 недели для привлечения подписчиков в социальную сеть {social_media}"
        context.user_data["prompt"] = prompt
        response = await generate_response(update, context)
        if response:
            context.user_data["content"] = response
            keyboard = [
                [InlineKeyboardButton("Да", callback_data="yes")],
                [
                    InlineKeyboardButton(
                        "Нет, вернуться в главное меню", callback_data="no"
                    )
                ],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"{response}. Хотите добавить что-то еще?", reply_markup=reply_markup
            )
            return CONTENT_PROMPT_HANDLER

    elif content_goal == "sales":
        await query.edit_message_text("Расскажите подробнее о своей услуге/продукте")
        return CONTENT_SALES


async def content_prompt_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    content_change = query.data
    if content_change == "yes":
        await query.edit_message_text("Что вы хотели бы добавить/изменить?")
        return CONTENT_CHANGE
    elif content_change == "no":
        return MAIN_MENU


async def content_change(update: Update, context: CallbackContext):
    content_change = update.message.text.strip()
    content = context.user_data.get("content")

    prompt = f"Это сгенерированный контент план для тренера {content}, скорреткируй его на основе этого комментария {content_change}"
    context.user_data["prompt"] = prompt
    response = await generate_response(update, context)
    if response:
        context.user_data["content"] = response
        keyboard = [
            [InlineKeyboardButton("Да", callback_data="yes")],
            [InlineKeyboardButton("Нет, вернуться в главное меню", callback_data="no")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"{response}. Хотите добавить что-то еще?", reply_markup=reply_markup
        )
        return CONTENT_PROMPT_HANDLER


async def content_sales(update: Update, context: CallbackContext):
    sale_product = update.message.text.strip()
    field = context.user_data.get("field")
    social_media = context.user_data.get("social_media")
    prompt = f"Ты маркетолог для тренеров. Перечисли 5-7 основных болей потенциальных клиентов для тренера по направлению {field}, а затем создай подробный контент-план на 2 недели в социальную сеть {social_media} для увеличения продаж на продукт/услугу со следующим описанием {sale_product}"
    context.user_data["prompt"] = prompt
    response = await generate_response(update, context)
    if response:
        context.user_data["content"] = response
        keyboard = [
            [InlineKeyboardButton("Да", callback_data="yes")],
            [InlineKeyboardButton("Нет, вернуться в главное меню", callback_data="no")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"{response}. Хотите добавить что-то еще?", reply_markup=reply_markup
        )
        return CONTENT_PROMPT_HANDLER


#################################################################################


async def text_generation(update: Update, context: CallbackContext):
    text_idea = update.message.text.strip()
    prompt = f"Ты - профессиональный маркетолог. На эту тему {text_idea} нужно написать пост (инстаграм/телеграм) со следующей структурой: обязательно сначала опиши проблему потенциального клиента тренера с цепляющим заголовком, затем - разбери проблемы с точки зрения того, что чувствует клиент, затем - что будет, если клиент не решит эту проблему, затем, как решение изменит его жизнь, дай несколько советов, которые можно применить прямо сейчас, а дальше призыв к действию - запишись ко мне на бесплатную консультацию и мы подберем иделаьное решение для тебя. Постарайся достучаться до эмоций читателя, говорить естественным языком, как бы обращаясь к читателю"
    context.user_data["prompt"] = prompt
    response = await generate_response(update, context)
    if response:
        context.user_data["text"] = response
        keyboard = [
            [InlineKeyboardButton("Да", callback_data="yes")],
            [InlineKeyboardButton("Нет, вернуться в главное меню", callback_data="no")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"Вот ваш текст: {response}. Хотите добавить что-то еще?",
            reply_markup=reply_markup,
        )
        return TEXT_PROMPT_HANDLER
    else:
        await update.message.reply_text("Произошла ошибка, попробуйте снова")
        return MAIN_MENU


async def text_prompt_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    text_change = query.data
    if text_change == "yes":
        await query.edit_message_text("Что вы хотели бы добавить/изменить?")
        return TEXT_CHANGE
    elif text_change == "no":
        return MAIN_MENU


async def text_change(update: Update, context: CallbackContext):
    text_change = update.message.text.strip()
    text = context.user_data.get("text")
    prompt = f"Это сгенерированный текст пользователя {text}, измени его с учетом следубщих комментариев {text_change}"
    context.user_data["prompt"] = prompt
    response = await generate_response(update, context)
    if response:
        context.user_data["text"] = response
        keyboard = [
            [InlineKeyboardButton("Да", callback_data="yes")],
            [InlineKeyboardButton("Нет, вернуться в главное меню", callback_data="no")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"Вот ваш текст: {response}. Хотите добавить что-то еще?",
            reply_markup=reply_markup,
        )
        return TEXT_PROMPT_HANDLER
    else:
        await update.message.reply_text("Произошла ошибка, попробуйте снова")
        return MAIN_MENU


def error(update, context):
    print(f"Error: {context.error}")
    update.message.reply_text("Произошла ошибка, попробуйте снова позже.")


def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("menu", main_menu))

    application.add_handler(
        ConversationHandler(
            entry_points=[CommandHandler("start", start)],
            states={
                MAIN_MENU: [CallbackQueryHandler(main_menu)],
                MAIN_MENU: [MessageHandler(filters.TEXT, main_menu)],
                CLIENT_CHOICE: [CallbackQueryHandler(client_choice)],
                CHOOSING_ACTION: [CallbackQueryHandler(choosing_action)],
                CLIENT_NAME: [MessageHandler(filters.TEXT, client_name)],
                CLIENT_SELECTION: [
                    CallbackQueryHandler(client_selection, pattern="^select_\\d+$"),
                ],
                CLIENT_SURNAME: [MessageHandler(filters.TEXT, client_surname)],
                CLIENT_WEIGHT: [MessageHandler(filters.TEXT, client_weight)],
                CLIENT_ACTION: [CallbackQueryHandler(client_action)],
                CLIENT_ACTIVITY_LEVEL_CHOICE: [
                    CallbackQueryHandler(client_activity_level_choice)
                ],
                CLIENT_GOAL: [CallbackQueryHandler(client_goal)],
                CLIENT_ALLERGIES: [MessageHandler(filters.TEXT, client_allergies)],
                CLIENT_YES_PRODUCTS: [
                    MessageHandler(filters.TEXT, client_yes_products)
                ],
                CLIENT_NO_PRODUCTS: [MessageHandler(filters.TEXT, client_no_products)],
                CLIENT_CALORIES: [MessageHandler(filters.TEXT, client_calories)],
                GENERATE_RESPONSE: [CallbackQueryHandler(generate_response)],
                CREATING_PLAN: [CallbackQueryHandler(creating_plan)],
                MENU_OPTIONS: [CallbackQueryHandler(menu_options)],
                EDIT_PLAN_COMMENT: [MessageHandler(filters.TEXT, edit_plan_comment)],
                CHOOSING_GOAL: [MessageHandler(filters.TEXT, handle_training_goal)],
                CHOOSING_MUSCLE_GROUP: [CallbackQueryHandler(handle_muscle_group)],
                TRAINING_WEEK: [CallbackQueryHandler(training_week)],
                PLAN_HANDLER: [CallbackQueryHandler(plan_handler)],
                DOWNLOAD_PDF: [CallbackQueryHandler(download_plan_pdf)],
                SOCIAL_MEDIA: [MessageHandler(filters.TEXT, social_media)],
                CONTENT_GOAL: [MessageHandler(filters.TEXT, content_goal)],
                CONTENT_PROMPT: [CallbackQueryHandler(content_prompt)],
                CONTENT_PROMPT_HANDLER: [CallbackQueryHandler(content_prompt_handler)],
                CONTENT_SALES: [MessageHandler(filters.TEXT, content_sales)],
                CONTENT_CHANGE: [MessageHandler(filters.TEXT, content_change)],
                TEXT_PROMPT_HANDLER: [CallbackQueryHandler(text_prompt_handler)],
                TEXT_CHANGE: [MessageHandler(filters.TEXT, text_change)],
                TEXT_GENERATION: [MessageHandler(filters.TEXT, text_generation)],
            },
            fallbacks=[],
        )
    )

    application.run_polling()


if __name__ == "__main__":
    main()
