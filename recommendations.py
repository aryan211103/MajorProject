import pandas as pd
from pymongo import MongoClient
from sklearn.metrics.pairwise import cosine_similarity

# Connect to MongoDB
client = MongoClient(
    'mongodb+srv://rolston20:NCc5P9VkSfrafZOs@course.vynlz.mongodb.net/?retryWrites=true&w=majority&appName=course'
)
db = client['recommendation_system']

def get_user_ratings():
    """Fetches user ratings from MongoDB for collaborative filtering."""
    ratings = list(db.user_module_ratings.find())
    if not ratings:
        return None

    ratings_df = pd.DataFrame(ratings)
    if 'rating' not in ratings_df.columns:
        raise KeyError("The 'rating' field is missing in the user_module_ratings collection.")
    return ratings_df

def get_module_similarity_matrix(ratings_df):
    """Generates a user-user similarity matrix based on ratings data."""
    user_item_matrix = ratings_df.pivot_table(index='user_id', columns='module_name', values='rating').fillna(0)
    similarity_matrix = cosine_similarity(user_item_matrix)
    return pd.DataFrame(similarity_matrix, index=user_item_matrix.index, columns=user_item_matrix.index)

def recommend_modules(user_id, skill_level, course_name):
    """Recommends modules using content-based and collaborative filtering."""
    try:
        # Load course dataset
        courses_df = pd.read_csv('Technical_course_modules.csv')

        # Normalize the Difficulty column
        difficulty_mapping = {
            'Easy': 1,
            'Medium': 2,
            'Hard': 3,
            'M_Expert': 4  # Highest difficulty level
        }
        courses_df['Difficulty'] = courses_df['Difficulty'].map(difficulty_mapping)
        courses_df = courses_df.dropna(subset=['Difficulty'])  # Drop invalid rows

        # Filter by course name
        course_modules = courses_df[courses_df['Course'] == course_name]
        if course_modules.empty:
            print(f"No modules found for course: {course_name}")
            return []

    except FileNotFoundError:
        print("Error: Course dataset file not found.")
        return []
    except Exception as e:
        print(f"Error processing dataset: {e}")
        return []

    # Skill level mapping
    skill_mapping = {'beginner': (1, 4), 'intermediate': (2, 4), 'expert': (3, 4)}
    skill_range = skill_mapping.get(skill_level.lower(), (1, 4))

    # Content-based filtering
    filtered_modules = course_modules[
        (course_modules['Difficulty'] >= skill_range[0]) &
        (course_modules['Difficulty'] <= skill_range[1])
    ]
    fallback_recommendations = (
        filtered_modules['Module'].tolist()
        if not filtered_modules.empty
        else course_modules['Module'].sample(min(5, len(course_modules))).tolist()
    )

    # Collaborative filtering logic
    try:
        ratings_df = get_user_ratings()
        if ratings_df is None:
            print("No user ratings found. Using fallback recommendations.")
            return fallback_recommendations

        similarity_matrix = get_module_similarity_matrix(ratings_df)

        if user_id not in similarity_matrix.index:
            print("User ID not found in similarity matrix. Using fallback recommendations.")
            return fallback_recommendations

        # Find similar users
        similar_users = similarity_matrix.loc[user_id].sort_values(ascending=False)[1:6].index
        similar_users_ratings = ratings_df[ratings_df['user_id'].isin(similar_users)]
        recommended_modules = similar_users_ratings['module_name'].unique()

        # Filter recommendations by skill level and course
        collaborative_filtered_modules = course_modules[
            (course_modules['Module'].isin(recommended_modules)) &
            (course_modules['Difficulty'] >= skill_range[0]) &
            (course_modules['Difficulty'] <= skill_range[1])
        ]

        if not collaborative_filtered_modules.empty:
            return collaborative_filtered_modules['Module'].tolist()

    except Exception as e:
        print(f"Error during collaborative filtering: {e}")

    # Return fallback recommendations if collaborative filtering fails
    return fallback_recommendations
