import os
import sys
import pandas as pd
import shutil
from flask import Flask, render_template, request, redirect, url_for, send_file, Response

UPLOAD_FOLDER = 'uploads'

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 🔐 AUTH konfiguracija
USERNAME = "admin"
PASSWORD = "tajna123"

def check_auth(username, password):
    return username == USERNAME and password == PASSWORD

def authenticate():
    return Response(
        'Pristup zabranjen.\nUnesite validne kredencijale.', 401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'}
    )

def requires_auth(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

# ⬇️ ZAŠTIĆENE RUTE
@app.route('/')
@requires_auth
def index():
    return render_template('index.html')

@app.route('/log')
@requires_auth
def prikazi_log():
    try:
        df = pd.read_excel("log_izvjestaj.xlsx")

        statusi = df["Status"].fillna("").str.strip()
        poslano = statusi.eq("✅ Poslano").sum()
        greske = len(statusi) - poslano

        return render_template("log.html", tabela=df.to_dict(orient="records"),
                               poslano=poslano, greske=greske)
    except Exception as e:
        return f"Greska pri čitanju log fajla: {e}"

@app.route('/preuzmi-log')
@requires_auth
def preuzmi_log():
    try:
        return send_file("log_izvjestaj.xlsx", as_attachment=True)
    except Exception as e:
        return f"Greska pri preuzimanju log fajla: {e}"

@app.route('/upload', methods=['POST'])
@requires_auth
def upload_files():
    if 'pdf_files' not in request.files:
        return "Nema PDF fajlova u zahtjevu.", 400

    files = request.files.getlist('pdf_files')
    for file in files:
        if file.filename.endswith('.pdf'):
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], file.filename))

    xlsx = request.files.get('xlsx_file')
    if xlsx and xlsx.filename.endswith('.xlsx'):
        xlsx.save("BAZA E MAIL.xlsx")

    return redirect(url_for('pokreni'))

@app.route('/pokreni')
@requires_auth
def pokreni():
    try:
        import subprocess

        rezultat = subprocess.run(
            [sys.executable, "posalji_fakture.py"],
            cwd=os.getcwd(),
            capture_output=True,
            text=True,
            encoding="utf-8"
        )

        stderr_clean = "\n".join([
            line for line in rezultat.stderr.splitlines()
            if "CropBox" not in line and "MediaBox" not in line
        ]).strip()

        stdout_clean = rezultat.stdout.strip()

        poruka_parts = []

        if stdout_clean:
            poruka_parts.append(f"""
                <h4>STDOUT:</h4>
                <pre>{stdout_clean}</pre>
            """)

        if stderr_clean:
            poruka_parts.append(f"""
                <h4>STDERR:</h4>
                <pre>{stderr_clean}</pre>
            """)

        poruka = "<h3>Rezultat pokretanja:</h3>" + "\n".join(poruka_parts)

        uspjeh = rezultat.returncode == 0
        return render_template("rezultat.html", uspjeh=uspjeh, poruka=poruka)

    except Exception as e:
        return render_template("rezultat.html", uspjeh=False, poruka=str(e))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
