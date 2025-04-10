from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    CallbackContext,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    CallbackQueryHandler,
)
from telegram.ext import Application, BasePersistence
from .models import Coach, Client, Subscription, ChatMapping
from fpdf import FPDF
from typing import Dict, List, Optional, Any
import logging
from asgiref.sync import sync_to_async
import os
from telegram import BotCommand, Bot
from dotenv import load_dotenv
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.timezone import now
import requests
import json
import hashlib
import hmac
from django.shortcuts import render
import stripe
from stripe import error
from stripe import StripeError, SignatureVerificationError
from django.utils import timezone
import datetime
from telegram.ext import PicklePersistence
import time
from django.db import transaction
import shutil
from datetime import datetime, timedelta
import asyncio
from django.http import HttpResponse
from .tasks import generate_openai_response_task

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
SUBSCRIPTION = 44
EDIT_CLIENT = 45
CLIENTS_HANDLER = 46
HANDLE_TRAINING_TYPE = 47
HANDLE_WORKOUT_TYPE = 48
CLIENT_DATA_QUERY = 49
CLIENT_DATA_MSG = 50
EDIT_CLIENT_DATA_HANDLER = 51
GET_CLIENTS = 52
COACH_FIELD = 53
APPROACH = 54
REQUEST = 55
TARGET = 56
PRODUCT = 57
FIELDS = 58
EFFECT = 59
POSITIONING = 60
EDIT_POS_HANDLER = 61
SAVE_POS_HANDLER = 62
ONLINE = 63
GET_POS = 64
NEW_CLIENT = 65
SUB_HANDLER = 66
CUSTOMER_EMAIL = 67
CANCEL_SUB_HANDLER = 68
REELS_PROMPT_HANDLER = 69
REELS_CHANGE = 70
REELS_GENERATION = 71
NEW_CLIENT_NAME = 72


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")


question = ""

messages = [
    {
        "role": "system",
        "content": "You are the nutritionist and coach marketing expert",
    }
]

TINKOFF_PASSWORD = os.getenv("TINKOFF_PASSWORD")
TINKOFF_TERMINAL_KEY = "1743522430515DEMO"

stripe.api_key = os.getenv("STRIPE_API_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

today = now()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


@sync_to_async
def update_chat_mapping(telegram_id, state=None, context=None):
    mapping, created = ChatMapping.objects.update_or_create(
        telegram_id=telegram_id,
        defaults={"state": state, "context": context},
    )
    return mapping


@sync_to_async
def get_chat_mapping(telegram_id):
    return ChatMapping.objects.filter(telegram_id=telegram_id).first()


async def set_bot_commands(application):
    commands = [
        BotCommand("menu", "Главное меню"),
        BotCommand("clients", "Список всех клиентов"),
    ]
    await application.bot.set_my_commands(commands)


def generate_signature(data):
    print("generate signature func is started")
    """
    Функция для генерации подписи для запроса к Тинькофф согласно документации MAPI
    """
    values_to_encode = {}

    for key, value in data.items():
        if not isinstance(value, (dict, list)):
            values_to_encode[key] = "" if value is None else str(value)

    values_to_encode["Password"] = TINKOFF_PASSWORD
    print(f"password {TINKOFF_PASSWORD}")

    sorted_keys = sorted(values_to_encode.keys())
    sorted_values = [values_to_encode[key] for key in sorted_keys]

    print(f"sorted_values:{sorted_values}")

    concatenated = "".join(sorted_values)

    token = hashlib.sha256(concatenated.encode("utf-8")).hexdigest()
    print(f"{token}")

    return token


async def initiate_initial_payment_async(amount, telegram_id):
    """Async wrapper for the synchronous payment function"""
    return await sync_to_async(initiate_initial_payment)(amount, telegram_id)


def initiate_initial_payment(amount, telegram_id):
    customer_key = str(telegram_id)
    rebill_id = str(telegram_id)
    order_id = f"order_{telegram_id}_{int(time.time())}"
    request_data = {
        "TerminalKey": TINKOFF_TERMINAL_KEY,
        "Amount": int(amount * 100),  # Amount in kopecks
        "OrderId": order_id,
        "Description": "Initial subscription payment",
        "DATA": {
            "telegram_id": telegram_id,
        },
        "CustomerKey": customer_key,
        "Recurrent": "Y",  # Mark as recurring payment
    }
    # Generate signature
    print("request_data before signature:")
    for k, v in request_data.items():
        if isinstance(v, dict):
            print(f"{k}: [dict]")
        else:
            print(f"{k}: {v} (type: {type(v)})")
    signature = generate_signature(request_data)
    request_data["Token"] = signature
    print(f"{signature}")
    # Send request
    response = requests.post("https://securepay.tinkoff.ru/v2/Init", json=request_data)
    print(f"{response.status_code}")

    if response.status_code == 200:
        response_data = response.json()  # Define response_data first
        print(f"{response_data}")  # Then print it

        if response_data.get("Success"):
            # Save initial order info
            subscription, created = Subscription.objects.update_or_create(
                customer_key=customer_key,
                rebill_id=rebill_id,
                defaults={
                    "status": "pending",
                    "amount": amount,
                    "payment_method": "tinkoff",
                },
            )
            subscription.save()
            return response_data.get("PaymentURL")
    return None


@csrf_exempt
def tinka_webhook(request):
    print("Webhook received")
    if request.method != "POST":
        print("Method not allowed")
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body)
        print(f"Webhook data received: {data}")

        # Get token from data
        token = data.get("Token")
        print(f"Token received: {token}")

        # Verify signature (but allow processing even if verification fails during testing)
        is_valid = verify_signature(data, token)
        print(f"Signature valid: {is_valid}")

        # For testing, we'll proceed even if signature is invalid
        # In production, you should uncomment the following lines:
        if not is_valid:
            print("Invalid signature")
            return JsonResponse({"error": "Invalid signature"}, status=400)

        status = data.get("Status")
        payment_id = data.get("PaymentId")
        order_id = data.get("OrderId")
        rebill_id = data.get("RebillId")

        print(
            f"Status: {status}, PaymentId: {payment_id}, OrderId: {order_id}, RebillId: {rebill_id}"
        )

        # Extract customer key from OrderId
        customer_key = None
        if order_id and "_" in order_id:
            parts = order_id.split("_")
            if len(parts) >= 2:
                customer_key = parts[1]
                print(f"Extracted customer_key: {customer_key}")

        if not customer_key:
            print("Missing customer identification")
            return JsonResponse(
                {"error": "Missing customer identification"}, status=400
            )

        # Process the subscription update
        with transaction.atomic():
            subscription = Subscription.objects.filter(
                customer_key=customer_key
            ).first()

            if not subscription:
                print(f"Subscription not found for customer {customer_key}")
                return JsonResponse({"error": "Subscription not found"}, status=404)

            print(
                f"Found subscription for customer {customer_key}: {subscription.status}"
            )

            # For the initial payment that completes successfully
            if status in ["AUTHORIZED", "CONFIRMED"] and rebill_id:
                # Save RebillId for future recurring payments
                subscription.rebill_id = rebill_id
                print(f"Saved rebill_id: {rebill_id}")
                subscription.payment_id = payment_id

            if status == "CONFIRMED":
                subscription.status = "active"
                subscription.payment_id = payment_id

                if not subscription.start_date or subscription.is_expired():
                    subscription.start_date = now()

                subscription.expires_at = now() + timedelta(
                    days=subscription.duration_days
                )

                subscription.save()
                print(f"Subscription activated for customer {customer_key}")

                # Send Telegram notification
                send_telegram_message(
                    customer_key,
                    "Оплата прошла успешно! Ваша подписка активирована, перейдите в главное меню слева внизу",
                )

            elif status in ["CANCELED", "REJECTED"]:
                subscription.status = "pending"
                subscription.save()
                print(f"Payment failed for customer {customer_key}, status: {status}")

                # Send Telegram notification
                send_telegram_message(
                    customer_key,
                    "Платеж не прошел. Пожалуйста, проверьте данные карты.",
                )

        return HttpResponse("OK", status=200)

    except Exception as e:
        print(f"Error processing webhook: {e}")
        return JsonResponse({"error": "Internal server error"}, status=500)


def send_telegram_message(telegram_id, message):
    """
    Функция для отправки сообщения в Telegram
    """
    bot = Bot(token=BOT_TOKEN)
    try:
        asyncio.run(bot.send_message(chat_id=telegram_id, text=message))
    except Exception as e:
        print(f"Ошибка при отправке сообщения в Telegram: {e}")


def process_recurring_payment(telegram_id, amount):
    try:
        # Get subscription with saved RebillId
        subscription = Subscription.objects.get(
            customer_key=telegram_id, status="active"
        )

        if not subscription.rebill_id:
            return {
                "status": "error",
                "message": "No rebill ID found for recurring payment",
            }

        # Step 1: Call Init to get PaymentId
        order_id = f"recur_{telegram_id}_{int(time.time())}"
        init_data = {
            "TerminalKey": TINKOFF_TERMINAL_KEY,
            "Amount": int(amount * 100),
            "OrderId": order_id,
            "Description": "Recurring subscription payment",
        }

        signature = generate_signature(init_data)
        init_data["Token"] = signature

        init_response = requests.post(
            "https://securepay.tinkoff.ru/v2/Init", json=init_data
        )

        if init_response.status_code != 200:
            return {"status": "error", "message": "Failed to initialize payment"}

        init_result = init_response.json()
        if not init_result.get("Success"):
            return {
                "status": "error",
                "message": init_result.get("Message", "Payment initialization failed"),
            }

        payment_id = init_result.get("PaymentId")

        # Step 2: Call Charge with RebillId and PaymentId
        charge_data = {
            "TerminalKey": TINKOFF_TERMINAL_KEY,
            "PaymentId": payment_id,
            "RebillId": subscription.rebill_id,
        }

        signature = generate_signature(charge_data)
        charge_data["Token"] = signature

        charge_response = requests.post(
            "https://securepay.tinkoff.ru/v2/Charge", json=charge_data
        )

        if charge_response.status_code != 200:
            return {"status": "error", "message": "Failed to charge payment"}

        charge_result = charge_response.json()
        if not charge_result.get("Success"):
            return {
                "status": "error",
                "message": charge_result.get("Message", "Payment charge failed"),
            }

        # If successful, update subscription
        if charge_result.get("Status") == "CONFIRMED":
            subscription.renew(subscription.duration_days)
            subscription.payment_id = payment_id
            subscription.save()

            # Notify customer
            send_telegram_message(telegram_id, "Ваша подписка успешно продлена!")

            return {"status": "success", "message": "Subscription renewed successfully"}
        else:
            return {"status": "pending", "message": "Payment is processing"}

    except Subscription.DoesNotExist:
        return {"status": "error", "message": "No active subscription found"}
    except Exception as e:
        logger.error(f"Error in recurring payment: {e}")
        return {"status": "error", "message": str(e)}


def verify_signature(data, received_token):
    """
    Verify Tinkoff payment notification signature according to their documentation
    with improved debugging and handling of different data types
    """
    # Create a copy of the data without the Token field
    data_copy = {
        k: v for k, v in data.items() if k != "Token" and k not in ["Receipt", "DATA"]
    }

    # Add password
    data_copy["Password"] = TINKOFF_PASSWORD

    # Convert all values to strings with special handling for booleans
    data_copy = {
        k: "true" if v is True else "false" if v is False else str(v)
        for k, v in data_copy.items()
    }

    # Print the prepared data for debugging
    print("Prepared data for signature calculation:")
    for k in sorted(data_copy.keys()):
        print(f"  {k}: {data_copy[k]}")

    # Sort alphabetically by key
    sorted_values = [data_copy[key] for key in sorted(data_copy.keys())]

    # Concatenate all values
    concat_string = "".join(sorted_values)
    print(f"Concatenated string: {concat_string}")

    # Apply SHA-256 hash function
    import hashlib

    calculated_token = hashlib.sha256(concat_string.encode("utf-8")).hexdigest()
    print(f"Calculated token: {calculated_token}")
    print(f"Received token: {received_token}")

    # Compare with the received token
    return calculated_token.lower() == received_token.lower()


def create_stripe_subscription(customer_email, price_id, telegram_id):
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="subscription",
            customer_email=customer_email,
            line_items=[{"price": price_id, "quantity": 1}],
            metadata={"telegram_id": telegram_id},
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
        )
        return session.url
    except stripe.error.StripeError as e:
        print(f"Stripe error: {e}")
        return None


@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.headers.get("Stripe-Signature")
    endpoint_secret = STRIPE_WEBHOOK_SECRET

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)

        # 🔄 Когда пользователь завершил оплату (первая подписка)
        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            telegram_id = session.get("metadata", {}).get("telegram_id")
            subscription_id = session.get("subscription")

            try:
                subscription = Subscription.objects.get(customer_key=telegram_id)

                subscription.start_date = now()
                subscription.subscription_id = subscription_id
                subscription.status = "active"
                subscription.expires_at = now() + timedelta(
                    days=subscription.duration_days
                )
                subscription.save()

                send_telegram_message(
                    telegram_id,
                    "Оплата прошла успешно! Ваша подписка активирована, перейдите в главное меню слева внизу.",
                )
                return JsonResponse({"status": "success"})

            except Subscription.DoesNotExist:
                return JsonResponse(
                    {"status": "error", "message": "Subscription not found"},
                    status=404,
                )

        # 🔁 Рекуррентный платёж прошёл — обновляем даты
        elif event["type"] == "invoice.paid":
            invoice = event["data"]["object"]
            subscription_id = invoice.get("subscription")

            # Add this check to avoid processing the initial payment invoice
            if invoice.get("billing_reason") == "subscription_create":
                # Skip processing for initial subscription creation
                return JsonResponse({"status": "initial invoice skipped"}, status=200)

            try:
                stripe_sub = stripe.Subscription.retrieve(subscription_id)
                current_period_start = datetime.fromtimestamp(
                    stripe_sub["current_period_start"], tz=timezone.utc
                )
                current_period_end = datetime.fromtimestamp(
                    stripe_sub["current_period_end"], tz=timezone.utc
                )
                subscription = Subscription.objects.get(subscription_id=subscription_id)
                subscription.start_date = current_period_start
                subscription.expires_at = current_period_end
                subscription.status = "active"
                subscription.save()
            except Subscription.DoesNotExist:
                print("Subscription not found for invoice.paid")

            return JsonResponse({"status": "received"}, status=200)

    except stripe.error.SignatureVerificationError as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@sync_to_async
def get_or_create_coach(telegram_id, name):
    print("get_or_create_coach started")
    try:
        coach, created = Coach.objects.get_or_create(
            telegram_id=telegram_id, defaults={"name": name}
        )
        return coach, created
    except Exception as e:
        print(f"{e}")
        raise e


async def entry_point(update: Update, context: CallbackContext):
    """Handle incoming messages and restore conversation state if needed"""
    telegram_id = update.message.from_user.id
    context.user_data["telegram_id"] = telegram_id

    # Try to get existing mapping
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.state:
        # Restore context
        if mapping.context:
            context.user_data.update(mapping.context)

        # Redirect to the appropriate handler based on saved state
        if mapping.state == SUBSCRIPTION:
            return await main_menu(update, context)
        elif mapping.state == CHOOSING_ACTION:
            return await main_menu(update, context)
        # Add other states as needed

    # If no saved state or couldn't restore, go to start
    return await start(update, context)


@sync_to_async
def reset_conversation_state(telegram_id):
    print("reset_conversation")
    try:
        # Delete any existing chat mapping
        ChatMapping.objects.filter(telegram_id=telegram_id).delete()
        print("deleted")
        return True
    except Exception as e:
        logger.error(f"Error resetting conversation state: {e}")
        return False


async def start(update: Update, context: CallbackContext):
    logger.info("Команда /start вызвана пользователем: %s", update.message.from_user.id)

    telegram_id = update.message.from_user.id
    print(f"telegram_id")
    name = update.message.from_user.first_name or "Anonymous"
    context.user_data["telegram_id"] = telegram_id

    await reset_conversation_state(telegram_id)

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
    keyboard = [
        [
            InlineKeyboardButton(
                "Подписка на месяц - 3000р/месяц (30 eur)", callback_data="month_3000"
            ),
        ],
        [
            InlineKeyboardButton(
                "Подписка на 3 месяца - 2300р/месяц (23 eur)",
                callback_data="3month_2300",
            ),
        ],
        [
            InlineKeyboardButton(
                "Подписка на 6 месяцев - 1800р/месяц (18 eur)",
                callback_data="6month_1800",
            ),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Привет! Я бот, который может <b>создавать программы питания и тренировок</b> для твоих клиентов, <b>определить твое позиционирование, создать контент-план, тексты и сценарии для рилс,</b> а еще я обладаю большой базой знаний для тренеров.\n"
        "<b>Бот использует ИИ</b>, поэтому подписка платная, но он сэкономит тебе часы работы!\n<b>Выбери подходящий тариф</b>\n"
        "<a href='https://www.basetraining.site/bot-offer'>ОФЕРТА</a>, <a href='https://www.basetraining.site/policy'>Политика конфиденциальности</a>.",
        reply_markup=reply_markup,
        parse_mode="HTML",  # Позволяет использовать разметку Markdown для ссылок
    )
    await update_chat_mapping(telegram_id, SUBSCRIPTION, context.user_data)
    return SUBSCRIPTION


@sync_to_async
def get_subscription(coach):
    return coach.subscription.first()


async def subscription(update: Update, context: CallbackContext):
    query = update.callback_query
    telegram_id = query.from_user.id
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    subscription_choice = query.data
    context.user_data["subscription_choice"] = subscription_choice

    await query.answer()
    keyboard = [
        [
            InlineKeyboardButton("Оплата картой (весь мир)", callback_data="world"),
        ],
        [
            InlineKeyboardButton(
                "Оплата картой РФ",
                callback_data="rus",
            ),
        ],
        [
            InlineKeyboardButton(
                "Назад к выбору подписки",
                callback_data="sub",
            ),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        f"Выберите метод оплаты:",
        reply_markup=reply_markup,
    )
    await update_chat_mapping(telegram_id, SUB_HANDLER, context.user_data)
    return SUB_HANDLER


async def sub_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    telegram_id = query.from_user.id
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    coach = await sync_to_async(Coach.objects.get)(telegram_id=telegram_id)
    subscription, created = await sync_to_async(Subscription.objects.get_or_create)(
        customer_key=telegram_id, coach=coach, rebill_id=telegram_id
    )
    choice = context.user_data.get("subscription_choice")
    if query.data == "sub":
        keyboard = [
            [
                InlineKeyboardButton(
                    "Подписка на месяц - 3000р/месяц (30 eur)",
                    callback_data="month_3000",
                ),
            ],
            [
                InlineKeyboardButton(
                    "Подписка на 3 месяца - 2300р/месяц (23 eur)",
                    callback_data="3month_2300",
                ),
            ],
            [
                InlineKeyboardButton(
                    "Подписка на 6 месяцев - 1800р/месяц (18 eur)",
                    callback_data="6month_1800",
                ),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Привет! Я бот, который может <b>создавать программы питания и тренировок</b> для твоих клиентов, <b>определить твое позиционирование, создать контент-план, тексты и сценарии для рилс,</b> а еще я обладаю большой базой знаний для тренеров.\n"
            "<b>Бот использует ИИ</b>, поэтому подписка платная, но он сэкономит тебе часы работы!\n<b>Выбери подходящий тариф</b>\n"
            "<a href='https://www.basetraining.site/bot-offer'>ОФЕРТА</a>, <a href='https://www.basetraining.site/policy'>Политика конфиденциальности</a>.",
            reply_markup=reply_markup,
            parse_mode="HTML",  # Позволяет использовать разметку Markdown для ссылок
        )

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update_chat_mapping(telegram_id, SUBSCRIPTION, context.user_data)

        return SUBSCRIPTION

    elif query.data == "rus":
        subscription.payment_method = "tinkoff"

        if choice == "month_3000":
            subscription.amount = 3000
            subscription.duration_days = 30
        elif choice == "3month_2300":
            subscription.amount = 6900
            subscription.duration_days = 90
        elif choice == "6month_1800":
            subscription.amount = 10800
            subscription.duration_days = 180
        else:
            await query.answer("Ошибка выбора")
            return MAIN_MENU

        payment_url = await initiate_initial_payment_async(
            subscription.amount, telegram_id
        )  # Здесь вызовите вашу функцию для запроса к Тинькофф
        await query.edit_message_text(
            f"Перейдите по следующей ссылке для оплаты: {payment_url}",
        )

    elif query.data == "world":
        subscription.payment_method = "stripe"
        await query.edit_message_text("Введите ваш e-mail:")

        await update_chat_mapping(telegram_id, CUSTOMER_EMAIL, context.user_data)

        return CUSTOMER_EMAIL


async def customer_email(update: Update, context: CallbackContext):
    customer_email = update.message.text.strip()
    telegram_id = update.message.from_user.id
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    context.user_data["customer_email"] = customer_email
    telegram_id = context.user_data.get("telegram_id")
    subscription = await sync_to_async(Subscription.objects.get)(
        customer_key=telegram_id
    )

    choice = context.user_data.get("subscription_choice")

    if choice == "month_3000":
        subscription.amount = 30
        subscription.duration_days = 30
        price_id = "price_1R1rEjAnFE16axxx9nhRX3dn"
    elif choice == "3month_2300":
        subscription.amount = 69
        subscription.duration_days = 90
        price_id = "price_1R1rGaAnFE16axxxbwK52VBt"
    elif choice == "6month_1800":
        subscription.amount = 108
        subscription.duration_days = 180
        price_id = "price_1R1rHQAnFE16axxxnFqy9K3l"
    else:
        await update.message.reply_text("Ошибка выбора")
        return MAIN_MENU
    url = create_stripe_subscription(customer_email, price_id, telegram_id)
    if url:
        await update.message.reply_text(
            f'Ваша <a href="{url}">ссылка на оплату</a>', parse_mode="HTML"
        )


async def cancel_subscription(update: Update, context: CallbackContext):
    telegram_id = update.message.from_user.id
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    keyboard = [
        [
            InlineKeyboardButton(
                "Да, отменить",
                callback_data="yes",
            ),
        ],
        [
            InlineKeyboardButton(
                "Назад в меню",
                callback_data="main_menu",
            ),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Вы уверены, что хотите отменить подписку?",
        reply_markup=reply_markup,
    )
    await update_chat_mapping(telegram_id, CANCEL_SUB_HANDLER, context.user_data)
    return CANCEL_SUB_HANDLER


async def cancel_subscription_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    telegram_id = query.from_user.id

    # Получение данных о клиенте
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"Mapping found and restored: {mapping.state}")

    try:
        # Получаем подписку клиента
        subscription = await sync_to_async(Subscription.objects.get)(
            customer_key=telegram_id
        )
    except Subscription.DoesNotExist:
        await query.answer()
        await query.edit_message_text("Подписка не найдена.")
        return

    # Ответ на callback
    await query.answer()

    # Получаем выбор пользователя
    user_choice = query.data

    if user_choice == "yes":
        try:
            # Обработка отмены подписки для Tinkoff
            if subscription.payment_method == "tinkoff":
                subscription.status = "pending_cancellation"
                await sync_to_async(subscription.save)()
                await query.edit_message_text(
                    "Ваша подписка отменена. Она будет завершена в конце текущего периода."
                )

            # Обработка отмены подписки для Stripe
            elif subscription.payment_method == "stripe":
                try:
                    stripe.Subscription.modify(
                        subscription.subscription_id, cancel_at_period_end=True
                    )
                    subscription.status = "pending_cancellation"
                    await sync_to_async(subscription.save)()
                    await query.edit_message_text(
                        "Ваша подписка отменена. Она будет завершена в конце текущего периода."
                    )
                except stripe.error.StripeError as e:
                    logger.error(
                        f"Ошибка при отмене подписки через Stripe: {e.user_message}"
                    )
                    await query.edit_message_text(
                        "Ошибка при отмене подписки через Stripe. Попробуйте позже."
                    )

        except Exception as e:
            logger.error(f"Ошибка при отмене подписки: {e}")
            await query.edit_message_text(
                "Произошла ошибка при отмене подписки. Попробуйте снова."
            )
    elif user_choice == "main_menu":
        await update_chat_mapping(telegram_id, MAIN_MENU, context.user_data)
        return MAIN_MENU


def get_subscription_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Подписка на месяц - 3000р/месяц (30 eur)",
                    callback_data="month_3000",
                )
            ],
            [
                InlineKeyboardButton(
                    "Подписка на 3 месяца - 2300р/месяц (23 eur)",
                    callback_data="3month_2300",
                )
            ],
            [
                InlineKeyboardButton(
                    "Подписка на 6 месяцев - 1800р/месяц (18 eur)",
                    callback_data="6month_1800",
                )
            ],
        ]
    )


async def main_menu(update: Update, context: CallbackContext):
    # Получаем telegram_id
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        telegram_id = query.from_user.id
    else:
        telegram_id = update.message.from_user.id

    context.user_data["telegram_id"] = telegram_id

    # Восстанавливаем контекст
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")

    # Получаем тренера
    coach = await sync_to_async(Coach.objects.get)(telegram_id=telegram_id)

    # Получаем подписку
    try:
        subscription = await get_subscription(coach)
    except Subscription.DoesNotExist:
        subscription = None

    # Если подписки нет — предлагаем оплатить
    if not subscription:
        await update.message.reply_text(
            "Упс, похоже, что подписка закончилась. Давай выберем подходящий тариф!",
            reply_markup=get_subscription_keyboard(),
        )
        await update_chat_mapping(telegram_id, SUBSCRIPTION, context.user_data)
        return SUBSCRIPTION

    # Проверка на истёкшую подписку (была ли она просрочена на день)
    expires_at = subscription.expires_at
    if expires_at and expires_at.date() <= (datetime.now().date() - timedelta(days=1)):
        subscription.status = "pending"
        await sync_to_async(subscription.save)()

    # Если подписка активна или ожидает отмены — показываем главное меню
    if subscription.status in ["active", "pending_cancellation"]:
        keyboard = [
            [InlineKeyboardButton("Создать меню для клиента", callback_data="1")],
            [
                InlineKeyboardButton(
                    "Создать тренировочную программу", callback_data="2"
                )
            ],
            [InlineKeyboardButton("Позиционирование", callback_data="3")],
            [InlineKeyboardButton("Создать идеи для контента", callback_data="4")],
            [InlineKeyboardButton("Написать пост", callback_data="5")],
            [InlineKeyboardButton("Написать текст для REELS", callback_data="6")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        text = (
            "<b>Что ты хочешь сделать?:)</b>\n"
            "Дисклеймер: не забывай, что бот — просто помощник. Он может допускать ошибки "
            "и не несёт ответственность за результаты твоих клиентов.\n"
            "Проверяй информацию перед тем, как передать её клиенту.\n"
            "<b>Выбери нужное действие из меню.</b>"
        )

        if update.callback_query:
            await query.edit_message_text(
                text, reply_markup=reply_markup, parse_mode="HTML"
            )
        else:
            await update.message.reply_text(
                text, reply_markup=reply_markup, parse_mode="HTML"
            )

        return CHOOSING_ACTION

    # Во всех остальных случаях — снова предлагаем оформить подписку
    await update.message.reply_text(
        "Упс, похоже, что у тебя ещё нет активной подписки. Давай выберем подходящий тариф!",
        reply_markup=get_subscription_keyboard(),
    )
    await update_chat_mapping(telegram_id, SUBSCRIPTION, context.user_data)
    return SUBSCRIPTION


def get_subscription_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Подписка на месяц - 3000р/месяц (30 eur)",
                    callback_data="month_3000",
                )
            ],
            [
                InlineKeyboardButton(
                    "Подписка на 3 месяца - 2300р/месяц (23 eur)",
                    callback_data="3month_2300",
                )
            ],
            [
                InlineKeyboardButton(
                    "Подписка на 6 месяцев - 1800р/месяц (18 eur)",
                    callback_data="6month_1800",
                )
            ],
        ]
    )


async def new_client(update: Update, context: CallbackContext):
    telegram_id = update.message.from_user.id
    context.user_data["telegram_id"] = telegram_id

    # Восстановление состояния
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")

    # Получаем тренера
    coach = await sync_to_async(Coach.objects.get)(telegram_id=telegram_id)

    # Получаем подписку
    try:
        subscription = await get_subscription(coach)
    except Subscription.DoesNotExist:
        subscription = None

    # Если подписки нет — предлагаем оплатить
    if not subscription:
        await update.message.reply_text(
            "Упс, похоже, что подписка закончилась. Давай выберем подходящий тариф!",
            reply_markup=get_subscription_keyboard(),
        )
        await update_chat_mapping(telegram_id, SUBSCRIPTION, context.user_data)
        return SUBSCRIPTION

    # Проверка на истёкшую подписку (была ли она просрочена на день)
    expires_at = subscription.expires_at
    if expires_at and expires_at.date() <= (datetime.now().date() - timedelta(days=1)):
        subscription.status = "pending"
        await sync_to_async(subscription.save)()

    # Если подписка неактивна или не в стадии отмены
    if subscription.status not in ["active", "pending_cancellation"]:
        await update.message.reply_text(
            "Упс, похоже, что у тебя ещё нет активной подписки. Давай выберем подходящий тариф!",
            reply_markup=get_subscription_keyboard(),
        )
        await update_chat_mapping(telegram_id, SUBSCRIPTION, context.user_data)
        return SUBSCRIPTION

    # Всё хорошо — продолжаем сценарий
    await update.message.reply_text("Введите имя нового клиента:")
    await update_chat_mapping(telegram_id, CLIENT_NAME, context.user_data)
    return NEW_CLIENT_NAME


async def new_client_name(update: Update, context: CallbackContext):
    telegram_id = context.user_data.get("telegram_id")
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return MAIN_MENU
    client_name = update.message.text.strip()
    try:
        coach, created = await sync_to_async(Coach.objects.get_or_create)(
            telegram_id=telegram_id
        )
        new_client = await sync_to_async(Client.objects.create)(
            name=client_name, coach=coach
        )

        context.user_data["selected_client_id"] = new_client.id
        await update.message.reply_text(
            f"Клиент {new_client.name} успешно добавлен!\n<b>Для корректной работы бота заполните все поля анкеты!</b>\nВведите фамилию клиента:"
        )
        await update_chat_mapping(telegram_id, CLIENT_SURNAME, context.user_data)
        return CLIENT_SURNAME
    except Exception as e:
        await update.message.reply_text("Произошла ошибка при добавлении клиента.")
        logger.error(f"Ошибка создания клиента: {e}")
        await update_chat_mapping(telegram_id, NEW_CLIENT, context.user_data)
        return NEW_CLIENT


async def choosing_action(update: Update, context: CallbackContext):
    query = update.callback_query
    telegram_id = context.user_data.get("telegram_id")
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return MAIN_MENU
    await query.answer()
    user_choice = query.data

    context.user_data["menu_action"] = user_choice
    await update_chat_mapping(telegram_id, CHOOSING_ACTION, context.user_data)

    if user_choice in ["1", "2"]:
        keyboard = [
            [InlineKeyboardButton("Выбрать клиента", callback_data="choose_client")],
            [
                InlineKeyboardButton(
                    "Добавить нового клиента", callback_data="add_client"
                )
            ],
            [InlineKeyboardButton("Назад в меню", callback_data="main_menu")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Выберите действие:", reply_markup=reply_markup)
        await update_chat_mapping(telegram_id, CLIENT_CHOICE, context.user_data)
        return CLIENT_CHOICE

    elif user_choice == "3":
        telegram_id = context.user_data.get("telegram_id")
        coach = await sync_to_async(Coach.objects.get)(telegram_id=telegram_id)
        print(f"coach_positioning: {coach.positioning}")
        if coach.positioning:
            keyboard = [
                [InlineKeyboardButton("Заполнить заново", callback_data="edit")],
                [
                    InlineKeyboardButton(
                        "Вернуться в главное меню", callback_data="main_menu"
                    )
                ],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "Твое позициониование уже заполнено, хочешь заполнить заново?",
                reply_markup=reply_markup,
                parse_mode="HTML",
            )
            await update_chat_mapping(telegram_id, GET_POS, context.user_data)
            return GET_POS

        else:
            keyboard = [
                [InlineKeyboardButton("Назад", callback_data="main_menu")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "<b>Тренером в каком направлении ты являешься?</b>",
                reply_markup=reply_markup,
                parse_mode="HTML",
            )
            await update_chat_mapping(telegram_id, COACH_FIELD, context.user_data)
            return COACH_FIELD

    elif user_choice == "4":
        telegram_id = context.user_data.get("telegram_id")
        coach = await sync_to_async(Coach.objects.get)(telegram_id=telegram_id)
        if coach.positioning:
            keyboard = [
                [InlineKeyboardButton("Назад", callback_data="main_menu")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "В какую соц сеть будем делать контент-план?",
                reply_markup=reply_markup,
                parse_mode="HTML",
            )
            return CONTENT_GOAL
        else:
            keyboard = [
                [InlineKeyboardButton("Назад", callback_data="main_menu")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "Чтобы сделать релевантный контент-план, нужно сначала определиться с позиционированием.\nЭто быстро, всего несколько вопросов!\nТренером в каком направлении ты являешься?",
                reply_markup=reply_markup,
                parse_mode="HTML",
            )
            await update_chat_mapping(telegram_id, COACH_FIELD, context.user_data)
            return COACH_FIELD

    elif user_choice == "5":
        telegram_id = context.user_data.get("telegram_id")
        coach = await sync_to_async(Coach.objects.get)(telegram_id=telegram_id)
        if coach.positioning:
            keyboard = [
                [InlineKeyboardButton("Назад", callback_data="main_menu")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "<b>На какую тему будем делать текст?</b> Постарайся подробно описать, что ты хочешь донести этим текстом, какую мысль или идею, а я помогу тебе со всем остальным!\nМожешь использовать темы из контент-плана",
                reply_markup=reply_markup,
                parse_mode="HTML",
            )
            await update_chat_mapping(telegram_id, TEXT_GENERATION, context.user_data)
            return TEXT_GENERATION
        else:
            keyboard = [
                [InlineKeyboardButton("Назад", callback_data="main_menu")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "Чтобы сделать релевантный текст к посту, нужно сначала определиться с позиционированием.\nЭто быстро, всего несколько вопросов!\nТренером в каком направлении ты являешься?",
                reply_markup=reply_markup,
                parse_mode="HTML",
            )
            await update_chat_mapping(telegram_id, COACH_FIELD, context.user_data)
            return COACH_FIELD

    elif user_choice == "6":
        telegram_id = context.user_data.get("telegram_id")
        coach = await sync_to_async(Coach.objects.get)(telegram_id=telegram_id)
        if coach.positioning:
            keyboard = [
                [InlineKeyboardButton("Назад", callback_data="main_menu")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "<b>На какую тему будем делать рилс?</b>\nЕсли нет идей - создай сначала контент-план (перейди в меню)",
                reply_markup=reply_markup,
                parse_mode="HTML",
            )
            await update_chat_mapping(telegram_id, REELS_GENERATION, context.user_data)
            return REELS_GENERATION
        else:
            keyboard = [
                [InlineKeyboardButton("Назад", callback_data="main_menu")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "Чтобы сделать релевантный текст к REELS, нужно сначала определиться с позиционированием.\nЭто быстро, всего несколько вопросов!\nТренером в каком направлении ты являешься?",
                reply_markup=reply_markup,
                parse_mode="HTML",
            )
            await update_chat_mapping(telegram_id, COACH_FIELD, context.user_data)
            return COACH_FIELD

    await update_chat_mapping(telegram_id, CHOOSING_ACTION, context.user_data)
    return CHOOSING_ACTION


async def client_choice(update: Update, context: CallbackContext):
    query = update.callback_query
    telegram_id = context.user_data.get("telegram_id")
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return MAIN_MENU
    await query.answer()

    user_choice = query.data

    context.user_data["client_action"] = user_choice
    data = context.user_data.get("menu_action")

    if user_choice == "choose_client":
        keyboard = [
            [InlineKeyboardButton("Назад", callback_data="main_menu")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "Введите имя клиента, чтобы выбрать из существующих:",
            reply_markup=reply_markup,
            parse_mode="HTML",
        )
        await update_chat_mapping(telegram_id, CLIENT_NAME, context.user_data)
        return CLIENT_NAME

    elif user_choice == "add_client":
        keyboard = [
            [InlineKeyboardButton("Назад", callback_data="main_menu")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "Введите имя нового клиента:",
            reply_markup=reply_markup,
            parse_mode="HTML",
        )
        await update_chat_mapping(telegram_id, CLIENT_NAME, context.user_data)
        return CLIENT_NAME

    else:
        await query.edit_message_text("Неверный выбор. Попробуй еще раз.")
        await update_chat_mapping(telegram_id, CLIENT_CHOICE, context.user_data)
        return CLIENT_CHOICE


async def client_name(update: Update, context: CallbackContext):
    telegram_id = context.user_data.get("telegram_id")
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return MAIN_MENU
    client_name = update.message.text.strip()
    action = context.user_data.get("client_action")

    if action == "choose_client":
        coach = await sync_to_async(Coach.objects.get)(telegram_id=telegram_id)
        clients = await sync_to_async(Client.objects.filter)(
            name__icontains=client_name, coach=coach
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
            await update_chat_mapping(telegram_id, CLIENT_SELECTION, context.user_data)
            return CLIENT_SELECTION
        else:
            await update.message.reply_text(
                "Клиенты с таким именем не найдены. Попробуйте снова."
            )
            await update_chat_mapping(telegram_id, CLIENT_NAME, context.user_data)
            return CLIENT_NAME

    elif action == "add_client":
        telegram_id = context.user_data.get("telegram_id")

        try:
            coach, created = await sync_to_async(Coach.objects.get_or_create)(
                telegram_id=telegram_id
            )
            new_client = await sync_to_async(Client.objects.create)(
                name=client_name, coach=coach
            )

            context.user_data["selected_client_id"] = new_client.id
            await update.message.reply_text(
                f"Клиент {new_client.name} успешно добавлен!\n<b>Для корректной работы бота заполните все поля анкеты!</b>\nВведите фамилию клиента:"
            )
            await update_chat_mapping(telegram_id, CLIENT_SURNAME, context.user_data)
            return CLIENT_SURNAME
        except Exception as e:
            await update.message.reply_text("Произошла ошибка при добавлении клиента.")
            logger.error(f"Ошибка создания клиента: {e}")
            await update_chat_mapping(telegram_id, CLIENT_CHOICE, context.user_data)
            return CLIENT_CHOICE

    else:
        await update.message.reply_text("Ошибка при выборе действия. Попробуйте снова.")
        await update_chat_mapping(telegram_id, CLIENT_CHOICE, context.user_data)
        return CLIENT_CHOICE


async def client_selection(update: Update, context: CallbackContext):
    telegram_id = context.user_data.get("telegram_id")
    query = update.callback_query
    mapping = await get_chat_mapping(telegram_id)

    if mapping and mapping.context:
        context.user_data.update(mapping.context)
    else:
        return MAIN_MENU

    await query.answer()

    selected_client_id = query.data.split("_", 1)[1]
    logger.info(f"Пользователь выбрал клиента с ID: {selected_client_id}")

    try:
        coach = await sync_to_async(Coach.objects.get)(telegram_id=telegram_id)
        client = await sync_to_async(Client.objects.get)(
            id=selected_client_id, coach=coach
        )

        if not client:
            logger.warning("Клиент с введенным ID не найден.")
            await query.message.reply_text("Клиент не найден. Попробуйте снова.")
            await update_chat_mapping(telegram_id, CLIENT_NAME, context.user_data)
            return CLIENT_NAME

        context.user_data["selected_client_id"] = client.id

        plan_type = await client_action(update, context)

        if plan_type == "training":
            keyboard = [
                [InlineKeyboardButton("Начальный уровень", callback_data="beginner")],
                [InlineKeyboardButton("Средний уровень", callback_data="intermediate")],
                [InlineKeyboardButton("Продвинутый уровень", callback_data="advanced")],
                [InlineKeyboardButton("Назад в меню", callback_data="main_menu")],
            ]
            await query.edit_message_text(
                "Для какого уровня подготовки будет тренировка?",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            await update_chat_mapping(telegram_id, TRAINING_WEEK, context.user_data)
            return TRAINING_WEEK

        elif plan_type == "menu":
            required_fields = [
                client.name,
                client.weight,
                client.goal,
                client.calories,
                client.proteins,
                client.fats,
                client.carbs,
                client.yes_products,
                client.no_products,
            ]
            if any(field is None or field == "" for field in required_fields):
                await query.edit_message_text(
                    "Анкета клиента заполнена не до конца. Перейдите в список клиентов в меню и отредактируйте анкету клиента."
                )
                await update_chat_mapping(
                    telegram_id, CHOOSING_ACTION, context.user_data
                )
                return MAIN_MENU

            prompt = await creating_plan(update, context)
            if not prompt:
                await query.edit_message_text("Не удалось создать промпт.")
                return MAIN_MENU

            context.user_data["prompt"] = prompt

            # Сообщаем пользователю ДО вызова OpenAI
            await query.edit_message_text("Минутку, составляю меню!🌀")

            # Получаем ответ
            response = await generate_response(update, context)

            if not response:
                return CHOOSING_ACTION

            # Удаляем prompt, чтобы не переиспользовался случайно
            context.user_data.pop("prompt", None)

            keyboard = [
                [InlineKeyboardButton("Редактировать", callback_data="edit_menu")],
                [InlineKeyboardButton("Скачать в PDF", callback_data="download_pdf")],
                [InlineKeyboardButton("Назад в меню", callback_data="main_menu")],
            ]

            await query.edit_message_text(
                text=f"Вот ваш персонализированный план:\n\n{response}\n\n"
                "Что вы хотели бы сделать с планом?",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML",
            )
            await update_chat_mapping(telegram_id, MENU_OPTIONS, context.user_data)
            return MENU_OPTIONS

    except Coach.DoesNotExist:
        logger.error("Тренер не найден.")
        await query.message.reply_text("Тренер не найден.")
        await update_chat_mapping(telegram_id, CHOOSING_ACTION, context.user_data)
        return CHOOSING_ACTION

    except Exception as e:
        logger.error(f"Произошла ошибка при обработке запроса: {e}")
        await query.message.reply_text("Произошла ошибка при обработке запроса.")
        await update_chat_mapping(telegram_id, CHOOSING_ACTION, context.user_data)
        return CHOOSING_ACTION


async def plan_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    telegram_id = context.user_data.get("telegram_id")
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return MAIN_MENU
    if query:
        try:
            await query.answer()
            if query.data == "main_menu":
                return MAIN_MENU
            else:
                training_type = query.data
                context.user_data["training_type"] = training_type
        except Exception as e:
            logger.error(f"Произошла ошибка при обработке запроса: {e}")
            await query.message.reply_text("Произошла ошибка при обработке запроса.")
            await update_chat_mapping(
                telegram_id, CHOOSING_MUSCLE_GROUP, context.user_data
            )
            return CHOOSING_MUSCLE_GROUP
    prompt = await creating_plan(update, context)
    if prompt:
        await query.message.reply_text("Минутку, составляю план!🌀")
        response = await generate_response(update, context)
        if response:
            keyboard = [
                [InlineKeyboardButton("Редактировать", callback_data="edit_menu")],
                [InlineKeyboardButton("Скачать в PDF", callback_data="download_pdf")],
                [InlineKeyboardButton("Назад в меню", callback_data="main_menu")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.message.reply_text(
                text=f"Вот ваш персонализированный план:\n\n{response}\n\n"
                "Что вы хотели бы сделать с планом?",
                reply_markup=reply_markup,
                parse_mode="HTML",
            )
            await update_chat_mapping(telegram_id, MENU_OPTIONS, context.user_data)
            return MENU_OPTIONS


async def client_surname(update: Update, context: CallbackContext):
    telegram_id = update.message.from_user.id
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return MAIN_MENU
    client_id = context.user_data.get("selected_client_id")
    client = await sync_to_async(Client.objects.get)(id=client_id)
    client.surname = update.message.text.strip()
    await sync_to_async(client.save)()
    await update.message.reply_text(f"Введите вес клиента:")
    await update_chat_mapping(telegram_id, CLIENT_WEIGHT, context.user_data)
    return CLIENT_WEIGHT


async def client_weight(update: Update, context: CallbackContext):
    telegram_id = update.message.from_user.id
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return MAIN_MENU
    try:
        weight = float(update.message.text.strip())
        client_id = context.user_data.get("selected_client_id")
        client = await sync_to_async(Client.objects.get)(id=client_id)
        client.weight = weight
        await sync_to_async(client.save)()

        keyboard = [
            [InlineKeyboardButton("Низкий", callback_data="1.2")],
            [InlineKeyboardButton("Средний", callback_data="1.3")],
            [InlineKeyboardButton("Высокий", callback_data="1.4")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "Выберите уровень активности клиента:", reply_markup=reply_markup
        )
        await update_chat_mapping(
            telegram_id, CLIENT_ACTIVITY_LEVEL_CHOICE, context.user_data
        )
        return CLIENT_ACTIVITY_LEVEL_CHOICE

    except ValueError:
        await update.message.reply_text("Пожалуйста, введите вес в числовом формате.")
        await update_chat_mapping(telegram_id, CLIENT_WEIGHT, context.user_data)
        return CLIENT_WEIGHT


async def client_activity_level_choice(update: Update, context: CallbackContext):
    query = update.callback_query
    telegram_id = query.from_user.id
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return MAIN_MENU
    await query.answer()

    activity_level = query.data
    client_id = context.user_data.get("selected_client_id")
    client = await sync_to_async(Client.objects.get)(id=client_id)
    client.activity_level = activity_level
    await sync_to_async(client.save)()

    keyboard = [
        [InlineKeyboardButton("Похудение", callback_data="похудение")],
        [InlineKeyboardButton("Набор массы", callback_data="набор массы")],
        [InlineKeyboardButton("Тонус", callback_data="тонус")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.reply_text(
        "Теперь выберите цель клиента:", reply_markup=reply_markup
    )
    await update_chat_mapping(telegram_id, CLIENT_GOAL, context.user_data)
    return CLIENT_GOAL


# Обработка цели клиента
async def client_goal(update: Update, context: CallbackContext):
    query = update.callback_query
    telegram_id = query.from_user.id
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return MAIN_MENU
    await query.answer()

    goal = query.data
    client_id = context.user_data.get("selected_client_id")
    client = await sync_to_async(Client.objects.get)(id=client_id)
    client.goal = goal
    await sync_to_async(client.save)()

    await query.message.reply_text(
        "Есть ли у клиента аллергии? Введите продукты через запятую или напишите прочерк, если их нет:"
    )
    await update_chat_mapping(telegram_id, CLIENT_ALLERGIES, context.user_data)
    return CLIENT_ALLERGIES


async def client_allergies(update: Update, context: CallbackContext):
    telegram_id = update.message.from_user.id
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return MAIN_MENU
    allergies = update.message.text.strip()
    client_id = context.user_data.get("selected_client_id")
    client = await sync_to_async(Client.objects.get)(id=client_id)
    client.allergies = allergies
    await sync_to_async(client.save)()

    await update.message.reply_text(
        "Какие продукты обязательно должны присутствовать в рационе? Введите продукты через запятую или напишите прочерк:"
    )
    await update_chat_mapping(telegram_id, CLIENT_YES_PRODUCTS, context.user_data)
    return CLIENT_YES_PRODUCTS


async def client_yes_products(update: Update, context: CallbackContext):
    telegram_id = update.message.from_user.id
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return MAIN_MENU
    yes_products = update.message.text.strip()
    client_id = context.user_data.get("selected_client_id")
    client = await sync_to_async(Client.objects.get)(id=client_id)

    logger.info(f"Получены продукты, которые должны быть в рационе: {yes_products}")

    client.yes_products = yes_products
    await sync_to_async(client.save)()

    logger.info(f"Данные о продуктах клиента {client.name} успешно сохранены.")
    await update.message.reply_text(
        "Какие продукты НЕ должны присутствовать в рационе? Введите продукты через запятую или напишите прочерк:"
    )
    await update_chat_mapping(telegram_id, CLIENT_NO_PRODUCTS, context.user_data)

    return CLIENT_NO_PRODUCTS


async def client_no_products(update: Update, context: CallbackContext):
    telegram_id = context.user_data.get("telegram_id")
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return MAIN_MENU
    no_products = update.message.text.strip().lower()
    client_id = context.user_data.get("selected_client_id")
    client = await sync_to_async(Client.objects.get)(id=client_id)

    logger.info(f"Получены продукты, которые не могут быть в рационе: {no_products}")

    client.no_products = no_products
    await sync_to_async(client.save)()

    logger.info(
        f"Данные о запрещенных продуктах для клиента {client.name} успешно сохранены."
    )
    calories = await client_calories(update, context)
    if calories:
        plan_type = await client_action(update, context)
        print(f"plan_type {plan_type}")
        if plan_type:
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
                    [InlineKeyboardButton("Назад в меню", callback_data="main_menu")],
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(
                    "Для какого уровня подготовки будет тренировка?",
                    reply_markup=reply_markup,
                )
                await update_chat_mapping(telegram_id, TRAINING_WEEK, context.user_data)
                return TRAINING_WEEK
            await update.message.reply_text("Минутку, составляю план!🌀")
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
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await update.message.reply_text(
                        text=f"Вот ваш персонализированный план:\n\n{response}\n\n"
                        "Что вы хотели бы сделать с планом?",
                        reply_markup=reply_markup,
                        parse_mode="HTML",
                    )
                    await update_chat_mapping(
                        telegram_id, MENU_OPTIONS, context.user_data
                    )
                    return MENU_OPTIONS


async def client_calories(update: Update, context: CallbackContext):
    telegram_id = update.message.from_user.id
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return MAIN_MENU
    client_id = context.user_data.get("selected_client_id")
    client = await sync_to_async(Client.objects.get)(id=client_id)

    weight = client.weight

    activity_level = client.activity_level
    goal = client.goal

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

    client.calories = calories
    client.proteins = proteins
    client.fats = fats
    client.carbs = carbs
    await sync_to_async(client.save)()
    return client.calories


async def client_action(update: Update, context: CallbackContext):
    telegram_id = context.user_data.get("telegram_id")
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return MAIN_MENU
    logger.info(f"client action function has started")

    client_id = context.user_data.get("selected_client_id")
    client = await sync_to_async(Client.objects.get)(id=client_id)
    menu_action = context.user_data.get("menu_action", None)

    if menu_action == "1":
        context.user_data["plan_type"] = "menu"
        plan_type = "menu"
        await update_chat_mapping(telegram_id, CLIENT_ACTION, context.user_data)
        return plan_type

    elif menu_action == "2":
        context.user_data["plan_type"] = "training"
        plan_type = "training"
        await update_chat_mapping(telegram_id, CLIENT_ACTION, context.user_data)
        return plan_type

    else:
        logger.error("Неизвестное действие в меню.")
        await update_chat_mapping(telegram_id, CHOOSING_ACTION, context.user_data)
        return CHOOSING_ACTION


############################## NUTRITION PLAN #####################################


async def generate_response(update: Update, context: CallbackContext):
    telegram_id = context.user_data.get("telegram_id")
    mapping = await get_chat_mapping(telegram_id)

    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return MAIN_MENU

    prompt = context.user_data.get("prompt")
    if not prompt:
        logger.warning("Пустой prompt при вызове generate_response.")
        return MAIN_MENU

    try:
        # Запуск синхронной Celery-задачи в фоне
        task = generate_openai_response_task.delay(prompt)  # запуск задачи Celery

        # Подождем получения результата от Celery через callback
        response_text = await asyncio.to_thread(
            task.get
        )  # Получаем результат из Celery задачи

        if not response_text:
            raise ValueError("OpenAI вернул пустой ответ.")

        # Сохраняем в context для последующего использования (например, редактирования)
        context.user_data["response"] = response_text

        # Обновляем состояние и сохраняем контекст
        await update_chat_mapping(telegram_id, CHOOSING_ACTION, context.user_data)

        return response_text

    except Exception as e:
        logger.error(f"Ошибка в generate_response: {e}")

        error_message = "Произошла ошибка при генерации ответа. Попробуйте снова."

        if update.callback_query:
            await update.callback_query.message.reply_text(error_message)
        else:
            await update.message.reply_text(error_message)

        await update_chat_mapping(telegram_id, CHOOSING_ACTION, context.user_data)
        return CHOOSING_ACTION


async def creating_plan(update: Update, context: CallbackContext):
    telegram_id = context.user_data.get("telegram_id")
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return MAIN_MENU
    logger.info(f"Startint grating_plan function")

    plan_type = context.user_data.get("plan_type")
    """Создание меню или программы тренировок."""
    try:
        client_id = context.user_data.get("selected_client_id")
        client = await sync_to_async(Client.objects.get)(id=client_id)
        if not client_id:
            await update.message.reply_text(
                "Данные клиента не найдены. Попробуйте снова."
            )
            await update_chat_mapping(telegram_id, CHOOSING_ACTION, context.user_data)
            return CHOOSING_ACTION

        prompt = ""

        if plan_type == "menu":
            prompt = (
                f"Создайте персонализированное меню для клиента с такими данными:\n"
                f"Имя: {client.name}\n"
                f"Вес: {client.weight} кг\n"
                f"Цель: {client.goal}\n"
                f"Калории: {client.calories} ккал\n"
                f"Белки: {client.proteins} г\n"
                f"Жиры: {client.fats} г\n"
                f"Углеводы: {client.carbs} г\n"
                f"Включить в рацион: {client.yes_products}\n"
                f"Исключить из рациона: {client.no_products}\n"
                f"Аллергии: {client.allergies if client.allergies else 'Отсутствуют'}\n"
                "Предложите 3 варианта рациона на неделю, разделив его на завтрак, обед, полдник и ужин.\n"
                "Меню должно быть в формате маркеров (пункты меню), строго в соответствии с примером ниже, включая граммы для каждого продукта:\n"
                "Пример: \n"
                f"<b>Суточная норма калорий - {client.calories}</b>\n"
                "<b>Вариант 1:</b> - <b>Завтрак:</b> омлет с овощами (2 яйца), овсянка с ягодами (100 г)\n"
                "- <b>Обед:</b> куриная грудка (150 г) с рисом (100 г) и овощами (150 г)\n"
                "- <b>Полдник:</b> яблоко (1 шт.), миндаль (20 г)\n"
                "- <b>Ужин:</b> рыба на пару (150 г) с картофелем (200 г)\n"
                "- <b>Вариант 2:...</b>\n"
            )
            await update_chat_mapping(telegram_id, CHOOSING_ACTION, context.user_data)
        elif plan_type == "training":
            training_goal = context.user_data.get("training_goal")
            level = context.user_data.get("training_level")
            muscle_group = context.user_data.get("muscle_group")
            week = context.user_data.get("week")
            workout_type = context.user_data.get("workout_type")
            training_type = context.user_data.get("training_type")

            prompt = f"""
            Создай подробный план тренировок для клиента на неделю ({week} тренировок в неделю) с учетом следующих параметров:

            <b>Цель тренировки:</b> {training_goal}  
            <b>Тип тренировки (домашняя/в зале):</b> {training_type}  
            <b>Направление тренировок (фитнес, йога, пилатес, силовая и т. д.):</b> {workout_type}  
            <b>Уровень подготовки:</b> {level}  
            <b>Тренировка на все тело с акцентом на:</b> {muscle_group}    

            <b>Требования к структуре:</b>  
            1. <b>Разминка (5–10 минут)</b> – должна соответствовать направлению тренировки ({workout_type}). Например, для йоги — дыхательные практики и мобилизация, для силовых — суставная разминка и динамическая растяжка.  
            2. <b>Основная часть</b> – упражнения должны строго соответствовать {workout_type}. Укажи количество подходов и повторений, прогрессию нагрузки.  
            3. <b>Заключительная часть (заминка и растяжка, 5–10 минут)</b> – должна быть связана с типом тренировки. Например, для силовой — статическая растяжка, для пилатеса — расслабляющие упражнения.  

            <b>Формат ответа (пример):</b>  

            -------------------------  
            <b>День 1 – {workout_type} (Фокус на {muscle_group})</b>\n  
            <b>Разминка:</b> (указать упражнения, соответствующие направлению)\n 
            <b>Основная часть:</b> (указать упражнения, количество подходов, повторений, варианты усложнения)\n  
            <b>Заминка:</b> (указать упражнения на расслабление и восстановление)\n  
            -------------------------  
            <b>День 2 – …</b> (повторить структуру) и так далее {week} тренировок в неделю 

            Добавь рекомендации по технике выполнения и типичные ошибки, которые стоит избегать.  
            
            """
            await update_chat_mapping(telegram_id, CHOOSING_ACTION, context.user_data)

        logger.info(f"Prompt для {plan_type}: {prompt}")
        context.user_data["plan_type"] = plan_type
        context.user_data["prompt"] = prompt
        await update_chat_mapping(telegram_id, CHOOSING_ACTION, context.user_data)
        prompt = prompt
        return prompt

    except Exception as e:
        logger.error(f"Error in creating_plan: {e}")
        await update.callback_query.edit_message_text(
            "Произошла ошибка при создании плана. Попробуйте снова."
        )
        await update_chat_mapping(telegram_id, CHOOSING_ACTION, context.user_data)
        return CHOOSING_ACTION


async def menu_options(update: Update, context: CallbackContext):
    """Handle menu options after plan generation."""
    logger.info("Starting menu_options function")
    query = update.callback_query
    telegram_id = query.from_user.id
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return MAIN_MENU
    await query.answer()

    plan_type = context.user_data.get("plan_type")
    logger.info(f"Plan type from context: {plan_type}")

    user_choice = query.data
    logger.info(f"User choice from callback: {user_choice}")

    try:
        if user_choice == "main_menu":
            await update_chat_mapping(telegram_id, MAIN_MENU, context.user_data)
            return MAIN_MENU

        if user_choice == "edit_menu":
            logger.info("User chose to edit menu")
            await query.message.reply_text("Введите ваши пожелания по изменению плана:")
            await update_chat_mapping(telegram_id, EDIT_PLAN_COMMENT, context.user_data)
            return EDIT_PLAN_COMMENT

        elif user_choice == "download_pdf":
            try:
                print("download_pdf function has started")
                plan_type = context.user_data.get("plan_type")
                query = update.callback_query
                await query.answer()

                plan = context.user_data.get("response")
                client_id = context.user_data.get("selected_client_id")
                client = await sync_to_async(Client.objects.get)(id=client_id)

                print(f"Plan: {plan}")

                if not plan:
                    await query.message.reply_text("План не найден.")
                    await update_chat_mapping(
                        telegram_id, MENU_OPTIONS, context.user_data
                    )
                    return MENU_OPTIONS

                file_path = generate_plan_pdf(
                    plan_text=plan,
                    client_name=client.name,
                    filename=f"{plan_type}_{client.name}.pdf",
                )

                if file_path:
                    with open(file_path, "rb") as file:
                        await query.message.reply_document(
                            document=file, filename=file_path
                        )
                        await update_chat_mapping(
                            telegram_id, MAIN_MENU, context.user_data
                        )
                        return MAIN_MENU
                else:
                    await query.message.reply_text("Возникла ошибка при создании PDF.")
                    await update_chat_mapping(telegram_id, MAIN_MENU, context.user_data)
                    return MAIN_MENU

            except Exception as e:
                print(f"Error in download_plan_pdf: {str(e)}")
                await query.message.reply_text(
                    "Произошла ошибка при обработке запроса."
                )
                await update_chat_mapping(telegram_id, MAIN_MENU, context.user_data)
                return MAIN_MENU

        else:
            logger.warning(f"Unknown menu option: {user_choice}")
            await query.message.reply_text("Неизвестный выбор. Попробуйте снова.")
            await update_chat_mapping(telegram_id, MENU_OPTIONS, context.user_data)
            return MENU_OPTIONS

    except Exception as e:
        logger.error(f"Error in menu_options: {e}")
        await query.message.reply_text("Произошла ошибка. Попробуйте снова.")
        await update_chat_mapping(telegram_id, CHOOSING_ACTION, context.user_data)
        return CHOOSING_ACTION


async def edit_plan_comment(update: Update, context: CallbackContext):
    telegram_id = context.user_data.get("telegram_id")
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return MAIN_MENU
    plan_type = context.user_data.get("plan_type")
    if not plan_type:
        await update.message.reply_text("План для редактирования не найден.")
        # Send a new message for main menu instead of editing
        keyboard = [
            [InlineKeyboardButton("Создать меню для клиента", callback_data="1")],
            [
                InlineKeyboardButton(
                    "Создать тренировочную программу", callback_data="2"
                )
            ],
            [InlineKeyboardButton("Создать договор", callback_data="3")],
            [InlineKeyboardButton("Создать идеи для контента", callback_data="4")],
            [InlineKeyboardButton("Написать текст/сценарий", callback_data="5")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Что ты хочешь сделать?", reply_markup=reply_markup
        )
        await update_chat_mapping(telegram_id, MAIN_MENU, context.user_data)
        return MAIN_MENU

    user_comment = update.message.text
    if not user_comment:
        await update.message.reply_text(
            "Пожалуйста, введите текст с вашими пожеланиями."
        )
        await update_chat_mapping(telegram_id, MENU_OPTIONS, context.user_data)
        return MENU_OPTIONS

    plan = context.user_data.get("response")
    if not plan:
        await update.message.reply_text("План не найден. Попробуйте снова.")
        await update_chat_mapping(telegram_id, MENU_OPTIONS, context.user_data)
        return MENU_OPTIONS

    prompt = (
        f"Вот текущий план для клиента: '{plan}'. "
        f"На основе следующего комментария обнови план: '{user_comment}'."
    )
    context.user_data["prompt"] = prompt
    response = await generate_response(update, context)
    await update_chat_mapping(telegram_id, MENU_OPTIONS, context.user_data)

    await update.message.reply_text("Минутку, составляю план!🌀")
    if response:
        keyboard = [
            [InlineKeyboardButton("Редактировать", callback_data="edit_menu")],
            [InlineKeyboardButton("Скачать в PDF", callback_data="download_pdf")],
            [InlineKeyboardButton("Назад в меню", callback_data="main_menu")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            text=f"Вот ваш персонализированный план:\n\n{response}\n\n"
            "Что вы хотели бы сделать с планом?",
            reply_markup=reply_markup,
            parse_mode="HTML",
        )
        await update_chat_mapping(telegram_id, EDIT_PLAN_COMMENT, context.user_data)
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

        self.set_font("DejaVu", "B", 24)

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
        plans_folder = os.path.join(os.path.dirname(__file__), "plans")
        os.makedirs(plans_folder, exist_ok=True)

        file_path = os.path.join(plans_folder, filename)

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

        pdf.output(file_path)
        return file_path

    except Exception as e:
        print(f"Error generating PDF: {str(e)}")
        raise


async def download_plan_pdf(update: Update, context: CallbackContext):
    try:
        print("download_pdf function has started")
        query = update.callback_query
        telegram_id = context.user_data.get("telegram_id")
        mapping = await get_chat_mapping(telegram_id)
        if mapping and mapping.context:
            context.user_data.update(mapping.context)
            print(f"mapping found and restored: {mapping.state}")
        else:
            return MAIN_MENU
        await query.answer()
        plan_type = context.user_data.get("plan_type")

        plan = context.user_data.get(plan_type)
        client_id = context.user_data.get("selected_client_id")
        client = await sync_to_async(Client.objects.get)(id=client_id)

        print(f"Plan: {plan}")

        if not plan:
            await query.message.reply_text("План не найден.")
            await update_chat_mapping(telegram_id, MENU_OPTIONS, context.user_data)
            return MENU_OPTIONS

        file_path = generate_plan_pdf(
            plan_text=plan,
            client_name=client.name,
            filename=f"{plan_type}_{client.name}.pdf",
        )

        if file_path:
            with open(file_path, "rb") as file:
                await query.message.reply_document(document=file, filename=file_path)
            await update_chat_mapping(telegram_id, MAIN_MENU, context.user_data)
            return MAIN_MENU
        else:
            await query.message.reply_text("Возникла ошибка при создании PDF.")
            await update_chat_mapping(telegram_id, MAIN_MENU, context.user_data)
            return MAIN_MENU

    except Exception as e:
        print(f"Error in download_plan_pdf: {str(e)}")
        await query.message.reply_text("Произошла ошибка при обработке запроса.")
        return MAIN_MENU


############################## NUTRITION PLAN #####################################


############################## TRAINING PLAN ###################################


async def training_week(update: Update, context: CallbackContext):
    query = update.callback_query
    telegram_id = context.user_data.get("telegram_id")
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return MAIN_MENU
    await query.answer()

    if query.data == "main_menu":
        await update_chat_mapping(telegram_id, MAIN_MENU, context.user_data)
        return MAIN_MENU
    else:

        level = query.data
        context.user_data["level"] = level

        await query.edit_message_text(f"Сколько тренировок в неделю? (1-7 в числах):")
        await update_chat_mapping(telegram_id, CHOOSING_GOAL, context.user_data)
        return CHOOSING_GOAL


async def handle_training_goal(update: Update, context: CallbackContext):
    telegram_id = context.user_data.get("telegram_id")
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        await update_chat_mapping(telegram_id, MAIN_MENU, context.user_data)
        return MAIN_MENU
    try:
        week = int(update.message.text.strip())
        context.user_data["week"] = week
    except ValueError:
        await update.message.reply_text(
            "Пожалуйста, введите число для количества недель."
        )
        await update_chat_mapping(telegram_id, TRAINING_WEEK, context.user_data)
        return TRAINING_WEEK

    keyboard = [
        [InlineKeyboardButton("Набор массы", callback_data="набор массы")],
        [InlineKeyboardButton("Снижение веса", callback_data="снижение веса")],
        [InlineKeyboardButton("Укрепление мышц", callback_data="укрепление мышц")],
        [InlineKeyboardButton("Развитие гибкости", callback_data="развитие гибкости")],
        [InlineKeyboardButton("Реабилитация", callback_data="реабилитация")],
        [InlineKeyboardButton("Назад в меню", callback_data="main_menu")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"Какая основная цель в тренировках на этой неделе?",
        reply_markup=reply_markup,
    )
    await update_chat_mapping(telegram_id, CHOOSING_MUSCLE_GROUP, context.user_data)
    return CHOOSING_MUSCLE_GROUP


async def handle_muscle_group(update: Update, context: CallbackContext):
    query = update.callback_query
    telegram_id = context.user_data.get("telegram_id")
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return MAIN_MENU
    await query.answer()

    if query.data == "main_menu":
        await update_chat_mapping(telegram_id, MAIN_MENU, context.user_data)
        return MAIN_MENU

    else:

        goal = query.data
        context.user_data["training_goal"] = goal

        keyboard = [
            [InlineKeyboardButton("Грудные мышцы", callback_data="грудные мышцы")],
            [InlineKeyboardButton("Ноги", callback_data="ноги")],
            [InlineKeyboardButton("Спина", callback_data="спина")],
            [InlineKeyboardButton("Ягодицы", callback_data="ягодицы")],
            [InlineKeyboardButton("Пресс", callback_data="пресс")],
            [InlineKeyboardButton("Плечи", callback_data="плечи")],
            [InlineKeyboardButton("Все тело", callback_data="все тело")],
            [InlineKeyboardButton("Назад в меню", callback_data="main_menu")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "Теперь выберите группу мышц, на которую хотите сделать акцент на этой неделе:",
            reply_markup=reply_markup,
        )
        await update_chat_mapping(telegram_id, HANDLE_WORKOUT_TYPE, context.user_data)
        return HANDLE_WORKOUT_TYPE


async def workout_type(update: Update, context: CallbackContext):
    query = update.callback_query
    telegram_id = context.user_data.get("telegram_id")
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return MAIN_MENU
    await query.answer()

    if query.data == "main_menu":
        await update_chat_mapping(telegram_id, MAIN_MENU, context.user_data)
        return MAIN_MENU
    else:

        muscle_group = query.data
        context.user_data["muscle_group"] = muscle_group

        await query.edit_message_text(
            f"Какое направление тренировок (йога/фитнес/пилатес и тд)"
        )
        await update_chat_mapping(telegram_id, HANDLE_TRAINING_TYPE, context.user_data)
        return HANDLE_TRAINING_TYPE


async def handle_training_type(update: Update, context: CallbackContext):
    telegram_id = context.user_data.get("telegram_id")
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return MAIN_MENU

    workout_type = update.message.text.strip()
    context.user_data["workout_type"] = workout_type

    keyboard = [
        [InlineKeyboardButton("В зале", callback_data="в зале")],
        [
            InlineKeyboardButton(
                "Домашние без оборудования", callback_data="домашние без оборудования"
            )
        ],
        [
            InlineKeyboardButton(
                "Домашние с оборудованием",
                callback_data="домашние с оборудованием",
            )
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Выберите тип тренировок",
        reply_markup=reply_markup,
    )
    await update_chat_mapping(telegram_id, PLAN_HANDLER, context.user_data)
    return PLAN_HANDLER


############################## TRAINING PLAN ###################################


############################## POSITIONING ####################################
async def get_positioning(update: Update, context: CallbackContext):
    query = update.callback_query
    telegram_id = context.user_data.get("telegram_id")
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return MAIN_MENU
    await query.answer()

    user_choice = query.data
    if user_choice == "edit":
        await query.edit_message_text(
            "<b>Тренером в каком направлении ты являешься?</b>", parse_mode="HTML"
        )
        await update_chat_mapping(telegram_id, COACH_FIELD, context.user_data)
        return COACH_FIELD
    elif user_choice == "main_menu":
        await update_chat_mapping(telegram_id, MAIN_MENU, context.user_data)
        return MAIN_MENU


async def coach_field(update: Update, context: CallbackContext):
    telegram_id = context.user_data.get("telegram_id")
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return MAIN_MENU
    field = update.message.text.strip()
    telegram_id = context.user_data.get("telegram_id")
    coach = await sync_to_async(Coach.objects.get)(telegram_id=telegram_id)
    coach.field = field
    context.user_data["field"] = field
    await update.message.reply_text(
        "<b>Расскажите про ваш подход к тренировкам/питанию?</b>\n (Например: я придерживаюсь подхода, в котором без запретов и ограничений можно достичь правильных пищевых привычек через работу с психологией)",
        parse_mode="HTML",
    )
    await update_chat_mapping(telegram_id, APPROACH, context.user_data)
    return APPROACH


async def approach(update: Update, context: CallbackContext):
    telegram_id = context.user_data.get("telegram_id")
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return MAIN_MENU
    approach = update.message.text.strip()
    context.user_data["approach"] = approach
    await update.message.reply_text(
        "<b>С какими запросами обычно к вам приходят клиенты?</b>", parse_mode="HTML"
    )
    await update_chat_mapping(telegram_id, REQUEST, context.user_data)
    return REQUEST


async def request(update: Update, context: CallbackContext):
    telegram_id = context.user_data.get("telegram_id")
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return MAIN_MENU
    request = update.message.text.strip()
    context.user_data["request"] = request
    await update.message.reply_text(
        "<b>Опишите вашу целевую аудиторию.</b>\n Старайтесь не брать всех, выделите клиентов по возрасту, деятельности, запросам. Например, молодые мамы 25-35 лет, восстановление после беременности. Или женщины 35-40 лет с запросом на похудение и восстановлению энергии",
        parse_mode="HTML",
    )
    await update_chat_mapping(telegram_id, TARGET, context.user_data)
    return TARGET


async def target_audience(update: Update, context: CallbackContext):
    telegram_id = context.user_data.get("telegram_id")
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return MAIN_MENU
    target_audience = update.message.text.strip()
    context.user_data["target_audience"] = target_audience
    await update.message.reply_text(
        "<b>Какую основную услугу вы хотели бы предоставлять?</b>\n (например, тренировки по йоге в зале/онлайн-ведение клиентов",
        parse_mode="HTML",
    )
    await update_chat_mapping(telegram_id, PRODUCT, context.user_data)
    return PRODUCT


async def product(update: Update, context: CallbackContext):
    telegram_id = context.user_data.get("telegram_id")
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return MAIN_MENU
    product = update.message.text.strip()
    context.user_data["product"] = product
    await update.message.reply_text(
        "<b>Вы хотите привлечь клиентов на онлайн или оффлайн направление?</b>",
        parse_mode="HTML",
    )
    await update_chat_mapping(telegram_id, ONLINE, context.user_data)
    return ONLINE


async def online(update: Update, context: CallbackContext):
    telegram_id = context.user_data.get("telegram_id")
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return MAIN_MENU
    online = update.message.text.strip()
    context.user_data["online"] = online
    await update.message.reply_text(
        "<b>Какие темы вам интересны помимо вашего основного направления?</b>\n (например, готовка, чтение, кино)",
        parse_mode="HTML",
    )
    await update_chat_mapping(telegram_id, FIELDS, context.user_data)
    return FIELDS


async def fields(update: Update, context: CallbackContext):
    telegram_id = context.user_data.get("telegram_id")
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return MAIN_MENU
    fields = update.message.text.strip()
    context.user_data["fileds"] = fields
    await update.message.reply_text(
        "<b>Как вы думаете, что еще получают от вашей услуги клиенты, помимо основного результата?</b>\n Например, уверенность в себе, гармонию, энергию и тд",
        parse_mode="HTML",
    )
    await update_chat_mapping(telegram_id, EFFECT, context.user_data)
    return EFFECT


async def effect(update: Update, context: CallbackContext):
    telegram_id = context.user_data.get("telegram_id")
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return MAIN_MENU
    effect = update.message.text.strip()
    context.user_data["effect"] = effect
    field = context.user_data.get("field")
    approach = context.user_data.get("approach")
    request = context.user_data.get("request")
    target_audience = context.user_data.get("target_audience")
    product = context.user_data.get("product")
    fields = context.user_data.get("fields")
    effect = context.user_data.get("effect")
    online = context.user_data.get("online")
    prompt = f"""
    Составь маркетинговую стратегию для тренера, основанную на его специфике и целевой аудитории. Стратегия должна включать:  

    <b>1. Позиционирование и ключевая идея</b>  
    Определи главную концепцию и уникальное торговое предложение (УТП) тренера, основываясь на следующих данных:  
    - Направление тренера: {field}  
    - Подход тренера: {approach}  
    - ЦА: {target_audience}
    - Основной запрос клиентов: {request}  
    - Основной продукт/услуга: {product}  
    - Онлайн или оффлайн продукт? {online}  
    - Дополнительный эффект для клиентов: {effect}  

    Оформи позиционирование так, чтобы оно было четким, привлекало целевую аудиторию и вызывало доверие.  

    <b>2. Контент-стратегия</b>  
    Разработай основные рубрики и форматы контента, которые помогут тренеру привлекать и удерживать аудиторию. Учитывай:  
    - Какие темы важно раскрывать, чтобы сформировать экспертность?  
    - Какой контент лучше всего заходит для прогрева клиентов?  
    - Как можно органично интегрировать личный бренд?  

    Укажи примеры рубрик, тем для постов и Reels, а также идеи для вовлекающего контента (челленджи, квизы, мини-курсы).  

    <b>3. Воронка продаж и монетизация</b>  
    Предложи стратегию прогрева и продажи, включая:  
    - Как эффективно перевести аудиторию в клиентов?  
    - Какие бесплатные материалы или активности могут усилить доверие?  
    - Как структурировать продажу услуг, чтобы повысить конверсии?  

    <b>4. Каналы продвижения</b>  
    Дай рекомендации по площадкам (Instagram, Telegram, YouTube и др.), объясни, какой контент лучше всего подойдет для каждой платформы и как их комбинировать для максимального эффекта.  

    Учитывай, что помимо {field} тренеру также интересны {fields}, и это можно использовать в контенте.  
    """
    context.user_data["prompt"] = prompt
    await update_chat_mapping(telegram_id, POSITIONING, context.user_data)
    await update.message.reply_text("Опрашиваю маркетологов, одну минутку!🌀")
    response = await generate_response(update, context)
    telegram_id = context.user_data.get("telegram_id")
    coach = await sync_to_async(Coach.objects.get)(telegram_id=telegram_id)
    if response:
        coach.positioning = response
        await sync_to_async(coach.save)()
        context.user_data["response"] = response
        keyboard = [
            [InlineKeyboardButton("Редактировать", callback_data="edit_pos")],
            [InlineKeyboardButton("Сохранить", callback_data="save_pos")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"<b>Определил твое позиционирование, как тебе?</b>\n{response}\nЧто хочешь сделать?",
            reply_markup=reply_markup,
            parse_mode="HTML",
        )
        await update_chat_mapping(telegram_id, POSITIONING, context.user_data)
        return POSITIONING


async def positioning(update: Update, context: CallbackContext):
    query = update.callback_query
    telegram_id = context.user_data.get("telegram_id")
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return MAIN_MENU
    await query.answer()
    telegram_id = context.user_data.get("telegram_id")
    coach = await sync_to_async(Coach.objects.get)(telegram_id=telegram_id)
    response = context.user_data.get("response")

    pos_choice = query.data
    if pos_choice == "edit_pos":
        await update.effective_chat.send_message("Что вы хотели бы изменить/добавить?")
        await update_chat_mapping(telegram_id, EDIT_POS_HANDLER, context.user_data)

        return EDIT_POS_HANDLER

    elif pos_choice == "save_pos":
        coach.positioning = response
        keyboard = [
            [
                InlineKeyboardButton(
                    "Создать контент-план", callback_data="content_plan"
                )
            ],
            [
                InlineKeyboardButton(
                    "Вернуться в главное меню", callback_data="main_menu"
                )
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.effective_chat.send_message(
            "Что хотите сделать дальше?", reply_markup=reply_markup, parse_mode="HTML"
        )
        await update_chat_mapping(telegram_id, SAVE_POS_HANDLER, context.user_data)
        return SAVE_POS_HANDLER


async def edit_pos_handler(update: Update, context: CallbackContext):
    telegram_id = context.user_data.get("telegram_id")
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return MAIN_MENU
    comment = update.message.text.strip()
    coach = await sync_to_async(Coach.objects.get)(telegram_id=telegram_id)
    response = context.user_data.get("response")
    prompt = f"""
    Это позиционирование и стратегия, которые ты составил для тренера {coach} - {response}, измени его в соответсвие с этим комменатрием {comment}"
    """
    context.user_data["prompt"] = prompt
    response = await generate_response(update, context)
    if response:
        context.user_data["response"] = response
        keyboard = [
            [InlineKeyboardButton("Редактировать", callback_data="edit_pos")],
            [InlineKeyboardButton("Сохранить", callback_data="save_pos")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"Определил твое позиционирование, как тебе?\n{response}\nЧто хочешь сделать?",
            reply_markup=reply_markup,
            parse_mode="HTML",
        )
        await update_chat_mapping(telegram_id, POSITIONING, context.user_data)
        return POSITIONING


async def save_pos_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    telegram_id = context.user_data.get("telegram_id")
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return MAIN_MENU
    await query.answer()

    pos_choice = query.data
    if pos_choice == "main_menu":
        await update_chat_mapping(telegram_id, MAIN_MENU, context.user_data)
        return MAIN_MENU

    elif pos_choice == "content_plan":
        await query.edit_message_text("В какую соц сеть будем делать контент-план?")
        await update_chat_mapping(telegram_id, CONTENT_GOAL, context.user_data)
        return CONTENT_GOAL


############################## CONTENT CREATION ###################################


async def social_media(update: Update, context: CallbackContext):
    telegram_id = context.user_data.get("telegram_id")
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return MAIN_MENU
    field = update.message.text.strip()
    telegram_id = context.user_data.get("telegram_id")
    coach = await sync_to_async(Coach.objects.get)(telegram_id=telegram_id)
    coach.field = field
    context.user_data["field"] = field
    await update.message.reply_text("В какую соц.сеть будем делать контент-план?")
    await update_chat_mapping(telegram_id, CONTENT_GOAL, context.user_data)
    return CONTENT_GOAL


async def content_goal(update: Update, context: CallbackContext):
    telegram_id = context.user_data.get("telegram_id")
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return MAIN_MENU
    social_media = update.message.text.strip()
    context.user_data["social_media"] = social_media
    await update_chat_mapping(telegram_id, CONTENT_PROMPT, context.user_data)
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
        "Какая основная цель у твоего контента на ближайшие 2-3 недели?",
        reply_markup=reply_markup,
    )
    await update_chat_mapping(telegram_id, CONTENT_PROMPT, context.user_data)
    return CONTENT_PROMPT


async def content_prompt(update: Update, context: CallbackContext):
    query = update.callback_query
    telegram_id = context.user_data.get("telegram_id")
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return MAIN_MENU
    await query.answer()
    telegram_id = context.user_data.get("telegram_id")
    coach = await sync_to_async(Coach.objects.get)(telegram_id=telegram_id)
    content_goal = query.data
    field = coach.field
    positioning = coach.positioning
    social_media = context.user_data.get("social_media")
    context.user_data["content_goal"] = content_goal
    await query.edit_message_text("Минутку, опрашиваю аудиторию!🌀")

    if content_goal == "followers":
        prompt = (
            prompt
        ) = f"""
Ты экспертный маркетолог, специализирующийся на продвижении тренеров.  
Твоя задача – провести исследование целевой аудитории тренера в направлении "{field}" со следующи позиционированием: {positioning} и разработать контент-план для привлечения подписчиков в {social_media}.  

<b>1. Исследование целевой аудитории:</b>  
Опиши <b>ключевые боли</b> потенциальных клиентов. Какие проблемы мешают им достичь результатов? Что вызывает у них сомнения и трудности?  
Перечисли <b>желания и внутреннюю мотивацию</b> этой аудитории – чего они хотят достичь, какие изменения ожидают?  
Опиши <b>5 страхов</b>, которые могут их останавливать от покупки.   

<b>2. Разработка контент-плана:</b>  
Составь 10 вопросов, который интересуют ЦА тренера на основе проведенного исследования, и  составь по ним план на 10 дней для привлечения подписчиков в {social_media}.  

<b>Формат контент-плана (пример):</b>  
Описание болей, страхов и желаний клиентов: \n
Кто ваш потенциальный клиент? - Это человек...\n
📅 <b>День 1 </b>– ...\n
📅 <b>День 2 </b>– ...\n
📅 <b>День 3 </b>– ...\n
📅 <b>День 4 </b>– ...\n
📅 <b>День 5 </b>– ...\n

Продолжи этот формат, создавая уникальные темы на каждый день, учитывая боли, мечты и страхи аудитории.  
Включи в контент-план разные форматы ( видео, карусели, подскасты) для максимального вовлечения. Контент должен быть направлен на привлечение подписчиков и набор аудитории - акцент на пользу и экспертность

<b>Важно:</b>  
- Указывай конкретные темы постов, а не просто "контент про боли аудитории".  
- Подбирай темы, которые вызывают отклик и вовлекают подписчиков.  
- Если контент в инстаграм - бери только(!) рилс и посты-карусели, если телеграм - посты, кружочки и аудиоподкасты, если ютуб - шортс и видео и тд)
- Сделай план удобным для реализации, чтобы можно было сразу использовать его в работе.  
"""

        context.user_data["prompt"] = prompt
        await update_chat_mapping(telegram_id, CONTENT_PROMPT, context.user_data)
        response = await generate_response(update, context)
        if response:
            context.user_data["content"] = response
            await update_chat_mapping(telegram_id, CONTENT_PROMPT, context.user_data)
            keyboard = [
                [InlineKeyboardButton("Да", callback_data="yes")],
                [
                    InlineKeyboardButton(
                        "Нет, вернуться в главное меню", callback_data="main_menu"
                    )
                ],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"{response}. Хотите добавить что-то еще?",
                reply_markup=reply_markup,
                parse_mode="HTML",
            )
            await update_chat_mapping(
                telegram_id, CONTENT_PROMPT_HANDLER, context.user_data
            )
            return CONTENT_PROMPT_HANDLER

    elif content_goal == "sales":
        await query.edit_message_text("Расскажите подробно о своей услуге/продукте")
        await update_chat_mapping(telegram_id, CONTENT_SALES, context.user_data)
        return CONTENT_SALES


async def content_prompt_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    telegram_id = context.user_data.get("telegram_id")
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return MAIN_MENU
    await query.answer()

    if query.data == "main_menu":
        await update_chat_mapping(telegram_id, MAIN_MENU, context.user_data)
        return MAIN_MENU

    content_change = query.data
    if content_change == "yes":
        await query.message.reply_text("Что вы хотели бы добавить/изменить?")
        await update_chat_mapping(telegram_id, CONTENT_CHANGE, context.user_data)
        return CONTENT_CHANGE


async def content_change(update: Update, context: CallbackContext):
    telegram_id = context.user_data.get("telegram_id")
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return MAIN_MENU
    content_change = update.message.text.strip()
    content = context.user_data.get("content")

    prompt = f"Это сгенерированный контент план для тренера {content}, скорректируй его на основе этого комментария {content_change}"
    context.user_data["prompt"] = prompt
    await update_chat_mapping(telegram_id, CONTENT_CHANGE, context.user_data)
    response = await generate_response(update, context)
    if response:
        context.user_data["content"] = response
        await update_chat_mapping(telegram_id, CONTENT_CHANGE, context.user_data)
        keyboard = [
            [InlineKeyboardButton("Да", callback_data="yes")],
            [
                InlineKeyboardButton(
                    "Нет, вернуться в главное меню", callback_data="main_menu"
                )
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"{response}.\n<b>Хотите добавить что-то еще?</b>",
            reply_markup=reply_markup,
            parse_mode="HTML",
        )
        await update_chat_mapping(
            telegram_id, CONTENT_PROMPT_HANDLER, context.user_data
        )
        return CONTENT_PROMPT_HANDLER


async def content_sales(update: Update, context: CallbackContext):
    telegram_id = context.user_data.get("telegram_id")
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return MAIN_MENU
    sale_product = update.message.text.strip()
    telegram_id = context.user_data.get("telegram_id")
    coach = await sync_to_async(Coach.objects.get)(telegram_id=telegram_id)
    field = coach.field
    positioning = coach.positioning
    social_media = context.user_data.get("social_media")
    await update.message.reply_text("Минутку, опрашиваю аудиторию!🌀")
    prompt = f"""
        Ты опытный маркетолог, специализирующийся на продвижении услуг тренеров.  
        Твоя задача – провести глубокое исследование целевой аудитории для продукта "{sale_product}" тренера по направлению {field} со следующим позиционированием: {positioning}.  

        <b>1. Исследование целевой аудитории:</b>  
        Опиши <b>ключевые боли</b> потенциальных клиентов, которые мешают им достичь результата и могут мотивировать их купить "{sale_product}".  
        Перечисли <b>Какие желания и внутрення мотивация</b> этой аудитории – чего они хотят достичь, к чему стремятся может стать основной причиной покупки.  
        Опиши <b>5 страхов</b>, которые могут их останавливать от покупки.  

        <b>2. Создание контент-плана:</b>  
        Составь 10 вопросов ЦА на основе проведенного исследования для социальной сети {social_media}, ориентируясь на продвижение "{sale_product}". На основе вопросов создай контент-план на 10 дней.
        Контент должен вызывать доверие, работать с возражениями, увеличивать интерес и стимулировать продажи. Иди по болям клиента.  

        <b>Формат ответа (пример):</b> 
        Описание болей, страхов и желаний клиентов: \n
        Кто ваш потенциальный клиент? - Это человек...\n
        📅 <b>День 1 </b>– ... \n
        📅 <b>День 2 </b>– ... \n
        📅 <b>День 3 </b>– ... \n
        📅 <b>День 4 </b>– ... \n
        📅 <b>День 5 </b>– ... \n

        Продолжи этот формат, создавая уникальные темы на каждый день на 10 дней, ориентируясь на боли и желания аудитории.  
        Контент должен быть разнообразным: вовлекающие посты, сторис-идеи, обучающие материалы, отзывы, личные истории.  

        <b>Важно:</b>  
        - Указывай конкретные темы для постов, а не просто "презентация продукта".  
        - Каждая тема должна работать с желаниями, страхами или возражениями аудитории.  
        - Предложи разные форматы контента (для инстаграма - только (!) рилс и посты-карусели, для телеграма - посты, кружочки и аудмоподкасты и тд).  

        Составь этот контент-план в понятном формате, чтобы его можно было сразу использовать в работе.  
        """
    context.user_data["prompt"] = prompt
    await update_chat_mapping(telegram_id, CONTENT_SALES, context.user_data)
    response = await generate_response(update, context)
    if response:
        context.user_data["content"] = response
        await update_chat_mapping(telegram_id, CONTENT_SALES, context.user_data)
        keyboard = [
            [InlineKeyboardButton("Да", callback_data="yes")],
            [
                InlineKeyboardButton(
                    "Нет, вернуться в главное меню", callback_data="main_menu"
                )
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"{response}.\n<b>Хотите добавить что-то еще?</b>",
            reply_markup=reply_markup,
            parse_mode="HTML",
        )
        await update_chat_mapping(
            telegram_id, CONTENT_PROMPT_HANDLER, context.user_data
        )
        return CONTENT_PROMPT_HANDLER


#################################################################################


async def text_generation(update: Update, context: CallbackContext):
    telegram_id = context.user_data.get("telegram_id")
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return MAIN_MENU
    text_idea = update.message.text.strip()
    coach = await sync_to_async(Coach.objects.get)(telegram_id=telegram_id)
    field = coach.field
    positioning = coach.positioning
    prompt = f"""
Ты — маркетолог, пишущий вовлекающие и продающие тексты для тренеров.

Создай подробный пост для Instagram/Telegram по теме: {text_idea}  
Специализация тренера: {field}  
Позиционирование и ЦА: {positioning}

Структура поста:

1. <b>Цепляющий заголовок</b> — без «всем привет», сразу в суть боли клиента.
2. <b>Описание проблемы</b>, с которой сталкивается клиент, с фокусом на его внутренние ощущения и переживания.
3. <b>Что будет, если проблему не решить</b> — возможные негативные сценарии, чтобы усилить мотивацию.
4. <b>Как решение изменит жизнь клиента</b> — результат в формате «после».
5. <b>Полезные советы</b>, которые клиент может применить прямо сейчас (2–3 штуки).
6. <b>Призыв к действию</b>: запишись ко мне на бесплатную консультацию, и мы подберем идеальное решение для тебя.

Требования:
- Без хештегов и смайликов.
- Пиши живым, современным языком, как будто ты обращаешься напрямую к читателю.
- Не используй формальности и клише.
- Текст должен быть цельным, глубоким и сразу готовым к публикации.
- Используй <b> вместо ***
"""
    context.user_data["prompt"] = prompt
    await update_chat_mapping(telegram_id, TEXT_GENERATION, context.user_data)
    await update.message.reply_text("Минутку! Опрашиваю тысячу копирайтеров!🌀")
    response = await generate_response(update, context)
    if response:
        context.user_data["text"] = response
        await update_chat_mapping(telegram_id, TEXT_GENERATION, context.user_data)
        keyboard = [
            [InlineKeyboardButton("Да", callback_data="yes")],
            [
                InlineKeyboardButton(
                    "Нет, вернуться в главное меню", callback_data="main_menu"
                )
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"Вот ваш текст: {response}.\n<b>Хотите добавить что-то еще?</b>",
            reply_markup=reply_markup,
            parse_mode="HTML",
        )
        await update_chat_mapping(telegram_id, TEXT_PROMPT_HANDLER, context.user_data)
        return TEXT_PROMPT_HANDLER
    else:
        await update.message.reply_text("Произошла ошибка, попробуйте снова")
        await update_chat_mapping(telegram_id, MAIN_MENU, context.user_data)
        return MAIN_MENU


async def text_prompt_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    telegram_id = context.user_data.get("telegram_id")
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return MAIN_MENU
    await query.answer()

    text_change = query.data
    if text_change == "yes":
        await query.edit_message_text("Что вы хотели бы добавить/изменить?")
        await update_chat_mapping(telegram_id, TEXT_CHANGE, context.user_data)
        return TEXT_CHANGE


async def text_change(update: Update, context: CallbackContext):
    telegram_id = context.user_data.get("telegram_id")
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return MAIN_MENU
    text_change = update.message.text.strip()
    text = context.user_data.get("text")
    prompt = f"Это сгенерированный текст пользователя {text}, измени его с учетом следубщих комментариев {text_change} и сделай снова три варианта меню"
    context.user_data["prompt"] = prompt
    await update_chat_mapping(telegram_id, TEXT_CHANGE, context.user_data)
    await update.message.reply_text("Минутку! Снова опрашиваю тысячу копирайтеров!🌀")
    response = await generate_response(update, context)
    if response:
        context.user_data["text"] = response
        await update_chat_mapping(telegram_id, TEXT_CHANGE, context.user_data)
        keyboard = [
            [InlineKeyboardButton("Да", callback_data="yes")],
            [
                InlineKeyboardButton(
                    "Нет, вернуться в главное меню", callback_data="main_menu"
                )
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"Вот ваш текст: {response}.\n<b>Хотите добавить что-то еще?</b>",
            reply_markup=reply_markup,
            parse_mode="HTML",
        )
        await update_chat_mapping(telegram_id, TEXT_PROMPT_HANDLER, context.user_data)
        return TEXT_PROMPT_HANDLER
    else:
        await update.message.reply_text("Произошла ошибка, попробуйте снова")
        await update_chat_mapping(telegram_id, MAIN_MENU, context.user_data)
        return MAIN_MENU


async def reels_generation(update: Update, context: CallbackContext):
    telegram_id = context.user_data.get("telegram_id")
    print(f"{telegram_id}")
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return MAIN_MENU
    text_idea = update.message.text.strip()
    coach = await sync_to_async(Coach.objects.get)(telegram_id=telegram_id)
    field = coach.field
    positioning = coach.positioning
    prompt = f"""
Ты — маркетолог, помогающий тренерам создавать продающий и вовлекающий контент.

Создай текст для Reels в Instagram для тренера по {field}.  
Его позиционирование и целевая аудитория: {positioning}.  
Тема Reels: {text_idea}.

Требования к тексту:
- Используй формат "говорящей головы".
- Начни с <b>цепляющего заголовка</b> — без «привет, друзья», сразу к сути.
- Покажи <b>проблему</b>, с которой сталкивается клиент.
- Дай <b>простое решение</b>, которое можно внедрить сразу.
- Сделай <b>призыв к действию</b>: подписаться на аккаунт или написать в директ.
- Пиши <b>живым, современным языком</b>, без штампов и формальных фраз.
- Используй <b> вместо ***
- Без хештегов и смайликов

Финальный текст должен быть структурирован и легко читаем.

"""

    context.user_data["prompt"] = prompt
    await update_chat_mapping(telegram_id, REELS_GENERATION, context.user_data)
    await update.message.reply_text("Минутку! Опрашиваю тысячу рилсмейкеров!🌀")
    response = await generate_response(update, context)
    if response:
        context.user_data["text"] = response
        await update_chat_mapping(telegram_id, REELS_GENERATION, context.user_data)
        keyboard = [
            [InlineKeyboardButton("Да", callback_data="yes")],
            [
                InlineKeyboardButton(
                    "Нет, вернуться в главное меню", callback_data="main_menu"
                )
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"Вот ваш текст для рилс:\n {response}.\n<b>Хотите добавить что-то еще?</b>",
            reply_markup=reply_markup,
            parse_mode="HTML",
        )
        await update_chat_mapping(telegram_id, REELS_PROMPT_HANDLER, context.user_data)
        return REELS_PROMPT_HANDLER
    else:
        await update.message.reply_text("Произошла ошибка, попробуйте снова")
        await update_chat_mapping(telegram_id, MAIN_MENU, context.user_data)
        return MAIN_MENU


async def reels_prompt_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    telegram_id = context.user_data.get("telegram_id")
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return MAIN_MENU
    await query.answer()

    text_change = query.data
    if text_change == "yes":
        await query.edit_message_text("Что вы хотели бы добавить/изменить?")
        await update_chat_mapping(telegram_id, REELS_CHANGE, context.user_data)
        return REELS_CHANGE


async def reels_change(update: Update, context: CallbackContext):
    telegram_id = context.user_data.get("telegram_id")
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return MAIN_MENU
    text_change = update.message.text.strip()
    text = context.user_data.get("text")
    prompt = f"Это сгенерированный текст пользователя {text}, измени его с учетом следубщих комментариев {text_change}"
    context.user_data["prompt"] = prompt
    await update_chat_mapping(telegram_id, REELS_CHANGE, context.user_data)
    await update.message.reply_text("Минутку! Снова опрашиваю тысячу рилсмейкеров!🌀")
    response = await generate_response(update, context)
    if response:
        context.user_data["text"] = response
        await update_chat_mapping(telegram_id, REELS_CHANGE, context.user_data)
        keyboard = [
            [InlineKeyboardButton("Да", callback_data="yes")],
            [
                InlineKeyboardButton(
                    "Нет, вернуться в главное меню", callback_data="main_menu"
                )
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"Вот ваш текст для рилс: {response}.\n<b>Хотите добавить что-то еще?</b>",
            reply_markup=reply_markup,
            parse_mode="HTML",
        )
        await update_chat_mapping(telegram_id, REELS_PROMPT_HANDLER, context.user_data)
        return REELS_PROMPT_HANDLER
    else:
        await update.message.reply_text("Произошла ошибка, попробуйте снова")
        await update_chat_mapping(telegram_id, MAIN_MENU, context.user_data)
        return MAIN_MENU


async def get_clients(update: Update, context: CallbackContext):
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        telegram_id = query.from_user.id
    else:
        telegram_id = update.message.from_user.id

    # Получаем информацию о чате (контексте)
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")

    # Получаем информацию о тренере
    coach = await sync_to_async(Coach.objects.get)(telegram_id=telegram_id)

    # Получаем подписку тренера
    try:
        subscription = await get_subscription(coach)
    except Subscription.DoesNotExist:
        subscription = None

    # Если подписка не существует
    if not subscription:
        keyboard = [
            [
                InlineKeyboardButton(
                    "Подписка на месяц - 3000р/месяц (30 eur)",
                    callback_data="month_3000",
                ),
            ],
            [
                InlineKeyboardButton(
                    "Подписка на 3 месяца - 2300р/месяц (23 eur)",
                    callback_data="3month_2300",
                ),
            ],
            [
                InlineKeyboardButton(
                    "Подписка на 6 месяцев - 1800р/месяц (18 eur)",
                    callback_data="6month_1800",
                ),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Упс, похоже, что подписка закончилась. Давай выберем подходящий тариф!",
            reply_markup=reply_markup,
        )
        await update_chat_mapping(telegram_id, SUBSCRIPTION, context.user_data)
        return SUBSCRIPTION

    # Если подписка существует, проверяем её срок
    expires_at = subscription.expires_at
    if expires_at and expires_at.date() <= (datetime.now().date() - timedelta(days=1)):
        subscription.status = "pending"
        await sync_to_async(subscription.save)()

    # Если подписка не активна или на отмене
    if subscription.status not in ["active", "pending_cancellation"]:
        keyboard = [
            [
                InlineKeyboardButton(
                    "Подписка на месяц - 3000р/месяц (30 eur)",
                    callback_data="month_3000",
                ),
            ],
            [
                InlineKeyboardButton(
                    "Подписка на 3 месяца - 2300р/месяц (23 eur)",
                    callback_data="3month_2300",
                ),
            ],
            [
                InlineKeyboardButton(
                    "Подписка на 6 месяцев - 1800р/месяц (18 eur)",
                    callback_data="6month_1800",
                ),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Упс, похоже, что у тебя еще нет подписки. Давай выберем подходящий тариф!",
            reply_markup=reply_markup,
        )
        await update_chat_mapping(telegram_id, SUBSCRIPTION, context.user_data)
        return SUBSCRIPTION
    else:
        # Подписка активна или на отмене — получаем список клиентов
        clients = await sync_to_async(
            lambda: list(Client.objects.filter(coach=coach))
        )()
        if clients:
            keyboard = [
                [
                    InlineKeyboardButton(
                        f"{client.name} {client.surname}",
                        callback_data=f"select_{client.id}",
                    ),
                ]
                for client in clients
            ]
            await update.message.reply_text(
                "Нашел следующих клиентов, чью анкету хотите посмотреть?",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            await update_chat_mapping(telegram_id, CLIENTS_HANDLER, context.user_data)
            return CLIENTS_HANDLER
        else:
            keyboard = [
                [InlineKeyboardButton("Да", callback_data="add_client")],
                [
                    InlineKeyboardButton(
                        "Нет, вернуться в главное меню", callback_data="main_menu"
                    )
                ],
            ]
            await update.message.reply_text(
                "Не нашел клиентов, привязанных к вам. Хотите добавить нового клиента?",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            await update_chat_mapping(telegram_id, CLIENT_CHOICE, context.user_data)
            return CLIENT_CHOICE


async def clients_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    telegram_id = context.user_data.get("telegram_id")
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return GET_CLIENTS
    await query.answer()
    coach = await sync_to_async(Coach.objects.get)(telegram_id=telegram_id)

    selected_client_id = query.data.split("_", 1)[1]
    logger.info(f"Пользователь выбрал клиента с ID: {selected_client_id}")

    client = await sync_to_async(Client.objects.get)(id=selected_client_id, coach=coach)

    if client:
        context.user_data["selected_client_id"] = client.id
        message = (
            f"<b>1. Имя:</b> {client.name}\n"
            f"<b>2. Фамилия:</b> {client.surname}\n"
            f"<b>3. Вес:</b> {client.weight}\n"
            f"<b>4. Уровень активности:</b>{client.activity_level}\n"
            f"<b>5. Цель:</b>{client.goal}\n"
            f"<b>6. Аллергии:</b>{client.allergies}\n"
            f'<b>7. "Да" продукты:</b>{client.yes_products}\n'
            f'<b>8. "Нет" продукты:</b>{client.no_products}\n'
        )
        keyboard = [
            [InlineKeyboardButton("Редактировать", callback_data="edit_client")],
            [InlineKeyboardButton("Удалить клиента", callback_data="delete")],
            [
                InlineKeyboardButton(
                    "Вернуться в главное меню", callback_data="main_menu"
                )
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"Что хотели бы сделать с анкетой?\n {message}",
            reply_markup=reply_markup,
            parse_mode="HTML",
        )
        await update_chat_mapping(telegram_id, EDIT_CLIENT, context.user_data)
        return EDIT_CLIENT


async def edit_client(update: Update, context: CallbackContext):
    query = update.callback_query
    telegram_id = context.user_data.get("telegram_id")
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return GET_CLIENTS
    await query.answer()
    client_id = context.user_data.get("selected_client_id")

    edit_client_choice = query.data
    if edit_client_choice == "edit_client":
        keyboard = [
            [InlineKeyboardButton("Имя", callback_data="name")],
            [InlineKeyboardButton("Фамилия", callback_data="surname")],
            [InlineKeyboardButton("Вес", callback_data="weight")],
            [InlineKeyboardButton("Уровень активности", callback_data="activity")],
            [InlineKeyboardButton("Цель", callback_data="goal")],
            [InlineKeyboardButton("Аллергии", callback_data="allergies")],
            [InlineKeyboardButton("ДА-продукты", callback_data="yes-prod")],
            [InlineKeyboardButton("НЕТ-продукты", callback_data="no-prod")],
            [
                InlineKeyboardButton(
                    "Вернуться к списку клиентов", callback_data="get_clients"
                )
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.effective_chat.send_message(
            "Какой пункт вы хотели бы изменить?",
            reply_markup=reply_markup,
            parse_mode="HTML",
        )
        await update_chat_mapping(
            telegram_id, EDIT_CLIENT_DATA_HANDLER, context.user_data
        )
        return EDIT_CLIENT_DATA_HANDLER

    elif edit_client_choice == "delete":
        client = await sync_to_async(Client.objects.get)(id=client_id)
        await sync_to_async(client.delete)()
        keyboard = [
            [
                InlineKeyboardButton(
                    "Вернуться к списку клиентов", callback_data="get_clients"
                )
            ],
            [
                InlineKeyboardButton(
                    "Вернуться в главное меню", callback_data="main_menu"
                )
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "Клиент удален. Что дальше?", reply_markup=reply_markup
        )
        await update_chat_mapping(telegram_id, MAIN_MENU, context.user_data)

        return MAIN_MENU
    elif edit_client_choice == "main_menu":
        await update_chat_mapping(telegram_id, MAIN_MENU, context.user_data)
        return MAIN_MENU


async def edit_client_data_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    telegram_id = context.user_data.get("telegram_id")
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return GET_CLIENTS
    await query.answer()
    client_choice = query.data
    context.user_data["client_data_choice"] = query.data
    if client_choice == "name":
        await query.edit_message_text("Введите имя", reply_markup=reply_markup)
        await update_chat_mapping(telegram_id, CLIENT_DATA_MSG, context.user_data)
        return CLIENT_DATA_MSG
    elif client_choice == "surname":
        await query.edit_message_text("Введите фамилию")
        await update_chat_mapping(telegram_id, CLIENT_DATA_MSG, context.user_data)
        return CLIENT_DATA_MSG
    elif client_choice == "weight":
        await query.edit_message_text("Введите вес клиента")
        await update_chat_mapping(telegram_id, CLIENT_DATA_MSG, context.user_data)
        return CLIENT_DATA_MSG
    elif client_choice == "activity":
        keyboard = [
            [InlineKeyboardButton("Низкий", callback_data="1.2")],
            [InlineKeyboardButton("Средний", callback_data="1.3")],
            [InlineKeyboardButton("Высокий", callback_data="1.4")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "Ввыберите уровень активности", reply_markup=reply_markup
        )
        await update_chat_mapping(telegram_id, CLIENT_DATA_QUERY, context.user_data)
        return CLIENT_DATA_QUERY
    elif client_choice == "goal":
        keyboard = [
            [InlineKeyboardButton("Похудение", callback_data="похудение")],
            [InlineKeyboardButton("Набор массы", callback_data="набор массы")],
            [InlineKeyboardButton("Тонус", callback_data="тонус")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update_chat_mapping(telegram_id, CLIENT_DATA_QUERY, context.user_data)
        return CLIENT_DATA_QUERY
    elif client_choice == "allergies":
        await query.edit_message_text("На что у клиента аллергии?")
        await update_chat_mapping(telegram_id, CLIENT_DATA_MSG, context.user_data)
        return CLIENT_DATA_MSG
    elif client_choice == "yes-prod":
        await query.edit_message_text(
            "Какие продукты обязательно должны присутствовать?"
        )
        await update_chat_mapping(telegram_id, CLIENT_DATA_MSG, context.user_data)
        return CLIENT_DATA_MSG
    elif client_choice == "no-prod":
        await query.edit_message_text("Какие продукты не должны присутствовать?")
        await update_chat_mapping(telegram_id, CLIENT_DATA_MSG, context.user_data)
        return CLIENT_DATA_MSG


async def client_data_msg(update: Update, context: CallbackContext):
    telegram_id = context.user_data.get("telegram_id")
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return GET_CLIENTS

    client_choice = context.user_data.get("client_data_choice")
    client_id = context.user_data.get("selected_client_id")
    client = await sync_to_async(Client.objects.get)(id=client_id)

    client_data = update.message.text.strip()

    if client_choice == "name":
        client.name = client_data
    elif client_choice == "surname":
        client.surname = client_data
    elif client_choice == "weight":
        client.weight = client_data
    elif client_choice == "allergies":
        client.allergies = client_data
    elif client_choice == "yes-prod":
        client.yes_products = client_data
    elif client_choice == "no-prod":
        client.no_products = client_data
    await sync_to_async(client.save)()
    message = (
        f"<b>1. Имя:</b> {client.name}\n"
        f"<b>2. Фамилия:</b> {client.surname}\n"
        f"<b>3. Вес:</b> {client.weight}\n"
        f"<b>4. Уровень активности:</b>{client.activity_level}\n"
        f"<b>5. Цель:</b>{client.goal}\n"
        f"<b>6. Аллергии:</b>{client.allergies}\n"
        f'<b>7. "Да" продукты:</b>{client.yes_products}\n'
        f'<b>8. "Нет" продукты:</b>{client.no_products}\n'
    )
    keyboard = [
        [InlineKeyboardButton("Редактировать", callback_data="edit_client")],
        [InlineKeyboardButton("Удалить клиента", callback_data="delete")],
        [InlineKeyboardButton("Вернуться в главное меню", callback_data="main_menu")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"Что хотели бы сделать с анкетой?\n {message}",
        reply_markup=reply_markup,
        parse_mode="HTML",
    )
    await update_chat_mapping(telegram_id, EDIT_CLIENT, context.user_data)
    return EDIT_CLIENT


async def client_data_query(update: Update, context: CallbackContext):
    query = update.callback_query
    telegram_id = context.user_data.get("telegram_id")
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    else:
        return GET_CLIENTS
    await query.answer()
    client_choice = context.user_data.get("client_data_choice")
    client_id = context.user_data.get("selected_client_id")
    client = await sync_to_async(Client.objects.get)(id=client_id)

    client_data = query.data

    if client_choice == "activity":
        client.activity_level = client_data
    elif client_choice == "goal":
        client.goal = client_data
    await sync_to_async(client.save)()
    message = (
        f"<b>1. Имя:</b> {client.name}\n"
        f"<b>2. Фамилия:</b> {client.surname}\n"
        f"<b>3. Вес:</b> {client.weight}\n"
        f"<b>4. Уровень активности:</b>{client.activity_level}\n"
        f"<b>5. Цель:</b>{client.goal}\n"
        f"<b>6. Аллергии:</b>{client.allergies}\n"
        f'<b>7. "Да" продукты:</b>{client.yes_products}\n'
        f'<b>8. "Нет" продукты:</b>{client.no_products}\n'
    )
    keyboard = [
        [InlineKeyboardButton("Редактировать", callback_data="edit_client")],
        [InlineKeyboardButton("Удалить клиента", callback_data="delete")],
        [InlineKeyboardButton("Вернуться в главное меню", callback_data="main_menu")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        f"Что хотели бы сделать с анкетой? {message}",
        reply_markup=reply_markup,
        parse_mode="HTML",
    )
    await update_chat_mapping(telegram_id, EDIT_CLIENT, context.user_data)
    return EDIT_CLIENT


async def education(update: Update, context: CallbackContext):
    telegram_id = update.message.from_user.id
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    context.user_data["telegram_id"] = telegram_id
    keyboard = [
        [InlineKeyboardButton("Вернуться в главное меню", callback_data="main_menu")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Ты можешь прийти на наш <a href='https://t.me/free_coach_course_bot'>бесплатный курс</a>. А еще нас есть полноценное обучение для тренеров, которые хотят работать онлайн. Унать подробности можно по <a href='https://www.basetraining.site/academy'>этой ссылке</a>",
        reply_markup=reply_markup,
        parse_mode="HTML",
    )
    await update_chat_mapping(telegram_id, MAIN_MENU, context.user_data)
    return MAIN_MENU


async def get_support(update: Update, context: CallbackContext):
    telegram_id = update.message.from_user.id
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    context.user_data["telegram_id"] = telegram_id
    keyboard = [
        [InlineKeyboardButton("Вернуться в главное меню", callback_data="main_menu")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Напишите нам в чат @basetraining_academy",
        reply_markup=reply_markup,
    )
    await update_chat_mapping(telegram_id, MAIN_MENU, context.user_data)
    return MAIN_MENU


async def knowledge_base(update: Update, context: CallbackContext):
    telegram_id = update.message.from_user.id
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    context.user_data["telegram_id"] = telegram_id
    keyboard = [
        [InlineKeyboardButton("Вернуться в главное меню", callback_data="main_menu")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Базу знаний для тренеров по ведению клиентов, продвижению и продажам вы найдете <a href='https://teletype.in/@basetraining/jEd0bRFSvCV'>ЗДЕСЬ</a>. Подписывайтесь на наш <a href='https://t.me/basetraining'>телеграм-канал</a>, там тоже много полезных материалов",
        reply_markup=reply_markup,
        parse_mode="HTML",
    )
    await update_chat_mapping(telegram_id, MAIN_MENU, context.user_data)
    return MAIN_MENU


def error(update, context):
    print(f"Error: {context.error}")
    update.message.reply_text("Произошла ошибка, попробуйте снова позже.")


async def error_handler(update: Update, context: CallbackContext):
    logger.error(f"Update {update} caused error {context.error}")

    # Get the user's telegram_id
    telegram_id = None
    if update.effective_user:
        telegram_id = update.effective_user.id

    if telegram_id:
        # Reset the conversation state
        await reset_conversation_state(telegram_id)

        # Send an error message to the user
        text = "Извините, произошла ошибка. Пожалуйста, начните заново с команды /menu"

        if update.callback_query:
            await update.callback_query.message.reply_text(text)
        elif update.message:
            await update.message.reply_text(text)


def main():
    persistence = PicklePersistence(filepath="conversation_states.pickle")
    application = (
        Application.builder().token(BOT_TOKEN).persistence(persistence).build()
    )

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("menu", main_menu),
            CommandHandler("clients", get_clients),
            CommandHandler("support", get_support),
            CommandHandler("base", knowledge_base),
            CommandHandler("edu", education),
            CommandHandler("new", new_client),
            CommandHandler("sub", cancel_subscription),
            MessageHandler(filters.TEXT & ~filters.COMMAND, entry_point),
        ],
        states={
            SUBSCRIPTION: [CallbackQueryHandler(subscription)],
            SUB_HANDLER: [CallbackQueryHandler(sub_handler)],
            MAIN_MENU: [
                CallbackQueryHandler(main_menu, pattern="^main_menu$"),
                CallbackQueryHandler(choosing_action, pattern="^[12345]$"),
            ],
            CHOOSING_ACTION: [
                CallbackQueryHandler(choosing_action, pattern="^[123456]$"),
                CallbackQueryHandler(main_menu, pattern="^main_menu$"),
            ],
            CLIENT_CHOICE: [
                CallbackQueryHandler(
                    client_choice, pattern="^(choose_client|add_client)$"
                ),
                CallbackQueryHandler(main_menu, pattern="^main_menu$"),
            ],
            NEW_CLIENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, new_client)],
            CLIENT_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, client_name),
                CallbackQueryHandler(main_menu, pattern="^main_menu$"),
            ],
            NEW_CLIENT_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, new_client_name),
                CallbackQueryHandler(main_menu, pattern="^main_menu$"),
            ],
            CLIENT_SELECTION: [
                CallbackQueryHandler(client_selection, pattern="^select_\\d+$"),
                CallbackQueryHandler(main_menu, pattern="^main_menu$"),
            ],
            CLIENT_SURNAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, client_surname)
            ],
            CLIENT_WEIGHT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, client_weight)
            ],
            CLIENT_ACTION: [
                CallbackQueryHandler(client_action),
                CallbackQueryHandler(main_menu, pattern="^main_menu$"),
            ],
            CLIENT_ACTIVITY_LEVEL_CHOICE: [
                CallbackQueryHandler(client_activity_level_choice),
                CallbackQueryHandler(main_menu, pattern="^main_menu$"),
            ],
            CLIENT_GOAL: [
                CallbackQueryHandler(client_goal),
                CallbackQueryHandler(main_menu, pattern="^main_menu$"),
            ],
            CLIENT_ALLERGIES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, client_allergies)
            ],
            CLIENT_YES_PRODUCTS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, client_yes_products)
            ],
            CLIENT_NO_PRODUCTS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, client_no_products)
            ],
            CLIENT_CALORIES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, client_calories)
            ],
            GENERATE_RESPONSE: [
                CallbackQueryHandler(generate_response),
                CallbackQueryHandler(main_menu, pattern="^main_menu$"),
            ],
            CREATING_PLAN: [
                CallbackQueryHandler(creating_plan),
                CallbackQueryHandler(main_menu, pattern="^main_menu$"),
            ],
            MENU_OPTIONS: [
                CallbackQueryHandler(menu_options),
            ],
            EDIT_PLAN_COMMENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_plan_comment)
            ],
            CHOOSING_GOAL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_training_goal)
            ],
            CHOOSING_MUSCLE_GROUP: [
                CallbackQueryHandler(handle_muscle_group),
                CallbackQueryHandler(main_menu, pattern="^main_menu$"),
            ],
            TRAINING_WEEK: [
                CallbackQueryHandler(training_week),
                CallbackQueryHandler(main_menu, pattern="^main_menu$"),
            ],
            PLAN_HANDLER: [
                CallbackQueryHandler(plan_handler),
                CallbackQueryHandler(main_menu, pattern="^main_menu$"),
            ],
            DOWNLOAD_PDF: [
                CallbackQueryHandler(download_plan_pdf),
                CallbackQueryHandler(main_menu, pattern="^main_menu$"),
            ],
            GET_POS: [
                CallbackQueryHandler(get_positioning),
                CallbackQueryHandler(main_menu, pattern="^main_menu$"),
            ],
            COACH_FIELD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, coach_field),
                CallbackQueryHandler(main_menu, pattern="^main_menu$"),
            ],
            APPROACH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, approach),
                CallbackQueryHandler(main_menu, pattern="^main_menu$"),
            ],
            REQUEST: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, request),
                CallbackQueryHandler(main_menu, pattern="^main_menu$"),
            ],
            TARGET: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, target_audience),
                CallbackQueryHandler(main_menu, pattern="^main_menu$"),
            ],
            PRODUCT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, product),
                CallbackQueryHandler(main_menu, pattern="^main_menu$"),
            ],
            ONLINE: [MessageHandler(filters.TEXT & ~filters.COMMAND, online)],
            EFFECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, effect)],
            FIELDS: [MessageHandler(filters.TEXT & ~filters.COMMAND, fields)],
            POSITIONING: [
                CallbackQueryHandler(positioning),
                CallbackQueryHandler(main_menu, pattern="^main_menu$"),
            ],
            EDIT_POS_HANDLER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_pos_handler)
            ],
            SAVE_POS_HANDLER: [
                CallbackQueryHandler(save_pos_handler),
                CallbackQueryHandler(main_menu, pattern="^main_menu$"),
            ],
            SOCIAL_MEDIA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, social_media),
                CallbackQueryHandler(main_menu, pattern="^main_menu$"),
            ],
            CONTENT_GOAL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, content_goal),
                CallbackQueryHandler(main_menu, pattern="^main_menu$"),
            ],
            CONTENT_PROMPT: [
                CallbackQueryHandler(content_prompt),
                CallbackQueryHandler(main_menu, pattern="^main_menu$"),
            ],
            CONTENT_PROMPT_HANDLER: [
                CallbackQueryHandler(content_prompt_handler),
                CallbackQueryHandler(main_menu, pattern="^main_menu$"),
            ],
            CONTENT_SALES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, content_sales),
                CallbackQueryHandler(main_menu, pattern="^main_menu$"),
            ],
            CONTENT_CHANGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, content_change),
                CallbackQueryHandler(main_menu, pattern="^main_menu$"),
            ],
            TEXT_PROMPT_HANDLER: [
                CallbackQueryHandler(text_prompt_handler),
                CallbackQueryHandler(main_menu, pattern="^main_menu$"),
            ],
            TEXT_CHANGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, text_change),
                CallbackQueryHandler(main_menu, pattern="^main_menu$"),
            ],
            TEXT_GENERATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, text_generation),
                CallbackQueryHandler(main_menu, pattern="^main_menu$"),
            ],
            HANDLE_TRAINING_TYPE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_training_type),
                CallbackQueryHandler(main_menu, pattern="^main_menu$"),
            ],
            HANDLE_WORKOUT_TYPE: [CallbackQueryHandler(workout_type)],
            GET_CLIENTS: [CallbackQueryHandler(get_clients, pattern="^get_clients$")],
            EDIT_CLIENT: [
                CallbackQueryHandler(edit_client),
                CallbackQueryHandler(main_menu, pattern="^main_menu$"),
                CallbackQueryHandler(get_clients, pattern="^get_clients$"),
            ],
            EDIT_CLIENT_DATA_HANDLER: [
                CallbackQueryHandler(edit_client_data_handler),
                CallbackQueryHandler(main_menu, pattern="^main_menu$"),
                CallbackQueryHandler(get_clients, pattern="^get_clients$"),
            ],
            CLIENTS_HANDLER: [
                CallbackQueryHandler(clients_handler),
                CallbackQueryHandler(main_menu, pattern="^main_menu$"),
            ],
            CLIENT_DATA_MSG: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, client_data_msg),
            ],
            CLIENT_DATA_QUERY: [
                CallbackQueryHandler(client_data_query),
                CallbackQueryHandler(main_menu, pattern="^main_menu$"),
            ],
            CUSTOMER_EMAIL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, customer_email),
            ],
            CANCEL_SUB_HANDLER: [
                CallbackQueryHandler(cancel_subscription_handler),
                CallbackQueryHandler(main_menu, pattern="^main_menu$"),
            ],
            REELS_PROMPT_HANDLER: [
                CallbackQueryHandler(reels_prompt_handler),
                CallbackQueryHandler(main_menu, pattern="^main_menu$"),
            ],
            REELS_CHANGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, reels_change),
                CallbackQueryHandler(main_menu, pattern="^main_menu$"),
            ],
            REELS_GENERATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, reels_generation),
                CallbackQueryHandler(main_menu, pattern="^main_menu$"),
            ],
        },
        fallbacks=[
            CommandHandler("start", start),
            CommandHandler("menu", main_menu),
            CommandHandler("clients", get_clients),
            CommandHandler("support", get_support),
            CommandHandler("base", knowledge_base),
            CommandHandler("edu", education),
            CommandHandler("new", new_client),
            CommandHandler("sub", cancel_subscription),
            # Add more fallback commands if needed
        ],
        name="main_conversation",
        persistent=True,
    )

    application.add_handler(conv_handler)
    application.add_error_handler(error_handler)
    application.run_polling()
    application.add_handler(CommandHandler("clients", get_clients))
    application.add_handler(CommandHandler("support", get_support))
    application.add_handler(CommandHandler("base", knowledge_base))
    application.add_handler(CommandHandler("edu", education))
    application.add_handler(CommandHandler("new", new_client))
    application.add_handler(CommandHandler("sub", cancel_subscription))


if __name__ == "__main__":
    main()
