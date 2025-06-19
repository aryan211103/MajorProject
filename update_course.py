import pandas as pd

# Cybersecurity data
cybersecurity_data = [
    ["Cybersecurity", "Introduction to Cybersecurity", "Easy"],
    ["Cybersecurity", "Basics of Network Security", "Easy"],
    ["Cybersecurity", "Overview of Cyber Threats", "Easy"],
    ["Cybersecurity", "Fundamentals of Cryptography", "Easy"],
    ["Cybersecurity", "Introduction to Security Policies", "Easy"],
    ["Cybersecurity", "Web Application Security Basics", "Medium"],
    ["Cybersecurity", "Introduction to Penetration Testing", "Medium"],
    ["Cybersecurity", "Cyber Incident Response", "Medium"],
    ["Cybersecurity", "Identity and Access Management", "Medium"],
    ["Cybersecurity", "Risk Assessment Fundamentals", "Medium"],
    ["Cybersecurity", "Advanced Penetration Testing", "Hard"],
    ["Cybersecurity", "Malware Analysis and Reverse Engineering", "Hard"],
    ["Cybersecurity", "Cloud Security Essentials", "Hard"],
    ["Cybersecurity", "Advanced Network Defense Techniques", "Hard"],
    ["Cybersecurity", "Incident Handling and Forensics", "Hard"],
    ["Cybersecurity", "Ethical Hacking Techniques", "Expert"],
    ["Cybersecurity", "Zero Trust Security Models", "Expert"],
    ["Cybersecurity", "Advanced Cryptography Applications", "Expert"],
    ["Cybersecurity", "AI in Cybersecurity", "Expert"],
    ["Cybersecurity", "Cybersecurity for Critical Infrastructure", "Expert"],
]

# Load existing data
existing_file = "all_courses_expanded_modules.csv"  # Replace with the path to your existing file
df_existing = pd.read_csv(existing_file)

# Create a DataFrame for the new data
df_cybersecurity = pd.DataFrame(cybersecurity_data, columns=["Course", "Module", "Difficulty"])

# Combine the existing and new data
df_full = pd.concat([df_existing, df_cybersecurity], ignore_index=True)

# Save the updated dataset
updated_file = "all_courses_cybersecurity_expanded_modules.csv"
df_full.to_csv(updated_file, index=False)

print(f"Updated file saved to: {updated_file}")
