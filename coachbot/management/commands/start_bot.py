from django.core.management.base import BaseCommand
from ... import views  # импортируйте ваш скрипт для бота, если он в другом файле


class Command(BaseCommand):
    help = "Запускает Telegram-бота"

    def handle(self, *args, **kwargs):
        views.main()
