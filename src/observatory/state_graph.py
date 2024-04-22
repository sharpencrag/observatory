from __future__ import annotations
import typing as t
import typing_extensions as te
import enum

from observatory.events import EventHook


T = t.TypeVar("T")


class CycleDetectedError(Exception):
    """Raised when a cycle is detected in the graph."""


class ValueStatus(enum.Enum):
    """Sentinel value for a node whose value has not been set or computed"""
    NOT_SET = enum.auto()


class _Node:
    """Base class for all nodes in the graph."""

    __slots__ = ["name", "_outputs", "_has_update", "_needs_update"]

    def __init__(self, *, name: str | None = None):
        """
        Args:

            value: The initial value of the data store. Ideally, stored values
                should be immutable. Defaults to None.

            name: An optional name for the data store.  This is mostly useful
                for debugging.
        """
        self.name = name
        self._outputs: t.List["Derived"] = list()
        self._has_update = False
        self._needs_update = False

    def _get_needs_update(self):
        return self._needs_update

    def _get_has_update(self):
        return self._has_update


class Value(_Node, t.Generic[T]):
    """Generic data store that can be used as part of a graph."""

    #: Emitted when a value has been successfully updated
    updated: EventHook[T | ValueStatus, T] = EventHook()

    __slots__ = _Node.__slots__ + ["_value"]

    def __init__(
        self,
        value: T | te.Literal[ValueStatus.NOT_SET] = ValueStatus.NOT_SET,
        *,
        name: str | None = None,
    ):
        """
        Args:

            value: The initial value of the data store. Ideally, stored values
                should be immutable. Defaults to None.

            name: An optional name for the data store.  This is mostly useful
                for debugging.
        """
        super().__init__(name=name)
        self._value = value
        self._has_update = True

    def _ensure_value(self) -> T:
        """Raise a ValueError if the value for this node has never been set"""
        if self._value is ValueStatus.NOT_SET:
            raise ValueError(f"Value for this node is unset: {repr(self)}")
        return self._value

    def get(self) -> T:
        """Get the current value of this node"""
        return self._ensure_value()

    def set(self, new_value: T):
        """Set a new value.

        If the new value is different from the previous one, this will set all
        downstream nodes pending.
        """
        old_value = self._value
        if old_value == new_value:
            return
        self._value = new_value
        self.updated.emit(old_value, new_value)
        self._has_update = True
        self._push_needs_update()

    def _push_needs_update(self):
        for output in self._outputs:
            output._needs_update = True
            output._push_needs_update()

    def __repr__(self) -> str:
        """<ClassName (name): value at 0x00000>"""
        node_type = self.__class__.__name__
        name_token = f" ({self.name})" if self.name else ""
        return f"<{node_type}{name_token}: {self._value} at {hex(id(self))}>"


class Observer(Value, t.Generic[T]):
    """Special Value node whose value is obtained from an event hook.

    The given event hook should only emit a single argument.
    """

    def __init__(self, name: t.Optional[str] = None, *, event_hook: EventHook[T]):
        super().__init__(name=name)
        self._event_hook = event_hook
        event_hook.connect(self.set)


class Derived(Value, t.Generic[T]):
    """Data store whose value is derived from other nodes."""

    __slots__ = _Node.__slots__ + ["_computer", "_inputs"]

    def __init__(
        self,
        *,
        name: str | None = None,
        compute: t.Callable[[t.Tuple], T] | None = None,
        inputs: t.Sequence[Value | Derived] | None = None,
    ):
        """
        Args:
            compute: A function that takes input nodes as a tuple and returns
                a computed value.
            name: An optional name for the data store.  This is mostly useful
                for debugging.
            inputs: A sequence of input nodes.  These nodes will be passed to
                the `compute` function.
        """
        super().__init__(name=name)
        self._inputs: t.Tuple[Value | Derived, ...] = (
            tuple(inputs) if inputs else tuple()
        )
        self._computer = compute

        self._needs_update = True

        if not self._inputs:
            return

        # Set up Graph Connections
        for input in self._inputs:
            if self not in input._outputs:
                input._outputs.append(self)

    def compute(self, input_data: t.Tuple[t.Any]) -> T:
        """Calculate a new value for this node based on its inputs.

        Subclasses can override this method to make custom derived node types.
        """
        if self._computer:
            return self._computer(input_data)
        raise ValueError("Derived node must have a compute function.")

    def _compute(self):
        """Calculate a new value for this node."""
        input_values = tuple(inp.get() for inp in self._inputs)

        if not any(inp._has_update for inp in self._inputs):
            self._needs_update = False
            self._has_update = False
            return self._ensure_value()

        old_value = self._value
        new_value = self.compute(input_values)

        if old_value == new_value:
            self._has_update = False
            self._needs_update = False
            return self._ensure_value()

        self._value = new_value
        self.updated.emit(old_value, new_value)
        self._has_update = True
        self._needs_update = False

    def get(self) -> T:
        """Get the computed value for this node"""

        if not self._needs_update:
            return self._ensure_value()

        self._compute()

        return self._ensure_value()

    def set(self, _):
        raise ValueError("Derived nodes are read-only")

    def __repr__(self) -> str:
        """<ClassName (name): value, has update, needs update at 0x00000>"""
        node_type = self.__class__.__name__
        name_display = f" ({self.name})" if self.name else ""
        has_update = ", has update" if self._has_update else ""
        needs_update = ", needs update" if self._has_update else ""
        return (
            f"<{node_type}{name_display}: "
            f"{self._value}{has_update}{needs_update} at {hex(id(self))}>"
        )


def derived(
    inputs: t.Sequence[Value | Derived] | None = None,
    name: str | None = None,
) -> t.Callable[[t.Callable[..., T]], Derived[T]]:
    """Decorator: quickly define a Derived node via a compute function.

    The decorated function should take a tuple of Value or Derived objects, or
    no arguments.
    """

    def derived_value(
        func: t.Callable[[t.Tuple], T],
    ) -> Derived[T]:
        container = Derived(inputs=inputs, compute=func, name=name)
        return container

    return derived_value


def cycle_check(node: "Value | Derived", _visited=None, _rec_stack=None):
    """Check for cycles in the graph starting from the given node.

    In regular use, THIS SHOULD NOT BE NECESSARY.  However, if you are abusing
    the system in some way, this might be a useful tool to have.

    Args:
        node: The starting node for the cycle check.
        visited: Set of nodes that have been visited.
        rec_stack: Set of nodes currently in the recursion stack.

    Raises:
        CycleDetectedError: If a cycle is detected in the graph.
    """
    if _visited is None:
        _visited = set()
    if _rec_stack is None:
        _rec_stack = set()

    # Mark the current node as visited and add it to the recursion stack
    _visited.add(node)
    _rec_stack.add(node)

    # Check all neighbors (inputs for Value and outputs for Derived) for cycles
    neighbors: t.List[Derived|Value] = []

    if isinstance(node, Derived):
        neighbors.extend(node._inputs)
    neighbors.extend(node._outputs)

    for neighbor in neighbors:

        # If the neighbor hasn't been visited, recursively visit it
        if neighbor not in _visited:
            if cycle_check(neighbor, _visited, _rec_stack):
                raise CycleDetectedError(
                    f"A cycle was detected involving {node.name} and {neighbor.name}"
                )

        # If the neighbor is in the current recursion stack, a cycle is detected
        elif neighbor in _rec_stack:
            raise CycleDetectedError(
                f"A cycle was detected involving {node.name} and {neighbor.name}"
            )

    # Remove the current node from the recursion stack since we're done exploring it
    _rec_stack.remove(node)

    # No cycle detected for this path
    return False
