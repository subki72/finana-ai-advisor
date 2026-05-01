# Finana — AI Financial Advisor

An intelligent, casual AI financial advisor built with Streamlit and powered by the blazing-fast Llama 3.3 model via Groq. Finana helps users manage their finances smarter by analyzing financial stories, calculating the 50/30/20 budget rule, and providing practical, easy-to-understand financial tips without the complicated jargon.

---

## Features

- **Conversational AI**: Uses natural language to understand your income, expenses, and installments.
- **Budgeting Made Easy**: Automatically calculates and recommends the 50/30/20 budget rule (Needs, Wants, Savings).
- **Practical Insights**: Provides actionable advice on expense management, investments, and mortgages (KPR).
- **Lightning Fast**: Powered by Groq's Llama-3.3-70b-versatile model for instant responses.
- **Responsive UI**: A premium, dark-themed Streamlit interface that looks great on mobile, tablet, and desktop.
- **Quick Prompts**: Ready-to-use question templates to get you started immediately.

---

## Tech Stack

- **Frontend**: [Streamlit](https://streamlit.io/)
- **LLM Provider**: [Groq API](https://groq.com/) (Llama 3.3 70B)
- **Language**: Python 3.10+
- **Environment Management**: `python-dotenv`

---

## How to Run Locally

1. **Clone the repository**  
    ```bash
    git clone https://github.com/username/finana-ai-advisor.git
    cd finana-ai-advisor
    ```

2. **Create a virtual environment (recommended)**  
    ```bash
    python -m venv venv
    # Windows
    .\venv\Scripts\activate
    # Linux/macOS
    source venv/bin/activate
    ```

3. **Install dependencies**  
    ```bash
    pip install -r requirements.txt
    ```

4. **Set up Environment Variables**  
    Create a `.env` file in the root directory and add your Groq API Key:
    ```env
    GROQ_API_KEY=your_groq_api_key_here
    ```
    *(You can get a free API key from [console.groq.com](https://console.groq.com/keys))*

5. **Run the application**  
    ```bash
    streamlit run src/main.py
    ```

---

## How to Host (Deploy) for Free

The easiest way to host this project for free so anyone can access it is by using **Streamlit Community Cloud**.

### Steps to Deploy:

1. **Push your code to GitHub:**
   Make sure your project (including `src/main.py` and `requirements.txt`) is pushed to a public or private repository on GitHub.
   *Note: Do NOT push your `.env` file. Ensure `.env` is inside your `.gitignore`.*

2. **Sign up for Streamlit Cloud:**
   Go to [share.streamlit.io](https://share.streamlit.io/) and log in using your GitHub account.

3. **Deploy the App:**
   - Click **"New app"**.
   - Select the GitHub repository where you uploaded this project.
   - Set the **Branch** to `main` (or whichever branch you use).
   - Set the **Main file path** to `src/main.py`.

4. **Add your API Key (Crucial Step):**
   - Before clicking deploy, click on **"Advanced settings..."** at the bottom.
   - Under the "Secrets" section, add your environment variable just like in your `.env` file:
     ```toml
     GROQ_API_KEY="your_groq_api_key_here"
     ```
   - Click **Save**.

5. **Launch:**
   Click **"Deploy!"**. Wait a few minutes, and your AI Financial Advisor will be live and accessible via a public link!
