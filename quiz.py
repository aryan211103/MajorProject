from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify
import random
import time
from db import quiz_questions_collection, db
from judge0 import submit_code, get_result

quiz_bp = Blueprint('quiz', __name__)

def serialize_question(question):
    """
    Convert non-JSON-serializable fields (like ObjectId) to strings.
    """
    question['_id'] = str(question['_id'])
    return question

@quiz_bp.route('/select_course', methods=['GET'])
def select_course():
    # If a quiz is already in progress, redirect to the quiz page.
    if 'quiz_data' in session:
        course = session['quiz_data'].get('course')
        return redirect(url_for('quiz.quiz', course=course))
    
    from db import users_collection  # Import here to avoid circular dependencies
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user_id = session['user_id']
    user = users_collection.find_one({"user_id": user_id})
    if not user or not user.get("gpa"):
        return redirect(url_for('auth.form'))
    quiz_results = list(db.quiz_results.find({"user_id": user_id}))
    completed_courses = {result['course'] for result in quiz_results}
    courses = [
        {"name": "Mobile App Development", "description": "Build responsive and engaging mobile applications.", "completed": "Mobile App Development" in completed_courses},
        # {"name": "Cloud Computing", "description": "Learn to build and manage cloud-based systems.", "completed": "Cloud Computing" in completed_courses},
        {"name": "Machine Learning", "description": "Build intelligent systems using ML algorithms.", "completed": "Machine Learning" in completed_courses},
        {"name": "AI", "description": "Explore artificial intelligence concepts and applications.", "completed": "AI" in completed_courses}
    ]
    return render_template('select_course.html', courses=courses)

@quiz_bp.route('/quiz')
def quiz():
    course = request.args.get('course')
    if not course:
        return "Invalid request: Course missing", 400

    # Retrieve quiz data from the session.
    quiz_data = session.get('quiz_data')
    if not quiz_data or quiz_data.get('course') != course:
        print("Quiz data missing or invalid. Redirecting to select_course.")
        return redirect(url_for('quiz.select_course'))

    # Determine current section.
    current_section = quiz_data.get('current_section', 'aptitude')

    # Select questions and set a time limit based on section.
    if current_section == 'aptitude':
        questions = quiz_data.get('aptitude_questions', [])
        time_limit = 10 * 60  # 10 minutes
    elif current_section == 'technical':
        questions = quiz_data.get('technical_questions', [])
        time_limit = 15 * 60  # 15 minutes
    else:
        return "Invalid section", 400

    print("Selected Course:", course)
    print("Questions for Template:", questions)
    return render_template(
        'quiz.html',
        selected_course=course,
        questions=questions,
        section=current_section,
        time_limit=time_limit
    )

@quiz_bp.route('/start_quiz', methods=['POST'])
def start_quiz():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    # Only generate new quiz data if it does not already exist.
    if 'quiz_data' not in session:
        data = request.get_json()
        course = data.get('course')
        if not course:
            return jsonify({"error": "Course is required"}), 400
        
        course = course.strip()  # Remove extra spaces
        
        print("Starting quiz for course:", course)

        # Use exact matching to fetch questions.
        aptitude_questions = list(quiz_questions_collection.aggregate([
            {'$match': {"course": course, "section": "aptitude"}},
            {'$sample': {'size': 10}}
        ]))
        aptitude_questions = [serialize_question(q) for q in aptitude_questions]

        technical_questions = list(quiz_questions_collection.aggregate([
            {'$match': {"course": course, "section": "technical"}},
            {'$sample': {'size': 1}}
        ]))
        technical_questions = [serialize_question(q) for q in technical_questions]

        print("Fetched aptitude questions:", aptitude_questions)
        print("Fetched technical questions:", technical_questions)

        # Initialize quiz_data in the session with breakdown counters.
        session['quiz_data'] = {
            "course": course,
            "aptitude_questions": aptitude_questions,
            "technical_questions": technical_questions,
            "aptitude_score": 0,
            "technical_score": 0,
            "score": 0,               # Overall score
            "current_question": 0,    # For step-by-step answer submissions
            "current_section": "aptitude",
            "start_time": time.time(),
            "beginner_correct": 0,
            "intermediate_correct": 0,
            "expert_correct": 0
        }
    
    return jsonify({"redirect": url_for('quiz.quiz', course=session['quiz_data']['course'])})

@quiz_bp.route('/quiz/answer', methods=['POST'])
def submit_answer():
    if request.headers.get('Content-Type') != 'application/json':
        return jsonify({"error": "Content-Type must be application/json"}), 400

    data = request.get_json()
    answer = data.get('answer')
    question_id = data.get('question_id')
    if not answer or not question_id:
        return jsonify({"error": "Missing answer or question_id"}), 400

    quiz_data = session.get('quiz_data')
    if not quiz_data:
        return jsonify({"error": "Quiz not started"}), 400

    current_question = quiz_data.get('current_question', 0)
    aptitude_questions = quiz_data.get('aptitude_questions', [])
    technical_questions = quiz_data.get('technical_questions', [])

    if current_question < len(aptitude_questions):
        correct_answer = aptitude_questions[current_question]['correct_answer']
        if answer == correct_answer:
            # Optionally update score here, though breakdown is handled separately.
            quiz_data['score'] = quiz_data.get('score', 0) + 1
    else:
        tech_index = current_question - len(aptitude_questions)
        if tech_index < len(technical_questions):
            technical_question = technical_questions[tech_index]
            if technical_question['type'] == 'coding':
                try:
                    submission_result = submit_code(
                        source_code=answer,
                        language_id=technical_question['language_id'],
                        stdin=""
                    )
                    result = get_result(submission_result)
                    if result and result.get('status', {}).get('description') == 'Accepted':
                        quiz_data['score'] = quiz_data.get('score', 0) + 5
                except Exception as e:
                    print(f"Error in Judge0 submission: {e}")
                    return jsonify({"error": "Failed to submit code to Judge0"}), 500
            else:
                if answer.lower() == technical_question['correct_answer'].lower():
                    quiz_data['score'] = quiz_data.get('score', 0) + 5
        else:
            return jsonify({"error": "No technical question available"}), 400

    quiz_data['current_question'] = current_question + 1
    session['quiz_data'] = quiz_data
    return jsonify({"message": "Answer submitted", "score": quiz_data['score']})

@quiz_bp.route('/submit_aptitude', methods=['POST'])
def submit_aptitude():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    quiz_data = session.get('quiz_data')
    if not quiz_data:
        return jsonify({"error": "Quiz not started"}), 400

    data = request.get_json()
    beginner_correct = 0
    intermediate_correct = 0

    # Loop through all aptitude questions and update breakdown counts.
    for question in quiz_data.get('aptitude_questions', []):
        answer = data.get(f"question_{question['_id']}")
        if answer == question['correct_answer']:
            # Retrieve the difficulty; default to 'beginner' if not provided.
            raw_diff = question.get('difficulty')
            if raw_diff is None or raw_diff.strip() == "":
                difficulty = "beginner"
            else:
                difficulty = raw_diff.strip().lower()
            # Use containment check to handle cases like "Beginner Level" etc.
            if "beginner" in difficulty:
                beginner_correct += 1
            elif "intermediate" in difficulty:
                intermediate_correct += 1
            else:
                # If difficulty is unknown, default to beginner.
                beginner_correct += 1

    # Update the session data with the breakdown and overall score.
    total = beginner_correct + intermediate_correct
    quiz_data['aptitude_score'] = total
    quiz_data['beginner_correct'] = beginner_correct
    quiz_data['intermediate_correct'] = intermediate_correct
    quiz_data['current_section'] = 'technical'
    session['quiz_data'] = quiz_data
    
    return jsonify({
        "redirect": url_for('quiz.quiz', course=quiz_data['course'], section='technical')
    })

@quiz_bp.route('/submit_technical', methods=['POST'])
def submit_technical():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    quiz_data = session.get('quiz_data')
    if not quiz_data or quiz_data.get('current_section') != 'technical':
        return jsonify({"error": "Quiz not started"}), 400

    data = request.get_json()
    technical_questions = quiz_data.get('technical_questions', [])
    if not technical_questions:
        return jsonify({"error": "No technical questions available"}), 400

    question = technical_questions[0]
    answer_key = f"question_{question['_id']}"
    answer = data.get(answer_key)
    score = 0
    expert_correct = 0

    if question['type'] == 'coding':
        try:
            test_case = question.get('test_cases', [])[0]
            stdin_value = test_case.get('stdin', '')
            expected_output = test_case.get('expected_output', '')
            submission_result = submit_code(
                source_code=answer,
                language_id=question['language_id'],
                stdin=stdin_value,
                expected_output=expected_output
            )
            result = get_result(submission_result)
            if result and result.get('status', {}).get('id') == 3:
                actual_output = result.get('stdout', '').strip()
                if actual_output == expected_output.strip():
                    score = 10
                    expert_correct = 1
            else:
                print("Execution failed. Status:", result.get('status', {}).get('description'))
        except Exception as e:
            print(f"Error submitting code: {e}")
            return jsonify({"error": "Code evaluation failed"}), 500
    else:
        if answer.lower() == question['correct_answer'].lower():
            score = 10
            expert_correct = 1

    quiz_data['technical_score'] = score
    quiz_data['expert_correct'] = expert_correct
    session['quiz_data'] = quiz_data

    final_score = (quiz_data.get('aptitude_score', 0) + quiz_data.get('technical_score', 0)) / 2
    if final_score <= 4:
        level = "Beginner"
    elif final_score <= 7:
        level = "Intermediate"
    else:
        level = "Expert"

    recommended_modules = list(db.modules.find(
        {"Course": quiz_data['course'], "Skill_level": level},
        {"Module": 1, "_id": 0}
    ))
    recommended_modules = [module['Module'] for module in recommended_modules] if recommended_modules else []

    # Insert a new document for every quiz attempt including breakdown counts.
    db.quiz_results.insert_one({
        "user_id": session['user_id'],
        "course": quiz_data['course'],
        "aptitude_score": quiz_data.get('aptitude_score', 0),
        "technical_score": quiz_data.get('technical_score', 0),
        "final_score": final_score,
        "beginner_correct": quiz_data.get('beginner_correct', 0),
        "intermediate_correct": quiz_data.get('intermediate_correct', 0),
        "expert_correct": quiz_data.get('expert_correct', 0),
        "recommended_modules": recommended_modules,
        "timestamp": time.time()
    })

    session.pop('quiz_data', None)
    return jsonify({
        "redirect": url_for('modules.results', course=quiz_data['course'])
    })

@quiz_bp.route('/quiz/end', methods=['GET'])
def end_quiz():
    quiz_data = session.get('quiz_data')
    if not quiz_data:
        return jsonify({"error": "Quiz not started"}), 400
    elapsed_time = time.time() - quiz_data.get('start_time', time.time())
    final_score = quiz_data.get('score', 0)
    session.pop('quiz_data', None)
    return jsonify({"message": "Quiz ended", "final_score": final_score, "time_taken": elapsed_time})
