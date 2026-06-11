from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("testing", "0009_stress_test"),
    ]

    operations = [
        migrations.AddField(
            model_name="stresstestrun",
            name="analysis",
            field=models.JSONField(blank=True, default=dict, verbose_name="性能分析"),
        ),
    ]
