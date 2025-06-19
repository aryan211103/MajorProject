from flask import Blueprint, render_template, request, redirect, session, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
from datetime import datetime
from db import users_collection, db

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/')
def home():
    user_id = session.get('user_id')
    quiz_unlocked = False
    if user_id:
        user = users_collection.find_one({"user_id": user_id})
        if user and "gpa" in user:
            quiz_unlocked = True
    return render_template('index.html', is_logged_in=bool(user_id), quiz_unlocked=quiz_unlocked)

@auth_bp.route('/signup', methods=['GET', 'POST'])
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
            return render_template('login.html', errors=errors, error_message=None, show_signup=True)
        user_data = {
            "user_id": str(uuid.uuid4()),
            "email": email,
            "password": generate_password_hash(password)
        }
        users_collection.insert_one(user_data)
        return render_template('login.html', errors={}, error_message="Account created successfully. Please log in.", show_signup=False)
    return render_template('login.html', errors={}, error_message=None, show_signup=True)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    error_message = None
    if request.method == 'POST':
        email = request.form.get("email")
        password = request.form.get("password")
        user = users_collection.find_one({"email": email})
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['user_id']
            session['email'] = user['email']
            return redirect(url_for('auth.home'))
        else:
            error_message = "Invalid email or password. Please try again."
    return render_template('login.html', error_message=error_message, errors={}, show_signup=False)

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.home'))

@auth_bp.route('/form', methods=['GET', 'POST'])
def form():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('auth.signup'))
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
            "gre": request.form.get("gre"),
            "ielts": request.form.get("ielts"),
            "toefl": request.form.get("toefl"),
            "Languages": {}
        }
        language_ratings = request.form.to_dict(flat=True)
        for key, value in language_ratings.items():
            if key.startswith("rating["):
                language = key[7:-1]
                form_data["Languages"][language] = int(value)
        users_collection.update_one({"user_id": user_id}, {"$set": form_data}, upsert=True)
        session['user_data'] = {
            "features": [
                float(request.form.get("gpa")),
                int(request.form.get("gre")),
                float(request.form.get("ielts", 0)),
                float(request.form.get("toefl", 0)),
                float(request.form.get("internship_duration", 0)),
                int(request.form.get("research_papers", 0))
            ]
        }
        action = request.form.get("action")
        if action == "select":
            return redirect(url_for('modules.select_university'))
        else:
            return redirect(url_for('auth.form'))
    user = users_collection.find_one({"user_id": user_id})
    form_filled = bool(user and user.get("gpa"))
    return render_template('form.html', user_data=user, form_filled=form_filled)

@auth_bp.route('/dashboard')
def dashboard():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('auth.login'))
    
    # Fetch user info.
    user = users_collection.find_one({"user_id": user_id})
    
    # Retrieve saved universities and top recommended university from the user document.
    saved_universities = user.get("saved_universities", []) if user else []
    top_recommended = user.get("top_recommended_university", None)
    
    # Get a list of distinct courses from the user's quiz attempts.
    courses = db.quiz_results.distinct("course", {"user_id": user_id})
    
    # Get the course filter from the query parameters.
    course_filter = request.args.get('course')
    
    # If no course filter is provided but courses exist, pick the first one and redirect.
    if not course_filter and courses:
        course_filter = courses[0]
        return redirect(url_for('auth.dashboard', course=course_filter))
    
    # Fetch quiz attempts for the selected course.
    quiz_attempts = list(db.quiz_results.find({"user_id": user_id, "course": course_filter}).sort("timestamp", -1))
    
    # Build overall line chart data in chronological order.
    labels = []
    scores = []
    for attempt in quiz_attempts:
        ts = attempt.get('timestamp')
        labels.append(datetime.fromtimestamp(ts).strftime("%Y-%m-%d") if ts else "Unknown")
        scores.append(attempt.get("final_score", 0))
    labels.reverse()
    scores.reverse()
    quiz_chart_data = {"labels": labels, "scores": scores}
    
    # Prepare grouped bar chart data for the last 5 attempts (chronological order).
    last5 = list(reversed(quiz_attempts[:5]))
    attempt_labels = [datetime.fromtimestamp(attempt.get('timestamp', 0)).strftime("Attempt on %Y-%m-%d") for attempt in last5]
    beginner_scores = [attempt.get('beginner_correct', 0) for attempt in last5]
    intermediate_scores = [attempt.get('intermediate_correct', 0) for attempt in last5]
    expert_scores = [attempt.get('expert_correct', 0) for attempt in last5]
    grouped_chart_data = {
        "labels": attempt_labels,
        "beginner": beginner_scores,
        "intermediate": intermediate_scores,
        "expert": expert_scores
    }
    
    # Determine allowed difficulties based on the latest quiz score.
    if quiz_attempts:
        final_score = quiz_attempts[0].get('final_score', 0)
        if final_score <= 4:
            level = "Beginner"
            allowed_difficulties = ["Easy", "Medium", "Hard", "M_Expert"]
        elif final_score <= 7:
            level = "Intermediate"
            allowed_difficulties = ["Medium", "Hard", "M_Expert"]
        else:
            level = "Expert"
            allowed_difficulties = ["Hard", "M_Expert"]
    else:
        # No quiz attempts? Use a default difficulty filter so that recommended modules are still fetched.
        level = "Beginner"
        allowed_difficulties = ["Easy", "Medium", "Hard", "M_Expert"]
    
    # Re-query the modules collection for recommended modules for the selected course.
    recommended_cursor = db.modules.find(
        {"Course": course_filter, "Difficulty": {"$in": allowed_difficulties}},
        {"Module": 1, "name": 1, "Difficulty": 1, "Links": 1, "_id": 0}
    )
    recommended_modules = list(recommended_cursor)
    
    return render_template(
        'dashboard.html',
        user=user,
        quiz_attempts=quiz_attempts,
        quiz_chart_data=quiz_chart_data,
        grouped_chart_data=grouped_chart_data,
        recommended_modules=recommended_modules,
        courses=courses,
        selected_course=course_filter,
        saved_universities=saved_universities,
        top_recommended=top_recommended
    )
@auth_bp.app_context_processor
def inject_form_status():
    user_id = session.get('user_id')
    if not user_id:
        return {"is_logged_in": False, "form_filled": False}
    user = users_collection.find_one({"user_id": user_id})
    form_filled = bool(user and user.get("gpa"))
    return {"is_logged_in": True, "form_filled": form_filled}
