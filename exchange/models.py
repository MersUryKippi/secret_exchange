from django.db import models
from cryptography.fernet import Fernet
import hashlib
import secrets


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

    # ── NEW: per-participant access tokens ──────────────────────────────────
    # Each participant gets a unique opaque token stored in their browser
    # (localStorage). This allows returning to the chat from any device /
    # after the session cookie changes, without exposing the other
    # participant's token.
    participant1_token = models.CharField(max_length=64, blank=True, default='')
    participant2_token = models.CharField(max_length=64, blank=True, default='')

    class Meta:
        db_table = 'exchange'

    def __str__(self):
        return f"Обмен #{self.id} [{self.status}]"

    # ── helpers ─────────────────────────────────────────────────────────────

    def generate_tokens(self):
        """Call once right after creation to populate both tokens."""
        self.participant1_token = secrets.token_hex(32)
        self.participant2_token = secrets.token_hex(32)

    def token_for_session(self, session_key: str) -> str | None:
        """Return the token that belongs to this session, or None."""
        if self.participant1_session_key == session_key:
            return self.participant1_token
        if self.participant2_session_key == session_key:
            return self.participant2_token
        return None

    def is_valid_token(self, token: str) -> bool:
        """Check whether the token belongs to either participant."""
        if not token:
            return False
        return token in (self.participant1_token, self.participant2_token)

    def token_identity(self, token: str) -> str | None:
        """
        Return a stable pseudo-identity string for a token so the chat UI can
        label messages as 'me' vs 'them' regardless of which device is used.
        Returns 'p1' | 'p2' | None.
        """
        if token == self.participant1_token:
            return 'p1'
        if token == self.participant2_token:
            return 'p2'
        return None


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
    # ── NEW: token-based sender identity so messages survive session changes ─
    sender_token = models.CharField(max_length=64, blank=True, default='')
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