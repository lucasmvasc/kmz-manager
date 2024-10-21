from flask import Flask, request, jsonify
from flask_pymongo import PyMongo
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash

from bson import ObjectId
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import os
import pytz

import openrouteservice

load_dotenv()

OPENROUTES_API_KEY = os.getenv("OPENROUTES_API_KEY")
client = openrouteservice.Client(key=OPENROUTES_API_KEY)

app = Flask(__name__)
app.config["MONGO_URI"] = os.getenv('MONGO_URI')
mongo = PyMongo(app)
db = mongo.cx.get_database("alagaprev")
collection = db.kmzs

app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')  # Troque por uma chave segura
jwt = JWTManager(app)

@app.route("/kmzs", methods=["GET"])
def get_kmzs():
    kmzs = collection.find({}, {"_id": 0})
    geojson = {
        "type": "FeatureCollection",
        "features": list(kmzs)
    }
    return jsonify(geojson)

@app.route("/kmzs/<kmz_id>", methods=["GET"])
def get_kmz(kmz_id):
    try:
        kmz = collection.find_one({"_id": ObjectId(kmz_id)}, {"_id": 0})
    except Exception:
        return jsonify({"error": "KMZ not found"}), 404
    if kmz:
        return jsonify(kmz)
    else:
        return jsonify({"error": "KMZ not found"}), 404

@app.route("/kmzs", methods=["POST"])
def add_kmz():
    data = request.get_json()
    try:
        lat, lon = data["lat"], data["lon"]
    except KeyError:
        print("Pontos de bloqueio não definidos")

    title = data["title"]
    description = data["description"]
    kmz_data = {
        "type": "Feature",
        "properties": {
            "title": title,
            "description": description
        },
        "geometry": {
            "type": "Point",
            "coordinates": [lat, lon]
        }
    }

    result = collection.insert_one(kmz_data)
    return jsonify({"_id": str(result.inserted_id)})

@app.route("/kmzs/<kmz_id>", methods=["PUT"])
def update_kmz(kmz_id):
    kmz_data = request.get_json()
    result = collection.update_one({"_id": ObjectId(kmz_id)}, {"$set": kmz_data})
    if result.modified_count > 0:
        return jsonify({"message": "KMZ updated successfully"})
    else:
        return jsonify({"error": "KMZ not found"}), 404

@app.route("/kmzs/<kmz_id>", methods=["DELETE"])
def delete_kmz(kmz_id):
    result = collection.delete_one({"_id": ObjectId(kmz_id)})
    if result.deleted_count > 0:
        return jsonify({"message": "KMZ deleted successfully"})
    else:
        return jsonify({"error": "KMZ not found"}), 404

@app.route("/get_route", methods=["POST"])
def get_route():
    data = request.get_json()
    
    origin, destination = data["origin"], data["destination"]
    origin, destination = origin.split(","), destination.split(",")
    origin = (float(origin[0]), float(origin[1]))
    destination = (float(destination[0]), float(destination[1]))

    kmzs = collection.find({}, {"_id": 0})
    blocked_areas = []
    for kmz in kmzs:
        coord = kmz["geometry"]["coordinates"]
        center_lat, center_lon = coord[0], coord[1]
        offset= 0.0001
        blocked_area = [
            [center_lon + offset, center_lat + offset], 
            [center_lon - offset, center_lat + offset],
            [center_lon - offset, center_lat - offset],
            [center_lon + offset, center_lat - offset],
            [center_lon + offset, center_lat + offset]
        ]
        blocked_areas.append(blocked_area)

    route = client.directions(
        coordinates = [origin[::-1], destination[::-1]],
        profile = 'foot-walking',
        format = 'geojson',
        options = {
            "avoid_polygons":{
            "type": "MultiPolygon",
            "coordinates": [[area] for area in blocked_areas]}
        }
    )
 
    return jsonify({"message": "Rota gerada com sucesso", "result":route})

@app.route("/register_user", methods=["POST"])
def register_user():
    data = request.get_json()
    try:
        username, password, email = data['username'], data['password'], data['email']
    except KeyError:
        return jsonify(message="Credenciais incompletas"), 401
    
    hashed_password = generate_password_hash(password)
    db.user.insert_one({
        'name': username,
        'email': email,
        'password': hashed_password,
        'score': 50
    })
    return jsonify(message="Usuário registrado"), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    try:
        password, email = data['password'], data['email']
    except KeyError:
        return jsonify(message="Email ou senha não recebidos"), 401

    user = db.user.find_one({'email': email})

    if user and check_password_hash(user['password'], password):
        access_token = create_access_token(identity=str(user['_id']))
        return jsonify(access_token=access_token), 200

    return jsonify(message="Credenciais inválidas"), 401

@app.route('/delete_user', methods=['POST'])
@jwt_required()
def delete_user():
    current_user_id = get_jwt_identity()
    mongo.db.users.delete_one({'_id': ObjectId(current_user_id)})
    return jsonify(message="Usuário deletado com sucesso"), 200

@app.route('/protected', methods=['GET'])
@jwt_required()
def protected():
    return jsonify(message="Essa é uma rota protegida"), 200

@app.route("/create_position", methods=["POST"])
def create_postion():
    data = request.get_json()
    try:
        origin = data["origin"]
        origin = origin.split(",")
        lat, lon = float(origin[0]), float(origin[1])
        title = data["title"]
        description = data["description"]
        classification = data['classification']
        email = data['email']
        user_score = data['user_score']
    except Exception:
        return jsonify(message="Informações de criação de ponto incompletas"), 401
    
    is_valid = False
    if user_score == 100:
        is_valid = True
    
    kmz_data = {
        "type": "Feature",
        "properties": {
            "title": title,
            "description": description
        },
        "geometry": {
            "type": "Point",
            "coordinates": [lat, lon]
        },
        "classification": classification,
        "created": datetime.now(pytz.timezone('America/Fortaleza')),
        "origin_user_id": email,
        "is_valid": is_valid
    }
    
    result = db.posicoes.insert_one(kmz_data)
    return jsonify({"_id": str(result.inserted_id)})
    
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=False)