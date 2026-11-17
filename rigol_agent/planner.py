import json
import re
from .models import AgentError, Proposal, Intent, Task, Subtask, Step

def _optimized_measurement_tasks(knowledge, intents):
    """Expand measurement intents with task-local UI state only.

    The state describes what this generated JSON is expected to leave on the
    screen; it is not an observation of the real device.
    """
    groups = []
    current_channel = None
    current_category = "Vertical"
    menu_open = False
    for intent in intents:
        params, _ = knowledge.expand(intent, None)
        channel, category, item = params["channel"], params["category"], params["item"]
        if current_channel != channel:
            if menu_open:
                groups[-1]["steps"].append(Step(component="Close-Measurement", action="click"))
                # Closing and reopening Measure resets the instrument UI to
                # the default Vertical category.
                current_category = "Vertical"
                menu_open = False
            groups.append({"intent": intent, "params": params, "steps": []})
            groups[-1]["steps"].append(Step(component=channel, action="click"))
            groups[-1]["steps"].append(Step(component="Measure", action="click"))
            menu_open = True
            current_channel = channel
        else:
            groups.append({"intent": intent, "params": params, "steps": []})
        if current_category != category:
            groups[-1]["steps"].append(Step(component=category, action="click"))
            current_category = category
        groups[-1]["steps"].append(Step(component=item, action="click"))
    if groups and menu_open:
        groups[-1]["steps"].append(Step(component="Close-Measurement", action="click"))
        current_category = "Vertical"
        menu_open = False
    return groups

class Planner:
    def __init__(self, knowledge, llm=None):
        self.knowledge = knowledge
        self.llm = llm

    def parse(self, text, history):
        if not self.knowledge.workflows:
            raise AgentError("正式知识库尚未配置。请提供原项目资料，或显式使用 --profile demo。")
        # Reject explicitly named unknown channels before any probabilistic interpretation.
        for channel in re.findall(r"CH\d+", text, flags=re.I):
            self.knowledge.resolve(channel)
        # Registered workflows are deterministic: do not spend an LLM call on
        # a known operation, otherwise the model can invent an unregistered name.
        try:
            return self.deterministic_parse(text)
        except AgentError as deterministic_error:
            if not self.llm:
                raise deterministic_error
            system = "你是 Rigol 任务规划器。只输出 JSON 任务提案，不能保存或执行。测量任务优先使用 workflow=measurement，并填写 channel、category、item；程序会自动生成无状态步骤：通道→Measure→分类→测量项。category 只能是 Vertical、Horizontal、Other；item 必须属于对应分类。其他没有合适 workflow 的任务使用 workflow=dynamic_steps，并按顺序输出原子步骤。dynamic_steps 只能使用领域配置中的组件和动作，不能创造组件、动作或坐标。缺失参数留空，不能猜测。仅根据用户明确意图使用上下文。格式 Schema：" + json.dumps(Proposal.model_json_schema(), ensure_ascii=False)
            system += "\n领域配置：" + json.dumps(self.knowledge.prompt_data(),ensure_ascii=False)
            return self.llm.propose([{"role":"system","content":system}, *history, {"role":"user","content":text}])

    def deterministic_parse(self, text):
        # Deterministic fast path for registered workflows; never silently drop clauses.
        parts = re.split(r"然后|最后|接着|再(?=测量|点击|切换)|[，,；;\n]", text)
        intents = []
        for raw in parts:
            part = raw.strip(" 。.!！")
            if not part:
                continue
            for prefix in ("先", "再", "请", "帮我"):
                if part.startswith(prefix):
                    part = part[len(prefix):]
            part = part.replace("一下", "")
            matched = None
            for name, w in self.knowledge.workflows.items():
                if any(p in part for p in w["phrases"]):
                    matched = (name,w)
                    break
            if matched is None:
                raise AgentError("当前配置无法直接匹配该需求，将交由 LLM 规划：" + part)
            name,w = matched
            params = {}
            rest = part
            for key,spec in w["parameters"].items():
                matches = []
                for alias, canonical in sorted(self.knowledge.aliases.items(), key=lambda p:-len(p[0])):
                    if spec["kind"] != "component" and self.knowledge.components[canonical]["kind"] != spec["kind"]:
                        continue
                    pattern = re.escape(alias)
                    if alias.isascii():
                        pattern = r"(?<![A-Za-z0-9])" + pattern + r"(?![A-Za-z0-9])"
                    if re.search(pattern, rest, re.I):
                        matches.append(canonical)
                        rest = re.sub(pattern,"",rest,flags=re.I)
                if len(set(matches)) > 1:
                    raise AgentError("同一子任务包含多个组件，请拆分成有序子任务。")
                if matches:
                    params[key] = matches[0]
            for phrase in sorted(w["phrases"],key=len,reverse=True):
                rest = rest.replace(phrase, "")
            rest = rest.replace("测量", "").replace("测量值", "").replace("电压", "").replace("的", "").strip()
            if rest:
                raise AgentError("当前配置无法识别或不支持：" + rest)
            intents.append(Intent(workflow=name,parameters=params))
        return Proposal(task_name="rigol_task",description=text,tasks=intents)

    def build(self, proposal):
        subtasks = []
        measurement_intents = [i for i in proposal.tasks if not i.is_dynamic and i.workflow == "measurement"]
        optimized = _optimized_measurement_tasks(self.knowledge, measurement_intents)
        optimized_by_id = {id(group["intent"]): group for group in optimized}
        for index, intent in enumerate(proposal.tasks, start=1):
            if intent.is_dynamic:
                if intent.workflow not in (None, "dynamic_steps"):
                    raise AgentError("动态步骤不能同时指定其他 workflow")
                if not intent.steps:
                    raise AgentError("动态任务缺少 steps")
                steps = []
                for raw_step in intent.steps:
                    component = self.knowledge.resolve(raw_step.component)
                    step = raw_step.model_copy(update={"component": component})
                    self.knowledge.validate_step(step)
                    steps.append(step)
                params = intent.parameters
                workflow = "dynamic_steps"
                name = f"dynamic_steps_{index}"
            else:
                if not intent.workflow:
                    raise AgentError("任务缺少 workflow 或 dynamic steps")
                params,steps = self.knowledge.expand(intent,proposal)
                if intent.workflow == "measurement":
                    group = optimized_by_id[id(intent)]
                    params, steps = group["params"], group["steps"]
                workflow = intent.workflow
                name = intent.workflow
            subtasks.append(Subtask(task_name=name, workflow=workflow, parameters=params,steps=steps))
        return Task(task_name=proposal.task_name,description=proposal.description,
                    knowledge_profile=self.knowledge.profile,knowledge_digest=self.knowledge.digest,tasks=subtasks)

class TaskValidator:
    def __init__(self, knowledge):
        self.knowledge = knowledge

    def validate(self, task):
        task = Task.model_validate(task.model_dump())
        k = self.knowledge
        if task.knowledge_digest != k.digest or task.knowledge_profile != k.profile:
            raise AgentError("任务知识配置版本不匹配，需重新规划。")
        if sum(len(t.steps) for t in task.tasks) > k.constraints["max_steps"]:
            raise AgentError("任务步骤数超出限制")
        seen = set()
        measurement_tasks = [t for t in task.tasks if t.workflow == "measurement"]
        expected_measurements = _optimized_measurement_tasks(k, [Intent(workflow="measurement", parameters=t.parameters) for t in measurement_tasks])
        expected_by_index = iter(expected_measurements)
        for t in task.tasks:
            if t.workflow == "dynamic_steps":
                for step in t.steps:
                    k.validate_step(step)
                expected = t.steps
            elif t.workflow == "measurement":
                expected = next(expected_by_index)["steps"]
                if expected != t.steps:
                    raise AgentError("测量步骤或关闭顺序不符合无状态规划规则")
            else:
                _, expected = k.expand(Intent(workflow=t.workflow,parameters=t.parameters), None)
                if expected != t.steps:
                    raise AgentError("步骤或顺序不符合工作流模板")
            missing = set(k.constraints["workflow_dependencies"].get(t.workflow,[])) - seen
            if missing:
                raise AgentError("缺少前置任务：" + ",".join(sorted(missing)))
            seen.add(t.workflow)
        for pair in k.constraints["forbidden_workflow_pairs"]:
            if set(pair) <= seen:
                raise AgentError("任务组合被禁止")
        return task
