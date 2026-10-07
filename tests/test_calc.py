"""运行：python tests/test_calc.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
import selfcheck  # noqa: E402

if __name__ == "__main__":
    bad, lines = selfcheck.run()
    print("\n".join(lines))
    sys.exit(1 if bad else 0)
