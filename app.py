import pyodbc
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify

app = Flask(__name__)
app.secret_key = '@b1@ck91nk_1l@73u'


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

            return redirect(url_for('dashboard'))  
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

@app.route('/dashboard')
def dashboard():
    if 'user' in session:
        user_name = f"{session.get('user', '')}"
        user_role = session.get('role', '')
        
        
        if user_role == 'admin':
            return render_template('dashboard.html', user_name=user_name)
        else:
            
            return render_template('unauthorized.html')
    else:
        return redirect(url_for('login')) 

@app.route('/user_management')
def user_management():
    if 'user' in session and session.get('role') == 'admin':
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Get dentists
            cursor.execute("""
                SELECT u.LOGIN_ID, u.USER_LNAME, u.USER_FNAME, u.PHO_NUM, u.USERNAME, 
                       u.USER_IMG, d.DENTIST_SPEC, u.ISACTIVE
                FROM USER_PROFILE u
                JOIN DENTIST d ON u.LOGIN_ID = d.LOGIN_ID
                WHERE u.USER_ROLE = 'dentist'
                ORDER BY u.USER_LNAME
            """)
            dentists = cursor.fetchall()
            
            # Get staff
            cursor.execute("""
                SELECT LOGIN_ID, USER_LNAME, USER_FNAME, PHO_NUM, USERNAME, 
                       USER_IMG, ISACTIVE
                FROM USER_PROFILE
                WHERE USER_ROLE = 'staff'
                ORDER BY USER_LNAME
            """)
            staff = cursor.fetchall()
            
            conn.close()
            
            return render_template('user_management.html', 
                                  dentists=dentists, 
                                  staff=staff, 
                                  user_name=session.get('user'))
        except Exception as e:
            print(f"Error fetching user data: {e}")
            return render_template('user_management.html', 
                                  error="Unable to fetch user data", 
                                  user_name=session.get('user'))
    else:
        return redirect(url_for('login'))

@app.route('/add_user', methods=['POST'])
def add_user():
    if 'user' in session and session.get('role') == 'admin':
        try:
            # Get form data
            first_name = request.form.get('firstName')
            last_name = request.form.get('lastName')
            contact_number = request.form.get('contactNumber')
            email = request.form.get('emailAddress')
            user_role = request.form.get('userRole')
            specialization = request.form.get('specialization') if user_role == 'dentist' else None
            
            # Handle profile image if provided
            profile_img = None
            if 'profileImage' in request.files:
                file = request.files['profileImage']
                if file.filename != '':
                    # Save the file and get the path/URL
                    filename = secure_filename(file.filename)
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    profile_img = f"/static/uploads/{filename}"
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Use stored procedure to add user
            if user_role == 'dentist':
                cursor.execute("""
                    EXEC SP_ADD_DENTIST ?, ?, ?, ?, ?, ?
                """, (first_name, last_name, contact_number, email, specialization, profile_img))
            else:
                cursor.execute("""
                    EXEC SP_ADD_STAFF ?, ?, ?, ?, ?
                """, (first_name, last_name, contact_number, email, profile_img))
            
            conn.commit()
            conn.close()
            
            flash('User added successfully', 'success')
            return redirect(url_for('user_management'))
            
        except Exception as e:
            print(f"Error adding user: {e}")
            flash('Error adding user', 'danger')
            return redirect(url_for('user_management'))
    else:
        return redirect(url_for('login'))

@app.route('/update_user/<int:user_id>', methods=['POST'])
def update_user(user_id):
    if 'user' in session and session.get('role') == 'admin':
        try:
            # Get form data
            email = request.form.get('emailAddress')
            contact_number = request.form.get('contactNumber')
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE USER_PROFILE
                SET PHO_NUM = ?, MODIFIED_BY = ?
                WHERE LOGIN_ID = ?
            """, (contact_number, session.get('user'), user_id))
            
            conn.commit()
            conn.close()
            
            flash('User updated successfully', 'success')
            return redirect(url_for('user_management'))
            
        except Exception as e:
            print(f"Error updating user: {e}")
            flash('Error updating user', 'danger')
            return redirect(url_for('user_management'))
    else:
        return redirect(url_for('login'))

@app.route('/toggle_user_status/<int:user_id>')
def toggle_user_status(user_id):
    if 'user' in session and session.get('role') == 'admin':
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Get current status
            cursor.execute("SELECT ISACTIVE FROM USER_PROFILE WHERE LOGIN_ID = ?", (user_id,))
            current_status = cursor.fetchone()[0]
            
            # Toggle status
            new_status = not current_status
            
            cursor.execute("""
                UPDATE USER_PROFILE
                SET ISACTIVE = ?, MODIFIED_BY = ?
                WHERE LOGIN_ID = ?
            """, (new_status, session.get('user'), user_id))
            
            conn.commit()
            conn.close()
            
            status_message = 'activated' if new_status else 'deactivated'
            flash(f'User {status_message} successfully', 'success')
            
            return redirect(url_for('user_management'))
            
        except Exception as e:
            print(f"Error toggling user status: {e}")
            flash('Error updating user status', 'danger')
            return redirect(url_for('user_management'))
    else:
        return redirect(url_for('login')) 


@app.route('/logout')
def logout():
    session.clear()  
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)

