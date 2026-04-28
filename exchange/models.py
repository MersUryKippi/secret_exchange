from django.db import models
from cryptography.fernet import Fernet
import hashlib


class SecretWeight(models.Model):
    weight = models.SmallIntegerField()

    class Meta:
        db_table = 'secret_weight'

    def __str__(self):
        return f"Уровень {self.weight}"


class Exchange(models.Model):
    STATUS_CHOICES = [
        ('active', 'Активный'),
        ('completed', 'Завершён'),
    ]
    participant1_session_key = models.CharField(max_length=40)
    participant2_session_key = models.CharField(max_length=40)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    chat_delete_at = models.DateTimeField()

    class Meta:
        db_table = 'exchange'

    def __str__(self):
        return f"Обмен #{self.id} [{self.status}]"


class Secret(models.Model):
    owner_session_key = models.CharField(max_length=40)
    encrypted_text = models.TextField()
    encryption_key = models.CharField(max_length=44)
    content_hash = models.CharField(max_length=64, unique=True)
    weight = models.ForeignKey(SecretWeight, on_delete=models.PROTECT, db_column='weight_id')
    exchange = models.ForeignKey(
        Exchange, null=True, blank=True,
        on_delete=models.SET_NULL, db_column='exchange_id'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    report_count = models.IntegerField(default=0)

    class Meta:
        db_table = 'secret'

    def save_text(self, plain_text):
        """Шифрует текст и сохраняет хеш"""
        key = Fernet.generate_key()
        f = Fernet(key)
        self.encrypted_text = f.encrypt(plain_text.encode()).decode()
        self.encryption_key = key.decode()
        self.content_hash = hashlib.sha256(plain_text.encode()).hexdigest()

    def get_text(self):
        """Расшифровывает текст"""
        f = Fernet(self.encryption_key.encode())
        return f.decrypt(self.encrypted_text.encode()).decode()

    def __str__(self):
        return f"Секрет #{self.id} (вес: {self.weight.weight})"


class Message(models.Model):
    exchange = models.ForeignKey(Exchange, on_delete=models.CASCADE)
    sender_session_key = models.CharField(max_length=40)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'message'

    def __str__(self):
        return f"Сообщение #{self.id} в обмене #{self.exchange_id}"


class Report(models.Model):
    secret = models.ForeignKey(Secret, on_delete=models.CASCADE)
    reporter_session_key = models.CharField(max_length=40)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'report'

    def __str__(self):
        return f"Жалоба на секрет #{self.secret_id}"