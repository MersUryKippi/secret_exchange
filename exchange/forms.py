from django import forms
from .models import Secret, SecretWeight

class SecretForm(forms.Form):
    text = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 6, 'placeholder': 'Твой секрет...'}),
        label='Секрет',
        min_length=10,
        max_length=2000
    )
    weight = forms.ModelChoiceField(
        queryset=SecretWeight.objects.all().order_by('weight'),
        label='Уровень тяжести (1 — лёгкий, 5 — тяжёлый)'
    )