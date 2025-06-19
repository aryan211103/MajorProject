# db.py
from pymongo import MongoClient

client = MongoClient('mongodb+srv://rolston20:NCc5P9VkSfrafZOs@course.vynlz.mongodb.net/?retryWrites=true&w=majority&appName=course')
db = client['recommendation_system']
users_collection = db['users']
quiz_results_collection = db['quiz_results']
quiz_questions_collection = db['quiz_questions']
