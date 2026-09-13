# ml/src/ingestion/run_ingestion.py

from pathlib import Path

from ingestion.csv_loader import load_csv
from ingestion.pdf_parser import parse_pdf

# Resolves to ml/data/raw regardless of your current working directory
RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"


def run_all_ingestion() -> list:
    all_transactions = []

    for csv_file in RAW_DIR.glob("*.csv"):
        print(f"Loading {csv_file.name}...")
        txns = load_csv(csv_file)
        print(f"  -> {len(txns)} transactions")
        all_transactions.extend(txns)

    for pdf_file in RAW_DIR.glob("*.pdf"):
        print(f"Parsing {pdf_file.name}...")
        try:
            txns = parse_pdf(pdf_file)
            print(f"  -> {len(txns)} transactions")
            all_transactions.extend(txns)
        except ValueError as e:
            print(f"  -> skipped: {e}")

    print(f"\nTotal: {len(all_transactions)} transactions")
    return all_transactions


if __name__ == "__main__":
    run_all_ingestion()