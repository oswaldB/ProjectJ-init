
import os
import shutil

def duplicate_py_to_md():
    # Walk through all directories
    for root, dirs, files in os.walk('.'):
        # Skip the .git directory if it exists
        if '.git' in dirs:
            dirs.remove('.git')
            
        # Find all .py files
        for file in files:
            if file.endswith('.py'):
                # Get full path
                py_path = os.path.join(root, file)
                # Create md path
                md_path = os.path.join(root, file[:-3] + '.md')
                # Copy file
                shutil.copy2(py_path, md_path)
                print(f"Created: {md_path}")

if __name__ == '__main__':
    duplicate_py_to_md()
