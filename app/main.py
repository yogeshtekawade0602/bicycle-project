from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from supabase import create_client
from dotenv import load_dotenv
import os
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "fallback-secret-key")

def get_supabase():
    """Get Supabase client"""
    try:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        
        if not url or not key:
            logger.error("Missing Supabase credentials")
            return None
            
        return create_client(url, key)
    except Exception as e:
        logger.error(f"Failed to initialize Supabase: {str(e)}")
        return None

# Health check endpoint
@app.route('/health')
def health_check():
    try:
        db = get_supabase()
        if db:
            # Simple database check
            db.table('city_dwellers').select("count", "exact").limit(1).execute()
            status = {
                "status": "healthy",
                "database": "connected",
                "timestamp": datetime.now().isoformat()
            }
            return jsonify(status), 200
        else:
            status = {
                "status": "degraded",
                "database": "disconnected",
                "timestamp": datetime.now().isoformat()
            }
            return jsonify(status), 503
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@app.route('/')
def index():
    return jsonify({"message": "API is running"}), 200

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return jsonify({
        "error": "Not Found",
        "message": "The requested resource was not found"
    }), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {str(error)}")
    return jsonify({
        "error": "Internal Server Error",
        "message": "An unexpected error occurred"
    }), 500

# For local development only
if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    app.run(host='0.0.0.0', port=port)