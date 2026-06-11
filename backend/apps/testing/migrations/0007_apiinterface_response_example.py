from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("testing", "0006_apiinterface_sort_order"),
    ]

    operations = [
        migrations.AddField(
            model_name="apiinterface",
            name="response_example",
            field=models.JSONField(blank=True, default=dict, verbose_name="响应示例"),
        ),
    ]
