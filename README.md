# EdlioX: Educational Resource & Community Learning Platform

EdlioX is a production-oriented educational web platform designed to facilitate academic collaboration, resource monetization, peer-to-peer discussions, and study material distribution. Built using Python, Flask, MongoDB, and Tailwind CSS, the platform features a complete marketplace and community system.

---

## Architectural Overview

```
+-----------------------+      +---------------------------+      +--------------------------+
|  Student / Creator    | ---> | Flask Application Layer   | ---> | MongoDB Database Cluster |
|  Web Browser Interface|      | (Gunicorn / WSGI Runtime) |      | (Users, Resources, Chats)|
+-----------------------+      +---------------------------+      +--------------------------+
                                             |
                                             +---> Stripe Payment Gateway
                                             +---> AWS S3 Object Storage (Uploads)
                                             +---> Google Gemini AI Integration
```

---

## Key Modules & Features

1. Educational Resource Marketplace:
   - Resource upload and distribution with configurable pricing models.
   - Preview generation and secure download token verification.
   - Creator monetization dashboard displaying sales analytics, revenue splits, and payout history.
   - Direct integration with Stripe Connect for merchant account onboarding and automated payouts.

2. Community Discussion Forums:
   - Topic-based discussion boards with nested comment threads and author badges.
   - Upvoting, answer resolution marking, and content categorization by academic subjects.
   - Real-time client-side updates using Service Workers (`discussion-sw.js`) and asynchronous fetch APIs.

3. User Authentication & Profile Management:
   - Secure account registration, email verification, and password recovery workflows.
   - Public creator portfolios showcasing uploaded study resources, reputation ratings, and peer reviews.
   - Role-based authorization distinguishing student accounts, verified educators, and administrative moderators.

4. Cloud File Storage & Media Processing:
   - Configurable storage backend supporting local filesystem storage or AWS S3 buckets.
   - Configurable file size limits (up to 100MB) with mimetype validation for PDFs, lecture documents, and images.

---

## Technology Stack

- Backend Framework: Flask, Werkzeug, Flask-Session
- Database: MongoDB (via PyMongo and BSON ObjectIDs)
- Payment Gateway: Stripe Connect & Webhooks
- Cloud Storage: Amazon Web Services (AWS S3)
- AI Tutoring & Assistance: Google Generative AI (Gemini Flash)
- Frontend Interface: Jinja2 Server Templates, Tailwind CSS, Custom JavaScript
- Containerization & Deployment: Docker, Docker Compose, Passenger WSGI

---

## Environment Configuration

Configure application secrets in a `.env` file in the project root:

```env
# Flask Application Settings
FLASK_APP=run.py
FLASK_ENV=production
SECRET_KEY=your_production_secret_key

# MongoDB Database Connection
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/edliox

# Transactional Mail (SMTP)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your_system_email@gmail.com
MAIL_PASSWORD=your_system_email_app_password
MAIL_DEFAULT_SENDER=your_system_email@gmail.com

# File Upload Policies
UPLOAD_FOLDER=app/static/uploads
MAX_CONTENT_LENGTH=104857600

# Google Gemini AI Integration
GEMINI_API_KEY=your_gemini_api_key

# Stripe Payment Infrastructure
STRIPE_PUBLIC_KEY=pk_live_your_stripe_public_key
STRIPE_SECRET_KEY=sk_live_your_stripe_secret_key
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_signing_secret

# Amazon Web Services (AWS S3)
AWS_ACCESS_KEY_ID=your_aws_access_key_id
AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key
AWS_BUCKET_NAME=your_s3_bucket_name
AWS_REGION=us-east-1
```

---

## Installation & Deployment

### Local Development Setup

1. Clone repository:
   ```bash
   git clone https://github.com/mianjunaid1223/EdlioX.git
   cd EdlioX
   ```

2. Create virtual environment and install packages:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Launch development server:
   ```bash
   python run.py
   ```
   Navigate to `http://localhost:5000`.

### Production Deployment via Docker Compose

```bash
docker-compose up --build -d
```

---

## Project Structure

```
EdlioX/
|-- app/
|   |-- __init__.py            # Flask application factory
|   |-- database.py            # MongoDB connection handlers
|   |-- forms.py               # Form validation definitions
|   |-- models/                # Schema definitions (user, resource, discussion)
|   |-- routes/                # Blueprint controllers (admin, auth, discussion, monetization, resources)
|   |-- api/                   # JSON REST endpoints for comments and discussion threads
|   |-- templates/             # Jinja2 HTML views organized by feature domain
|   |-- static/                # Stylesheets, JavaScript modules, and icon assets
|-- config.py                  # Environment-specific configuration classes
|-- run.py                     # Development execution entry point
|-- wsgi.py                    # Production WSGI application wrapper
|-- Dockerfile                 # Container image specification
|-- docker-compose.yml         # Multi-service composition
|-- requirements.txt           # Python dependency manifest
```
