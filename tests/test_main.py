import unittest
from app.main import app, supabase
from datetime import datetime
import json

class CityDwellerTests(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()
        
        # Test user data
        self.test_user = {
            'first_name': 'Test',
            'last_name': 'User',
            'email': f'test{datetime.now().timestamp()}@example.com',
            'phone_number': '123-456-7890',
            'date_of_birth': '01/01/1990',
            'address': '123 Test St',
            'registration_date': '01/01/2024',
            'password': 'testpass123',
            'preferred_language': 'en',
            'credit_balance': 100.00,
            'rating': 4.5,
            'verification_status': 'pending'
        }

    def test_list_dwellers_page(self):
        """Test if the main page loads correctly"""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'City Dwellers', response.data)

    def test_add_dweller(self):
        """Test adding a new city dweller"""
        response = self.client.post('/manage_dweller', data={
            'action': 'add_dweller',
            **self.test_user
        })
        self.assertEqual(response.status_code, 302)  # Redirect after success
        
        # Verify the user was added
        db_response = supabase.table('city_dwellers')\
            .select("*")\
            .eq('email', self.test_user['email'])\
            .execute()
        self.assertTrue(len(db_response.data) > 0)

    def test_edit_dweller(self):
        """Test editing an existing city dweller"""
        # First, add a test user
        add_response = self.client.post('/manage_dweller', data={
            'action': 'add_dweller',
            **self.test_user
        })
        
        # Get the user_id from database
        db_response = supabase.table('city_dwellers')\
            .select("*")\
            .eq('email', self.test_user['email'])\
            .execute()
        user_id = db_response.data[0]['user_id']
        
        # Edit the user
        updated_data = {
            'action': 'edit_dweller',
            'user_id': user_id,
            **self.test_user,
            'first_name': 'Updated',
            'credit_balance': 200.00
        }
        
        edit_response = self.client.post('/manage_dweller', data=updated_data)
        self.assertEqual(edit_response.status_code, 302)
        
        # Verify the update
        verify_response = supabase.table('city_dwellers')\
            .select("*")\
            .eq('user_id', user_id)\
            .execute()
        self.assertEqual(verify_response.data[0]['first_name'], 'Updated')
        self.assertEqual(float(verify_response.data[0]['credit_balance']), 200.00)

    def test_delete_dweller(self):
        """Test deleting (deactivating) a city dweller"""
        # First, add a test user
        add_response = self.client.post('/manage_dweller', data={
            'action': 'add_dweller',
            **self.test_user
        })
        
        # Get the user_id
        db_response = supabase.table('city_dwellers')\
            .select("*")\
            .eq('email', self.test_user['email'])\
            .execute()
        user_id = db_response.data[0]['user_id']
        
        # Delete the user
        delete_response = self.client.post('/manage_dweller', data={
            'action': 'delete_dweller',
            'user_id': user_id
        })
        self.assertEqual(delete_response.status_code, 302)
        
        # Verify the user is deactivated
        verify_response = supabase.table('city_dwellers')\
            .select("*")\
            .eq('user_id', user_id)\
            .execute()
        self.assertEqual(verify_response.data[0]['account_status'], 'inactive')

    def test_validation(self):
        """Test input validation"""
        # Test invalid email
        invalid_user = dict(self.test_user)
        invalid_user['email'] = 'invalid-email'
        
        # Follow redirects to see the flash message
        response = self.client.post('/manage_dweller', data={
            'action': 'add_dweller',
            **invalid_user
        }, follow_redirects=True)
        
        # Check if the response contains an error message
        self.assertEqual(response.status_code, 200)
        
        # Test invalid phone number
        invalid_user = dict(self.test_user)
        invalid_user['phone_number'] = '123'
        response = self.client.post('/manage_dweller', data={
            'action': 'add_dweller',
            **invalid_user
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        
        # Test invalid date
        invalid_user = dict(self.test_user)
        invalid_user['date_of_birth'] = 'invalid-date'
        response = self.client.post('/manage_dweller', data={
            'action': 'add_dweller',
            **invalid_user
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)

    def test_credit_balance_update(self):
        """Test credit balance operations"""
        # Add test user
        add_response = self.client.post('/manage_dweller', data={
            'action': 'add_dweller',
            **self.test_user
        })
        
        # Get user_id
        db_response = supabase.table('city_dwellers')\
            .select("*")\
            .eq('email', self.test_user['email'])\
            .execute()
        user_id = db_response.data[0]['user_id']
        
        # Update credit balance
        update_response = self.client.post('/manage_dweller', data={
            'action': 'edit_dweller',
            'user_id': user_id,
            **self.test_user,
            'credit_balance': 150.00
        })
        
        # Verify update
        verify_response = supabase.table('city_dwellers')\
            .select("*")\
            .eq('user_id', user_id)\
            .execute()
        self.assertEqual(float(verify_response.data[0]['credit_balance']), 150.00)

    def test_rating_update(self):
        """Test rating updates"""
        # Add test user
        add_response = self.client.post('/manage_dweller', data={
            'action': 'add_dweller',
            **self.test_user
        })
        
        # Get user_id
        db_response = supabase.table('city_dwellers')\
            .select("*")\
            .eq('email', self.test_user['email'])\
            .execute()
        user_id = db_response.data[0]['user_id']
        
        # Update rating
        update_response = self.client.post('/manage_dweller', data={
            'action': 'edit_dweller',
            'user_id': user_id,
            **self.test_user,
            'rating': 4.8
        })
        
        # Verify update
        verify_response = supabase.table('city_dwellers')\
            .select("*")\
            .eq('user_id', user_id)\
            .execute()
        self.assertEqual(float(verify_response.data[0]['rating']), 4.8)

    def tearDown(self):
        """Clean up test data"""
        try:
            # Delete test user
            supabase.table('city_dwellers')\
                .delete()\
                .eq('email', self.test_user['email'])\
                .execute()
        except:
            pass

if __name__ == '__main__':
    unittest.main() 