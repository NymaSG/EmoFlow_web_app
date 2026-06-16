from collections import OrderedDict, defaultdict

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import RegisterForm
from .models import (
    ProgramBlock,
    ProgramDay,
    Exercise,
    ExerciseQuestion,
    UserAnswer,
    UserDayProgress,
    DiagnosticQuestion,
    DiagnosticAnswer,
    FinalDiagnosticQuestion,
    FinalDiagnosticAnswer,
    FinalDiagnosticResult,
)


def home(request):
    return render(request, "emotional_app/home.html")


def register(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)

        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Регистрация завершена. Добро пожаловать!")
            return redirect("dashboard")
    else:
        form = RegisterForm()

    return render(request, "emotional_app/register.html", {
        "form": form,
    })


def is_day_available(user, day):
    if day.number == 1:
        return True

    previous_day = ProgramDay.objects.filter(
        number=day.number - 1
    ).first()

    return UserDayProgress.objects.filter(
        user=user,
        day=previous_day,
        completed=True
    ).exists()


@login_required
def dashboard(request):
    POINTS_PER_DAY = 50

    blocks = ProgramBlock.objects.prefetch_related("days").all()

    completed_days = set(
        UserDayProgress.objects.filter(
            user=request.user,
            completed=True
        ).values_list("day__number", flat=True)
    )

    total_days = ProgramDay.objects.count()
    completed_count = len(completed_days)

    available_day = 1

    if completed_days:
        available_day = min(max(completed_days) + 1, total_days)

    total_points = completed_count * POINTS_PER_DAY
    max_points = total_days * POINTS_PER_DAY if total_days else POINTS_PER_DAY
    progress_percent = round((completed_count / total_days) * 100) if total_days else 0

    chart_days = []

    for day in ProgramDay.objects.all().order_by("number"):
        is_completed = day.number in completed_days
        is_available = day.number == available_day

        chart_days.append({
            "number": day.number,
            "title": day.title,
            "completed": is_completed,
            "available": is_available,
            "points": POINTS_PER_DAY if is_completed else 0,
            "height": 100 if is_completed else 18,
        })

    return render(request, "emotional_app/dashboard.html", {
        "blocks": blocks,
        "completed_days": completed_days,
        "available_day": available_day,
        "total_days": total_days,
        "completed_count": completed_count,
        "total_points": total_points,
        "max_points": max_points,
        "progress_percent": progress_percent,
        "points_per_day": POINTS_PER_DAY,
        "chart_days": chart_days,
    })


@login_required
def day_detail(request, day_number):
    day = get_object_or_404(
        ProgramDay.objects.prefetch_related("exercises"),
        number=day_number
    )

    if not is_day_available(request.user, day):
        messages.warning(request, "Этот день откроется после завершения предыдущего дня.")
        return redirect("dashboard")

    progress_obj, _ = UserDayProgress.objects.get_or_create(
        user=request.user,
        day=day
    )

    exercises = day.exercises.all().order_by("order", "id")

    answers = UserAnswer.objects.filter(
        user=request.user,
        question__exercise__day=day
    )

    answered_question_ids = set(
        answers.values_list("question_id", flat=True)
    )

    return render(request, "emotional_app/day_detail.html", {
        "day": day,
        "exercises": exercises,
        "progress": progress_obj,
        "answered_question_ids": answered_question_ids,
    })


@login_required
def exercise_detail(request, exercise_id):
    exercise = get_object_or_404(
        Exercise.objects.select_related("day"),
        id=exercise_id
    )

    if not is_day_available(request.user, exercise.day):
        messages.warning(request, "Это упражнение пока недоступно.")
        return redirect("dashboard")

    questions = exercise.questions.all().order_by("order")

    existing_answers = {
        answer.question_id: answer.value
        for answer in UserAnswer.objects.filter(
            user=request.user,
            question__in=questions
        )
    }

    if request.method == "POST":
        has_errors = False

        for question in questions:
            if question.question_type == "info":
                continue

            field_name = f"q_{question.id}"

            if question.question_type == "multiselect":
                selected_values = request.POST.getlist(field_name)
                selected_values = [
                    value.strip()
                    for value in selected_values
                    if value.strip()
                ]
                value = "; ".join(selected_values)
            else:
                value = request.POST.get(field_name, "").strip()

            if question.question_type == "select" and value == "Другое":
                other_value = request.POST.get(
                    f"q_other_{question.id}",
                    ""
                ).strip()

                if other_value:
                    value = f"Другое: {other_value}"

            if question.required and not value:
                has_errors = True
                messages.error(
                    request,
                    "Заполните все обязательные поля перед переходом дальше."
                )
                break

            UserAnswer.objects.update_or_create(
                user=request.user,
                question=question,
                defaults={
                    "value": value,
                }
            )

        if not has_errors:
            next_exercise = Exercise.objects.filter(
                day=exercise.day,
                order__gt=exercise.order
            ).order_by("order").first()

            if next_exercise:
                return redirect(
                    "exercise_detail",
                    exercise_id=next_exercise.id
                )

            progress_obj, _ = UserDayProgress.objects.get_or_create(
                user=request.user,
                day=exercise.day
            )

            progress_obj.completed = True
            progress_obj.completed_at = timezone.now()
            progress_obj.save()

            messages.success(
                request,
                "День завершен. Спасибо за выполнение упражнений!"
            )

            # После 21-го дня открывается новая итоговая диагностика.
            # После 14-го дня диагностика больше не открывается.
            if exercise.day.number == 21:
                return redirect("final_diagnostic")

            return redirect("dashboard")

    return render(request, "emotional_app/exercise_detail.html", {
        "exercise": exercise,
        "questions": questions,
        "existing_answers": existing_answers,
    })


@login_required
def diagnostic(request, day_number):
    """
    Старая диагностика.
    Сейчас переходы к ней убраны, но функцию можно оставить,
    чтобы не ломать старые ссылки или маршрут diagnostic/<day_number>/.
    """
    if day_number not in [14, 21]:
        return redirect("dashboard")

    questions = DiagnosticQuestion.objects.all()

    previous = {
        answer.question_id: answer.score
        for answer in DiagnosticAnswer.objects.filter(
            user=request.user,
            day_number=day_number
        )
    }

    result = None

    if request.method == "POST":
        total = 0

        for question in questions:
            score = int(request.POST.get(f"q_{question.id}", "0"))

            if score < 1 or score > 5:
                messages.error(request, "Ответьте на все вопросы диагностики.")
                return redirect("diagnostic", day_number=day_number)

            saved_score = 6 - score if question.reverse_score else score
            total += saved_score

            DiagnosticAnswer.objects.update_or_create(
                user=request.user,
                question=question,
                day_number=day_number,
                defaults={
                    "score": score,
                }
            )

        max_score = questions.count() * 5
        percent = round(total / max_score * 100) if max_score else 0

        result = {
            "total": total,
            "max": max_score,
            "percent": percent,
        }

    return render(request, "emotional_app/diagnostic.html", {
        "questions": questions,
        "day_number": day_number,
        "previous": previous,
        "result": result,
    })


@login_required
def progress(request):
    POINTS_PER_DAY = 50

    completed_days = set(
        UserDayProgress.objects.filter(
            user=request.user,
            completed=True
        ).values_list("day__number", flat=True)
    )

    total_days = ProgramDay.objects.count()
    completed_count = len(completed_days)

    progress_percent = round((completed_count / total_days) * 100) if total_days else 0
    total_points = completed_count * POINTS_PER_DAY
    max_points = total_days * POINTS_PER_DAY if total_days else 0

    recent_answers = UserAnswer.objects.filter(
        user=request.user
    ).select_related(
        "question",
        "question__exercise",
        "question__exercise__day"
    ).order_by("-id")[:12]

    chart_days = []

    for day in ProgramDay.objects.all().order_by("number"):
        chart_days.append({
            "number": day.number,
            "title": day.title,
            "completed": day.number in completed_days,
        })

    return render(request, "emotional_app/progress.html", {
        "completed_days": completed_days,
        "completed_count": completed_count,
        "total_days": total_days,
        "progress_percent": progress_percent,
        "total_points": total_points,
        "max_points": max_points,
        "points_per_day": POINTS_PER_DAY,
        "recent_answers": recent_answers,
        "chart_days": chart_days,
    })


@login_required
def final_diagnostic(request):
    questions = FinalDiagnosticQuestion.objects.all().order_by("order")

    previous_answers = {
        answer.question_id: answer.value
        for answer in FinalDiagnosticAnswer.objects.filter(
            user=request.user,
            question__in=questions
        )
    }

    if request.method == "POST":
        has_errors = False

        for question in questions:
            field_name = f"q_{question.id}"
            raw_value = request.POST.get(field_name)

            if raw_value is None or raw_value == "":
                has_errors = True
                messages.error(request, "Ответьте на все вопросы итоговой диагностики.")
                break

            try:
                value = int(raw_value)
            except ValueError:
                has_errors = True
                messages.error(request, "Некорректное значение ответа.")
                break

            if value < question.scale_min or value > question.scale_max:
                has_errors = True
                messages.error(request, "Ответ находится вне допустимой шкалы.")
                break

            FinalDiagnosticAnswer.objects.update_or_create(
                user=request.user,
                question=question,
                defaults={
                    "value": value,
                }
            )

        if not has_errors:
            result_data = calculate_final_diagnostic(request.user)
            conclusion = build_final_conclusion(result_data)

            FinalDiagnosticResult.objects.update_or_create(
                user=request.user,
                defaults={
                    "results": result_data,
                    "conclusion": conclusion,
                }
            )

            messages.success(request, "Итоговая диагностика завершена.")
            return redirect("final_diagnostic_result")

    method_meta = {
        "wellbeing": {
            "title": "Методика диагностики субъективного благополучия",
            "author": "Р. М. Шамионов, Т. В. Бескова",
        },
        "erq": {
            "title": "Опросник эмоциональной регуляции ERQ",
            "author": "Дж. Гросс",
        },
        "ecv": {
            "title": "Ценности эмоционального контроля ECV",
            "author": "А. Маусс",
        },
        "srspm": {
            "title": "Стиль саморегуляции поведения ССПМ-2020",
            "author": "В. И. Моросанова",
        },
        "fivepfq": {
            "title": "Пятифакторный опросник личности 5PFQ",
            "author": "Хийджиро Тсуйи",
        },
    }

    grouped_questions = OrderedDict()

    for question in questions:
        if question.method_code not in grouped_questions:
            meta = method_meta.get(question.method_code, {
                "title": question.method_name,
                "author": "",
            })

            grouped_questions[question.method_code] = {
                "method_title": meta["title"],
                "method_author": meta["author"],
                "questions": []
            }

        grouped_questions[question.method_code]["questions"].append(question)

    return render(request, "emotional_app/final_diagnostic.html", {
        "grouped_questions": grouped_questions,
        "previous_answers": previous_answers,
    })


@login_required
def final_diagnostic_result(request):
    result_obj = FinalDiagnosticResult.objects.filter(
        user=request.user
    ).order_by("-updated_at").first()

    if not result_obj:
        messages.info(request, "Сначала пройдите итоговую диагностику.")
        return redirect("final_diagnostic")

    conclusion_sections = build_final_conclusion_sections(result_obj.results)

    return render(request, "emotional_app/final_diagnostic_result.html", {
        "result_obj": result_obj,
        "short_summary": conclusion_sections["short_summary"],
        "detail_paragraphs": conclusion_sections["detail_paragraphs"],
        "final_note": conclusion_sections["final_note"],
    })


def calculate_final_diagnostic(user):
    answers = FinalDiagnosticAnswer.objects.filter(
        user=user
    ).select_related("question")

    scores = defaultdict(int)

    for answer in answers:
        question = answer.question
        value = answer.value

        # Для 5PFQ шкала -2..2 переводится в 1..5,
        # чтобы итоговый показатель был положительным.
        if question.scale_min == -2 and question.scale_max == 2:
            value_for_sum = value + 3
        else:
            value_for_sum = value

        if question.reverse_score:
            if question.scale_min == -2 and question.scale_max == 2:
                value_for_sum = 6 - value_for_sum
            else:
                value_for_sum = question.scale_max + question.scale_min - value_for_sum

        scores[question.criterion] += value_for_sum

        # Для 5PFQ общий показатель должен учитывать все 75 вопросов.
        # Если вопрос относится к эмоциональной стабильности,
        # он всё равно дополнительно входит в общий 5PFQ-показатель.
        if question.method_code == "fivepfq" and question.criterion != "fivepfq_total":
            scores["fivepfq_total"] += value_for_sum

    result = {}

    result["wellbeing"] = interpret_wellbeing(scores["wellbeing"])
    result["erq_reappraisal"] = interpret_reappraisal(scores["erq_reappraisal"])
    result["erq_suppression"] = interpret_suppression(scores["erq_suppression"])
    result["ecv"] = interpret_ecv(scores["ecv"])
    result["srspm_total"] = interpret_srspm(scores["srspm_total"])
    result["fivepfq_emotional_stability"] = interpret_5pfq_stability(
        scores["fivepfq_emotional_stability"]
    )
    result["fivepfq_total"] = interpret_5pfq_total(scores["fivepfq_total"])

    return result


def make_result(title, score, level, description):
    return {
        "title": title,
        "score": score,
        "level": level,
        "description": description,
    }


def interpret_wellbeing(score):
    if score <= 79:
        return make_result(
            "Субъективное благополучие",
            score,
            "Низкий уровень",
            "По результатам диагностики может наблюдаться сниженное ощущение удовлетворенности жизнью, недостаток эмоциональных ресурсов или преобладание напряжения. Это можно рассматривать как зону поддержки и постепенного восстановления саморегуляции."
        )

    if score <= 124:
        return make_result(
            "Субъективное благополучие",
            score,
            "Средний уровень",
            "Результаты могут говорить о том, что удовлетворенность отдельными сторонами жизни в целом сохраняется, однако эмоциональное состояние и ощущение внутренних ресурсов могут быть неустойчивыми."
        )

    return make_result(
        "Субъективное благополучие",
        score,
        "Высокий уровень",
        "Результаты отражают выраженное ощущение удовлетворенности жизнью, наличие позитивного эмоционального фона и внутренних ресурсов, которые могут поддерживать продуктивную переработку негативных эмоциональных состояний."
    )


def interpret_reappraisal(score):
    if score <= 18:
        return make_result(
            "Когнитивная переоценка",
            score,
            "Низкий уровень",
            "Навык когнитивной переоценки может использоваться редко или неустойчиво. В эмоционально значимых ситуациях человеку может быть сложно изменить взгляд на происходящее и найти альтернативное объяснение ситуации."
        )

    if score <= 30:
        return make_result(
            "Когнитивная переоценка",
            score,
            "Средний уровень",
            "Навык когнитивной переоценки сформирован частично. Человек может переосмысливать ситуацию в отдельных случаях, однако в стрессовых обстоятельствах может нуждаться в дополнительных вопросах, подсказках или упражнениях."
        )

    return make_result(
        "Когнитивная переоценка",
        score,
        "Высокий уровень",
        "Когнитивная переоценка достаточно часто используется как способ эмоциональной регуляции. Это помогает искать другой угол зрения, снижать субъективную напряженность и выбирать более адаптивное объяснение происходящего."
    )


def interpret_suppression(score):
    if score >= 20:
        return make_result(
            "Эмоциональное подавление",
            score,
            "Низкий уровень сформированности навыка",
            "Высокая выраженность эмоционального подавления может указывать на склонность скрывать или сдерживать эмоциональные проявления. Это не является негативной оценкой личности, но может быть зоной развития более гибких способов выражения и переработки переживаний."
        )

    if score >= 12:
        return make_result(
            "Эмоциональное подавление",
            score,
            "Средний уровень",
            "Подавление эмоций может использоваться ситуативно. В одних обстоятельствах человек способен выражать эмоции, а в других — сдерживает их. Важно различать адаптивное сдерживание и привычное избегание эмоционального опыта."
        )

    return make_result(
        "Эмоциональное подавление",
        score,
        "Высокий уровень сформированности навыка",
        "Низкий показатель подавления может говорить о большей готовности вступать в контакт со своим эмоциональным опытом, не блокировать его автоматически и использовать более открытые способы переработки переживаний."
    )


def interpret_ecv(score):
    if score <= 39:
        return make_result(
            "Ценность эмоционального контроля",
            score,
            "Низкая выраженность",
            "Эмоциональный контроль может восприниматься как недостаточно значимый способ саморегуляции. В некоторых ситуациях это может затруднять осознанное управление интенсивностью и выражением эмоций."
        )

    if score <= 84:
        return make_result(
            "Ценность эмоционального контроля",
            score,
            "Умеренная / оптимальная выраженность",
            "Умеренная выраженность ценности эмоционального контроля является наиболее благоприятной. Она показывает, что человек признает важность управления эмоциями, но не обязательно стремится к их жесткому подавлению."
        )

    return make_result(
        "Ценность эмоционального контроля",
        score,
        "Высокая выраженность",
        "Высокая ориентация на эмоциональный контроль может говорить о стремлении сильно контролировать переживания. Само по себе это не является отрицательным результатом, однако при сочетании с подавлением может указывать на риск чрезмерного контроля."
    )


def interpret_srspm(score):
    # 28 вопросов, шкала 1–5, диапазон 28–140.
    if score <= 65:
        return make_result(
            "Стиль саморегуляции поведения",
            score,
            "Низкий уровень",
            "Результат может указывать на трудности планирования, программирования действий, оценки результатов или сохранения устойчивости поведения при эмоциональном напряжении. Это может быть зоной дальнейшего развития саморегуляции."
        )

    if score <= 103:
        return make_result(
            "Стиль саморегуляции поведения",
            score,
            "Средний уровень",
            "Саморегуляция поведения выражена умеренно. Отдельные компоненты регуляции могут быть сформированы, однако в стрессовых ситуациях человеку может требоваться дополнительная опора на план, внешнюю структуру или специальные упражнения."
        )

    return make_result(
        "Стиль саморегуляции поведения",
        score,
        "Высокий уровень",
        "Результат отражает более выраженную способность планировать действия, оценивать результаты, адаптироваться к изменениям и сохранять продуктивность поведения даже при эмоциональном напряжении."
    )


def interpret_5pfq_stability(score):
    # 15 вопросов эмоциональной стабильности из 5PFQ.
    # После перевода -2..2 в 1..5 диапазон 15–75.
    if score <= 34:
        return make_result(
            "Эмоциональная стабильность",
            score,
            "Низкий уровень",
            "Результат может отражать повышенную эмоциональную чувствительность, более выраженную реактивность на стресс или трудности восстановления после напряжения. Это можно рассматривать как зону развития эмоциональной устойчивости."
        )

    if score <= 55:
        return make_result(
            "Эмоциональная стабильность",
            score,
            "Средний уровень",
            "Эмоциональная устойчивость выражена умеренно. В сложных ситуациях могут возникать колебания настроения или потребность в дополнительных стратегиях эмоциональной регуляции."
        )

    return make_result(
        "Эмоциональная стабильность",
        score,
        "Высокий уровень",
        "Результат отражает способность сохранять относительное эмоциональное равновесие и восстанавливаться после стрессовых ситуаций. Это является ресурсом продуктивной переработки негативных эмоциональных состояний."
    )


def interpret_5pfq_total(score):
    # 75 вопросов, после перевода -2..2 в 1..5 диапазон 75–375.
    if score <= 174:
        return make_result(
            "Пятифакторный опросник личности",
            score,
            "Низкая выраженность интегрального показателя",
            "Личностный профиль может требовать дополнительного анализа по отдельным особенностям поведения, эмоциональности и взаимодействия с окружающими. В рамках приложения этот показатель используется как дополнительный контекст."
        )

    if score <= 274:
        return make_result(
            "Пятифакторный опросник личности",
            score,
            "Средняя выраженность интегрального показателя",
            "Результат отражает умеренную выраженность личностных особенностей, связанных с поведением, эмоциональностью, саморегуляцией и взаимодействием с окружающими."
        )

    return make_result(
        "Пятифакторный опросник личности",
        score,
        "Высокая выраженность интегрального показателя",
        "Результат отражает выраженность ряда личностных характеристик. Его следует рассматривать как дополнительный контекст к показателям эмоциональной регуляции, благополучия и саморегуляции поведения."
    )


def build_final_conclusion(result_data):
    high_count = 0
    medium_count = 0
    low_count = 0

    detail_paragraphs = []

    for item in result_data.values():
        level = item["level"].lower()

        if "высок" in level or "оптимальная" in level:
            high_count += 1
        elif "сред" in level or "умеренная" in level:
            medium_count += 1
        else:
            low_count += 1

        detail_paragraphs.append(item["description"])

    if high_count >= 4:
        main_text = (
            "По итогам диагностики можно говорить о достаточно выраженной сформированности "
            "навыков продуктивной психологической переработки негативных эмоциональных состояний. "
            "Результаты показывают, что пользователь в целом способен замечать свои эмоции, "
            "анализировать их, использовать более гибкие способы саморегуляции и восстанавливаться "
            "после эмоционального напряжения."
        )
    elif medium_count >= 4:
        main_text = (
            "По итогам диагностики можно говорить о частично сформированных навыках продуктивной "
            "психологической переработки негативных эмоциональных состояний. У пользователя уже есть "
            "отдельные ресурсы эмоциональной саморегуляции, однако некоторые навыки могут оставаться "
            "зоной дальнейшего развития и требуют регулярного закрепления."
        )
    else:
        main_text = (
            "По итогам диагностики можно говорить о том, что навыки продуктивной психологической "
            "переработки негативных эмоциональных состояний находятся в стадии формирования. "
            "Пользователю может быть полезно продолжать работу с упражнениями, уделяя внимание "
            "осознанию эмоций, их описанию, переоценке ситуаций и более бережному отношению к своим переживаниям."
        )

    detail_intro = (
        "Более подробная расшифровка результатов позволяет выделить несколько важных особенностей:"
    )

    detail_text = "\n\n".join(detail_paragraphs)

    final_note = (
        "Данное заключение не является клинической оценкой. Его следует рассматривать как ориентир, "
        "который помогает увидеть сильные стороны, зоны развития и возможные направления дальнейшей "
        "самостоятельной работы с эмоциональными состояниями."
    )

    return (
        f"{main_text}\n\n"
        f"{detail_intro}\n\n"
        f"{detail_text}\n\n"
        f"{final_note}"
    )
    
def build_final_conclusion_sections(result_data):
    high_count = 0
    medium_count = 0
    low_count = 0

    detail_paragraphs = []

    for item in result_data.values():
        level = item["level"].lower()

        if "высок" in level or "оптимальная" in level:
            high_count += 1
        elif "сред" in level or "умеренная" in level:
            medium_count += 1
        else:
            low_count += 1

        detail_paragraphs.append(item["description"])

    if high_count >= 4:
        short_summary = (
            "По итогам диагностики можно говорить о достаточно выраженной сформированности "
            "навыков продуктивной психологической переработки негативных эмоциональных состояний. "
            "Результаты показывают, что пользователь в целом способен замечать свои эмоции, "
            "анализировать их, использовать более гибкие способы саморегуляции и восстанавливаться "
            "после эмоционального напряжения."
        )
    elif medium_count >= 4:
        short_summary = (
            "По итогам диагностики можно говорить о частично сформированных навыках продуктивной "
            "психологической переработки негативных эмоциональных состояний. У пользователя уже есть "
            "отдельные ресурсы эмоциональной саморегуляции, однако некоторые навыки могут оставаться "
            "зоной дальнейшего развития и требуют регулярного закрепления."
        )
    else:
        short_summary = (
            "По итогам диагностики можно говорить о том, что навыки продуктивной психологической "
            "переработки негативных эмоциональных состояний находятся в стадии формирования. "
            "Пользователю может быть полезно продолжать работу с упражнениями, уделяя внимание "
            "осознанию эмоций, их описанию, переоценке ситуаций и более бережному отношению к своим переживаниям."
        )

    final_note = (
        "Данное заключение не является клинической оценкой. Его следует рассматривать как ориентир, "
        "который помогает увидеть сильные стороны, зоны развития и возможные направления дальнейшей "
        "самостоятельной работы с эмоциональными состояниями."
    )

    return {
        "short_summary": short_summary,
        "detail_paragraphs": detail_paragraphs,
        "final_note": final_note,
    }