# 📚 StudyForge AI

StudyForge AI is a study assistant that turns PDF course materials into structured revision sessions and tracks learning progress.

Users can upload lecture notes, revision packs, past papers, or other study materials. StudyForge extracts the document text, detects important academic topics, creates revision sessions, and tracks confidence across topics.

## ✨ Features

- 📄 Upload and process PDF study materials
- 🔎 Extract text automatically from documents
- 🧠 Detect important academic topics
- 🤖 OpenAI-powered topic analysis
- 📴 Offline topic detection when the AI service is unavailable
- ✏️ Review and edit detected topics
- 📝 Generate structured revision questions
- 📊 Track confidence for individual topics
- 💾 Store revision history using SQLite
- 📈 Identify strongest and weakest topics
- 🎯 Recommend areas that need more revision

## 🖥️ Preview

StudyForge includes four main areas:

### Document
Preview the text extracted from an uploaded PDF.

### Topics
Analyze study material and identify the concepts that matter most.

### Revision
Choose a topic, answer revision questions, and assess your confidence.

### Progress
View revision history, confidence scores, and recommended areas to improve.

## 🛠️ Tech Stack

- Python
- Streamlit
- OpenAI API
- PyPDF
- SQLite
- Pandas
- YAKE
- python-dotenv
- Git & GitHub

## 🧠 How It Works

```text
PDF Upload
    ↓
Text Extraction
    ↓
Topic Analysis
    ↓
┌───────────────────────┐
│ OpenAI API available? │
└───────────┬───────────┘
            │
      Yes   │   No
       ↓    │    ↓
 AI Analysis    Offline Analysis
       ↓          ↓
       └────┬─────┘
            ↓
      Detected Topics
            ↓
      Revision Session
            ↓
     Confidence Score
            ↓
       SQLite Storage
            ↓
     Progress Dashboard
```

## 🚀 Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/adalyatixten/studyforge-ai.git
```

### 2. Open the project

```bash
cd studyforge-ai
```

### 3. Create a virtual environment

```bash
py -m venv .venv
```

### 4. Activate it

PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

### 5. Install dependencies

```bash
pip install -r requirements.txt
```

### 6. Run StudyForge

```bash
streamlit run app.py
```

Then open:

```text
http://localhost:8501
```

## 🔑 OpenAI API

StudyForge can use the OpenAI API for intelligent topic detection.

Create a `.env` file:

```text
OPENAI_API_KEY=your_api_key_here
```

The `.env` file is ignored by Git and should never be committed.

If the OpenAI API is unavailable, StudyForge automatically switches to its offline topic detection system.

## 📂 Project Structure

```text
studyforge-ai/
│
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
│
├── .env              # Local only
├── .venv/            # Local only
└── studyforge.db     # Local progress database
```

## 📴 Offline Mode

StudyForge is designed to remain usable even without access to the OpenAI API.

The offline analysis system combines:

- predefined academic concept recognition
- keyword matching
- YAKE keyword extraction

This allows the application to continue detecting study topics when external AI services are unavailable.

## 🗺️ Roadmap

Planned improvements:

- AI-generated exam-style questions
- User-written answers inside StudyForge
- Automatic AI answer grading
- Personalized feedback
- Weak-topic detection based on quiz performance
- Adaptive revision plans
- Multiple document support
- User accounts
- Cloud database
- Semantic search / RAG
- Public deployment

## 🎯 Project Goal

StudyForge AI is being developed as an exploration of how AI can be used to build adaptive educational tools.

The long-term goal is to create a system that does more than summarize documents: it should understand what a student is learning, identify weak areas, and adapt future revision sessions accordingly.

## 👤 Author

**Adalyat Orduhani**

GitHub: [@adalyatixten](https://github.com/adalyatixten)