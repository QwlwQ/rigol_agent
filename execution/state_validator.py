"""Conservative validation for observations before and after a click."""
from __future__ import annotations

from models.observation import Observation


class StateValidator:
    def validate(self, expected, observation: Observation) -> bool:
        if not isinstance(observation, Observation):
            return False
        if isinstance(expected, Observation):
            if expected.screen_state != "unknown" and observation.screen_state != expected.screen_state:
                return False
            for item in expected.components:
                if not any(candidate.target.casefold() == item.target.casefold() and candidate.observed_state.casefold() == item.observed_state.casefold() for candidate in observation.components):
                    return False
            return True
        if isinstance(expected, str):
            return observation.screen_state == expected
        if not isinstance(expected, dict):
            return False
        if expected.get("screen_state") and observation.screen_state != expected["screen_state"]:
            return False
        target = expected.get("target")
        state = expected.get("observed_state") or expected.get("state")
        if target and state:
            return any(item.target.casefold() == str(target).casefold() and item.observed_state.casefold() == str(state).casefold() for item in observation.components)
        return True

    def transition(self, before: Observation, after: Observation, *, target: str, from_state: str | None = None, to_state: str | None = None) -> bool:
        """Validate an expected component state transition after an action."""
        before_item = next((item for item in before.components if item.target.casefold() == target.casefold()), None)
        after_item = next((item for item in after.components if item.target.casefold() == target.casefold()), None)
        if before_item is None or after_item is None:
            return False
        if from_state and before_item.observed_state.casefold() != from_state.casefold():
            return False
        if to_state and after_item.observed_state.casefold() != to_state.casefold():
            return False
        return True
