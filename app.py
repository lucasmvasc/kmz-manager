from flask import Flask, request, jsonify, render_template_string
from flask_pymongo import PyMongo
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash

from bson import ObjectId
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os

import openrouteservice

load_dotenv()

CATEGORIES  = {
    0: "Buraco",
    1: "Assalto",
    2: "Alagamento",
    3: "Obra",
    4: "Interditado"
}
OPENROUTES_API_KEY = os.getenv("OPENROUTES_API_KEY")
client = openrouteservice.Client(key=OPENROUTES_API_KEY)

app = Flask(__name__)
app.config["MONGO_URI"] = os.getenv('MONGO_URI')
mongo = PyMongo(app)
db = mongo.cx.get_database("alagaprev")
collection = db.kmzs

app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')
jwt = JWTManager(app)

@app.route("/kmzs", methods=["GET"])
def get_kmzs():
    kmzs = collection.find({}, {"_id": 0})
    geojson = {
        "type": "FeatureCollection",
        "features": list(kmzs)
    }
    return jsonify(geojson)

@app.route("/posicoes", methods=["GET"])
def get_posicoes():
    posicoes = db.posicoes.find({}, {"origin_user_id": 0})
    
    features = []
    for doc in posicoes:
        doc["_id"] = str(doc["_id"])
        features.append(doc)
        
    geojson = {
        "type": "FeatureCollection",
        "features": features
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
    
    is_walking = True
    try:
        is_walking = data['is_walking']
    except Exception:
        pass
    origin, destination = data["origin"], data["destination"]
    origin, destination = origin.split(","), destination.split(",")
    origin = (float(origin[0]), float(origin[1]))
    destination = (float(destination[0]), float(destination[1]))

    posicoes = db.posicoes.find({}, {"_id": 0, "origin_user_id": 0})
    blocked_areas = []
    for pos in posicoes:
        if not pos['is_valid']: continue
        coord = pos["geometry"]["coordinates"]
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
        profile = 'foot-walking' if is_walking else "cycling-regular",
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
        access_token = create_access_token(identity=str(user['_id']), expires_delta=timedelta(days=1))
        return jsonify(access_token=access_token), 200

    return jsonify(message="Credenciais inválidas"), 401

@app.route('/delete_user', methods=['POST'])
@jwt_required()
def delete_user():
    current_user_id = get_jwt_identity()
    db.user.delete_one({'_id': ObjectId(current_user_id)})
    return jsonify(message="Usuário deletado com sucesso"), 200

@app.route('/protected', methods=['GET'])
@jwt_required()
def protected():
    return jsonify(message="Essa é uma rota protegida"), 200

def get_score_by(user_id):
    result = db.user.find_one({'_id': user_id}, {'score': 1, '_id': 0})
    if result:
        return result.get('score', 0)
    else:
        return 0

@app.route("/create_position", methods=["POST"])
@jwt_required()
def create_postion():
    data = request.get_json()
    try:
        origin = data["origin"]
        origin = origin.split(",")
        lat, lon = float(origin[0]), float(origin[1])
        title = data["title"]
        classification = data['classification']
    except Exception:
        return jsonify(message="Informações de criação de ponto incompletas"), 401

    description = CATEGORIES[classification]
    user_str_id = get_jwt_identity()
    user_id = ObjectId(user_str_id)
    score = get_score_by(user_id)

    is_valid = False
    if score == 100:
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
        "created": datetime.now(),
        "origin_user_id": user_id,
        "is_valid": is_valid
    }
    result = db.posicoes.insert_one(kmz_data)
    return jsonify({"_id": str(result.inserted_id)})

def validate_same_user_position(position_id, current_user_id):
    posicao = db.posicoes.find_one({'_id': position_id})
    origin_user_id = posicao["origin_user_id"]
    if str(origin_user_id) == str(current_user_id):
        return False
    return True

def verify_current_pos_status(position_id):
    current_pos = db.posicoes.find_one({'_id': position_id})
    current_pos_is_valid = current_pos['is_valid']
    if current_pos_is_valid: return False
    else: return True

def update_position_by(position_id, bool_info):
    if bool_info:
        db.posicoes.update_one({'_id': position_id}, {'$set': {'is_valid': bool_info}})
    else:
        db.posicoes.delete_one({'_id': position_id})
    
    pos = db.posicoes.find_one({'_id': position_id})
    return pos.get("origin_user_id", None)

def update_score(user, bool_info):
    if bool_info:
        if user['score'] < 90:
            user['score'] += 10
        else:
            user['score'] = 100
    else:
        if user['score'] > 10:
            user['score'] -= 10
        else:
            user['score'] = 0
    return user

def update_user_score(user_id, bool_info):
    user = db.user.find_one({'_id': user_id})
    
    if user:
        updated_user = update_score(user, bool_info)
        db.user.update_one({'_id': user_id}, {'$set': {'score': updated_user['score']}})
    
@app.route("/validate", methods=["POST"])
@jwt_required()
def validate():
    data = request.get_json()
    
    try:
        position_id = data["position_id"]
        bool_info = data["bool_info"]
    except Exception:
        return jsonify(message="Ponto não pode ser validado"), 401
    
    current_user_id = get_jwt_identity()
    is_valid_user = validate_same_user_position(ObjectId(position_id), current_user_id)
    if not is_valid_user:
        return "Usuário validou o próprio ponto", 401
    
    is_valid_pos = verify_current_pos_status(ObjectId(position_id))
    if not is_valid_pos:
        return "Ponto já validado", 401
        
    user_id = update_position_by(ObjectId(position_id), bool_info)
    update_user_score(user_id, bool_info)
    
    return jsonify("Ponto alterado e usuário modificado")

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=False)