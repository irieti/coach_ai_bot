from django.db import models


class Coach(models.Model):
    name = models.CharField(max_length=100)
    telegram_id = models.CharField(max_length=50, unique=True)
    field = models.CharField(max_length=100, null=True)

    def __str__(self):
        return self.name


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


class MuscleGroup(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Exercise(models.Model):
    DIFFICULTY_CHOICES = [
        ("beginner", "Beginner"),
        ("intermediate", "Intermediate"),
        ("advanced", "Advanced"),
    ]

    id = models.BigAutoField(primary_key=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    technique = models.TextField(blank=True)
    muscle_group = models.ForeignKey(
        MuscleGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="exercises",
    )
    sets = models.PositiveIntegerField(null=True, blank=True)
    reps = models.PositiveIntegerField(null=True, blank=True)
    difficulty = models.CharField(
        max_length=50, choices=DIFFICULTY_CHOICES, blank=True, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class TrainingProgram(models.Model):
    id = models.BigAutoField(primary_key=True)
    client = models.ForeignKey(
        Client, on_delete=models.CASCADE, related_name="training_programs"
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    exercises = models.ManyToManyField(Exercise, related_name="training_programs")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.client.name} {self.client.surname} - {self.title}"
