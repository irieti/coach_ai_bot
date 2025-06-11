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
from telegram.ext import Application, BasePersistence, JobQueue
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
from openai import OpenAI
import concurrent.futures
from functools import partial
from openai import AsyncOpenAI

load_dotenv()

API_SEMAPHORE = asyncio.Semaphore(5)

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

# TINKOFF_PASSWORD = os.getenv("TINKOFF_PASSWORD")
# TINKOFF_TERMINAL_KEY = "1743522430515DEMO"

stripe.api_key = os.getenv("STRIPE_API_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
LAVA_API_KEY = os.getenv("LAVA_API_KEY")

thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=10)

DB_POOL_SEMAPHORE = asyncio.Semaphore(10)

API_SEMAPHORE = asyncio.Semaphore(5)  # Allow up to 5 concurrent API calls

today = now()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
job_queue = JobQueue()


async def handle_ai_response(
    update: Update, context: CallbackContext, waiting_message, content_type
):
    response = await generate_response(update, context)
    context.user_data["response"] = response
    telegram_id = context.user_data.get("telegram_id")
    coach = await sync_to_async(Coach.objects.get)(telegram_id=telegram_id)
    if content_type == "positioning":
        coach.positioning = response
        await sync_to_async(coach.save)()

    try:
        await waiting_message.delete()
    except Exception as e:
        logger.error(f"Error deleting waiting message: {e}")

    if not response:
        # Определяем, откуда пришёл запрос — кнопка или текст
        if update.callback_query:
            await update.callback_query.message.reply_text(
                "Не удалось сгенерировать план."
            )
        elif update.message:
            await update.message.reply_text("Не удалось сгенерировать план.")
        return

    # Тоже — разделяем кнопку и текст
    if update.callback_query:
        await update.callback_query.message.reply_text(
            text=f"Готово:\n\n{response}\n\n",
            parse_mode="HTML",
        )
    elif update.message:
        await update.message.reply_text(
            text=f"Готово:\n\n{response}\n\n",
            parse_mode="HTML",
        )

    return MAIN_MENU


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


async def initiate_payment_async(amount, telegram_id, email, price_id, period):
    """Async wrapper for the synchronous payment function"""
    return await sync_to_async(initiate_payment)(
        amount, telegram_id, email, price_id, period
    )


def initiate_payment(amount, telegram_id, email, price_id, period):
    """
    Initialize a payment with Lava.top payment system
    """
    # Map subscription choice to correct period
    periodicity = period

    # Get offer_id based on subscription choice
    offer_id = price_id

    # Prepare request data
    request_data = {
        "email": email,
        "offerId": offer_id,
        "periodicity": periodicity,
        "currency": "RUB",
        "paymentMethod": "BANK131",  # Default payment method
        "buyerLanguage": "RU",
        "clientUtm": {"telegram_id": str(telegram_id)},
    }

    # Send request to Lava API
    headers = {
        "accept": "application/json",
        "X-Api-Key": LAVA_API_KEY,
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            "https://gate.lava.top/api/v2/invoice", headers=headers, json=request_data
        )

        logger.info(f"Lava payment init response: {response.status_code}")

        if response.status_code == 201:
            response_data = response.json()
            logger.info(f"Lava payment response data: {response_data}")

            if "paymentUrl" in response_data:
                # Save initial subscription info
                subscription, created = Subscription.objects.update_or_create(
                    customer_key=str(telegram_id),
                    defaults={
                        "status": "pending",
                        "amount": amount,
                        "payment_method": "lava",
                        "email": email,
                    },
                )

                # Save contract ID if available
                if "contractId" in response_data:
                    subscription.payment_id = response_data["contractId"]
                    subscription.save()

                return response_data["paymentUrl"]

        logger.error(f"Lava payment error: {response.text}")
        return None

    except Exception as e:
        logger.error(f"Error initializing Lava payment: {e}")
        return None


@csrf_exempt
def lava_webhook(request):
    """
    Handle webhook notifications from Lava.top payment system
    """
    logger.info("Lava webhook received")

    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body)
        logger.info(f"Webhook data received: {data}")

        # Extract data from webhook
        event_type = data.get("eventType")
        status = data.get("status")
        contract_id = data.get("contractId")
        parent_contract_id = data.get("parentContractId")
        email = data.get("buyer", {}).get("email")

        # Extract telegram_id from clientUtm if available
        webhook_telegram_id = None
        if "clientUtm" in data and "telegram_id" in data["clientUtm"]:
            webhook_telegram_id = data["clientUtm"]["telegram_id"]

        print(f"webhook_telegram_id: {webhook_telegram_id}")

        logger.info(
            f"Event type: {event_type}, Status: {status}, Contract ID: {contract_id}"
        )

        if not webhook_telegram_id and not email:
            logger.error("Missing customer identification")
            return JsonResponse(
                {"error": "Missing customer identification"}, status=400
            )

        # First try to find subscription by telegram_id from webhook
        subscription = None
        if webhook_telegram_id:
            subscription = Subscription.objects.filter(
                customer_key=webhook_telegram_id
            ).first()

        # If not found, try by email
        if not subscription and email:
            subscription = Subscription.objects.filter(email=email).first()

        if not subscription:
            logger.error(
                f"Subscription not found for customer: {webhook_telegram_id or email}"
            )
            return JsonResponse({"error": "Subscription not found"}, status=404)

        # Get the telegram_id from the subscription object if we didn't have it from webhook
        telegram_id = webhook_telegram_id
        if not telegram_id:
            # If we found the subscription by email, get the coach's telegram_id
            if hasattr(subscription, "coach") and subscription.coach:
                telegram_id = subscription.coach.telegram_id
                print(f"Found telegram_id {telegram_id} from subscription's coach")

        # Process subscription based on webhook event type
        with transaction.atomic():
            # Save contract IDs
            if contract_id:
                subscription.payment_id = contract_id

            if parent_contract_id:
                subscription.rebill_id = parent_contract_id

            # Process first payment success
            if event_type == "payment.success" and status == "subscription-active":
                handle_payment_success(subscription)

                # Send Telegram notification if we have telegram_id
                if telegram_id:
                    send_telegram_message(
                        telegram_id,
                        "Оплата прошла успешно! Ваша подписка активирована, перейдите в главное меню слева внизу",
                    )

            # Process recurring payment success
            elif (
                event_type == "subscription.recurring.payment.success"
                and status == "subscription-active"
            ):
                handle_payment_success(subscription)

                if telegram_id:
                    send_telegram_message(
                        telegram_id, "Ваша подписка успешно продлена!"
                    )

            # Process payment failures
            elif event_type in [
                "payment.failed",
                "subscription.recurring.payment.failed",
            ]:
                subscription.status = "pending"
                subscription.save()

                if telegram_id:
                    send_telegram_message(
                        telegram_id,
                        "Платеж не прошел. Пожалуйста, проверьте данные карты.",
                    )

        return HttpResponse("OK", status=200)

    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return JsonResponse({"error": f"Internal server error: {str(e)}"}, status=500)


def handle_payment_success(subscription):
    """
    Update subscription on successful payment
    """
    subscription.status = "active"

    if not subscription.start_date or subscription.is_expired():
        subscription.start_date = now()

    subscription.expires_at = now() + timedelta(days=subscription.duration_days)
    subscription.save()

    logger.info(f"Subscription activated for customer {subscription.customer_key}")


def send_telegram_message(telegram_id, message):
    """
    Функция для отправки сообщения в Telegram
    """
    print(f"Sending Telegram message to {telegram_id}: {message}")
    bot = Bot(token=BOT_TOKEN)
    try:
        asyncio.run(bot.send_message(chat_id=telegram_id, text=message))
    except Exception as e:
        print(f"Ошибка при отправке сообщения в Telegram: {e}")


def create_stripe_subscription(customer_email, price_id, telegram_id):
    logger.info("Creating Stripe subscription session")
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
        logger.info(f"Stripe session created: {session.id}")
        return session.url
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {e}")
        return None


@csrf_exempt
def stripe_webhook(request):
    logger.info("Stripe webhook triggered")
    payload = request.body
    sig_header = request.headers.get("Stripe-Signature")
    endpoint_secret = STRIPE_WEBHOOK_SECRET

    try:
        logger.info("Constructing Stripe event")
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        logger.info(f"Stripe event type: {event['type']}")

        if event["type"] == "checkout.session.completed":
            logger.info("Processing checkout.session.completed event")
            session = event["data"]["object"]
            telegram_id = session.get("metadata", {}).get("telegram_id")
            subscription_id = session.get("subscription")

            logger.info(
                f"telegram_id: {telegram_id}, subscription_id: {subscription_id}"
            )

            try:
                subscription = Subscription.objects.get(customer_key=telegram_id)
                logger.info("Subscription object found in DB")

                subscription.start_date = now()
                subscription.subscription_id = subscription_id
                subscription.status = "active"
                subscription.expires_at = now() + timedelta(
                    days=subscription.duration_days
                )
                subscription.save()

                logger.info("Subscription updated and saved")
                send_telegram_message(
                    telegram_id,
                    "Оплата прошла успешно! Ваша подписка активирована, перейдите в главное меню слева внизу.",
                )
                logger.info("Telegram message sent successfully")
                return JsonResponse({"status": "success"})

            except Subscription.DoesNotExist:
                logger.error("Subscription not found for telegram_id")
                return JsonResponse(
                    {"status": "error", "message": "Subscription not found"},
                    status=404,
                )

        elif event["type"] == "invoice.paid":
            logger.info("Processing invoice.paid event")
            invoice = event["data"]["object"]
            subscription_id = invoice.get("subscription")
            logger.info(f"invoice.paid for subscription_id: {subscription_id}")

            if invoice.get("billing_reason") == "subscription_create":
                logger.info("Initial subscription_create invoice - skipping")
                return JsonResponse({"status": "initial invoice skipped"}, status=200)

            try:
                stripe_sub = stripe.Subscription.retrieve(subscription_id)
                logger.info(f"Retrieved stripe subscription: {stripe_sub.id}")

                current_period_start = datetime.fromtimestamp(
                    stripe_sub["current_period_start"], tz=timezone.utc
                )
                current_period_end = datetime.fromtimestamp(
                    stripe_sub["current_period_end"], tz=timezone.utc
                )

                subscription = Subscription.objects.get(subscription_id=subscription_id)
                logger.info("Subscription object found in DB for invoice.paid")

                subscription.start_date = current_period_start
                subscription.expires_at = current_period_end
                subscription.status = "active"
                subscription.save()

                logger.info("Subscription updated with new period dates")
            except Subscription.DoesNotExist:
                logger.error("Subscription not found for invoice.paid")

            return JsonResponse({"status": "received"}, status=200)

    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Signature verification error: {e}")
        return JsonResponse({"status": "error", "message": str(e)}, status=400)
    except Exception as e:
        logger.exception("Unexpected error in webhook handler")
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
    context.user_data["telegram_id"] = telegram_id
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
    telegram_id = context.user_data.get("telegram_id")
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")
    coach = await sync_to_async(Coach.objects.get)(telegram_id=telegram_id)
    subscription, created = await sync_to_async(Subscription.objects.get_or_create)(
        customer_key=telegram_id, coach=coach
    )
    choice = context.user_data.get("subscription_choice")

    if query.data == "sub":
        # Show subscription options
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
        await query.edit_message_text(
            "Привет! Я бот, который может <b>создавать программы питания и тренировок</b> для твоих клиентов, <b>определить твое позиционирование, создать контент-план, тексты и сценарии для рилс,</b> а еще я обладаю большой базой знаний для тренеров.\n"
            "<b>Бот использует ИИ</b>, поэтому подписка платная, но он сэкономит тебе часы работы!\n<b>Выбери подходящий тариф</b>\n"
            "<a href='https://www.basetraining.site/bot-offer'>ОФЕРТА</a>, <a href='https://www.basetraining.site/policy'>Политика конфиденциальности</a>.",
            reply_markup=reply_markup,
            parse_mode="HTML",
        )

        await update_chat_mapping(telegram_id, SUBSCRIPTION, context.user_data)
        return SUBSCRIPTION

    # User selected Russian payment method (Lava)
    elif query.data == "rus":
        subscription.payment_method = "lava"

        # Set subscription parameters based on choice
        choice = context.user_data.get("subscription_choice")
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

        await sync_to_async(subscription.save)()

        # Ask for email
        await query.edit_message_text("Введите ваш e-mail:")

        await update_chat_mapping(telegram_id, CUSTOMER_EMAIL, context.user_data)
        return CUSTOMER_EMAIL

    # User selected international payment method (Stripe)
    elif query.data == "world":
        subscription.payment_method = "stripe"
        await sync_to_async(subscription.save)()

        await query.edit_message_text("Введите ваш e-mail:")

        await update_chat_mapping(telegram_id, CUSTOMER_EMAIL, context.user_data)
        return CUSTOMER_EMAIL


async def customer_email(update: Update, context: CallbackContext):
    customer_email = update.message.text.strip()
    telegram_id = context.user_data.get("telegram_id")
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        print(f"mapping found and restored: {mapping.state}")

    context.user_data["customer_email"] = customer_email

    # Get subscription and update email
    subscription = await sync_to_async(Subscription.objects.get)(
        customer_key=telegram_id
    )
    subscription.email = customer_email
    await sync_to_async(subscription.save)()

    choice = context.user_data.get("subscription_choice")
    payment_method = subscription.payment_method

    # Handle payment based on method
    if payment_method == "stripe":
        # For Stripe (international payments)
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

        await sync_to_async(subscription.save)()

        # Create Stripe payment link
        url = create_stripe_subscription(customer_email, price_id, telegram_id)
        if url:
            await update.message.reply_text(
                f'Ваша <a href="{url}">ссылка на оплату</a>', parse_mode="HTML"
            )
        else:
            await update.message.reply_text(
                "Произошла ошибка при создании платежа. Пожалуйста, попробуйте позже."
            )

    elif payment_method == "lava":
        # For Lava (Russian payments)
        if choice == "month_3000":
            subscription.amount = 3000
            subscription.duration_days = 30
            price_id = "8007e933-162e-4136-8bc7-35ecc33582ac"
            period = "MONTHLY"
        elif choice == "3month_2300":
            subscription.amount = 6900
            subscription.duration_days = 90
            price_id = "8007e933-162e-4136-8bc7-35ecc33582ac"
            period = "PERIOD_90_DAYS"
        elif choice == "6month_1800":
            subscription.amount = 10800
            subscription.duration_days = 180
            price_id = "8007e933-162e-4136-8bc7-35ecc33582ac"
            period = "PERIOD_180_DAYS"
        else:
            await update.message.reply_text("Ошибка выбора")
            return MAIN_MENU

        # Generate Lava payment link
        payment_url = await initiate_payment_async(
            subscription.amount, telegram_id, customer_email, price_id, period
        )

        if payment_url:
            await update.message.reply_text(
                f'Ваша <a href="{payment_url}">ссылка на оплату</a>\n\n'
                f"После оплаты вы получите уведомление об активации подписки.",
                parse_mode="HTML",
            )
        else:
            await update.message.reply_text(
                "Произошла ошибка при создании платежа. Пожалуйста, попробуйте позже."
            )

    # Update chat mapping to return to main menu after payment link is sent
    await update_chat_mapping(telegram_id, MAIN_MENU, context.user_data)
    return MAIN_MENU


async def cancel_subscription(update: Update, context: CallbackContext):
    telegram_id = update.message.from_user.id
    context.user_data["telegram_id"] = telegram_id
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
    telegram_id = context.user_data.get("telegram_id")

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


async def non_blocking_db_operation(func, *args, **kwargs):
    """Wrapper to make database operations non-blocking"""
    async with DB_POOL_SEMAPHORE:
        try:
            result = await func(*args, **kwargs)
            return result
        except Exception as e:
            logger.error(f"Database operation error: {e}")
            raise


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


# Rewrite get_subscription to be fully async
async def get_subscription(coach):
    """Non-blocking implementation of get_subscription"""
    async with DB_POOL_SEMAPHORE:
        try:
            # Use Django's sync_to_async for all database operations
            subscription = await sync_to_async(Subscription.objects.filter)(
                coach=coach, status__in=["active", "pending", "pending_cancellation"]
            )
            subscription = await sync_to_async(subscription.first)()

            if not subscription:
                raise Subscription.DoesNotExist("No active subscription found")

            return subscription
        except Exception as e:
            logger.error(f"Error in get_subscription: {e}")
            raise


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
            f"Клиент {new_client.name} успешно добавлен!\n<b>Для корректной работы бота заполните все поля анкеты!</b>\nВведите фамилию клиента:",
            parse_mode="HTML",
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
                f"Клиент {new_client.name} успешно добавлен!\n<b>Для корректной работы бота заполните все поля анкеты!</b>\nВведите фамилию клиента:",
                parse_mode="HTML",
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

            if prompt:

                context.user_data["prompt"] = prompt
                context.user_data["state"] = MAIN_MENU

            context.user_data["state"] = MAIN_MENU

            # Получаем ответ
            waiting_message = await update.callback_query.message.reply_text(
                "Минутку, составляю план!🌀"
            )
            content_type = "menu"
            await update_chat_mapping(telegram_id, MAIN_MENU, context.user_data)

            # Background task that continues the flow without blocking other users
            asyncio.create_task(
                handle_ai_response(update, context, waiting_message, content_type)
            )

            return MAIN_MENU

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
        waiting_message = await query.message.reply_text("Минутку, составляю план!🌀")
        context.user_data["state"] = MAIN_MENU
        content_type = "menu"
        await update_chat_mapping(telegram_id, MAIN_MENU, context.user_data)
        asyncio.create_task(
            handle_ai_response(update, context, waiting_message, content_type)
        )
        return MAIN_MENU


async def client_surname(update: Update, context: CallbackContext):
    telegram_id = context.user_data.get("telegram_id")
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
    telegram_id = context.user_data.get("telegram_id")
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
    telegram_id = context.user_data.get("telegram_id")
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
    telegram_id = context.user_data.get("telegram_id")
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
            prompt = await creating_plan(update, context)
            if prompt:
                waiting_message = await update.message.reply_text(
                    "Минутку, составляю план!🌀"
                )
                context.user_data["state"] = MAIN_MENU
                await update_chat_mapping(telegram_id, MAIN_MENU, context.user_data)
                content_type = "training"

                # Background task that continues the flow without blocking other users
                asyncio.create_task(
                    handle_ai_response(update, context, waiting_message, content_type)
                )

                return MAIN_MENU


async def client_calories(update: Update, context: CallbackContext):
    telegram_id = context.user_data.get("telegram_id")
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


async def generate_openai_response(prompt, api_key):
    """Make an asynchronous OpenAI API call."""
    try:
        async with API_SEMAPHORE:
            client = AsyncOpenAI(api_key=api_key)
            response = await client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="gpt-4-turbo",
            )
            return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Error in OpenAI API call: {e}")
        return None


async def generate_response(update: Update, context: CallbackContext, send_typing=True):
    """Asynchronously generate a response from OpenAI."""
    telegram_id = context.user_data.get("telegram_id")

    # Create a task for context restoration to make it non-blocking
    mapping = await get_chat_mapping(telegram_id)
    if mapping and mapping.context:
        context.user_data.update(mapping.context)
        logger.info(f"Mapping found and restored: {mapping.state}")
    else:
        return None

    prompt = context.user_data.get("prompt")
    if not prompt:
        logger.error("No prompt found in user data")
        return None

    # Send "typing" action if requested
    if send_typing:
        chat_id = None
        if update.callback_query:
            chat_id = update.callback_query.message.chat_id
        elif update.message:
            chat_id = update.message.chat_id

        if chat_id:
            # Don't await this, let it run in the background
            asyncio.create_task(
                context.bot.send_chat_action(chat_id=chat_id, action="typing")
            )

    try:
        # Make the API call directly with the async function
        response_text = await generate_openai_response(prompt, OPENAI_API_KEY)

        if response_text:
            # Store response in context
            context.user_data["response"] = response_text
            messages = context.user_data.get("messages", [])
            messages.append({"role": "assistant", "content": response_text})
            context.user_data["messages"] = messages

            # Update the chat mapping (run as a separate task to avoid blocking)
            current_state = context.user_data.get("state", CHOOSING_ACTION)
            asyncio.create_task(
                update_chat_mapping(telegram_id, current_state, context.user_data)
            )
            return response_text
        else:
            return None
    except Exception as e:
        logger.error(f"Error in generate_response: {e}")
        message_task = None
        if update.callback_query:
            message_task = update.callback_query.message.reply_text(
                "Произошла ошибка при генерации ответа. Попробуйте снова."
            )
        else:
            message_task = update.message.reply_text(
                "Произошла ошибка при генерации ответа. Попробуйте снова."
            )

        # Run as separate tasks to avoid blocking
        asyncio.create_task(message_task)
        asyncio.create_task(
            update_chat_mapping(telegram_id, CHOOSING_ACTION, context.user_data)
        )
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
            client.calories = await client_calories(update, context)
            logger.info(f"calories: {client.calories}")
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

            Добавь рекомендации по технике выполнения и типичные ошибки, которые стоит избегать. Строго придерживайся формата ответа!         
            """
            await update_chat_mapping(telegram_id, CHOOSING_ACTION, context.user_data)

        logger.info(f"Prompt для {plan_type}: {prompt}")
        context.user_data["plan_type"] = plan_type
        context.user_data["prompt"] = prompt
        await update_chat_mapping(telegram_id, CHOOSING_ACTION, context.user_data)
        prompt = prompt
        logger.info(f"prompt: {prompt}")
        return prompt

    except Exception as e:
        logger.error(f"Error in creating_plan: {e}")
        await update.callback_query.edit_message_text(
            "Произошла ошибка при создании плана. Попробуйте снова."
        )
        await update_chat_mapping(telegram_id, CHOOSING_ACTION, context.user_data)
        return CHOOSING_ACTION


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
    - Используй <b> вместо *** и ###
    - Четко придерживайся формата как в примере
    - Используй <b>, чтобы выделить главное
    """
    context.user_data["prompt"] = prompt
    await update_chat_mapping(telegram_id, EFFECT, context.user_data)

    waiting_message = await update.message.reply_text(
        "Опрашиваю маркетологов, одну минутку!🌀"
    )
    context.user_data["state"] = MAIN_MENU
    content_type = "positioning"
    asyncio.create_task(
        handle_ai_response(update, context, waiting_message, content_type)
    )
    await update_chat_mapping(telegram_id, EFFECT, context.user_data)
    return MAIN_MENU


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

    if content_goal == "followers":
        prompt = f"""
Ты экспертный маркетолог, специализирующийся на продвижении тренеров.  
Твоя задача – провести исследование целевой аудитории тренера в направлении "{field}" с позиционированием: {positioning} и разработать контент-план для привлечения подписчиков в {social_media}.  

<b>1. Исследование целевой аудитории:</b>  
Опиши <b>ключевые боли</b> потенциальных клиентов. Какие проблемы мешают им достичь результатов? Что вызывает у них сомнения и трудности?  
Перечисли <b>желания и внутреннюю мотивацию</b> этой аудитории – чего они хотят достичь, какие изменения ожидают?  
Опиши <b>5 страхов</b>, которые могут их останавливать от покупки.  

<b>Важно:</b> Используй только те HTML-теги, которые поддерживаются в Telegram:  
<b>, <i>, <u>, <s>, <code>, <pre>, <a href=""></a>.  
Никаких <ul>, <li>, <h1>, <div>, Markdown, *** или ###.

Если нужно оформить список, используй символы "•" или "-" с переносом строки вручную.

<b>2. Разработка контент-плана:</b>  
Составь 10 вопросов, которые интересуют ЦА тренера на основе проведенного исследования, и создай по ним план на 10 дней для привлечения подписчиков в {social_media}.  

<b>Формат контент-плана (пример):</b>  
Описание болей, страхов и желаний клиентов:  
Кто ваш потенциальный клиент? - Это человек...  
📅 <b>День 1</b> – ...  
📅 <b>День 2</b> – ...  
📅 <b>День 3</b> – ...  
📅 <b>День 4</b> – ...  
📅 <b>День 5</b> – ...  

Продолжи этот формат, создавая уникальные темы на каждый день, опираясь на боли, мечты и страхи аудитории.  
Включи разные форматы (видео, карусели, подкасты), подходящие для {social_media}.  

<b>Важно:</b>  
- Указывай конкретные темы постов, а не просто "контент про боли аудитории".  
- Подбирай темы, которые вызывают отклик и вовлекают.  
- Если контент для Instagram – используй только Reels и посты-карусели.  
- Если для Telegram – посты, кружочки и аудиоподкасты.  
- Если для YouTube – Shorts и видео.  
- Сделай план удобным для реализации, чтобы его можно было сразу использовать в работе.  
- Четко следуй заданному формату.
"""

        context.user_data["prompt"] = prompt
        await update_chat_mapping(telegram_id, CONTENT_PROMPT, context.user_data)
    waiting_message = await update.callback_query.message.reply_text(
        "Опрашиваю аудиторию, одну минутку!🌀"
    )
    context.user_data["state"] = MAIN_MENU
    content_type = "content"
    asyncio.create_task(
        handle_ai_response(update, context, waiting_message, content_type)
    )
    await update_chat_mapping(telegram_id, CONTENT_PROMPT, context.user_data)

    if content_goal == "sales":
        await query.edit_message_text("Расскажите подробно о своей услуге/продукте")
        await update_chat_mapping(telegram_id, CONTENT_SALES, context.user_data)
        return CONTENT_SALES


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
Твоя задача – провести глубокое исследование целевой аудитории для продукта "<b>{sale_product}</b>" тренера по направлению <b>{field}</b> с позиционированием: <b>{positioning}</b>.  

<b>1. Исследование целевой аудитории:</b>  
Опиши <b>ключевые боли</b> потенциальных клиентов, которые мешают им достичь результата и могут мотивировать их купить "<b>{sale_product}</b>".  
Перечисли <b>желания и внутреннюю мотивацию</b> этой аудитории — чего они хотят достичь, к чему стремятся, и что может стать основной причиной покупки.  
Опиши <b>5 страхов</b>, которые могут останавливать их от покупки.  

<b>2. Создание контент-плана:</b>  
Составь 10 вопросов, которые реально волнуют ЦА в контексте {social_media} и связаны с продвижением "<b>{sale_product}</b>". На основе этих вопросов создай контент-план на 10 дней.  
Контент должен вызывать доверие, работать с возражениями, усиливать интерес и мотивировать к покупке. Ориентируйся на боли, желания и страхи клиентов.  

<b>Формат ответа (пример):</b>  
Описание болей, страхов и желаний клиентов:  
Кто ваш потенциальный клиент? – Это человек...  
📅 <b>День 1</b> – ...  
📅 <b>День 2</b> – ...  
📅 <b>День 3</b> – ...  
📅 <b>День 4</b> – ...  
📅 <b>День 5</b> – ...  
📅 <b>День 6</b> – ...  
📅 <b>День 7</b> – ...  
📅 <b>День 8</b> – ...  
📅 <b>День 9</b> – ...  
📅 <b>День 10</b> – ...

<b>Контент должен быть разнообразным:</b>  
• Вовлекающие посты  
• Сторис-идеи  
• Обучающие материалы  
• Отзывы  
• Личные истории  

<b>Важно:</b>  
- Указывай конкретные темы для постов, а не просто "презентация продукта".  
- Каждая тема должна работать с желаниями, страхами или возражениями аудитории.  
- Предложи разные форматы контента:  
  • Instagram — <b>только Reels и посты-карусели</b>  
  • Telegram — <b>только посты, кружочки и аудиоподкасты</b>  
  • YouTube — <b>Shorts и видео</b>  

Сделай контент-план <b>максимально понятным и удобным для использования</b> — чтобы его можно было сразу реализовать в продвижении.
"""
    context.user_data["prompt"] = prompt
    await update_chat_mapping(telegram_id, CONTENT_SALES, context.user_data)
    waiting_message = await update.message.reply_text("Одну минутку!🌀")
    context.user_data["state"] = MAIN_MENU
    content_type = "content"
    asyncio.create_task(
        handle_ai_response(update, context, waiting_message, content_type)
    )
    await update_chat_mapping(telegram_id, CONTENT_SALES, context.user_data)
    return MAIN_MENU


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

Создай <b>подробный, готовый к публикации пост</b> для Instagram/Telegram по теме: <b>{text_idea}</b>  
Специализация тренера: <b>{field}</b>  
Позиционирование и целевая аудитория: <b>{positioning}</b>

<b>Структура поста:</b>

1. <b>Цепляющий заголовок</b> — без «всем привет», сразу в суть боли клиента. Заголовок должен вовлекать с первой секунды и быть написан так, чтобы захотелось читать дальше.

2. <b>Описание проблемы</b> — покажи, с какой ситуацией сталкивается клиент, что он чувствует, о чём переживает, чего боится.

3. <b>Что будет, если проблему не решить</b> — усили внутреннюю мотивацию клиента через возможные негативные сценарии.

4. <b>Как решение изменит жизнь клиента</b> — покажи «жизнь после» и конкретные результаты, к которым он может прийти.

5. <b>Полезные советы</b>, которые клиент может применить уже сейчас — дай 2–3 простых, но действенных совета по теме поста.

6. <b>Призыв к действию</b> — например: «Запишись ко мне на бесплатную консультацию — подберем лучшее решение для тебя».

<b>Требования:</b>
- Без хештегов и смайликов.
- Пиши живым, современным языком, как будто обращаешься к читателю напрямую.
- Избегай формальных фраз, штампов и банальностей.
- Текст должен быть цельным, глубоким и сразу готовым к публикации.
- Используй <b> вместо *** для акцентов.
- Четко следуй предложенной структуре.
"""
    context.user_data["prompt"] = prompt
    await update_chat_mapping(telegram_id, TEXT_GENERATION, context.user_data)
    waiting_message = await update.message.reply_text(
        "Минутку! Опрашиваю тысячу копирайтеров!🌀"
    )
    context.user_data["state"] = MAIN_MENU
    content_type = "post"
    asyncio.create_task(
        handle_ai_response(update, context, waiting_message, content_type)
    )

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
Ты — опытный маркетолог, помогающий тренерам создавать короткие, вовлекающие и продающие Reels.

Твоя задача — написать <b>готовый текст</b> для Reels в Instagram, который тренер сможет использовать как «говорящую голову» (монолог на камеру).  
Специализация тренера: <b>{field}</b>  
Позиционирование и целевая аудитория: <b>{positioning}</b>  
Тема Reels: <b>{text_idea}</b>

<b>Требования к структуре Reels:</b>
1. <b>Цепляющий заголовок</b> — с первых слов в суть боли клиента. Без «привет» и разогрева.
2. <b>Описание проблемы</b> — чётко и живо покажи, с чем сталкивается клиент. Что он чувствует? Что не получается?
3. <b>Простое решение</b> — короткое и понятное, чтобы можно было применить сразу.
4. <b>Призыв к действию</b> — например, подписаться на аккаунт или написать в директ.

<b>Формат и стиль:</b>
- Структурированный, живой, легко читаемый текст.
- Язык — живой, разговорный, как будто говоришь с человеком один на один.
- Без хештегов, смайликов и формальных фраз.
- Используй <b> вместо *** для выделения акцентов.
- Всё оформление — строго в HTML-формате, как для Telegram и Instagram (без ul, без markdown).
"""

    context.user_data["prompt"] = prompt
    await update_chat_mapping(telegram_id, REELS_GENERATION, context.user_data)
    waiting_message = await update.message.reply_text(
        "Минутку! Опрашиваю тысячу рилсмейкеров!🌀"
    )
    context.user_data["state"] = MAIN_MENU
    content_type = "reels"
    asyncio.create_task(
        handle_ai_response(update, context, waiting_message, content_type)
    )
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
    context.user_data["telegram_id"] = telegram_id
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
            CONTENT_SALES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, content_sales),
                CallbackQueryHandler(main_menu, pattern="^main_menu$"),
            ],
            TEXT_GENERATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, text_generation),
                CallbackQueryHandler(main_menu, pattern="^main_menu$"),
            ],
            HANDLE_TRAINING_TYPE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    handle_training_type,
                ),
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
    job_queue.set_application(application)
    job_queue.start()

    application.add_handler(conv_handler)
    application.add_error_handler(error_handler)
    application.add_handler(CommandHandler("clients", get_clients))
    application.add_handler(CommandHandler("support", get_support))
    application.add_handler(CommandHandler("base", knowledge_base))
    application.add_handler(CommandHandler("edu", education))
    application.add_handler(CommandHandler("new", new_client))
    application.add_handler(CommandHandler("sub", cancel_subscription))
    application.run_polling()


if __name__ == "__main__":
    main()
