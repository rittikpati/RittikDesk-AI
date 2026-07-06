# RittikDesk AI

AI-Powered CRM & Campaign Management Platform

## Tech Stack

- Python 3.14
- Django 6.0
- Django REST Framework
- PostgreSQL (Neon)
- Bootstrap 5 (Dark Theme)
- Chart.js
- DeepSeek API
- Cloudinary
- WhiteNoise

## Setup

1. Clone the repository:
   ```bash
   git clone <repo-url>
   cd rittikdesk-ai
   ```

2. Create virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   .\venv\Scripts\activate   # Windows
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment:
   ```bash
   cp .env.example .env
   # Edit .env with your secrets
   ```

5. Run migrations:
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

6. Create superuser:
   ```bash
   python manage.py createsuperuser
   ```

7. Run development server:
   ```bash
   python manage.py runserver
   ```

8. Open http://127.0.0.1:8000/

## Deployment

Deployed on Vercel with Neon PostgreSQL.
