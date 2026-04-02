from waitress import serve
from app import app
import os

if __name__ == "__main__":
    # Get port from environment or default to 8080
    port = int(os.environ.get('PORT', 8080))
    print(f"Starting production server...")
    print(f"👉 Open in browser: http://localhost:{port}")
    serve(app, host='0.0.0.0', port=port)
