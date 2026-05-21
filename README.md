I built a Text-to-SQL tool in Python.
Then I found out Uber built the exact same architecture — at 1.2M queries/month.

Here's what my pipeline looks like:

🤖 Agent 1 — Table Selector
Doesn't dump the full schema into the prompt.
First asks the LLM: "which tables do you actually need?"
Passes only those to the next step.

📚 Agent 2 — RAG Retrieval
15 hand-written Q→SQL pairs stored in ChromaDB.
On every query, cosine similarity finds the 3 most relevant examples.
Those go into the prompt as style context.

⚡ Agent 3 — SQL Generator
Now works with: pruned schema + 3 similar examples.
Not a blank prompt. A guided one.

Uber calls this QueryGPT.
It saved them 140,000 engineering hours a year.

Same idea. Different scale.

Stack: Python · Gemini · ChromaDB · SQLite · Streamlit

What's one system you built before realising a FAANG was already running it in prod?

(GitHub link in comments)

#AI #LLMs #RAG #AIAgents #Python #GenerativeAI #TextToSQL
