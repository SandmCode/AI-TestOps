from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ai_features", "0004_testreport_source_meta"),
    ]

    operations = [
        migrations.CreateModel(
            name="AnalysisRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "analysis_type",
                    models.CharField(
                        choices=[
                            ("contract", "契约测试"),
                            ("coverage", "覆盖率分析"),
                            ("log", "日志分析"),
                        ],
                        max_length=20,
                        verbose_name="分析类型",
                    ),
                ),
                ("title", models.CharField(max_length=200, verbose_name="标题")),
                ("summary", models.TextField(blank=True, verbose_name="摘要")),
                ("input_content", models.TextField(verbose_name="输入内容")),
                ("input_preview", models.CharField(blank=True, max_length=300, verbose_name="输入预览")),
                ("result", models.JSONField(default=dict, verbose_name="分析结果")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
            ],
            options={
                "verbose_name": "分析记录",
                "verbose_name_plural": "分析记录",
                "ordering": ["-created_at"],
            },
        ),
    ]
