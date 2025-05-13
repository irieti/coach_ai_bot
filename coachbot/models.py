from django.db import models
from django.utils.timezone import now, timedelta


class Coach(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=100)
    telegram_id = models.CharField(max_length=50, unique=True)
    field = models.CharField(max_length=100, null=True)
    positioning = models.CharField(max_length=5000, null=True)

    def __str__(self):
        return self.name


class Subscription(models.Model):
    rebill_id = models.CharField(max_length=255, unique=True, blank=True)
    subscription_id = models.CharField(max_length=255, blank=True, null=True)
    email = models.EmailField(null=True, blank=True)
    payment_id = models.CharField(max_length=255, blank=True, null=True)
    customer_key = models.CharField(max_length=255, blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=50,
        choices=[
            ("active", "Active"),
            ("canceled", "Canceled"),
            ("pending", "Pending"),
            ("pending_cancellation", "Pending cancellation"),
        ],
        default="pending",
    )
    coach = models.ForeignKey(
        Coach, related_name="subscription", on_delete=models.CASCADE
    )

    start_date = models.DateTimeField(null=True, blank=True)  # Дата начала подписки
    duration_days = models.IntegerField(default=30)  # Длительность подписки в днях
    payment_method = models.CharField(
        max_length=50,
        choices=[
            ("stripe", "card (world)"),
            ("tinkoff", "card (russia)"),
        ],
        default="tinkoff",
    )

    def __str__(self):
        return f"Subscription {self.rebill_id} ({self.status})"

    def calculate_expires_at(self):
        if self.start_date:
            return self.start_date + timedelta(days=self.duration_days)
        return None

    def is_expired(self):
        """Подписка истекла (нужно попробовать оплатить)"""
        expiration_date = self.expires_at
        return expiration_date and expiration_date <= now()

    def is_expired_yesterday(self):
        """Подписка истекла вчера или раньше (оплата не прошла)"""
        expiration_date = self.expires_at
        return expiration_date and expiration_date.date() <= (
            now().date() - timedelta(days=1)
        )

    def is_active(self):
        """Подписка активна, если её срок не истёк"""
        return self.status == "active" and not self.is_expired()

    def check_and_cancel(self):
        if self.status == "pending_cancellation":
            self.status = "canceled"
            self.save()

    def renew(self, duration_days):
        """Продление подписки"""
        self.start_date = now()
        self.duration_days = duration_days
        self.status = "active"
        self.save()


class Client(models.Model):
    id = models.BigAutoField(primary_key=True)
    coach = models.ForeignKey(Coach, on_delete=models.CASCADE, related_name="clients")
    name = models.CharField(max_length=100)
    surname = models.CharField(max_length=50)
    weight = models.IntegerField(null=True)
    activity_level = models.FloatField(null=True)
    goal = models.CharField(
        max_length=50,
        choices=[
            ("похудение", "Похудение"),
            ("набор массы", "Набор массы"),
            ("тонус", "Тонус"),
        ],
        default="похудение",
    )
    calories = models.FloatField(null=True)
    carbs = models.FloatField(blank=True, null=True)
    fats = models.FloatField(blank=True, null=True)
    proteins = models.FloatField(blank=True, null=True)
    no_products = models.TextField(max_length=500, blank=True, null=True)
    yes_products = models.TextField(max_length=500, blank=True, null=True)
    allergies = models.TextField(max_length=500, blank=True, null=True)
    menu_generator = models.TextField(max_length=10000, blank=True, null=True)

    def __str__(self):
        return f"{self.id}: {self.name}, {self.surname}"


class NutritionPlan(models.Model):
    client = models.ForeignKey(
        Client, on_delete=models.CASCADE, related_name="nutrition_plans"
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    details = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.client.name} - {self.title}"


class ChatMapping(models.Model):
    telegram_id = models.CharField(max_length=100, unique=True)  # ID пользователя
    state = models.CharField(max_length=100, blank=True, null=True)  # Текущее состояние
    context = models.JSONField(default=dict)  # Текущий контекст

    def __str__(self):
        return f"User ID: {self.telegram_id}"
