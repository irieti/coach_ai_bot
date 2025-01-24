from django.core.management.base import BaseCommand
from ...models import Exercise, MuscleGroup


class Command(BaseCommand):
    help = "Добавляет упражнения для рук в базу данных"

    def handle(self, *args, **options):
        self.add_arm_exercises()
        self.stdout.write(self.style.SUCCESS("Упражнения успешно добавлены!"))

    @staticmethod
    def add_arm_exercises():
        # Получаем или создаем группы мышц для рук
        biceps_group, _ = MuscleGroup.objects.get_or_create(name="Бицепсы")
        triceps_group, _ = MuscleGroup.objects.get_or_create(name="Трицепсы")
        deltoids_group, _ = MuscleGroup.objects.get_or_create(name="Дельтовидные")

        # Упражнения для бицепсов
        biceps_exercises = [
            {
                "title": "Подъем штанги на бицепс",
                "description": "Классическое упражнение для бицепсов, не требующее сложной техники.",
                "technique": "Поднимайте штангу к плечам, не двигая локтями. Затем медленно опустите.",
                "difficulty": "beginner",
                "sets": 3,
                "reps": 12,
            },
            {
                "title": "Подъем гантелей на бицепс",
                "description": "Упражнение для проработки бицепсов с использованием гантелей.",
                "technique": "Поднимайте гантели, сгибая локти и удерживая их неподвижными.",
                "difficulty": "beginner",
                "sets": 3,
                "reps": 12,
            },
            # Intermediate
            {
                "title": "Подъем штанги на бицепс с утяжелением",
                "description": "Базовое упражнение с дополнительным весом.",
                "technique": "Используйте штангу и поднимайте ее к плечам, удерживая локти неподвижно.",
                "difficulty": "intermediate",
                "sets": 4,
                "reps": 10,
            },
            {
                "title": "Концентрированный подъем на бицепс",
                "description": "Упражнение на проработку бицепсов с гантелью.",
                "technique": "Сядьте, поддерживайте локоть на бедре, поднимайте гантель вверх.",
                "difficulty": "intermediate",
                "sets": 3,
                "reps": 10,
            },
            # Advanced
            {
                "title": "Подъем на бицепс с EZ-штангой",
                "description": "Упражнение с EZ-штангой для снижения нагрузки на запястья.",
                "technique": "Поднимайте штангу, удерживая локти неподвижно, опускайте медленно.",
                "difficulty": "advanced",
                "sets": 4,
                "reps": 8,
            },
            {
                "title": "Подъем гантелей с супинацией",
                "description": "Дополнительное усложнение за счет разворота кистей.",
                "technique": "Начинайте с нейтрального хвата, поворачивайте кисти вверх в верхней точке.",
                "difficulty": "advanced",
                "sets": 4,
                "reps": 8,
            },
        ]

        # Упражнения для трицепсов
        triceps_exercises = [
            {
                "title": "Отжимания",
                "description": "Простой вариант отжиманий для проработки трицепсов.",
                "technique": "Опуститесь в положение отжимания, удерживайте локти вдоль тела.",
                "difficulty": "beginner",
                "sets": 3,
                "reps": 12,
            },
            {
                "title": "Французский жим с гантелями (лежа)",
                "description": "Изолированное упражнение для трицепсов.",
                "technique": "Лежа на скамье, опустите гантели за голову, затем верните их в исходное положение.",
                "difficulty": "beginner",
                "sets": 3,
                "reps": 12,
            },
            # Intermediate
            {
                "title": "Жим узким хватом",
                "description": "Сосредотачивает нагрузку на трицепсах.",
                "technique": "Держите штангу узким хватом, опустите к груди и выжмите вверх.",
                "difficulty": "intermediate",
                "sets": 4,
                "reps": 10,
            },
            {
                "title": "Разгибание рук на блоке",
                "description": "Используйте верхний блок для изоляции трицепсов.",
                "technique": "Разгибайте руки вниз, удерживая локти неподвижными.",
                "difficulty": "intermediate",
                "sets": 4,
                "reps": 10,
            },
            # Advanced
            {
                "title": "Отжимания на брусьях",
                "description": "Сложное упражнение, требующее хорошей физической подготовки.",
                "technique": "Опускайтесь медленно, удерживая локти вдоль тела, затем выжимайте вверх.",
                "difficulty": "advanced",
                "sets": 4,
                "reps": 8,
            },
            {
                "title": "Французский жим со штангой",
                "description": "Упражнение для опытных атлетов, требующее стабильного хвата.",
                "technique": "Опускайте штангу за голову и возвращайте в исходное положение.",
                "difficulty": "advanced",
                "sets": 4,
                "reps": 8,
            },
        ]

        # Упражнения для дельтовидных
        deltoids_exercises = [
            # Beginner
            {
                "title": "Жим гантелей сидя",
                "description": "Простое упражнение для плеч.",
                "technique": "Поднимайте гантели на уровне плеч и выжмите их вверх.",
                "difficulty": "beginner",
                "sets": 3,
                "reps": 12,
            },
            {
                "title": "Махи гантелями в стороны",
                "description": "Упражнение для проработки средней части плеч.",
                "technique": "Поднимайте гантели в стороны, удерживая локти немного согнутыми.",
                "difficulty": "beginner",
                "sets": 3,
                "reps": 12,
            },
            # Intermediate
            {
                "title": "Жим Арнольда",
                "description": "Сложное упражнение, включающее поворот кистей.",
                "technique": "Начните с гантелями перед лицом, вращайте их при подъеме вверх.",
                "difficulty": "intermediate",
                "sets": 4,
                "reps": 10,
            },
            {
                "title": "Тяга штанги к подбородку",
                "description": "Упражнение для развития передней и средней частей дельт.",
                "technique": "Держите штангу узким хватом и тяните ее вверх вдоль тела.",
                "difficulty": "intermediate",
                "sets": 4,
                "reps": 10,
            },
            # Advanced
            {
                "title": "Жим гантелей стоя",
                "description": "Упражнение для развития силы и стабилизации.",
                "technique": "Держите гантели на уровне плеч, выжимайте их вверх.",
                "difficulty": "advanced",
                "sets": 4,
                "reps": 8,
            },
            {
                "title": "Обратные махи в наклоне",
                "description": "Изолированное упражнение для задней части дельт.",
                "technique": "В наклоне поднимайте гантели в стороны, удерживая локти согнутыми.",
                "difficulty": "advanced",
                "sets": 4,
                "reps": 8,
            },
        ]

        # Функция для добавления упражнений
        def add_exercises_to_db(exercises, muscle_group):
            for exercise_data in exercises:
                Exercise.objects.get_or_create(
                    title=exercise_data["title"],
                    defaults={
                        "description": exercise_data["description"],
                        "technique": exercise_data["technique"],
                        "difficulty": exercise_data["difficulty"],
                        "sets": exercise_data["sets"],
                        "reps": exercise_data["reps"],
                        "muscle_group": muscle_group,
                    },
                )

        # Добавляем упражнения в базу данных
        add_exercises_to_db(biceps_exercises, biceps_group)
        add_exercises_to_db(triceps_exercises, triceps_group)
        add_exercises_to_db(deltoids_exercises, deltoids_group)
