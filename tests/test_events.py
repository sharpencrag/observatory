import unittest
from observatory import events


class EventHookTests(unittest.TestCase):
    """Base class - actual test scenarios are added in TestCases below.

    This allows us to run the same tests on event hooks that are created in
    various ways and with different scopes.
    """

    def setUp(self):
        self.event_hook = events.EventHook()
        self.event_hook_two = events.EventHook()
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
        with self.assertRaises(events.EventHookError):
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
        @events.observes(self.event_hook)
        def func():
            self.result = "function"

        self.assertIsNone(self.result)
        self.event_hook.emit()
        self.assertEqual(self.result, "function")


class TestEventHookAsClassAttribute(EventHookTests):
    """Ensures all the tests work when an event hook is a descriptor"""

    class AnotherClass:
        event_hook = events.EventHook()

    def setUp(self):
        self.result = None
        self.result_two = None
        self.event_hook = self.AnotherClass().event_hook
        self.event_hook_two = self.AnotherClass().event_hook


class TestEventDecorator(unittest.TestCase):
    def test_event_decorated_function_returns_event(self):
        @events.event()
        def _test():
            pass

        self.assertIsInstance(_test, events.Event)

    def test_event_decorated_method_returns_event(self):
        class EventTestClass:
            @events.event()
            def _test(_):
                pass

        instance = EventTestClass()
        self.assertIsInstance(instance._test, events.Event)

    def test_event_decorated_staticmethod_returns_event(self):
        class EventTestClass:
            @events.static_event()
            def _test():
                pass

        instance = EventTestClass()
        self.assertIsInstance(instance._test, events.Event)

    def test_event_decorated_classmethod_returns_event(self):
        class EventTestClass:
            @events.class_event()
            def _test(cls):
                pass

        instance = EventTestClass()
        self.assertIsInstance(instance._test, events.Event)

    def test_event_decorator_attr_passthrough(self):
        @events.event()
        def _test():
            """test docstring"""

        self.assertEqual(_test.name, "_test")
        self.assertEqual(_test.__doc__, "test docstring")

    def test_decorated_action_actually_runs(self):
        has_run = {"status": False}

        @events.event()
        def _test():
            has_run["status"] = True

        _test()

        self.assertTrue(has_run["status"])

    def test_decorated_method_gets_self(self):
        has_run = {"status": False}

        class X:
            @events.event()
            def _test(self_):
                has_run["status"] = True
                self.assertIsInstance(self_, X)

        x = X()
        x._test()

        self.assertTrue(has_run["status"])

    def test_decorated_classmethod_gets_class(self):
        has_run = {"status": False}

        class X:
            @events.class_event()
            def _test(cls):
                has_run["status"] = True
                self.assertIs(cls, X)

        x = X()
        x._test()

        self.assertTrue(has_run["status"])

    def test_decorated_staticmethod_gets_nothing(self):
        has_run = {"status": False}

        class X:
            @events.static_event()
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

        event = events.Event(action)
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

        event = events.Event(action)
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
        event = events.Event(instance.action)
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
        status = events.EventStatus.ABOUT_TO_RUN

        def cbk(_):
            pass

        events.add_global_event_callback(status, cbk)
        self.assertIn(cbk, events._global_event_callbacks[status])

    def test_clear_global_event_callbacks(self):
        status = events.EventStatus.ABOUT_TO_RUN

        def cbk(_):
            pass

        events.add_global_event_callback(status, cbk)
        self.assertIn(cbk, events._global_event_callbacks[status])

        events.clear_global_event_callbacks(status)
        self.assertNotIn(cbk, events._global_event_callbacks[status])


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

        @events.event()
        def a_event():
            for _ in a_event.track(["a_one", "a_two", "a_three"]):
                pass

        @events.event()
        def b_event():
            for _ in b_event.track(["b_one", "b_two", "b_three"]):
                pass

        events.add_global_event_callback(events.EventStatus.ABOUT_TO_RUN, about_to_run)

        events.add_global_event_callback(events.EventStatus.COMPLETED, completed)

        events.add_global_event_callback(events.EventStatus.CRASHED, crashed)

        events.add_global_event_callback(events.EventStatus.EXITED, exited)

        events.add_global_event_callback(
            events.EventStatus.PROGRESS_UPDATED, progress_updated
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

        @events.event()
        def a_event():
            for _ in a_event.track(["a_one", "a_two", "a_three"]):
                pass

        @events.event()
        def b_event():
            for _ in b_event.track(["b_one", "b_two", "b_three"]):
                pass

        @events.observes(events.EventStatus.ABOUT_TO_RUN)
        def about_to_run(data):
            results.append("about_to_run_{}".format(data.name))

        @events.observes(events.EventStatus.COMPLETED)
        def completed(data):
            results.append("completed_{}".format(data.name))

        @events.observes(events.EventStatus.CRASHED)
        def crashed(data):
            results.append("crashed_{}".format(data.name))

        @events.observes(events.EventStatus.EXITED)
        def exited(data):
            results.append("exited_{}".format(data.name))

        @events.observes(events.EventStatus.PROGRESS_UPDATED)
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

        @events.event()
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

        @events.event()
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
            @events.event()
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
            @events.event()
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
            self.assertIsInstance(progress_data.event, events.Event)
            self.assertIsInstance(progress_data.item, int)
            self.assertEqual(progress_data.name, "test")
            results.append(progress_data.completion)

        @events.event()
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
            self.assertIsInstance(progress_data.event, events.Event)
            self.assertIsInstance(progress_data.item, int)
            self.assertEqual(progress_data.name, "test")
            results.append(progress_data.completion)

        class EventClass:
            @events.event()
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
