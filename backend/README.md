# InsightPro Backend

This is the FastAPI backend server for the InsightPro application, which provides Instagram profile analysis and authenticity scoring using mathematical models (discrete probability, graph theory).

## Prerequisites

- Python 3.8 or higher
- pip (Python package installer)

## Installation

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. (Recommended) Create and activate a virtual environment:
   ```bash
   # Create virtual environment
   python -m venv venv
   
   # Activate on Linux/Mac:
   source venv/bin/activate
   
   # Activate on Windows:
   venv\Scripts\activate
   ```

3. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Install Playwright browsers (required for Instagram scraping):
   ```bash
   playwright install chromium
   ```

## Running the Backend Server

To start the FastAPI backend server, run:

```bash
uvicorn app:app --host 127.0.0.1 --port 8001 --reload
```

### Command Breakdown:
- `uvicorn` - ASGI server for running FastAPI applications
- `app:app` - Runs the `app` object from `app.py`
- `--host 127.0.0.1` - Makes the server accessible on localhost
- `--port 8001` - Runs the server on port 8001 (required for frontend connection)
- `--reload` - Auto-reloads the server when code changes (useful for development)

### Alternative (Production):
For production without auto-reload:
```bash
uvicorn app:app --host 127.0.0.1 --port 8001
```

## Accessing the API

Once the server is running, you can access:

- **API Documentation (Swagger UI)**: http://127.0.0.1:8001/docs
- **Alternative API Documentation (ReDoc)**: http://127.0.0.1:8001/redoc
- **API Base URL**: http://127.0.0.1:8001

## API Endpoints

The backend provides the following endpoints:

### Authentication
- `POST /signup` - Create a new user account
- `POST /login` - Login with email and password

### Instagram Scraping
- `POST /ig/profile-basic` - Get basic profile information via scraping
- `POST /ig/profile-audit` - Perform detailed profile audit (posts, comments)
- `POST /ig/follower-audit` - Audit follower authenticity

### Analysis
- `POST /analyze` - Analyze Instagram profile using mathematical models (manual data input)

## Database

The backend uses SQLite for storing user accounts. The database file (`insightpro.db`) is automatically created in the backend directory when you first run the server.

## Instagram Login (Optional)

For Instagram scraping features to work, you need to login to Instagram once:

1. Run the login script:
   ```bash
   python ig_login.py
   ```

2. Follow the prompts to login with your Instagram credentials

3. The session will be saved in the `pw_ig_session/` directory (ignored by git)

**Note**: Instagram scraping features may not work without a valid session.

## Troubleshooting

### Port already in use
If you get an error that port 8001 is already in use:
```bash
# On Linux/Mac, find and kill the process:
lsof -ti:8001 | xargs kill -9

# On Windows:
netstat -ano | findstr :8001
taskkill /PID <PID> /F
```

### Playwright installation issues
If Playwright browsers fail to install:
```bash
# Install system dependencies (Linux)
playwright install-deps

# Then reinstall browsers
playwright install chromium
```

### Import errors
Make sure you're in the backend directory and have activated your virtual environment before running the server.

## Development

When developing, use the `--reload` flag to automatically restart the server when you make code changes:

```bash
uvicorn app:app --host 127.0.0.1 --port 8001 --reload
```

## Frontend Connection

The Streamlit frontend (in the `../frontend` directory) connects to this backend at `http://127.0.0.1:8001`. Make sure the backend is running before starting the frontend.
