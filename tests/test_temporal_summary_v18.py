"""Postprocessing accepts original adaptive telemetry's descriptive labels."""
import unittest
from scripts.summarize_temporal_v18 import numeric_telemetry


class TelemetrySummaryTests(unittest.TestCase):
    def test_labels_are_not_interpreted_as_numeric_cost(self):
        rows=[{'telemetry':{'cpu_seconds':2.,'forecasts':4,'scope':'after restore'}},
              {'telemetry':{'cpu_seconds':4.,'forecasts':8,'scope':'after restore'}}]
        self.assertEqual(numeric_telemetry(rows),{'cpu_seconds':3.,'forecasts':6.})


if __name__=='__main__':
    unittest.main()
