from typing import Optional

from .core import EventHook


class ObservableAssignment:
    """A descriptor that makes an attribute's assignment observable.

    When an attribute is assigned to, the observer will be called with the
    new value as its only argument.

    """

    assigned = EventHook()

    def __init__(self, default=None):
        self.default = default

    def __get__(self, instance, cls):
        if cls is not None:
            return self
        return instance.__dict__.get(self, self.default)

    def __set__(self, instance, value):
        self.assigned.emit(value)
        instance.__dict__[self] = value


class ObservableList(ObservableAssignment):
    """Interface to a list that makes operations observable."""

    list_item_set = EventHook()
    list_item_appended = EventHook()
    list_extended = EventHook()
    list_item_inserted = EventHook()
    list_item_popped = EventHook()
    list_item_removed = EventHook()
    list_reversed = EventHook()
    list_sorted = EventHook()
    list_cleared = EventHook()
    list_changed = EventHook()

    def __init__(self, default: Optional[list] = None):
        ObservableAssignment.__init__(self, default)
        self.list = default or []

    def __hash__(self):
        return hash(id(self))

    def __setitem__(self, index, value):
        self.list[index] = value
        self.list_item_set.emit(index, value)
        self.list_changed.emit()

    def __getitem__(self, index):
        return self.list[index]

    def __len__(self):
        return len(self.list)

    def __iter__(self):
        return iter(self.list)

    def __reversed__(self):
        return reversed(self.list)

    def __contains__(self, item):
        return item in self.list

    def append(self, item):
        self.list.append(item)
        self.list_changed.emit()
        self.list_item_appended.emit(item)

    def extend(self, items):
        self.list.extend(items)
        self.list_changed.emit()
        self.list_extended.emit(items)

    def insert(self, index, item):
        self.list.insert(index, item)
        self.list_changed.emit()
        self.list_item_inserted.emit(index, item)

    def pop(self, index=-1):
        item = self.list.pop(index)
        self.list_item_popped.emit(index, item)
        self.list_changed.emit()
        return item

    def remove(self, item):
        self.list.remove(item)
        self.list_item_removed.emit(item)
        self.list_changed.emit()

    def reverse(self):
        self.list.reverse()
        self.list_reversed.emit()
        self.list_changed.emit()

    def sort(self, key=None, reverse=False):
        self.list.sort(key=key, reverse=reverse)
        self.list_sorted.emit()
        self.list_changed.emit()

    def clear(self):
        self.list.clear()
        self.list_cleared.emit()
        self.list_changed.emit()

    def __repr__(self):
        return f"ObservableList({repr(self.list)})"

    def __str__(self):
        return f"ObservableList({str(self.list)})"

    def __eq__(self, other):
        return self.list == other

    def __ne__(self, other):
        return self.list != other

    def __lt__(self, other):
        return self.list < other

    def __le__(self, other):
        return self.list <= other

    def __gt__(self, other):
        return self.list > other

    def __ge__(self, other):
        return self.list >= other

    def __add__(self, other):
        return self.list + other

    def __iadd__(self, other):
        self.list += other
        return self

    def __mul__(self, other):
        return self.list * other

    def __imul__(self, other):
        self.list *= other
        return self

    def __rmul__(self, other):
        return other * self.list


class ObservableDict(ObservableAssignment):
    """Interface to a dict that makes operations observable."""

    dict_item_set = EventHook()
    dict_item_deleted = EventHook()
    dict_item_popped = EventHook()
    dict_cleared = EventHook()
    dict_updated = EventHook()
    dict_changed = EventHook()

    def __init__(self, default: Optional[dict] = None):
        ObservableAssignment.__init__(self, default)
        if default:
            self.dict = dict(default)
        else:
            self.dict = {}

    def pop(self, key, default=None):
        value = self.dict.pop(key, default)
        self.dict_item_popped.emit(key, value)
        self.dict_changed.emit()
        return value

    def popitem(self):
        key, value = self.dict.popitem()
        self.dict_item_popped.emit(key, value)
        self.dict_changed.emit()
        return key, value

    def setdefault(self, key, default=None):
        value = self.dict.setdefault(key, default)
        self.dict_item_set.emit(key, value)
        self.dict_changed.emit()
        return value

    def clear(self):
        self.dict.clear()
        self.dict_cleared.emit()
        self.dict_changed.emit()

    def update(self, other):
        self.dict.update(other)
        self.dict_updated.emit(other)
        self.dict_changed.emit()

    def copy(self):
        return self.dict.copy()

    def get(self, key, default=None):
        return self.dict.get(key, default)

    def items(self):
        return self.dict.items()

    def keys(self):
        return self.dict.keys()

    def __hash__(self):
        return hash(id(self))

    def __setitem__(self, key, value):
        self.dict[key] = value
        self.dict_item_set.emit(key, value)
        self.dict_changed.emit()

    def __getitem__(self, key):
        return self.dict[key]

    def __len__(self):
        return len(self.dict)

    def __iter__(self):
        return iter(self.dict)

    def __contains__(self, key):
        return key in self.dict

    def __repr__(self):
        return f"ObservableDict({repr(self.dict)})"

    def __str__(self):
        return f"ObservableDict({str(self.dict)})"

    def __eq__(self, other):
        return self.dict == other

    def __ne__(self, other):
        return self.dict != other
