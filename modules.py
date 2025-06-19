from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify
import pandas as pd
from ml_model import predict  # Ensure ml_model.py is accessible and loads xgb_model.pkl correctly
from db import db, users_collection  # Make sure users_collection is imported
from datetime import datetime
from pymongo import DESCENDING

modules_bp = Blueprint('modules', __name__)

def load_multipliers():
    try:
        university_df = pd.read_excel("uni_multiplier.xlsx", engine="openpyxl")
        degree_df = pd.read_excel("masters_degree.xlsx", engine="openpyxl")

        # Extract university and degree lists using exact column names
        university_list = university_df["Engineering Schools"].dropna().tolist()
        degree_list = degree_df["masters_degree"].dropna().tolist()  # Use 'masters_degree'

        # Build university weights dictionary
        university_weights = {
            row["Engineering Schools"]: {
                "gre_weight": row.get("GRE Weight", 0.25),
                "gpa_weight": row.get("GPA Weight", 0.25),
                "papers_weight": row.get("Papers Weight", 0.25),
                "experience_weight": row.get("Experience Weight", 0.25)
            }
            for _, row in university_df.iterrows()
        }

        # Build degree difficulty factor dictionary
        degree_factors = dict(zip(degree_list, degree_df["difficulty_factor"]))

        return university_weights, university_list, degree_factors, degree_list
    except Exception as e:
        print(f"Error loading files: {e}")
        return {}, [], {}, []

# ------------------ ML-BASED UNIVERSITY SELECTION ------------------

@modules_bp.route('/select_university', methods=['GET', 'POST'])
def select_university():
    university_weights, university_list, degree_factors, degree_list = load_multipliers()

    # Static categories for display (update as needed)
    university_categories = {
        "GPA-Based": ["University of Southern California", "University of Texas at Dallas"],
        "GRE-Based": ["Northwestern University", "University of Pennsylvania"],
        "Research Paper-Based": ["New York University, Tandon", "University of Maryland, College Park"],
        "Work Experience-Based": ["Carnegie Mellon University", "Columbia University"]
    }
    highly_selective_universities = [
        "University of Southern California", 
        "Carnegie Mellon University", 
        "Columbia University", 
        "Northwestern University"
    ]

    if request.method == 'POST':
        selected_universities = request.form.getlist("universities")
        selected_degrees = request.form.getlist("degrees")

        if "user_data" not in session:
            return redirect(url_for('modules.form'))

        input_features = session["user_data"]["features"]
        user_gre = input_features[1]
        user_gpa = input_features[0]
        user_papers = input_features[4]
        user_experience = input_features[5]

        university_degree_predictions = {}

        for university in selected_universities:
            for degree in selected_degrees:
                base_probability = predict(input_features)
                weights = university_weights.get(university, {
                    "gre_weight": 0.25, "gpa_weight": 0.25, "papers_weight": 0.25, "experience_weight": 0.25
                })
                degree_factor = degree_factors.get(degree, 1.0)
                total_weight = weights["gre_weight"] + weights["gpa_weight"] + weights["papers_weight"] + weights["experience_weight"]
                gre_weight = weights["gre_weight"] / total_weight
                gpa_weight = weights["gpa_weight"] / total_weight
                papers_weight = weights["papers_weight"] / total_weight
                experience_weight = weights["experience_weight"] / total_weight

                gre_multiplier = 1.5 if user_gre >= 320 else (0.5 if user_gre < 310 else 1.0)
                gpa_multiplier = 1.5 if user_gpa > 3.7 else (0.5 if user_gpa < 3.5 else 0.8)
                papers_multiplier = 1.5 if user_papers > 1 else 0.7
                experience_multiplier = 1.4 if user_experience > 12 else 0.6

                weighted_adjustment = (
                    (gre_weight * gre_multiplier) +
                    (gpa_weight * gpa_multiplier) +
                    (papers_weight * papers_multiplier) +
                    (experience_weight * experience_multiplier)
                )

                adjusted_probability = base_probability * (0.4 + 0.4 * weighted_adjustment)

                if university in highly_selective_universities:
                    adjusted_probability *= 0.6
                if university == "University of Southern California" and user_gpa < 3.7:
                    adjusted_probability = min(adjusted_probability, 30)

                adjusted_probability *= degree_factor
                final_probability = max(5, min(80, round(adjusted_probability, 2)))
                university_degree_predictions[f"{university} - {degree}"] = final_probability

        if university_degree_predictions:
            values = list(university_degree_predictions.values())
            average_probability = round(sum(values) / len(values), 1) if values else 0
            top_choice = max(university_degree_predictions.items(),
                             key=lambda x: x[1],
                             default=("None", 0))
        else:
            average_probability = 0
            top_choice = ("None", 0)

        # Save the top recommended university in the user document.
        user_id = session.get("user_id")
        if user_id:
            users_collection.update_one(
                {"user_id": user_id},
                {"$set": {"top_recommended_university": top_choice[0]}},
                upsert=True
            )

        return render_template('results1.html', 
                             predictions=university_degree_predictions,
                             average_probability=average_probability,
                             top_choice=top_choice)

    return render_template('select_university.html', 
                         university_categories=university_categories, 
                         degrees=degree_list)

# ------------------ EXISTING MODULE/QUIZ ROUTES ------------------

@modules_bp.route('/results')
def results():
    course = request.args.get('course')
    user_id = session.get('user_id')
    if not user_id or not course:
        return redirect(url_for('auth.home'))

    quiz_result = db.quiz_results.find_one(
        {"user_id": user_id, "course": course},
        sort=[("timestamp", DESCENDING)]
    )
    if not quiz_result:
        return redirect(url_for('auth.home'))

    final_score = quiz_result.get('final_score', 0)
    if final_score <= 4:
        level = "Beginner"
        allowed_difficulties = ["Easy", "Medium", "Hard", "M_Expert"]
    elif final_score <= 7:
        level = "Intermediate"
        allowed_difficulties = ["Medium", "Hard", "M_Expert"]
    else:
        level = "Expert"
        allowed_difficulties = ["Hard", "M_Expert"]

    recommended_cursor = db.modules.find(
        {"Course": course, "Difficulty": {"$in": allowed_difficulties}},
        {"Module": 1, "_id": 0}
    )
    recommended_modules = [doc['Module'] for doc in recommended_cursor] if recommended_cursor else []

    db.quiz_results.update_one(
        {"_id": quiz_result["_id"]},
        {"$set": {"recommended_modules": recommended_modules}},
        upsert=True
    )

    attempts = list(db.quiz_results.find({"user_id": user_id, "course": course}).sort("timestamp", DESCENDING).limit(5))
    attempts.reverse()
    labels = []
    beginner_scores = []
    intermediate_scores = []
    expert_scores = []
    for attempt in attempts:
        ts = attempt.get('timestamp')
        labels.append(datetime.fromtimestamp(ts).strftime("%Y-%m-%d") if ts else "Unknown")
        beginner_scores.append(attempt.get('beginner_correct', 0))
        intermediate_scores.append(attempt.get('intermediate_correct', 0))
        expert_scores.append(attempt.get('expert_correct', 0))
    
    grouped_chart_data = {
        "labels": labels,
        "beginner": beginner_scores,
        "intermediate": intermediate_scores,
        "expert": expert_scores
    }

    return render_template(
        'results.html',
        quiz_data=quiz_result,
        recommended_modules=recommended_modules,
        level=level,
        grouped_chart_data=grouped_chart_data
    )

@modules_bp.route('/modules')
def modules():
    course = request.args.get('course')
    user_id = session.get('user_id')
    if not user_id or not course:
        return redirect(url_for('auth.home'))
    
    quiz_result = db.quiz_results.find_one(
        {"user_id": user_id, "course": course},
        sort=[("timestamp", DESCENDING)]
    )
    if not quiz_result or 'recommended_modules' not in quiz_result:
        return redirect(url_for('modules.results'))
    
    recommended_modules = quiz_result['recommended_modules']
    module_data = list(db.modules.find({"Module": {"$in": recommended_modules}}, {"_id": 0}))
    
    return render_template(
        'modules.html',
        modules=module_data,
        course=course,
        quiz_data=quiz_result
    )

@modules_bp.route('/module_details')
def module_details():
    module_name = request.args.get('module_name')
    if not module_name:
        return redirect(url_for('auth.home'))
    
    module_data = db.modules.find_one({"Module": module_name}, {"_id": 0})
    if module_data:
        return render_template('module_details.html', module=module_data)
    else:
        return "Module not found.", 404

# New Route: Save University
@modules_bp.route('/save_university', methods=['POST'])
def save_university():
    from flask import jsonify
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('auth.login'))
    
    data = request.get_json()
    if not data or 'choice' not in data:
        return jsonify({"error": "No choice provided"}), 400
    
    choice = data['choice']
    
    # Use $addToSet with upsert=True to ensure the document exists and the value is added only once.
    users_collection.update_one(
        {"user_id": user_id},
        {"$addToSet": {"saved_universities": choice}},
        upsert=True
    )
    
    # Re-fetch the updated user document and update the session if needed.
    user = users_collection.find_one({"user_id": user_id})
    saved_universities = user.get("saved_universities", [])
    
    # (Optional) Update the session variable if your dashboard relies on it.
    session['saved_universities'] = saved_universities

    return jsonify({"status": "success", "saved_universities": saved_universities})

