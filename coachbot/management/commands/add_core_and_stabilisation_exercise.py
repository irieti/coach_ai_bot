from django.core.management.base import BaseCommand
from ...models import Exercise, MuscleGroup


class Command(BaseCommand):
    help = (
        "Добавление упражнений для мышц кора и разгибателей позвоночника в базу данных"
    )

    def handle(self, *args, **options):
        # Создание групп мышц
        core_group, created = MuscleGroup.objects.get_or_create(name="Мышцы кора")
        lower_back_group, created = MuscleGroup.objects.get_or_create(
            name="Разгибатели позвоночника"
        )

        # Упражнения для мышц кора
        core_exercises = [
            {
                "title": "Планка",
                "description": "Одно из самых эффективных упражнений для тренировки мышц кора.",
                "technique": "Примите положение, как для отжиманий, но опирайтесь на локти. Держите тело в прямой линии от головы до пят. Удерживайте это положение максимально долго.",
                "difficulty": "advanced",
                "sets": 3,
                "duration": 30,  # Продолжительность в секундах
            },
            {
                "title": "Русские повороты",
                "description": "Упражнение для укрепления боковых мышц кора.",
                "technique": "Сядьте на пол, согнув колени, немного откиньтесь назад. Держите руки перед собой, поворачивайте корпус влево и вправо.",
                "difficulty": "advanced",
                "sets": 3,
                "reps": 20,  # Повторения на каждую сторону
            },
            {
                "title": "Подъемы ног",
                "description": "Упражнение для тренировки нижней части мышц кора.",
                "technique": "Лягте на спину, руки под ягодицы. Поднимайте прямые ноги вверх, затем опускайте, не касаясь пола.",
                "difficulty": "advanced",
                "sets": 4,
                "reps": 15,
            },
            {
                "title": "Боковая планка",
                "description": "Упражнение для проработки боковых мышц корпуса.",
                "technique": "Лягте на бок, опирайтесь на один локоть. Поднимите бедра, создавая прямую линию от головы до ног. Удерживайте положение.",
                "difficulty": "advanced",
                "sets": 3,
                "duration": 30,  # Продолжительность в секундах
            },
            {
                "title": "Велосипед",
                "description": "Динамическое упражнение для тренировки мышц кора и бедер.",
                "technique": "Лягте на спину, подтяните колени к груди. Попеременно вытягивайте ноги, стараясь коснуться локтем противоположного колена.",
                "difficulty": "advanced",
                "sets": 3,
                "reps": 20,
            },
        ]

        # Упражнения для разгибателей позвоночника
        lower_back_exercises = [
            {
                "title": "Гиперэкстензия",
                "description": "Основное упражнение для тренировки разгибателей позвоночника.",
                "technique": "Лягте на тренажер для гиперэкстензии. Согните колени, зафиксируйте ноги. Поднимите корпус вверх, затем опуститесь, не округляя спину.",
                "difficulty": "advanced",
                "sets": 3,
                "reps": 12,
            },
            {
                "title": "Супермен",
                "description": "Упражнение для укрепления нижней части спины и разгибателей позвоночника.",
                "technique": "Лягте на живот, вытяните руки и ноги. Одновременно поднимите руки, грудную клетку и ноги от пола, удерживая это положение.",
                "difficulty": "advanced",
                "sets": 3,
                "reps": 15,
            },
            {
                "title": "Румынская тяга",
                "description": "Упражнение для укрепления поясничных мышц и задней цепи.",
                "technique": "Возьмите штангу или гантели. Стоя с прямыми ногами, наклонитесь вперед, сохраняя спину прямой. Поднимитесь, возвращаясь в исходное положение.",
                "difficulty": "advanced",
                "sets": 4,
                "reps": 8,
            },
            {
                "title": "Мостик на спине",
                "description": "Упражнение для тренировки нижней части спины и ягодичных мышц.",
                "technique": "Лягте на спину, согните колени. Поднимите бедра вверх, напрягая ягодицы и мышцы спины. Опуститесь и повторите.",
                "difficulty": "advanced",
                "sets": 3,
                "reps": 12,
            },
            {
                "title": "Тяга блока к груди сидя",
                "description": "Упражнение для тренировки разгибателей позвоночника и спины.",
                "technique": "Сядьте в тренажер с канатной рукояткой. Потяните рукоятку к груди, сохраняя спину прямой. Вернитесь в исходное положение.",
                "difficulty": "advanced",
                "sets": 3,
                "reps": 10,
            },
        ]

        # Добавление упражнений в базу данных
        for exercise_data in core_exercises:
            Exercise.objects.create(
                title=exercise_data["title"],
                description=exercise_data["description"],
                technique=exercise_data["technique"],
                muscle_group=core_group,
                difficulty=exercise_data["difficulty"],
                sets=exercise_data["sets"],
                reps=exercise_data.get("reps", None),
            )

        for exercise_data in lower_back_exercises:
            Exercise.objects.create(
                title=exercise_data["title"],
                description=exercise_data["description"],
                technique=exercise_data["technique"],
                muscle_group=lower_back_group,
                difficulty=exercise_data["difficulty"],
                sets=exercise_data["sets"],
                reps=exercise_data.get("reps", None),
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Упражнения для мышц кора и разгибателей позвоночника успешно добавлены!"
            )
        )
