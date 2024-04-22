# Observatory
Observatory is a suite of tools for event-driven and observable python, including:

- Standalone [event emitters](#EventHooks) inspired by Qt's Signals
- [Event decorators](#Events) for adding observability to otherwise-opaque functions
- [Data Types](#Observable-Types) for observable assignment and mutation
- A basic [Publish-Subscribe](#Publish/Subscribe) implementation
- A [State Machine](#State-Machine)
- A lazily-evaluated [State Graph](#State-Graph)

## About Observability and Events

*Observability* is the ability to gain information about a system; For example,
logging provides a form of observability.  Your code writes a message to a
logger, and we can learn something about that code during runtime.

```
logger = logging.getLogger(__name__)
logger.info("hello world!")
```

Observability is not just about getting information, though;  A logger is a
specific example of an *event system* - When you call `logger.info`, the system
generates an *event*, one which can be picked up or ignored by any number of
`Handler`s.

```
logger.addHandler(file_handler)
```

One major benefit of an event system is that the code that creates an event (`logger.info`) and the *observer* of the event (`file_handler`) are *decoupled*.

Your application code doesn't need to know anything about the handler's existence
or implementation in order to continue working.

Outside of just logging, we can create entire systems that are event-driven
and observable by design.  This can be used to create a wide range of
highly-decoupled components in an application.

# About `observatory`

## EventHooks

The core of the event system and the rest of `observatory`'s tools is the `EventHook`.

An `EventHook` is an object that can be connected to one or more *observers*,
callables that get connected to the hook.  When an `EventHook` is triggered
via its `emit` method, each connected observer is called in turn.

`EventHook`s can be standalone objects, or defined as part of a class.

```python
def say_hello(x: str):  # <-- function to call when events occur
    print(f"hello {x}")

an_event_hook: EventHook[str] = EventHook() # <-- standalone event hook

an_event_hook.connect(say_hello) # <-- add observer

an_event_hook.emit("events")     # <-- emit event hook

# output: hello events
```

In most cases, an `EventHook` will be defined as part of a class.

```python
class SpaceTelescope:
    coords_received: EventHook[Coordinates] = EventHook()
    aliens_detected = EventHook()  # This event hook takes no arguments

    def __init__():
        self.coords_received.connect(self.rotate_to_coords)
        self.aliens_detected.connect(everybody_panic)

###

def say_hello():
    print(f"Welcome to Earth!")

telescope = SpaceTelescope()

telescope.aliens_detected.connect(say_hello)
```

Functions (or static methods) can also be connected to a specific event hook at
definition by using the "observes" decorator:

```python
@observes(telescope.aliens_detected)
def say_hello():
    print(f"Welcome to Earth!")
```

instance- and class-methods cannot be decorated as observers due to their
nature as descriptors; in short, there's not a good way to attach them at
definition time.

### Type Hinting

EventHooks can be annotated to indicate the argument(s) that are expected to be
emitted and passed to the observer:

```python
# This event hook emits a string and an integer
an_event_hook: EventHook[str, int] = EventHook()

# An observer's signature must match the EventHook's
@observes(an_event_hook)
def an_observer(name: str, number: int):
    ...
```

This should give static type checkers a good clue when emitting from and
connecting to the event hook.

> **Warning**
> Type hinting only supports positional arguments currently -- static type
> checking may break if you need to emit keyword arguments directly to
> observers.  That said, keyword arguments themselves are supported in the
> system, just not type-hinted.

## Events

`Event` objects use `EventHook`s to add observability to otherwise opaque methods
and functions.

The most common way to create an event is by decorating a function or method.

Example:
```python
def start(event_data):
    print("hello!")

def stop(event_data):
    print("goodbye!")

@event()
def function_one():
    print("in function_one")

function_one.about_to_run.connect(start)
function_one.completed.connect(stop)

some_function()
# output: hello
# output: in some_function
# output: goodbye
```

`class_event` and `static_event` decorators are also included to decorate
classmethods and staticmethods as events, respectively.

`Event`s are bristling with observability!  They provide the following
event hooks:

- *about_to_run*: emitted before the event callback is run.
- *completed*: emitted after the event callback is run successfully.
- *crashed*: emitted after the event callback has raised an unhandled exception.
- *exited*: emitted after the event callback has returned, whether successful
  or not
- *progress_updated*: emitted when the event callback needs to update incremental
  progress

The `progress_updated` `EventHook` emits a `ProgressData` object.  All the
others emit an `EventData` object.

### Event Data

When the `EventHooks` on an `Event` are emitted, they send an `EventData`
object as their only argument (except for `progress_updated` -- see below)

`EventData` objects store a lot of information about the current event:
 - *event*: (Event) - the event currently being evaluated
 - *name*: (Str) - the name of the event
 - *action*: (Callable) - the wrapped function or method used as an event
 - *args*: (Tuple) - the arguments passed into the action
 - *kwargs*: (Dict) - the keyword arguments passed into the action
 - *extra*: (Dict) - arbitrary extra information about the event
 - *elevated*: (Bool) - whether the event should be handled independently
 - *description*: (Str) - a description of the event
 - *crashed*: (Bool) - True if an exception was raised by the action
 - *exc_desc*: (str) - The exception's name and message
 - *exc_trace*: (str) - A multiline string representing a entire stack trace.
 - *tags*: (Dict) - string tags for the event.
 - *result*: (Any) - the return value of the event's action, if completed
 - *status*: (EventStatus) - the current status of the event

### Tracking Progress

Consider this example:

```python
def automate_tasks(tasks: Sequence[Task]):
    for task in tasks:
        task.do_it()  # <- assume this takes some time
```

Let's say this is a function that runs as part of a tool with a UI.  How do we
report progress back to the user?

Events to the rescue!

```python
@event()
def automate_tasks(tasks: Sequence[Task]):
    total_tasks =
    for task in automate_tasks.track(tasks):
        task.do_it()

def update_progress_bar(progress: ProgressData):
    ... # <- update the UI here...

automate_tasks.progress_updated.connect(update_progress_bar)
```

This is the most convenient way to send progress updates based on any iterable
value, but you could also emit the `progress_updated` signal manually.

Because this is designed to use an event system, we can write `automate_tasks`
once, and re-use it for UIs, CLIs, or headless operation if needed.

### Adding Context to Events

There are three ways to add additional information to an event -- "extra" data,
tags, and elevated status.

"extra" data is a globally-defined dictionary that is shared between all calls
to a given event:

```python
@event(extra={"project": "SuperProject"})
def my_event():
    ...
```

"tags", on the other hand, are assigned to *one particular execution* of an
event.  Tags should be used when the data is likely to change each time an
event is called.  Tags can be assigned using dictionary-style keys on an event,
within the function call.

This can be useful to get additional information into your logging, telemetry,
or other event-based systems:

```python
@event()
def my_event(asset_name):
    my_event["asset"] = asset_name
    ...
```

This extra contextual data will be added to the `EventData` object, which is
emitted by the event at each stage of its execution.

Finally, if you create an event with `elevated=True`, the `elevated` attribute
will be `True` in all emitted `EventData` objects for the event.  There is no
built-in functionality that uses this feature, but it is intended for use-cases
where an event needs to pre-empt or otherwise behave differently than its parent
or child events.

### Observing event categories

Rather than connecting to one specific `EventHook` of an `Event`, you can
connect to all `EventHook`s of a specific type.

For example, let's say we want to call a function every time an event completes.

You can use the `add_global_event_callback` function, or use an `EventStatus`
argument to the `observes` decorator:


```python
@event()
def event_one():
    ...

@event()
def event_two():
    ...

@observes(EventStatus.COMPLETED)
def on_any_event_completed(event_data: EventData):
    ...
```

## Observable Types

The provided observable data types allow us to connect callbacks to changes to data.

### Assignment
Not strictly a data type itself, the `ObservableAttr` object emits an event hook every
time the given attribute name is assigned a new value.

```python
class X:
    attr = ObservableAttr(default=5)

x = X()

@observes(x.assigned)
def print_it(new_value):
	print(f"new value is {new_value}")

x.attr = 10
# output: "new value is 10"
```

### Observable Lists and Dicts
Observatory currently provides two observable data types - `ObservableList` and
`ObservableDict`.  These allow us to connect observers to changes that mutate
the data in-place.

```python
x = ObservableList([1, 2])

@observes(x.appended)
def correction(value):
    if value == 5:
        print("three, sir!")

x.append(5)
# output: "three, sir!"
```

## Publish/Subscribe
"Publish-subscribe" is a special case of the observer
pattern, where subjects and observers are mediated by a third object.

An Event Broker is a middle-man object between events and their callbacks,
allowing event-generating objects (publishers) and callbacks (subscribers)
to never know about each-other's existence.  A subscriber can subscribe to
an event broker that has no publishers, and a publisher can publish to an
event broker with no subscribers.

In order to make event filtering easier, event brokers can be organized into a
hierarchy:

```python
top_level_broker = get_event_broker("top")
child_broker = top_level_broker.child("middle")
grandchild_broker = child_broker.child("bottom")
```

A publisher can send data to subscribers via the broker broadcast function:

```python
broker.broadcast("positional arg", keyword_arg=None)
```

A subscriber can receive data from publishers by connecting to the broker's
broadcast_sent event:

```python
broker.broadcast_sent.connect(subscriber_function)
```

### Event Thread Safety

A primitive (hah) attempt has been made at thread-safety by using a single
re-entrant lock for all functions that modify state in events.  Thread-safety
is not *guaranteed*, but should be sufficient for most use cases.


## State Machine

`observatory` provides a basic but extremely user-friendly implementation of a
state machine.  This system does not support dynamic addition or removal of states,
so it will be most useful if you know your states, transitions, and triggers upfront.

```py
import enum
from observatory.state_machine import Machine, State, Trigger

class TrafficLight(Machine):

    green = State("GREEN")
    yellow = State("YELLOW")
    red = State("RED")

    default_state = red

    to_green = Trigger(red >> green)
    to_yellow = Trigger(green >> yellow)
    to_stop = Trigger(yellow >> red)
```

Once your state machine is defined, you can interact with it by firing triggers
to transition between states.

```python
traffic_light = TrafficLight()
print(traffic_light.get_state())  # Outputs: RED

# Transition from RED to GREEN
traffic_light.to_green()
print(traffic_light.get_state())  # Outputs: GREEN

# Transition from GREEN to YELLOW
traffic_light.to_yellow()
print(traffic_light.get_state())  # Outputs: YELLOW

```

### State Machine Events
You can connect observers to individual states, triggers, and the machine
itself.

Here's an example observing all state change on our traffic light:

```python
@observes(traffic_light.updated)
def report_state_changed(old_state, new_state):
    print(f"Exited {old_state}")
    print(f"Entered {new_state}")
```

Now, firing a trigger will also print event messages

```py
traffic_light.to_green()
# Exited RED
# Entered GREEN
```

## State Graph

The `observatory` `state_graph` module allows you to make a graph of data nodes
whose values are computed lazily. The `state_graph` approach is particularly
useful when a few things are true:

- Your data has complex chains of dependencies
- Your data requires expensive computation
- You have a clear picture of your data flow up-front, but
- You aren't sure which piece of data will be required at runtime

Here is a very basic example of a state graph:

```py
from typing import Tuple
from observatory.state_graph import Value, derived

value_one: Value[int] = Value(3)
value_two: Value[str] = Value("hello")

@derived(inputs=[value_one, value_two])
def multiplied(values: Tuple[int, str]) -> str:
    return values[0] * values[1]

```

We've created three nodes: `value_one`, `value_two`, and `multiplied`.

`value_one` and `value_two` are `Value` nodes.  They are simple containers for
a piece of data (ideally, immutable data).

`multiplied` is a `Derived` node, here created by a decorator.  `Derived` nodes
compute their values based on one or more inputs.

`Derived` nodes can also be created by instantiating the `Derived` class:

```py
def multiply(values: Tuple[int, str]) -> str:
    return values[0] * values[1]

multiplied = Derived(inputs=[value_one, value_two], compute=multiply)
```

At this point, the value of `multiplied` has not been calculated.  It won't be
until its `get` method is called:

```py
print(multiplied.get())
# 'hellohellohello'
```

Once computed, the value of `multiplied` is cached until its upstream
dependencies change, so further calls to `get` will not run the compute
callback.

### Observing State Graph Changes

Each state graph node provides an `updated` `EventHook` which will only emit if
the value has been actually updated.  For `Value` nodes, this means the value
has been updated by code:

```py
value_one.set(2)
```

For `Derived` nodes, `updated` is emitted only if
1. An upstream `Value` or `Derived` node has been updated, and
2. The re-computed value is different than the previous computation.

Both the old and new values are emitted to observers.