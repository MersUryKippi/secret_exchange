from celery import shared_task
from django.utils import timezone

@shared_task
def delete_expired_exchanges():
    from .models import Exchange, Message
    expired = Exchange.objects.filter(chat_delete_at__lt=timezone.now(), status='active')
    for ex in expired:
        Message.objects.filter(exchange=ex).delete()
        ex.status = 'completed'
        ex.save()