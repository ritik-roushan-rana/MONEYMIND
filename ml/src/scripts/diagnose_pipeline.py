# ml/src/scripts/diagnose_pipeline.py
#
# One-off diagnostic script — not part of the pipeline. Run this manually
# to sanity-check feature store numbers before trusting them downstream.

import pandas as pd
from preprocessing.persist import PROCESSED_DIR

pd.set_option("display.width", 140)
pd.set_option("display.max_colwidth", 50)


def main():
    df = pd.read_parquet(PROCESSED_DIR / "transactions_with_income_flags.parquet")
    df["txn_date"] = pd.to_datetime(df["txn_date"])
    df["month"] = df["txn_date"].dt.to_period("M").astype(str)

    for account in df["source_file"].unique():
        acc_df = df[df["source_file"] == account]
        print(f"\n{'='*70}\n{account}\n{'='*70}")

        # 1. Which single month has the highest total_expenses, and what's in it?
        monthly_expenses = acc_df[acc_df["txn_type"] == "debit"].groupby("month")["amount"].sum()
        if monthly_expenses.empty:
            continue
        worst_month = monthly_expenses.idxmax()
        print(f"\nWorst expense month: {worst_month} (total debits: {monthly_expenses[worst_month]:.2f})")

        worst_month_debits = acc_df[(acc_df["month"] == worst_month) & (acc_df["txn_type"] == "debit")]
        top_debits = worst_month_debits.nlargest(10, "amount")[["txn_date", "clean_merchant", "category", "amount"]]
        print("\nTop 10 debits in that month:")
        print(top_debits.to_string(index=False))

        # 2. Category breakdown of ALL expenses for this account — flags if
        # a "Transfer" category is contributing heavily to total_expenses,
        # which would mean money moving between the user's own accounts is
        # being double-counted as spending.
        cat_totals = acc_df[acc_df["txn_type"] == "debit"].groupby("category")["amount"].sum().sort_values(ascending=False)
        print(f"\nExpense total by category (all months):")
        print(cat_totals.to_string())

        # 3. Refund/reversal pairs — does a REV-/reversal credit exist for
        # every matching debit, and if so, is it being netted anywhere, or
        # are both counted independently (debit as expense, credit ignored
        # since it's not tagged as income)?
        reversals = acc_df[acc_df["clean_merchant"].str.contains("REV", case=False, na=False)]
        if len(reversals):
            print(f"\nReversal-looking transactions ({len(reversals)}):")
            print(reversals[["txn_date", "clean_merchant", "txn_type", "amount"]].to_string(index=False))

    # 4. Global check: CLUB LLOYDS FEE vs WAIVED — do these amounts match
    # 1:1 by date, confirming they should net to zero rather than both
    # counting separately (fee as expense, waiver as unrelated "income")?
    print(f"\n{'='*70}\nCLUB LLOYDS FEE / WAIVED check\n{'='*70}")
    fee = df[df["clean_merchant"] == "CLUB LLOYDS FEE"][["txn_date", "amount"]].reset_index(drop=True)
    waived = df[df["clean_merchant"] == "CLUB LLOYDS WAIVED"][["txn_date", "amount"]].reset_index(drop=True)
    print(f"Fee occurrences: {len(fee)}, Waived occurrences: {len(waived)}")
    if len(fee) and len(waived):
        merged = pd.merge(fee, waived, on="txn_date", suffixes=("_fee", "_waived"), how="outer")
        mismatches = merged[merged["amount_fee"] != merged["amount_waived"]]
        print(f"Dates where fee and waiver DON'T match 1:1: {len(mismatches)}")
        if len(mismatches):
            print(mismatches.to_string(index=False))


if __name__ == "__main__":
    main()