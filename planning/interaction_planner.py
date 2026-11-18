"""Next-interaction planning boundary for the future visual closed loop."""
class InteractionPlanner:
    def next_action(self, goal, observation):
        raise NotImplementedError("Interaction planning requires state recognition and execution feedback.")
