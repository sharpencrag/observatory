import unittest
from observatory import core
from observatory import data_types


class EventHookTests(unittest.TestCase):
    """Base class - actual test scenarios are added in TestCases below.

    This allows us to run the same tests on event hooks that are created in
    various ways and with different scopes.
    """

    def setUp(self):
        self.event_hook = core.EventHook()
        self.event_hook_two = core.EventHook()
        self.result = None
        self.result_two = None

    def test_connect_function_to_event_hook(self):
        def func():
            self.result = "function"

        self.event_hook.connect(func)
        self.event_hook.emit()
        self.assertEqual(self.result, "function")

    def _set_result(self, value="method"):
        self.result = value

    def test_connect_method_to_event_hook(self):
        self.event_hook.connect(self._set_result)
        self.event_hook.emit()
        self.assertEqual(self.result, "method")

    def test_connect_lambda_to_event_hook(self):
        self.event_hook.connect(lambda: self._set_result("lambda"))
        self.assertIsNone(self.result)
        self.event_hook.emit()
        self.assertEqual(self.result, "lambda")

    def test_connect_callable_object_to_event_hook(self):
        class CallableObject:
            def __call__(self_):
                self.result = "callable_object"

        self.event_hook.connect(CallableObject())
        self.event_hook.emit()
        self.assertEqual(self.result, "callable_object")

    def test_disconnect_function_from_event_hook(self):
        def func():
            self.result = "function"

        self.event_hook.connect(func)
        self.event_hook.disconnect(func)
        self.event_hook.emit()
        self.assertIsNone(self.result)

    def test_disconnect_method_from_event_hook(self):
        self.event_hook.connect(self._set_result)
        self.event_hook.disconnect(self._set_result)
        self.event_hook.emit()
        self.assertEqual(self.result, None)

    def test_disconnect_lambda_from_event_hook(self):
        lam = lambda: self._set_result("lambda")
        self.event_hook.connect(lam)
        self.event_hook.disconnect(lam)
        self.event_hook.emit()
        self.assertIsNone(self.result)

    def test_disconnect_callable_object_from_event_hook(self):
        class CallableObject:
            def __call__(self_):
                self.result = "callable_object"

        callable_object = CallableObject()
        self.event_hook.connect(callable_object)
        self.event_hook.disconnect(callable_object)
        self.event_hook.emit()
        self.assertIsNone(self.result)

    def test_event_hook_error(self):
        self.event_hook.connect(self._set_result)
        with self.assertRaises(core.EventHookError):
            self.event_hook.emit(foo="bar")

    def test_no_event_hook_crosstalk(self):
        """Early versions of the tool introduced a bug where event hooks would
        call each-other's observers. This test ensures that this is no longer
        the case.
        """

        def func_one():
            self.result = "func_one"

        def func_two():
            self.result_two = "func_two"

        self.event_hook.connect(func_one)
        self.event_hook_two.connect(func_two)

        self.event_hook.emit()

        self.assertIsNone(self.result_two)
        self.assertEqual(self.result, "func_one")

        self.result = None
        self.event_hook_two.emit()

        self.assertIsNone(self.result)
        self.assertEqual(self.result_two, "func_two")

    def test_local_event_pause(self):
        self.event_hook.connect(self._set_result)
        self.event_hook.pause()
        self.event_hook.emit()
        self.event_hook.resume()
        self.assertIsNone(self.result)
        self.event_hook.emit()
        self.assertEqual(self.result, "method")

    def test_local_event_pause_context_manager(self):
        self.event_hook.connect(self._set_result)
        with self.event_hook.paused():
            self.event_hook.emit()
        self.assertIsNone(self.result)
        self.event_hook.emit()
        self.assertEqual(self.result, "method")

    def test_observes_decorator_function(self):
        @core.observes(self.event_hook)
        def func():
            self.result = "function"

        self.assertIsNone(self.result)
        self.event_hook.emit()
        self.assertEqual(self.result, "function")


class TestEventHookAsClassAttribute(EventHookTests):
    """Ensures all the tests work when an event hook is a descriptor"""

    class AnotherClass:
        event_hook = core.EventHook()

    def setUp(self):
        self.result = None
        self.result_two = None
        self.event_hook = self.AnotherClass().event_hook
        self.event_hook_two = self.AnotherClass().event_hook


class TestObservableList(unittest.TestCase):
    def setUp(self):
        self.result = None

    def _set_result(self, *args):
        self.result = args

    def _just_a_trigger(self, value):
        def cbk():
            self.result = value

        return cbk

    def test_observable_attr_inst_attr(self):
        class TestClass:
            attr = data_types.ObservableAssignment()

        TestClass.attr.assigned.connect(self._set_result)
        instance = TestClass()
        self.assertEqual(self.result, None)
        instance.attr = "set_as_method"
        self.assertEqual(self.result, ("set_as_method",))

    def test_observable_list_reassignment(self):
        class TestClass:
            obs_list = data_types.ObservableList([1, 2, 3])

        instance = TestClass()
        instance.obs_list.assigned.connect(self._set_result)
        instance.obs_list = "reassigned"
        self.assertEqual(self.result, ("reassigned",))

    def test_observable_list_as_attr(self):
        class TestClass:
            obs_list = data_types.ObservableList([1, 2, 3])

        instance = TestClass()
        self.assertEqual(self.result, None)
        self.assert_all_observed(instance.obs_list)

        # reset
        TestClass.obs_list.list = [1, 2, 3]
        self.assert_all_observed(TestClass.obs_list)

    def test_observable_list(self):
        obs_list = data_types.ObservableList([1, 2, 3])

        # sanity check
        self.assertEqual(self.result, None)
        self.assert_all_observed(obs_list)

    def assert_all_observed(self, obs_list):
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
        self.results_obtained = core.EventHook()
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

    def test_observable_dict_as_attr(self):
        class TestClass:
            obs_dict = data_types.ObservableDict(self.data)

        instance = TestClass()
        self.assertEqual(self.result, None)
        self.assert_all_observed(instance.obs_dict)

        # reset
        TestClass.obs_dict.dict = dict(self.data)
        self.assert_all_observed(TestClass.obs_dict)

    def assert_all_observed(self, obs_dict: data_types.ObservableDict):
        # dict_item_set
        obs_dict.dict_item_set.connect(self._set_result)
        expected = ("b", 4)
        obs_dict["b"] = 4
        self.assertEqual(self.result, expected)

        expected = ("d", "danger")
        obs_dict.setdefault("d", "danger")

        # dict_item_popped
        obs_dict.dict_item_popped.connect(self._set_result)
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
        obs_dict.dict_cleared.connect(self._just_a_trigger(trigger))
        obs_dict.clear()
        self.assertEqual(self.result, trigger)

        # dict_updated
        obs_dict.dict_updated.connect(self._set_result)
        expected = ({"d": 4, "e": 5},)
        obs_dict.update(expected[0])
        self.assertEqual(self.result, expected)

    def test_observable_dict_equivalency(self):
        obs_dict = data_types.ObservableDict(self.data)
        self.assertEqual(obs_dict, self.data)


class TestEventDecorator(unittest.TestCase):
    def test_event_decorated_function_returns_event(self):
        @core.event()
        def _test():
            pass

        self.assertIsInstance(_test, core.Event)

    def test_event_decorated_method_returns_event(self):
        class EventTestClass:
            @core.event()
            def _test(_):
                pass

        instance = EventTestClass()
        self.assertIsInstance(instance._test, core.Event)

    def test_event_decorated_staticmethod_returns_event(self):
        class EventTestClass:
            @core.static_event()
            def _test():
                pass

        instance = EventTestClass()
        self.assertIsInstance(instance._test, core.Event)

    def test_event_decorated_classmethod_returns_event(self):
        class EventTestClass:
            @core.class_event()
            def _test(cls):
                pass

        instance = EventTestClass()
        self.assertIsInstance(instance._test, core.Event)

    def test_event_decorator_attr_passthrough(self):
        @core.event()
        def _test():
            """test docstring"""

        self.assertEqual(_test.name, "_test")
        self.assertEqual(_test.__doc__, "test docstring")

    def test_decorated_action_actually_runs(self):
        has_run = {"status": False}

        @core.event()
        def _test():
            has_run["status"] = True

        _test()

        self.assertTrue(has_run["status"])

    def test_decorated_method_gets_self(self):
        has_run = {"status": False}

        class X:
            @core.event()
            def _test(self_):
                has_run["status"] = True
                self.assertIsInstance(self_, X)

        x = X()
        x._test()

        self.assertTrue(has_run["status"])

    def test_decorated_classmethod_gets_class(self):
        has_run = {"status": False}

        class X:
            @core.class_event()
            def _test(cls):
                has_run["status"] = True
                self.assertIs(cls, X)

        x = X()
        x._test()

        self.assertTrue(has_run["status"])

    def test_decorated_staticmethod_gets_nothing(self):
        has_run = {"status": False}

        class X:
            @core.static_event()
            def _test(*args):
                has_run["status"] = True
                self.assertEqual(len(args), 0)

        x = X()
        x._test()

        self.assertTrue(has_run["status"])


class TestEvents(unittest.TestCase):
    def test_event_individual_status_hooks_on_success(self):
        results = list()
        expected = ["about_to_run", "completed", "exited"]

        def about_to_run_cbk(_):
            results.append("about_to_run")

        def completed_cbk(_):
            results.append("completed")

        def crashed_cbk(_):
            results.append("crashed")

        def exited_cbk(_):
            results.append("exited")

        def action():
            pass

        event = core.Event(action)
        event.about_to_run.connect(about_to_run_cbk)
        event.completed.connect(completed_cbk)
        event.crashed.connect(crashed_cbk)
        event.exited.connect(exited_cbk)
        event()

        self.assertCountEqual(results, expected)

    def test_event_individual_status_hooks_on_crash(self):
        results = list()
        expected = ["about_to_run", "crashed", "exited"]

        def about_to_run_cbk(_):
            results.append("about_to_run")

        def completed_cbk(_):
            results.append("completed")

        def crashed_cbk(_):
            results.append("crashed")

        def exited_cbk(_):
            results.append("exited")

        def action():
            raise Exception()

        event = core.Event(action)
        event.about_to_run.connect(about_to_run_cbk)
        event.completed.connect(completed_cbk)
        event.crashed.connect(crashed_cbk)
        event.exited.connect(exited_cbk)

        with self.assertRaises(Exception):
            event()

        self.assertCountEqual(results, expected)

    def test_event_replaces_method(self):
        results = list()
        expected = ["about_to_run", "crashed", "exited"]
        function_run = False

        def about_to_run_cbk(_):
            results.append("about_to_run")

        def completed_cbk(_):
            results.append("completed")

        def crashed_cbk(_):
            results.append("crashed")

        def exited_cbk(_):
            results.append("exited")

        class TestClass:
            def action(self):
                nonlocal function_run
                function_run = True
                raise ZeroDivisionError()

        instance = TestClass()
        self.assertFalse(function_run)
        event = core.Event(instance.action)
        event.about_to_run.connect(about_to_run_cbk)
        event.completed.connect(completed_cbk)
        event.crashed.connect(crashed_cbk)
        event.exited.connect(exited_cbk)

        with self.assertRaises(ZeroDivisionError):
            event()
        self.assertTrue(function_run)
        self.assertCountEqual(results, expected)


class TestGlobalCallbackFunctions(unittest.TestCase):
    def test_add_global_event_callback(self):
        status = core.EventStatus.ABOUT_TO_RUN

        def cbk(_):
            pass

        core.add_global_event_callback(status, cbk)
        self.assertIn(cbk, core._global_event_callbacks[status])

    def test_clear_global_event_callbacks(self):
        status = core.EventStatus.ABOUT_TO_RUN

        def cbk(_):
            pass

        core.add_global_event_callback(status, cbk)
        self.assertIn(cbk, core._global_event_callbacks[status])

        core.clear_global_event_callbacks(status)
        self.assertNotIn(cbk, core._global_event_callbacks[status])


class TestGlobalEventCallbacks(unittest.TestCase):
    def test_global_event_callbacks_success(self):
        self.maxDiff = None
        results = list()
        expected = [
            "about_to_run_a_event",
            "about_to_run_b_event",
            "progress_a_one",
            "progress_a_two",
            "progress_a_three",
            "progress_b_one",
            "progress_b_two",
            "progress_b_three",
            "completed_a_event",
            "completed_b_event",
            "exited_a_event",
            "exited_b_event",
        ]

        def about_to_run(data):
            results.append("about_to_run_{}".format(data.name))

        def completed(data):
            results.append("completed_{}".format(data.name))

        def crashed(data):
            results.append("crashed_{}".format(data.name))

        def exited(data):
            results.append("exited_{}".format(data.name))

        def progress_updated(data):
            results.append("progress_{}".format(data.item))

        @core.event()
        def a_event():
            for _ in a_event.track(["a_one", "a_two", "a_three"]):
                pass

        @core.event()
        def b_event():
            for _ in b_event.track(["b_one", "b_two", "b_three"]):
                pass

        core.add_global_event_callback(core.EventStatus.ABOUT_TO_RUN, about_to_run)

        core.add_global_event_callback(core.EventStatus.COMPLETED, completed)

        core.add_global_event_callback(core.EventStatus.CRASHED, crashed)

        core.add_global_event_callback(core.EventStatus.EXITED, exited)

        core.add_global_event_callback(
            core.EventStatus.PROGRESS_UPDATED, progress_updated
        )

        self.assertFalse(results)

        a_event()
        b_event()

        self.assertCountEqual(results, expected)

    def test_global_event_callbacks_observed(self):
        self.maxDiff = None
        results = list()
        expected = [
            "about_to_run_a_event",
            "about_to_run_b_event",
            "progress_a_one",
            "progress_a_two",
            "progress_a_three",
            "progress_b_one",
            "progress_b_two",
            "progress_b_three",
            "completed_a_event",
            "completed_b_event",
            "exited_a_event",
            "exited_b_event",
        ]

        @core.event()
        def a_event():
            for _ in a_event.track(["a_one", "a_two", "a_three"]):
                pass

        @core.event()
        def b_event():
            for _ in b_event.track(["b_one", "b_two", "b_three"]):
                pass

        @core.observes(core.EventStatus.ABOUT_TO_RUN)
        def about_to_run(data):
            results.append("about_to_run_{}".format(data.name))

        @core.observes(core.EventStatus.COMPLETED)
        def completed(data):
            results.append("completed_{}".format(data.name))

        @core.observes(core.EventStatus.CRASHED)
        def crashed(data):
            results.append("crashed_{}".format(data.name))

        @core.observes(core.EventStatus.EXITED)
        def exited(data):
            results.append("exited_{}".format(data.name))

        @core.observes(core.EventStatus.PROGRESS_UPDATED)
        def progress_updated(data):
            results.append("progress_{}".format(data.item))

        self.assertFalse(results)

        a_event()
        b_event()

        self.assertCountEqual(results, expected)

    def test_event_call_tagging(self):
        results = list()
        expected = ["event run", "after"]
        expected_tag = ("key", "value")

        @core.event()
        def an_event():
            results.append("event run")
            an_event["key"] = "value"

        def after(data):
            # this will just confirm that this function actually ran
            results.append("after")
            tags = list(data.tags.items())
            self.assertEqual(len(tags), 1)
            tags = tags[0]
            self.assertEqual(tags, expected_tag)

        an_event.exited.connect(after)

        an_event()

        self.assertCountEqual(expected, results)

    def test_event_call_recursive_tagging(self):
        results = list()
        expected = ["event run0", "event run1", ("key1", "value1"), ("key0", "value0")]

        from itertools import count

        counter = count()

        @core.event()
        def an_event():
            call_count = counter.__next__()
            call_count_str = str(call_count)
            results.append("event run" + call_count_str)
            an_event["key" + call_count_str] = "value" + call_count_str

            # we recurse exactly twice
            if call_count < 1:
                an_event()

        def after(data):
            # this will just confirm that this function actually ran
            tags = list(data.tags.items())
            self.assertEqual(len(tags), 1)
            tag = tags[0]
            results.append(tag)

        an_event.exited.connect(after)

        an_event()

        self.assertCountEqual(expected, results)

    def test_method_event_call_tagging(self):
        results = list()
        expected = ["event run", "after"]
        expected_tag = ("key", "value")

        class EventClass:
            @core.event()
            def an_event(self):
                results.append("event run")
                self.an_event["key"] = "value"

        def after(data):
            # this will just confirm that this function actually ran
            results.append("after")
            tags = list(data.tags.items())
            self.assertEqual(len(tags), 1)
            tags = tags[0]
            self.assertEqual(tags, expected_tag)

        event_instance = EventClass()
        event_instance.an_event.exited.connect(after)

        event_instance.an_event()

        self.assertEqual(expected, results)

    def test_method_event_call_recursive_tagging(self):
        results = list()
        expected = ["event run0", "event run1", ("key1", "value1"), ("key0", "value0")]

        from itertools import count

        counter = count()

        class EventClass:
            @core.event()
            def an_event(self):
                call_count = counter.__next__()
                call_count_str = str(call_count)
                results.append("event run" + call_count_str)
                self.an_event["key" + call_count_str] = "value" + call_count_str

                # we recurse exactly twice
                if call_count < 1:
                    self.an_event()

        def after(data):
            # this will just confirm that this function actually ran
            tags = list(data.tags.items())
            self.assertEqual(len(tags), 1)
            tag = tags[0]
            results.append(tag)

        event_instance = EventClass()
        event_instance.an_event.exited.connect(after)

        event_instance.an_event()

        self.assertEqual(expected, results)


class TestEventProgress(unittest.TestCase):
    def test_function_decorated_event_progress(self):
        results = list()
        expected = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]

        def handle_progress_update(progress_data):
            self.assertIsInstance(progress_data.event, core.Event)
            self.assertIsInstance(progress_data.item, int)
            self.assertEqual(progress_data.name, "test")
            results.append(progress_data.completion)

        @core.event()
        def an_event():
            data = list(range(10))
            for _ in an_event.track(data, name="test"):
                pass

        self.assertFalse(results)

        an_event.progress_updated.connect(handle_progress_update)
        an_event()

        self.assertEqual(results, expected)

    def test_method_decorated_event_progress(self):
        results = list()
        expected = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]

        def handle_progress_update(progress_data):
            self.assertIsInstance(progress_data.event, core.Event)
            self.assertIsInstance(progress_data.item, int)
            self.assertEqual(progress_data.name, "test")
            results.append(progress_data.completion)

        class EventClass:
            @core.event()
            def an_event(self):
                data = list(range(10))
                for _ in self.an_event.track(data, name="test"):
                    pass

        self.assertFalse(results)

        event_instance = EventClass()
        event_instance.an_event.progress_updated.connect(handle_progress_update)
        event_instance.an_event()

        self.assertEqual(results, expected)


if __name__ == "__main__":
    unittest.main()
