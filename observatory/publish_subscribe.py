"""
Simple implementation of a publish-subscribe event system.
"""

from collections import deque
from typing import Dict, Hashable, Optional

from functools import lru_cache, wraps

from observatory import core as events

__all__ = ["event_broker", "EventBroker"]


def ancestors(child):
    """Helper utility to get a list of all ancestors of a given object."""
    parent = child.parent
    ancestors = list()
    while parent is not None:
        ancestors.append(parent)
        parent = parent.parent
    return ancestors


@lru_cache
def _get_broker_dict() -> Dict[Hashable, "EventBroker"]:
    """Returns a common dictionary used for storing top-level event brokers"""
    return dict()


def event_broker(topic: Hashable, parent: Optional["EventBroker"] = None):
    """Gets or creates a new EventBroker instance for the given topic.

    This function is the preferred way to obtain an EventBroker.

    Args:
        topic: The id of the event broker.  This will be used as a dict
            key to store the broker in a common dictionary and therefore must
            be hashable.  In practice, this will typically be a str or enum.
        parent (EventBroker): A parent broker to obtain a child broker from.

    Example:
        # get a top-level broker
        news_broker = get_event_broker("news")

        # get a child broker
        sports_broker = get_event_broker("sports", parent=news_broker)

        # the above is equivalent to this...
        sports_broker = news_broker.child("sports")

        # and this
        sports_broker = news_broker["sports"]
    """
    if parent is None:
        broker_dict = _get_broker_dict()
    else:
        broker_dict = parent.child_dict
    try:
        return broker_dict[topic]
    except KeyError:
        broker = EventBroker(topic, parent=parent)
        broker_dict[topic] = broker
        return broker


class EventBroker:
    """Mediates the connections between publishers and subscribers to events.

    EventBroker objects should not be instantiated directly, instead, the
    preferred method is to use get_event_broker() to obtain a broker object
    based on its topic.

    To obtain a child event broker, use the child() method or the [] operator.
    """

    broadcast_sent = events.EventHook()

    def __init__(self, topic: Hashable, parent=None):
        self.topic = topic
        self.queue = deque()
        self.child_dict = dict()
        self.parent = parent

    def child(self, topic):
        """Gets or creates a new EventBroker instance for the given child name.

        Returns:
            (EventBroker) An event broker with the given name.
        """
        if topic == self.topic:
            return self
        return event_broker(topic, parent=self)

    def add_publisher(self, publish_event_hook: events.EventHook):
        """Connects an event hook to the broadcast event on this broker.
        Args:
            event_hook (EventHook): an event hook that is acting as a publisher
        """
        publish_event_hook.connect(self.broadcast)

    def remove_publisher(self, publish_event_hook: events.EventHook):
        """Disconnects an event hook from the broadcast event on this broker.
        Args:
            event_hook (EventHook): an event hook that is acting as a publisher
        """
        publish_event_hook.disconnect(self.broadcast)

    def add_subscriber(self, callback):
        """Connects a callable to the broadcast event on this broker.
        Args:
            callback (callable): A function, method, or other callable object
                that is acting as a subscriber to this event broker.
        """
        self.broadcast_sent.connect(callback)

    def remove_subscriber(self, callback):
        """Disconnects a callable from the broadcast event on this broker.
        Args:
            callback (callable): A function, method, or other callable object
                that is acting as a subscriber to this event broker.
        """
        self.broadcast_sent.disconnect(callback)

    @property
    def subscribers(self):
        """The list of subscribers on this broker"""
        return self.broadcast_sent.observers

    def queue_up(self, *args, **kwargs):
        """Add a set of arguments to this broker's broadcast queue.

        They will be broadcast in the order they are queued, first-come,
        first-served.
        """
        self.queue.append((args, kwargs))

    def broadcast_queue(self):
        """Send all queued-up arguments to subscribers"""
        while self.queue:
            args, kwargs = self.queue.popleft()
            self.broadcast(*args, **kwargs)

    def broadcast(self, *args, **kwargs):
        """Broadcast arguments to this brokers' and its parents' subscribers"""
        for broker in [self] + ancestors(self):
            broker.broadcast_sent.emit(*args, **kwargs)

    @property
    def namespace(self):
        """The unique name of this event broker as a string.

        Each event broker has a unique name based on both it's and its parents'
        names.  Child and parent names are separated by the pipe symbol.

        Example:
            news_broker = get_event_broker("news")
            sports_broker = news_broker["sports"]
            sports_broker.namespace  # <- 'news|sports'

        """
        name_chain = [self] + ancestors(self)
        return "|".join([str(item.topic) for item in reversed(name_chain)])

    def subscribes(self, topic: Optional[Hashable] = None):
        """Decorator for subscribing a function to an event broker."""

        def decorator(func):
            if topic:
                self.child(topic).add_subscriber(func)
            else:
                self.add_subscriber(func)
            return func

        return decorator

    def publishes(self, topic: Optional[Hashable] = None):
        """Decorator for publishing an event hook to an event broker."""
        publish = events.EventHook()
        if topic is None:
            self.add_publisher(publish)
        else:
            self.child(topic).add_publisher(publish)

        def decorator(func):
            @wraps(func)
            def wrapped_as_publisher(*args, **kwargs):
                result = func(*args, **kwargs)
                publish.emit(result)
                return result

            return wrapped_as_publisher

        return decorator

    def __getitem__(self, child_topic):
        """Use dictionary-style lookup to obtain a child event broker"""
        return self.child(child_topic)
