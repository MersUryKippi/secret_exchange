from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('exchange', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='exchange',
            name='participant1_token',
            field=models.CharField(blank=True, default='', max_length=64),
        ),
        migrations.AddField(
            model_name='exchange',
            name='participant2_token',
            field=models.CharField(blank=True, default='', max_length=64),
        ),
        migrations.AddField(
            model_name='message',
            name='sender_token',
            field=models.CharField(blank=True, default='', max_length=64),
        ),
    ]
