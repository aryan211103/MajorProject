from pymongo import MongoClient
import json

client = MongoClient("mongodb+srv://rolston20:NCc5P9VkSfrafZOs@course.vynlz.mongodb.net/?retryWrites=true&w=majority&appName=course")
db = client["recommendation_system"]
collection = db["quiz_questions"]

with open("questions.json") as file:
    data = json.load(file)
    collection.insert_many(data)  # Or insert_many(data) for multiple courses