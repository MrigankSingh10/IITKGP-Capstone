import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from hr_navigator.ingestion.audit import audit  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument('archive', type=Path)
parser.add_argument('--raw-dir', type=Path, default=Path('data/raw'))
parser.add_argument('--report-dir', type=Path, default=Path('reports'))
args = parser.parse_args()
print(audit(args.archive, args.raw_dir, args.report_dir))
