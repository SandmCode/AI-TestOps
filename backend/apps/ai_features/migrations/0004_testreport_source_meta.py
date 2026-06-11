from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ai_features", "0003_aiskillssettings_aiskill"),
    ]

    operations = [
        migrations.AddField(
            model_name="testreport",
            name="source_type",
            field=models.CharField(
                choices=[
                    ("manual", "手动"),
                    ("automation", "接口自动化"),
                    ("security", "安全扫描"),
                    ("stress", "接口压测"),
                ],
                default="manual",
                max_length=20,
                verbose_name="来源",
            ),
        ),
        migrations.AddField(
            model_name="testreport",
            name="meta",
            field=models.JSONField(blank=True, default=dict, verbose_name="扩展数据"),
        ),
        migrations.AlterField(
            model_name="testreport",
            name="report_type",
            field=models.CharField(
                choices=[
                    ("functional", "功能测试"),
                    ("api", "接口测试"),
                    ("performance", "性能测试"),
                    ("security", "安全测试"),
                    ("web", "Web自动化"),
                ],
                max_length=20,
                verbose_name="报告类型",
            ),
        ),
    ]
