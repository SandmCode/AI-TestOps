from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0002_document_file_ext_document_file_size_and_more"),
        ("testing", "0004_asynctask_progress_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="apiinterface",
            name="document",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="api_interfaces",
                to="projects.document",
                verbose_name="来源文档",
            ),
        ),
        migrations.AddField(
            model_name="apiinterface",
            name="depends_on",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="dependents",
                to="testing.apiinterface",
                verbose_name="关联接口",
            ),
        ),
        migrations.AddField(
            model_name="apiinterface",
            name="dependency_mappings",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='[{"source":"body.token","target":"headers.Authorization"}]',
                verbose_name="关联字段映射",
            ),
        ),
    ]
