"""Execution-state validation boundary for a later visual closed loop."""
class StateValidator:
    def validate(self, expected, observation):
        raise NotImplementedError("State validation requires the future observation model.")
