# Generated manually

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0003_chunkuploadsession"),
        ("testing", "0002_casetemplate_alter_requirement_options_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="testcase",
            name="case_no",
            field=models.CharField(blank=True, max_length=100, verbose_name="用例标号"),
        ),
        migrations.AddField(
            model_name="testcase",
            name="module",
            field=models.CharField(blank=True, max_length=100, verbose_name="模块"),
        ),
        migrations.AddField(
            model_name="testcase",
            name="extra_data",
            field=models.JSONField(blank=True, default=dict, verbose_name="扩展字段"),
        ),
        migrations.CreateModel(
            name="TestCaseFieldDefinition",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=50, verbose_name="字段键")),
                ("label", models.CharField(max_length=100, verbose_name="显示名称")),
                (
                    "field_type",
                    models.CharField(
                        choices=[
                            ("text", "单行文本"),
                            ("textarea", "多行文本"),
                            ("select", "下拉选择"),
                            ("date", "日期"),
                            ("priority", "优先级"),
                            ("passed", "执行状态"),
                        ],
                        default="text",
                        max_length=20,
                        verbose_name="字段类型",
                    ),
                ),
                (
                    "storage",
                    models.CharField(
                        choices=[("column", "标准列"), ("extra", "扩展字段")],
                        default="column",
                        max_length=20,
                        verbose_name="存储方式",
                    ),
                ),
                ("column_name", models.CharField(blank=True, max_length=50, verbose_name="对应列名")),
                ("required", models.BooleanField(default=False, verbose_name="必填")),
                ("searchable", models.BooleanField(default=False, verbose_name="参与搜索")),
                ("show_in_list", models.BooleanField(default=True, verbose_name="列表展示")),
                ("show_in_filter", models.BooleanField(default=False, verbose_name="筛选展示")),
                ("sort_order", models.PositiveIntegerField(default=0, verbose_name="排序")),
                ("is_system", models.BooleanField(default=False, verbose_name="系统字段")),
                ("options", models.JSONField(blank=True, default=list, verbose_name="选项")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                (
                    "project",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="case_field_definitions",
                        to="projects.project",
                        verbose_name="所属项目",
                    ),
                ),
            ],
            options={
                "verbose_name": "用例字段定义",
                "verbose_name_plural": "用例字段定义",
                "ordering": ["sort_order", "id"],
            },
        ),
        migrations.AddConstraint(
            model_name="testcasefielddefinition",
            constraint=models.UniqueConstraint(fields=("project", "key"), name="uniq_case_field_project_key"),
        ),
    ]
