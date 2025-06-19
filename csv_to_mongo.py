import csv
import pymongo
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

# Connect to MongoDB (adjust the URI if you're using a remote MongoDB instance)
client = pymongo.MongoClient("mongodb+srv://rolston20:NCc5P9VkSfrafZOs@course.vynlz.mongodb.net/?retryWrites=true&w=majority&appName=course")

# Create a new database (if not already existing) called recommendation_system
db = client["recommendation_system"]

# Create a new collection for modules
modules_collection = db["modules"]

# Path to your CSV file
csv_file_path = 'Technical_course_modules_links.csv'
# Read the CSV file and insert each row as a document into MongoDB
with open(csv_file_path, mode='r') as file:
    csv_reader = csv.DictReader(file)
    
    # Clear the existing collection (optional: in case you're running this multiple times)
    modules_collection.delete_many({})
    
    # Iterate through each row in the CSV and insert it into the MongoDB collection
    for row in csv_reader:
        # Convert the row into a dictionary and insert into the collection
        modules_collection.insert_one({
            "Course": row['Course'],
            "Module": row['Module'],
            "Links": row['Links'],
            "Difficulty": row['Difficulty'],
            "Skill_level": row['Skill_level'],  # Beginner, Intermediate, or Expert
        })

print("Data successfully inserted into MongoDB.")
