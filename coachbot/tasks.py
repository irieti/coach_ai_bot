from celery import shared_task
from django.utils.timezone import now
from .models import Subscription
import logging
from datetime import timedelta
import openai
from django.conf import settings
from telegram import Bot
import os
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")


@shared_task
def check_expired_subscriptions():
    today = now()
    renewed_count = 0
    failed_count = 0

    active_subscriptions = Subscription.objects.filter(
        status__in=["active", "pending"],
        expires_at__isnull=False,
        expires_at__lte=today,
    )

    for subscription in active_subscriptions:
        logger.info(f"Found expired subscription: {subscription.rebill_id}")

        from .views import (
            process_recurring_payment,
        )

        if subscription.payment_method == "tinkoff":
            result = process_recurring_payment(
                subscription.customer_key, subscription.amount
            )

            if result["status"] == "success":
                logger.info(
                    f"Successfully renewed subscription {subscription.rebill_id}"
                )
                renewed_count += 1

                subscription.start_date = now()
                subscription.expires_at = now() + timedelta(
                    days=subscription.duration_days
                )
                subscription.status = "active"
                subscription.save()
            else:
                logger.error(
                    f"Failed to renew subscription {subscription.rebill_id}: {result['message']}"
                )
                failed_count += 1
                subscription.status = "pending"
                subscription.save()

        elif subscription.payment_method == "stripe":
            subscription.status = "pending"
            subscription.save()

    cancel_subs = Subscription.objects.filter(
        status="pending_cancellation",
        expires_at__isnull=False,
        expires_at__lte=today,
    )
    for subscription in cancel_subs:
        subscription.check_and_cancel()

    return f"Processed {renewed_count + failed_count} expired subscriptions: {renewed_count} renewed, {failed_count} failed"


@shared_task
def generate_openai_response_task(prompt, telegram_id):
    try:
        openai.api_key = OPENAI_API_KEY
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=2000,
        )
        reply = response.choices[0].message.content

        # Отправляем сообщение в телеграм
        bot = Bot(token=BOT_TOKEN)
        bot.send_message(chat_id=telegram_id, text=reply)

        # Можно также обновить mapping в базе
        return reply
    except Exception as e:
        logger.error(f"Error generating OpenAI response: {e}")
        return None
