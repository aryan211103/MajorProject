import os
from flask import Flask
from auth import auth_bp
from quiz import quiz_bp
from modules import modules_bp
from flask_session import Session
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your_secret_key')
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# Custom filter to format Unix timestamps (ensuring the value is a float)
@app.template_filter('datetimeformat')
def datetimeformat(value, format='%Y-%m-%d %H:%M:%S'):
    try:
        return datetime.fromtimestamp(float(value)).strftime(format)
    except Exception as e:
        return value

# Register Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(quiz_bp)
app.register_blueprint(modules_bp)

if __name__ == '__main__':
    app.run(debug=True)
