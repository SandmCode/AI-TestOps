from django.db import models


class TestReport(models.Model):
    REPORT_TYPE_CHOICES = [
        ("functional", "功能测试"),
        ("api", "接口测试"),
        ("performance", "性能测试"),
        ("security", "安全测试"),
        ("web", "Web自动化"),
    ]
    SOURCE_TYPE_CHOICES = [
        ("manual", "手动"),
        ("automation", "接口自动化"),
        ("security", "安全扫描"),
        ("stress", "接口压测"),
    ]

    name = models.CharField("报告名称", max_length=200)
    report_type = models.CharField("报告类型", max_length=20, choices=REPORT_TYPE_CHOICES)
    source_type = models.CharField(
        "来源", max_length=20, choices=SOURCE_TYPE_CHOICES, default="manual"
    )
    summary = models.TextField("报告摘要", blank=True)
    pass_rate = models.FloatField("通过率", default=0)
    total_cases = models.IntegerField("总用例数", default=0)
    passed_cases = models.IntegerField("通过数", default=0)
    report_url = models.CharField("报告链接", max_length=500, blank=True)
    meta = models.JSONField("扩展数据", default=dict, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "测试报告"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class AIProviderConfig(models.Model):
    PROVIDER_CHOICES = [
        ("zhipu", "智谱 AI"),
        ("openai", "OpenAI"),
        ("deepseek", "DeepSeek"),
        ("qwen", "通义千问"),
        ("moonshot", "Moonshot"),
        ("custom", "自定义 OpenAI 兼容"),
    ]

    name = models.CharField("配置名称", max_length=100)
    provider = models.CharField("厂商", max_length=20, choices=PROVIDER_CHOICES)
    api_key = models.CharField("API Key", max_length=500)
    base_url = models.CharField("Base URL", max_length=500, blank=True)
    model = models.CharField("模型", max_length=100)
    temperature = models.FloatField("温度", default=0.7)
    max_tokens = models.IntegerField("最大 Token", default=4096)
    is_active = models.BooleanField("当前启用", default=False)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "大模型配置"
        verbose_name_plural = verbose_name
        ordering = ["-is_active", "-updated_at"]

    def __str__(self):
        return f"{self.name} ({self.get_provider_display()})"

    @property
    def masked_api_key(self) -> str:
        key = self.api_key or ""
        if len(key) <= 8:
            return "*" * len(key)
        return f"{key[:4]}****{key[-4:]}"


class AISkillsSettings(models.Model):
    """Skills 全局开关（单例）。"""

    skills_enabled = models.BooleanField("启用 Skills 注入", default=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "Skills 全局设置"
        verbose_name_plural = verbose_name

    @classmethod
    def get_solo(cls) -> "AISkillsSettings":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class AnalysisRecord(models.Model):
    ANALYSIS_TYPE_CHOICES = [
        ("contract", "契约测试"),
        ("coverage", "覆盖率分析"),
        ("log", "日志分析"),
    ]

    analysis_type = models.CharField("分析类型", max_length=20, choices=ANALYSIS_TYPE_CHOICES)
    title = models.CharField("标题", max_length=200)
    summary = models.TextField("摘要", blank=True)
    input_content = models.TextField("输入内容")
    input_preview = models.CharField("输入预览", max_length=300, blank=True)
    result = models.JSONField("分析结果", default=dict)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "分析记录"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class AISkill(models.Model):
    name = models.CharField("名称", max_length=200)
    folder_name = models.CharField("文件夹名", max_length=200)
    content = models.TextField("SKILL.md 内容")
    source_path = models.CharField("来源路径", max_length=500, blank=True)
    source_type = models.CharField(
        "来源",
        max_length=20,
        choices=[("local", "本地扫描"), ("ccswitch", "CC Switch"), ("manual", "手动")],
        default="manual",
    )
    is_enabled = models.BooleanField("启用", default=True)
    sort_order = models.IntegerField("排序", default=0)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "Skill"
        verbose_name_plural = "Skills"
        ordering = ["sort_order", "name"]
        unique_together = [("folder_name", "source_path")]

    def __str__(self):
        return self.name
