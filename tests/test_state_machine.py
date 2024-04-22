import unittest
from observatory.state_machine import (
    Machine,
    State,
    Trigger,
    ANY_STATE,
    StateTransitionError,
    TriggerValidityError,
    ObjectBindingError,
)


class DummyMachine(Machine):
    # Define states
    state_a = State("A")
    state_b = State("B")
    state_c = State("C")

    # Orphan states, no defined triggers
    state_d = State("D", require_trigger=False)
    state_e = State("E")

    # States for testing ANY_STATE transitions
    state_x = State("X")
    state_y = State("Y")
    state_z = State("Z")

    # Define default state
    default_state = state_a

    # Define triggers
    trigger_ab = Trigger(state_a >> state_b)
    trigger_bc = Trigger(state_b >> state_c)
    trigger_ca = Trigger(state_c >> state_a)
    trigger_x = Trigger(ANY_STATE >> state_x)
    trigger_y = Trigger(ANY_STATE >> state_y)
    trigger_z = Trigger(
        ANY_STATE >> state_z,
        state_d >> state_y
    )


class TestStateMachine(unittest.TestCase):
    def setUp(self):
        self.machine = DummyMachine()

    def test_initial_state(self):
        self.assertEqual(
            self.machine.get_state(),
            DummyMachine.state_a,
            "Machine does not start in the default state.",
        )

    def test_transition_ab(self):
        self.machine.trigger_ab()
        self.assertEqual(
            self.machine.get_state(),
            DummyMachine.state_b,
            "Transition from state A to B failed.",
        )

    def test_transition_bc(self):
        # First, transition to state B
        self.machine.trigger_ab()
        # Then, transition to state C
        self.machine.trigger_bc()
        self.assertEqual(
            self.machine.get_state(),
            DummyMachine.state_c,
            "Transition from state B to C failed.",
        )

    def test_invalid_trigger(self):
        with self.assertRaises(TriggerValidityError):
            self.machine.trigger_bc()

    def test_unbound_trigger_call(self):
        unbound_trigger = Trigger(DummyMachine.state_a >> DummyMachine.state_b)
        with self.assertRaises(ObjectBindingError):
            unbound_trigger()

    def test_transition_to_self(self):
        # Trigger that transitions to the same state it's triggered from
        self.machine.trigger_ab()  # Move to state B
        self.machine.trigger_bc()  # Move to state C
        self.machine.trigger_ca()  # Back to state A
        self.assertEqual(
            self.machine.get_state(),
            DummyMachine.state_a,
            "Transition back to initial state failed.",
        )

    def test_require_trigger_flag(self):
        # Move to an orphan state that does not require a trigger
        self.machine.set_state(DummyMachine.state_d)
        self.assertEqual(
            self.machine.get_state(),
            DummyMachine.state_d,
            "Transition to a state without require_trigger flag failed.",
        )
        with self.assertRaises(StateTransitionError):
            self.machine.set_state(DummyMachine.state_e)

    def test_any_state_to_x(self):
        self.machine.trigger_x()
        self.assertEqual(
            self.machine.get_state(),
            DummyMachine.state_x,
            "Transition from A to X failed.",
        )
        # From B to A using ANY_STATE
        self.machine.trigger_y()
        self.assertEqual(
            self.machine.get_state(),
            DummyMachine.state_y,
            "X transition to Y failed.",
        )

        # Transition from Y to Y (to itself) using ANY_STATE
        self.machine.trigger_y()
        self.assertEqual(
            self.machine.get_state(),
            DummyMachine.state_y,
            "ANY_STATE transition to self failed.",
        )

    def test_any_state_trigger_validity(self):
        # Ensuring ANY_STATE trigger is always valid
        self.machine.trigger_ab()  # Transition to B
        self.assertTrue(
            self.machine.trigger_x.is_ready(),
            "ANY_STATE trigger to X should be ready.",
        )
        self.machine.trigger_bc()  # Transition to C
        self.assertTrue(
            self.machine.trigger_y.is_ready(),
            "ANY_STATE trigger to Y should be ready.",
        )

    def test_any_state_trigger_overrides(self):
        self.machine.set_state(self.machine.state_a)
        self.machine.trigger_z()
        self.assertEqual(
            self.machine.get_state(), self.machine.state_z,
            "ANY_STATE trigger should transition to Z",
        )
        self.machine.set_state(self.machine.state_d)
        self.machine.trigger_z()
        self.assertEqual(
            self.machine.get_state(), self.machine.state_y,
            "Override trigger should transition to Y",
        )


if __name__ == "__main__":
    unittest.main()
