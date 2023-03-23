from typing import (
    Optional,
    Self,
    Type,
    TypeVar,
    Generic,
    Any,
    overload,
    Hashable,
    Callable,
)

from .events import EventHook


T = TypeVar("T")


class NotSet:
    """Sentinel class for indicating that a value has not been set."""


class ObservableAttr(Generic[T]):
    """A descriptor that makes an attribute's assignment observable.

    When an attribute is assigned to, the observer will be called with the
    new value as its only argument.

    """

    assigned: EventHook[Any, T] = EventHook()

    __slots__ = ("default", "factory")

    def __init__(
        self, default: Optional[T] = None, factory: Optional[Callable[..., T]] = None
    ):
        if not default and not factory:
            raise ValueError("Either default or factory must be provided.")
        if default and factory:
            raise ValueError("Only one of default or factory can be provided.")
        self.default = default
        self.factory = factory

    @overload
    def __get__(self, instance: None, cls: Type[Any]) -> Self:
        ...

    @overload
    def __get__(self, instance: Any, cls: Type[Any]) -> T:
        ...

    def __get__(self, instance, cls):
        if instance is None:
            return self
        instance_value = instance.__dict__.get(self, NotSet)
        if self.factory and instance_value is NotSet:
            instance_value = self.factory()
            instance.__dict__[self] = instance_value
        elif self.default and instance_value is NotSet:
            instance_value = self.default
            instance.__dict__[self] = instance_value
        return instance_value

    def __set__(self, instance, value: T):
        self.assigned.emit(instance, value)
        instance.__dict__[self] = value


class ObservableList(list):
    """Interface to a list that makes operations observable."""

    list_item_set: EventHook[int, Any] = EventHook()
    list_item_appended: EventHook[Any] = EventHook()
    list_extended: EventHook[list[Any]] = EventHook()
    list_item_inserted: EventHook[int, Any] = EventHook()
    list_item_popped: EventHook[int, Any] = EventHook()
    list_item_removed: EventHook[Any] = EventHook()
    list_reversed = EventHook()
    list_sorted = EventHook()
    list_cleared = EventHook()
    list_changed = EventHook()

    def __hash__(self):
        # required in order to act as a binding object for event hooks
        return hash(id(self))

    def __setitem__(self, index, value):
        super().__setitem__(index, value)
        self.list_item_set.emit(index, value)
        self.list_changed.emit()

    def append(self, item):
        super().append(item)
        self.list_changed.emit()
        self.list_item_appended.emit(item)

    def extend(self, items):
        super().extend(items)
        self.list_changed.emit()
        self.list_extended.emit(items)

    def insert(self, index, item):
        super().insert(index, item)
        self.list_changed.emit()
        self.list_item_inserted.emit(index, item)

    def pop(self, index=-1):
        item = super().pop(index)
        self.list_item_popped.emit(index, item)
        self.list_changed.emit()
        return item

    def remove(self, item):
        super().remove(item)
        self.list_item_removed.emit(item)
        self.list_changed.emit()

    def reverse(self):
        super().reverse()
        self.list_reversed.emit()
        self.list_changed.emit()

    def sort(self, key=None, reverse=False):
        super().sort(key=key, reverse=reverse)
        self.list_sorted.emit()
        self.list_changed.emit()

    def clear(self):
        super().clear()
        self.list_cleared.emit()
        self.list_changed.emit()

    def __repr__(self):
        return f"ObservableList({super().__repr__()})"

    def __str__(self):
        return f"ObservableList({super().__str__()})"


class ObservableDict(dict):
    """Interface to a dict that makes operations observable."""

    item_set: EventHook[Hashable, Any] = EventHook()
    item_popped: EventHook[Hashable, Any] = EventHook()
    cleared = EventHook()
    updated: EventHook[dict] = EventHook()
    changed = EventHook()

    def pop(self, key, default=None):
        value = super().pop(key, default)
        self.item_popped.emit(key, value)
        self.changed.emit()
        return value

    def popitem(self):
        key, value = super().popitem()
        self.item_popped.emit(key, value)
        self.changed.emit()
        return key, value

    def setdefault(self, key, default=None):
        value = super().setdefault(key, default)
        self.item_set.emit(key, value)
        self.changed.emit()
        return value

    def clear(self):
        super().clear()
        self.cleared.emit()
        self.changed.emit()

    def update(self, other):
        super().update(other)
        self.updated.emit(other)
        self.changed.emit()

    def __hash__(self):
        # required to act as a binding object for event hooks
        return hash(id(self))

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self.item_set.emit(key, value)
        self.changed.emit()

    def __repr__(self):
        return f"ObservableDict({repr(super())})"

    def __str__(self):
        return f"ObservableDict({str(super())})"
