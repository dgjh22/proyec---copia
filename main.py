from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Configuración de la base de datos
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = '12345'
app.config['MYSQL_DB'] = 'GestionE'

mysql = MySQL(app)

# Configuración de Flask-Mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = 'danaj6038@gmail.com'
app.config['MAIL_PASSWORD'] = '1082@@Dana2003'
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True

mail = Mail(app)

# Agregar organizadores fijos
def add_fixed_organizers():
    organizers = [
        
        ('Dana Jimenez', 'danaj6038@gmail.com', generate_password_hash('123'), 'organizer'),
        
    ]
    
    with mysql.connection.cursor() as cur:
        for name, email, hashed_password, role in organizers:
            cur.execute("SELECT * FROM Users WHERE email = %s", (email,))
            if cur.fetchone() is None:
                try:
                    cur.execute("INSERT INTO Users (name, email, password, role) VALUES (%s, %s, %s, %s)", 
                                (name, email, hashed_password, role))
                except Exception as e:
                    print(f'Error al insertar {name}: {e}')
        mysql.connection.commit()

with app.app_context():
    add_fixed_organizers()

@app.route('/')
def index():
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    cur = mysql.connection.cursor()
    cur.execute("SELECT COUNT(*) FROM Users")
    user_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM Events")
    event_count = cur.fetchone()[0]

    cur.close()
    return render_template('dashboard.html', user_count=user_count, event_count=event_count)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']
        hashed_password = generate_password_hash(password)

        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO Users (name, email, password, role) VALUES (%s, %s, %s, %s)", 
                    (name, email, hashed_password, role))
        mysql.connection.commit()
        cur.close()
        flash('Registro exitoso, ahora puedes iniciar sesión.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        print(f"Email: {email}")  # Imprimir el email ingresado
        print(f"Password: {password}")  # Imprimir la contraseña ingresada
        
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM Users WHERE email = %s", (email,))
        user = cur.fetchone()
        cur.close()

        print(f"User: {user}")  # Imprimir el usuario recuperado

        if user and check_password_hash(user[3], password):
            session['user_id'] = user[0]
            session['user_role'] = user[4]
            session['user_email'] = user[2]
            return redirect(url_for('events'))

        flash('Credenciales incorrectas, intenta nuevamente.', 'danger')

    return render_template('login.html')


@app.route('/events')
def events():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM Events")
    events = cur.fetchall()
    cur.close()
    
    if session.get('user_role') == 'organizer':
        return render_template('events.html', events=events)
    else:
        return render_template('events_user.html', events=events)

@app.route('/create_event', methods=['GET', 'POST'])
def create_event():
    if session['user_role'] != 'organizer':
        flash('No tienes permisos para crear eventos.', 'danger')
        return redirect(url_for('events'))

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        date = request.form['date']
        time = request.form['time']
        location = request.form['location']
        capacity = request.form['capacity']
        organizer_id = session['user_id']

        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO Events (title, description, date, time, location, capacity, organizer_id) VALUES (%s, %s, %s, %s, %s, %s, %s)", 
                    (title, description, date, time, location, capacity, organizer_id))
        mysql.connection.commit()
        cur.close()
        flash('Evento creado exitosamente.', 'success')
        return redirect(url_for('events'))

    return render_template('create_event.html')

@app.route('/events/<int:event_id>/register', methods=['POST'])
def register_for_event(event_id):
    if 'user_id' not in session:
        flash('Necesitas iniciar sesión para registrarte en un evento.', 'danger')
        return redirect(url_for('login'))

    attendee_id = session['user_id']

    try:
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO EventRegistrations (event_id, attendee_id) VALUES (%s, %s)", 
                    (event_id, attendee_id))
        mysql.connection.commit()
        
        cur.execute("SELECT title FROM Events WHERE id = %s", (event_id,))
        event = cur.fetchone()
        cur.close()

        send_notification(session['user_email'], event[0])  
        return redirect(url_for('registration_success', event_title=event[0]))

    except Exception as e:
        flash(f'Error al registrarse en el evento: {e}', 'danger')
        return redirect(url_for('events'))

@app.route('/registration_success')
def registration_success():
    event_title = request.args.get('event_title')
    return render_template('registration_success.html', event_title=event_title)

def send_notification(email, event_title):
    msg = Message('Te has registrado en un evento',
                  sender='danaj6038@gmail.com',
                  recipients=[email])
    msg.body = f'Has sido registrado en el evento: {event_title}'
    mail.send(msg)

@app.route('/events/<int:event_id>/attendees')
def event_attendees(event_id):
    if session['user_role'] != 'organizer':
        flash('No tienes permisos para ver los asistentes.', 'danger')
        return redirect(url_for('events'))

    if 'user_id' not in session:
        flash('Necesitas iniciar sesión para ver los asistentes.', 'danger')
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT Users.name FROM EventRegistrations
        JOIN Users ON EventRegistrations.attendee_id = Users.id
        WHERE event_id = %s
    """, (event_id,))
    attendees = cur.fetchall()
    cur.close()

    return render_template('attendees.html', attendees=attendees)

@app.route('/add_organizer', methods=['GET', 'POST'])
def add_organizer():
    if session['user_role'] != 'organizer':
        flash('No tienes permisos para añadir organizadores.', 'danger')
        return redirect(url_for('events'))

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        hashed_password = generate_password_hash(password)

        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO Users (name, email, password, role) VALUES (%s, %s, %s, 'organizer')", 
                    (name, email, hashed_password))
        mysql.connection.commit()
        cur.close()
        flash('Organizador añadido exitosamente.', 'success')
        return redirect(url_for('add_organizer'))

    return render_template('add_organizer.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Has cerrado sesión.', 'success')
    return redirect(url_for('index'))

@app.route('/organizer_dashboard')
def organizer_dashboard():
    return render_template('organizer_dashboard.html')

@app.route('/organizer_events')
def organizer_events():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM Events WHERE organizer_id = %s", (session['user_id'],))
    events = cur.fetchall()
    cur.close()
    return render_template('organizer_events.html', events=events)

@app.route('/organizer_events/<int:event_id>/attendees')
def organizer_event_attendees(event_id):
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT Users.name FROM EventRegistrations
        JOIN Users ON EventRegistrations.attendee_id = Users.id
        WHERE event_id = %s
    """, (event_id,))
    attendees = cur.fetchall()
    cur.close()

    return render_template('attendees.html', attendees=attendees)

if __name__ == '__main__':
    app.run(debug=True)
