import unittest
from observatory import EventHook
from observatory import publish_subscribe


class TestEventBroker(unittest.TestCase):
    def test_event_broker_caching(self):
        broker_first_get = publish_subscribe.event_broker("hello")
        broker_second_get = publish_subscribe.event_broker("hello")
        broker_other_category = publish_subscribe.event_broker("world")
        self.assertIs(broker_first_get, broker_second_get)
        self.assertIsNot(broker_first_get, broker_other_category)

    def test_event_broker_child_creation_and_caching(self):
        broker = publish_subscribe.event_broker("foo")
        child = broker.child("bar")
        child_second_get = broker.child("bar")
        other_child = broker.child("baz")
        self.assertIsInstance(child, publish_subscribe.EventBroker)
        self.assertIs(child, child_second_get)
        self.assertIs(child.parent, broker)
        self.assertIsNot(child, other_child)
        self.assertEqual(child.namespace, "foo|bar")


class TestEventBrokerSubscriberConnections(unittest.TestCase):
    incremented = EventHook()

    def setUp(self):
        self.event_count = 0
        self.broker = publish_subscribe.EventBroker("connections")

    def add_one(self):
        self.event_count += 1

    def add_two(self):
        self.event_count += 2

    def test_subscriber_add_remove(self):
        self.broker.add_subscriber(self.add_one)
        self.assertEqual(self.event_count, 0)
        self.broker.broadcast()
        self.assertEqual(self.event_count, 1)

        self.broker.add_subscriber(self.add_two)
        self.broker.broadcast()
        self.assertEqual(self.event_count, 4)

        self.broker.remove_subscriber(self.add_two)
        self.broker.broadcast()
        self.assertEqual(self.event_count, 5)

        self.broker.remove_subscriber(self.add_one)
        self.broker.broadcast()
        self.assertEqual(self.event_count, 5)

    def test_publisher_add_remove(self):
        self.broker.add_publisher(self.incremented)
        self.broker.add_subscriber(self.add_one)
        self.assertEqual(self.event_count, 0)
        self.incremented.emit()
        self.assertEqual(self.event_count, 1)


class TestEventBrokerPubSubDecorators(unittest.TestCase):
    def setUp(self):
        publish_subscribe._get_broker_dict.cache_clear()
        self.broker = publish_subscribe.event_broker("decorator")
        self.result = []

    def test_subscribes_decorator(self):
        @self.broker.subscribes()
        def add_one():
            self.result.append(1)

        self.assertFalse(self.result)
        self.broker.broadcast()
        self.assertEqual(self.result, [1])

    def test_publishes_decorator(self):
        @self.broker.subscribes()
        def add(x):
            self.result.append(x)

        @self.broker.publishes()
        def tell_the_other_guy_to_add():
            return 1

        self.assertFalse(self.result)
        tell_the_other_guy_to_add()
        self.assertEqual(self.result, [1])

    def test_hierarchy_subscriber_decorated(self):
        @self.broker.subscribes()
        def add_none(_):
            self.result.append(None)

        @self.broker.subscribes("ints")
        def add_int(x):
            self.result.append(x)

        @self.broker.subscribes("strings")
        def add_str(x):
            self.result.append(x)

        self.assertFalse(self.result)

        self.broker["ints"].broadcast(1)
        self.broker["ints"].broadcast(2)
        self.broker["strings"].broadcast("a")
        self.broker["strings"].broadcast("b")

        self.assertEqual(self.result, [1, None, 2, None, "a", None, "b", None])

    def test_hierarchy_publisher_decorated(self):
        @self.broker.publishes("ints")
        def int_publisher():
            return 1

        @self.broker.publishes("strings")
        def str_publisher():
            return "a"

        @self.broker.subscribes("ints")
        def add_int(x):
            self.result.append(x)

        @self.broker.subscribes("strings")
        def add_str(x):
            self.result.append(x)

        self.assertFalse(self.result)

        int_publisher()
        str_publisher()
        int_publisher()
        str_publisher()

        self.assertEqual(self.result, [1, "a", 1, "a"])


class TestEventBrokerHierarchy(unittest.TestCase):
    def setUp(self):
        self.parent_broker = publish_subscribe.EventBroker("parent")
        self.child_broker = self.parent_broker["child"]
        self.grandchild_broker = self.child_broker["grandchild"]

        self.set_by_parent = False
        self.set_by_child = False
        self.set_by_grandchild = False

        self.parent_broker.add_subscriber(self.set_parent)
        self.child_broker.add_subscriber(self.set_child)
        self.grandchild_broker.add_subscriber(self.set_grandchild)

    def set_parent(self):
        self.set_by_parent = True

    def set_child(self):
        self.set_by_child = True

    def set_grandchild(self):
        self.set_by_grandchild = True

    def test_parent_broker_only_broadcasts_parent(self):
        self.parent_broker.broadcast()
        self.assertTrue(self.set_by_parent)
        self.assertFalse(self.set_by_child)
        self.assertFalse(self.set_by_grandchild)

    def test_child_broker_only_broadcasts_ancestors(self):
        self.child_broker.broadcast()
        self.assertTrue(self.set_by_parent)
        self.assertTrue(self.set_by_child)
        self.assertFalse(self.set_by_grandchild)

    def test_grandchild_broker_broadcasts_ancestors(self):
        self.grandchild_broker.broadcast()
        self.assertTrue(self.set_by_parent)
        self.assertTrue(self.set_by_child)
        self.assertTrue(self.set_by_grandchild)


class TestEventBrokerQueueing(unittest.TestCase):
    def setUp(self):
        self.result = []
        self.broker = publish_subscribe.EventBroker("queueing")

    def add_to_event_count(self, value):
        self.result.append(value)

    def test_event_broker_queue(self):
        self.broker.queue_up(1)
        self.broker.queue_up(2)
        self.broker.queue_up(3)

        self.broker.broadcast_sent.connect(self.add_to_event_count)

        self.broker.broadcast_queue()

        self.assertEqual(self.result, [1, 2, 3])


if __name__ == "__main__":
    unittest.main()
