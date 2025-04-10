from django.contrib import admin
from django.urls import path
from . import views

urlpatterns = [path("admin/", admin.site.urls),
    path(
        "tinkoff-webhook",
        views.tinka_webhook,
        name="tinkoff_webhook",
    ),
    path("stripe-webhook", views.stripe_webhook, name="stripe_webhook"),
]
