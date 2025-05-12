from django.contrib import admin
from django.urls import path
from . import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("webhook-lava/", views.lava_webhook, name="lava_webhook"),
    path("stripe-webhook", views.stripe_webhook, name="stripe_webhook"),
]
