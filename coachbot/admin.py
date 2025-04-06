from django.contrib import admin
from .models import Coach, Subscription, Client, NutritionPlan, ChatMapping


@admin.register(Coach)
class CoachAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "telegram_id", "field", "positioning")
    search_fields = ("name", "telegram_id")


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("rebill_id", "coach", "status", "start_date", "expires_at")
    list_filter = ("status", "payment_method")
    search_fields = ("rebill_id", "coach__name")


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "surname", "coach", "goal", "calories")
    list_filter = ("goal",)
    search_fields = ("name", "surname", "coach__name")


@admin.register(NutritionPlan)
class NutritionPlanAdmin(admin.ModelAdmin):
    list_display = ("id", "client", "title", "created_at")
    search_fields = ("title", "client__name")


@admin.register(ChatMapping)
class ChatMappingAdmin(admin.ModelAdmin):
    list_display = ("telegram_id", "state")
    search_fields = ("telegram_id",)
