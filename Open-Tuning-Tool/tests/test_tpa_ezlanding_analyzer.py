import unittest
import pandas as pd
from fpv_tuner.core.pid_tuning.tpa_ezlanding_analyzer import analyze
from fpv_tuner.core.pid_tuning.tuning_context import TuningContext
from fpv_tuner.core.cli.schema import CliSchema, CliVariable
from unittest.mock import patch

class TestTpaEzlandingAnalyzer(unittest.TestCase):
    @patch('fpv_tuner.core.pid_tuning.tpa_ezlanding_analyzer.measure_landing_bounce')
    def test_analyzer_with_schema(self, mock_measure):
        """Test that the analyzer successfully extracts the default value from the schema."""
        # Mock the landing detector to return a valid bounce
        mock_measure.return_value = {"bounce_rms": 10.0}
        
        # Setup fake log dataframe and headers
        df = pd.DataFrame()
        pids = {}
        headers = {
            "tpa_low_rate": "20",
            "tpa_low_breakpoint": "1050",
            "thr_hover": "1300"
        }
        
        # Setup schema with a CliVariable
        schema = CliSchema()
        var = CliVariable(name="tpa_low_rate", default="20")
        schema.variables["tpa_low_rate"] = var
        
        context = TuningContext(schema=schema)
        
        rules = {
            "ez_landing": {
                "base_rate": 10,
                "bounce_multiplier": 2.5,
                "max_rate": 60,
                "status": "heuristic_unvalidated"
            }
        }
        
        recs = analyze(df, pids, headers, context, rules)
        
        # 10.0 * 2.5 = 25.0 + 10 = 35 rate
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0].changes["tpa_low_rate"], 35)
        self.assertEqual(recs[0].changes["tpa_low_breakpoint"], 1200) # 1300 - 100
        # Since firmware default was 20 and current was 20, it's NOT customized. Confidence = 0.8
        self.assertEqual(recs[0].confidence, 0.8)

if __name__ == '__main__':
    unittest.main()
