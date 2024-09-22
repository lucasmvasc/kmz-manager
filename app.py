from flask import Flask, request, jsonify
from flask_pymongo import PyMongo
from bson import ObjectId
from dotenv import load_dotenv
import os

import openrouteservice

load_dotenv()

OPENROUTE_API_KEY = os.getenv("OPENROUTE_API_KEY")
client = openrouteservice.Client(key=OPENROUTE_API_KEY)

app = Flask(__name__)
app.config["MONGO_URI"] = os.environ.get('MONGO_URI')
mongo = PyMongo(app)
db = mongo.cx.get_database("alagaprev")
collection = db.kmzs

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

@app.route("/get_route", methods=["GET"])
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
    
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=False)