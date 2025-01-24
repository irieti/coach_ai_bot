from django.contrib import admin
from .models import Coach, Client, NutritionPlan, MuscleGroup, Exercise, TrainingProgram


class CoachAdmin(admin.ModelAdmin):
    search_fields = ["name", "telegram_id"]
    list_display = ["name", "telegram_id"]


class ClientAdmin(admin.ModelAdmin):
    search_fields = ["name", "surname", "coach__name"]
    list_display = ["name", "surname", "coach", "weight", "activity_level"]
    list_filter = ["coach", "activity_level"]


class NutritionPlanAdmin(admin.ModelAdmin):
    search_fields = ["title", "client__name"]
    list_display = ["title", "client", "created_at"]


class ExerciseAdmin(admin.ModelAdmin):
    search_fields = ["title", "muscle_group__name"]
    list_display = ["title", "muscle_group", "difficulty", "sets", "reps"]


class TrainingProgramAdmin(admin.ModelAdmin):
    search_fields = ["title", "client__name"]
    list_display = ["title", "client", "created_at"]
    list_filter = ["client"]


class MuscleGroupAdmin(admin.ModelAdmin):
    search_fields = ["name"]
    list_display = ["name"]


# Регистрируем модели с дополнительными настройками
admin.site.register(Coach, CoachAdmin)
admin.site.register(Client, ClientAdmin)
admin.site.register(NutritionPlan, NutritionPlanAdmin)
admin.site.register(MuscleGroup, MuscleGroupAdmin)
admin.site.register(Exercise, ExerciseAdmin)
admin.site.register(TrainingProgram, TrainingProgramAdmin)
