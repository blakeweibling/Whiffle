import os

directory = r"C:\Users\bweibling\Documents\GitHub\Whiffle\11.4"  # Raw string with 'r'
# OR: directory = "C:\\Users\\bweibling\\Documents\\GitHub\\Whiffle\\11.4"  # Escaped backslashes
# OR: directory = "C:/Users/bweibling/Documents/GitHub/Whiffle/11.4"  # Forward slashes

search_terms = ["score keeping", "scorekeeping"]

for filename in os.listdir(directory):
    if filename.endswith(".txt"):  # Adjust for your file types
        with open(os.path.join(directory, filename), "r") as file:
            content = file.read()
            for term in search_terms:
                if term in content:
                    print(f"Found '{term}' in {filename}")
