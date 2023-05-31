import json
import os
from datetime import datetime

from flask import Flask, render_template, request, jsonify, flash, redirect, make_response, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from bs4 import BeautifulSoup
import boto3


application = Flask(__name__, template_folder="Templates")

# AWS production uri
application.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://Faateh:Faateh123@projects-db.cwvdgyt4btit.us-east-1.rds.amazonaws.com:5432/projecttool_db'

# development uri
#application.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:Faateh123@localhost:5432/projects_test'
application.config['SECRET_KEY'] = 'secret!'
application.config['SQLALCHEMY_ECHO'] = True
db = SQLAlchemy(application)
login_manager = LoginManager(application)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'
s3 = boto3.client('s3', region_name='us-east-1')

class Projects(db.Model):
    __tablename__ = 'projects'
    project_id = db.Column(db.String(50), primary_key=True)
    project_year = db.Column(db.String(50))
    country = db.Column(db.String(50))
    status = db.Column(db.String(255))
    start_date = db.Column(db.String(50))
    end_date = db.Column(db.String(50))
    result = db.Column(db.String(500))
    notes = db.Column(db.String(1000))
    last_updated = db.Column(db.String(500))

class notes(db.Model):
    __tablename__ = 'notes'
    id = db.Column(db.Integer, primary_key=True)
    note = db.Column(db.String(5000))
    project_id = db.Column(db.String(100))
    timestamp = db.Column(db.String(100))
    user = db.Column(db.String(100))
    filename = db.Column(db.String(500))
    s3_url = db.Column(db.String(500))

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    username = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(100))
#
# with app.app_context():
#     # Create the tables
#     db.create_all()


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@application.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out!', 'success')
    return redirect(url_for('login'))

def generate_next_trial_id():
    current_year = datetime.now().year
    last_two_digits = current_year % 100
    latest_ticket = Projects.query.order_by(Projects.project_id.desc()).first()

    if latest_ticket:
        latest_year = int(latest_ticket.project_id.split("-")[2])
        counter = int(latest_ticket.project_id.split("-")[3])

        if latest_year == last_two_digits:
            counter += 1
        else:
            counter = 1
    else:
        counter = 1

    counter = str(counter).zfill(3)
    return f"MAT-PRJ-{last_two_digits}-{counter}"



@application.route('/', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        logout_user()
        print("logged in")
        return redirect(url_for('login'))
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        # print(user.id)
        if user and user.password == password:
            login_user(user)
            return redirect(url_for('user_home'))
        else:
            print("error")
            flash('Login unsuccessful. Please check your username and password.', 'danger')
    # return render_template("home.html")
    response = make_response(render_template("login.html"))
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


@application.route("/register", methods=['GET', 'POST'])
def register():
    if request.method == "POST":
        username = request.form['name']
        email = request.form['email']
        password = request.form['password']
        confirm = request.form['confirm-password']
        if " " in username:
            username_parts = username.split(" ")
            username = username_parts[0]
        if password == confirm:
            user = User(
                username=username,
                email=email,
                password=password
            )
            db.session.add(user)
            db.session.commit()
            flash('You have successfully created an account!')
            return redirect(url_for('login'))
        else:
            flash('Registration unsuccessful. Passwords Do Not Match!', 'danger')
    return render_template("register.html")




@application.route('/user-home', methods=['GET', 'POST'])
@login_required
def user_home():
    current = current_user._get_current_object()
    return render_template("home.html", user=current)

@application.route('/projects', methods=['GET', 'POST'])
def projects():
    rows = Projects.query.all()
    return render_template("projects.html", rows=rows)

@application.route('/new-project', methods=['GET', 'POST'])
def new_project():
    if request.method == "POST":
        # operator = request.form.get("operator")
        country = request.form.get("country")
        # rep_company = request.form.get("rep-company")
        # venue = request.form.get("venue")
        selected_date = request.form.get("date")
        parsed_date = datetime.strptime(selected_date, "%Y-%m-%d")
        formatted_date = parsed_date.strftime("%m/%d/%Y")
        project = Projects(
            project_id=generate_next_trial_id(),
            project_year=datetime.now().year,
            country=country,
            # operator=operator,
            # rep_company=rep_company,
            # venue=venue,
            start_date=formatted_date
        )
        db.session.add(project)
        db.session.commit()
        print("sucessfully added new trial")
    return render_template("new-project.html")

@application.route("/project-activity/<id>", methods=['GET', 'POST'])
# @login_required
def project_activity(id):
    current = current_user._get_current_object()
    results = notes.query.filter_by(project_id=id).order_by(notes.id.desc()).all()
    return render_template("project-activity.html", notes=results, project_number=id, user=current)

@application.route("/save-activity", methods=['GET', 'POST'])
# @login_required
def save_activity():
    current = current_user._get_current_object()
    if request.method == "POST":
        note_data = request.get_json()
        print(note_data)
        note_text = note_data.get('note')
        project_id = note_data.get('project-id')
        timestamp = note_data.get('timestamp')
        note = notes(
            note=note_text,
            project_id=project_id,
            timestamp=timestamp,
            user=current.username
        )
        db.session.add(note)
        db.session.commit()
    return jsonify({'status': 'success'})


@application.route("/update-project", methods=['GET', 'POST'])
# @login_required
def update_ticket():
    if request.method == "POST":
        data = request.json
        print(data)
        ticket_id = data.get('id')
        field = data.get('field')
        value = data.get('value')
        soup = BeautifulSoup(value, 'html.parser')
        cleaned_value = soup.get_text()
        print(cleaned_value)
        ticket = Projects.query.get(ticket_id)
        setattr(ticket, field, cleaned_value)
        db.session.commit()
    return jsonify({'status': 'success'})

@application.route('/upload-file', methods=['GET', 'POST'])
@login_required
def upload_file():
    if request.method == "POST":
        project_id = request.form.get('project-id')
        timestamp = request.form.get('date')
        file = request.files['file']
        current = current_user._get_current_object()
        note = notes(
            project_id=project_id,
            timestamp=timestamp,
            user=current.username,
            s3_url=f'https://projectstool-bucket.s3.amazonaws.com/{file.filename}',
            filename=file.filename
        )
        db.session.add(note)
        db.session.commit()
        extension = os.path.splitext(file.filename)[1].lower()
        print(extension)
        if extension == ".jpg" or extension == ".png":
            content_type = "image/png"
        elif extension == ".pdf":
            content_type = "application/pdf"
        else:
            content_type = None
        if content_type:
            print(content_type)
            s3.put_object(
                Bucket='projectstool-bucket',
                Key=file.filename,
                Body=file,
                ACL='public-read',
                ContentType=content_type,
                ContentDisposition='inline'
            )
        else:
            s3.put_object(
                Bucket='projectstool-bucket',
                Key=file.filename,
                Body=file,
                ACL='public-read'
            )
    response = {"status": "success", "message": "Activity file upload"}
    json_response = json.dumps(response)
    return json_response







if __name__ == '__main__':
    application.run(debug=True)


