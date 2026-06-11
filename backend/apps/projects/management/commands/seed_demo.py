from django.core.management.base import BaseCommand

from apps.ai_features.models import TestReport
from apps.projects.models import Document, Project
from apps.testing.models import Requirement, TestCase, TestPoint


class Command(BaseCommand):
    help = "初始化演示数据"

    def handle(self, *args, **options):
        project, _ = Project.objects.get_or_create(
            name="电商测试项目",
            defaults={"description": "电商平台核心功能测试", "owner": "张三"},
        )

        doc, _ = Document.objects.get_or_create(
            project=project,
            name="用户模块需求文档",
            defaults={
                "version": "v1.0",
                "doc_type": "requirement",
                "content": "用户模块包含登录、注册、密码找回等功能。登录需支持手机号和邮箱两种方式。",
            },
        )

        req, _ = Requirement.objects.get_or_create(
            project=project,
            name="用户登录",
            defaults={
                "document": doc,
                "module": "用户模块",
                "description": "验证用户名密码登录功能，支持手机号和邮箱登录",
            },
        )

        tp, _ = TestPoint.objects.get_or_create(
            requirement=req,
            name="正常登录流程",
            defaults={"point_type": "functional"},
        )

        cases_data = [
            {"title": "手机号+正确密码登录", "steps": "1.输入手机号\n2.输入密码\n3.点击登录", "expected": "登录成功跳转首页", "priority": "P0"},
            {"title": "邮箱+正确密码登录", "steps": "1.输入邮箱\n2.输入密码\n3.点击登录", "expected": "登录成功跳转首页", "priority": "P1"},
            {"title": "错误密码登录", "steps": "1.输入手机号\n2.输入错误密码\n3.点击登录", "expected": "提示密码错误", "priority": "P1"},
        ]
        for idx, data in enumerate(cases_data):
            TestCase.objects.get_or_create(
                project=project,
                title=data["title"],
                defaults={**data, "test_point": tp, "sort_order": idx},
            )

        TestReport.objects.get_or_create(
            name="用户模块回归测试报告",
            defaults={
                "report_type": "functional",
                "summary": "用户模块核心功能回归测试",
                "total_cases": 3,
                "passed_cases": 2,
                "pass_rate": 66.7,
            },
        )

        self.stdout.write(self.style.SUCCESS("演示数据初始化完成"))
