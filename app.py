import os
import pyodbc
import secrets
import string
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = '@b1@ck91nk_1l@73u'
app.config['UPLOAD_FOLDER'] = 'static/uploads'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)



def get_db_connection():
    try:
        conn = pyodbc.connect(
            'DRIVER={ODBC Driver 11 for SQL Server};'
            'SERVER=DESKTOP-N2FF52A\\SQLEXPRESS;'
            'DATABASE=DENTAL_MANAGEMENT;'
            'Trusted_Connection=yes;'
        )
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

@app.route('/')
def index():
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            EXEC SP_USERLOGIN ?, ?
        """, (username, password))

        user = cursor.fetchone()

        if user:
            login_id = user[0]
            user_role = get_user_role(login_id)

          
            session['user'] = user[1]  
            session['role'] = user_role 
            session['login_id'] = login_id 

            return redirect(url_for('admin_dashboard'))  
        else:
            flash('Invalid credentials or inactive user', 'danger')  
            return redirect(url_for('login')) 

    return render_template('login.html')  


def get_user_role(login_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT dbo.FN_GETUSERROLE(?)", (login_id,))
    role = cursor.fetchone()
    
    return role[0] if role else None

@app.route('/admin_dashboard')
def admin_dashboard():
    if 'user' in session:
        user_name = f"{session.get('user', '')}"
        user_role = session.get('role', '')
        
        
        if user_role == 'admin':
            return render_template('admin_dashboard.html', user_name=user_name)
        else:
            
            return render_template('unauthorized.html')
    else:
        return redirect(url_for('login')) 


@app.route('/user_management')
def admin_user_management():
    if 'user' in session and session.get('role') == 'admin':
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
         
            cursor.execute("""
                SELECT u.LOGIN_ID, u.USER_LNAME, u.USER_FNAME, u.PHO_NUM, u.USERNAME, 
                       u.USER_IMG, d.DENTIST_SPEC, u.ISACTIVE
                FROM USER_PROFILE u
                JOIN DENTIST d ON u.LOGIN_ID = d.LOGIN_ID
                WHERE u.USER_ROLE = 'dentist'
                ORDER BY u.USER_LNAME
            """)
            dentists = cursor.fetchall()
            
           
            cursor.execute("""
                SELECT LOGIN_ID, USER_LNAME, USER_FNAME, PHO_NUM, USERNAME, 
                       USER_IMG, ISACTIVE
                FROM USER_PROFILE
                WHERE USER_ROLE = 'staff'
                ORDER BY USER_LNAME
            """)
            staff = cursor.fetchall()
            
            conn.close()
            
            return render_template('admin_user_management.html', 
                                  dentists=dentists, 
                                  staff=staff, 
                                  user_name=session.get('user'))
        except Exception as e:
            print(f"Error fetching user data: {e}")
            return render_template('admin_user_management.html', 
                                  error="Unable to fetch user data", 
                                  user_name=session.get('user'))
    else:
        return redirect(url_for('login'))



def generate_username(first_name, last_name):
   
    base_username = f"{first_name[0].lower()}{last_name.lower()}"
    
   
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM USER_PROFILE WHERE USERNAME = ?", (base_username,))
    count = cursor.fetchone()[0]
    
    if count > 0:
      
        cursor.execute("""
            SELECT TOP 1 USERNAME 
            FROM USER_PROFILE 
            WHERE USERNAME LIKE ?
            ORDER BY USERNAME DESC
        """, (f"{base_username}%",))
        
        result = cursor.fetchone()
        if result:
            existing_username = result[0]
            if existing_username == base_username:
                return f"{base_username}1"
            else:
                
                try:
                    suffix = ''.join(filter(str.isdigit, existing_username[len(base_username):]))
                    if suffix:
                        return f"{base_username}{int(suffix) + 1}"
                    else:
                        return f"{base_username}1"
                except:
                    return f"{base_username}1"
        else:
            return base_username
    else:
        return base_username


def generate_password(length=10):
    alphabet = string.ascii_letters + string.digits
    password = ''.join(secrets.choice(alphabet) for i in range(length))
    return password

@app.route('/api/users')
def get_users():
    """API endpoint to get all users"""
    if 'user' in session and session.get('role') == 'admin':
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            
            cursor.execute("""
                SELECT u.LOGIN_ID, u.USER_LNAME, u.USER_FNAME, u.PHO_NUM, u.EMAIL, 
                       u.USER_IMG, d.DENTIST_SPEC, u.ISACTIVE
                FROM USER_PROFILE u
                JOIN DENTIST d ON u.LOGIN_ID = d.LOGIN_ID
                WHERE u.USER_ROLE = 'dentist'
                ORDER BY u.USER_LNAME
            """)
            
            dentists = []
            columns = [column[0] for column in cursor.description]
            for row in cursor.fetchall():
                dentists.append(dict(zip(columns, row)))
            
        
            cursor.execute("""
                SELECT LOGIN_ID, USER_LNAME, USER_FNAME, PHO_NUM, EMAIL, 
                       USER_IMG, ISACTIVE
                FROM USER_PROFILE
                WHERE USER_ROLE = 'staff'
                ORDER BY USER_LNAME
            """)
            
            staff = []
            columns = [column[0] for column in cursor.description]
            for row in cursor.fetchall():
                staff.append(dict(zip(columns, row)))
            
            conn.close()
            
            return jsonify({'dentists': dentists, 'staff': staff})
        except Exception as e:
            print(f"Error fetching user data: {e}")
            return jsonify({'error': str(e)}), 500
    else:
        return jsonify({'error': 'Unauthorized'}), 401
        

@app.route('/add_user', methods=['POST'])
def add_user():
    """Add a new user and return generated credentials"""
    if 'user' in session and session.get('role') == 'admin':
        try:
         
            first_name = request.form.get('firstName')
            last_name = request.form.get('lastName')
            contact_number = request.form.get('contactNumber')
            email = request.form.get('emailAddress')
            user_role = request.form.get('userRole')
            specialization = request.form.get('specialization') if user_role == 'dentist' else None
            
          
            username = generate_username(first_name, last_name)
            password = generate_password()
            
        
            profile_img = None
            if 'profileImage' in request.files:
                file = request.files['profileImage']
                if file.filename != '':
                  
                    filename = secure_filename(file.filename)
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    profile_img = f"/static/uploads/{filename}"
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
           
            if user_role == 'dentist':
                cursor.execute("""
                    EXEC SP_ADD_DENTIST ?, ?, ?, ?, ?, ?, ?, ?
                """, (first_name, last_name, contact_number, email, specialization, profile_img, username, password))
            else:
                cursor.execute("""
                    EXEC SP_ADD_STAFF ?, ?, ?, ?, ?, ?, ?
                """, (first_name, last_name, contact_number, email, profile_img, username, password))
            
            conn.commit()
        
            cursor.execute("""
                SELECT TOP 1 LOGIN_ID FROM USER_PROFILE
                WHERE USERNAME = ?
                ORDER BY LOGIN_ID DESC
            """, (username,))
            
            new_user_id = cursor.fetchone()[0]
            conn.close()
            
            return jsonify({
                'success': True,
                'message': 'User added successfully',
                'username': username,
                'password': password,
                'userId': new_user_id
            })
            
        except Exception as e:
            print(f"Error adding user: {e}")
            return jsonify({
                'success': False,
                'message': f'Error adding user: {str(e)}'
            }), 500
    else:
        return jsonify({
            'success': False,
            'message': 'Unauthorized'
        }), 401

@app.route('/update_user/<int:user_id>', methods=['POST'])
def update_user(user_id):
    """Update an existing user"""
    if 'user' in session and session.get('role') == 'admin':
        try:
         
            email = request.form.get('emailAddress')
            contact_number = request.form.get('contactNumber')
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE USER_PROFILE
                SET PHO_NUM = ?, EMAIL = ?, MODIFIED_BY = ?
                WHERE LOGIN_ID = ?
            """, (contact_number, email, session.get('user'), user_id))
            
            conn.commit()
            conn.close()
            
            return jsonify({
                'success': True,
                'message': 'User updated successfully'
            })
            
        except Exception as e:
            print(f"Error updating user: {e}")
            return jsonify({
                'success': False,
                'message': f'Error updating user: {str(e)}'
            }), 500
    else:
        return jsonify({
            'success': False,
            'message': 'Unauthorized'
        }), 401

@app.route('/toggle_user_status/<int:user_id>')
def toggle_user_status(user_id):
    """Toggle a user's active status"""
    if 'user' in session and session.get('role') == 'admin':
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
        
            cursor.execute("SELECT ISACTIVE FROM USER_PROFILE WHERE LOGIN_ID = ?", (user_id,))
            current_status = cursor.fetchone()[0]
            
           
            new_status = not current_status
            
            cursor.execute("""
                UPDATE USER_PROFILE
                SET ISACTIVE = ?, MODIFIED_BY = ?
                WHERE LOGIN_ID = ?
            """, (new_status, session.get('user'), user_id))
            
            conn.commit()
            conn.close()
            
            status_message = 'activated' if new_status else 'deactivated'
            
            return jsonify({
                'success': True,
                'message': f'User {status_message} successfully',
                'newStatus': new_status
            })
            
        except Exception as e:
            print(f"Error toggling user status: {e}")
            return jsonify({
                'success': False,
                'message': f'Error updating user status: {str(e)}'
            }), 500
    else:
        return jsonify({
            'success': False,
            'message': 'Unauthorized'
        }), 401

@app.route('/treatments')
def admin_treatments():
    if 'user' in session:
        user_name = f"{session.get('user', '')}"
        return render_template('admin_treatments.html', user_name=user_name)
    else:
        return redirect(url_for('login'))

@app.route('/api/treatments')
def get_treatments():
    """API endpoint to get all treatments"""
    if 'user' in session:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("EXEC SP_GET_ALL_TREATMENTS")
            
            treatments = []
            columns = [column[0] for column in cursor.description]
            for row in cursor.fetchall():
                treatments.append(dict(zip(columns, row)))
            
            conn.close()
            
            return jsonify({'treatments': treatments})
        except Exception as e:
            print(f"Error fetching treatments: {e}")
            return jsonify({'error': str(e)}), 500
    else:
        return jsonify({'error': 'Unauthorized'}), 401
        
@app.route('/api/treatments/<int:treatment_id>')
def get_treatment(treatment_id):
    """API endpoint to get a specific treatment"""
    if 'user' in session:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("EXEC SP_GET_TREATMENT_BY_ID ?", (treatment_id,))
            
            row = cursor.fetchone()
            if row:
                columns = [column[0] for column in cursor.description]
                treatment = dict(zip(columns, row))
                
                conn.close()
                return jsonify({'treatment': treatment})
            else:
                conn.close()
                return jsonify({'error': 'Treatment not found'}), 404
        except Exception as e:
            print(f"Error fetching treatment: {e}")
            return jsonify({'error': str(e)}), 500
    else:
        return jsonify({'error': 'Unauthorized'}), 401

@app.route('/api/treatments/add', methods=['POST'])
def add_treatment():
    """Add a new treatment"""
    if 'user' in session:
        try:
            treatment_type = request.form.get('treatmentName')
            no_of_sessions = int(request.form.get('noOfSessions'))
            treatment_desc = request.form.get('description')
            estimated_duration = request.form.get('estimatedDuration')
            treatment_price = float(request.form.get('treatmentPrice'))
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                EXEC SP_ADD_TREATMENT ?, ?, ?, ?, ?
            """, (treatment_type, no_of_sessions, treatment_desc, estimated_duration, treatment_price))

            # Skip any empty result sets
            while cursor.nextset() and not cursor.description:
                pass

            result = cursor.fetchone()
            treatment_id = result[0] if result else None
            
            try:
                result = cursor.fetchone()
                treatment_id = result[0] if result else None
            except pyodbc.ProgrammingError:
                
                treatment_id = None
            
            conn.commit()
            conn.close()
            
            return jsonify({
                'success': True,
                'message': 'Treatment added successfully',
                'treatmentId': treatment_id
            })
            
        except Exception as e:
            print(f"Error adding treatment: {e}")
            return jsonify({
                'success': False,
                'message': f'Error adding treatment: {str(e)}'
            }), 500
    else:
        return jsonify({
            'success': False,
            'message': 'Unauthorized'
        }), 401

@app.route('/api/treatments/update/<int:treatment_id>', methods=['POST'])
def update_treatment(treatment_id):
    """Update an existing treatment"""
    if 'user' in session:
        try:
            treatment_type = request.form.get('treatmentName')
            no_of_sessions = request.form.get('noOfSessions')
            treatment_desc = request.form.get('description')
            estimated_duration = request.form.get('estimatedDuration')
            treatment_price = request.form.get('treatmentPrice')
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                EXEC SP_UPDATE_TREATMENT ?, ?, ?, ?, ?, ?
            """, (treatment_id, treatment_type, no_of_sessions, treatment_desc, estimated_duration, treatment_price))
            
            
            result = cursor.fetchone()
            affected_rows = result[0] if result else 0
            
            conn.commit()
            conn.close()
            
            if affected_rows > 0:
                return jsonify({
                    'success': True,
                    'message': 'Treatment updated successfully'
                })
            else:
                return jsonify({
                    'success': False,
                    'message': 'Treatment not found or no changes made'
                }), 404
            
        except Exception as e:
            print(f"Error updating treatment: {e}")
            return jsonify({
                'success': False,
                'message': f'Error updating treatment: {str(e)}'
            }), 500
    else:
        return jsonify({
            'success': False,
            'message': 'Unauthorized'
        }), 401

@app.route('/logout')
def logout():
    session.clear()  
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)

