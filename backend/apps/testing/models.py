from django.db import models

from apps.projects.models import Document, Project


class Requirement(models.Model):
    TYPE_CHOICES = [
        ("feature", "功能点"),
        ("constraint", "约束"),
        ("exception", "异常场景"),
    ]

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="requirements", verbose_name="所属项目"
    )
    document = models.ForeignKey(
        Document, on_delete=models.SET_NULL, null=True, blank=True, related_name="requirements"
    )
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="children"
    )
    module = models.CharField("模块", max_length=100, blank=True)
    name = models.CharField("需求名称", max_length=200)
    description = models.TextField("需求描述", blank=True)
    requirement_type = models.CharField(
        "需求类型", max_length=20, choices=TYPE_CHOICES, default="feature"
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "功能需求"
        verbose_name_plural = verbose_name
        ordering = ["module", "id"]

    def __str__(self):
        return self.name


class TestPoint(models.Model):
    POINT_TYPE_CHOICES = [
        ("functional", "功能测试"),
        ("boundary", "边界测试"),
        ("exception", "异常测试"),
        ("security", "安全测试"),
    ]
    STRATEGY_CHOICES = [
        ("equivalence", "等价类"),
        ("boundary", "边界值"),
        ("scenario", "场景法"),
        ("state", "状态迁移"),
        ("default", "综合策略"),
    ]

    requirement = models.ForeignKey(
        Requirement, on_delete=models.CASCADE, related_name="test_points", verbose_name="关联需求"
    )
    name = models.CharField("测试点名称", max_length=200)
    description = models.TextField("测试点描述", blank=True)
    point_type = models.CharField("测试点类型", max_length=20, choices=POINT_TYPE_CHOICES, default="functional")
    design_strategy = models.CharField(
        "设计策略", max_length=20, choices=STRATEGY_CHOICES, default="default"
    )
    rag_context = models.TextField("RAG召回上下文", blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "测试点"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class KnowledgeItem(models.Model):
    CATEGORY_CHOICES = [
        ("experience", "测试经验库"),
        ("bug", "Bug知识库"),
        ("history", "历史用例库"),
    ]

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, null=True, blank=True, related_name="knowledge_items"
    )
    category = models.CharField("分类", max_length=20, choices=CATEGORY_CHOICES, default="experience")
    title = models.CharField("标题", max_length=200)
    content = models.TextField("内容")
    tags = models.JSONField("标签", default=list, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "知识库条目"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class CaseTemplate(models.Model):
    CATEGORY_CHOICES = [
        ("login", "登录模板"),
        ("payment", "支付模板"),
        ("upload", "文件上传模板"),
        ("custom", "自定义模板"),
    ]

    name = models.CharField("模板名称", max_length=200)
    category = models.CharField("模板分类", max_length=20, choices=CATEGORY_CHOICES, default="custom")
    precondition = models.TextField("前置条件", blank=True)
    steps = models.TextField("测试步骤", blank=True)
    expected = models.TextField("预期结果", blank=True)
    postcondition = models.TextField("后置条件", blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "用例模板"
        verbose_name_plural = verbose_name
        ordering = ["category", "id"]

    def __str__(self):
        return self.name


class TestCase(models.Model):
    PRIORITY_CHOICES = [
        ("P0", "P0-紧急"),
        ("P1", "P1-高"),
        ("P2", "P2-中"),
        ("P3", "P3-低"),
    ]
    SOURCE_CHOICES = [
        ("manual", "手动用例"),
        ("ai", "AI用例"),
        ("test_point", "测试点生成"),
        ("template", "模板生成"),
    ]

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="test_cases", verbose_name="所属项目"
    )
    test_point = models.ForeignKey(
        TestPoint, on_delete=models.SET_NULL, null=True, blank=True, related_name="test_cases"
    )
    template = models.ForeignKey(
        CaseTemplate, on_delete=models.SET_NULL, null=True, blank=True, related_name="test_cases"
    )
    depends_on = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="dependents"
    )
    case_no = models.CharField("用例标号", max_length=100, blank=True)
    module = models.CharField("模块", max_length=100, blank=True)
    title = models.CharField("用例标题", max_length=300)
    precondition = models.TextField("前置条件", blank=True)
    extra_data = models.JSONField("扩展字段", default=dict, blank=True)
    steps = models.TextField("测试步骤", blank=True)
    expected = models.TextField("预期结果", blank=True)
    postcondition = models.TextField("后置条件", blank=True)
    actual = models.TextField("实际结果", blank=True)
    priority = models.CharField("优先级", max_length=5, choices=PRIORITY_CHOICES, default="P2")
    source_type = models.CharField("用例来源", max_length=20, choices=SOURCE_CHOICES, default="manual")
    executor = models.CharField("执行人", max_length=100, blank=True)
    passed = models.BooleanField("是否通过", null=True, blank=True)
    sort_order = models.PositiveIntegerField("排序", default=0)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "测试用例"
        verbose_name_plural = verbose_name
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.title


class TestCaseFieldDefinition(models.Model):
    FIELD_TYPE_CHOICES = [
        ("text", "单行文本"),
        ("textarea", "多行文本"),
        ("select", "下拉选择"),
        ("date", "日期"),
        ("priority", "优先级"),
        ("passed", "执行状态"),
    ]
    STORAGE_CHOICES = [
        ("column", "标准列"),
        ("extra", "扩展字段"),
    ]

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="case_field_definitions",
        verbose_name="所属项目",
    )
    key = models.CharField("字段键", max_length=50)
    label = models.CharField("显示名称", max_length=100)
    field_type = models.CharField("字段类型", max_length=20, choices=FIELD_TYPE_CHOICES, default="text")
    storage = models.CharField("存储方式", max_length=20, choices=STORAGE_CHOICES, default="column")
    column_name = models.CharField("对应列名", max_length=50, blank=True)
    required = models.BooleanField("必填", default=False)
    searchable = models.BooleanField("参与搜索", default=False)
    show_in_list = models.BooleanField("列表展示", default=True)
    show_in_filter = models.BooleanField("筛选展示", default=False)
    sort_order = models.PositiveIntegerField("排序", default=0)
    is_system = models.BooleanField("系统字段", default=False)
    options = models.JSONField("选项", default=list, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "用例字段定义"
        verbose_name_plural = verbose_name
        ordering = ["sort_order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["project", "key"], name="uniq_case_field_project_key"),
        ]

    def __str__(self):
        return f"{self.label}({self.key})"


class ApiInterface(models.Model):
    METHOD_CHOICES = [
        ("GET", "GET"),
        ("POST", "POST"),
        ("PUT", "PUT"),
        ("DELETE", "DELETE"),
        ("PATCH", "PATCH"),
    ]

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="api_interfaces", verbose_name="所属项目"
    )
    document = models.ForeignKey(
        "projects.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="api_interfaces",
        verbose_name="来源文档",
    )
    depends_on = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dependents",
        verbose_name="关联接口",
    )
    dependency_mappings = models.JSONField(
        "关联字段映射",
        default=list,
        blank=True,
        help_text='[{"depends_on":1,"source":"body.data.access_token","target":"headers.Authorization"}]',
    )
    name = models.CharField("接口名称", max_length=200)
    module = models.CharField("模块", max_length=100, blank=True)
    method = models.CharField("请求方式", max_length=10, choices=METHOD_CHOICES, default="GET")
    url = models.CharField("接口地址", max_length=500)
    headers = models.JSONField("请求头", default=dict, blank=True)
    params = models.JSONField("请求参数", default=dict, blank=True)
    body = models.JSONField("请求体", default=dict, blank=True)
    response_example = models.JSONField("响应示例", default=dict, blank=True)
    description = models.TextField("接口描述", blank=True)
    sort_order = models.PositiveIntegerField("排序", default=0)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "接口"
        verbose_name_plural = verbose_name
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.name


class StressTestTarget(models.Model):
    """压测目标接口快照，与接口自动化 ApiInterface 独立存储。"""

    METHOD_CHOICES = ApiInterface.METHOD_CHOICES

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="stress_test_targets", verbose_name="所属项目"
    )
    source_interface_id = models.PositiveIntegerField("来源接口ID", null=True, blank=True)
    depends_on = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dependents",
        verbose_name="关联压测目标",
    )
    dependency_mappings = models.JSONField("关联字段映射", default=list, blank=True)
    name = models.CharField("接口名称", max_length=200)
    module = models.CharField("模块", max_length=100, blank=True)
    method = models.CharField("请求方式", max_length=10, choices=METHOD_CHOICES, default="GET")
    url = models.CharField("接口地址", max_length=500)
    headers = models.JSONField("请求头", default=dict, blank=True)
    params = models.JSONField("请求参数", default=dict, blank=True)
    body = models.JSONField("请求体", default=dict, blank=True)
    response_example = models.JSONField("响应示例", default=dict, blank=True)
    description = models.TextField("接口描述", blank=True)
    sort_order = models.PositiveIntegerField("排序", default=0)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "压测目标"
        verbose_name_plural = verbose_name
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.name


class StressTestRun(models.Model):
    """压测执行记录与实时指标。"""

    STATUS_CHOICES = [
        ("pending", "等待中"),
        ("running", "执行中"),
        ("completed", "已完成"),
        ("stopped", "已停止"),
        ("failed", "失败"),
    ]

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="stress_test_runs", verbose_name="所属项目"
    )
    name = models.CharField("任务名称", max_length=200, blank=True)
    status = models.CharField("状态", max_length=20, choices=STATUS_CHOICES, default="pending")
    config = models.JSONField("压测配置", default=dict, blank=True)
    summary = models.JSONField("汇总指标", default=dict, blank=True)
    time_series = models.JSONField("时序指标", default=list, blank=True)
    endpoint_stats = models.JSONField("接口统计", default=list, blank=True)
    resource_series = models.JSONField("资源监控", default=list, blank=True)
    analysis = models.JSONField("性能分析", default=dict, blank=True)
    error_message = models.TextField("错误信息", blank=True)
    started_at = models.DateTimeField("开始时间", null=True, blank=True)
    finished_at = models.DateTimeField("结束时间", null=True, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "压测记录"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]

    def __str__(self):
        return self.name or f"压测#{self.pk}"


class SecurityScanTarget(models.Model):
    """安全扫描任务接口快照，与接口自动化 ApiInterface 独立存储。"""

    METHOD_CHOICES = ApiInterface.METHOD_CHOICES

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="security_scan_targets", verbose_name="所属项目"
    )
    source_interface_id = models.PositiveIntegerField("来源接口ID", null=True, blank=True)
    depends_on = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dependents",
        verbose_name="关联扫描目标",
    )
    dependency_mappings = models.JSONField("关联字段映射", default=list, blank=True)
    name = models.CharField("接口名称", max_length=200)
    module = models.CharField("模块", max_length=100, blank=True)
    method = models.CharField("请求方式", max_length=10, choices=METHOD_CHOICES, default="GET")
    url = models.CharField("接口地址", max_length=500)
    headers = models.JSONField("请求头", default=dict, blank=True)
    params = models.JSONField("请求参数", default=dict, blank=True)
    body = models.JSONField("请求体", default=dict, blank=True)
    response_example = models.JSONField("响应示例", default=dict, blank=True)
    description = models.TextField("接口描述", blank=True)
    sort_order = models.PositiveIntegerField("排序", default=0)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "安全扫描目标"
        verbose_name_plural = verbose_name
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.name


class ApiTestCase(models.Model):
    api = models.ForeignKey(
        ApiInterface, on_delete=models.CASCADE, related_name="test_cases", verbose_name="关联接口"
    )
    title = models.CharField("用例标题", max_length=300)
    params = models.JSONField("请求参数", default=dict, blank=True)
    validate_content = models.TextField("校验内容", blank=True)
    extract_content = models.JSONField("提取内容", default=dict, blank=True)
    should_run = models.BooleanField("是否执行", default=True)
    sort_order = models.PositiveIntegerField("排序", default=0)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "接口测试用例"
        verbose_name_plural = verbose_name
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.title


class TestSuite(models.Model):
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="test_suites", verbose_name="所属项目"
    )
    name = models.CharField("套件名称", max_length=200)
    case_ids = models.JSONField("用例ID列表", default=list, blank=True)
    schedule = models.CharField("定时任务", max_length=100, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "测试套件"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class ExecutionRun(models.Model):
    STATUS_CHOICES = [
        ("pending", "等待中"),
        ("running", "执行中"),
        ("success", "成功"),
        ("failed", "失败"),
        ("partial", "部分成功"),
    ]

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="execution_runs", verbose_name="所属项目"
    )
    suite = models.ForeignKey(
        TestSuite, on_delete=models.SET_NULL, null=True, blank=True, related_name="runs"
    )
    name = models.CharField("执行名称", max_length=200)
    status = models.CharField("状态", max_length=20, choices=STATUS_CHOICES, default="pending")
    total = models.PositiveIntegerField("总数", default=0)
    passed = models.PositiveIntegerField("通过数", default=0)
    failed = models.PositiveIntegerField("失败数", default=0)
    results = models.JSONField("执行结果", default=list, blank=True)
    ai_analysis = models.TextField("AI分析", blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "执行记录"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class AsyncTask(models.Model):
    STATUS_CHOICES = [
        ("pending", "等待中"),
        ("running", "执行中"),
        ("success", "成功"),
        ("failed", "失败"),
    ]

    task_name = models.CharField("任务名称", max_length=200)
    task_type = models.CharField("任务类型", max_length=50)
    status = models.CharField("执行状态", max_length=20, choices=STATUS_CHOICES, default="pending")
    project = models.ForeignKey(
        Project,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="async_tasks",
        verbose_name="所属项目",
    )
    progress = models.PositiveSmallIntegerField("进度百分比", default=0)
    total_steps = models.PositiveIntegerField("总步骤", default=0)
    completed_steps = models.PositiveIntegerField("已完成步骤", default=0)
    current_step = models.CharField("当前步骤", max_length=300, blank=True)
    meta = models.JSONField("任务参数", default=dict, blank=True)
    error_message = models.TextField("错误信息", blank=True)
    result = models.TextField("执行结果", blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "异步任务"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]

    def __str__(self):
        return self.task_name
