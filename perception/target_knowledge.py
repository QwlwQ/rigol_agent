from pathlib import Path
import yaml
from knowledge.visual_knowledge import load_visual_knowledge

class TargetKnowledge:
    def __init__(self, path=None, components_path=None):
        root = Path(__file__).resolve().parents[1]
        path = Path(path) if path else root / "data" / "knowledge" / "DHO804" / "visual_knowledge.yaml"
        components_path = Path(components_path) if components_path else root / "data" / "knowledge" / "DHO804" / "components.yaml"
        # Phase 2 deliberately removed the old fixed component YAML files.
        # Keep this adapter optional so the manual JSONL remains the source of
        # truth and the Phase 1 locator can still be used with arbitrary text.
        data = load_visual_knowledge(path) if path.is_file() else {}
        components_data = yaml.safe_load(components_path.read_text(encoding="utf-8")) if components_path.is_file() else {}
        data = data or {}
        components_data = components_data or {}
        self.targets = data.get("targets", {})
        self.channels = data.get("channels", {})
        self.global_prompt_rules = data.get("prompt_rules", [])
        self.screen_states = data.get("screen_states", {})
        self.operation_hints = data.get("operations", {})
        self.components = {item["name"]: item for item in components_data.get("components", [])}
        self.aliases = {}
        for name, item in {**self.targets, **self.channels}.items():
            for alias in [name, *item.get("aliases", [])]:
                self.aliases[str(alias).casefold()] = name
        for name, component in self.components.items():
            for alias in [name, *component.get("aliases", [])]:
                self.aliases[str(alias).casefold()] = name

    def resolve(self, target: str) -> str:
        return self.aliases.get(str(target).casefold(), target)

    def describe(self, target: str, state: str = "any") -> str:
        target = self.resolve(target)
        item = self.targets.get(target) or self.channels.get(target)
        if item and item.get("visual_description"):
            description = item["visual_description"]
            state_rules = item.get("state_rules", {})
            if state in state_rules:
                description += "\n" + str(state_rules[state])
            elif state in {"on", "off"}:
                description += f"\n要求目标处于 {state} 状态，并报告 observed_state。"
            for rule in item.get("prompt_rules", []):
                description += "\n" + str(rule)
            for rule in self.global_prompt_rules:
                description += "\n" + str(rule)
            return description
        component = self.components.get(target)
        if not component:
            return "未提供该目标的设备视觉映射；请根据图像直接判断，不要编造坐标。"
        kind = component.get("kind", "component")
        aliases = "、".join(str(value) for value in component.get("aliases", [])[:6])
        if kind == "channel":
            suffix = target[2:] if target.upper().startswith("CH") else target
            description = (f"Locate the channel control card for logical {target}. It belongs to the bottom "
                    f"channel-control strip and is usually identified by the visible channel number {suffix}. "
                    f"The literal text {target} may not be present; common semantic aliases include {aliases}.")
            if state == "on":
                description += " The requested state is ON/SELECTED: look for a bright highlighted card and the corresponding colored waveform or channel marker."
            elif state == "off":
                description += " The requested state is OFF/UNSELECTED: the card still exists and must be returned even without a waveform. Use the fixed card position and channel number; do not treat absence of a waveform as absence of the card."
            else:
                description += " State is not constrained: locate the card regardless of whether it is selected or unselected, and report observed_state as on, off, or unknown."
            return description
        if kind == "measurement_category":
            description = (f"Locate the {target} measurement category/tab inside the measurement panel. "
                    f"It may use a Chinese or localized label; aliases include {aliases}.")
            return description
        if kind == "measurement":
            description = (f"Locate the {target} measurement item inside the currently visible measurement panel. "
                    f"It may use a localized label; aliases include {aliases}. Do not search outside the panel.")
            if state == "on":
                description += " Require the selected/enabled visual state, such as lighter text or a highlighted border."
            elif state == "off":
                description += " Require the unselected/disabled visual state, such as normal or dim text without the selected border."
            else:
                description += " State is not constrained: return the item whenever its label or icon can be located, and report observed_state as on, off, or unknown. Do not reject the item merely because its state is unclear."
            return description
        if kind == "menu":
            return (f"Locate the {target} menu or control in the DHO804 interface. "
                    f"It may use a localized label; aliases include {aliases}.")
        return f"Locate the logical component {target}. Visible aliases include {aliases}. Do not invent coordinates."

    def screen_prompt(self) -> str:
        """Return YAML-defined screen-state guidance for the VLM prompt."""
        lines = []
        for name, item in self.screen_states.items():
            if isinstance(item, dict):
                description = item.get("description", "")
                if description:
                    lines.append(f"{name}: {description}")
            elif item:
                lines.append(f"{name}: {item}")
        lines.extend(str(rule) for rule in self.global_prompt_rules)
        return "\n".join(lines)
