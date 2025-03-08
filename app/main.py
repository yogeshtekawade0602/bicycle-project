from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from supabase import create_client
from dotenv import load_dotenv
import os
from datetime import datetime
import logging
import uuid
import hashlib

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

def hash_password(password, salt=None):
    """Hash password with salt"""
    if not salt:
        salt = uuid.uuid4().hex
    hashed = hashlib.sha256(f"{password}{salt}".encode()).hexdigest()
    return hashed, salt

@app.route('/')
@app.route('/dashboard')
def list_dwellers():
    try:
        db = get_supabase()
        if not db:
            raise Exception("Database connection not available")

        response = db.table('city_dwellers')\
            .select("*")\
            .eq('account_status', 'active')\
            .execute()
            
        dwellers = response.data if response else []
        
        # Format dates and ensure numeric values
        for dweller in dwellers:
            try:
                for date_field in ['registration_date', 'date_of_birth']:
                    if dweller.get(date_field):
                        dweller[date_field] = datetime.strptime(
                            dweller[date_field], 
                            '%Y-%m-%d'
                        ).strftime('%m/%d/%Y')
                
                dweller['credit_balance'] = float(dweller.get('credit_balance', 0))
                dweller['rating'] = float(dweller.get('rating', 0))
                dweller['verification_status'] = dweller.get('verification_status', 'pending')
            except ValueError as e:
                logger.warning(f"Error formatting dweller data: {str(e)}")
                
        return render_template('dashboard.html', dwellers=dwellers)
                             
    except Exception as e:
        logger.error(f"Error in list_dwellers: {str(e)}")
        flash(str(e), 'error')
        return render_template('dashboard.html', dwellers=[])

@app.route('/manage_dweller', methods=['POST'])
def manage_dweller():
    try:
        db = get_supabase()
        if not db:
            raise Exception("Database connection not available")

        action = request.form.get('action')
        if not action:
            raise ValueError("No action specified")

        if action == 'add_dweller':
            # Validate required fields
            required_fields = ['first_name', 'last_name', 'email', 'password', 
                             'date_of_birth', 'registration_date']
            for field in required_fields:
                if not request.form.get(field):
                    raise ValueError(f"Missing required field: {field}")

            # Format dates
            try:
                registration_date = datetime.strptime(
                    request.form['registration_date'], 
                    '%m/%d/%Y'
                ).strftime('%Y-%m-%d')
                
                date_of_birth = datetime.strptime(
                    request.form['date_of_birth'], 
                    '%m/%d/%Y'
                ).strftime('%Y-%m-%d')
            except ValueError:
                raise ValueError("Invalid date format. Use MM/DD/YYYY")

            # Hash password
            password_hash, salt = hash_password(request.form['password'])

            new_dweller = {
                'first_name': request.form['first_name'],
                'last_name': request.form['last_name'],
                'email': request.form['email'],
                'phone_number': request.form.get('phone_number'),
                'address': request.form.get('address'),
                'date_of_birth': date_of_birth,
                'registration_date': registration_date,
                'password_hash': password_hash,
                'salt': salt,
                'preferred_language': request.form.get('preferred_language', 'en'),
                'verification_status': 'pending',
                'account_status': 'active',
                'credit_balance': 0,
                'rating': 0,
                'verification_code': str(uuid.uuid4().hex[:6].upper())
            }
            
            db.table('city_dwellers').insert(new_dweller).execute()
            flash('City dweller added successfully!', 'success')

        elif action == 'edit_dweller':
            user_id = request.form.get('user_id')
            if not user_id:
                raise ValueError("User ID is required")

            # Format dates
            try:
                registration_date = datetime.strptime(
                    request.form['registration_date'], 
                    '%m/%d/%Y'
                ).strftime('%Y-%m-%d')
                
                date_of_birth = datetime.strptime(
                    request.form['date_of_birth'], 
                    '%m/%d/%Y'
                ).strftime('%Y-%m-%d')
            except ValueError:
                raise ValueError("Invalid date format. Use MM/DD/YYYY")

            updated_dweller = {
                'first_name': request.form['first_name'],
                'last_name': request.form['last_name'],
                'email': request.form['email'],
                'phone_number': request.form.get('phone_number'),
                'address': request.form.get('address'),
                'date_of_birth': date_of_birth,
                'registration_date': registration_date,
                'verification_status': request.form.get('verification_status', 'pending'),
                'credit_balance': float(request.form.get('credit_balance', 0)),
                'rating': float(request.form.get('rating', 0))
            }

            db.table('city_dwellers')\
                .update(updated_dweller)\
                .eq('user_id', user_id)\
                .execute()
            flash('City dweller updated successfully!', 'success')

        elif action == 'delete_dweller':
            user_id = request.form.get('user_id')
            if not user_id:
                raise ValueError("User ID is required")

            # Soft delete
            db.table('city_dwellers')\
                .update({'account_status': 'inactive'})\
                .eq('user_id', user_id)\
                .execute()
            flash('City dweller removed successfully!', 'success')

    except ValueError as e:
        logger.warning(f"Validation error in manage_dweller: {str(e)}")
        flash(str(e), 'error')
    except Exception as e:
        logger.error(f"Error in manage_dweller: {str(e)}")
        flash("An unexpected error occurred", 'error')

    return redirect(url_for('list_dwellers'))

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