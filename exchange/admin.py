from django.contrib import admin
from .models import Secret, Exchange, Message, Report, SecretWeight

@admin.register(SecretWeight)
class SecretWeightAdmin(admin.ModelAdmin):
    list_display = ['id', 'weight']

@admin.register(Secret)
class SecretAdmin(admin.ModelAdmin):
    list_display = ['id', 'owner_session_key', 'weight', 'created_at', 'report_count']

@admin.register(Exchange)
class ExchangeAdmin(admin.ModelAdmin):
    list_display = ['id', 'status', 'created_at', 'chat_delete_at']

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'exchange', 'sender_session_key', 'created_at']

@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ['id', 'secret', 'reporter_session_key', 'created_at']