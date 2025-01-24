from django.core.management.base import BaseCommand
from ...models import Exercise, MuscleGroup


class Command(BaseCommand):
    help = "Добавляет упражнения для ног уровня advanced"

    def handle(self, *args, **kwargs):
        # Создание групп мышц для ног
        quads_group, created = MuscleGroup.objects.get_or_create(name="Квадрицепсы")
        hamstrings_group, created = MuscleGroup.objects.get_or_create(
            name="Бицепсы бедра"
        )
        calves_group, created = MuscleGroup.objects.get_or_create(
            name="Икроножные мышцы"
        )

        # Упражнения для квадрицепсов
        quads_exercises = [
            {
                "title": "Приседания с паузой в нижней точке",
                "description": "Усложненная версия приседаний для повышения силы и выносливости квадрицепсов.",
                "technique": "Встаньте с штангой на плечах, выполните приседание и задержитесь на 2-3 секунды в нижней точке перед возвратом в исходное положение.",
                "difficulty": "advanced",
                "sets": 4,
                "reps": 6,
            },
            {
                "title": "Болгарские сплит-приседания с гантелями",
                "description": "Упражнение на силу и баланс для глубокого прорабатывания квадрицепсов.",
                "technique": "Одну ногу поставьте на скамью позади себя, держите гантели в руках и выполняйте приседания на передней ноге.",
                "difficulty": "advanced",
                "sets": 3,
                "reps": 10,
            },
        ]

        # Упражнения для бицепсов бедра
        hamstrings_exercises = [
            {
                "title": "Становая тяга на прямых ногах",
                "description": "Сложное упражнение для интенсивной нагрузки на бицепсы бедра и ягодицы.",
                "technique": "Возьмите штангу, держите ноги почти прямыми, опустите штангу вниз, сохраняя спину ровной, затем вернитесь в исходное положение.",
                "difficulty": "advanced",
                "sets": 4,
                "reps": 8,
            },
            {
                "title": "Сгибания ног в тренажере с увеличенным весом",
                "description": "Упражнение для изолированной нагрузки на бицепсы бедра с высокой интенсивностью.",
                "technique": "Настройте тренажер с большим весом, выполните сгибания ног, задерживая движение в пиковой точке.",
                "difficulty": "advanced",
                "sets": 4,
                "reps": 10,
            },
        ]

        # Упражнения для икроножных мышц
        calves_exercises = [
            {
                "title": "Подъемы на носки в тренажере с увеличенной амплитудой",
                "description": "Интенсивное упражнение для максимального прорабатывания икроножных мышц.",
                "technique": "Сядьте в тренажер, поднимайтесь на носки, удерживая верхнюю точку на 2-3 секунды, затем медленно опуститесь вниз.",
                "difficulty": "advanced",
                "sets": 4,
                "reps": 12,
            },
            {
                "title": "Подъемы на носки с гантелями на одной ноге",
                "description": "Упражнение для улучшения баланса и силы икроножных мышц.",
                "technique": "Держите гантель в одной руке, другой рукой опирайтесь на устойчивую поверхность. Выполняйте подъемы на носке одной ноги, меняя ногу после подхода.",
                "difficulty": "advanced",
                "sets": 3,
                "reps": 15,
            },
        ]

        # Добавление упражнений в базу данных
        for exercise_data in quads_exercises:
            Exercise.objects.create(
                title=exercise_data["title"],
                description=exercise_data["description"],
                technique=exercise_data["technique"],
                muscle_group=quads_group,
                difficulty=exercise_data["difficulty"],
                sets=exercise_data["sets"],
                reps=exercise_data["reps"],
            )

        for exercise_data in hamstrings_exercises:
            Exercise.objects.create(
                title=exercise_data["title"],
                description=exercise_data["description"],
                technique=exercise_data["technique"],
                muscle_group=hamstrings_group,
                difficulty=exercise_data["difficulty"],
                sets=exercise_data["sets"],
                reps=exercise_data["reps"],
            )

        for exercise_data in calves_exercises:
            Exercise.objects.create(
                title=exercise_data["title"],
                description=exercise_data["description"],
                technique=exercise_data["technique"],
                muscle_group=calves_group,
                difficulty=exercise_data["difficulty"],
                sets=exercise_data["sets"],
                reps=exercise_data["reps"],
            )

        self.stdout.write(
            self.style.SUCCESS("Упражнения для ног уровня advanced успешно добавлены!")
        )
