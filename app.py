from flask import Flask, request, jsonify
from flask_pymongo import PyMongo
from bson import ObjectId
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)
app.config["MONGO_URI"] = os.environ.get('MONGO_URI')
mongo = PyMongo(app)
db = mongo.cx.get_database("alagaprev")
collection = db.kmzs

@app.route("/kmzs", methods=["GET"])
def get_kmzs():
    kmzs = collection.find({}, {"_id": 0})
    return jsonify(list(kmzs))

@app.route("/kmzs/<kmz_id>", methods=["GET"])
def get_kmz(kmz_id):
    try:
        kmz = collection.find_one({"_id": ObjectId(kmz_id)}, {"_id": 0})
    except:
        return jsonify({"error": "KMZ not found"}), 404
    if kmz:
        return jsonify(kmz)
    else:
        return jsonify({"error": "KMZ not found"}), 404

@app.route("/kmzs", methods=["POST"])
def add_kmz():
    kmz_data = request.get_json()
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

if __name__ == "__main__":
    app.run(debug=True)