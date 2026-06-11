from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("testing", "0005_apiinterface_document_dependency"),
    ]

    operations = [
        migrations.AddField(
            model_name="apiinterface",
            name="sort_order",
            field=models.PositiveIntegerField(default=0, verbose_name="排序"),
        ),
        migrations.AlterModelOptions(
            name="apiinterface",
            options={"ordering": ["sort_order", "id"], "verbose_name": "接口", "verbose_name_plural": "接口"},
        ),
    ]
