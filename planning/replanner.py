"""Replanning boundary for future execution feedback."""
class Replanner:
    def replan(self, goal, observation, failure):
        raise NotImplementedError("Replanning requires an execution state and observed device feedback.")
