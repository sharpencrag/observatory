"""
Implements a version of the observer pattern similar to Qt's signals.
"""
import copy
import enum
import itertools
import traceback
from collections import OrderedDict, defaultdict
from collections.abc import MutableSet
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Hashable,
    Optional,
    Sequence,
    Tuple,
    TypeVarTuple,
    Union,
)


from observatory import thread_safe


__all__ = [
    "OrderedSet",
    "EventHook",
    "Event",
    "event",
    "class_event",
    "static_event",
    "EventStatus",
    "EventData",
    "add_global_event_callback",
    "clear_global_event_callbacks",
    "EventHookError",
    "ProgressTracker",
    "ProgressData",
]


#: typevar for event hooks' emit signatures
Ts = TypeVarTuple("Ts")


class OrderedSet(MutableSet):
    """Uses an ordered dict to establish the membership of the set.

    Original recipe by Raymond Hettinger
    """

    def __init__(self, values=()):
        self._ordered_dict = OrderedDict().fromkeys(values)

    def __len__(self):
        return len(self._ordered_dict)

    def __iter__(self):
        return iter(self._ordered_dict)

    def __contains__(self, value):
        return value in self._ordered_dict

    def add(self, value: Any):
        self._ordered_dict[value] = None

    def discard(self, value: Any):
        self._ordered_dict.pop(value, None)

    def __getitem__(self, index: int):
        return tuple(self)[index]

    def __repr__(self):
        return "{type_name}{tuple_repr}".format(
            type_name=type(self).__name__, tuple_repr=tuple(self)
        )


class EventHook(Generic[*Ts]):
    """EventHooks implement a signal/slot or "emitter" style observer pattern."""

    __slots__ = ["name", "observers", "_bound_to", "_paused", "_bound_instances"]

    def __init__(self, name: Optional[str] = None):
        """
        Args:
            name (Optional, str): An optional name for the event hook.  The
                name will appear in the __repr__ for instances of this class,
                making debugging easier.
        """
        super().__init__()

        self.name = name or ""

        # Connections to this event hook. Evaluated in order of connection.
        self.observers = OrderedSet()

        # An object that this event hook is bound to.  This allows event hooks
        # to behave like methods, and be bound to a particular instance, or
        # classmethods, and be bound to a particular class.
        self._bound_to: object = None

        # If True, the event hook will not trigger.
        self._paused = False

        # A dictionary of instances that this event hook is bound to.  This is
        # part of the binding behavior that mimics methods.
        self._bound_instances = dict()

    @thread_safe.locks()
    def connect(self, observer: Callable[[*Ts], Any]):
        """Connects the callable to the event hook.

        Multiple callables can be connected to a single event hook.

        Args:
            observer (callable)
        """
        self.observers.add(observer)

    @thread_safe.locks()
    def disconnect(self, observer: Callable):
        """Disconnects an observer from this event hook.

        Args:
            observer (callable): A callable that was previously-attached
                to this event hook.
        """
        self.observers.discard(observer)

    @thread_safe.locks()
    @contextmanager
    def paused(self):
        """Context Manager: pauses triggering of this event while active.

        This state change is re-entrant, so if the event is already paused,
        it will remain paused until the outermost context manager exits.
        """
        previous_state = self._paused
        self._paused = True
        try:
            yield
        finally:
            self._paused = previous_state

    @thread_safe.locks()
    def pause(self):
        """Prevents this event from triggering"""
        self._paused = True

    @thread_safe.locks()
    def resume(self):
        """Allows this event to trigger"""
        self._paused = False

    @thread_safe.locks()
    def emit(self, *args: *Ts, **kwargs: Any):
        """Calls every observer connected to this event hook.

        All provided arguments are passed directly to the observers.
        """

        # skip event triggering when paused
        if self._paused:
            return

        for observer in self.observers:
            try:
                observer(*args, **kwargs)
            except Exception:
                raise EventHookError(f"Error in event hook: {self!r}")

    def _as_bound_to(self, obj):
        """returns a new event hook instance bound to obj."""
        inst = type(self)()
        inst.observers = OrderedSet(self.observers)
        inst._bound_to = obj
        return inst

    @thread_safe.locks()
    def __get__(self, obj, _):
        """Gets an object when event hook is used as a descriptor."""

        if obj is None:
            return self

        # We cache the mediator objects per instance when first created
        try:
            return self._bound_instances[obj]
        except KeyError:
            bound_instance = self._as_bound_to(obj)
            self._bound_instances[obj] = bound_instance
            return bound_instance

    def __repr__(self):
        """<EventHook: event_name object at #####>"""
        if self.name:
            return "<{cls}: {name} object at {hex_id}>".format(
                cls=type(self).__name__, name=self.name, hex_id=hex(id(self))
            )
        return super(EventHook, self).__repr__()

    def __call__(self, *args: *Ts, **kwargs):
        """Alias to self.emit()"""
        self.emit(*args, **kwargs)


def observes(when: Union[EventHook, "EventStatus"]):
    """Decorator that connects a callable to an event hook.

    Args:
        event_hook (EventHook): The event hook to connect to.
        *args: Arguments to pass to the event hook's connect() method.
        **kwargs: Keyword arguments to pass to the event hook's connect()
            method.

    Returns:
        callable: The decorated callable.
    """

    def decorator(func):
        if isinstance(when, EventHook):
            when.connect(func)
        elif isinstance(when, EventStatus):
            add_global_event_callback(when, func)
        else:
            raise TypeError("@observes() must be used with an EventHook or EventStatus")
        return func

    return decorator


class EventStatus(enum.Enum):
    NEVER_RUN = 0
    ABOUT_TO_RUN = 1
    PROGRESS_UPDATED = 2
    COMPLETED = 3
    CRASHED = 4
    EXITED = 5


@dataclass
class EventData:
    """A dataclass containing information about an event.

    An EventData instance will be passed to all non-progress event callbacks.
    """

    #: the event currently being evaluated
    event: "Event"

    #: the name of the event
    name: str

    #: the wrapped function or method used as an event
    action: Callable

    #: the arguments passed into the action
    args: Tuple

    #: the keyword arguments passed into the action
    kwargs: Dict

    #: arbitrary extra information about the event
    extra: Dict

    #: whether the event should be handled independently
    elevated: bool

    #: a description of the event
    description: str = ""

    #: True if an exception was raised by the action
    crashed: bool = False

    #: The exception's name and message ("Exception: Message")
    exc_desc: str = ""

    #: A multiline string representing a entire stack trace.
    exc_trace: str = ""

    #: string tags for the event.
    tags: Dict[str, str] = field(default_factory=dict)

    #: the result of the action
    result: Any = None

    #: the current status of the event
    status: EventStatus = EventStatus.NEVER_RUN

    def __post_init__(self):
        self.description = self.description or self.action.__doc__ or ""


@dataclass
class ProgressData:
    """A dataclass containing information about a progress update.

    A ProgressData instance will be passed to all progress event callbacks.
    """

    event: "Event"  # the event currently being evaluated
    name: Optional[str]  # the name of the progression
    completion: int  # a percentage value between 0 and 100
    item: Any  # the object currently being iterated over
    status: EventStatus = EventStatus.PROGRESS_UPDATED

    def __post_init__(self):
        if self.name is None:
            self.name = self.event.name


class Event:
    """Adds observability to a wrapped function or method.

    Events are used to add loosely-coupled functionality to any callable.

    Each Event has hooks that trigger just before the function runs, just after
    it has completed successfully, just after an exception has been raised, and
    after the function has exited, regardless of its failure or success.

    In addition to the individual event's hooks, functions can be specified to
    run on every event using `add_global_event_callback`.

    Events can be created as standalone objects, but the preferred approach to
    create Events is by decorating a function or method using @event().
    """

    about_to_run: EventHook[EventData] = EventHook()
    completed: EventHook[EventData] = EventHook()
    crashed: EventHook[EventData] = EventHook()
    exited: EventHook[EventData] = EventHook()
    progress_updated: EventHook[ProgressData] = EventHook()

    # for internal use, emitted when tags are updated on the event
    _tags_updated: EventHook[Hashable, Any] = EventHook()

    def __init__(
        self,
        action,
        description="",
        extra: Optional[Dict[str, Any]] = None,
        elevate=False,
    ):
        """
        Args:

            action (callable): The wrapped function or method.

            name (str, optional): Name of the event. If not provided, the name
                of the action will be used. Defaults to None.

            description (str, optional): Brief description of the event. If not
                provided, the docstring of the action will be used. Defaults to
                None.

            extra (dict[str, Any], optional): Additional info about the
                event. Defaults to None.
        """
        self.action = action
        self.name = action.__name__
        self.description = description
        self.__doc__ = self.description or action.__doc__
        self.extra = extra or dict()
        self.elevated = elevate

        # generates a unique id each time this event is called
        self._call_id_generator = itertools.count()

        self._call_id = 0

        self._bound_instances = dict()
        self._bound_to = None

        # these two attributes are mutually exclusive -- handle with care:

        # when True, the event lives in the type definition and is not bound
        self._is_staticmethod = False

        # when True, the event lives in the type definition but is bound to
        # the class when accessed
        self._is_classmethod = False

    def track(self, sequence: Sequence[Any], name: Optional[str] = None):
        """Yields a generator that emits progress updates in an event.

        The progress updates are emitted as a ProgressData object, which
        contains the current completion percentage and the current item
        being iterated over.

        Example::

            @event
            def my_event():
                for i in my_event.track(range(10)):
                    ... some long function ...

            my_event.progress_updated.connect(print)

            # 10
            # 20
            # 30
            # ...

        """
        len_of_iterable = len(sequence)
        progress_data = ProgressData(event=self, completion=0, item=None, name=name)
        for i, item in enumerate(sequence):
            percent = int(((i + 1) / len_of_iterable) * 100)
            progress_data.item = item
            progress_data.completion = percent
            _run_global_callbacks(progress_data)
            self.progress_updated.emit(progress_data)
            yield item

    def _as_bound_to(self, instance):
        """Return a copy of this event bound to the given instance."""
        extra = copy.deepcopy(self.extra)
        inst = type(self)(self.action, self.description, extra, self.elevated)
        inst._bound_to = instance
        return inst

    def __get__(self, obj, cls):
        # four options are available when accessing an event:

        # 1. an unbound event obtained by Class.event
        if obj is None and not self._is_classmethod:
            return self

        # 2. a static event obtained by Class.event or instance.event
        elif self._is_staticmethod:
            return self

        # 3. a class event obtained by Class.event or instance.event
        elif self._is_classmethod:
            binding_obj = cls

        # 4. a non-static, non-class-event obtained by instance.event
        else:
            binding_obj = obj

        # do the appropriate binding behavior
        try:
            return self._bound_instances[binding_obj]
        except KeyError:
            bound_instance = self._as_bound_to(binding_obj)
            self._bound_instances[binding_obj] = bound_instance
            return bound_instance

    def __setitem__(self, tag: Hashable, value: Any):
        self._tags_updated.emit(tag, value)

    def __call__(self, *args, **kwargs):
        # if this event is a method or classmethod, the first argument is the
        # instance or the class, respectively
        if self._bound_to:
            args = (self._bound_to,) + args

        call_id = next(self._call_id_generator)

        event_data = EventData(
            event=self,
            action=self.action,
            name=self.name,
            description=self.description,
            args=args,
            kwargs=kwargs,
            extra=self.extra,
            elevated=self.elevated,
        )

        # this nested function is a little weird, but handles the edge case
        # where tags get updated during a recursive call of an event.
        def update_tags(key, value):
            if call_id == self._call_id:
                event_data.tags[key] = value

        # -- About to Run -- #
        event_data.status = EventStatus.ABOUT_TO_RUN
        self.about_to_run.emit(event_data)
        self._tags_updated.connect(update_tags)
        self._call_id = call_id
        _run_global_callbacks(event_data)

        try:
            # -- Running -- #
            self.action(*event_data.args, **event_data.kwargs)

        except Exception as exc:
            # -- Crashed -- #
            event_data.status = EventStatus.CRASHED
            event_data.crashed = True
            event_data.exc_desc = "{}: {}".format(type(exc).__name__, exc)
            event_data.exc_trace = traceback.format_exc()
            self.crashed.emit(event_data)
            _run_global_callbacks(event_data)
            raise

        else:
            # -- Completed -- #
            event_data.status = EventStatus.COMPLETED
            self.completed.emit(event_data)
            _run_global_callbacks(event_data)

        finally:
            # -- Exited -- #
            event_data.status = EventStatus.EXITED
            self.exited.emit(event_data)
            _run_global_callbacks(event_data)
            self._tags_updated.disconnect(update_tags)


class ProgressTracker:
    """A simplified progress tracker that emits a percentage complete.

    Use this class in place of an Event when you don't need all the bells
    and whistles of an Event.
    """

    updated = EventHook()

    def tracked(self, iterable, name: Optional[str] = None):
        """Yields a generator that emits progress updates as it iterates.

        The progress updates are emitted as a ProgressData object, which
        contains the current completion percentage and the current item
        being iterated over.
        """
        len_of_iterable = len(iterable)
        for i, item in enumerate(iterable):
            percent = int(((i + 1) / len_of_iterable) * 100)
            self.updated.emit(percent)
            yield item


def event(description: str = "", extra: Optional[Dict[str, Any]] = None, elevate=False):
    """DECORATOR: convert the decorated function or method into an Event.

    Args:

        name (str, optional): Name of the event; if not provided, the name of
            the wrapped function will be used. Defaults to None.

        description (str, optional): Brief description of the event; if not
            provided, the docstring of the wrapped function will be used.
            Defaults to None.

        extra (dict[str, Any], optional): Additional info about the event.
            Defaults to None.

        elevate (bool, optional): True if this event should be handled
            independently of any enclosing (parent) events

    """

    def _get_event(action):
        return Event(action, description, extra, elevate)

    return _get_event


# NOTE: static_event and class_event below are required due to python bug 19072
#       which has been resolved in Python 3.9.


def static_event(*args, **kwargs):
    """DECORATOR: convert the decorated staticmethod into an Event.

    When using this decorator, you no longer need a staticmethod decorator::

        class X:

            @static_event()
            def my_method():
                ...

    """

    def _get_event(action):
        e = Event(action, *args, **kwargs)
        e._is_staticmethod = True
        return e

    return _get_event


def class_event(*args, **kwargs):
    """DECORATOR: convert the decorated classmethod into an Event.

    When using this decorator, you no longer need a classmethod decorator::

        class X:

            @class_event()
            def my_method(cls):
                ...

    """

    def _get_event(action):
        e = Event(action, *args, **kwargs)
        e._is_classmethod = True
        return e

    return _get_event


#: dict[EventStatus, list[Callable]]: A dict of globally-registered callbacks
_global_event_callbacks = defaultdict(list)


@thread_safe.locks()
def add_global_event_callback(
    status: EventStatus, callback: Callable[[EventData], Any]
):
    """Adds a callback that runs when a status hook is triggered by ANY event.

    Args:

        status (EventStatus): An enumerated EventStatus

        callback (callable): A function or method that accepts an EventData as
            its only argument.

    """
    _global_event_callbacks[status].append(callback)


@thread_safe.locks()
def clear_global_event_callbacks(status):
    """Clears the list of callbacks for the given status.

    Args:

        status (EventStatus): an enumerated EventStatus

    """
    _global_event_callbacks[status][:] = []


def _run_global_callbacks(event_data: Union[EventData, ProgressData]):
    """Runs the global callbacks for the state hook of the given event data"""
    for callback in _global_event_callbacks[event_data.status]:
        callback(event_data)


class EventHookError(Exception):
    """Raised when an event hook or attached observer raises an exception."""

    pass
