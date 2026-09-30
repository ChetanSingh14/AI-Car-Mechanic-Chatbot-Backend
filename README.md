# 🚗 AI Car Mechanic Chatbot - Backend

A powerful Django REST Framework backend service for an AI-powered Automotive Diagnostic Assistant and Mechanic Booking system. This service integrates with **Google Gemini API** for intelligent troubleshooting, multimodal media analysis (images/audio/video), severity classification, diagnostic reports, and appointment booking management.

---

## 🛠 Tech Stack

* **Framework:** Python 3.9+ / Django 5.x / Django REST Framework
* **AI Engine:** Google Generative AI SDK (`google-generativeai` / Gemini 1.5 & Flash models)
* **API Documentation:** `drf-spectacular` (OpenAPI 3.0 & Swagger UI)
* **Database:** SQLite (default development database, PostgreSQL compatible)
* **Testing:** Django Test Suite & `pytest-django`

---

## 🚀 Features

* **AI Diagnostic Chat (`/api/chat/`):** Interactive troubleshooting conversation tailored to vehicle make, model, year, and symptoms.
* **Multimodal Media Analysis (`/api/upload/`):** Upload vehicle images (dash lights, engine bay, damaged components), audio (engine knock, squeaking brakes), or video for AI analysis.
* **Diagnostic Report Generation (`/api/diagnosis/`):** Automatic categorization of vehicle issues with severity levels (*Low*, *Medium*, *High*, *Critical*), recommended services, and estimated repair costs.
* **Mechanic Booking Management (`/api/booking/`):** Seamless appointment scheduling with preferred mechanics/shops.
* **Swagger API Explorer (`/api/docs/`):** Interactive API documentation for easy frontend integration.

---

## 📋 Requirements & Prerequisites

* **Python 3.9+** installed on your system.
* **Google Gemini API Key** (Get one from [Google AI Studio](https://aistudio.google.com/)).

---

## ⚙️ Installation & Local Setup

### 1. Clone the Repository
```bash
git clone https://github.com/ChetanSingh14/AI-Car-Mechanic-Chatbot-Backend.git
cd AI-Car-Mechanic-Chatbot-Backend
```

### 2. Create and Activate Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
```

> **Note for macOS / Linux users:** If `python` is not aliased in your shell, always use `python3` and `pip3` commands.

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Environment Configuration
Copy `.env.example` to create your `.env` file:
```bash
cp .env.example .env
```
Open `.env` and add your Gemini API key:
```env
DEBUG=True
SECRET_KEY=your_django_secret_key_here
ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
GEMINI_API_KEY=your_gemini_api_key_here
```

### 5. Apply Database Migrations
```bash
python3 manage.py migrate
```

### 6. Start Development Server
```bash
python3 manage.py runserver
```
The server will start running at `http://127.0.0.1:8000/`.

---

## 🧪 Running Tests

To run the complete API test suite:
```bash
python3 manage.py test api.tests.test_api
```

Or using `pytest`:
```bash
pytest
```

---

## 📡 API Endpoints Overview

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/chat/` | Send user message & receive AI diagnostic response |
| `POST` | `/api/upload/` | Upload image/audio/video attachment for AI analysis |
| `POST` | `/api/diagnosis/` | Generate diagnostic summary & severity report |
| `POST` | `/api/booking/` | Create mechanic appointment booking |
| `GET` | `/api/booking/<uuid>/` | Fetch booking confirmation details |
| `GET` | `/api/conversation/<uuid>/` | Retrieve full chat & diagnostic history |
| `GET` | `/api/docs/` | Interactive Swagger UI documentation |
| `GET` | `/api/redoc/` | ReDoc API documentation |

---

## 📁 Project Structure

```
.
├── api/
│   ├── models.py         # Database models (Conversation, Message, MediaAttachment, Diagnosis, Booking)
│   ├── views.py          # REST API Views (Chat, Upload, Diagnosis, Booking)
│   ├── serializers.py    # Serializers for request/response payloads
│   ├── services/         # Gemini AI Service integrations
│   ├── tests/            # API Test suite
│   └── urls.py           # API endpoint routing
├── core/
│   ├── settings.py       # Django project configuration
│   ├── urls.py           # Root URL routing & Swagger docs configuration
│   └── wsgi.py
├── manage.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## 📄 License
This project is licensed under the MIT License.
