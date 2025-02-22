from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from supabase import create_client
from dotenv import load_dotenv
import os
from datetime import datetime
import logging
import uuid

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

def format_date_for_form(date_str):
    """Convert date string to form-compatible format"""
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').strftime('%Y-%m-%d')
    except:
        return ''

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
        
        for dweller in dwellers:
            try:
                # Format dates for display
                for date_field in ['registration_date', 'date_of_birth']:
                    if dweller.get(date_field):
                        # Store both display and form formats
                        dweller[f'{date_field}_display'] = datetime.strptime(
                            dweller[date_field], 
                            '%Y-%m-%d'
                        ).strftime('%m/%d/%Y')
                        dweller[date_field] = format_date_for_form(dweller[date_field])
                
                dweller['credit_balance'] = float(dweller.get('credit_balance', 0))
                dweller['rating'] = float(dweller.get('rating', 0))
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
            required_fields = ['first_name', 'last_name', 'email', 'date_of_birth', 'registration_date']
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

            new_dweller = {
                'first_name': request.form['first_name'],
                'last_name': request.form['last_name'],
                'email': request.form['email'],
                'phone_number': request.form.get('phone_number'),
                'date_of_birth': date_of_birth,
                'registration_date': registration_date,
                'verification_code': str(uuid.uuid4().hex[:6].upper())
            }
            
            db.table('city_dwellers').insert(new_dweller).execute()
            flash('City dweller added successfully!', 'success')

        elif action == 'delete_dweller':
            user_id = request.form.get('user_id')
            if not user_id:
                raise ValueError("User ID is required")

            # Check for active rentals
            rental_response = db.table('rentals')\
                .select("*")\
                .eq('dweller_id', user_id)\
                .eq('status', 'active')\
                .execute()

            if rental_response.data:
                raise ValueError("Cannot remove dweller with active rentals")

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