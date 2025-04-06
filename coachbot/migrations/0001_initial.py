# Generated by Django 5.1.2 on 2025-04-01 20:07

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ChatMapping",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("telegram_id", models.CharField(max_length=100, unique=True)),
                ("state", models.CharField(blank=True, max_length=100, null=True)),
                ("context", models.JSONField(default=dict)),
            ],
        ),
        migrations.CreateModel(
            name="Coach",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=100)),
                ("telegram_id", models.CharField(max_length=50, unique=True)),
                ("field", models.CharField(max_length=100, null=True)),
                ("positioning", models.CharField(max_length=1000, null=True)),
            ],
        ),
        migrations.CreateModel(
            name="Client",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=100)),
                ("surname", models.CharField(max_length=50)),
                ("weight", models.IntegerField(null=True)),
                ("activity_level", models.FloatField(null=True)),
                (
                    "goal",
                    models.CharField(
                        choices=[
                            ("похудение", "Похудение"),
                            ("набор массы", "Набор массы"),
                            ("тонус", "Тонус"),
                        ],
                        default="похудение",
                        max_length=50,
                    ),
                ),
                ("calories", models.FloatField(null=True)),
                ("carbs", models.FloatField(blank=True, null=True)),
                ("fats", models.FloatField(blank=True, null=True)),
                ("proteins", models.FloatField(blank=True, null=True)),
                (
                    "no_products",
                    models.TextField(blank=True, max_length=500, null=True),
                ),
                (
                    "yes_products",
                    models.TextField(blank=True, max_length=500, null=True),
                ),
                ("allergies", models.TextField(blank=True, max_length=500, null=True)),
                (
                    "menu_generator",
                    models.TextField(blank=True, max_length=10000, null=True),
                ),
                (
                    "coach",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="clients",
                        to="coachbot.coach",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="NutritionPlan",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("title", models.CharField(max_length=200)),
                ("description", models.TextField()),
                ("details", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="nutrition_plans",
                        to="coachbot.client",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Subscription",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("rebill_id", models.CharField(max_length=255, unique=True)),
                (
                    "subscription_id",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                ("payment_id", models.CharField(blank=True, max_length=255, null=True)),
                (
                    "customer_key",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                (
                    "amount",
                    models.DecimalField(decimal_places=2, max_digits=10, null=True),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("active", "Active"),
                            ("canceled", "Canceled"),
                            ("pending", "Pending"),
                            ("pending_cancellation", "Pending cancellation"),
                        ],
                        default="pending",
                        max_length=50,
                    ),
                ),
                ("start_date", models.DateTimeField(blank=True, null=True)),
                ("duration_days", models.IntegerField(default=30)),
                (
                    "payment_method",
                    models.CharField(
                        choices=[
                            ("stripe", "card (world)"),
                            ("tinkoff", "card (russia)"),
                        ],
                        default="tinkoff",
                        max_length=50,
                    ),
                ),
                (
                    "coach",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="subscription",
                        to="coachbot.coach",
                    ),
                ),
            ],
        ),
    ]
