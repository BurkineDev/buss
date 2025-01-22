from flask import Flask, request, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from dotenv import load_dotenv
import os
import qrcode
import io

# Charger les variables d'environnement
load_dotenv()

# Initialisation de l'application Flask
app = Flask(__name__)

# Configurations Flask
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bus_app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')  # Récupérer la clé secrète

# Initialisation des extensions
db = SQLAlchemy(app)
jwt = JWTManager(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    plan = db.Column(db.String(50), nullable=False)  # Example: 'Weekly', 'Monthly', 'Yearly'
    valid_until = db.Column(db.String(50), nullable=False)  # Example: '2025-12-31'

    user = db.relationship('User', backref='subscriptions')

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(email=data['email']).first()
    if user and user.password == data['password']:
        access_token = create_access_token(identity={'id': user.id, 'name': user.name})
        return jsonify({'access_token': access_token}), 200
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/add_user', methods=['POST'])
def add_user():
    data = request.get_json()
    if not data or not all(k in data for k in ('name', 'email', 'password')):
        return jsonify({'error': 'Invalid data'}), 400

    new_user = User(name=data['name'], email=data['email'], password=data['password'])
    try:
        db.session.add(new_user)
        db.session.commit()
        return jsonify({'message': 'Utilisateur ajouté avec succès !'}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/add_subscription', methods=['POST'])
@jwt_required()
def add_subscription():
    data = request.get_json()
    if not data or not all(k in data for k in ('user_id', 'plan', 'valid_until')):
        return jsonify({'error': 'Invalid data'}), 400

    subscription = Subscription(user_id=data['user_id'], plan=data['plan'], valid_until=data['valid_until'])
    try:
        db.session.add(subscription)
        db.session.commit()
        return jsonify({'message': 'Abonnement ajouté avec succès !'}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/subscriptions', methods=['GET'])
@jwt_required()
def get_subscriptions():
    subscriptions = Subscription.query.all()
    return jsonify({'subscriptions': [
        {
            'id': sub.id,
            'user_id': sub.user_id,
            'plan': sub.plan,
            'valid_until': sub.valid_until
        } for sub in subscriptions]
    })

@app.route('/generate_qr/<int:subscription_id>', methods=['GET'])
@jwt_required()
def generate_qr(subscription_id):
    subscription = Subscription.query.get(subscription_id)
    if not subscription:
        return jsonify({'error': 'Abonnement introuvable'}), 404

    qr_data = f"User ID: {subscription.user_id}, Plan: {subscription.plan}, Valid Until: {subscription.valid_until}"
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)

    return send_file(buf, mimetype='image/png', as_attachment=True, download_name=f'subscription_{subscription_id}.png')

@app.route('/validate_qr', methods=['POST'])
@jwt_required()
def validate_qr():
    data = request.get_json()
    qr_content = data.get('qr_content')

    if not qr_content:
        return jsonify({'error': 'Invalid QR data'}), 400

    user_id, plan, valid_until = None, None, None
    try:
        qr_parts = qr_content.split(', ')
        user_id = int(qr_parts[0].split(': ')[1])
        plan = qr_parts[1].split(': ')[1]
        valid_until = qr_parts[2].split(': ')[1]
    except Exception:
        return jsonify({'error': 'Malformed QR data'}), 400

    subscription = Subscription.query.filter_by(user_id=user_id, plan=plan, valid_until=valid_until).first()
    if not subscription:
        return jsonify({'error': 'Invalid QR code'}), 404

    return jsonify({'message': 'QR code valid', 'subscription': {
        'user_id': subscription.user_id,
        'plan': subscription.plan,
        'valid_until': subscription.valid_until
    }}), 200

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
print("Loaded secret key:", app.config['JWT_SECRET_KEY'])
