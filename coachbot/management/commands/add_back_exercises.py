from django.core.management.base import BaseCommand
from ...models import Exercise, MuscleGroup


class Command(BaseCommand):
    help = (
        "Добавляет упражнения для верхней части спины и широчайших мышц в базу данных"
    )

    def handle(self, *args, **kwargs):
        # Получаем или создаем группу мышц для верхней части спины и широчайших
        upper_back_group, created = MuscleGroup.objects.get_or_create(
            name="Верхняя часть спины"
        )
        lats_group, created = MuscleGroup.objects.get_or_create(name="Широчайшие")

        # Упражнения для верхней части спины (beginner, intermediate, advanced)
        upper_back_exercises = [
            {
                "title": "Тяга верхнего блока широким хватом",
                "description": "Эффективно прорабатывает верхнюю часть спины, включая трапецию и ромбовидные мышцы.",
                "technique": "Сядьте на тренажер для тяги верхнего блока. Возьмитесь за рукоятки широким хватом и потяните их к груди, разводя локти в стороны.",
                "difficulty": "beginner",
                "sets": 3,
                "reps": 12,
            },
            {
                "title": "Тяга с канатной рукояткой",
                "description": "Акцент на верхнюю часть спины, трапецию и ромбовидные мышцы.",
                "technique": "Используйте канат в тренажере для тяги верхнего блока. Тяните канат к лицу, разводя локти в стороны.",
                "difficulty": "beginner",
                "sets": 3,
                "reps": 10,
            },
            {
                "title": "Тяга штанги к подбородку",
                "description": "Развивает верхнюю часть спины и плечи.",
                "technique": "Тяните штангу к подбородку, разводя локти в стороны.",
                "difficulty": "intermediate",
                "sets": 4,
                "reps": 10,
            },
            {
                "title": "Тяга T-образного блока",
                "description": "Развивает верхнюю часть спины и улучшает осанку.",
                "technique": "Используйте T-образный тренажер. Потяните рукоятки к груди, разводя локти в стороны и сжимая лопатки.",
                "difficulty": "intermediate",
                "sets": 4,
                "reps": 8,
            },
            {
                "title": "Тяга штанги в наклоне",
                "description": "Тяга штанги в наклоне с хорошим фокусом на верхней части спины.",
                "technique": "Станьте в наклон, держите штангу и тяните её к верхней части живота, сводя лопатки.",
                "difficulty": "advanced",
                "sets": 5,
                "reps": 6,
            },
            {
                "title": "Подтягивания с дополнительным весом",
                "description": "Продвинутое упражнение для тренировки верхней части спины.",
                "technique": "Подтягивайтесь с дополнительным весом, контролируя движение.",
                "difficulty": "advanced",
                "sets": 5,
                "reps": 5,
            },
        ]

        # Упражнения для широчайших мышц спины (beginner, intermediate, advanced)
        lats_exercises = [
            {
                "title": "Тяга гантели в наклоне одной рукой",
                "description": "Упражнение для тренировки широчайших мышц спины.",
                "technique": "Встаньте на одно колено, опирайтесь на скамью. Поднимите гантель, приводя локоть к бедру.",
                "difficulty": "beginner",
                "sets": 3,
                "reps": 10,
            },
            {
                "title": "Подтягивания с опорой",
                "description": "Подтягивания с помощью тренажера для облегчения движения.",
                "technique": "Используйте тренажер для подтягиваний с опорой. Подтягивайтесь, контролируя движение.",
                "difficulty": "beginner",
                "sets": 3,
                "reps": 6,
            },
            {
                "title": "Тяга штанги в наклоне",
                "description": "Основное упражнение для тренировки широчайших мышц.",
                "technique": "Тяните штангу к животу, сводя локти в стороны.",
                "difficulty": "intermediate",
                "sets": 4,
                "reps": 8,
            },
            {
                "title": "Подтягивания с дополнительным весом",
                "description": "Продвинутое упражнение для тренировки широчайших мышц.",
                "technique": "Подтягивайтесь с дополнительным весом, контролируя движение.",
                "difficulty": "intermediate",
                "sets": 4,
                "reps": 6,
            },
            {
                "title": "Тяга в Т-образном тренажере с дополнительным весом",
                "description": "Акцент на широчайшие мышцы с добавлением дополнительного веса.",
                "technique": "Используйте T-образный тренажер с дополнительным весом, тяни рукоятки к животу.",
                "difficulty": "advanced",
                "sets": 5,
                "reps": 5,
            },
            {
                "title": "Тяга с канатной рукояткой в наклоне",
                "description": "Упражнение для проработки широчайших мышц с канатом.",
                "technique": "Тяните канат в наклоне, сосредоточив усилия на лопатках.",
                "difficulty": "advanced",
                "sets": 5,
                "reps": 6,
            },
        ]

        # Добавление упражнений в базу данных
        for exercise_data in upper_back_exercises:
            Exercise.objects.create(muscle_group=upper_back_group, **exercise_data)

        for exercise_data in lats_exercises:
            Exercise.objects.create(muscle_group=lats_group, **exercise_data)

        self.stdout.write(
            self.style.SUCCESS(
                "Упражнения для верхней части спины и широчайших мышц успешно добавлены в базу данных."
            )
        )
