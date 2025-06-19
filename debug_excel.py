import pandas as pd

# Load the Excel files for debugging column names
df_university = pd.read_excel("top_50_engineering_schools.xlsx", engine="openpyxl")
df_degree = pd.read_excel("masters_degree.xlsx", engine="openpyxl")

print("University Columns:", df_university.columns)
print("Degree Columns:", df_degree.columns)
