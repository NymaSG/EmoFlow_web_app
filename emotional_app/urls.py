from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('program/', views.dashboard, name='program'),
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='emotional_app/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('day/<int:day_number>/', views.day_detail, name='day_detail'),
    path('exercise/<int:exercise_id>/', views.exercise_detail, name='exercise_detail'),
    path('progress/', views.progress, name='progress'),
    path('final-diagnostic/', views.final_diagnostic, name='final_diagnostic'),
    path('final-diagnostic/result/', views.final_diagnostic_result, name='final_diagnostic_result'),
]
