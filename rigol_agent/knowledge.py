import hashlib
import json
from pathlib import Path
import re
import yaml
from .models import AgentError, Clarification, Proposal, Step

class Knowledge:
    def __init__(self, directory):
        self.directory = Path(directory)
        data = {}
        for name in ("metadata", "components", "operations", "workflows", "constraints"):
            try:
                data.update(yaml.safe_load((self.directory / f"{name}.yaml").read_text(encoding="utf-8")))
            except (OSError, yaml.YAMLError, TypeError) as exc:
                raise AgentError(f"无法读取知识配置 {name}: {type(exc).__name__}") from None
        self.profile = data["metadata"]["profile"]
        if self.profile != "demo" and not data["metadata"].get("verified"):
            if data["components"] or data["workflows"]:
                raise AgentError("正式配置必须核实来源并设置 metadata.verified。")
        self.digest = hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        self.components = {}
        self.aliases = {}
        self.operations = data["operations"]
        self.workflows = data["workflows"]
        self.constraints = data["constraints"]
        for c in data["components"]:
            if c["name"] in self.components:
                raise AgentError("重复组件名称")
            self.components[c["name"]] = c
            for alias in [c["name"], *c.get("aliases", [])]:
                key = alias.casefold()
                if key in self.aliases and self.aliases[key] != c["name"]:
                    raise AgentError("组件别名冲突: " + alias)
                self.aliases[key] = c["name"]
            if not set(c["actions"]) <= set(self.operations):
                raise AgentError("组件引用了未知动作")
        for name,w in self.workflows.items():
            if not w["steps"]:
                raise AgentError("工作流不能为空: " + name)
            for step in w["steps"]:
                c = step["component"]
                if c.startswith("{") and c.endswith("}"):
                    if c[1:-1] not in w["parameters"]:
                        raise AgentError("工作流占位符未声明")
                else:
                    self.validate_step(Step(**step))
                if step["action"] not in self.operations:
                    raise AgentError("工作流引用未知动作")

    def resolve(self, value):
        try:
            return self.aliases[value.casefold()]
        except KeyError:
            raise AgentError(f"当前配置不支持组件：{value}") from None

    def validate_step(self, step):
        if step.component not in self.components:
            raise AgentError("不支持组件：" + step.component)
        if step.action not in self.operations or step.action not in self.components[step.component]["actions"]:
            raise AgentError("不支持动作：" + step.action)
        if {"component":step.component,"action":step.action} in self.constraints["forbidden_pairs"]:
            raise AgentError("操作被约束禁止")

    def expand(self, intent, proposal):
        if intent.workflow not in self.workflows:
            raise AgentError("不支持工作流：" + intent.workflow)
        w = self.workflows[intent.workflow]
        if set(intent.parameters) - set(w["parameters"]):
            raise AgentError("工作流含未知参数")
        params = dict(intent.parameters)
        # Vertical is the instrument's default measurement category. If the
        # user names a vertical item without naming a category, infer it.
        if intent.workflow == "measurement" and not params.get("category") and params.get("item"):
            item_name = self.resolve(params["item"])
            category_items = {
                "Vertical": {"Maximum", "Minimum", "Peak-to-Peak", "Top", "Base", "Amplitude"},
                "Horizontal": {"Period", "Frequency", "Positive-Duty", "Negative-Duty"},
                "Other": {"Delay", "Phase"},
            }
            for category_name, items in category_items.items():
                if item_name in items:
                    params["category"] = category_name
                    break
        for key, spec in w["parameters"].items():
            if not params.get(key):
                if spec.get("required"):
                    choices = [n for n,c in self.components.items() if spec["kind"] == "component" or c["kind"] == spec["kind"]]
                    raise Clarification(f"请为 {intent.workflow} 提供 {key}：{' / '.join(choices)}", proposal)
                continue
            params[key] = self.resolve(params[key])
            if spec["kind"] != "component" and self.components[params[key]]["kind"] != spec["kind"]:
                raise AgentError(f"参数 {key} 必须是 {spec['kind']}")
        if intent.workflow == "measurement":
            category = params["category"]
            item = params["item"]
            category_name = self.components[category]["name"]
            allowed = {
                "Vertical": {"Maximum", "Minimum", "Peak-to-Peak", "Top", "Base", "Amplitude"},
                "Horizontal": {"Period", "Frequency", "Positive-Duty", "Negative-Duty"},
                "Other": {"Delay", "Phase"},
            }
            if item not in allowed.get(category_name, set()):
                raise AgentError(f"测量项 {item} 不属于测量分类 {category_name}")
        steps = []
        for spec in w["steps"]:
            step = Step(component=spec["component"].format(**params), action=spec["action"])
            self.validate_step(step)
            steps.append(step)
        return params, steps

    def prompt_data(self):
        return {"components":list(self.components.values()), "workflows":self.workflows, "constraints":self.constraints}
