"""Workflow matching boundary reserved for the validated workflow repository."""
class WorkflowMatcher:
    def __init__(self, knowledge): self.knowledge = knowledge
    def match(self, text):
        return [name for name, workflow in self.knowledge.workflows.items() if any(p in text for p in workflow.get("phrases", []))]
