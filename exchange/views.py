from django.shortcuts import render, redirect
from .forms import SecretForm
from .models import Secret, SecretWeight
import hashlib

def submit_page(request):
    if request.method == 'POST':
        form = SecretForm(request.POST)
        if form.is_valid():
            text = form.cleaned_data['text']
            weight = form.cleaned_data['weight']
            
            # Проверка на дубликат
            content_hash = hashlib.sha256(text.encode()).hexdigest()
            if Secret.objects.filter(content_hash=content_hash).exists():
                form.add_error('text', 'Такой секрет уже существует.')
                return render(request, 'submit.html', {'form': form})
            
            # Получаем или создаём сессию
            if not request.session.session_key:
                request.session.create()
            session_key = request.session.session_key
            
            # Создаём и шифруем секрет
            secret = Secret(owner_session_key=session_key, weight=weight)
            secret.save_text(text)
            secret.save()
            
            return redirect('/submit/success/')
    else:
        form = SecretForm()
    return render(request, 'submit.html', {'form': form})

def submit_success(request):
    return render(request, 'submit_success.html')

def index(request):
    return render(request, 'index.html')

def secret_list(request):
    weights = SecretWeight.objects.all().order_by('weight')
    return render(request, 'secret_list.html', {'weights': weights})

def weight_detail(request, pk):
    weight = SecretWeight.objects.get(id=pk)
    count = Secret.objects.filter(weight=weight).count()
    return render(request, 'weight_detail.html', {'weight': weight, 'count': count})