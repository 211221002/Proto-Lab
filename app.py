from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from pymongo import MongoClient
import bcrypt
from bson import ObjectId
from werkzeug.utils import secure_filename
import os
from os.path import join, dirname
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify
from pymongo import MongoClient

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)


app = Flask(__name__)
app.secret_key = "rahasia"

client = MongoClient("mongodb://test:test@ac-owhiyhy-shard-00-00.6znvghk.mongodb.net:27017,ac-owhiyhy-shard-00-01.6znvghk.mongodb.net:27017,ac-owhiyhy-shard-00-02.6znvghk.mongodb.net:27017/?ssl=true&replicaSet=atlas-10141m-shard-0&authSource=admin&retryWrites=true&w=majority")
MONGODB_URI = os.environ.get("MONGODB_URI")
DB_NAME =  os.environ.get("DB_NAME")
db = client["Cluster0"]
users_collection = db["user"]
equipment_collection = db["equipment"]
borrowed_equipment_collection = db["borrowed_equipment"]
projects_collection = db['project']
mahasiswa_collection = db["mahasiswa"]

# untuk menyimpan data user di setiap halaman


@app.context_processor
def inject_user_data():
    user_data = None
    if 'user' in session:
        user_id = ObjectId(session['user']['_id'])
        user_data = users_collection.find_one({'_id': user_id})
    return dict(user_data=user_data)


@app.route('/')
def index():
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password'].encode('utf-8')

        user_data = users_collection.find_one({'email': email})

        if user_data and bcrypt.checkpw(password, user_data['password']):
            session['user'] = {
                '_id': str(user_data['_id']),
                'name': user_data['name'],
                'email': user_data['email'],
                'role': user_data['role']
            }
            return redirect(url_for('home'))
        else:
            return render_template('login.html', error='Invalid email or password')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password'].encode('utf-8')
        role = request.form['role']
        photo = request.files['photo'] if 'photo' in request.files else None
        default_bio = "This is a default bio."

        existing_user = users_collection.find_one(
            {'$or': [{'name': name}, {'email': email}]})

        if existing_user is None:
            hashed_password = bcrypt.hashpw(password, bcrypt.gensalt())

            # untu foto tapi masih tidak bisa
            photo_data = None
            if photo:
                photo_data = photo.read()

            # untuk insert user
            users_collection.insert_one({
                'name': name,
                'email': email,
                'password': hashed_password,
                'role': role,
                'photo': photo_data,  # masih tidak bisa
                'bio': default_bio
            })

            if role == 'mahasiswa':
                # untuk insert mahasiswa
                mahasiswa_collection.insert_one({
                    'name': name,
                    'email': email,
                    'password': hashed_password,
                    'role': role,
                    'photo': photo_data,  # masih tidak bisa
                    'bio': default_bio
                })

            return redirect(url_for('login'))
        else:
            return render_template('register.html', error='Name or email already exists')

    return render_template('register.html')


@app.route('/home')
def home():
    if 'user' in session:
        user_id = ObjectId(session['user']['_id'])
        user_data = users_collection.find_one({'_id': user_id})

        # Fetch projects untuk user saat ini
        projects_data = list(projects_collection.find({}))

        return render_template('home.html', user_data=user_data, projects_data=projects_data)
    else:
        return redirect(url_for('login'))


@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))


@app.route('/profile')
def profile():
    if 'user' in session:
        current_user = session['user']
        return render_template('profile.html', user=current_user)
    else:
        return redirect(url_for('login'))


@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'user' in session:
        user_id = ObjectId(session['user']['_id'])
        success_flag = False

        if request.method == 'POST':
            new_name = request.form['name']
            new_email = request.form['email']
            new_role = request.form['role']
            new_bio = request.form['bio']

            existing_photo = request.form.get('existing_photo', None)

            new_photo = request.files['photo'] if 'photo' in request.files else None

            # proses upload file
            if new_photo:
                # menyimpan ke folder static
                filename = secure_filename(new_photo.filename)
                new_photo.save(f'static/{filename}')

                # upload ke field
                users_collection.update_one(
                    {'_id': user_id}, {'$set': {'photo': filename}})

            # update collection user
            result = users_collection.update_one(
                {'_id': user_id},
                {'$set': {'name': new_name, 'email': new_email,
                          'role': new_role, 'bio': new_bio}}
            )

            if result.modified_count > 0:
                success_flag = True

                # Perbarui data pengguna di sesi tersebut
                session['user']['name'] = new_name
                session['user']['email'] = new_email
                session['user']['role'] = new_role
                session['user']['bio'] = new_bio

        user_data = users_collection.find_one({'_id': user_id})
        return render_template('edit_profile.html', user=user_data, success_flag=success_flag)
    else:
        return redirect(url_for('login'))


@app.route('/get_user_data')
def get_user_data():
    if 'user' in session:
        user_id = ObjectId(session['user']['_id'])
        user_data = users_collection.find_one({'_id': user_id})
        return jsonify({'name': user_data['name'], 'email': user_data['email'], 'role': user_data['role']})
    else:
        return jsonify({'error': 'User not logged in'})


@app.route('/borrow_equipment', methods=['GET', 'POST'])
def borrow_equipment_page():
    # Fetch equipment data
    equipment_data = list(equipment_collection.find({}, {'_id': 0}))

    # Fetch semua borrowed equipment data
    borrowed_equipment_data = list(borrowed_equipment_collection.find())

    if request.method == 'POST':
        # Form untuk pinjam alat
        equipment_name = request.form['equipment']
        requested_quantity = int(request.form['quantity'])
        user_id = ObjectId(session['user']['_id'])
        user_data = users_collection.find_one({'_id': user_id})
        user_name = user_data['name']

        # Fetch ketersediaan quantity dari collection equipment
        available_quantity_data = equipment_collection.find_one(
            {'name': equipment_name}, {'_id': 0, 'quantity': 1})
        available_quantity = available_quantity_data['quantity'] if available_quantity_data else 0

        # mengecek apa quantity masih ada
        if requested_quantity > available_quantity:
            flash('Not enough quantity available for borrowing.', 'danger')
        else:
            # Update data quantity di equipment collection agar dapat turun untuk quantity
            equipment_collection.update_one({'name': equipment_name}, {
                                            '$inc': {'quantity': -requested_quantity}})

            # menyimpan peralatan yang dipinjam ke database
            borrowed_equipment_collection.insert_one({
                'user_id': user_id,
                'user_name': user_name,
                'equipment_name': equipment_name,
                'quantity': requested_quantity
            })

            flash('Borrow successful!', 'success')

    return render_template('borrow_equipment.html', equipment=equipment_data, borrowed_equipment=borrowed_equipment_data)


@app.route('/newproject', methods=['GET', 'POST'])
def newproject():
    if 'user' in session:
        users_data = list(users_collection.find({'role': {'$in': ['peneliti', 'mahasiswa']}}, {'_id': 0, 'name': 1}))

        if request.method == 'POST':
            project_name = request.form['project_name']

            existing_project = projects_collection.find_one(
                {'project_name': project_name})

            if existing_project:
                flash(
                    'Project with this name already exists. Please choose a different name.', 'danger')
            else:
                project_description = request.form['project_description']
                selected_members_data = request.form['selectedMembersData']

                # Print untuk check member
                print(f"Selected Members Data: {selected_members_data}")

                selected_members_list = [item.split(
                    ',') for item in selected_members_data.split(';') if item]

                # menyimpan data member ke database
                project_members = []
                for member_data in selected_members_list:
                    member_name, member_role = member_data
                    project_members.append(
                        {'name': member_name, 'role': member_role})

                # Insert project ke database
                project_id = projects_collection.insert_one({
                    'project_name': project_name,
                    'project_description': project_description,
                    'members': project_members
                }).inserted_id

                # Print data
                print(f"Project ID: {project_id}")
                print(f"Project Members: {project_members}")

                flash('Project created successfully!', 'success')

        return render_template('newproject.html', users=users_data)
    else:
        return redirect(url_for('login'))


@app.route('/join_project', methods=['POST'])
def join_project():
    if 'user' in session:
        user_id = ObjectId(session['user']['_id'])
        user_data = users_collection.find_one({'_id': user_id})
        user_name = user_data['name']

        project_id = ObjectId(request.form['project_id'])
        selected_role = request.form['role']

        # update project dengan member baru
        projects_collection.update_one(
            {'_id': project_id},
            {'$push': {'members': {'name': user_name, 'role': selected_role}}}
        )

        flash('Joined the project successfully!', 'success')
        return redirect(url_for('home'))
    else:
        return redirect(url_for('login'))


@app.route('/delete_project', methods=['POST'])
def delete_project():
    if 'user' in session and session['user']['role'] == 'admin':
        project_id = ObjectId(request.form['project_id'])

        # menghapus project dari collection
        projects_collection.delete_one({'_id': project_id})

        flash('Project deleted successfully!', 'success')
        return redirect(url_for('home'))
    else:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('home'))


@app.route('/add_equipment', methods=['GET', 'POST'])
def add_equipment():
    if 'user' in session:
        if request.method == 'POST':
            equipment_name = request.form['equipment_name']
            equipment_quantity = int(request.form['equipment_quantity'])

            # Check if equipment already exists
            existing_equipment = equipment_collection.find_one(
                {'name': equipment_name})

            if existing_equipment:
                flash(
                    'Equipment with this name already exists. Please choose a different name.', 'danger')
            else:
                # Insert equipment to the database
                equipment_collection.insert_one({
                    'name': equipment_name,
                    'quantity': equipment_quantity
                })

                flash('Equipment added successfully!', 'success')

        return render_template('add_equipment.html')
    else:
        return redirect(url_for('login'))


if __name__ == "__main__":
    app.run("0.0.0.0", port=5000, debug=True)
