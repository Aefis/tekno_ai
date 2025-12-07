import os
import json
import bcrypt
import psycopg2
from flask import Flask, render_template, request

from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)

conn = psycopg2.connect(os.getenv("DATABASE_URL"))
cursor = conn.cursor()


@app.route("/", methods=["GET", "POST"])
def create_user():
    if request.method == "POST":
        email = request.form["email"].strip()
        password = request.form["password"].strip()

        # Hash password
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

        # Insert into database
        cursor.execute(
            '''
            INSERT INTO "User" ("identifier", "password", "metadata")
            VALUES (%s, %s, %s)
            ''',
            (email, hashed, json.dumps({}))
        )
        conn.commit()

        return "<h3 style='color:green'>✅ User created successfully!</h3><a href='/'>Create another</a>"

    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)
