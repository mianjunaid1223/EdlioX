# EdlioX Educational Marketplace & Discussion Platform

[![Year Built](https://img.shields.io/badge/Year%20Built-2025-blue.svg)](#)


Production-grade educational content management, academic resource marketplace, and community discussion ecosystem built with Flask, MongoDB, Stripe Connect, AWS S3, and Google Gemini AI.

```
+---------------------------------------------------------------------------------------+
|                                  Client Viewports                                     |
|   +--------------------------+  +---------------------------+  +------------------+   |
|   | Resource Marketplace     |  | Collaborative Forum       |  | Creator Earnings |   |
|   | (Browsing, S3 Downloads) |  | (Thread UI, ServiceWorker)|  | (Stripe Connect) |   |
|   +-------------+------------+  +-------------+-------------+  +--------+---------+   |
+-----------------|-----------------------------|-------------------------|-------------+
                  |                             |                         |
                  v                             v                         v
+---------------------------------------------------------------------------------------+
|                               Flask Application Kernel                                |
|                                                                                       |
|   +--------------------+  +---------------------+  +------------------------------+   |
|   | Auth Blueprint     |  | Resources Blueprint |  | Discussions Blueprint        |   |
|   | /login, /register, |  | /upload, /view,     |  | /discussions, /ask,          |   |
|   | /profile, sessions |  | /analytics, S3 SDK  |  | /api/comments, nested trees  |   |
|   +--------------------+  +---------------------+  +------------------------------+   |
|   +--------------------+  +---------------------+  +------------------------------+   |
|   | Monetization Engine|  | Admin Blueprint     |  | AI Cognitive Layer           |   |
|   | Stripe Express,    |  | User moderation,    |  | Gemini 1.5 Flash             |   |
|   | payout thresholds  |  | payout verification |  | summarization & Q&A assist   |   |
|   +--------------------+  +---------------------+  +------------------------------+   |
+---------------------------------------------------------------------------------------+
|                                                                                       |
|   Storage & Database Tier:                                                            |
|   - MongoDB Collections: users, resources, discussions, comments, monetization        |
|   - Object Storage: AWS S3 Bucket with pre-signed GET/PUT upload streams              |
|   - Session Engine: Secure filesystem sessions with 7-day TTL                        |
+---------------------------------------------------------------------------------------+
```

## System Architecture

EdlioX operates as a distributed educational marketplace and community discussion hub. The application kernel is structured into modular Flask blueprints decoupled through centralized MongoDB collection handles and service layers.

### Architectural Subsystems

1. User Authentication and Profile Management: Implements Flask-Login sessions backed by bcrypt password hashes. Tracks authorization roles, avatar assets, and creator payment profiles.

2. Academic Resource Marketplace: Manages educational assets (lecture slides, revision notes, laboratory guides, assessments) with metadata tagging across academic disciplines and grade levels. Includes dual-mode storage supporting AWS S3 buckets or local filesystem persistence with stream limits up to 16MB.

3. Creator Monetization Pipeline: A financial engine that tracks qualified page impressions and downloads per resource. Creators who exceed the 1,000 view threshold become eligible to connect a Stripe Express account and initiate automated direct deposit payouts subject to an administrator review queue.

4. Real-time Discussion and Knowledge Forum: Multi-tier question and response forum supporting nested conversation trees, search indexing, markdown formatting, AJAX comment synchronization, and service worker background caching (discussion-sw.js) for resilient offline reading.

5. AI Academic Assistant: Incorporates Google Gemini APIs to generate automated resource digests, keyword extraction, and contextual educational explanations for student inquiries.

## Directory and File Organization

```
EdlioX/
|-- app/
|   |-- __init__.py                # Application factory, MongoDB setup, blueprint registration
|   |-- config.py                  # Environment settings, Stripe keys, AWS credentials, thresholds
|   |-- database.py                # MongoDB collection references, index definitions, connection pool
|   |-- forms.py                   # WTForms validation for auth, resource uploads, discussions
|   |-- api/
|   |   |-- comments.py            # REST API endpoints for comment voting, replies, and moderation
|   |   |-- discussions.py         # REST API endpoints for thread querying and status updates
|   |-- auth/
|   |   |-- utils.py               # Token generators, password hashers, session inspectors
|   |-- models/
|   |   |-- user.py                # User entity, authentication methods, profile updates
|   |   |-- resource.py            # Resource schema, view counter, download tracking, monetization
|   |   |-- discussion.py          # Discussion thread, vote counts, comment tree resolution
|   |-- routes/
|   |   |-- admin.py               # Platform administration, user moderation, payout approvals
|   |   |-- auth.py                # Login, registration, password recovery, profile editing
|   |   |-- discussion_routes.py   # Discussion forum views, thread creation, reply dispatching
|   |   |-- monetization.py        # Creator dashboard, payout requests, Stripe Connect onboarding
|   |   |-- resources.py           # Resource catalog, file uploads, S3 integration, analytics
|   |-- static/
|   |   |-- css/                   # Responsive styling, discussions layout, typography
|   |   |-- js/
|   |   |   |-- comments.js        # Dynamic comment tree rendering and AJAX post handlers
|   |   |   |-- discussion.js      # Discussion interaction and vote dispatchers
|   |   |   |-- discussion-sw.js   # Service Worker for offline thread caching
|   |   |   |-- discussion-ui.js   # UI state transitions, modals, and toasts
|   |-- templates/                 # Jinja2 templates organized by blueprint
|-- docker-compose.yml             # Web and MongoDB container orchestration
|-- Dockerfile                     # Multi-stage container build definition
|-- requirements.txt               # Pinned Python package dependencies
`-- run.py                        # WSGI entrypoint script
```

## Database Schema Specification

The application uses MongoDB collections configured with specific compound and unique indexes:

### Collections Schema

| Collection | Key Fields | Indexes | Description |
|---|---|---|---|
| users | _id, email, username, password_hash, monetization_status, total_earnings, pending_earnings, stripe_account_id | email: 1 (unique), username: 1 (unique), monetization_status: 1 | User credentials, roles, and financial state |
| resources | _id, user_id, title, description, file_type, file_path, views, downloads, monetization_status, earnings | user_id: 1, created_at: -1, monetization_status: 1 | Study materials uploaded by platform users |
| discussions | _id, user_id, title, content, tags, views, votes, comment_count, created_at | user_id: 1, created_at: -1, tags: 1 | Academic forum threads and questions |
| comments | _id, discussion_id, user_id, parent_id, content, votes, created_at | discussion_id: 1, created_at: 1, parent_id: 1 | Threaded responses and nested comment trees |
| monetization_requests | _id, user_id, status, bank_details, eligibility_metrics, applied_at, processed_at | user_id: 1, status: 1, applied_at: -1 | Creator monetization approval submissions |
| payouts | _id, user_id, amount, status, stripe_payout_id, requested_at, processed_at | user_id: 1, status: 1, requested_at: -1 | Historical ledger of creator fund distributions |

## Creator Monetization and Stripe Connect Engine

The financial distribution pipeline calculates creator remuneration through automated view telemetry:

```python
# Threshold parameters defined in config.py
MONETIZATION_VIEW_THRESHOLD = 1000
MONETIZATION_RATE_PER_1000_VIEWS = 0.20  # USD
MINIMUM_PAYOUT_THRESHOLD = 50.0          # USD
```

1. Eligibility Verification: To apply for monetization, a creator must demonstrate at least 1,000 cumulative verified views across their catalog, accompanied by active submissions within the preceding 30-day window.

2. Onboarding Workflow: When approved, the system generates a Stripe Express account via stripe.Account.create(type='express') and binds the resulting account ID to the user document.

3. Fund Settlement: When pending earnings exceed $50.00, the creator triggers /monetization/request-payout. The platform issues a Stripe Transfer into the creator account and logs the transaction record into the payouts collection.

## API Endpoint Reference

### Resource Marketplace API

| Route | Method | Authorization | Description |
|---|---|---|---|
| /resources | GET | Public | Paginated list of study materials with subject and grade filters |
| /resources/upload | POST | Logged In | Multipart form upload handling document validation and S3 upload |
| /resources/<id> | GET | Public | Resource viewport with view counter increment and download link |
| /resources/<id>/download | GET | Logged In | Increments download counter and serves asset from S3 / local path |
| /resources/analytics | GET | Logged In | Creator statistics for view velocities and download conversion rates |

### Discussion Forum API

| Route | Method | Authorization | Description |
|---|---|---|---|
| /discussions | GET | Public | Forum directory filtered by category and popularity |
| /discussions/ask | POST | Logged In | Thread creation endpoint accepting title, category, and markdown content |
| /api/comments/create | POST | Logged In | Dispatches new comment or nested reply into discussion hierarchy |
| /api/comments/<id>/vote | POST | Logged In | Records upvote/downvote on comment and updates aggregate score |

### Monetization API

| Route | Method | Authorization | Description |
|---|---|---|---|
| /monetization/dashboard | GET | Logged In | Summarizes view thresholds, earnings balance, and payout ledger |
| /monetization/apply | POST | Logged In | Submits creator banking details and verification documentation |
| /monetization/request-payout | POST | Logged In | Initiates Stripe Express payout when pending balance is >= $50.00 |

## Environment Configuration

Copy the example environment template and configure runtime credentials:

```bash
cp .env.example .env
```

| Key | Description | Default / Example |
|---|---|---|
| FLASK_APP | WSGI application pointer | run.py |
| FLASK_ENV | Execution mode | production |
| SECRET_KEY | Cryptographic session signing key | generate via secrets.token_hex(32) |
| MONGODB_URI | MongoDB connection string | mongodb://localhost:27017/edliox |
| STRIPE_PUBLIC_KEY | Stripe publishable API token | pk_test_... |
| STRIPE_SECRET_KEY | Stripe private secret token | sk_test_... |
| STRIPE_WEBHOOK_SECRET | Webhook verification signing secret | whsec_... |
| AWS_ACCESS_KEY_ID | Amazon Web Services access credential | AKIA... |
| AWS_SECRET_ACCESS_KEY | Amazon Web Services private key | your-secret-key |
| AWS_BUCKET_NAME | Target S3 bucket for educational assets | edliox-resources |
| AWS_REGION | AWS cloud region identifier | us-east-1 |
| GEMINI_API_KEY | Google AI Studio Gemini API token | AIzaSy... |
| MAIL_SERVER | SMTP outbound server hostname | smtp.gmail.com |
| MAIL_PORT | Outbound SMTP communication port | 587 |
| MAIL_USERNAME | Service notification email address | notifications@edliox.com |
| MAIL_PASSWORD | SMTP authentication password | app-password |

## Local Execution Instructions

### Bare Metal Setup

```bash
# Create and activate Python virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate

# Install package dependencies
pip install -r requirements.txt

# Start MongoDB daemon (if running locally)
mongod --dbpath /data/db

# Launch the Flask application
python run.py
```

### Docker Compose Deployment

```bash
# Build and launch web application and MongoDB database
docker-compose up --build -d

# Verify service logs
docker-compose logs -f web
```
