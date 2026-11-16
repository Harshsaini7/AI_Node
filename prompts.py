"""
Prompts
=======
System prompts and conversation templates for the AI Loan Customer Agent.

The system prompt defines the AI's:
- Identity (bank customer success partner)
- Objective (determine loan interest)
- Conversation style (polite, professional, short)
- Safety rules (no guarantees, no pressure, no sensitive data)

Phase 3.2 - Loan Agent Prompt Engineering
"""


SYSTEM_PROMPT = """You are a polite and professional Customer Success Partner calling on behalf of a bank to discuss a loan program.

YOUR OBJECTIVE:
Determine whether the customer is interested in learning more about the bank's loan program. You are NOT making loan decisions — you are only qualifying interest.

CONVERSATION RULES:
1. Start by greeting the customer by name and introducing yourself.
2. Briefly mention that you are calling about a loan program offered by the bank.
3. Ask if the customer would be interested in learning more.
4. Keep your responses SHORT — 1 to 3 sentences maximum.
5. Listen carefully to the customer's response.
6. If the customer seems unsure, ask ONE clarification question.
7. Respect the customer's decision — never pressure them.
8. When the conversation reaches a clear conclusion, politely end the call.

IF THE CUSTOMER IS INTERESTED:
Say something like: "Thank you! A person from our loan team will connect with you shortly to discuss the details."

IF THE CUSTOMER IS NOT INTERESTED:
Say something like: "No problem at all. Thank you for your time. Have a great day!"

SAFETY RULES — YOU MUST NEVER:
- Guarantee loan approval
- Invent or state specific loan interest rates
- Invent eligibility criteria
- Make any credit or lending decisions
- Request OTPs, passwords, PINs, or banking credentials
- Request Aadhaar, PAN, or account numbers
- Pressure or manipulate the customer
- Provide false or misleading information

If the customer asks about specific rates, eligibility, or loan details, say:
"Our loan team will be able to share all the specific details with you. I'm reaching out to see if you'd be interested in learning more."

TONE:
- Warm and professional
- Conversational, not robotic
- Respectful of the customer's time
"""


# Appended to SYSTEM_PROMPT so ONE Gemini call returns both the spoken reply
# and the classification (saves API quota).
TURN_OUTPUT_FORMAT = """

OUTPUT FORMAT (MANDATORY):
Respond with ONLY a valid JSON object, no extra text, in exactly this format:
{"reply": "<what you say to the customer, 1-3 sentences>", "status": "<INTERESTED | NOT_INTERESTED | UNCLEAR>"}

STATUS RULES:
- "INTERESTED": the customer clearly wants to learn more. Your reply should be the closing line for interested customers.
- "NOT_INTERESTED": the customer clearly declined. Your reply should politely end the call.
- "UNCLEAR": the customer's intent is not yet clear. Your reply should be ONE short clarification question.
"""

TURN_SYSTEM_PROMPT = SYSTEM_PROMPT + TURN_OUTPUT_FORMAT


def get_fixed_greeting(customer_name):
    """
    Opening line for a customer. Fixed text, so it costs 0 LLM calls.

    Args:
        customer_name (str): The customer's name

    Returns:
        str: The greeting the agent says first
    """
    return (
        f"Hello {customer_name}, this is a Customer Success Partner calling on behalf of "
        "your bank. We have a loan program and I'd like to know if you would be "
        "interested in learning more about it."
    )


def get_turn_prompt(conversation_history):
    """
    Build the prompt for one conversation turn (reply + classification in one call).

    Args:
        conversation_history (list): Lines like "AI: ..." and "Customer: ..."

    Returns:
        str: The prompt to send to the LLM
    """
    context = "\n".join(conversation_history)
    return f"""Conversation so far:

{context}

Reply to the customer's latest message and classify their interest, using the required JSON format."""


def get_greeting_prompt(customer_name):
    """
    Generate the first message prompt for a customer.

    Args:
        customer_name (str): The customer's name

    Returns:
        str: The prompt to send to the AI for the opening message
    """
    return f"Start the conversation by greeting the customer named {customer_name}. Introduce yourself and briefly mention you are calling about a loan program. Keep it short and natural."


def get_classification_prompt():
    """
    Generate a prompt to ask the AI for its final classification.

    Returns:
        str: The prompt asking for a structured decision
    """
    return """Based on the conversation so far, classify the customer's interest level.

Respond with ONLY a valid JSON object in this exact format (no extra text):

If interested:
{"status": "INTERESTED"}

If not interested:
{"status": "NOT_INTERESTED"}

If still unclear:
{"status": "UNCLEAR"}
"""


# ---- Run this file directly to test ----
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    from llm_provider import GeminiProvider

    print("=" * 50)
    print("  PROMPT ENGINEERING - Test")
    print("=" * 50)
    print()

    provider = GeminiProvider()

    # Test 1: Greeting for a customer
    print("TEST 1: AI greets 'Rahul Sharma'")
    print("-" * 40)
    greeting = provider.chat(
        message=get_greeting_prompt("Rahul Sharma"),
        system_instruction=SYSTEM_PROMPT,
    )
    print(f"AI: {greeting}")
    print()

    # Test 2: Customer says yes — AI responds
    print("TEST 2: Customer says 'Yes, tell me more'")
    print("-" * 40)
    response = provider.chat(
        message="The customer replied: 'Yes, tell me more about it.' Respond naturally.",
        system_instruction=SYSTEM_PROMPT,
    )
    print(f"AI: {response}")
    print()

    # Test 3: Customer says no — AI responds
    print("TEST 3: Customer says 'Not interested'")
    print("-" * 40)
    response = provider.chat(
        message="The customer replied: 'No thanks, I'm not interested.' Respond naturally and politely end the call.",
        system_instruction=SYSTEM_PROMPT,
    )
    print(f"AI: {response}")
    print()

    # Test 4: Customer asks about rates — AI follows safety rules
    print("TEST 4: Customer asks about interest rates (safety test)")
    print("-" * 40)
    response = provider.chat(
        message="The customer replied: 'What interest rate are you offering?' Respond according to your rules.",
        system_instruction=SYSTEM_PROMPT,
    )
    print(f"AI: {response}")
    print()

    print("[OK] Phase 3.2 complete!")
