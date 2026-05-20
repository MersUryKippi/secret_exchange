from django.shortcuts import render, redirect
from .forms import SecretForm
from .models import Secret, SecretWeight
import hashlib
from django.http import Http404, JsonResponse
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from .models import Exchange, Message
import json


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
        return render(request, 'burn_done.html', {'exchange_id': exchange_id})
    return render(request, 'burn_done.html', {'exchange_id': exchange_id})


# ── Chat views ──────────────────────────────────────────────────────────────

def _get_exchange_for_session(exchange_id, session_key):
    """
    Returns the Exchange only if the current session is a participant
    and the exchange has not expired.
    Raises Http404 otherwise.
    """
    try:
        ex = Exchange.objects.get(id=exchange_id)
    except Exchange.DoesNotExist:
        raise Http404("Обмен не найден")

    is_participant = (
        ex.participant1_session_key == session_key or
        ex.participant2_session_key == session_key
    )
    if not is_participant:
        raise Http404("Ты не участник этого обмена")

    return ex


def chat_view(request, exchange_id):
    """Renders the ephemeral chat page."""
    session_key = get_or_create_session(request)
    ex = _get_exchange_for_session(exchange_id, session_key)

    # Expire check: mark completed if past deletion time
    if ex.status == 'active' and timezone.now() >= ex.chat_delete_at:
        Message.objects.filter(exchange=ex).delete()
        ex.status = 'completed'
        ex.save()

    messages = Message.objects.filter(exchange=ex).order_by('created_at')

    return render(request, 'chat.html', {
        'exchange': ex,
        'messages': messages,
        'session_key': session_key,
    })


def chat_messages_json(request, exchange_id):
    """
    GET /chat/<id>/messages/?after=<last_id>
    Returns JSON list of messages newer than `after`.
    """
    session_key = get_or_create_session(request)
    ex = _get_exchange_for_session(exchange_id, session_key)

    # Expire check
    if ex.status == 'active' and timezone.now() >= ex.chat_delete_at:
        Message.objects.filter(exchange=ex).delete()
        ex.status = 'completed'
        ex.save()
        return JsonResponse({'messages': [], 'status': 'completed'})

    after_id = int(request.GET.get('after', 0))
    qs = Message.objects.filter(exchange=ex, id__gt=after_id).order_by('created_at')

    return JsonResponse({
        'messages': [
            {
                'id': m.id,
                'sender_session_key': m.sender_session_key,
                'text': m.text,
                'created_at': m.created_at.isoformat(),
            }
            for m in qs
        ],
        'status': ex.status,
    })


def chat_send(request, exchange_id):
    """
    POST /chat/<id>/send/
    Body: {"text": "..."}
    Returns the saved message as JSON.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    session_key = get_or_create_session(request)
    ex = _get_exchange_for_session(exchange_id, session_key)

    if ex.status != 'active' or timezone.now() >= ex.chat_delete_at:
        return JsonResponse({'error': 'Чат закрыт'}, status=403)

    try:
        body = json.loads(request.body)
        text = body.get('text', '').strip()
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    if not text:
        return JsonResponse({'error': 'Пустое сообщение'}, status=400)
    if len(text) > 1000:
        return JsonResponse({'error': 'Сообщение слишком длинное'}, status=400)

    msg = Message.objects.create(
        exchange=ex,
        sender_session_key=session_key,
        text=text,
    )

    return JsonResponse({
        'message': {
            'id': msg.id,
            'sender_session_key': msg.sender_session_key,
            'text': msg.text,
            'created_at': msg.created_at.isoformat(),
        }
    })