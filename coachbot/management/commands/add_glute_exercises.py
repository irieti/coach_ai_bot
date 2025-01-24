from django.core.management.base import BaseCommand
from ...models import Exercise, MuscleGroup


class Command(BaseCommand):
    help = "Добавление упражнений для ягодиц в базу данных"

    def handle(self, *args, **options):
        # Создание групп мышц для ягодиц
        glutes_major_group, created = MuscleGroup.objects.get_or_create(
            name="Большие ягодичные мышцы"
        )
        glutes_minor_group, created = MuscleGroup.objects.get_or_create(
            name="Средние и малые ягодичные мышцы"
        )

        # Упражнения для больших ягодичных мышц
        glutes_major_exercises = [
            {
                "title": "Приседания с паузой в нижней точке",
                "description": "Усложненный вариант приседаний для активации больших ягодичных мышц.",
                "technique": "Встаньте с штангой на плечах, ноги на ширине плеч. Приседайте, удерживая паузу в нижней точке на 2-3 секунды, затем возвращайтесь в исходное положение.",
                "difficulty": "advanced",
                "sets": 5,
                "reps": 6,
            },
            {
                "title": "Румынская тяга с штангой",
                "description": "Упражнение для усиленной нагрузки на ягодичные мышцы и заднюю поверхность бедра.",
                "technique": "Возьмите штангу, наклонитесь вперед с прямой спиной, опуская штангу вниз, затем вернитесь в исходное положение.",
                "difficulty": "advanced",
                "sets": 4,
                "reps": 8,
            },
            {
                "title": "Ягодичный мостик с утяжелением",
                "description": "Продвинутый вариант ягодичного мостика с дополнительным весом.",
                "technique": "Лягте на спину, положите штангу на бедра. Поднимите бедра вверх, сжимая ягодицы, затем опуститесь.",
                "difficulty": "advanced",
                "sets": 4,
                "reps": 10,
            },
            {
                "title": "Жим ногами с высокой постановкой ног",
                "description": "Усложненный жим ногами для акцента на ягодичные мышцы.",
                "technique": "Сядьте в тренажер для жима ногами, поставьте ноги на платформу выше обычного. Приседайте и выжимайте платформу вверх.",
                "difficulty": "advanced",
                "sets": 5,
                "reps": 8,
            },
            {
                "title": "Приседания с гантелями на одной ноге",
                "description": "Упражнение для повышения стабильности и активации ягодичных мышц.",
                "technique": "Держите гантель в одной руке, встаньте на одну ногу и выполните приседание, сохраняя баланс.",
                "difficulty": "advanced",
                "sets": 4,
                "reps": 8,
            },
        ]

        # Упражнения для средних и малых ягодичных мышц
        glutes_minor_exercises = [
            {
                "title": "Отведение ноги в кроссовере",
                "description": "Продвинутый вариант упражнения для изоляции средней ягодичной мышцы.",
                "technique": "Закрепите манжету кроссовера на лодыжке. Выполняйте отведение ноги в сторону, сохраняя контроль.",
                "difficulty": "advanced",
                "sets": 4,
                "reps": 12,
            },
            {
                "title": "Болгарские сплит-приседания",
                "description": "Сложное упражнение для проработки средней и малой ягодичной мышцы.",
                "technique": "Встаньте спиной к скамье, поставьте одну ногу на скамью, другую перед собой. Приседайте, сохраняя равновесие.",
                "difficulty": "advanced",
                "sets": 4,
                "reps": 10,
            },
            {
                "title": "Отведение ноги с утяжелителями",
                "description": "Упражнение с использованием утяжелителей для повышения нагрузки на малые ягодичные мышцы.",
                "technique": "Наденьте утяжелители на лодыжки. Выполняйте отведение ноги в сторону стоя или лежа на боку.",
                "difficulty": "advanced",
                "sets": 3,
                "reps": 15,
            },
            {
                "title": "Ягодичный мостик на одной ноге с весом",
                "description": "Продвинутый вариант упражнения для средней ягодичной мышцы.",
                "technique": "Лягте на спину, согните одну ногу в колене, другую вытяните. Положите гантель на бедра и поднимайте бедра вверх.",
                "difficulty": "advanced",
                "sets": 4,
                "reps": 10,
            },
            {
                "title": "Гиперэкстензия с весом",
                "description": "Добавление веса для увеличения нагрузки на ягодичные мышцы.",
                "technique": "Лягте на тренажер для гиперэкстензии, держите гантель или диск на груди. Поднимайте корпус вверх, акцентируя нагрузку на ягодицы.",
                "difficulty": "advanced",
                "sets": 4,
                "reps": 8,
            },
        ]

        # Добавление упражнений в базу данных
        for exercise_data in glutes_major_exercises:
            Exercise.objects.create(
                title=exercise_data["title"],
                description=exercise_data["description"],
                technique=exercise_data["technique"],
                muscle_group=glutes_major_group,
                difficulty=exercise_data["difficulty"],
                sets=exercise_data["sets"],
                reps=exercise_data["reps"],
            )

        for exercise_data in glutes_minor_exercises:
            Exercise.objects.create(
                title=exercise_data["title"],
                description=exercise_data["description"],
                technique=exercise_data["technique"],
                muscle_group=glutes_minor_group,
                difficulty=exercise_data["difficulty"],
                sets=exercise_data["sets"],
                reps=exercise_data["reps"],
            )

        self.stdout.write(
            self.style.SUCCESS("Упражнения для ягодиц успешно добавлены!")
        )
