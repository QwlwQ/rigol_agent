"""Workflow repository boundary for future extracted/manual workflows."""
class WorkflowRepository:
    def __init__(self, workflows): self.workflows = workflows
    def get(self, name): return self.workflows[name]
