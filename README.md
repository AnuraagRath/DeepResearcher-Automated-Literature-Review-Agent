
# 🧠 **DeepResearcher: Automated Literature Review Agent**

**DeepResearcher** is a lightweight, API-free research companion that scours the open web and scientific archives to generate concise literature-style summaries on any topic — from *Agentic Economics* to *Neural Symbolic AI*.  

It’s designed for **independent researchers, students, and AI developers** who want quick, multi-source research briefs — no API keys required.

---

## 🚀 Features

✅ **Multi-Source Search (No API Required)**  
Searches across open scientific databases (OpenAlex, arXiv, PubMed) and the public web.  

✅ **Intelligent Result Consolidation**  
Merges duplicate titles and combines metadata (authors, abstracts, URLs, etc.) into a unified record.  

✅ **Markdown-Ready Report Generation**  
Creates a structured, easy-to-read literature review-style report — great for use in Notion, Obsidian, or research wikis.  

✅ **Local & Offline Friendly**  
No need for API keys, tokens, or cloud LLMs. Works with your local Python environment.

---

## 🧩 Tech Stack

| Component | Description |
|------------|-------------|
| **Python 3.9+** | Core runtime |
| **Requests** | Lightweight HTTP client |
| **BeautifulSoup4** | HTML parsing for metadata extraction |
| **Rich / Colorama** *(optional)* | Pretty terminal logging |
| **(Optional)** | Plug-in hooks for Ollama, Claude, or Bedrock for advanced summarization |

---

## 📂 Folder Structure

```

Test_TopicResearcher/
│
├── deep_research_agent.py    # Main script
├── README.md                   # This file
├── results/                    # Output reports saved here
│   ├── Agentic_Economics.md
│   └── Cognitive_AI_Systems.md
└── venv/                       # Local Python environment

````

---

## ⚙️ Setup

### 1️⃣ Clone the repo
```bash
git clone https://github.com/yourusername/DeepResearcher.git
cd DeepResearcher
````

### 2️⃣ Create a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3️⃣ Install dependencies

```bash
pip install -r requirements.txt
```

### 4️⃣ Run your first query

```bash
python3 '# deep_research_agent.py' "Agentic Economics"
```

---

## 📜 Output Example

```
🧩 Query: Agentic Economics

🔍 Sources analyzed:
 - Web Search
 - arXiv
 - CrossRef
 - OpenAlex
 - PubMed

📘 Consolidated Summary:
[Consolidated-1] "The Role of Agency in Economic Systems" — sources: arXiv, OpenAlex  
[Consolidated-2] "Cognitive Agency and Financial Decision-Making" — sources: Web, PubMed
```

Each output is saved in Markdown format under `/results/`.

---

## 🧠 Future Enhancements

* [ ] Add offline embeddings for smarter summarization
* [ ] Integrate local LLaMA or Claude via Ollama
* [ ] Export citations in BibTeX / APA style
* [ ] Visualize knowledge graphs of research topics

---

## 🪶 Inspiration

DeepResearcher is inspired by the idea that **research should be conversational** — not a battle with APIs or paywalls.
It merges automation with the curiosity-driven exploration of human scholars.

> “An AI that reads papers so you don’t have to — but still lets you think.”

---

## 🧑‍💻 Author

**Anuraag Rath**
AI Researcher • Developer • Agentic Systems Dev
Amazon India

