# Generated manually for stress test models

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("testing", "0008_security_scan_target"),
    ]

    operations = [
        migrations.CreateModel(
            name="StressTestTarget",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_interface_id", models.PositiveIntegerField(blank=True, null=True, verbose_name="来源接口ID")),
                ("dependency_mappings", models.JSONField(blank=True, default=list, verbose_name="关联字段映射")),
                ("name", models.CharField(max_length=200, verbose_name="接口名称")),
                ("module", models.CharField(blank=True, max_length=100, verbose_name="模块")),
                (
                    "method",
                    models.CharField(
                        choices=[
                            ("GET", "GET"),
                            ("POST", "POST"),
                            ("PUT", "PUT"),
                            ("DELETE", "DELETE"),
                            ("PATCH", "PATCH"),
                        ],
                        default="GET",
                        max_length=10,
                        verbose_name="请求方式",
                    ),
                ),
                ("url", models.CharField(max_length=500, verbose_name="接口地址")),
                ("headers", models.JSONField(blank=True, default=dict, verbose_name="请求头")),
                ("params", models.JSONField(blank=True, default=dict, verbose_name="请求参数")),
                ("body", models.JSONField(blank=True, default=dict, verbose_name="请求体")),
                ("response_example", models.JSONField(blank=True, default=dict, verbose_name="响应示例")),
                ("description", models.TextField(blank=True, verbose_name="接口描述")),
                ("sort_order", models.PositiveIntegerField(default=0, verbose_name="排序")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                (
                    "depends_on",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="dependents",
                        to="testing.stresstesttarget",
                        verbose_name="关联压测目标",
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="stress_test_targets",
                        to="projects.project",
                        verbose_name="所属项目",
                    ),
                ),
            ],
            options={
                "verbose_name": "压测目标",
                "verbose_name_plural": "压测目标",
                "ordering": ["sort_order", "id"],
            },
        ),
        migrations.CreateModel(
            name="StressTestRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(blank=True, max_length=200, verbose_name="任务名称")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "等待中"),
                            ("running", "执行中"),
                            ("completed", "已完成"),
                            ("stopped", "已停止"),
                            ("failed", "失败"),
                        ],
                        default="pending",
                        max_length=20,
                        verbose_name="状态",
                    ),
                ),
                ("config", models.JSONField(blank=True, default=dict, verbose_name="压测配置")),
                ("summary", models.JSONField(blank=True, default=dict, verbose_name="汇总指标")),
                ("time_series", models.JSONField(blank=True, default=list, verbose_name="时序指标")),
                ("endpoint_stats", models.JSONField(blank=True, default=list, verbose_name="接口统计")),
                ("resource_series", models.JSONField(blank=True, default=list, verbose_name="资源监控")),
                ("error_message", models.TextField(blank=True, verbose_name="错误信息")),
                ("started_at", models.DateTimeField(blank=True, null=True, verbose_name="开始时间")),
                ("finished_at", models.DateTimeField(blank=True, null=True, verbose_name="结束时间")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="stress_test_runs",
                        to="projects.project",
                        verbose_name="所属项目",
                    ),
                ),
            ],
            options={
                "verbose_name": "压测记录",
                "verbose_name_plural": "压测记录",
                "ordering": ["-created_at"],
            },
        ),
    ]
