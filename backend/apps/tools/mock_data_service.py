"""Rich mock data generator for testing tools."""

from __future__ import annotations

import random
import string
import uuid
from datetime import datetime, timedelta
from typing import Any

SURNAMES = list("赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜")
GIVEN_NAMES = [
    "伟", "芳", "娜", "敏", "静", "丽", "强", "磊", "军", "洋", "勇", "艳", "杰", "娟", "涛",
    "明", "超", "秀英", "霞", "平", "刚", "桂英", "建华", "文", "华", "建国", "云", "志强", "玉兰",
    "浩然", "子涵", "梓轩", "雨桐", "思远", "佳怡", "宇航", "欣妍", "博文", "诗涵",
]
CITIES = [
    "北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", "西安", "南京", "苏州",
    "重庆", "天津", "长沙", "郑州", "青岛", "厦门", "合肥", "福州", "济南", "昆明",
]
DISTRICTS = ["朝阳区", "浦东新区", "天河区", "南山区", "西湖区", "高新区", "江汉区", "雁塔区", "江宁区", "工业园区"]
STREETS = ["人民路", "解放大道", "科技路", "建设路", "中山路", "文化路", "学院路", "和平大道", "滨河路", "创业街"]
COMPANIES = [
    "星云科技", "蓝海信息", "智汇软件", "云启网络", "数联智能", "华信系统", "极光数据", "启明互联",
    "优测科技", "矩阵实验室", "未来动力", "磐石云服", "灵犀智能", "方舟测试",
]
DEPARTMENTS = ["研发部", "测试部", "产品部", "运维部", "市场部", "销售部", "人力资源部", "财务部", "客服部"]
JOB_TITLES = [
    "测试工程师", "高级测试工程师", "测试开发工程师", "产品经理", "后端开发", "前端开发",
    "DevOps 工程师", "项目经理", "数据分析师", "UI 设计师",
]
PRODUCT_NAMES = [
    "无线蓝牙耳机 Pro", "机械键盘 RGB 版", "运动水杯 750ml", "智能手环 S3", "USB-C 扩展坞",
    "27 寸 4K 显示器", "人体工学椅", "便携投影仪", "氮化镓充电器", "降噪睡眠耳塞",
    "电竞鼠标", "固态硬盘 1TB", "路由器 WiFi6", "摄像头 1080P", "蓝牙音箱 Mini",
]
PRODUCT_CATEGORIES = ["数码配件", "电脑外设", "智能家居", "办公设备", "运动户外", "影音娱乐"]
ORDER_STATUSES = ["PENDING_PAY", "PAID", "SHIPPED", "DELIVERED", "CANCELLED", "REFUNDING"]
USER_ROLES = ["user", "vip", "admin", "tester", "guest"]
COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4", "#ec4899", "#14b8a6"]
SENTENCES = [
    "系统在高并发场景下响应稳定，接口平均耗时低于 200ms。",
    "用户在结算页提交订单后，库存扣减与订单状态同步更新。",
    "登录失败超过 5 次后，账号进入 15 分钟锁定状态。",
    "支付回调延迟到达时，订单状态仍保持幂等更新。",
    "搜索关键词为空时，返回默认推荐商品列表。",
]
PARAGRAPHS = [
    "本次测试覆盖登录、商品浏览、购物车、下单与支付全链路。重点验证 token 过期刷新、库存边界和优惠券叠加规则。",
    "需求文档要求支持分页查询、关键词搜索和多字段排序。需补充异常参数、空结果集及权限隔离场景。",
    "接口返回结构需包含 code、message、data 与 request_id，错误码需与文档保持一致。",
]

FIELD_TYPE_META: list[dict[str, Any]] = [
    {"value": "name", "label": "中文姓名", "group": "基础信息"},
    {"value": "username", "label": "用户名", "group": "基础信息"},
    {"value": "nickname", "label": "昵称", "group": "基础信息"},
    {"value": "gender", "label": "性别", "group": "基础信息"},
    {"value": "age", "label": "年龄", "group": "基础信息"},
    {"value": "id_card", "label": "身份证号", "group": "基础信息"},
    {"value": "email", "label": "邮箱", "group": "联系方式"},
    {"value": "phone", "label": "手机号", "group": "联系方式"},
    {"value": "password", "label": "密码", "group": "联系方式"},
    {"value": "address", "label": "详细地址", "group": "地址"},
    {"value": "city", "label": "城市", "group": "地址"},
    {"value": "province", "label": "省份", "group": "地址"},
    {"value": "postcode", "label": "邮编", "group": "地址"},
    {"value": "company", "label": "公司名称", "group": "职场"},
    {"value": "department", "label": "部门", "group": "职场"},
    {"value": "job_title", "label": "职位", "group": "职场"},
    {"value": "product_name", "label": "商品名称", "group": "电商"},
    {"value": "product_id", "label": "商品 ID", "group": "电商"},
    {"value": "sku", "label": "SKU 编码", "group": "电商"},
    {"value": "category", "label": "商品分类", "group": "电商"},
    {"value": "order_no", "label": "订单号", "group": "电商"},
    {"value": "order_status", "label": "订单状态", "group": "电商"},
    {"value": "price", "label": "价格", "group": "数值"},
    {"value": "amount", "label": "金额", "group": "数值"},
    {"value": "quantity", "label": "数量", "group": "数值"},
    {"value": "int", "label": "整数", "group": "数值"},
    {"value": "float", "label": "浮点数", "group": "数值"},
    {"value": "bool", "label": "布尔值", "group": "数值"},
    {"value": "score", "label": "评分(1-5)", "group": "数值"},
    {"value": "date", "label": "日期", "group": "时间"},
    {"value": "datetime", "label": "日期时间", "group": "时间"},
    {"value": "timestamp", "label": "时间戳", "group": "时间"},
    {"value": "uuid", "label": "UUID", "group": "标识"},
    {"value": "user_id", "label": "用户 ID", "group": "标识"},
    {"value": "token", "label": "Access Token", "group": "标识"},
    {"value": "url", "label": "网址", "group": "网络"},
    {"value": "avatar", "label": "头像 URL", "group": "网络"},
    {"value": "image_url", "label": "图片 URL", "group": "网络"},
    {"value": "ipv4", "label": "IPv4", "group": "网络"},
    {"value": "mac", "label": "MAC 地址", "group": "网络"},
    {"value": "bank_card", "label": "银行卡号", "group": "金融"},
    {"value": "color", "label": "颜色值", "group": "其他"},
    {"value": "role", "label": "用户角色", "group": "其他"},
    {"value": "sentence", "label": "短句描述", "group": "文本"},
    {"value": "paragraph", "label": "段落文本", "group": "文本"},
    {"value": "remark", "label": "备注", "group": "文本"},
    {"value": "string", "label": "随机字符串", "group": "文本"},
]

PRESETS: list[dict[str, Any]] = [
    {
        "id": "user",
        "name": "用户注册",
        "desc": "C 端用户基础资料，适合登录/注册接口",
        "icon": "User",
        "color": "#3b82f6",
        "fields": [
            {"name": "user_id", "type": "user_id"},
            {"name": "username", "type": "username"},
            {"name": "nickname", "type": "nickname"},
            {"name": "name", "type": "name"},
            {"name": "gender", "type": "gender"},
            {"name": "phone", "type": "phone"},
            {"name": "email", "type": "email"},
            {"name": "age", "type": "age"},
            {"name": "city", "type": "city"},
            {"name": "register_time", "type": "datetime"},
        ],
    },
    {
        "id": "order",
        "name": "电商订单",
        "desc": "订单列表、支付回调等场景",
        "icon": "ShoppingCart",
        "color": "#f59e0b",
        "fields": [
            {"name": "order_no", "type": "order_no"},
            {"name": "user_id", "type": "user_id"},
            {"name": "product_name", "type": "product_name"},
            {"name": "quantity", "type": "quantity"},
            {"name": "price", "type": "price"},
            {"name": "amount", "type": "amount"},
            {"name": "status", "type": "order_status"},
            {"name": "pay_channel", "type": "pay_channel"},
            {"name": "created_at", "type": "datetime"},
        ],
    },
    {
        "id": "product",
        "name": "商品 SKU",
        "desc": "商品管理、库存、列表查询",
        "icon": "Goods",
        "color": "#10b981",
        "fields": [
            {"name": "product_id", "type": "product_id"},
            {"name": "sku", "type": "sku"},
            {"name": "name", "type": "product_name"},
            {"name": "category", "type": "category"},
            {"name": "price", "type": "price"},
            {"name": "stock", "type": "quantity"},
            {"name": "score", "type": "score"},
            {"name": "cover_url", "type": "image_url"},
            {"name": "on_sale", "type": "bool"},
        ],
    },
    {
        "id": "employee",
        "name": "员工档案",
        "desc": "HR、权限、组织架构测试",
        "icon": "OfficeBuilding",
        "color": "#8b5cf6",
        "fields": [
            {"name": "emp_no", "type": "emp_no"},
            {"name": "name", "type": "name"},
            {"name": "gender", "type": "gender"},
            {"name": "department", "type": "department"},
            {"name": "job_title", "type": "job_title"},
            {"name": "phone", "type": "phone"},
            {"name": "email", "type": "email"},
            {"name": "hire_date", "type": "date"},
            {"name": "salary", "type": "amount"},
        ],
    },
    {
        "id": "api_auth",
        "name": "API 鉴权",
        "desc": "Token、角色、会话接口",
        "icon": "Key",
        "color": "#06b6d4",
        "fields": [
            {"name": "user_id", "type": "user_id"},
            {"name": "username", "type": "username"},
            {"name": "role", "type": "role"},
            {"name": "access_token", "type": "token"},
            {"name": "refresh_token", "type": "token"},
            {"name": "expires_in", "type": "expires_in"},
            {"name": "client_ip", "type": "ipv4"},
            {"name": "login_time", "type": "datetime"},
        ],
    },
    {
        "id": "logistics",
        "name": "物流地址",
        "desc": "收货地址、配送场景",
        "icon": "Location",
        "color": "#ec4899",
        "fields": [
            {"name": "consignee", "type": "name"},
            {"name": "phone", "type": "phone"},
            {"name": "province", "type": "province"},
            {"name": "city", "type": "city"},
            {"name": "address", "type": "address"},
            {"name": "postcode", "type": "postcode"},
            {"name": "is_default", "type": "bool"},
            {"name": "remark", "type": "remark"},
        ],
    },
]

_rng = random.Random()


def _pick(items: list[Any]) -> Any:
    return _rng.choice(items)


def _rand_date(days_back: int = 365) -> datetime:
    base = datetime.now() - timedelta(days=_rng.randint(0, days_back))
    return base.replace(
        hour=_rng.randint(8, 22),
        minute=_rng.randint(0, 59),
        second=_rng.randint(0, 59),
        microsecond=0,
    )


def _normalize_field_spec(spec: Any) -> dict[str, Any]:
    if isinstance(spec, dict):
        ftype = str(spec.get("type") or spec.get("field") or "string")
        return {"type": ftype, **{k: v for k, v in spec.items() if k not in ("type", "field")}}
    return {"type": str(spec)}


def generate_field(spec: Any, index: int = 0) -> Any:
    cfg = _normalize_field_spec(spec)
    ftype = cfg["type"]

    if ftype == "name":
        return _pick(SURNAMES) + _pick(GIVEN_NAMES) + (_pick(GIVEN_NAMES) if _rng.random() > 0.6 else "")
    if ftype == "username":
        return f"{_pick(['user', 'test', 'demo', 'qa', 'dev'])}{_rng.randint(100, 9999)}"
    if ftype == "nickname":
        prefixes = ["快乐的", "安静的", "机智的", "勤奋的", "神秘的"]
        return f"{_pick(prefixes)}{_pick(GIVEN_NAMES)}"
    if ftype == "gender":
        return _pick(["男", "女", "未知"])
    if ftype == "age":
        return _rng.randint(int(cfg.get("min", 18)), int(cfg.get("max", 60)))
    if ftype == "id_card":
        area = _rng.randint(110000, 659999)
        birth = _rand_date(365 * 40).strftime("%Y%m%d")
        seq = _rng.randint(100, 999)
        return f"{area}{birth}{seq}"
    if ftype == "email":
        domains = ["test.com", "example.com", "demo.cn", "mail.test", "qa.io"]
        local = "".join(_rng.choices(string.ascii_lowercase + string.digits, k=_rng.randint(5, 10)))
        return f"{local}@{_pick(domains)}"
    if ftype == "phone":
        prefix = _pick(["130", "131", "132", "133", "135", "136", "137", "138", "139",
                        "150", "151", "152", "157", "158", "159", "186", "187", "188", "189"])
        return prefix + "".join(str(_rng.randint(0, 9)) for _ in range(8))
    if ftype == "password":
        chars = string.ascii_letters + string.digits + "!@#$%"
        return "".join(_rng.choices(chars, k=_rng.randint(10, 16)))
    if ftype == "address":
        return f"{_pick(CITIES)}{_pick(DISTRICTS)}{_pick(STREETS)}{_rng.randint(1, 999)}号{_rng.randint(1, 30)}层"
    if ftype == "city":
        return _pick(CITIES)
    if ftype == "province":
        return _pick(CITIES) + "市"
    if ftype == "postcode":
        return str(_rng.randint(100000, 999999))
    if ftype == "company":
        return _pick(COMPANIES) + _pick(["有限公司", "股份有限公司", "科技中心", "研究院"])
    if ftype == "department":
        return _pick(DEPARTMENTS)
    if ftype == "job_title":
        return _pick(JOB_TITLES)
    if ftype == "emp_no":
        return f"EMP{_rand_date(365 * 5).strftime('%Y%m')}{_rng.randint(100, 999)}"
    if ftype == "product_name":
        return _pick(PRODUCT_NAMES)
    if ftype == "product_id":
        return 20000 + index + _rng.randint(1, 999)
    if ftype == "sku":
        return f"SKU-{_rand_date(120).strftime('%Y%m%d')}-{_rng.randint(1000, 9999)}"
    if ftype == "category":
        return _pick(PRODUCT_CATEGORIES)
    if ftype == "order_no":
        return f"ORD{datetime.now().strftime('%Y%m%d')}{_rng.randint(100000, 999999)}"
    if ftype == "order_status":
        return _pick(ORDER_STATUSES)
    if ftype == "pay_channel":
        return _pick(["wechat", "alipay", "unionpay", "balance"])
    if ftype == "price":
        return round(_rng.uniform(9.9, 9999.0), 2)
    if ftype == "amount":
        return round(_rng.uniform(19.9, 50000.0), 2)
    if ftype == "quantity":
        return _rng.randint(int(cfg.get("min", 1)), int(cfg.get("max", 99)))
    if ftype == "int":
        return _rng.randint(int(cfg.get("min", 1)), int(cfg.get("max", 1000)))
    if ftype == "float":
        return round(_rng.uniform(float(cfg.get("min", 1)), float(cfg.get("max", 1000))), 2)
    if ftype == "bool":
        return _rng.choice([True, False])
    if ftype == "score":
        return round(_rng.uniform(3.5, 5.0), 1)
    if ftype == "date":
        return _rand_date(int(cfg.get("days_back", 365))).strftime("%Y-%m-%d")
    if ftype == "datetime":
        return _rand_date(int(cfg.get("days_back", 365))).strftime("%Y-%m-%d %H:%M:%S")
    if ftype == "timestamp":
        return int(_rand_date(int(cfg.get("days_back", 365))).timestamp())
    if ftype == "uuid":
        return str(uuid.uuid4())
    if ftype == "user_id":
        return 10000 + index + _rng.randint(1, 5000)
    if ftype == "token":
        return f"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.{uuid.uuid4().hex[:16]}.{_rng.randint(1000, 9999)}"
    if ftype == "expires_in":
        return _pick([3600, 7200, 86400])
    if ftype == "url":
        slug = "".join(_rng.choices(string.ascii_lowercase, k=8))
        return f"https://demo.test/{slug}"
    if ftype == "avatar":
        return f"https://i.pravatar.cc/150?u={uuid.uuid4().hex[:8]}"
    if ftype == "image_url":
        return f"https://picsum.photos/seed/{uuid.uuid4().hex[:8]}/400/300"
    if ftype == "ipv4":
        return ".".join(str(_rng.randint(1, 254)) for _ in range(4))
    if ftype == "mac":
        parts = [f"{_rng.randint(0, 255):02x}" for _ in range(6)]
        return ":".join(parts)
    if ftype == "bank_card":
        return "6222" + "".join(str(_rng.randint(0, 9)) for _ in range(12))
    if ftype == "color":
        return _pick(COLORS)
    if ftype == "role":
        return _pick(USER_ROLES)
    if ftype == "sentence":
        return _pick(SENTENCES)
    if ftype == "paragraph":
        return _pick(PARAGRAPHS)
    if ftype == "remark":
        return _pick(["无", "尽快发货", "工作日配送", "放门口即可", "测试订单", "需要发票"])
    if ftype == "string":
        length = int(cfg.get("length", 8))
        return "".join(_rng.choices(string.ascii_letters + string.digits, k=length))

    options = cfg.get("options")
    if isinstance(options, list) and options:
        return _pick(options)
    return f"mock_{_rng.randint(1000, 9999)}"


def generate_mock_data(schema: dict[str, Any], count: int, seed: int | None = None) -> list[dict[str, Any]]:
    global _rng
    _rng = random.Random(seed if seed is not None else random.randrange(1, 10_000_000))
    result: list[dict[str, Any]] = []
    for index in range(count):
        item: dict[str, Any] = {}
        for field, spec in schema.items():
            item[field] = generate_field(spec, index=index)
        result.append(item)
    return result


def get_meta() -> dict[str, Any]:
    return {
        "field_types": FIELD_TYPE_META,
        "presets": PRESETS,
    }
