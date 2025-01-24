from django.core.management.base import BaseCommand
from ...models import Exercise, MuscleGroup


class Command(BaseCommand):
    help = "Add abdominal exercises to the database"

    def handle(self, *args, **kwargs):
        self.add_abdominal_exercises()

    def add_abdominal_exercises(self):
        # Проверяем существование группы мышц и создаем её при необходимости
        abdominal_group, created = MuscleGroup.objects.get_or_create(name="Abs")
        if created:
            self.stdout.write(self.style.SUCCESS('Muscle group "Abs" created.'))
        else:
            self.stdout.write(self.style.SUCCESS('Muscle group "Abs" already exists.'))

        # Прямые мышцы пресса (beginner, intermediate, advanced)
        straight_abdominal_exercises = [
            # Beginner
            {
                "title": "Классические скручивания",
                "description": "Основное упражнение для тренировки прямых мышц пресса.",
                "technique": "Лягте на спину, согните колени и поднимайте верхнюю часть туловища к коленям.",
                "difficulty": "beginner",
                "sets": 3,
                "reps": 15,
            },
            {
                "title": "Подъемы ног лежа",
                "description": "Упражнение для тренировки нижней части пресса.",
                "technique": "Лежа на спине, поднимайте прямые ноги вверх, затем опускайте.",
                "difficulty": "beginner",
                "sets": 3,
                "reps": 12,
            },
            # Intermediate
            {
                "title": "Велосипедные скручивания",
                "description": "Эффективное упражнение для тренировки прямых и косых мышц пресса.",
                "technique": "Лягте на спину и выполняйте попеременные скручивания, касаясь локтем противоположного колена.",
                "difficulty": "intermediate",
                "sets": 3,
                "reps": 20,
            },
            {
                "title": "Пресс с поднятыми ногами",
                "description": "Усложненный вариант подъема корпуса.",
                "technique": "Лягте на спину, поднимите ноги перпендикулярно полу и выполняйте скручивания.",
                "difficulty": "intermediate",
                "sets": 3,
                "reps": 15,
            },
            # Advanced
            {
                "title": "Подъемы корпуса с утяжелением",
                "description": "Сложное упражнение с дополнительной нагрузкой.",
                "technique": "Лягте на спину, держите гантель на груди и поднимайте верхнюю часть туловища.",
                "difficulty": "advanced",
                "sets": 4,
                "reps": 12,
            },
            {
                "title": "Драконий флаг",
                "description": "Упражнение на силу пресса и стабилизацию.",
                "technique": "Лежа на скамье, удерживайте корпус прямым, опуская ноги медленно вниз.",
                "difficulty": "advanced",
                "sets": 3,
                "reps": 10,
            },
        ]

        # Косые мышцы пресса (beginner, intermediate, advanced)
        oblique_abdominal_exercises = [
            # Beginner
            {
                "title": "Косые скручивания",
                "description": "Упражнение для тренировки косых мышц пресса.",
                "technique": "Лягте на спину и поочередно поворачивайтесь, скручивая туловище.",
                "difficulty": "beginner",
                "sets": 3,
                "reps": 15,
            },
            # Intermediate
            {
                "title": "Русский твист с гантелей",
                "description": "Тренировка косых мышц с дополнительной нагрузкой.",
                "technique": "Сядьте на пол, держите гантель и поворачивайтесь туловищем в стороны.",
                "difficulty": "intermediate",
                "sets": 3,
                "reps": 20,
            },
            {
                "title": "Повороты корпуса на блоке",
                "description": "Эффективное упражнение для тренировки косых мышц.",
                "technique": "Встаньте боком к тренажеру и тяните ручку блока, поворачивая корпус.",
                "difficulty": "intermediate",
                "sets": 3,
                "reps": 15,
            },
            # Advanced
            {
                "title": "Боковая планка с утяжелением",
                "description": "Сложный вариант боковой планки.",
                "technique": "Примите положение боковой планки, удерживая утяжеление на бедре.",
                "difficulty": "advanced",
                "sets": 3,
                "reps": 12,
            },
            {
                "title": "Скручивания на наклонной скамье",
                "description": "Сложное упражнение для тренировки косых мышц.",
                "technique": "Лягте на наклонную скамью и выполняйте скручивания с поворотом.",
                "difficulty": "advanced",
                "sets": 4,
                "reps": 15,
            },
        ]

        # Добавление упражнений в базу данных
        for exercise_data in straight_abdominal_exercises:
            Exercise.objects.create(muscle_group=abdominal_group, **exercise_data)

        for exercise_data in oblique_abdominal_exercises:
            Exercise.objects.create(muscle_group=abdominal_group, **exercise_data)

        self.stdout.write(self.style.SUCCESS("Abdominal exercises successfully added."))
