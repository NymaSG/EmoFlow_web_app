from django.conf import settings
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User

class UserProfile(models.Model):
    GENDER_CHOICES = [('M', 'Мужской'), ('F', 'Женский')]
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    phone_or_email = models.CharField('Почта или телефон', max_length=150)
    gender = models.CharField('Пол', max_length=1, choices=GENDER_CHOICES)

    def __str__(self):
        return self.user.get_full_name() or self.user.username

class ProgramBlock(models.Model):
    title = models.CharField('Название блока', max_length=200)
    description = models.TextField('Описание', blank=True)
    order = models.PositiveIntegerField('Порядок', unique=True)

    class Meta:
        ordering = ['order']
        verbose_name = 'Блок программы'
        verbose_name_plural = 'Блоки программы'

    def __str__(self):
        return self.title

class ProgramDay(models.Model):
    block = models.ForeignKey(ProgramBlock, on_delete=models.CASCADE, related_name='days')
    number = models.PositiveIntegerField('День', unique=True)
    title = models.CharField('Название дня', max_length=200)
    intro_text = models.TextField('Пояснение дня', blank=True)

    class Meta:
        ordering = ['number']
        verbose_name = 'День программы'
        verbose_name_plural = 'Дни программы'

    def __str__(self):
        return f'День {self.number}. {self.title}'

class Exercise(models.Model):
    day = models.ForeignKey(ProgramDay, on_delete=models.CASCADE, related_name='exercises')
    title = models.CharField('Название упражнения', max_length=200)
    description = models.TextField('Инструкция')
    order = models.PositiveIntegerField('Порядок')
    exercise_type = models.CharField('Тип', max_length=50, default='text')
    timer_seconds = models.PositiveIntegerField('Таймер в секундах', default=0)
    button_text = models.CharField('Текст кнопки', max_length=80, default='Далее')

    class Meta:
        ordering = ['day__number', 'order']
        unique_together = ['day', 'order']
        verbose_name = 'Упражнение'
        verbose_name_plural = 'Упражнения'

    def __str__(self):
        return f'{self.day}: {self.title}'

class ExerciseQuestion(models.Model):
    QUESTION_TYPES = [
        ('text', 'Текстовое поле'),
        ('textarea', 'Большое текстовое поле'),
        ('select', 'Список'),
        ('multiselect', 'Множественный выбор'),
        ('scale', 'Шкала'),
        ('info', 'Информационный блок'),
    ]
    exercise = models.ForeignKey(Exercise, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField('Вопрос/текст')
    question_type = models.CharField('Тип вопроса', max_length=20, choices=QUESTION_TYPES, default='textarea')
    options = models.TextField('Варианты через точку с запятой', blank=True)
    required = models.BooleanField('Обязательное', default=True)
    order = models.PositiveIntegerField('Порядок')
    scale_min = models.IntegerField('Минимум шкалы', default=1)
    scale_max = models.IntegerField('Максимум шкалы', default=10)
    scale_default = models.IntegerField('Значение по умолчанию', default=5)
    
    
    def get_options(self):
        if not self.options:
            return []

        separators = ["|", ";", ","]

        for separator in separators:
            if separator in self.options:
                return [
                    option.strip()
                    for option in self.options.split(separator)
                    if option.strip()
                ]

        return [self.options.strip()]
    

    class Meta:
        ordering = ['exercise__day__number', 'exercise__order', 'order']
        unique_together = ['exercise', 'order']
        verbose_name = 'Вопрос упражнения'
        verbose_name_plural = 'Вопросы упражнений'

    def option_list(self):
        return [item.strip() for item in self.options.split(';') if item.strip()]

class UserAnswer(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(ExerciseQuestion, on_delete=models.CASCADE, related_name='answers')
    value = models.TextField('Ответ')
    updated_at = models.DateTimeField('Обновлено', auto_now=True)
    created_at = models.DateTimeField('Создано', auto_now_add=True)

    class Meta:
        unique_together = ['user', 'question']
        verbose_name = 'Ответ пользователя'
        verbose_name_plural = 'Ответы пользователей'

class UserDayProgress(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='day_progress')
    day = models.ForeignKey(ProgramDay, on_delete=models.CASCADE, related_name='progress')
    completed = models.BooleanField('Завершен', default=False)
    completed_at = models.DateTimeField('Дата завершения', null=True, blank=True)

    class Meta:
        unique_together = ['user', 'day']
        verbose_name = 'Прогресс по дню'
        verbose_name_plural = 'Прогресс по дням'

    def mark_completed(self):
        self.completed = True
        self.completed_at = timezone.now()
        self.save()

class DiagnosticQuestion(models.Model):
    text = models.TextField('Вопрос')
    reverse_score = models.BooleanField('Обратная шкала', default=False)
    order = models.PositiveIntegerField('Порядок')

    class Meta:
        ordering = ['order']
        verbose_name = 'Вопрос диагностики'
        verbose_name_plural = 'Вопросы диагностики'

class DiagnosticAnswer(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='diagnostic_answers')
    question = models.ForeignKey(DiagnosticQuestion, on_delete=models.CASCADE)
    day_number = models.PositiveIntegerField('День диагностики', default=14)
    score = models.PositiveIntegerField('Оценка')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'question', 'day_number']
        verbose_name = 'Ответ диагностики'
        verbose_name_plural = 'Ответы диагностики'
        
class FinalDiagnosticQuestion(models.Model):
    METHOD_CHOICES = [
        ("wellbeing", "Методика диагностики субъективного благополучия"),
        ("erq", "Опросник эмоциональной регуляции ERQ"),
        ("ecv", "Ценности эмоционального контроля ECV"),
        ("srspm", "Стиль саморегуляции поведения ССПМ-2020"),
        ("fivepfq", "Пятифакторный опросник личности 5PFQ"),
    ]

    CRITERION_CHOICES = [
        ("wellbeing", "Субъективное благополучие"),
        ("erq_reappraisal", "Когнитивная переоценка"),
        ("erq_suppression", "Эмоциональное подавление"),
        ("ecv", "Ценность эмоционального контроля"),
        ("srspm_total", "Стиль саморегуляции поведения"),
        ("fivepfq_total", "Пятифакторный опросник личности"),
        ("fivepfq_emotional_stability", "Эмоциональная стабильность"),
    ]

    method_code = models.CharField(max_length=50, choices=METHOD_CHOICES)
    method_name = models.CharField(max_length=255)
    criterion = models.CharField(max_length=80, choices=CRITERION_CHOICES)

    text = models.TextField()

    # Для обычных шкал: 1–5, 1–7, 0–10.
    # Для 5PFQ: -2..2.
    scale_min = models.IntegerField(default=1)
    scale_max = models.IntegerField(default=5)

    # Для 5PFQ, где вопрос состоит из двух противоположных высказываний.
    left_text = models.TextField(blank=True)
    right_text = models.TextField(blank=True)

    reverse_score = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.method_name} — {self.text[:60]}"

    def get_scale_values(self):
        return list(range(self.scale_min, self.scale_max + 1))


class FinalDiagnosticAnswer(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    question = models.ForeignKey(FinalDiagnosticQuestion, on_delete=models.CASCADE)
    value = models.IntegerField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "question")

    def __str__(self):
        return f"{self.user.username} — {self.question_id}: {self.value}"


class FinalDiagnosticResult(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    results = models.JSONField(default=dict)
    conclusion = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Итоговая диагностика — {self.user.username}"