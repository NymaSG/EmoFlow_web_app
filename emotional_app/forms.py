from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import UserProfile

class RegisterForm(UserCreationForm):
    first_name = forms.CharField(label='Имя', max_length=100)
    contact = forms.CharField(label='Почта', max_length=150)
    gender = forms.ChoiceField(label='Пол', choices=UserProfile.GENDER_CHOICES)

    class Meta:
        model = User
        fields = ('first_name', 'contact', 'gender', 'password1', 'password2')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['contact']
        user.first_name = self.cleaned_data['first_name']
        if '@' in self.cleaned_data['contact']:
            user.email = self.cleaned_data['contact']
        if commit:
            user.save()
            UserProfile.objects.create(
                user=user,
                phone_or_email=self.cleaned_data['contact'],
                gender=self.cleaned_data['gender']
            )
        return user
