import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise ValueError("GROQ_API_KEY not found. Please set it in your .env file.")

client = Groq(api_key=api_key)
sys_instruct = "You are a casual Financial Advisor. Your tasks: 1. Analyze the user's financial story. 2. If there are numbers, calculate a 50/30/20 budget. 3. Give practical advice. Tone: Casual, friendly, to the point. Important: Do not use emojis in your responses. Keep the text clean and readable."

def chatbot(user_message, history):
    try:
        print(f"User: {user_message}")

        messages = [{"role": "system", "content": sys_instruct}]
        if history:
            for msg in history:
                messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_message})

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages
        )

        reply = response.choices[0].message.content
        print(f"Bot: {reply[:50]}...")

        return reply

    except Exception as e:
        error_msg = f"Error: {str(e)}"
        print(error_msg)
        return error_msg