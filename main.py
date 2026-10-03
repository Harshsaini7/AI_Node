"""
AI Loan Customer Agent
======================
A simple AI Voice Agent that acts as a Customer Success Partner
for a bank's loan-program outreach.

The agent reads a spreadsheet, finds PENDING customers,
processes them one by one, determines loan interest, and
updates the spreadsheet accordingly.

Commands:
    start  - Start processing PENDING customers
    stop   - Stop after current customer finishes
    status - Show current agent status
    reset  - Regenerate fresh test data
    quit   - Exit the application

Phase 2.2 - Terminal Start/Stop with Threading
"""

import time

from dotenv import load_dotenv
from agent import Agent

# Load environment variables from .env file
load_dotenv()

# Path to the spreadsheet
SPREADSHEET_PATH = "loan_leads.xlsx"


def print_banner():
    """Print the application banner."""
    print()
    print("=" * 50)
    print("   AI LOAN CUSTOMER AGENT")
    print("=" * 50)
    print()
    print("Commands:")
    print("  start  - Start processing customers")
    print("  stop   - Stop the agent gracefully")
    print("  status - Show current agent status")
    print("  reset  - Regenerate fresh test data")
    print("  quit   - Exit the application")
    print()


def handle_reset():
    """Regenerate fresh test data."""
    from create_sample_data import create_sample_spreadsheet
    create_sample_spreadsheet(SPREADSHEET_PATH)


def main():
    """Entry point - interactive terminal loop."""
    print_banner()

    agent = Agent(SPREADSHEET_PATH)

    while True:
        try:
            # Show prompt with current status
            prompt = f"[{agent.status}]> "
            command = input(prompt).strip().lower()

            if command == "start":
                agent.start()
                # Give the thread a moment to start and print its first output
                time.sleep(0.5)

            elif command == "stop":
                agent.stop()

            elif command == "status":
                print(f"  Agent Status:     {agent.status}")
                if agent.current_customer:
                    print(f"  Current Customer: {agent.current_customer}")
                else:
                    print(f"  Current Customer: -")
                print(f"  Processed:        {agent.summary['total_processed']}")
                print(f"  Interested:       {agent.summary['interested']}")
                print(f"  Not Interested:   {agent.summary['not_interested']}")

            elif command == "reset":
                if agent.is_running:
                    print("Cannot reset while agent is running. Stop it first.")
                else:
                    handle_reset()
                    agent = Agent(SPREADSHEET_PATH)
                    print("Agent reset. Ready to start.")

            elif command == "quit" or command == "exit":
                if agent.is_running:
                    print("Stopping agent first...")
                    agent.stop()
                    time.sleep(1)
                print("Goodbye!")
                break

            elif command == "":
                continue

            else:
                print(f"Unknown command: '{command}'")
                print("Commands: start, stop, status, reset, quit")

        except KeyboardInterrupt:
            print("\nInterrupted! Shutting down...")
            if agent.is_running:
                agent.stop()
                time.sleep(1)
            break


if __name__ == "__main__":
    main()
