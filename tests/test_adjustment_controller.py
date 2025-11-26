import unittest

from src.core.adjustment_controller import AdjustmentController, AdjustmentControllerError
from src.core.adjustments import AdjustmentState


class AdjustmentControllerTest(unittest.TestCase):
    def test_update_factor_notifies_listener(self) -> None:
        captured: list[AdjustmentState] = []
        controller = AdjustmentController(lambda state: captured.append(state))

        controller.update_factor("brightness", 1.5)
        controller.update_factor("contrast", 0.8)
        controller.update_temperature(20)

        self.assertEqual(len(captured), 3)
        last_state = captured[-1]
        self.assertAlmostEqual(last_state.brightness, 1.5)
        self.assertAlmostEqual(last_state.contrast, 0.8)
        self.assertEqual(last_state.temperature, 20)

    def test_reset_restores_defaults(self) -> None:
        controller = AdjustmentController()
        controller.update_factor("saturation", 1.8)
        controller.update_temperature(-30)
        controller.reset()

        state = controller.state
        self.assertAlmostEqual(state.brightness, 1.0)
        self.assertAlmostEqual(state.contrast, 1.0)
        self.assertAlmostEqual(state.saturation, 1.0)
        self.assertAlmostEqual(state.sharpness, 1.0)
        self.assertEqual(state.temperature, 0)

    def test_invalid_field_raises(self) -> None:
        controller = AdjustmentController()
        with self.assertRaises(AdjustmentControllerError):
            controller.update_factor("invalid", 1.0)


if __name__ == "__main__":
    unittest.main()
