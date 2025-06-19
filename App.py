from flask import Flask, render_template, request, redirect, session, url_for, jsonify
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
import requests
import random
import time
import re
from recommendations import recommend_modules

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# MongoDB setup
client = MongoClient('mongodb+srv://rolston20:NCc5P9VkSfrafZOs@course.vynlz.mongodb.net/?retryWrites=true&w=majority&appName=course')
db = client['recommendation_system']
users_collection = db['users']
quiz_results_collection = db['quiz_results']
quiz_questions_collection = db['quiz_questions']

# Judge0 API Configuration using RapidAPI (Self-hosted alternative if needed)
JUDGE0_ENDPOINT = "https://judge0-ce.p.rapidapi.com/submissions/"
JUDGE0_API_URL = "https://api.judge0.com/submissions"
HEADERS = {
    "Content-Type": "application/json",
    "X-RapidAPI-Key": "68ebceab75msha4531b3497020cdp1d32adjsn7ed41e077261",  # Replace with your actual API key
    "X-RapidAPI-Host": "judge0-ce.p.rapidapi.com"
}

def submit_code(source_code, language_id, stdin=""):
    """
    Submit code to the Judge0 API.
    :param source_code: The code to execute.
    :param language_id: The Judge0 language ID (e.g., 71 for Python 3).
    :param stdin: (Optional) Input to pass to the program.
    :return: A token string to track the submission.
    """
    payload = {
        "source_code": source_code,
        "language_id": language_id,
        "stdin": stdin
    }
    params = {"base64_encoded": "false", "wait": "false"}
    response = requests.post(JUDGE0_ENDPOINT, json=payload, headers=HEADERS, params=params)
    response_data = response.json()
    token = response_data.get("token")
    if not token:
        raise Exception(f"Submission failed: {response_data}")
    return token

def get_result(token):
    """
    Poll the Judge0 API using the token until the result is ready.
    :param token: The token received from submit_code.
    :return: The final result as a dictionary.
    """
    params = {"base64_encoded": "false"}
    while True:
        result_response = requests.get(f"{JUDGE0_ENDPOINT}{token}", headers=HEADERS, params=params)
        result = result_response.json()
        status_id = result["status"]["id"]
        if status_id in [1, 2]:  # In Queue or Processing
            time.sleep(1)
        else:
            break
    return result

@app.route('/')
def home():
    user_id = session.get('user_id')
    quiz_unlocked = False
    if user_id:
        user = users_collection.find_one({"user_id": user_id})
        if user and "gpa" in user:
            quiz_unlocked = True
    return render_template('index.html', is_logged_in=bool(user_id), quiz_unlocked=quiz_unlocked)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm-password")
        errors = {}
        if password != confirm_password:
            errors['confirm-password'] = "Passwords do not match."
        if users_collection.find_one({"email": email}):
            errors['email'] = "An account with this email already exists."
        if errors:
            return render_template('signup.html', errors=errors)
        user_data = {
            "user_id": str(uuid.uuid4()),
            "email": email,
            "password": generate_password_hash(password)
        }
        users_collection.insert_one(user_data)
        session['user_id'] = user_data['user_id']
        session['email'] = email
        return redirect(url_for('home'))
    return render_template('signup.html', errors={})

@app.route('/login', methods=['GET', 'POST'])
def login():
    error_message = None
    if request.method == 'POST':
        email = request.form.get("email")
        password = request.form.get("password")
        user = users_collection.find_one({"email": email})
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['user_id']
            session['email'] = user['email']
            return redirect(url_for('home'))
        else:
            error_message = "Invalid email or password. Please try again."
    return render_template('login.html', error_message=error_message)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/form', methods=['GET', 'POST'])
def form():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('signup'))
    if request.method == 'POST':
        form_data = {
            "name": request.form.get("name"),
            "gpa": request.form.get("gpa"),
            "degree": request.form.get("degree"),
            "skills": request.form.getlist("skills"),
            "job_experience": request.form.get("job_experience"),
            "extra_curricular": request.form.get("extra_curricular"),
            "internship_duration": request.form.get("internship_duration"),
            "research_papers": request.form.get("research_papers"),
            "Languages": {}
        }
        language_ratings = request.form.to_dict(flat=True)
        for key, value in language_ratings.items():
            if key.startswith("rating["):
                language = key[7:-1]
                form_data["Languages"][language] = int(value)
        users_collection.update_one({"user_id": user_id}, {"$set": form_data}, upsert=True)
        return redirect(url_for('home'))
    user_data = users_collection.find_one({"user_id": user_id})
    return render_template('form.html', user_data=user_data, form_filled=bool(user_data))

@app.context_processor
def inject_form_status():
    user_id = session.get('user_id')
    if not user_id:
        return {"is_logged_in": False, "form_filled": False}
    user_profile = users_collection.find_one({"user_id": user_id})
    return {"is_logged_in": True, "form_filled": bool(user_profile)}

@app.route('/select_course', methods=['GET'])
def select_course():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    user_profile = users_collection.find_one({"user_id": user_id})
    if not user_profile:
        return redirect(url_for('form'))
    quiz_results = list(db.quiz_results.find({"user_id": user_id}))
    completed_courses = {result['course'] for result in quiz_results}
    courses = [
        {"name": "DevOps", "description": "Master CI/CD, automation, and scalable deployments.", "completed": "DevOps" in completed_courses},
        {"name": "Mobile App Development", "description": "Build responsive and engaging mobile applications.", "completed": "Mobile App Development" in completed_courses},
        {"name": "IoT", "description": "Learn to connect devices and analyze IoT data.", "completed": "IoT" in completed_courses},
        {"name": "Software Engineering", "description": "Explore software design, testing, and methodologies.", "completed": "Software Engineering" in completed_courses},
        {"name": "Data Science", "description": "Analyze and interpret complex data for insights.", "completed": "Data Science" in completed_courses},
        {"name": "Cloud Computing", "description": "Learn to build and manage cloud-based systems.", "completed": "Cloud Computing" in completed_courses},
        {"name": "Machine Learning", "description": "Build intelligent systems using ML algorithms.", "completed": "Machine Learning" in completed_courses},
        {"name": "AI", "description": "Explore artificial intelligence concepts and applications.", "completed": "AI" in completed_courses},
        {"name": "UI/UX Design", "description": "Design intuitive and user-friendly interfaces.", "completed": "UI/UX Design" in completed_courses},
        {"name": "Blockchain", "description": "Understand distributed ledgers and smart contracts.", "completed": "Blockchain" in completed_courses},
        {"name": "Web Development", "description": "Create modern and dynamic websites.", "completed": "Web Development" in completed_courses},
        {"name": "Cybersecurity", "description": "Protect systems and networks from cyber threats.", "completed": "Cybersecurity" in completed_courses},
        {"name": "Neural Networks", "description": "Learn biologically inspired neural network models.", "completed": "Neural Networks" in completed_courses}
    ]
    return render_template('select_course.html', courses=courses)

@app.route('/quiz')
def quiz():
    course = request.args.get('course')
    section = request.args.get('section', 'aptitude')
    if not course:
        return "Invalid request: Course missing", 400

    if section == 'aptitude':
        aptitude_questions = list(quiz_questions_collection.aggregate([
            {"$match": {"course": course, "section": "aptitude"}},
            {"$sample": {"size": 10}}
        ]))
        time_limit = 10 * 60
    elif section == 'technical':
        technical_questions = list(quiz_questions_collection.aggregate([
            {"$match": {"course": course, "section": "technical"}},
            {"$sample": {"size": 2}}
        ]))
        time_limit = 15 * 60
    else:
        return "Invalid section", 400

    return render_template(
        'quiz.html',
        selected_course=course,
        aptitude_questions=aptitude_questions if section == 'aptitude' else [],
        technical_questions=technical_questions if section == 'technical' else [],
        section=section,
        time_limit=time_limit
    )

@app.route('/quiz/start', methods=['POST'])
def start_quiz():
    data = request.json
    course = data.get('course')
    if not course:
        return jsonify({"error": "Course is required"}), 400

    aptitude_questions = list(quiz_questions_collection.aggregate([
        {"$match": {"course": course, "section": "aptitude"}},
        {"$sample": {"size": 10}}
    ]))
    technical_questions = list(quiz_questions_collection.aggregate([
        {"$match": {"course": course, "section": "technical"}},
        {"$sample": {"size": 2}}
    ]))
    session['quiz_data'] = {
        "course": course,
        "aptitude": aptitude_questions,
        "technical": technical_questions,
        "current_question": 0,
        "score": 0,
        "start_time": time.time()
    }
    return jsonify({"message": "Quiz started", "total_questions": 12})

def get_questions(course, section, limit):
    questions = list(quiz_questions_collection.find({"course": course, "section": section}))
    return random.sample(questions, limit) if len(questions) >= limit else questions

@app.route('/quiz/answer', methods=['POST'])
def submit_answer():
    data = request.json
    answer = data.get('answer')
    quiz_data = session.get('quiz_data')
    if not quiz_data:
        return jsonify({"error": "Quiz not started"}), 400

    current_question = quiz_data['current_question']
    if current_question < 10:
        correct_answer = quiz_data['aptitude'][current_question]['correct_answer']
        if answer == correct_answer:
            quiz_data['score'] += 1
    else:
        technical_question = quiz_data['technical'][current_question - 10]
        if technical_question['type'] == 'coding':
            submission_result = submit_code(
                source_code=answer,
                language_id=technical_question['language_id'],
                stdin=""  # Optionally provide test case input
            )
            print(submission_result)
            # Poll for result using get_result
            result = get_result(submission_result)
            if result and result.get('status', {}).get('description') == 'Accepted':
                quiz_data['score'] += 5
        else:
            if answer.lower() == technical_question['correct_answer'].lower():
                quiz_data['score'] += 5

    quiz_data['current_question'] += 1
    session['quiz_data'] = quiz_data
    return jsonify({"message": "Answer submitted", "score": quiz_data['score']})

@app.route('/quiz/end', methods=['GET'])
def end_quiz():
    quiz_data = session.get('quiz_data')
    if not quiz_data:
        return jsonify({"error": "Quiz not started"}), 400
    elapsed_time = time.time() - quiz_data['start_time']
    final_score = quiz_data['score']
    session.pop('quiz_data', None)
    return jsonify({"message": "Quiz ended", "final_score": final_score, "time_taken": elapsed_time})

@app.route('/results')
def results():
    course = request.args.get('course')
    user_id = session.get('user_id')
    if not user_id or not course:
        return redirect(url_for('home'))
    quiz_result = db.quiz_results.find_one({"user_id": user_id, "course": course})
    if not quiz_result:
        return redirect(url_for('home'))
    recommended_modules = quiz_result.get('recommended_modules', [])
    return render_template('results.html', quiz_data=quiz_result, recommended_modules=recommended_modules)

@app.route('/modules')
def modules():
    course = request.args.get('course')
    user_id = session.get('user_id')
    if not user_id or not course:
        return redirect(url_for('home'))
    quiz_result = db.quiz_results.find_one({"user_id": user_id, "course": course})
    if not quiz_result or 'recommended_modules' not in quiz_result:
        return redirect(url_for('results'))
    recommended_modules = quiz_result['recommended_modules']
    module_data = list(db.modules.find({"Module": {"$in": recommended_modules}}, {"_id": 0}))
    quiz_data = {"course": course, "recommended_modules": recommended_modules}
    return render_template('modules.html', modules=module_data, course=course, quiz_data=quiz_data)

@app.route('/module_details')
def module_details():
    module_name = request.args.get('module_name')
    if not module_name:
        return redirect(url_for('home'))
    module_data = db.modules.find_one({"Module": module_name}, {"_id": 0})
    if module_data:
        return render_template('module_details.html', module=module_data)
    else:
        return "Module not found.", 404

# # Judge0 API functions
# def submit_code(source_code, language_id, stdin=""):
#     """
#     Submit code to the Judge0 API.
#     """
#     headers = {
#         "content-type": "application/json",
#         "X-RapidAPI-Key": "68ebceab75msha4531b3497020cdp1d32adjsn7ed41e077261",  # Replace with your actual API key
#         "X-RapidAPI-Host": "judge0-ce.p.rapidapi.com"
#     }
#     payload = {
#         "source_code": source_code,
#         "language_id": language_id,
#         "stdin": stdin
#     }
#     params = {"base64_encoded": "false", "wait": "false"}
#     response = requests.post(JUDGE0_API_URL, json=payload, headers=headers, params=params)
#     response_data = response.json()
#     token = response_data.get("token")
#     if not token:
#         raise Exception(f"Submission failed: {response_data}")
#     return token

# def get_result(token):
#     """
#     Poll the Judge0 API using the token until the result is ready.
#     """
#     params = {"base64_encoded": "false"}
#     while True:
#         result_response = requests.get(f"{JUDGE0_API_URL}{token}", headers={"content-type": "application/json", "X-RapidAPI-Key": "68ebceab75msha4531b3497020cdp1d32adjsn7ed41e077261", "X-RapidAPI-Host": "judge0-ce.p.rapidapi.com"}, params=params)
#         result = result_response.json()
#         status_id = result["status"]["id"]
#         if status_id in [1, 2]:
#             time.sleep(1)
#         else:
#             break
#     return result

if __name__ == '__main__':
    app.run(debug=True)
