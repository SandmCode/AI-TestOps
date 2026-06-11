import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0001_initial"),
        ("testing", "0003_testcasefielddefinition_testcase_case_no_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="asynctask",
            name="project",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="async_tasks",
                to="projects.project",
                verbose_name="所属项目",
            ),
        ),
        migrations.AddField(
            model_name="asynctask",
            name="progress",
            field=models.PositiveSmallIntegerField(default=0, verbose_name="进度百分比"),
        ),
        migrations.AddField(
            model_name="asynctask",
            name="total_steps",
            field=models.PositiveIntegerField(default=0, verbose_name="总步骤"),
        ),
        migrations.AddField(
            model_name="asynctask",
            name="completed_steps",
            field=models.PositiveIntegerField(default=0, verbose_name="已完成步骤"),
        ),
        migrations.AddField(
            model_name="asynctask",
            name="current_step",
            field=models.CharField(blank=True, max_length=300, verbose_name="当前步骤"),
        ),
        migrations.AddField(
            model_name="asynctask",
            name="meta",
            field=models.JSONField(blank=True, default=dict, verbose_name="任务参数"),
        ),
        migrations.AddField(
            model_name="asynctask",
            name="error_message",
            field=models.TextField(blank=True, verbose_name="错误信息"),
        ),
        migrations.AddField(
            model_name="asynctask",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, verbose_name="更新时间"),
        ),
    ]
