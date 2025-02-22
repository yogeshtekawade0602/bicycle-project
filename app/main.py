from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from supabase import create_client
from dotenv import load_dotenv
import os
from datetime import datetime
import hashlib
import uuid

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "fallback-secret-key")  # Added fallback

# Add custom exception classes
class SupabaseConnectionError(Exception):
    pass

class DwellerNotFoundError(Exception):
    pass

class InvalidDataError(Exception):
    pass

# Initialize Supabase client with better error handling
def init_supabase():
    try:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        
        if not url or not key:
            raise SupabaseConnectionError("Missing Supabase credentials")
            
        return create_client(url, key)
    except Exception as e:
        raise SupabaseConnectionError(f"Failed to initialize Supabase: {str(e)}")

try:
    supabase = init_supabase()
except SupabaseConnectionError as e:
    print(f"Supabase initialization error: {str(e)}")
    supabase = None

# Add more comprehensive error handlers
@app.errorhandler(404)
def not_found_error(error):
    return jsonify({
        "error": "Not Found",
        "message": "The requested resource was not found"
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        "error": "Internal Server Error",
        "message": str(error)
    }), 500

def generate_salt():
    return uuid.uuid4().hex

def hash_password(password, salt):
    return hashlib.sha256((password + salt).encode()).hexdigest()

@app.route('/')
@app.route('/dashboard')
def list_dwellers():
    try:
        if not supabase:
            raise SupabaseConnectionError("Database connection not available")

        # Fetch active dwellers with all columns
        response = supabase.table('city_dwellers')\
            .select("*")\
            .eq('account_status', 'active')\
            .execute()
            
        if not response:
            raise DwellerNotFoundError("Failed to fetch dwellers data")
            
        dwellers = response.data
        
        # Format dates and ensure numeric values with error handling
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
                
                # Ensure numeric values have defaults
                dweller['credit_balance'] = float(dweller.get('credit_balance', 0))
                dweller['rating'] = float(dweller.get('rating', 0))
            except ValueError as e:
                print(f"Error formatting dweller data: {str(e)}")
                # Set default values if formatting fails
                dweller['credit_balance'] = 0
                dweller['rating'] = 0
        
        return render_template('dashboard.html', dwellers=dwellers)
                             
    except SupabaseConnectionError as e:
        flash(f"Database connection error: {str(e)}", 'error')
        return render_template('dashboard.html', dwellers=[])
    except DwellerNotFoundError as e:
        flash(f"Data retrieval error: {str(e)}", 'error')
        return render_template('dashboard.html', dwellers=[])
    except Exception as e:
        flash(f"Unexpected error: {str(e)}", 'error')
        return render_template('dashboard.html', dwellers=[])

@app.route('/manage_dweller', methods=['POST'])
def manage_dweller():
    try:
        if not supabase:
            raise SupabaseConnectionError("Database connection not available")

        action = request.form.get('action')
        if not action:
            raise InvalidDataError("No action specified")

        if action == 'add_dweller':
            try:
                # Validate required fields
                required_fields = ['first_name', 'last_name', 'email', 'password', 
                                 'registration_date', 'date_of_birth']
                for field in required_fields:
                    if not request.form.get(field):
                        raise InvalidDataError(f"Missing required field: {field}")

                # Generate salt and hash password
                salt = generate_salt()
                password = request.form['password']
                password_hash = hash_password(password, salt)
                
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
                    raise InvalidDataError("Invalid date format. Use MM/DD/YYYY")

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
                
                supabase.table('city_dwellers').insert(new_dweller).execute()
                flash('City dweller added successfully!', 'success')
                
            except ValueError as e:
                raise InvalidDataError(f"Invalid data format: {str(e)}")

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
            response = supabase.table('city_dwellers')\
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
            supabase.table('city_dwellers')\
                .update({'account_status': 'inactive'})\
                .eq('user_id', user_id)\
                .execute()
            flash('City dweller removed successfully!', 'success')
            
    except SupabaseConnectionError as e:
        flash(f"Database connection error: {str(e)}", 'error')
    except InvalidDataError as e:
        flash(f"Invalid data: {str(e)}", 'error')
    except Exception as e:
        flash(f"Unexpected error: {str(e)}", 'error')
        print(f"Error in manage_dweller: {str(e)}")  # Log the full error
        
    return redirect(url_for('list_dwellers'))

@app.route('/add', methods=['GET', 'POST'])
def add_dweller():
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
            
            response = supabase.table('city_dwellers').insert(new_dweller).execute()
            
            if response.data:
                flash('City dweller added successfully!', 'success')
                return redirect(url_for('list_dwellers'))
            
        except Exception as e:
            flash(f"Error: {str(e)}", 'error')
            
    return render_template('add_dweller.html')

@app.route('/manage_rental/<uuid:dweller_id>', methods=['POST'])
def manage_rental(dweller_id):
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
            rental_response = supabase.table('rentals').insert(new_rental).execute()
            
            # Update bicycle status
            supabase.table('bicycles')\
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
            rental_response = supabase.table('rentals')\
                .update(rental_update)\
                .eq('dweller_id', str(dweller_id))\
                .eq('status', 'active')\
                .execute()
                
            if rental_response.data:
                # Get bicycle ID from rental
                bike_id = rental_response.data[0]['bicycle_id']
                
                # Update bicycle status
                supabase.table('bicycles')\
                    .update({'status': 'available'})\
                    .eq('id', bike_id)\
                    .execute()
                    
                flash('Rental ended successfully!', 'success')
            
    except Exception as e:
        flash(f"Error managing rental: {str(e)}", 'error')
        
    return redirect(url_for('list_dwellers'))

@app.route('/edit/<uuid:dweller_id>', methods=['GET', 'POST'])
def edit_dweller(dweller_id):
    try:
        if request.method == 'GET':
            response = supabase.table('city_dwellers')\
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
            
            response = supabase.table('city_dwellers')\
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
    try:
        # Check if dweller has active rentals
        rental_response = supabase.table('rentals')\
            .select("*")\
            .eq('dweller_id', str(dweller_id))\
            .eq('status', 'active')\
            .execute()
            
        if rental_response.data:
            flash('Cannot remove dweller with active rentals.', 'error')
            return redirect(url_for('list_dwellers'))
            
        # Soft delete
        response = supabase.table('city_dwellers')\
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

# Health check endpoint with database connection status
@app.route('/health')
def health_check():
    status = {
        "status": "healthy" if supabase else "degraded",
        "database": "connected" if supabase else "disconnected",
        "timestamp": datetime.now().isoformat()
    }
    return jsonify(status), 200 if supabase else 503

# Modified app run configuration
if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    app.run(host='0.0.0.0', port=port)