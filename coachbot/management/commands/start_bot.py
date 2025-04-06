from django.core.management.base import BaseCommand
import asyncio
from ... import views  # импортируйте ваш скрипт для бота, если он в другом файле


class Command(BaseCommand):
    help = "Запускает Telegram-бота"

    def handle(self, *args, **kwargs):
        # Run the main coroutine using asyncio
        asyncio.run(views.main())
