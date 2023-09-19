from flask import Flask, render_template, request, redirect, url_for, jsonify, abort
from flask_login import LoginManager, UserMixin, login_user, current_user
from functools import wraps
from flask import redirect, url_for, flash
import bcrypt
import pyotp
from flask_sqlalchemy import SQLAlchemy
from flask_uploads import UploadSet, configure_uploads, IMAGES
from flask import send_file
import pyexcel as pe
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib import colors
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import request, jsonify

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///pages.db'
db = SQLAlchemy(app)

photos = UploadSet("photos", IMAGES)
app.config["UPLOADED_PHOTOS_DEST"] = "uploads"
configure_uploads(app, photos)

app.config['SECRET_KEY'] = 'your_secret_key_here'

login_manager = LoginManager()
login_manager.init_app(app)

#user = UserLogin(username = "tyo", hashed_password = bcrypt.hashpw("sacremotdepass".encode('utf-8'), bcrypt.gensalt()), twofa_key = "AZERTYUIOPQSDFGHJKLMWXCVBNAZ", is_active=True)

class Page(db.Model):
    __tablename__ = 'page'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100))
    date = db.Column(db.String(20))
    image = db.Column(db.String(100))
    location = db.Column(db.String(100))
    max_participants = db.Column(db.Integer)
    cost = db.Column(db.Float)

class UserLogin(db.Model, UserMixin):
    __tablename__ = 'UserLogin'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20))
    hashed_password = db.Column(db.String(100))
    twofa_key = db.Column(db.String(100))
    is_active = db.Column(db.Boolean)

    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.hashed_password)
    
    def check_two_FA(self, twofa_code):
        totp = pyotp.TOTP(self.twofa_key)
        return twofa_code == totp.now() 
    
class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100))
    lastname = db.Column(db.String(100))
    firstname = db.Column(db.String(100))
    email = db.Column(db.String(100))
    phone = db.Column(db.String(8))

class Cotisants(db.Model):
    __tablename__ = 'cotisants'
    id = db.Column(db.Integer, primary_key=True)
    lastname = db.Column(db.String(100))
    firstname = db.Column(db.String(100))
    email = db.Column(db.String(100))
    phone = db.Column(db.String(8))

@login_manager.user_loader
def load_user(user_id):
    user = UserLogin.query.filter_by(id=user_id).first()
    if user:
        return user
    return None

def login_required(route_function):
    @wraps(route_function)
    def decorated_route(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return route_function(*args, **kwargs)
    return decorated_route

@app.route('/')
@login_required
def home():
    pages = Page.query.all()
    return render_template('home.html', pages=pages)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        twofa_code = request.form['twofa_code']
        user_to_login = UserLogin.query.filter_by(username=username).first()
        if user_to_login and user_to_login.check_password(password):
            if user_to_login.check_two_FA(twofa_code):
                login_user(user_to_login)
                return redirect('/')
            else:
                return 'Code 2FA incorrect'
        else:
            return 'Mauvais nom d\'utilisateur ou mot de passe'
    return render_template('login.html')

@app.route('/create_page', methods=['GET', 'POST'])
@login_required
def create_page():
    if request.method == 'POST':
        title = request.form.get('title')
        date = request.form.get('date')
        location = request.form.get('location')
        max_participants = request.form.get('max_participants')
        cost = request.form.get('cost')
        
        # Gérer l'envoi de l'image
        if 'image' in request.files:
            image = request.files['image']
            image.save(f"static/uploads/{image.filename}")
        else:
            image = None
        
        new_page = Page(title=title, date=date, image=image.filename if image else None, location=location, max_participants=max_participants, cost=cost)
        db.session.add(new_page)
        db.session.commit()
        return redirect('/')
    return render_template('create_page.html')

@app.route('/pages')
@login_required
def list_pages():
    pages = Page.query.all()
    return render_template('list_pages.html', pages=pages)

@app.route('/<int:page_id>')
@login_required
def page_details(page_id):
    page = Page.query.get(page_id)
    if page:
        users = User.query.filter_by(title=page.title).all()
        return render_template('page_details.html', page=page, users=users)
    else:
        return "Page non trouvée"
    
@app.route('/page/<string:title>', methods=['GET', 'POST'])
def page_title(title):
    page = Page.query.filter_by(title=title).first()
    if request.method == 'POST':
        lastname = request.form.get('lastname')
        firstname = request.form.get('firstname')
        email = request.form.get('email')
        phone = request.form.get('phone')
        if function_check_registration(email, phone, firstname, lastname, title)=="False":
            new_user = User(title=title, lastname=lastname, firstname=firstname, email=email, phone=phone)
            db.session.add(new_user)
            db.session.commit()
            return redirect('/thanks')
        else:
            return "Utilisateur déjà enregistré avec cette combinaison nom/prénom, cette adresse mail ou ce numéro de téléphone"
    if page:
        users = User.query.filter_by(id=page.id).all()
        if users:
            places = page.max_participants - len(users)
            return render_template('page_title.html', page=page, places=places)
    else:
        return "Page non trouvée"
    
@app.route('/add_user/<int:id_page>', methods=['POST'])
def add_user(id_page):
    page = Page.query.filter_by(id=id_page).first()
    try :
        title = page.title
        lastname = request.form.get('lastname')
        firstname = request.form.get('firstname')
        email = request.form.get('email')
        phone = request.form.get('phone')
        new_user = User(title=title, lastname=lastname, firstname=firstname, email=email, phone=phone)
        db.session.add(new_user)
        db.session.commit()
        return redirect(f'/{page.id}')
    except Exception as e:
        return f"Error in adding the user: {str(e)}"


@app.route('/delete_user', methods=['GET','POST'])
@login_required
def delete_user():
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        user = User.query.get(user_id)
        if user:
            db.session.delete(user)
            db.session.commit()
            return jsonify({"message": "User successfully deleted"})
        else:
            return jsonify({"message": "User not found"}), 404
    except Exception as e:
        return jsonify({"error": f"Error in the deletion of the user: {str(e)}"}), 500

@app.route('/update_user', methods=['POST'])
@login_required
def update_user():
    try:
        user_id = request.form.get('user_id')
        user = User.query.get(user_id)
        if user:
            # Update user data with the input values
            user.firstname = request.form.get('firstname')
            user.lastname = request.form.get('lastname')
            user.email = request.form.get('email')
            user.phone = request.form.get('phone')
            db.session.commit()
            return "User successfully updated"
        else:
            return "User not found"
    except Exception as e:
        return f"Error in updating the user: {str(e)}"


@app.route('/thanks', methods=['GET', 'POST'])
def thanks():
    return "Thanks for your inscription, see you soon :)"    

@app.route('/download_users_ods/<int:page_id>')
def download_users_ods(page_id):
    page = Page.query.filter_by(id=page_id).first()
    if not page:
        return "Page not found", 404
    users = User.query.filter_by(title=page.title).all()
    user_data = [['Index', 'Nom', 'Prénom', 'Email', 'Telephone']]

    for i, user in enumerate(users, start=1):
        user_row = [i, user.lastname or '', user.firstname or '', user.email or '', user.phone or '']
        user_data.append(user_row)

    sheet = pe.Sheet(user_data)
    output = BytesIO()
    sheet.save_to_memory("ods", output)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name=f'users_{page_id}.ods')

@app.route('/download_users_pdf/<int:page_id>')
@login_required
def download_users_pdf(page_id):
    page = Page.query.filter_by(id=page_id).first()
    if not page:
        return "Page not found", 404
    users = User.query.filter_by(title=page.title).all()
    user_data = [['Index', 'Nom', 'Prénom', 'Email', 'Telephone']]

    for i, user in enumerate(users, start=1):
        user_row = [i, user.lastname or '', user.firstname or '', user.email or '', user.phone or '']
        user_data.append(user_row)
    pdf_file = BytesIO()
    doc = SimpleDocTemplate(pdf_file, pagesize=letter)
    table = Table(user_data)
    style = TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                        ('GRID', (0, 0), (-1, -1), 1, colors.black)])

    table.setStyle(style)
    elements = [table]
    doc.build(elements)
    pdf_file.seek(0) 
    return send_file(pdf_file, as_attachment=True, download_name=f'users_{page_id}.pdf')

@app.route('/edit_cotisants', methods=['GET'])
@login_required
def edit_cotisants():
    cotisants = Cotisants.query.all()
    return render_template('cotisants.html', cotisants=cotisants)

@app.route('/add_cotisant', methods=['POST'])
@login_required
def add_cotisant():
    lastname = request.form.get('lastname')
    firstname = request.form.get('firstname')
    email = request.form.get('email')
    phone = request.form.get('phone')
    if cotisant_doesnt_exists(mail=email, phone=phone):
        cotisant = Cotisants(lastname=lastname, firstname=firstname, email=email, phone=phone)
        db.session.add(cotisant)
        db.session.commit()
        return redirect('/edit_cotisants')
    else:
        return "Cotisant mail or phone number already used", 400
 
@app.route('/update_cotisant', methods=['POST'])
@login_required
def update_cotisant():
    try:
        cotisant_id = request.form.get('cotisant_id')
        cotisant = Cotisants.query.get(cotisant_id)
        if cotisant:
            cotisant.firstname = request.form.get('firstname').lower()
            cotisant.lastname = request.form.get('lastname').lower()
            cotisant.email = request.form.get('email').lower()
            cotisant.phone = request.form.get('phone').lower()
            if cotisant_doesnt_exists(cotisant_id, cotisant.email, cotisant.phone):
                db.session.commit()
                return "Cotisant successfully updated", 200
            else:
                abort(400, "Cotisant mail or phone number already used")
        else:
            abort(404, "Cotisant not found")
    except Exception as e:
        abort(400, f"Error in updating the cotisant: {str(e)}")
    
@app.route('/delete_cotisant', methods=['GET','POST'])
@login_required
def delete_cotisant():
    try:
        data = request.get_json()
        cotisant_id = data.get('cotisant_id')
        cotisant = Cotisants.query.get(cotisant_id)
        if cotisant:
            db.session.delete(cotisant)
            db.session.commit()
            return jsonify({"message": "Cotisant successfully deleted"})
        else:
            return jsonify({"message": "Cotisant not found"}), 404
    except Exception as e:
        return jsonify({"error": f"Error in the deletion of the cotisant: {str(e)}"}), 500

@app.route('/check_cotisant', methods=['POST'])
def check_cotisant():
    try:
        data = request.get_json()
        email = data.get('email')
        phone = data.get('phone')
        cotisants = Cotisants.query.all()
        for cotisant in cotisants:
            cotisant_mail = cotisant.email.lower()
            cotisant_phone = cotisant.phone.lower()
            if cotisant_mail== email.lower() or cotisant_phone == phone.lower():
                return "Vous êtes cotisant, la séance est gratuite pour vous! Merci de nous soutenir :)"
        else:
            return "Vous n'êtes pas cotisant, la seance sera payante (voir prix en haut de la page). Paiement sur place ou dès maintenant par Lyf au 0768162920"
    except Exception as e:
        return jsonify({"error": f"Error in cotisant status check: {str(e)}"}), 500
    

@app.route('/check_cotisant_backend', methods=['POST'])
def check_cotisant_backend():
    try:
        data = request.get_json()
        email = data.get('email')
        phone = data.get('phone')
        cotisants = Cotisants.query.all()
        for cotisant in cotisants:
            cotisant_mail = cotisant.email.lower()
            cotisant_phone = cotisant.phone.lower()
            if cotisant_mail== email.lower() or cotisant_phone == phone.lower():
                return "Oui"
        else:
            return "Non"
    except Exception as e:
        return jsonify({"error": f"Error in cotisant status check: {str(e)}"}), 500

@app.route('/check_registration', methods=['POST'])
def check_registration():
    data = request.get_json()
    email = data.get('email')
    phone = data.get('phone')
    firstname = data.get('firstname')
    lastname = data.get('lastname')
    title = data.get('title')
    return function_check_registration(email, phone, firstname, lastname, title)

@app.route('/get_user_list/<int:page_id>', methods=['GET'])
@login_required
def get_user_list(page_id):
    try:
        page = Page.query.get(page_id)
        if page:
            users = User.query.filter_by(title=page.title).all()
            serialized_users = [user_to_dict(user) for user in users]
            return jsonify(serialized_users)
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/send_user_list_email', methods=['POST'])
@login_required
def send_user_list_email():
    try:
        data = request.get_json()
        userText = data.get('userText')
        # Configurez les informations de votre serveur SMTP
        smtp_server = 'smtp.gmail.com'
        smtp_port = 587
        smtp_username = 'thebaultyoann56@gmail.com'
        smtp_password = 'vdhc gwru jmeb nnho'
        sender_email = 'thebaultyoann56@example.com'
        recipient_email = 'thebaultyoann@gmail.com'

        # Créez un objet MIMEMultipart pour l'e-mail
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = 'Liste des Participants'

        # Ajoutez le texte de la liste des participants à l'e-mail
        msg.attach(MIMEText(userText, 'plain'))

        # Établissez une connexion SMTP sécurisée et envoyez l'e-mail
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(smtp_username, smtp_password)
        server.sendmail(sender_email, recipient_email, msg.as_string())
        server.quit()

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)})


def function_check_registration(email, phone, firstname, lastname, title):
    users = User.query.filter_by(title=title).all()
    try:
        for user in users:
            user_mail = user.email.lower()
            user_phone = user.phone.lower()
            user_firstname = user.firstname.lower()
            user_lastname = user.lastname.lower()
            if user_mail== email.lower() or user_phone == phone.lower() or (user_firstname==firstname.lower() and user_lastname==lastname.lower()) or (user_firstname==lastname.lower() and user_lastname==firstname.lower()):
                return "True"
        else:
            return "False"
    except Exception as e:
        return jsonify({"error": f"Error in cotisant status check: {str(e)}"}), 500

def cotisant_doesnt_exists(mail, phone, id=0):
    cotisants = Cotisants.query.all()
    for cotisant in cotisants:
        if cotisant.id != id:
            if cotisant.phone==phone or cotisant.email==mail:
                return False
    return True

def user_to_dict(user):
    return {
        'id': user.id,
        'lastname': user.lastname,
        'firstname': user.firstname,
        'email': user.email,
        'phone': user.phone,
    }

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
