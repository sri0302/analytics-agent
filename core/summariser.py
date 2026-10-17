from openai import OpenAI
import config
from core.datapool import get_all_messages, save_summary, count_messages

client = OpenAI(api_key=config.OPENAI_API_KEY)

SUMMARISE_EVERY = 10  # summarise after every 10 messages

def should_summarise(session_id: str) -> bool:
    """Check whether the session message count has reached a summarisation interval."""
    count = count_messages(session_id)
    return count > 0 and count % SUMMARISE_EVERY == 0

def summarise_session(session_id: str):
    """Summarise the session conversation using OpenAI and save it to memory."""
    messages = get_all_messages(session_id)
    if not messages:
        return

    # build conversation text
    conversation = "\n".join([
        f"{m['role'].upper()}: {m['content']}"
        for m in messages
    ])

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "Summarise this conversation about database schema analysis in 3-5 concise bullet points. Focus on key insights, patterns, and decisions made."
            },
            {
                "role": "user",
                "content": conversation
            }
        ],
        max_tokens=300
    )

    summary = response.choices[0].message.content
    save_summary(session_id, summary, 0, len(messages))
    print(f"\n[Agent memory updated — session summarised]\n")