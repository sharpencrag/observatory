from __future__ import annotations
import typing as t
from abc import ABC, abstractmethod
import enum

from observatory.events import EventHook


#: Generic type variable
T = t.TypeVar("T")


#: Type variable for objects that get bound to instances.
TBindable = t.TypeVar("TBindable", bound="_Bindable")


#: Type alias for a state transition mapping.
TriggerMapping = t.Dict[t.Tuple["State", "State|None"], "Trigger"]


class StateTransitionError(Exception):
    """Catch-all exception for state transition errors."""


class TriggerValidityError(Exception):
    """Raised when triggers are called from an invalid state"""


class ObjectBindingError(Exception):
    """Raised when there is an issue with an object's binding to an instance"""


class _Bindable(ABC):
    """Abstract descriptor that binds an item to a Machine instance.

    This behaves similarly to old-style methods, where the instance obtained
    from a class is different from the one obtained from an instance:

        ```py
        class XClass:
            bindable = SomeBindable()

        x_instance = XClass()
        assert x_instance.bindable is not XClass.bindable
        ```
    """

    _bound_instances: t.Dict[t.Tuple["_Bindable", Machine], "_Bindable"] = dict()

    def __init__(self):
        self._bound_to: Machine | None = None

    @abstractmethod
    def _copy(self: TBindable) -> TBindable:
        """Return a copy of the bindable.

        This method should be overridden by subclasses to return a copy of
        the instance with whatever information necessary.
        """
        raise NotImplementedError

    def bound_to(self: TBindable, machine: Machine) -> TBindable:
        bound_instance = self._bound_instances.get((self, machine))
        if bound_instance is None:
            bound_instance = self._copy()
            bound_instance._bound_to = machine
            self._bound_instances[(self, machine)] = bound_instance
        return bound_instance

    def __get__(self: TBindable, instance: Machine, _) -> TBindable:
        if instance is None:
            return self
        return self.bound_to(instance)


class AbstractAttribute:
    """An abstract class attribute.

    Use this in an abstract base class when an attribute MUST be overridden by
    subclasses, and is not intended to be used as a property.

    """

    __isabstractmethod__ = True

    def __new__(cls, *args, **kwargs):
        return super().__new__(cls)

    def __get__(self, _, __):
        return self


def abstractattribute() -> t.Any:
    """Return an abstract attribute.

    This is a convenience function that returns an instance of the
    AbstractAttribute class while preserving type hints, similar to
    the dataclass.field() function.
    """
    return AbstractAttribute()


class Machine(ABC):
    """Abstract state machine"""

    #: The default or "resting" state for the machine.
    default_state: "State" = abstractattribute()

    #: emitted after a state change has occurred
    updated: EventHook["State", "State"] = EventHook()

    def __init__(self):
        self._state = self.default_state
        self._states: t.Dict[str, State] = dict()
        self._triggers: t.Dict[str, Trigger] = dict()
        self._trigger_transitions: TriggerMapping = dict()
        self._init_states()
        self._init_triggers()

    def _init_states(self):
        """Gather the states stored on the class definition of this instance."""
        for name in dir(type(self)):
            if name == "default_state":
                continue
            state = getattr(self, name)
            if isinstance(state, State):
                self._states[name] = state

    def add_state(self, state: "State", name: str):
        """Add a named state to the machine.

        Note that without also adding Triggers, the state cannot be visited.
        """
        self._states[name] = state

    def _init_triggers(self):
        """Gather triggers defined on the class definition of this instance."""
        for name in dir(type(self)):
            trigger = getattr(self, name)
            if not isinstance(trigger, Trigger):
                continue
            self._triggers[name] = trigger
            trigger.name = name
            for trans in trigger.transitions:
                self._trigger_transitions[(trans.source, trans.target)] = trigger

    def add_trigger(self, trigger: Trigger, name: str):
        """Add a named trigger to the state machine."""
        trigger._bound_to = self
        trigger.name = name
        self._triggers[name] = trigger
        for transition in trigger.transitions:
            self._trigger_transitions[(transition.source, transition.target)] = trigger

    def get_state(self) -> State:
        """Return the current state of the state machine."""
        return self._state

    def _set_state(self, new_state: State):
        """Set the state and trigger appropriate callbacks."""
        old_state = self._state
        self._state = new_state
        old_state.exited.emit()
        new_state.entered.emit()

    def set_state(self, new_state: State):
        """Set the state of the machine.

        If the target state has "require_trigger" set to True, a valid trigger
        and transition must be defined in order to set the state.

        If a trigger is found that matches the intended transition, its
        `triggered` EventHook will be emitted as if it were called directly.
        """
        old_state = self._state
        if old_state == new_state:
            return
        trigger = self._trigger_transitions.get((ANY_STATE, new_state), None)
        trigger = self._trigger_transitions.get((old_state, new_state), trigger)
        if new_state.require_trigger and not trigger:
            raise StateTransitionError(
                f"No trigger defined for transition: {old_state} -> {new_state}"
            )
        elif trigger:
            trigger.triggered.emit()
        self._set_state(new_state)

    def __getitem__(self, identifier):
        try:
            self._states[identifier]
        except KeyError:
            raise KeyError(f"State with identifier '{identifier}' not found")


class State:
    __slots__ = ("identifier", "require_trigger")

    entered = EventHook()
    exited = EventHook()

    def __init__(
        self,
        identifier: str | enum.Enum,
        require_trigger=True,
    ):
        self.identifier = identifier
        self.require_trigger = require_trigger

    def __rshift__(self: "State", other: "State|None") -> "Transition":
        return Transition(self, other)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.identifier} at " f" {hex(id(self))}>"

    def __str__(self) -> str:
        return str(self.identifier)


#: Special sentinel value to allow transitions from any state
ANY_STATE = State("any_state")


class Trigger(_Bindable):
    triggered = EventHook()

    __slots__ = ("transitions", "_transitions_dict")

    def __init__(self, *transitions: "Transition"):
        self.transitions = transitions
        self._transitions_dict = {trans.source: trans.target for trans in transitions}
        self.name: str | None = None

    def _copy(self) -> "Trigger":
        return type(self)(*self.transitions)

    def __call__(self):
        """Fire the trigger, initiating a state transition on the machine."""
        if "_bound_to" not in self.__dict__ or self._bound_to is None:
            raise ObjectBindingError("Cannot run an unbound Trigger")
        if not self.is_ready():
            raise TriggerValidityError(
                f"Current state: '{self._bound_to.get_state()}' is an invalid "
                f"source for the trigger '{self.name}'"
            )
        try:
            target_state = self._transitions_dict[self._bound_to.get_state()]
        except KeyError:
            target_state = self._transitions_dict[ANY_STATE]
        if target_state is not None:
            self._bound_to._set_state(target_state)
            self.triggered.emit()

    def is_ready(self) -> bool:
        """Checks if the trigger can be initiated from the current state"""
        if self._bound_to is None:
            raise ObjectBindingError(
                "Cannot check readiness of a Trigger from the class attribute."
            )
        if ANY_STATE in self._transitions_dict:
            return True
        return self._bound_to.get_state() in self._transitions_dict

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.name} at {hex(id(self))}>"


class Transition:
    """Encodes a valid transition from one state to another"""

    def __init__(self, source: State, target: State | None):
        self.source = source
        self.target = target

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__}: {self.source} -> {self.target} "
            f"at {hex(id(self))}>"
        )

    def __str__(self) -> str:
        return f"{self.source} -> {self.target}"
