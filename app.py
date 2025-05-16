import os
import pyodbc
import secrets
import string
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime
from werkzeug.utils import secure_filename


app = Flask(__name__)
app.secret_key = '@b1@ck91nk_1l@73u'
app.config['UPLOAD_FOLDER'] = 'static/uploads'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


def get_db_connection():
    try:
        conn = pyodbc.connect(
            'DRIVER={ODBC Driver 11 for SQL Server};'
            'SERVER=DESKTOP-8DN8MKL\\SQLEXPRESS;'
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
            
            # Get first and last name
            cursor.execute("""
                SELECT USER_LNAME
                FROM USER_PROFILE
                WHERE LOGIN_ID = ?
            """, (login_id,))
            
            name_data = cursor.fetchone()
            if name_data:
                user_name = f"{name_data[0]}"
            else:
                user_name = username  # Fallback to username
          
            session['user'] = user_name  # Store full name in session
            session['role'] = user_role 
            session['login_id'] = login_id 

            # Redirect based on user role
            if user_role == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user_role == 'dentist':
                return redirect(url_for('dentist_dashboard'))
            elif user_role == 'staff':
                return redirect(url_for('staff_dashboard'))
            else:
                # Default redirection 
                return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid credentials or inactive user', 'danger')  
            return redirect(url_for('login')) 

    return render_template('login.html')

    return render_template('login.html')


@app.route('/dentist_dashboard')
def dentist_dashboard():
    if 'user' in session and session.get('role') == 'dentist':
        user_name = session.get('user', '')
        
        # Here you can fetch dentist-specific data from the database
        # For example: today's appointments, patient stats, etc.
        
        # Get current date for the dashboard
        from datetime import datetime
        current_date = datetime.now().strftime("%A, %d %B %Y")
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Get dentist ID from login ID
            login_id = session.get('login_id')
            cursor.execute("SELECT DENTIST_ID FROM DENTIST WHERE LOGIN_ID = ?", (login_id,))
            dentist_result = cursor.fetchone()
            
            if dentist_result:
                dentist_id = dentist_result[0]
                
                # Get today's appointments for this dentist
                cursor.execute("""
                    SELECT 
                        a.APPT_ID,
                        p.PAT_FNAME + ' ' + p.PAT_LNAME AS PATIENT_NAME,
                        FORMAT(a.APPOINTMENT_TIME, 'hh:mm tt') AS APPT_TIME,
                        t.TREATMENT_TYPE,
                        CASE 
                            WHEN p.PAT_REGDATE = CONVERT(date, GETDATE()) THEN 'New Patient'
                            ELSE t.TREATMENT_TYPE
                        END AS APPOINTMENT_TYPE
                    FROM APPOINTMENT a
                    JOIN PATIENT p ON a.PATIENT_ID = p.PATIENT_ID
                    LEFT JOIN TREATMENT t ON a.TREATMENT_ID = t.TREATMENT_ID
                    WHERE a.DENTIST_ID = ? 
                    AND CONVERT(date, a.APPT_DATE) = CONVERT(date, GETDATE())
                    ORDER BY a.APPOINTMENT_TIME
                """, (dentist_id,))
                
                appointments = []
                columns = [column[0] for column in cursor.description]
                for row in cursor.fetchall():
                    appointments.append(dict(zip(columns, row)))
                
                # Get monthly appointment stats
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM APPOINTMENT 
                    WHERE DENTIST_ID = ? 
                    AND MONTH(APPOINTMENT_DATE) = MONTH(GETDATE())
                    AND YEAR(APPOINTMENT_DATE) = YEAR(GETDATE())
                """, (dentist_id,))
                
                monthly_appointments = cursor.fetchone()[0]
                
                # Get monthly patient stats
                cursor.execute("""
                    SELECT COUNT(DISTINCT PATIENT_ID) 
                    FROM APPOINTMENT 
                    WHERE DENTIST_ID = ? 
                    AND MONTH(APPOINTMENT_DATE) = MONTH(GETDATE())
                    AND YEAR(APPOINTMENT_DATE) = YEAR(GETDATE())
                """, (dentist_id,))
                
                monthly_patients = cursor.fetchone()[0]
                
                conn.close()
                
                return render_template('dentist_dashboard.html', 
                                      user_name=user_name,
                                      current_date=current_date,
                                      appointments=appointments,
                                      appointment_count=len(appointments),
                                      monthly_appointments=monthly_appointments,
                                      monthly_patients=monthly_patients)
            else:
                flash('Dentist profile not found', 'danger')
                return redirect(url_for('login'))
                
        except Exception as e:
            print(f"Error fetching dentist data: {e}")
            return render_template('dentist_dashboard.html', 
                                  user_name=user_name,
                                  current_date=current_date,
                                  error="Unable to fetch appointment data")
    else:
        return redirect(url_for('login'))

@app.route('/staff_dashboard')
def staff_dashboard():
    if 'user' in session and session.get('role') == 'staff':
        login_id = session.get('login_id')
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Get staff's actual first and last name
            cursor.execute("""
                SELECT USER_FNAME, USER_LNAME
                FROM USER_PROFILE
                WHERE LOGIN_ID = ?
            """, (login_id,))
            
            user_data = cursor.fetchone()
            if user_data:
                user_name = f"{user_data[0]} {user_data[1]}"
            else:
                user_name = session.get('user', '')  # Fallback to session value
            
            # Get current date for the dashboard
            from datetime import datetime
            current_date = datetime.now().strftime("%A, %d %B %Y")
            
            # Get today's patient count
            cursor.execute("""
                SELECT COUNT(DISTINCT a.PATIENT_ID)
                FROM APPOINTMENT a
                WHERE CONVERT(date, a.APPT_DATE) = CONVERT(date, GETDATE())
            """)
            
            today_patients = cursor.fetchone()[0]
            
            # Get yesterday's patient count
            cursor.execute("""
                SELECT COUNT(DISTINCT a.PATIENT_ID)
                FROM APPOINTMENT a
                WHERE CONVERT(date, a.APPT_DATE) = DATEADD(day, -1, CONVERT(date, GETDATE()))
            """)
            
            yesterday_patients = cursor.fetchone()[0]
            
            # Get recent activities
            cursor.execute("""
                SELECT TOP 5
                    FORMAT(a.APPT_DATE, 'yy-MM-dd') AS DATE,
                    p.PAT_FNAME + ' ' + p.PAT_LNAME + ' - ' + t.TREATMENT_TYPE AS ACTIVITY_TITLE
                FROM APPOINTMENT a
                JOIN PATIENT p ON a.PATIENT_ID = p.PATIENT_ID
                LEFT JOIN TREATMENT t ON a.TREATMENT_ID = t.TREATMENT_ID
                ORDER BY a.APPT_DATE DESC
            """)
            
            activities = []
            columns = [column[0] for column in cursor.description]
            for row in cursor.fetchall():
                activities.append(dict(zip(columns, row)))
            
            conn.close()
            
            return render_template('staff_dashboard.html', 
                                  user_name=user_name,  # This will be the first and last name
                                  current_date=current_date,
                                  today_patients=today_patients,
                                  yesterday_patients=yesterday_patients,
                                  activities=activities)
        except Exception as e:
            print(f"Error fetching staff data: {e}")
            return render_template('staff_dashboard.html', 
                                  user_name=session.get('user', ''),
                                  current_date=datetime.now().strftime("%A, %d %B %Y"),
                                  error="Unable to fetch appointment data")
    else:
        return redirect(url_for('login'))

def get_user_role(login_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT dbo.FN_GETUSERROLE(?)", (login_id,))
    role = cursor.fetchone()
    
    return role[0] if role else None

@app.route('/api/dashboard/active-patients', methods=['GET'])
def get_active_patients():
    if 'login_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Count only active patients (not deactivated)
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM PATIENT
        """)
        
        result = cursor.fetchone()
        conn.close()
        
        return jsonify({'count': result[0]})
    except Exception as e:
        return jsonify({'error': str(e), 'count': 0}), 500

@app.route('/api/dashboard/today-appointments', methods=['GET'])
def get_today_appointments():
    if 'login_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get today's appointment count
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM APPOINTMENT
            WHERE CONVERT(date, APPT_DATE) = CONVERT(date, GETDATE())
        """)
        
        result = cursor.fetchone()
        conn.close()
        
        return jsonify({'count': result[0]})
    except Exception as e:
        return jsonify({'error': str(e), 'count': 0}), 500

@app.route('/api/dashboard/monthly-revenue', methods=['GET'])
def get_monthly_revenue():
    if 'login_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Calculate monthly revenue from transaction_header table
        cursor.execute("""
            SELECT ISNULL(SUM(TOTAL_AMOUNT), 0) as total
            FROM TRANSACTION_HEADER
            WHERE MONTH(TRANSC_DATE) = MONTH(GETDATE())
            AND YEAR(TRANSC_DATE) = YEAR(GETDATE())
        """)
        
        result = cursor.fetchone()
        conn.close()
        
        return jsonify({'amount': float(result[0]) if result[0] else 0})
    except Exception as e:
        return jsonify({'error': str(e), 'amount': 0}), 500


@app.route('/admin_dashboard')
def admin_dashboard():
    if 'user' in session and session.get('role') == 'admin':
        user_name = session.get('user', '')
        
        return render_template('admin_dashboard.html', user_name=user_name)
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

@app.route('/staff_treatments')
def staff_treatments():
    if 'user' in session:
        user_name = f"{session.get('user', '')}"
        return render_template('staff_treatments.html', user_name=user_name)
    else:
        return redirect(url_for('login'))

@app.route('/dentist_treatments')
def dentist_treatments():
    if 'user' in session:
        user_name = f"{session.get('user', '')}"
        return render_template('dentist_treatments.html', user_name=user_name)
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

# Replace the current admin_settings function with this unified version
@app.route('/user_settings')
def user_settings():
    print("Entering user_settings function")  # Debug print
    if 'user' in session:
        try:
            login_id = session.get('login_id')
            user_role = session.get('role')
            
            print(f"User in session: {session.get('user')}, Role: {user_role}, ID: {login_id}")  # Debug print
            
            conn = get_db_connection()
            if conn is None:
                print("Database connection failed")  # Debug print
                flash('Database connection error', 'danger')
                return redirect(url_for('login'))
                
            cursor = conn.cursor()
            
            # Base user profile information (common for all roles)
            cursor.execute("""
                SELECT u.LOGIN_ID, u.USER_LNAME, u.USER_FNAME, u.USER_ROLE, 
                       u.PHO_NUM, u.EMAIL, u.USER_IMG
                FROM USER_PROFILE u
                WHERE u.LOGIN_ID = ?
            """, (login_id,))
            
            user = cursor.fetchone()
            print(f"User data fetched: {user}")  # Debug print
            
            if user:
                # Format the common data
                user_data = {
                    'login_id': user[0],
                    'user_lname': user[1],
                    'user_fname': user[2],
                    'user_role': user[3],
                    'phone_number': user[4],
                    'email': user[5],
                    'user_img': user[6]
                }
                
                # Get role-specific information if needed
                if user_role == 'dentist':
                    # Get dentist specialization
                    cursor.execute("""
                        SELECT DENTIST_SPEC
                        FROM DENTIST
                        WHERE LOGIN_ID = ?
                    """, (login_id,))
                    
                    dentist_info = cursor.fetchone()
                    if dentist_info:
                        user_data['specialization'] = dentist_info[0]
                
                conn.close()
                
                # Determine which template to use based on role
                if user_role == 'admin':
                    template = 'admin_settings.html'
                elif user_role == 'dentist':
                    template = 'dentist_settings.html'
                else:  # staff or any other role
                    template = 'staff_settings.html'
                
                print(f"Rendering template: {template}")  # Debug print
                return render_template(template, 
                                    user_name=session.get('user'),
                                    **user_data)
            else:
                conn.close()
                print("User profile not found")  # Debug print
                flash('User profile not found', 'danger')
                return redirect(url_for('login'))
        except Exception as e:
            print(f"Error in user_settings: {e}")  # Debug print with specific error
            flash('Error accessing settings', 'danger')
            return redirect(url_for('login'))
    else:
        print("No user in session")  # Debug print
        return redirect(url_for('login'))

@app.route('/update_profile', methods=['POST'])
def update_profile():
    if 'user' in session:
        try:
            login_id = session.get('login_id')
            user_role = session.get('role')
            
            # Get common form data
            firstname = request.form.get('firstname')
            lastname = request.form.get('lastname')
            phone = request.form.get('phone')
            email = request.form.get('email')
            
            # Handle the case where email is 'N/A' or empty
            if email == 'N/A' or not email.strip():
                email = None
                
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT USERNAME FROM USER_PROFILE WHERE LOGIN_ID = ?", (login_id,))
            result = cursor.fetchone()
            if result:
                actual_username = result[0]
            else:
                actual_username = username 
            
            # Use direct SQL update instead of stored procedure
            cursor.execute("""
                UPDATE USER_PROFILE
                SET USER_FNAME = ?,
                    USER_LNAME = ?,
                    PHO_NUM = ?,
                    EMAIL = ?,
                    MODIFIED_BY = ?
                WHERE LOGIN_ID = ?
            """, (firstname, lastname, phone, email, actual_username, login_id))
            
            # Handle role-specific updates
            if user_role == 'dentist':
                # Update dentist specialization if provided
                specialization = request.form.get('specialization')
                if specialization:
                    cursor.execute("""
                        UPDATE DENTIST
                        SET DENTIST_SPEC = ?
                        WHERE LOGIN_ID = ?
                    """, (specialization, login_id))
            
            # Handle profile image upload if present
            if 'profile_image' in request.files:
                profile_img = request.files['profile_image']
                if profile_img.filename != '':
                    filename = secure_filename(profile_img.filename)
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    profile_img.save(file_path)
                    profile_img_path = f"/static/uploads/{filename}"
                    
                    cursor.execute("""
                        UPDATE USER_PROFILE
                        SET USER_IMG = ?
                        WHERE LOGIN_ID = ?
                    """, (profile_img_path, login_id))
            
       
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            if new_password and new_password == confirm_password:
                cursor.execute("""
                    UPDATE USER_PROFILE
                    SET PASSWORD = ?
                    WHERE LOGIN_ID = ?
                """, (new_password, login_id))
            
            conn.commit()
            conn.close()
            
            # Update session data
            session['user'] = f"{firstname} {lastname}"
            
            flash('Profile updated successfully', 'success')
            return redirect(url_for('user_settings'))
                
        except Exception as e:
            print(f"Error updating profile: {e}")
            flash('An error occurred while updating your profile', 'danger')
            return redirect(url_for('user_settings'))
    else:
        return redirect(url_for('login'))


@app.route('/admin_settings')
def admin_settings():
    
    return redirect(url_for('user_settings'))

@app.route('/dentist_settings')
def dentist_settings():
    
    return redirect(url_for('user_settings'))


@app.route('/staff_settings')
def staff_settings():
     
    return redirect(url_for('user_settings'))

# Routes for patient management pages
@app.route('/staff_patient_management')
def staff_patient_management():
    if 'login_id' not in session:  # Check for login_id instead of user_id
        return redirect(url_for('login'))
    return render_template('staff_patient_management.html')

@app.route('/dentist_patient')
def dentist_patient():
    if 'login_id' not in session:  # Check for login_id instead of user_id
        return redirect(url_for('login'))
    return render_template('dentist_patient.html')


# API endpoints for patient data
@app.route('/api/patients', methods=['GET'])
def get_patients():
    if 'login_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("EXEC SP_GET_ALL_PATIENTS")
        
        patients = []
        columns = [column[0] for column in cursor.description]
        
        for row in cursor.fetchall():
            patient = dict(zip(columns, row))
            patients.append(patient)
            
        conn.close()
        return jsonify(patients)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/dashboard/monthly-performance')
def monthly_performance():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        current_date = datetime.now()
        current_month = current_date.month
        current_year = current_date.year
        
        cursor.execute("""
            SELECT 
                COUNT(CASE WHEN t.TRANSACTION_HEADER_ID IS NOT NULL THEN 1 END) AS completed_count,
                COUNT(CASE WHEN a.APPT_STATUS = 'CANCELLED' THEN 1 END) AS cancelled_count,
                COUNT(*) AS total_count
            FROM APPOINTMENT a
            LEFT JOIN TRANSACTION_HEADER t ON a.APPT_ID = t.APPT_ID
            WHERE MONTH(a.APPT_DATE) = ? AND YEAR(a.APPT_DATE) = ?
        """, (current_month, current_year))
        
        result = cursor.fetchone()
        
        if result:
            completed_count, cancelled_count, total_count = result
            return jsonify({
                'success': True,
                'completed': completed_count,
                'cancelled': cancelled_count,
                'total': total_count
            })
        else:
            return jsonify({
                'success': True,
                'completed': 0,
                'cancelled': 0,
                'total': 0
            })
            
    except Exception as e:
        print(f"Error fetching monthly performance: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"Error fetching monthly performance data: {str(e)}",
            'completed': 0,
            'cancelled': 0,
            'total': 0
        })
    
    finally:
        cursor.close()
        conn.close()

@app.route('/api/patients', methods=['POST'])
def add_patient():
    if 'login_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['lastName', 'firstName', 'phoneNumber']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
                
        # Get optional fields
        email_address = data.get('emailAddress')
        sex = data.get('sex', 'Not specified')  # Default value if not provided
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Execute stored procedure
        cursor.execute(
            "EXEC SP_ADD_PATIENT @lastName=?, @firstName=?, @sex=?, @phoneNumber=?, @emailAddress=?, @loginId=?",
            data['lastName'], data['firstName'], sex, data['phoneNumber'], email_address, session['login_id']
        )
        
       # Try to get the newly created patient ID, but handle case where no results are returned
        patient_id = None
        try:
            result = cursor.fetchone()
            patient_id = result[0] if result else None
        except:
            # Procedure executed but didn't return results
            pass
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'patientId': patient_id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500
        

@app.route('/api/patients/<int:patient_id>', methods=['GET'])
def get_patient_details(patient_id):
    if 'login_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Execute stored procedure to get patient details
        cursor.execute("EXEC SP_GET_PATIENT_DETAILS @patientId=?", patient_id)
        
        # Get patient basic info
        patient_info = cursor.fetchone()
        if not patient_info:
            return jsonify({'error': 'Patient not found'}), 404
            
        columns = [column[0] for column in cursor.description]
        patient = dict(zip(columns, patient_info))
        
        # Next resultset: Insurance info
        cursor.nextset()
        insurances = []
        if cursor.description:  # Check if there are results
            columns = [column[0] for column in cursor.description]
            for row in cursor.fetchall():
                insurance = dict(zip(columns, row))
                insurances.append(insurance)
        
        # Next resultset: Appointments
        cursor.nextset()
        appointments = []
        if cursor.description:  # Check if there are results
            columns = [column[0] for column in cursor.description]
            for row in cursor.fetchall():
                appointment = dict(zip(columns, row))
                
                # Convert date to string format
                if 'date' in appointment:
                    appointment['date'] = appointment['date'].strftime('%b %d, %Y %I:%M %p')
                
                appointments.append(appointment)
                
        # Next resultset: Treatments/Transactions
        cursor.nextset()
        treatments = []
        if cursor.description:  # Check if there are results
            columns = [column[0] for column in cursor.description]
            for row in cursor.fetchall():
                treatment = dict(zip(columns, row))
                
                # Convert date to string format
                if 'transactionDate' in treatment:
                    treatment['transactionDate'] = treatment['transactionDate'].strftime('%b %d, %Y')
                
                treatments.append(treatment)
        
        conn.close()
        
        # Combine all data
        patient_data = {
            **patient,
            'insurances': insurances,
            'appointments': appointments,
            'treatments': treatments
        }
        
        return jsonify(patient_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/patients/<int:patient_id>', methods=['PUT'])
def update_patient(patient_id):
    if 'login_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['lastName', 'firstName', 'phoneNumber']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
                
        # Get current user info for modified_by field
        user_name = session.get('user_name', 'Unknown')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Execute stored procedure
        cursor.execute(
            """EXEC SP_UPDATE_PATIENT
               @patientId=?, @lastName=?, @firstName=?, @sex=?, @phoneNumber=?, 
               @emailAddress=?, @modifiedBy=?""",
            patient_id, data['lastName'], data['firstName'], data.get('sex', 'Not specified'), 
            data['phoneNumber'], data.get('emailAddress'), session.get('user_name')
        )
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'User updated successfully'
        })
            
    except Exception as e:
        print(f"Error updating patient: {e}")
        return jsonify({
            'success': False,
            'message': f'Error updating patient: {str(e)}'
        }), 500

# API endpoint for insurance management
@app.route('/api/patients/<int:patient_id>/insurance', methods=['POST'])
def add_insurance(patient_id):
    if 'login_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['company', 'policyNumber', 'coverage', 'expirationDate']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
                
        # Parse expiration date
        try:
            expiration_date = datetime.strptime(data['expirationDate'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Invalid expiration date format. Use YYYY-MM-DD'}), 400
            
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Execute stored procedure
        cursor.execute(
            """EXEC SP_ADD_INSURANCE_TO_PATIENT 
               @patientId=?, @company=?, @policyNumber=?, @coverage=?, 
               @expirationDate=?, @isPrimary=?""",
            patient_id, data['company'], data['policyNumber'], 
            data['coverage'], expiration_date, data.get('isPrimary', 0)
        )
        
        # Get the newly created insurance ID
        result = cursor.fetchone()
        insurance_id = result[0] if result else None
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'insuranceId': insurance_id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/insurance/<int:insurance_id>', methods=['PUT'])
def update_insurance(insurance_id):
    if 'login_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['company', 'policyNumber', 'coverage', 'expirationDate']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
                
        # Parse expiration date
        try:
            expiration_date = datetime.strptime(data['expirationDate'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Invalid expiration date format. Use YYYY-MM-DD'}), 400
            
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Execute stored procedure
        cursor.execute(
            """EXEC SP_UPDATE_INSURANCE
               @insuranceId=?, @company=?, @policyNumber=?, @coverage=?, 
               @expirationDate=?, @isPrimary=?""",
            insurance_id, data['company'], data['policyNumber'], 
            data['coverage'], expiration_date, data.get('isPrimary', 0)
        )
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Appointments page route
@app.route('/staff_APPOINTMENT')
def staff_APPOINTMENT():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Modified query to show all appointments except completed ones
        cursor.execute("""
            SELECT 
                a.APPT_ID,
                p.PAT_FNAME + ' ' + p.PAT_LNAME as PATIENT_NAME,
                d.USER_FNAME + ' ' + d.USER_LNAME as DENTIST_NAME,
                FORMAT(CAST(a.APPT_DATE as time), 'hh:mm tt') as APPT_TIME,
                FORMAT(CAST(a.APPT_DATE as date), 'MMM dd, yyyy') as APPT_DATE,
                CASE 
                    WHEN a.APPT_STATUS = 'BOOKED' AND CAST(a.APPT_DATE AS DATE) < CAST(GETDATE() AS DATE) THEN 'ONGOING'
                    ELSE a.APPT_STATUS 
                END as APPT_STATUS,
                a.CANCEL_RES
            FROM APPOINTMENT a
            JOIN PATIENT p ON a.PATIENT_ID = p.PATIENT_ID
            JOIN DENTIST dt ON a.DENTIST_ID = dt.DENTIST_ID
            JOIN USER_PROFILE d ON dt.LOGIN_ID = d.LOGIN_ID
            WHERE a.APPT_STATUS != 'COMPLETED'
            ORDER BY 
                CASE 
                    WHEN a.APPT_STATUS = 'BOOKED' AND CAST(a.APPT_DATE AS DATE) < CAST(GETDATE() AS DATE) THEN 1
                    WHEN a.APPT_STATUS = 'BOOKED' THEN 2
                    ELSE 3
                END,
                a.APPT_DATE DESC
        """)
        
        appointments = []
        for row in cursor.fetchall():
            appointments.append({
                'APPT_ID': row.APPT_ID,
                'PATIENT_NAME': row.PATIENT_NAME,
                'DENTIST_NAME': row.DENTIST_NAME,
                'APPT_TIME': row.APPT_TIME,
                'APPT_DATE': row.APPT_DATE,
                'APPT_STATUS': row.APPT_STATUS,
                'CANCEL_RES': row.CANCEL_RES
            })
        
        return render_template('staff_APPOINTMENT.html', appointments=appointments)
    
    except Exception as e:
        print(f"Error fetching appointments: {str(e)}")
        return render_template('staff_APPOINTMENT.html', appointments=[], error="Unable to fetch appointments")
    
    finally:
        cursor.close()
        conn.close()

# API endpoint to search patients
@app.route('/api/search_patients')

def search_patients():
    search_term = request.args.get('term', '')
    
    if len(search_term) < 2:
        return jsonify([])
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("EXEC sp_SearchPatients @SearchTerm=?", search_term)
        patients = []
        for row in cursor.fetchall():
            patients.append({
                'PATIENT_ID': row.PATIENT_ID,
                'PATIENT_NAME': row.PATIENT_NAME,
                'PATIENT_PHO_NUM': row.PATIENT_PHO_NUM,
                'PATIENT_EMAIL_ADD': row.PATIENT_EMAIL_ADD
            })
        
        return jsonify(patients)
    
    except Exception as e:
        print(f"Error searching patients: {str(e)}")
        return jsonify([])
    
    finally:
        cursor.close()
        conn.close()

# API endpoint to check appointment availability
@app.route('/api/check_appointment_availability')
def check_appointment_availability():
    date = request.args.get('date', '')
    time = request.args.get('time', '')
    
    print(f"Checking availability for date: {date}, time: {time}")  # Debug log
    
    if not date or not time:
        return jsonify({'available': False, 'message': 'Date and time are required'})
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Convert time to SQL time format and combine with date
        try:
            time_obj = datetime.strptime(time, "%H:%M")
            date_obj = datetime.strptime(date, "%Y-%m-%d")
            appointment_datetime = datetime.combine(date_obj.date(), time_obj.time())
            
            # Check if appointment is in the past
            current_datetime = datetime.now()
            if appointment_datetime < current_datetime:
                return jsonify({
                    'available': False,
                    'message': 'Cannot book appointments in the past'
                })
                
            print(f"Checking datetime: {appointment_datetime}")  # Debug log
        except ValueError as e:
            print(f"DateTime format error: {str(e)}")  # Debug log
            return jsonify({'available': False, 'message': 'Invalid date/time format'})
        
        # Check if there are any existing appointments at the same time
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM APPOINTMENT
            WHERE CAST(APPT_DATE AS DATE) = CAST(? AS DATE)
            AND CAST(APPT_TIME AS TIME) = CAST(? AS TIME)
            AND APPT_STATUS = 'BOOKED'
        """, (appointment_datetime, appointment_datetime))
        
        result = cursor.fetchone()
        count = result[0] if result else 0
        print(f"Found {count} existing appointments")  # Debug log
        
        available = count == 0
        
        response = {
            'available': available,
            'message': 'Time slot is available' if available else 'Time slot is already booked'
        }
        print(f"Sending response: {response}")  # Debug log
        return jsonify(response)
    
    except Exception as e:
        print(f"Error checking appointment availability: {str(e)}")
        return jsonify({'available': False, 'message': f'Error checking availability: {str(e)}'})
    
    finally:
        cursor.close()
        conn.close()

# API endpoint to get available dentists
@app.route('/api/available_dentists')

def get_available_dentists():
    date = request.args.get('date', '')
    time = request.args.get('time', '')
    
    if not date or not time:
        return jsonify([])
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("EXEC sp_GetAvailableDentists @AppointmentDate=?, @AppointmentTime=?", 
                      date, time)
        dentists = []
        for row in cursor.fetchall():
            dentists.append({
                'DENTIST_ID': row.DENTIST_ID,
                'DENTIST_NAME': row.DENTIST_NAME,
                'DENTIST_SPEC': row.DENTIST_SPEC
            })
        
        return jsonify(dentists)
    
    except Exception as e:
        print(f"Error getting available dentists: {str(e)}")
        return jsonify([])
    
    finally:
        cursor.close()
        conn.close()

# Create appointment
@app.route('/staff/create_appointment', methods=['POST'])
def create_appointment():
    data = request.json
    
    patient_id = data.get('patient_id')
    dentist_id = data.get('dentist_id')
    appointment_date = data.get('appointment_date')
    appointment_time = data.get('appointment_time')
    
    # Basic validation
    if not all([patient_id, dentist_id, appointment_date, appointment_time]):
        return jsonify({
            'success': False,
            'message': 'All fields are required'
        })
    
    # Convert time to SQL datetime format
    try:
        time_obj = datetime.strptime(appointment_time, "%H:%M")
        date_obj = datetime.strptime(appointment_date, "%Y-%m-%d")
        appointment_datetime = datetime.combine(date_obj.date(), time_obj.time())
        
        # Check if appointment is in the past
        current_datetime = datetime.now()
        if appointment_datetime < current_datetime:
            return jsonify({
                'success': False,
                'message': 'Cannot book appointments in the past'
            })
            
    except ValueError:
        return jsonify({
            'success': False,
            'message': 'Invalid date/time format'
        })
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check for existing appointments at the same time
        cursor.execute("""
            SELECT COUNT(*) as ExistingAppointments
            FROM APPOINTMENT
            WHERE CAST(APPT_DATE AS DATE) = CAST(? AS DATE)
            AND CAST(APPT_DATE AS TIME) = CAST(? AS TIME)
            AND APPT_STATUS != 'CANCELLED'
            AND (PATIENT_ID = ? OR DENTIST_ID = ?)
        """, (appointment_datetime, appointment_datetime, patient_id, dentist_id))
        
        result = cursor.fetchone()
        if result.ExistingAppointments > 0:
            return jsonify({
                'success': False,
                'message': 'This time slot is already booked for the patient or dentist'
            })
        
        # Get the current user's name for modified_by field
        modified_by = f"{session.get('user_fname', '')} {session.get('user_lname', '')}"
        
        # Create the appointment
        cursor.execute("""
            INSERT INTO APPOINTMENT (PATIENT_ID, DENTIST_ID, APPT_DATE, APPT_STATUS, MODIFIED_BY)
            OUTPUT INSERTED.APPT_ID
            VALUES (?, ?, ?, 'BOOKED', ?)
        """, (patient_id, dentist_id, appointment_datetime, modified_by))
        
        result = cursor.fetchone()
        appt_id = result[0] if result else 0
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Appointment created successfully',
            'appointment_id': appt_id
        })
    
    except Exception as e:
        print(f"Error creating appointment: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"Error creating appointment: {str(e)}"
        })
    
    finally:
        cursor.close()
        conn.close()

# Cancel appointment endpoint
@app.route('/staff/cancel_appointment', methods=['POST'])
def cancel_appointment():
    data = request.json
    
    appointment_id = data.get('appointment_id')
    cancel_reason = data.get('cancel_reason')
    
    # Basic validation
    if not appointment_id or not cancel_reason:
        return jsonify({
            'success': False,
            'message': 'Appointment ID and cancellation reason are required'
        })
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get the current user's name for modified_by field
        modified_by = f"{session.get('user_fname', '')} {session.get('user_lname', '')}"
        
        cursor.execute("EXEC sp_CancelAppointment @AppointmentID=?, @CancelReason=?, @ModifiedBy=?",
                       appointment_id, cancel_reason, modified_by)
        
        # Try to fetch result, but handle case where nothing is returned
        try:
            result = cursor.fetchone()
            message = result.Message if result and hasattr(result, 'Message') else "Appointment cancelled successfully"
        except:
            # If fetchone fails, assume success (since the SP executed without error)
            message = "Appointment cancelled successfully"
        
        return jsonify({
            'success': True,
            'message': message
        })
    
    except Exception as e:
        print(f"Error cancelling appointment: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"Error cancelling appointment: {str(e)}"
        })
    
    finally:
        conn.commit()
        cursor.close()
        conn.close()

# Dentist appointments page route
@app.route('/dentist_appointment')
def dentist_appointment():
    if 'login_id' not in session:
        return redirect(url_for('login'))
    
    # Get date parameter from request
    selected_date = request.args.get('date')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        login_id = session['login_id']
        
        # Get the DENTIST_ID
        cursor.execute("SELECT DENTIST_ID FROM DENTIST WHERE LOGIN_ID = ?", login_id)
        row = cursor.fetchone()
        
        if not row:
            flash("Your account is not linked to a dentist profile", "error")
            return redirect(url_for('login'))
        
        dentist_id = row.DENTIST_ID
        dentist_name = f"{session.get('user_fname', '')} {session.get('user_lname', '')}"

        today_date = datetime.now().strftime('%Y-%m-%d')
        
        # Pass the date parameter if provided
        if selected_date:
            cursor.execute("EXEC sp_GetDentistAppointments @DentistID=?, @AppointmentDate=?", 
                          dentist_id, selected_date)
        else:
            cursor.execute("EXEC sp_GetDentistAppointments @DentistID=?", dentist_id)
        
        appointments = []
        for row in cursor.fetchall():
            appointments.append({
                'APPT_ID': row.APPT_ID,
                'PATIENT_NAME': row.PATIENT_NAME,
                'DENTIST_NAME': row.DENTIST_NAME,
                'APPT_TIME': row.APPT_TIME,
                'APPT_DATE': row.APPT_DATE,
                'APPT_STATUS': row.APPT_STATUS,
                'CANCEL_RES': row.CANCEL_RES
            })
        
        return render_template('dentist_appointment.html',
                              appointments=appointments,
                              dentist_name=dentist_name,
                              selected_date=selected_date)
        
    except Exception as e:
        flash(f"Error loading appointments: {str(e)}", "error")
        return render_template('dentist_appointment.html',
                              appointments=[],
                              dentist_name=dentist_name,
                              selected_date=selected_date)
    
    finally:
        cursor.close()
        conn.close()

@app.route('/dentist/reschedule_appointment', methods=['POST'])
def reschedule_appointment():
    if 'login_id' not in session:
        return redirect(url_for('login'))
    
    data = request.json
    appointment_id = data.get('appointment_id')
    new_date = data.get('new_date')
    new_time = data.get('new_time')
    
    # Basic validation
    if not all([appointment_id, new_date, new_time]):
        return jsonify({
            'success': False,
            'message': 'All fields are required'
        })
    
    # Convert time to SQL datetime format
    try:
        time_obj = datetime.strptime(new_time, "%H:%M")
        date_obj = datetime.strptime(new_date, "%Y-%m-%d")
        appointment_datetime = datetime.combine(date_obj.date(), time_obj.time())
    except ValueError:
        return jsonify({
            'success': False,
            'message': 'Invalid date/time format'
        })
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get the current appointment details
        cursor.execute("""
            SELECT PATIENT_ID, DENTIST_ID, APPT_STATUS
            FROM APPOINTMENT
            WHERE APPT_ID = ?
        """, (appointment_id,))
        
        appt = cursor.fetchone()
        if not appt:
            return jsonify({
                'success': False,
                'message': 'Appointment not found'
            })
        
        if appt.APPT_STATUS == 'COMPLETED':
            return jsonify({
                'success': False,
                'message': 'Cannot reschedule a completed appointment'
            })
        
        # Check for existing appointments at the new time
        cursor.execute("""
            SELECT COUNT(*) as ExistingAppointments
            FROM APPOINTMENT
            WHERE CAST(APPT_DATE AS DATE) = CAST(? AS DATE)
            AND CAST(APPT_TIME AS TIME) = CAST(? AS TIME)
            AND APPT_STATUS != 'CANCELLED'
            AND APPT_ID != ?
            AND (PATIENT_ID = ? OR DENTIST_ID = ?)
        """, (appointment_datetime, appointment_datetime, appointment_id, appt.PATIENT_ID, appt.DENTIST_ID))
        
        result = cursor.fetchone()
        if result.ExistingAppointments > 0:
            return jsonify({
                'success': False,
                'message': 'This time slot is already booked'
            })
        
        # Get the current user's name for modified_by field
        modified_by = f"{session.get('user_fname', '')} {session.get('user_lname', '')}"
        
        # Update the appointment
        cursor.execute("""
            UPDATE APPOINTMENT
            SET APPT_DATE = ?,
                MODIFIED_BY = ?,
                MODIFIED_DATE = GETDATE()
            WHERE APPT_ID = ?
        """, (appointment_datetime, modified_by, appointment_id))
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Appointment rescheduled successfully'
        })
    
    except Exception as e:
        print(f"Error rescheduling appointment: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"Error rescheduling appointment: {str(e)}"
        })
    
    finally:
        cursor.close()
        conn.close()


@app.route('/api/dentist/patients', methods=['GET'])
def get_dentist_patients():
    if 'login_id' not in session or session.get('role') != 'dentist':
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get dentist ID from login ID
        login_id = session['login_id']
        cursor.execute("SELECT DENTIST_ID FROM DENTIST WHERE LOGIN_ID = ?", (login_id,))
        dentist_result = cursor.fetchone()
        
        if not dentist_result:
            return jsonify({"error": "Dentist not found"}), 404
            
        dentist_id = dentist_result[0]
        
        # Get all patients assigned to this dentist
        cursor.execute("EXEC SP_GET_DENTIST_PATIENTS ?", (dentist_id,))
        
        patients = []
        columns = [column[0] for column in cursor.description]
        for row in cursor.fetchall():
            patients.append(dict(zip(columns, row)))
            
        conn.close()
        return jsonify(patients)
        
    except Exception as e:
        print(f"Error fetching dentist patients: {str(e)}")
        return jsonify({"error": "Failed to fetch patients"}), 500


# Dentist Transaction Routes
@app.route('/dentist_transactions')
def dentist_transactions():
    if 'user' in session and session.get('role') == 'dentist':
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Get dentist ID from login ID
            login_id = session.get('login_id')
            cursor.execute("SELECT DENTIST_ID FROM DENTIST WHERE LOGIN_ID = ?", (login_id,))
            dentist_result = cursor.fetchone()
            
            if dentist_result:
                dentist_id = dentist_result[0]
                
                # Get dentist's transactions (both pending and completed)
                cursor.execute("""
                    SELECT 
                        TH.TRANSACTION_HEADER_ID,
                        P.PATIENT_FNAME + ' ' + P.PATIENT_LNAME AS PatientName,
                        TH.TRANSC_DATE,
                        TH.TOTAL_AMOUNT,
                        PM.MODE_OF_PAYMENT AS PaymentStatus
                    FROM 
                        TRANSACTION_HEADER TH
                    JOIN 
                        APPOINTMENT A ON TH.APPT_ID = A.APPT_ID
                    JOIN 
                        PATIENT P ON A.PATIENT_ID = P.PATIENT_ID
                    JOIN 
                        PAYMENT PM ON TH.PAYMENT_ID = PM.PAYMENT_ID
                    WHERE 
                        A.DENTIST_ID = ?
                    ORDER BY 
                        TH.TRANSC_DATE DESC
                """, (dentist_id,))
                
                transactions = []
                columns = [column[0] for column in cursor.description]
                for row in cursor.fetchall():
                    transactions.append(dict(zip(columns, row)))
                
                conn.close()
                
                return render_template('dentist_transactions.html', 
                                    user_name=session.get('user'),
                                    transactions=transactions)
            else:
                flash('Dentist profile not found', 'danger')
                return redirect(url_for('login'))
                
        except Exception as e:
            print(f"Error fetching dentist transactions: {e}")
            return render_template('dentist_transactions.html', 
                                user_name=session.get('user'),
                                error="Unable to fetch transaction data")
    else:
        return redirect(url_for('login'))
    
# Staff endpoints
@app.route('/api/transactions/pending', methods=['GET'])
def get_pending_transactions():
    if 'login_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get pending transactions based on role
        if session.get('role') == 'staff':
            cursor.execute("""
                SELECT 
                    TH.TRANSACTION_HEADER_ID,
                    P.PAT_FNAME + ' ' + P.PAT_LNAME AS PatientName,
                    D.USER_FNAME + ' ' + D.USER_LNAME AS DentistName,
                    TH.TRANSC_DATE,
                    TH.TOTAL_AMOUNT,
                    TH.STATUS
                FROM TRANSACTION_HEADER TH
                JOIN APPOINTMENT A ON TH.APPT_ID = A.APPT_ID
                JOIN PATIENT P ON A.PATIENT_ID = P.PATIENT_ID
                JOIN DENTIST DT ON A.DENTIST_ID = DT.DENTIST_ID
                JOIN USER_PROFILE D ON DT.LOGIN_ID = D.LOGIN_ID
                WHERE TH.STATUS = 'PENDING'
                ORDER BY TH.TRANSC_DATE DESC
            """)
        else:  # dentist
            cursor.execute("""
                SELECT 
                    TH.TRANSACTION_HEADER_ID,
                    P.PAT_FNAME + ' ' + P.PAT_LNAME AS PatientName,
                    TH.TRANSC_DATE,
                    TH.TOTAL_AMOUNT,
                    TH.STATUS
                FROM TRANSACTION_HEADER TH
                JOIN APPOINTMENT A ON TH.APPT_ID = A.APPT_ID
                JOIN PATIENT P ON A.PATIENT_ID = P.PATIENT_ID
                JOIN DENTIST D ON A.DENTIST_ID = D.DENTIST_ID
                WHERE D.LOGIN_ID = ? AND TH.STATUS = 'PENDING'
                ORDER BY TH.TRANSC_DATE DESC
            """, (session['login_id'],))
        
        transactions = []
        columns = [column[0] for column in cursor.description]
        for row in cursor.fetchall():
            transactions.append(dict(zip(columns, row)))
            
        return jsonify(transactions)
        
    except Exception as e:
        print(f"Error fetching pending transactions: {str(e)}")
        return jsonify({'error': str(e)}), 500
    
    finally:
        if conn:
            conn.close()

@app.route('/api/transactions/completed', methods=['GET'])
def get_completed_transactions():
    if 'login_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get completed transactions based on role
        if session.get('role') == 'staff':
            cursor.execute("""
                SELECT 
                    TH.TRANSACTION_HEADER_ID,
                    P.PAT_FNAME + ' ' + P.PAT_LNAME AS PatientName,
                    D.USER_FNAME + ' ' + D.USER_LNAME AS DentistName,
                    TH.TRANSC_DATE,
                    TH.TOTAL_AMOUNT,
                    TH.STATUS,
                    TH.PAYMENT_MODE,
                    TH.COMPLETED_DATE
                FROM TRANSACTION_HEADER TH
                JOIN APPOINTMENT A ON TH.APPT_ID = A.APPT_ID
                JOIN PATIENT P ON A.PATIENT_ID = P.PATIENT_ID
                JOIN DENTIST DT ON A.DENTIST_ID = DT.DENTIST_ID
                JOIN USER_PROFILE D ON DT.LOGIN_ID = D.LOGIN_ID
                WHERE TH.STATUS = 'COMPLETED'
                ORDER BY TH.COMPLETED_DATE DESC
            """)
        else:  # dentist
            cursor.execute("""
                SELECT 
                    TH.TRANSACTION_HEADER_ID,
                    P.PAT_FNAME + ' ' + P.PAT_LNAME AS PatientName,
                    TH.TRANSC_DATE,
                    TH.TOTAL_AMOUNT,
                    TH.STATUS,
                    TH.PAYMENT_MODE,
                    TH.COMPLETED_DATE
                FROM TRANSACTION_HEADER TH
                JOIN APPOINTMENT A ON TH.APPT_ID = A.APPT_ID
                JOIN PATIENT P ON A.PATIENT_ID = P.PATIENT_ID
                JOIN DENTIST D ON A.DENTIST_ID = D.DENTIST_ID
                WHERE D.LOGIN_ID = ? AND TH.STATUS = 'COMPLETED'
                ORDER BY TH.COMPLETED_DATE DESC
            """, (session['login_id'],))
        
        transactions = []
        columns = [column[0] for column in cursor.description]
        for row in cursor.fetchall():
            transactions.append(dict(zip(columns, row)))
        
        return jsonify(transactions)
            
    except Exception as e:
        print(f"Error fetching completed transactions: {str(e)}")
        return jsonify({'error': str(e)}), 500
        
    finally:
        if conn:
            conn.close()

@app.route('/api/transactions/create', methods=['POST'])
def create_transaction():
    if 'login_id' not in session or session.get('role') != 'dentist':
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        data = request.json
        patient_id = data.get('patient_id')
        treatment_ids = data.get('treatment_ids')
        appointment_id = data.get('appointment_id')
        
        if not patient_id or not treatment_ids or not appointment_id:
            return jsonify({'error': 'Patient ID, treatments, and appointment ID are required'}), 400
            
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get dentist ID from login ID
        login_id = session['login_id']
        cursor.execute("SELECT DENTIST_ID FROM DENTIST WHERE LOGIN_ID = ?", (login_id,))
        dentist_result = cursor.fetchone()
        
        if not dentist_result:
            return jsonify({"error": "Dentist not found"}), 404
            
        dentist_id = dentist_result[0]
        
        # Create transaction with PENDING status
        cursor.execute("""
            INSERT INTO TRANSACTION_HEADER (PATIENT_ID, DENTIST_ID, APPT_ID, TRANSC_DATE, TOTAL_AMOUNT, STATUS)
            OUTPUT INSERTED.TRANSACTION_HEADER_ID
            VALUES (?, ?, ?, GETDATE(), 0, 'PENDING')
        """, (patient_id, dentist_id, appointment_id))
        
        transaction_id = cursor.fetchone()[0]
        
        # Insert treatments and calculate total
        total_amount = 0
        for treatment_id in treatment_ids.split(','):
            cursor.execute("""
                INSERT INTO TRANSACTION_DETAIL (TRANSACTION_HEADER_ID, TREATMENT_ID)
                VALUES (?, ?)
            """, (transaction_id, treatment_id))
            
            # Get treatment price
            cursor.execute("SELECT TREATMENT_PRICE FROM TREATMENT WHERE TREATMENT_ID = ?", (treatment_id,))
            price = cursor.fetchone()[0]
            total_amount += float(price)
        
        # Update total amount
        cursor.execute("""
            UPDATE TRANSACTION_HEADER 
            SET TOTAL_AMOUNT = ?
            WHERE TRANSACTION_HEADER_ID = ?
        """, (total_amount, transaction_id))
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Transaction created successfully',
            'transaction_id': transaction_id,
            'total_amount': total_amount
        })
            
    except Exception as e:
        print(f"Error creating transaction: {str(e)}")
        return jsonify({'error': str(e)}), 500
        
    finally:
        if conn:
            conn.close()

@app.route('/api/transactions/complete', methods=['POST'])
def complete_transaction():
    if 'login_id' not in session or session.get('role') != 'staff':
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        data = request.json
        transaction_id = data.get('transaction_id')
        payment_mode = data.get('payment_mode')
        insurance_id = data.get('insurance_id')
        amount_paid = data.get('amount_paid')
        
        if not transaction_id or not payment_mode:
            return jsonify({'error': 'Transaction ID and payment mode are required'}), 400
            
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Update transaction status to COMPLETED
        cursor.execute("""
            UPDATE TRANSACTION_HEADER
            SET STATUS = 'COMPLETED',
                PAYMENT_MODE = ?,
                INSURANCE_ID = ?,
                AMOUNT_PAID = ?,
                COMPLETED_BY = ?,
                COMPLETED_DATE = GETDATE()
            WHERE TRANSACTION_HEADER_ID = ?
        """, (payment_mode, insurance_id, amount_paid, session['login_id'], transaction_id))
        
        # Update appointment status to COMPLETED
        cursor.execute("""
            UPDATE APPOINTMENT
            SET APPT_STATUS = 'COMPLETED'
            FROM APPOINTMENT A
            JOIN TRANSACTION_HEADER TH ON A.APPT_ID = TH.APPT_ID
            WHERE TH.TRANSACTION_HEADER_ID = ?
        """, (transaction_id,))
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Transaction completed successfully',
            'transaction_id': transaction_id
        })
            
    except Exception as e:
        print(f"Error completing transaction: {str(e)}")
        return jsonify({'error': str(e)}), 500
        
    finally:
        if conn:
            conn.close()

@app.route('/api/insurance', methods=['GET'])
def get_insurance_providers():
    if 'login_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT INSURANCE_ID, INSURANCE_COMPANY FROM INSURANCE")
        
        insurances = []
        columns = [column[0] for column in cursor.description]
        for row in cursor.fetchall():
            insurances.append(dict(zip(columns, row)))
            
        conn.close()
        return jsonify(insurances)
        
    except Exception as e:
        print(f"Error fetching insurance providers: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/transactions/<int:transaction_id>', methods=['GET'])
def get_transaction_details(transaction_id):
    if 'login_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("EXEC SP_GET_TRANSACTION_DETAILS ?", (transaction_id,))
        
        # First result set - basic info
        basic_info = {}
        if cursor.description:
            columns = [column[0] for column in cursor.description]
            row = cursor.fetchone()
            if row:
                basic_info = dict(zip(columns, row))
        
        # Second result set - treatments
        cursor.nextset()
        treatments = []
        if cursor.description:
            columns = [column[0] for column in cursor.description]
            for row in cursor.fetchall():
                treatments.append(dict(zip(columns, row)))
        
        # Third result set - insurance (if exists)
        cursor.nextset()
        insurance = None
        if cursor.description:
            columns = [column[0] for column in cursor.description]
            row = cursor.fetchone()
            if row:
                insurance = dict(zip(columns, row))
        
        conn.close()
        
        return jsonify({
            'success': True,
            'basic_info': basic_info,
            'treatments': treatments,
            'insurance': insurance
        })
    except Exception as e:
        print(f"Error fetching transaction details: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/logout')
def logout():
    session.clear()  
    return redirect(url_for('login'))

# Staff Transaction Routes
@app.route('/staff_transactions')
def staff_transactions():
    if 'user' in session and session.get('role') == 'staff':
        try:
            return render_template('staff_transactions.html', 
                                user_name=session.get('user'))
        except Exception as e:
            print(f"Error loading staff transactions page: {e}")
            return render_template('staff_transactions.html', 
                                user_name=session.get('user'),
                                error="Unable to load transactions page")
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)

