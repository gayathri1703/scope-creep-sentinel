"""
Scope Creep Sentinel - CLI entry point.

MVP note: client messages are simulated via keyboard input (no Gmail/Slack/
Teams integration yet - real integrations are a deliberate later step, see
README). This lets the whole agent pipeline be demoed without any external
service besides Amazon Bedrock.
"""

from __future__ import annotations

import sys
from pathlib import Path

from botocore.exceptions import ClientError
from strands.models import BedrockModel

from models.scope_models import DecisionOption
from services.project_state import ProjectState
from services.scope_ledger import ScopeLedger

DATA_DIR = Path(__file__).parent / "data"
SOW_PATH = DATA_DIR / "sample_sow.json"

BEDROCK_MODEL_ID = "anthropic.claude-sonnet-4-6"
BEDROCK_REGION = "ap-south-1"


def build_model() -> BedrockModel:
    # Credentials come from the AWS CLI configuration already set up on this
    # machine (aws configure / aws sso login). Nothing is hard-coded here,
    # and nothing should be.
    return BedrockModel(model_id=BEDROCK_MODEL_ID, region_name=BEDROCK_REGION)


def print_header(text: str) -> None:
    print("\n" + "=" * 60)
    print(text)
    print("=" * 60)


def ask_decision() -> DecisionOption:
    options = {
        "1": DecisionOption.BILL_IT,
        "2": DecisionOption.NEGOTIATE_IT,
        "3": DecisionOption.DECLINE_IT,
    }
    while True:
        choice = input("\nChoose 1) BILL IT  2) NEGOTIATE IT  3) DECLINE IT: ").strip()
        if choice in options:
            return options[choice]
        print("Please enter 1, 2, or 3.")


def main() -> None:
    if not SOW_PATH.exists():
        print(f"SOW file not found at {SOW_PATH}")
        sys.exit(1)

    history_path = DATA_DIR / "history_ecommerce_website.json"
    ledger = ScopeLedger.load(sow_path=SOW_PATH, history_path=history_path)

    model = build_model()
    project = ProjectState(model=model, ledger=ledger)

    print_header(f"Scope Creep Sentinel - {ledger.sow.project_name}")
    print(f"Hourly rate: ${ledger.sow.hourly_rate}/hour")
    print(f"Revisions used: {ledger.sow.revisions_used}/{ledger.sow.revision_limit}")
    print("Type a simulated client message, or 'summary' / 'quit'.")

    while True:
        request_text = input("\nClient message > ").strip()
        if not request_text:
            continue
        if request_text.lower() in {"quit", "exit"}:
            break
        if request_text.lower() == "summary":
            print_header("Project Summary")
            for key, value in ledger.summary().items():
                print(f"{key}: {value}")
            continue

        try:
            outcome = project.handle_incoming_request(request_text)
        except ClientError as e:
            print(f"\nBedrock call failed: {e}")
            print(
                "If this is AccessDeniedException about account verification, "
                "that's an AWS account issue, not a code issue - try again later."
            )
            continue
        except Exception as e:  # noqa: BLE001 - top-level CLI safety net
            print(f"\nUnexpected error while processing request: {e}")
            continue

        print_header("Analysis")
        print(f"Classification : {outcome.analysis.classification.value}")
        print(f"Reason         : {outcome.analysis.reasoning}")
        print(f"Matched item   : {outcome.analysis.matched_sow_item}")
        print(f"Est. hours     : {outcome.analysis.estimated_hours}")
        print(f"Est. cost      : ${outcome.estimated_cost:.2f}")
        print(f"Risk level     : {outcome.risk_level}")
        print(f"Decision agent : {outcome.decision_reasoning}")

        if not outcome.requires_decision:
            print("\nWithin scope - no action needed. Logging and continuing.")
            project.finalize_decision(outcome, decision=None, sent_message=None)
            continue

        print_header("Choose how to respond")
        print(f"1) BILL IT:\n   {outcome.messages.bill_it}")
        print(f"\n2) NEGOTIATE IT:\n   {outcome.messages.negotiate_it}")
        print(f"\n3) DECLINE IT:\n   {outcome.messages.decline_it}")

        decision = ask_decision()
        message_map = {
            DecisionOption.BILL_IT: outcome.messages.bill_it,
            DecisionOption.NEGOTIATE_IT: outcome.messages.negotiate_it,
            DecisionOption.DECLINE_IT: outcome.messages.decline_it,
        }
        sent_message = message_map[decision]
        project.finalize_decision(outcome, decision=decision, sent_message=sent_message)

        print(f"\nLogged decision: {decision.value}")
        print(f"Message to send:\n{sent_message}")

    print("\nSession ended.")


if __name__ == "__main__":
    main()