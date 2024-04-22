import unittest
from observatory import EventHook
from observatory.state_graph import (
    Value,
    Derived,
    Observer,
    ValueStatus,
    derived,
    CycleDetectedError,
    cycle_check,
)

from itertools import count
counter = count()


class TestValue(unittest.TestCase):
    def test_value_set_get(self):
        """Test setting and getting the value of a Value node."""
        initial_value = 10
        new_value = 20
        value_node = Value(initial_value, name="TestValue")

        # Test initial value is set correctly
        self.assertEqual(
            value_node.get(),
            initial_value,
            "Initial value should be equal to the value passed in the constructor.",
        )

        # Test updating the value
        value_node.set(new_value)
        self.assertEqual(
            value_node.get(), new_value, "Value should be updated to the new value."
        )

        # Test notset error behavior
        value_node.set(ValueStatus.NOT_SET)  # type: ignore
        with self.assertRaises(ValueError):
            value_node.get()


class TestGraphLibrary(unittest.TestCase):
    def setUp(self):
        # Setup common to all tests can be done here
        # For example, create some nodes that can be used in multiple tests
        self.value_a = Value(1, name="A")
        self.value_b = Value(2, name="B")

    # Using a simple sum for the compute function
    def sum(self, input_data):
        return sum(input_data)

    def test_derived_node_computation(self):
        """Test that a Derived node correctly computes its value based on inputs."""

        derived_c = Derived(
            inputs=[self.value_a, self.value_b],
            compute=self.sum,
            name="C",
        )
        self.assertEqual(
            derived_c.get(),
            3,
            "Derived node C should correctly compute the sum of A and B.",
        )

    def test_update_propagates_when_values_update(self):
        """Test that updates to Value nodes propagate correctly to Derived nodes."""
        self.value_a.set(2)  # Update value of A
        derived_c = Derived(
            inputs=[self.value_a, self.value_b],
            compute=self.sum,
            name="C",
        )
        self.assertEqual(
            derived_c.get(), 4, "Derived node C should update based on new value of A."
        )

    def test_cycle_detection(self):
        """Test that cycles are correctly detected."""
        derived_c = Derived(
            inputs=[self.value_a],
            compute=self.sum,
            name="C",
        )
        self.value_a._outputs.append(
            derived_c
        )  # Artificially create a potential cycle for testing

        # Attempt to create a cycle by misusing the internals
        with self.assertRaises(CycleDetectedError):
            cycle_check(
                self.value_a
            )

    def test_derived_decorator(self):
        """Test the derived decorator for creating derived nodes."""

        @derived(inputs=[self.value_a, self.value_b], name="D")
        def compute_sum(input_data):
            return sum(input_data)

        self.assertIsInstance(
            compute_sum,
            Derived,
            "The derived decorator should create a Derived instance.",
        )
        self.assertEqual(
            compute_sum.get(),
            3,
            "Derived node D should correctly compute the sum of A and B using the decorator.",
        )

    def test_pending_flag_propagation(self):
        """Test that the pending flag propagates correctly through the graph."""
        derived_c = Derived(
            inputs=[self.value_a, self.value_b],
            compute=self.sum,
            name="C",
        )

        derived_d = Derived(
            inputs = [derived_c],
            compute = lambda _: next(counter),
            name = "D"
        )


        self.assertTrue(
            derived_c._needs_update,
            "Derived node C should need an update initially."
        )

        _ = derived_d.get()  # Trigger computation

        self.assertFalse(
            derived_c._needs_update,
            "Derived node C should not need update after computation."
        )
        self.assertTrue(derived_c._has_update)
        self.assertFalse(
            derived_d._needs_update,
            "Derived node D should not need update after computation "
        )
        self.assertTrue(derived_d._has_update)

        self.value_a.set(3)

        self.assertTrue(
            derived_c._needs_update,
            "Derived node C should be marked as pending after an input is updated.",
        )
        self.assertTrue(
            derived_d._needs_update,
            "Derived node D should be marked as pending after grandparent input is updated.",
        )

        derived_d.get()
        self.value_a.set(3)

        self.assertFalse(
            derived_c._needs_update,
            "Derived node C should be marked as pending after an input is updated.",
        )
        self.assertFalse(
            derived_d._needs_update,
            "Derived node D should be marked as pending after grandparent input is updated.",
        )


class TestIdempotentComputePendingFlagPropagation(unittest.TestCase):

    def setUp(self):
        self.updated_emitted = False

    def set(self, *_):
        self.updated_emitted = True

    def test_idempotent_compute(self):
        """Test that a Derived node's compute returning the same value clears the pending flag."""
        initial_value = Value(-5, name="InitialValue")

        def absolute(input_data):
            return abs(input_data[0])

        # Derived node with some idempotent potential
        absolute_value = Derived(
            inputs=[initial_value],
            compute=absolute,
            name="AbsoluteValue",
        )

        # Derived node that should not update after absolute_value
        after_absolute = Derived(
            inputs=[absolute_value],
            compute=lambda x: next(counter),
            name="AfterAbsolute"
        )

        after_absolute.updated.connect(self.set)
        self.assertFalse(self.updated_emitted)
        self.assertTrue(after_absolute._needs_update)
        _ = after_absolute.get()
        self.assertTrue(self.updated_emitted)
        self.updated_emitted = False
        self.assertEqual(absolute_value._value, 5)

        initial_value.set(2)
        self.assertTrue(after_absolute._needs_update)
        _ = after_absolute.get()
        self.assertEqual(absolute_value._value, 2)
        self.assertTrue(self.updated_emitted)
        self.updated_emitted = False

        initial_value.set(-2)
        _ = after_absolute.get()
        self.assertEqual(absolute_value._value, 2)
        self.assertFalse(self.updated_emitted)
        self.updated_emitted = False

        initial_value.set(-3)
        _ = after_absolute.get()
        self.assertTrue(self.updated_emitted)


class TestEventDependencies(unittest.TestCase):
    def test_observer_reacts_to_event_hook(self):
        """Test that an Observer node updates its pending state upon an event."""
        event_hook = EventHook()
        observer_node = Observer(name="observer", event_hook=event_hook)
        with self.assertRaises(ValueError):
            observer_node.get()
        event_hook.emit("updated")
        self.assertEqual(observer_node.get(), "updated")


if __name__ == "__main__":
    unittest.main()
