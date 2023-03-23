import unittest

from observatory import data_types, events


class TestObservableAttr(unittest.TestCase):
    def setUp(self):
        self.result = None

    def _set_result(self, *args):
        self.result = args

    def test_observable_attr(self):
        class TestClass:
            attr = data_types.ObservableAttr("nothing to see here...")

        TestClass.attr.assigned.connect(self._set_result)
        instance = TestClass()
        self.assertEqual(instance.attr, "nothing to see here...")
        self.assertEqual(self.result, None)
        instance.attr = "set_as_method"
        self.assertEqual(
            self.result,
            (
                instance,
                "set_as_method",
            ),
        )

    def test_observable_attr_factory(self):
        def factory():
            yield "one"
            yield "two"

        f = factory()

        class TestClass:
            attr = data_types.ObservableAttr(factory=lambda: next(f))

        TestClass.attr.assigned.connect(self._set_result)

        instance_one = TestClass()
        instance_two = TestClass()
        self.assertEqual(instance_one.attr, "one")
        self.assertEqual(instance_two.attr, "two")
        self.assertEqual(self.result, None)
        instance_one.attr = "set_one"
        self.assertEqual(
            self.result,
            (
                instance_one,
                "set_one",
            ),
        )
        instance_two.attr = "set_two"
        self.assertEqual(
            self.result,
            (
                instance_two,
                "set_two",
            ),
        )
        self.assertEqual(instance_one.attr, "set_one")
        self.assertEqual(instance_two.attr, "set_two")

    def test_observable_attr_factory_no_collision_in_instances(self):
        class TestClass:
            attr = data_types.ObservableAttr(factory=list)

        TestClass.attr.assigned.connect(self._set_result)

        instance_one = TestClass()
        instance_two = TestClass()
        self.assertIsInstance(instance_one.attr, list)
        self.assertFalse(instance_one.attr)
        self.assertIsInstance(instance_two.attr, list)
        self.assertFalse(instance_two.attr)
        self.assertIsNot(instance_one.attr, instance_two.attr)


class TestObservableList(unittest.TestCase):
    def setUp(self):
        self.result = None

    def _set_result(self, *args):
        self.result = args

    def _just_a_trigger(self, value):
        def cbk():
            self.result = value

        return cbk

    def test_observable_list(self):
        obs_list = data_types.ObservableList()

        # sanity check
        self.assertEqual(self.result, None)

        self.assert_all_observed(obs_list)

    def assert_all_observed(self, obs_list):
        obs_list.extend([1, 2, 3])

        # list_item_set
        obs_list.list_item_set.connect(self._set_result)
        expected = (2, 4)
        obs_list[2] = 4
        self.assertEqual(self.result, expected)

        # list_item_inserted
        obs_list.list_item_inserted.connect(self._set_result)
        expected = (2, 5)
        obs_list.insert(2, 5)
        self.assertEqual(self.result, expected)

        # list_item_appended
        obs_list.list_item_appended.connect(self._set_result)
        expected = (6,)
        obs_list.append(6)
        self.assertEqual(self.result, expected)

        # list_item_popped
        obs_list.list_item_popped.connect(self._set_result)
        obs_list.list_item_appended.disconnect(self._set_result)
        # sanity check
        obs_list.append(7)
        self.assertEqual(self.result, expected)
        expected = (-1, 7)
        obs_list.pop()
        self.assertEqual(self.result, expected)

        # list_extended
        obs_list.list_extended.connect(self._set_result)
        expected = ([7, 8],)
        obs_list.extend([7, 8])
        self.assertEqual(self.result, expected)

        # list_cleared
        trigger = "cleared"
        obs_list.list_cleared.connect(self._just_a_trigger(trigger))
        obs_list.clear()
        self.assertEqual(self.result, trigger)

        # list_reversed
        trigger = "reversed"
        obs_list.list_reversed.connect(self._just_a_trigger(trigger))
        obs_list.reverse()
        self.assertEqual(self.result, trigger)

        # list_sorted
        trigger = "sorted"
        obs_list.list_sorted.connect(self._just_a_trigger(trigger))
        obs_list.sort()
        self.assertEqual(self.result, trigger)


class TestObservableDict(unittest.TestCase):
    def setUp(self):
        self.data = {"a": 1, "b": 2, "c": 3}
        self.result = None
        self.results_obtained = events.EventHook()
        self.results_obtained.connect(self._set_result)

    def _set_result(self, *args):
        self.result = args

    def _just_a_trigger(self, value):
        def cbk():
            self.result = value

        return cbk

    def test_observable_dict(self):
        obs_dict = data_types.ObservableDict(self.data)

        # sanity check
        self.assertEqual(self.result, None)

        self.assert_all_observed(obs_dict)

    def assert_all_observed(self, obs_dict: data_types.ObservableDict):
        # dict_item_set
        obs_dict.item_set.connect(self._set_result)
        expected = ("b", 4)
        obs_dict["b"] = 4
        self.assertEqual(self.result, expected)

        expected = ("d", "danger")
        obs_dict.setdefault("d", "danger")

        # dict_item_popped
        obs_dict.item_popped.connect(self._set_result)
        expected = ("c", 3)
        obs_dict.pop("c")
        self.assertEqual(self.result, expected)

        # dict_item_popitem
        # the popped item will be the last item in the dict
        expected = ("d", "danger")
        obs_dict.popitem()
        self.assertEqual(self.result, expected)

        # dict_cleared
        trigger = "cleared"
        obs_dict.cleared.connect(self._just_a_trigger(trigger))
        obs_dict.clear()
        self.assertEqual(self.result, trigger)

        # dict_updated
        obs_dict.updated.connect(self._set_result)
        expected = ({"d": 4, "e": 5},)
        obs_dict.update(expected[0])
        self.assertEqual(self.result, expected)

    def test_observable_dict_equivalency(self):
        obs_dict = data_types.ObservableDict(self.data)
        self.assertEqual(obs_dict, self.data)
