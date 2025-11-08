import pandas as pd

# Step 1: Load the dataset
df = pd.read_csv('malicious_phish.csv')  # change to your filename

# Step 2: Check total rows
print("Total rows before:", len(df))

# Step 3: Reduce to 1000 records
df_sample = df.sample(n=1000, random_state=42)  # random 1000 rows for fairness

# Step 4: Save the smaller dataset
df_sample.to_csv('malicious_phish_1000.csv', index=False)

print("Reduced dataset saved as 'malicious_phish_1000.csv'")
print("Total rows after:", len(df_sample))
