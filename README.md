# Observatory
Observatory is a suite of tools for event-driven and observable python, including:

- Standalone [event emitters](#EventHooks) inspired by Qt's Signals
- [Event decorators](#Events) for adding observability to otherwise-opaque functions
- [Data Types](#Observable-Types) for observable assignment and mutation
- A basic [Publish-Subscribe](#Publish/Subscribe) implementation

## EventHooks

EventHooks can be connected to one or more "observers", callables that are
invoked when the EventHook is emitted (with or without arguments):

```python
def say_hello(x):                # <-- function to call when events occur
    print(f"hello {x}")

an_event_hook = EventHook()     # <-- event hook as a standalone object

an_event_hook.connect(print_it) # <-- add observer

event_triggered.emit("events")  # <-- emit event hook

# output: hello events
```

Functions (or static methods) can also be connected to a specific event hook at
definition by using the "observes" decorator:

```python
@observes(an_event_hook)
def print_it(x):
    print(f"hello {x}")
```

### Type Hinting

EventHooks can be annotated to indicate the arguments that are expected to be
emitted and passed to the observer:

```python
an_event_hook: EventHook[str] = EventHook()
```

This should give static type checkers a good clue when emitting from and
connecting to the event hook. Type hinting only supports positional arguments
currently -- static type checking may break if you need to emit keyword
arguments directly to observers.

## Events

Event objects use EventHooks to add observability to otherwise opaque methods
and functions.  The EventHooks attached to an Event always emit an EventData
object with information about the Event.  See the Event class for more details.

Example:
```python
def start(event_data):
    print("hello!")

def stop(event_data):
    print("goodbye!")

@event()
def function_one():
    print("in some_function")

some_function.about_to_run.connect(start)
some_function.completed.connect(stop)

>>> some_function()
hello
in some_function
goodbye
```

### Adding Context to Events

There are two ways to add additional information to an event -- "extra" data,
and "tags".

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
or other event-based systems::
```python
@event()
def my_event(asset_name):
    my_event["asset"] = asset_name
    ...
```

## Observable Types

The provided observable data types allow us to connect callbacks to changes to our data. 

### Assignment
Not strictly a data type itself, the `ObservableAssignment` object emits an event hook every time the given attribute name is assigned a new value.

```python
class X:
    attr = ObservableAssignment(default=5)

x = X()

@observes(x.assigned)
def print_it(new_value):
	print(f"new value is {new_value}")

x.attr = 10
# output: "new value is 10"
```

### Observable Lists and Dicts
Observatory currently provides two observable data types - `ObservableList` and `ObservableDict`.  These allow us to connect observers to changes that mutate the data in-place.

```python
x = ObservableList([1, 2])

@observes(x.appended)
def correction(value):
    if value == 5:
        print("three, sir!")

x.append(5)
# output: "three, sir!"
```

`ObservableDict` and `ObservableList` are both`ObservableAssignment` subclasses, so they can also be used as attributes to watch for reassignment.

## Publish/Subscribe
"Publish-subscribe" is a special case of the observer
pattern, where subjects and observers are mediated by a third object.

We're using an `EventBroker` as our middle-man object. Each `EventBroker` is
assigned a unique id and can be obtained reliably by both publisher and
subscriber objects.

In order to make event filtering easier, event brokers can be organized into a hierarchy.

For example, let's say you have two news services. One writes political
news stories, the other writes sports stories. They send their data to a
broker, who passes on the data to subscribers. A subscriber might want
just political news, just sports news, or all news:
  
```python
# the broker for all news items
news_broker = get_event_broker("news")

# the broker just for sports stories
sports_broker = news_broker.child("sports")

# the broker just for politics stories
politics_broker = news_broker.child("politics")

# a subscriber that displays only sports news
sports_feed = MySportsFeed()
sports_feed.subscribe(sports_broker)

# a subscriber that displays all news stories
news_feed = MyNewsFeed()
news_feed.subscribe(news_broker)

# a publisher that only publishes sports stories
sports_publisher = MySportsPublisher()
sports_publisher.send_story(story, sports_broker)

# a publisher that only publishes politics stories
politics_publisher = MyPoliticsPublisher()

politics_publisher.send_story(story, politics_broker)
# news_feed and politics_feed will get the story, but
# sports_feed will not.
```

Thread Safety
-------------

A primitive (hah) attempt has been made at thread-safety by using a single
re-entrant lock for all functions that modify state in events.  Thread-safety
is not *guaranteed*, but should be sufficient for most use cases.
