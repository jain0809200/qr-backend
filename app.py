from flask import Flask, request, jsonify, redirect
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore
import hashlib
import datetime

# Initialize app
app = Flask(__name__)
CORS(app)

# Firebase setup
cred = credentials.Certificate("firebase_config.json")
firebase_admin.initialize_app(cred)
db = firestore.client()
qr_ref = db.collection('qrcodes')

# Utility: Hash password
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# ------------------ ROUTES ------------------

# ✅ Redirect from QR Code
@app.route("/q/<code>", methods=["GET"])
def redirect_qr(code):
    doc = qr_ref.document(code).get()
    if doc.exists:
        data = doc.to_dict()
        # increment scan count
        qr_ref.document(code).update({"scans": firestore.Increment(1)})
        return redirect(data['url'], code=302)
    else:
        return "QR Code not found", 404

# ✅ Admin: Create new QR
@app.route("/api/create", methods=["POST"])
def create_qr():
    data = request.json
    code = data.get("code")
    url = data.get("url")
    password = data.get("password")

    if not all([code, url, password]):
        return jsonify({"success": False, "message": "Missing fields"}), 400

    hashed_pass = hash_password(password)

    qr_ref.document(code).set({
        "url": url,
        "password": hashed_pass,
        "created": datetime.datetime.utcnow().isoformat(),
        "scans": 0
    })

    return jsonify({"success": True, "message": "QR created", "fixed_link": f"/q/{code}"}), 200

# ✅ User: Update URL
@app.route("/api/update", methods=["POST"])
def update_qr():
    data = request.json
    code = data.get("code")
    password = data.get("password")
    new_url = data.get("new_url")

    doc = qr_ref.document(code).get()
    if not doc.exists:
        return jsonify({"success": False, "message": "QR Code not found"}), 404

    stored = doc.to_dict()
    if hash_password(password) != stored["password"]:
        return jsonify({"success": False, "message": "Incorrect password"}), 403

    qr_ref.document(code).update({"url": new_url})
    return jsonify({"success": True, "message": "Destination updated"}), 200

# ✅ Admin: Delete QR
@app.route("/api/delete/<code>", methods=["DELETE"])
def delete_qr(code):
    qr_ref.document(code).delete()
    return jsonify({"success": True, "message": f"{code} deleted"}), 200

# ✅ Admin: List All
@app.route("/api/list", methods=["GET"])
def list_qr():
    docs = qr_ref.stream()
    result = []
    for doc in docs:
        data = doc.to_dict()
        data["code"] = doc.id
        result.append(data)
    return jsonify(result)

# ✅ Health Check
@app.route("/")
def index():
    return "QR Backend is running", 200

# ------------------ RUN ------------------
if __name__ == "__main__":
    app.run(debug=True)
