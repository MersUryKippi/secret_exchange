from django.shortcuts import render, redirect
from .forms import SecretForm
from .models import Secret, SecretWeight
import hashlib
from django.http import Http404
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from .models import Exchange, Message

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

def get_or_create_session(request):
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key

def my_secrets(request):
    session_key = get_or_create_session(request)
    secrets = Secret.objects.filter(owner_session_key=session_key).order_by('-created_at')
    return render(request, 'my_secrets.html', {'secrets': secrets})

def delete_secret(request, pk):
    session_key = get_or_create_session(request)
    try:
        secret = Secret.objects.get(id=pk, owner_session_key=session_key)
    except Secret.DoesNotExist:
        raise Http404("Секрет не найден или не принадлежит тебе")
    
    if request.method == 'POST':
        secret.delete()
        return redirect('/my/')
    return render(request, 'confirm_delete.html', {'secret': secret})

def do_exchange(request):
    session_key = get_or_create_session(request)
    
    # Проверяем, есть ли у пользователя свой секрет без обмена
    my_secret = Secret.objects.filter(
        owner_session_key=session_key,
        exchange__isnull=True
    ).first()
    
    if not my_secret:
        return render(request, 'exchange_no_secret.html')
    
    try:
        with transaction.atomic():
            # SELECT FOR UPDATE — блокируем строку от race condition
            partner_secret = Secret.objects.select_for_update().filter(
                exchange__isnull=True,
                weight__weight__gte=my_secret.weight.weight - 1,
                weight__weight__lte=my_secret.weight.weight + 1,
            ).exclude(owner_session_key=session_key).first()
            
            if not partner_secret:
                return render(request, 'exchange_wait.html')
            
            # Создаём обмен
            ex = Exchange.objects.create(
                participant1_session_key=session_key,
                participant2_session_key=partner_secret.owner_session_key,
                chat_delete_at=timezone.now() + timedelta(hours=1)
            )
            my_secret.exchange = ex
            my_secret.save()
            partner_secret.exchange = ex
            partner_secret.save()
            
            # Расшифровываем и передаём текст
            received_text = partner_secret.get_text()
            
            # Уничтожаем ключ партнёра после показа
            partner_secret.encryption_key = ''
            partner_secret.save()
            
    except Exception as e:
        return render(request, 'exchange_error.html', {'error': str(e)})
    
    return render(request, 'exchange_result.html', {
        'received_text': received_text,
        'exchange': ex
    })

def burn_secret(request, exchange_id):
    if request.method == 'POST':
        session_key = get_or_create_session(request)
        try:
            ex = Exchange.objects.get(id=exchange_id)
            # Удаляем секрет партнёра (тот, что получил текущий пользователь)
            Secret.objects.filter(
                exchange=ex
            ).exclude(owner_session_key=session_key).update(
                encrypted_text='[СОЖЖЁН]',
                encryption_key=''
            )
        except Exchange.DoesNotExist:
            pass
    return render(request, 'burn_done.html')