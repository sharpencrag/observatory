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
    Iterable,
    Protocol,
    Mapping
)

from .events import EventHook


T = TypeVar("T")

K = TypeVar("K", bound=Hashable)


class Sortable(Protocol):
    """Protocol for defining sortable objects."""

    def __gt__(self, other: Any) -> bool:
        ...

    def __lt__(self, other: Any) -> bool:
        ...


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


class ObservableList(list[T]):
    """Interface to a list that makes operations observable."""

    list_item_set: EventHook[int, T] = EventHook()
    list_item_appended: EventHook[T] = EventHook()
    list_extended: EventHook[list[T]] = EventHook()
    list_item_inserted: EventHook[int, T] = EventHook()
    list_item_popped: EventHook[int, T] = EventHook()
    list_item_removed: EventHook[T] = EventHook()
    list_reversed = EventHook()
    list_sorted = EventHook()
    list_cleared = EventHook()
    list_changed = EventHook()

    # required in order to act as a binding object for event hooks
    def __hash__(self):
        return hash(id(self))

    def __setitem__(self, index: int, value: T):
        super().__setitem__(index, value)
        self.list_item_set.emit(index, value)
        self.list_changed.emit()

    def append(self, item: T):
        """Append the given item to the end of the list."""
        super().append(item)
        self.list_changed.emit()
        self.list_item_appended.emit(item)

    def extend(self, items: Iterable[T]):
        """Extend the list in-place."""
        items = list(items)
        super().extend(items)
        self.list_changed.emit()
        self.list_extended.emit(items)

    def insert(self, index: int, item: T):
        """Insert the item at the given index."""
        super().insert(index, item)
        self.list_changed.emit()
        self.list_item_inserted.emit(index, item)

    def pop(self, index: int=-1) -> T:
        """Remove and return the item at the given index."""
        item = super().pop(index)
        self.list_item_popped.emit(index, item)
        self.list_changed.emit()
        return item

    def remove(self, item: T):
        """Remove the given item from the list."""
        super().remove(item)
        self.list_item_removed.emit(item)
        self.list_changed.emit()

    def reverse(self):
        """Reverse the list in-place."""
        super().reverse()
        self.list_reversed.emit()
        self.list_changed.emit()

    def sort(self, key: Optional[Callable[[T], Sortable]]=None, reverse=False):
        """Sort the list in-place."""
        super().sort(key=key, reverse=reverse)  # type: ignore (typeshed bug)
        self.list_sorted.emit()
        self.list_changed.emit()

    def clear(self):
        """Empty the list in-place."""
        super().clear()
        self.list_cleared.emit()
        self.list_changed.emit()

    def __repr__(self):
        return f"ObservableList({super().__repr__()})"

    def __str__(self):
        return f"ObservableList({super().__str__()})"


class ObservableDict(dict[K, T]):
    """Interface to a dict that makes operations observable."""

    item_set: EventHook[K, T] = EventHook()
    item_popped: EventHook[tuple[K, T | None]] = EventHook()
    cleared = EventHook()
    updated: EventHook[dict[K, T]] = EventHook()
    changed = EventHook()

    def pop(self, key: K, default=None) -> T | None:
        """Remove and return the value for the given key.

        If the key is not found, return the default value.
        """
        value = super().pop(key, default)
        self.item_popped.emit((key, value))
        self.changed.emit()
        return value

    def popitem(self) -> tuple[K, T]:
        """Remove and return the last entry in the dict as a (key, value) pair."""
        item = super().popitem()
        self.item_popped.emit(item)
        self.changed.emit()
        return item

    def setdefault(self, key: K, default: T) -> T:
        """Set key's value to `default` if not found. Return the stored value."""
        value = super().setdefault(key, default)
        self.item_set.emit(key, value)
        self.changed.emit()
        return value

    def clear(self):
        """Remove all items from the dict in-place."""
        super().clear()
        self.cleared.emit()
        self.changed.emit()

    def update(self, other: Mapping[K, T]):
        """Update the dict in-place with the given mapping."""
        super().update(other)
        self.updated.emit(dict(other))
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
