from django.contrib import admin
from .models import (
    UserProfile, ProgramBlock, ProgramDay, Exercise, ExerciseQuestion,
    UserAnswer, UserDayProgress, DiagnosticQuestion, DiagnosticAnswer
)

class ExerciseQuestionInline(admin.TabularInline):
    model = ExerciseQuestion
    extra = 1

@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display = ('title', 'day', 'order', 'exercise_type')
    list_filter = ('day__block', 'day')
    inlines = [ExerciseQuestionInline]

@admin.register(ProgramDay)
class ProgramDayAdmin(admin.ModelAdmin):
    list_display = ('number', 'title', 'block')
    list_filter = ('block',)

admin.site.register(UserProfile)
admin.site.register(ProgramBlock)
admin.site.register(UserAnswer)
admin.site.register(UserDayProgress)
admin.site.register(DiagnosticQuestion)
admin.site.register(DiagnosticAnswer)
