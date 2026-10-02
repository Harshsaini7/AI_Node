"""
AI Loan Customer Agent
======================
A simple AI Voice Agent that acts as a Customer Success Partner
for a bank's loan-program outreach.

The agent reads a spreadsheet, finds PENDING customers,
calls them one by one, determines loan interest, and
updates the spreadsheet accordingly.

Phase 1.3 - Read & Find PENDING Customers
"""

from dotenv import load_dotenv
from spreadsheet_manager import load_spreadsheet, validate_spreadsheet, get_pending_customers

# Load environment variables from .env file
load_dotenv()

# Path to the spreadsheet
SPREADSHEET_PATH = "loan_leads.xlsx"


def main():
    """Entry point for the AI Loan Customer Agent."""
    print("=" * 50)
    print("   AI LOAN CUSTOMER AGENT")
    print("=" * 50)
    print()

    # Step 1: Load the spreadsheet
    print("[1] Loading spreadsheet...")
    try:
        workbook = load_spreadsheet(SPREADSHEET_PATH)
        print(f"    Loaded: {SPREADSHEET_PATH}")
    except FileNotFoundError:
        print(f"    ERROR: '{SPREADSHEET_PATH}' not found!")
        print("    Run 'python create_sample_data.py' first.")
        return
    except Exception as e:
        print(f"    ERROR: Could not load spreadsheet - {e}")
        return

    # Step 2: Validate the spreadsheet format
    print("[2] Validating spreadsheet format...")
    try:
        validate_spreadsheet(workbook)
        print("    Format is valid.")
    except ValueError as e:
        print(f"    ERROR: {e}")
        return

    # Step 3: Find pending customers
    print("[3] Finding PENDING customers...")
    pending = get_pending_customers(workbook)
    print(f"    Found {len(pending)} PENDING customers.")
    print()

    if not pending:
        print("No PENDING customers to process. All done!")
        return

    # Display the queue
    print(f"    {'#':<4} {'Name':<20} {'Phone':<15}")
    print(f"    {'-'*39}")
    for i, customer in enumerate(pending, 1):
        print(f"    {i:<4} {customer['name']:<20} {customer['phone']:<15}")

    print()
    print(f"Ready to process {len(pending)} customers.")
    print("(Processing loop coming in Phase 2.1)")
    print("=" * 50)


if __name__ == "__main__":
    main()
