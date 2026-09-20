import ast
import unittest
from pathlib import Path


SOURCE = (
    Path(__file__).parents[1]
    / "FlexScan"
    / "CloudPerimeterScan"
    / "python"
    / "LaunchExternalScanConnectors.py"
)


class RequestTimeoutTests(unittest.TestCase):
    def test_all_qualys_requests_have_a_timeout(self):
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        calls = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "requests":
                calls.append(node)

        self.assertEqual(len(calls), 3)
        self.assertTrue(all(any(keyword.arg == "timeout" for keyword in call.keywords) for call in calls))


if __name__ == "__main__":
    unittest.main()
