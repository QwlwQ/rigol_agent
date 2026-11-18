"""Separate task, conversation, and observation context boundary."""
class ContextManager:
    def __init__(self):
        self.task_context = {}
        self.observation_context = None
    def set_observation(self, observation): self.observation_context = observation
    def clear_observation(self): self.observation_context = None
