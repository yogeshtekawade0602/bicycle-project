from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from supabase import create_client, Client
from dotenv import load_dotenv
import os
from datetime import datetime
import hashlib
import uuid
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "fallback-secret-key")

# Initialize Supabase client as None first
supabase: Client = None

def get_supabase() -> Client:
    """Get or initialize Supabase client"""
    global supabase
    if supabase is None:
        try:
            url = os.getenv("SUPABASE_URL")
            key = os.getenv("SUPABASE_KEY")
            
            if not url or not key:
                logger.error("Missing Supabase credentials")
                return None
                
            supabase = create_client(url, key)
            logger.info("Supabase client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase: {str(e)}")
            return None
    return supabase

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

# Health check endpoint
@app.route('/health')
def health_check():
    db = get_supabase()
    try:
        # Simple database check
        if db:
            db.table('city_dwellers').select("count", "exact").limit(1).execute()
            db_status = "connected"
        else:
            db_status = "disconnected"
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        db_status = "error"

    status = {
        "status": "healthy" if db_status == "connected" else "degraded",
        "database": db_status,
        "timestamp": datetime.now().isoformat()
    }
    return jsonify(status), 200 if db_status == "connected" else 503

@app.route('/')
@app.route('/dashboard')
def list_dwellers():
    db = get_supabase()
    if not db:
        flash("Database connection not available", 'error')
        return render_template('dashboard.html', dwellers=[])

    try:
        response = db.table('city_dwellers')\
            .select("*")\
            .eq('account_status', 'active')\
            .execute()
        
        dwellers = response.data if response else []
        
        # Format dates and ensure numeric values
        for dweller in dwellers:
            try:
                if dweller.get('registration_date'):
                    dweller['registration_date'] = datetime.strptime(
                        dweller['registration_date'], 
                        '%Y-%m-%d'
                    ).strftime('%m/%d/%Y')
                
                if dweller.get('date_of_birth'):
                    dweller['date_of_birth'] = datetime.strptime(
                        dweller['date_of_birth'], 
                        '%Y-%m-%d'
                    ).strftime('%m/%d/%Y')
                
                dweller['credit_balance'] = float(dweller.get('credit_balance', 0))
                dweller['rating'] = float(dweller.get('rating', 0))
            except (ValueError, TypeError) as e:
                logger.warning(f"Error formatting dweller data: {str(e)}")
                dweller['credit_balance'] = 0
                dweller['rating'] = 0
        
        return render_template('dashboard.html', dwellers=dwellers)
                             
    except Exception as e:
        logger.error(f"Error fetching dwellers: {str(e)}")
        flash("Error fetching data", 'error')
        return render_template('dashboard.html', dwellers=[])

@app.route('/manage_dweller', methods=['POST'])
def manage_dweller():
    db = get_supabase()
    if not db:
        flash("Database connection not available", 'error')
        return redirect(url_for('list_dwellers'))

    try:
        action = request.form.get('action')
        if not action:
            raise ValueError("No action specified")

        if action == 'add_dweller':
            try:
                # Validate required fields
                required_fields = ['first_name', 'last_name', 'email', 'password', 
                                 'registration_date', 'date_of_birth']
                for field in required_fields:
                    if not request.form.get(field):
                        raise ValueError(f"Missing required field: {field}")

                # Generate salt and hash password
                salt = uuid.uuid4().hex
                password = request.form['password']
                password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
                
                # Format dates with validation
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
                    'phone_number': request.form['phone_number'],
                    'date_of_birth': date_of_birth,
                    'address': request.form['address'],
                    'registration_date': registration_date,
                    'password_hash': password_hash,
                    'salt': salt,
                    'preferred_language': request.form.get('preferred_language', 'en'),
                    'verification_code': str(uuid.uuid4().hex[:6].upper())
                }
                
                db.table('city_dwellers').insert(new_dweller).execute()
                flash('City dweller added successfully!', 'success')
                
            except ValueError as e:
                raise ValueError(f"Invalid data format: {str(e)}")

        elif action == 'edit_dweller':
            # Get the user_id
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
            except ValueError as e:
                flash("Invalid date format. Please use MM/DD/YYYY", 'error')
                return redirect(url_for('list_dwellers'))

            # Prepare update data
            updated_dweller = {
                'first_name': request.form['first_name'],
                'last_name': request.form['last_name'],
                'email': request.form['email'],
                'phone_number': request.form['phone_number'],
                'date_of_birth': date_of_birth,
                'address': request.form['address'],
                'registration_date': registration_date,
                'credit_balance': float(request.form.get('credit_balance', 0)),
                'rating': float(request.form.get('rating', 0)),
                'verification_status': request.form.get('verification_status', 'pending'),
                'preferred_language': request.form.get('preferred_language', 'en')
            }

            # Update the database
            response = db.table('city_dwellers')\
                .update(updated_dweller)\
                .eq('user_id', user_id)\
                .execute()

            if response.data:
                flash('City dweller updated successfully!', 'success')
            else:
                flash('No changes were made.', 'warning')
            
        elif action == 'delete_dweller':
            # Soft delete by updating account status
            user_id = request.form.get('user_id')
            response = db.table('city_dwellers')\
                .update({'account_status': 'inactive'})\
                .eq('user_id', user_id)\
                .execute()
            flash('City dweller removed successfully!', 'success')
            
    except ValueError as e:
        flash(f"Invalid data: {str(e)}", 'error')
    except Exception as e:
        flash(f"Unexpected error: {str(e)}", 'error')
        print(f"Error in manage_dweller: {str(e)}")  # Log the full error
        
    return redirect(url_for('list_dwellers'))

@app.route('/add', methods=['GET', 'POST'])
def add_dweller():
    db = get_supabase()
    if not db:
        flash("Database connection not available", 'error')
        return redirect(url_for('list_dwellers'))

    if request.method == 'POST':
        try:
            registration_date = datetime.strptime(
                request.form['registration_date'], 
                '%m/%d/%Y'
            ).strftime('%Y-%m-%d')
            
            new_dweller = {
                'first_name': request.form['first_name'],
                'last_name': request.form['last_name'],
                'email': request.form['email'],
                'phone': request.form['phone'],
                'registration_date': registration_date,
            }
            
            response = db.table('city_dwellers').insert(new_dweller).execute()
            
            if response.data:
                flash('City dweller added successfully!', 'success')
                return redirect(url_for('list_dwellers'))
            
        except Exception as e:
            flash(f"Error: {str(e)}", 'error')
            
    return render_template('add_dweller.html')

@app.route('/manage_rental/<uuid:dweller_id>', methods=['POST'])
def manage_rental(dweller_id):
    db = get_supabase()
    if not db:
        flash("Database connection not available", 'error')
        return redirect(url_for('list_dwellers'))

    try:
        action = request.form.get('action')
        bike_id = request.form.get('bike_id')
        
        if action == 'start':
            # Start new rental
            new_rental = {
                'dweller_id': str(dweller_id),
                'bicycle_id': bike_id,
                'status': 'active',
                'start_location_lat': request.form.get('lat'),
                'start_location_lng': request.form.get('lng')
            }
            
            # Create rental record
            rental_response = db.table('rentals').insert(new_rental).execute()
            
            # Update bicycle status
            db.table('bicycles')\
                .update({'status': 'in_use'})\
                .eq('id', bike_id)\
                .execute()
                
            flash('Rental started successfully!', 'success')
            
        elif action == 'end':
            # End existing rental
            rental_update = {
                'status': 'completed',
                'end_time': datetime.now().isoformat(),
                'end_location_lat': request.form.get('lat'),
                'end_location_lng': request.form.get('lng')
            }
            
            # Update rental record
            rental_response = db.table('rentals')\
                .update(rental_update)\
                .eq('dweller_id', str(dweller_id))\
                .eq('status', 'active')\
                .execute()
                
            if rental_response.data:
                # Get bicycle ID from rental
                bike_id = rental_response.data[0]['bicycle_id']
                
                # Update bicycle status
                db.table('bicycles')\
                    .update({'status': 'available'})\
                    .eq('id', bike_id)\
                    .execute()
                    
                flash('Rental ended successfully!', 'success')
            
    except Exception as e:
        flash(f"Error managing rental: {str(e)}", 'error')
        
    return redirect(url_for('list_dwellers'))

@app.route('/edit/<uuid:dweller_id>', methods=['GET', 'POST'])
def edit_dweller(dweller_id):
    db = get_supabase()
    if not db:
        flash("Database connection not available", 'error')
        return redirect(url_for('list_dwellers'))

    try:
        if request.method == 'GET':
            response = db.table('city_dwellers')\
                .select("*")\
                .eq('id', str(dweller_id))\
                .execute()
            
            if not response.data:
                flash('City dweller not found.', 'error')
                return redirect(url_for('list_dwellers'))
            
            dweller = response.data[0]
            dweller['registration_date'] = datetime.strptime(
                dweller['registration_date'], 
                '%Y-%m-%d'
            ).strftime('%m/%d/%Y')
            
            return render_template('edit_dweller.html', dweller=dweller)
            
        elif request.method == 'POST':
            registration_date = datetime.strptime(
                request.form['registration_date'], 
                '%m/%d/%Y'
            ).strftime('%Y-%m-%d')
            
            updated_dweller = {
                'first_name': request.form['first_name'],
                'last_name': request.form['last_name'],
                'email': request.form['email'],
                'phone': request.form['phone'],
                'registration_date': registration_date,
            }
            
            response = db.table('city_dwellers')\
                .update(updated_dweller)\
                .eq('id', str(dweller_id))\
                .execute()
                
            if response.data:
                flash('City dweller updated successfully!', 'success')
                return redirect(url_for('list_dwellers'))
            
    except Exception as e:
        flash(f"Error: {str(e)}", 'error')
        
    return redirect(url_for('list_dwellers'))

@app.route('/delete/<uuid:dweller_id>', methods=['POST'])
def delete_dweller(dweller_id):
    db = get_supabase()
    if not db:
        flash("Database connection not available", 'error')
        return redirect(url_for('list_dwellers'))

    try:
        # Check if dweller has active rentals
        rental_response = db.table('rentals')\
            .select("*")\
            .eq('dweller_id', str(dweller_id))\
            .eq('status', 'active')\
            .execute()
            
        if rental_response.data:
            flash('Cannot remove dweller with active rentals.', 'error')
            return redirect(url_for('list_dwellers'))
            
        # Soft delete
        response = db.table('city_dwellers')\
            .update({'active': False})\
            .eq('id', str(dweller_id))\
            .execute()
            
        if response.data:
            flash('City dweller removed successfully!', 'success')
        else:
            flash('City dweller not found.', 'error')
            
    except Exception as e:
        flash(f"Error: {str(e)}", 'error')
        
    return redirect(url_for('list_dwellers'))

# For local development only
if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    app.run(host='0.0.0.0', port=port)