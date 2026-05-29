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


def get_or_create_session(request):
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


def submit_page(request):
    if request.method == 'POST':
        form = SecretForm(request.POST)
        if form.is_valid():
            text = form.cleaned_data['text']
            weight = form.cleaned_data['weight']
            content_hash = hashlib.sha256(text.encode()).hexdigest()
            if Secret.objects.filter(content_hash=content_hash).exists():
                form.add_error('text', 'Такой секрет уже существует.')
                return render(request, 'submit.html', {'form': form})
            if not request.session.session_key:
                request.session.create()
            session_key = request.session.session_key
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

    # Если у пользователя УЖЕ есть активный обмен — показать его
    active_ex = (
        Exchange.objects.filter(
            status='active',
            chat_delete_at__gt=timezone.now(),
            participant1_session_key=session_key,
        ).first()
        or Exchange.objects.filter(
            status='active',
            chat_delete_at__gt=timezone.now(),
            participant2_session_key=session_key,
        ).first()
    )

    if active_ex:
        partner = (
            Secret.objects.filter(exchange=active_ex)
            .exclude(owner_session_key=session_key)
            .first()
        )
        received_text = None
        if partner:
            if partner.encryption_key and partner.encrypted_text not in ('[СОЖЖЁН]', '[BURNED]'):
                try:
                    received_text = partner.get_text()
                except Exception:
                    received_text = '[ТЕКСТ НЕДОСТУПЕН]'
            else:
                received_text = '[СОЖЖЁН]'
        return render(request, 'exchange_result.html', {
            'received_text': received_text or '[СОЖЖЁН]',
            'exchange': active_ex,
            'my_token': active_ex.token_for_session(session_key),
        })

    # Поиск своего свободного секрета
    my_secret = Secret.objects.filter(
        owner_session_key=session_key,
        exchange__isnull=True
    ).first()

    if not my_secret:
        return render(request, 'exchange_no_secret.html')

    try:
        with transaction.atomic():
            partner_secret = Secret.objects.select_for_update().filter(
                exchange__isnull=True,
                weight__weight__gte=my_secret.weight.weight - 1,
                weight__weight__lte=my_secret.weight.weight + 1,
            ).exclude(owner_session_key=session_key).first()

            if not partner_secret:
                return render(request, 'exchange_wait.html')

            ex = Exchange(
                participant1_session_key=session_key,
                participant2_session_key=partner_secret.owner_session_key,
                chat_delete_at=timezone.now() + timedelta(hours=1)
            )
            ex.generate_tokens()
            ex.save()

            my_secret.exchange = ex
            my_secret.save()
            partner_secret.exchange = ex
            partner_secret.save()

            received_text = partner_secret.get_text()
            my_token = ex.participant1_token

    except Exception as e:
        return render(request, 'exchange_error.html', {'error': str(e)})

    return render(request, 'exchange_result.html', {
        'received_text': received_text,
        'exchange': ex,
        'my_token': my_token,
    })


def burn_secret(request, exchange_id):
    session_key = get_or_create_session(request)
    my_token = request.POST.get('token', '')
    try:
        ex = Exchange.objects.get(id=exchange_id)
        # Use token if valid, else fall back to session key
        if my_token and ex.is_valid_token(my_token):
            if my_token == ex.participant1_token:
                Secret.objects.filter(
                    exchange=ex, owner_session_key=ex.participant2_session_key
                ).update(encrypted_text='[СОЖЖЁН]', encryption_key='')
            else:
                Secret.objects.filter(
                    exchange=ex, owner_session_key=ex.participant1_session_key
                ).update(encrypted_text='[СОЖЖЁН]', encryption_key='')
        else:
            Secret.objects.filter(
                exchange=ex
            ).exclude(owner_session_key=session_key).update(
                encrypted_text='[СОЖЖЁН]', encryption_key=''
            )
    except Exchange.DoesNotExist:
        pass
    return render(request, 'burn_done.html', {
        'exchange_id': exchange_id,
        'my_token': my_token,
    })


def _resolve_chat_token(request, exchange_id: int):
    try:
        ex = Exchange.objects.get(id=exchange_id)
    except Exchange.DoesNotExist:
        raise Http404("Обмен не найден")
    token = (
        request.GET.get('token')
        or request.POST.get('token')
        or _token_from_json_body(request)
    )
    if token and ex.is_valid_token(token):
        return ex, token
    session_key = get_or_create_session(request)
    derived_token = ex.token_for_session(session_key)
    if derived_token:
        return ex, derived_token
    raise Http404("Нет доступа к этому обмену")


def _token_from_json_body(request):
    try:
        body = json.loads(request.body)
        return body.get('token', '')
    except Exception:
        return ''


def _expire_if_needed(ex: Exchange) -> bool:
    if ex.status == 'active' and timezone.now() >= ex.chat_delete_at:
        Message.objects.filter(exchange=ex).delete()
        ex.status = 'completed'
        ex.save()
        return True
    return False


def chat_view(request, exchange_id):
    ex, token = _resolve_chat_token(request, exchange_id)
    _expire_if_needed(ex)
    messages = Message.objects.filter(exchange=ex).order_by('created_at')
    my_identity = ex.token_identity(token)
    return render(request, 'chat.html', {
        'exchange': ex,
        'messages': messages,
        'my_token': token,
        'my_identity': my_identity,
    })


def chat_messages_json(request, exchange_id):
    ex, token = _resolve_chat_token(request, exchange_id)
    if _expire_if_needed(ex):
        return JsonResponse({'messages': [], 'status': 'completed'})
    my_identity = ex.token_identity(token)
    after_id = int(request.GET.get('after', 0))
    qs = Message.objects.filter(exchange=ex, id__gt=after_id).order_by('created_at')
    return JsonResponse({
        'messages': [
            {
                'id': m.id,
                'is_mine': m.sender_token == token,
                'identity': ex.token_identity(m.sender_token),
                'text': m.text,
                'created_at': m.created_at.isoformat(),
            }
            for m in qs
        ],
        'my_identity': my_identity,
        'status': ex.status,
        'seconds_left': max(0, int((ex.chat_delete_at - timezone.now()).total_seconds())),
    })


def chat_send(request, exchange_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    ex, token = _resolve_chat_token(request, exchange_id)
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
    session_key = get_or_create_session(request)
    msg = Message.objects.create(
        exchange=ex,
        sender_session_key=session_key,
        sender_token=token,
        text=text,
    )
    return JsonResponse({
        'message': {
            'id': msg.id,
            'is_mine': True,
            'identity': ex.token_identity(token),
            'text': msg.text,
            'created_at': msg.created_at.isoformat(),
        }
    })


def active_exchange_status(request):
    token = request.GET.get('token', '').strip()
    if not token:
        return JsonResponse({'active': False})
    ex = Exchange.objects.filter(
        status='active',
        chat_delete_at__gt=timezone.now(),
    ).filter(
        participant1_token=token
    ).first() or Exchange.objects.filter(
        status='active',
        chat_delete_at__gt=timezone.now(),
    ).filter(
        participant2_token=token
    ).first()
    if not ex:
        return JsonResponse({'active': False})
    return JsonResponse({
        'active': True,
        'exchange_id': ex.id,
        'seconds_left': max(0, int((ex.chat_delete_at - timezone.now()).total_seconds())),
    })

def chat_end(request, exchange_id):
    """Завершить чат досрочно. Принимает POST с токеном."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    ex, token = _resolve_chat_token(request, exchange_id)
    if ex.status != 'active':
        return JsonResponse({'ok': True, 'already_closed': True})
    Message.objects.filter(exchange=ex).delete()
    ex.status = 'completed'
    ex.save()
    return JsonResponse({'ok': True})