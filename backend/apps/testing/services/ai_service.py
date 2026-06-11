import json
import re
from dataclasses import dataclass
from typing import Any

from django.conf import settings

from .json_utils import parse_json_from_llm, prepare_json_text


class AIServiceError(Exception):
    """大模型未配置或调用失败。"""


@dataclass
class AIConfig:
    provider: str
    api_key: str
    base_url: str
    model: str
    temperature: float = 0.7
    max_tokens: int = 4096
    name: str = ""


class AIService:
    """多厂商大模型服务，必须配置 API Key 后才可调用。"""

    CONFIG_HINT = "未配置大模型 API，请前往「系统管理 → 大模型配置 → AI 配置」填写或从 CC Switch 导入"

    def _load_config(self) -> AIConfig | None:
        from apps.ai_features.models import AIProviderConfig

        active = AIProviderConfig.objects.filter(is_active=True).first()
        if active:
            return AIConfig(
                provider=active.provider,
                api_key=active.api_key,
                base_url=active.base_url,
                model=active.model,
                temperature=active.temperature,
                max_tokens=active.max_tokens,
                name=active.name,
            )
        if settings.ZHIPUAI_API_KEY:
            return AIConfig(
                provider="zhipu",
                api_key=settings.ZHIPUAI_API_KEY,
                base_url="",
                model="glm-4-flash",
                name="环境变量 ZHIPUAI_API_KEY",
            )
        return None

    @classmethod
    def get_status(cls) -> dict[str, Any]:
        empty = {
            "configured": False,
            "source": "none",
            "provider": "",
            "provider_display": "",
            "model": "",
            "name": "",
            "masked_api_key": "",
        }
        config = cls()._load_config()
        if not config:
            return empty
        from apps.ai_features.models import AIProviderConfig

        active = AIProviderConfig.objects.filter(is_active=True).first()
        source = "database" if active else "env"
        provider_labels = dict(AIProviderConfig.PROVIDER_CHOICES)
        masked = active.masked_api_key if active else (
            f"{config.api_key[:4]}****{config.api_key[-4:]}" if len(config.api_key) > 8 else "****"
        )
        return {
            "configured": True,
            "source": source,
            "provider": config.provider,
            "provider_display": provider_labels.get(config.provider, config.provider),
            "model": config.model,
            "name": config.name,
            "masked_api_key": masked,
        }

    def _require_config(self) -> AIConfig:
        config = self._load_config()
        if not config or not config.api_key:
            raise AIServiceError(self.CONFIG_HINT)
        return config

    def _call_ai(self, prompt: str, *, include_skills: bool = True, temperature: float | None = None) -> str:
        from apps.ai_features.services.skills_service import get_skills_prompt_prefix

        config = self._require_config()
        prefix = get_skills_prompt_prefix() if include_skills else ""
        full_prompt = f"{prefix}{prompt}"
        temp = temperature if temperature is not None else config.temperature
        try:
            if config.provider == "zhipu":
                content = self._call_zhipu(config, full_prompt, temp)
            else:
                content = self._call_openai_compatible(config, full_prompt, temp)
        except AIServiceError:
            raise
        except Exception as exc:
            err = str(exc).lower()
            if "timeout" in err or "timed out" in err:
                raise AIServiceError(
                    f"大模型响应超时（>{int(self._ai_timeout())}s），请换用更快模型或缩短文档/Skills 内容"
                ) from exc
            raise AIServiceError(f"大模型调用失败: {exc}") from exc
        if not content.strip():
            raise AIServiceError("大模型返回空内容，请检查模型名称与 API 配额")
        return content

    def _ai_timeout(self) -> float:
        return float(getattr(settings, "AI_CALL_TIMEOUT", 180))

    def _call_zhipu(self, config: AIConfig, prompt: str, temperature: float | None = None) -> str:
        from zhipuai import ZhipuAI

        client = ZhipuAI(api_key=config.api_key, timeout=self._ai_timeout())
        response = client.chat.completions.create(
            model=config.model or "glm-4-flash",
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature if temperature is not None else config.temperature,
        )
        return response.choices[0].message.content or ""

    def _call_openai_compatible(self, config: AIConfig, prompt: str, temperature: float | None = None) -> str:
        from openai import OpenAI

        if not config.base_url:
            raise AIServiceError("OpenAI 兼容厂商需配置 Base URL")
        client = OpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=self._ai_timeout(),
        )
        response = client.chat.completions.create(
            model=config.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature if temperature is not None else config.temperature,
            max_tokens=config.max_tokens,
        )
        return response.choices[0].message.content or ""

    def test_connection(self, config: AIConfig | None = None) -> str:
        if config is None:
            config = self._require_config()
        prompt = "请仅回复：连接成功"
        if config.provider == "zhipu":
            return self._call_zhipu(config, prompt)
        return self._call_openai_compatible(config, prompt)

    def _parse_json_with_repair(self, raw: str, kind: str) -> Any:
        assert kind in ("object", "array")
        try:
            return parse_json_from_llm(raw, kind)  # type: ignore[arg-type]
        except ValueError:
            pass

        broken = prepare_json_text(raw, kind)  # type: ignore[arg-type]
        repair_prompt = (
            "以下 JSON 存在语法错误。请只输出修正后的合法 JSON，"
            "不要 markdown 代码块，不要任何解释文字：\n\n"
            f"{broken[:12000]}"
        )
        try:
            fixed_raw = self._call_ai(repair_prompt, include_skills=False, temperature=0.1)
            return parse_json_from_llm(fixed_raw, kind)  # type: ignore[arg-type]
        except (ValueError, AIServiceError) as exc:
            preview = broken[:200].replace("\n", " ")
            raise AIServiceError(f"大模型返回 JSON 无法解析，请重试或换用模型。片段: {preview}…") from exc

    def _parse_json_array(self, raw: str) -> list[dict[str, Any]]:
        data = self._parse_json_with_repair(raw, "array")
        if not isinstance(data, list):
            raise AIServiceError("大模型返回格式异常，期望 JSON 数组")
        return data

    def _parse_json_object(self, raw: str) -> dict[str, Any]:
        data = self._parse_json_with_repair(raw, "object")
        if not isinstance(data, dict):
            raise AIServiceError("大模型返回格式异常，期望 JSON 对象")
        return data

    def generate_requirements(self, content: str) -> list[dict[str, Any]]:
        prompt = (
            "你是资深测试工程师。根据以下需求文档内容，提取功能需求，"
            "以 JSON 数组返回，每项包含 module、name、description 字段。只返回 JSON，不要其他说明。\n\n"
            f"文档内容:\n{content[:4000]}"
        )
        raw = self._call_ai(prompt)
        return self._parse_json_array(raw)

    def parse_requirement_detail(self, content: str) -> dict[str, list[dict[str, Any]]]:
        prompt = (
            "你是资深测试分析师。从需求文档中提取结构化信息，严格输出合法 JSON 对象。\n"
            "要求：\n"
            "1. 仅包含 features、constraints、exceptions 三个键，值均为数组\n"
            "2. 数组每项仅含 module、name、description 三个字符串字段\n"
            "3. 不要使用 trailing comma，不要注释，不要 markdown 代码块\n"
            "4. description 尽量简洁（50字内），避免未转义的双引号\n\n"
            "输出格式示例：\n"
            '{"features":[{"module":"订单","name":"创建订单","description":"用户提交订单"}],"constraints":[],'
            '"exceptions":[]}\n\n'
            f"文档内容:\n{content[:5000]}"
        )
        raw = self._call_ai(prompt, temperature=0.2)
        data = self._parse_json_object(raw)
        return {
            "features": data.get("features", []),
            "constraints": data.get("constraints", []),
            "exceptions": data.get("exceptions", []),
        }

    def generate_test_points(
        self,
        requirement_name: str,
        description: str,
        strategy: str = "default",
        rag_context: str = "",
    ) -> list[dict[str, Any]]:
        strategy_map = {
            "equivalence": "等价类划分",
            "boundary": "边界值分析",
            "scenario": "场景法",
            "state": "状态迁移法",
            "default": "综合测试设计",
        }
        strategy_text = strategy_map.get(strategy, "综合测试设计")
        rag_part = f"\n参考知识:\n{rag_context[:2000]}" if rag_context else ""
        prompt = (
            f"你是资深测试工程师。使用【{strategy_text}】为需求生成测试点，"
            "以 JSON 数组返回，每项包含 name、description、point_type(functional/boundary/exception/security)。"
            "只返回 JSON，不要其他说明。"
            f"{rag_part}\n\n需求: {requirement_name}\n描述: {description}"
        )
        raw = self._call_ai(prompt)
        return self._parse_json_array(raw)

    def analyze_execution(self, results: list[dict]) -> str:
        prompt = (
            "你是测试分析专家。根据以下测试执行结果，给出简洁的失败原因分析与改进建议（200字内）。\n\n"
            f"结果: {json.dumps(results[:20], ensure_ascii=False)}"
        )
        return self._call_ai(prompt)

    def generate_test_cases(
        self,
        test_point_name: str,
        description: str = "",
        strategy: str = "default",
        point_type: str = "functional",
        rag_context: str = "",
        field_definitions: list[dict[str, Any]] | None = None,
        module_hint: str = "",
    ) -> list[dict[str, Any]]:
        strategy_map = {
            "equivalence": "等价类划分",
            "boundary": "边界值分析",
            "scenario": "场景法",
            "state": "状态迁移法",
            "default": "综合测试设计",
        }
        strategy_text = strategy_map.get(strategy, "综合测试设计")
        rag_part = f"\n参考知识:\n{rag_context[:2000]}" if rag_context else ""
        if field_definitions:
            keys = [f["key"] for f in field_definitions]
            field_lines = []
            for f in field_definitions:
                line = f"- {f['key']}: {f['label']}"
                if f.get("field_type") == "priority":
                    line += "，取值 P0/P1/P2/P3"
                elif f.get("options"):
                    line += f"，取值 {'/'.join(f['options'])}"
                elif f.get("field_type") == "passed":
                    line += "，可留空"
                elif f.get("required"):
                    line += "，必填"
                field_lines.append(line)
            fields_text = "\n".join(field_lines)
            required_keys = [f["key"] for f in field_definitions if f.get("required")]
            required_part = (
                f"必填字段不可为空: {', '.join(required_keys)}。"
                if required_keys
                else ""
            )
            prompt = (
                f"你是资深测试工程师。使用【{strategy_text}】根据测试点生成测试用例。\n"
                "严格按以下字段配置输出 JSON 数组，每项对象的键名必须与配置完全一致，不要增减字段：\n"
                f"{fields_text}\n"
                f"{required_part}passed、actual 可留空。只返回 JSON，不要其他说明。"
                f"{rag_part}\n\n"
                f"测试点: {test_point_name}\n"
                f"模块: {module_hint}\n"
                f"类型: {point_type}\n"
                f"描述: {description}\n"
                f"允许使用的键名（仅此列表）: {', '.join(keys)}"
            )
        else:
            prompt = (
                f"你是资深测试工程师。使用【{strategy_text}】为测试点生成1条核心用例。\n"
                "以 JSON 数组返回，每项仅含 title、module、steps、expected、priority(P0-P3)，不要其他字段。"
                "只返回 JSON。"
                f"{rag_part}\n\n"
                f"测试点: {test_point_name}\n"
                f"模块: {module_hint}\n"
                f"类型: {point_type}\n"
                f"描述: {description}"
            )
        raw = self._call_ai(prompt)
        return self._parse_json_array(raw)

    def generate_test_cases_batch(
        self,
        test_points: list[dict[str, str]],
        strategy: str = "default",
        rag_context: str = "",
    ) -> list[dict[str, Any]]:
        """一次请求为多个测试点生成用例，减少 API 调用次数。"""
        strategy_map = {
            "equivalence": "等价类划分",
            "boundary": "边界值分析",
            "scenario": "场景法",
            "state": "状态迁移法",
            "default": "综合测试设计",
        }
        strategy_text = strategy_map.get(strategy, "综合测试设计")
        rag_part = f"\n参考知识:\n{rag_context[:1500]}" if rag_context else ""
        lines = []
        for idx, tp in enumerate(test_points, 1):
            lines.append(
                f"{idx}. 名称:{tp['name']} | 模块:{tp.get('module', '')} | "
                f"类型:{tp.get('point_type', '')} | 描述:{tp.get('description', '')[:120]}"
            )
        points_text = "\n".join(lines)
        prompt = (
            f"你是资深测试工程师。使用【{strategy_text}】为下列每个测试点各生成1条核心用例。\n"
            "返回 JSON 数组，每项必须含 test_point(对应测试点名称)、title、module、steps、expected、priority(P0-P3)。\n"
            "不要生成 case_no、precondition、postcondition 等额外字段。只返回 JSON。"
            f"{rag_part}\n\n"
            f"测试点列表:\n{points_text}"
        )
        raw = self._call_ai(prompt)
        return self._parse_json_array(raw)

    def generate_api_cases(self, api_info: dict, full: bool = True) -> list[dict[str, Any]]:
        scope = "全面" if full else "正向"
        prompt = (
            f"你是接口测试工程师。为以下接口生成{scope}测试用例，"
            "以 JSON 数组返回，每项包含 title、params、validate_content。只返回 JSON，不要其他说明。\n\n"
            f"接口信息: {json.dumps(api_info, ensure_ascii=False)}"
        )
        raw = self._call_ai(prompt)
        return self._parse_json_array(raw)

    def parse_api_document(self, content: str) -> list[dict[str, Any]]:
        """AI 解析（Markdown 规则解析失败时的回退）。"""
        prompt = (
            "你是接口文档解析专家。从接口文档中提取所有 API，"
            "以 JSON 数组返回，每项包含："
            "name、module、method、url、headers(对象)、params(对象)、body(对象)、"
            "response(对象，完整响应示例)、description。"
            "不要输出 response_fields，减少体积。只返回 JSON 数组。\n\n"
            f"接口文档:\n{content[:20000]}"
        )
        raw = self._call_ai(prompt)
        data = self._parse_json_with_repair(raw, "array")
        if not isinstance(data, list):
            raise AIServiceError("大模型返回格式异常，期望 JSON 数组")
        return data

    def contract_test(self, api_spec: str) -> dict[str, Any]:
        from apps.ai_features.services.contract_test_service import run_contract_test

        ai_result: dict[str, Any] | None = None
        if self._load_config():
            prompt = (
                "你是契约测试专家。分析以下 OpenAPI/Swagger 规范，找出契约不一致、缺失字段、"
                "响应定义不完整等问题。\n"
                "严格要求：summary、violations 中每项的 message、fix 必须使用简体中文；"
                "severity 仅允许 error、warning、info；"
                "violations 每项还需包含 fix(修复建议文字) 和 auto_fixable(是否可自动修复，布尔)。\n"
                "返回 JSON 对象，包含 violations(数组，每项有 field/message/severity/fix/auto_fixable)、"
                "summary 字段。只返回 JSON，不要其他说明。\n\n"
                f"API规范:\n{api_spec[:12000]}"
            )
            try:
                raw = self._call_ai(prompt, temperature=0.2)
                ai_result = self._parse_json_object(raw)
            except AIServiceError:
                ai_result = None
        return run_contract_test(api_spec, ai_result)

    def coverage_analysis(self, code_or_cases: str) -> dict[str, Any]:
        prompt = (
            "你是测试覆盖率分析专家。根据以下代码或用例信息，"
            "评估测试覆盖情况并给出可执行的补充建议。\n"
            "严格要求：summary、uncovered、suggestions 中所有文字必须使用简体中文。\n"
            "返回 JSON 对象，包含 summary(字符串)、line_coverage(0-100 数字)、"
            "branch_coverage(0-100 数字)、uncovered(字符串数组，未覆盖模块/函数/场景)、"
            "suggestions(字符串数组，改进建议)。只返回 JSON，不要其他说明。\n\n"
            f"内容:\n{code_or_cases[:8000]}"
        )
        raw = self._call_ai(prompt, temperature=0.3)
        data = self._parse_json_object(raw)
        line_cov = data.get("line_coverage", 0)
        branch_cov = data.get("branch_coverage", 0)
        try:
            line_cov = max(0, min(100, int(float(line_cov))))
            branch_cov = max(0, min(100, int(float(branch_cov))))
        except (TypeError, ValueError):
            line_cov, branch_cov = 0, 0
        return {
            "summary": data.get("summary") or "覆盖率分析完成",
            "line_coverage": line_cov,
            "branch_coverage": branch_cov,
            "uncovered": data.get("uncovered") if isinstance(data.get("uncovered"), list) else [],
            "suggestions": data.get("suggestions") if isinstance(data.get("suggestions"), list) else [],
        }

    def log_analysis(self, logs: str) -> dict[str, Any]:
        from apps.ai_features.services.log_analysis_service import analyze_logs_local, merge_log_analysis

        local = analyze_logs_local(logs)
        if not self._load_config():
            return local

        prompt = (
            "你是日志分析专家。分析以下测试或系统日志，识别错误模式与根因。\n"
            "严格要求：summary、patterns 中 pattern/suggestion 必须使用简体中文。\n"
            "返回 JSON 对象，包含 summary、error_count(整数)、warning_count(整数)、"
            "patterns(数组，每项含 pattern/count/suggestion)。只返回 JSON，不要其他说明。\n\n"
            f"日志:\n{logs[:8000]}"
        )
        try:
            raw = self._call_ai(prompt, temperature=0.2)
            ai_data = self._parse_json_object(raw)
            return merge_log_analysis(local, ai_data)
        except AIServiceError:
            return local
