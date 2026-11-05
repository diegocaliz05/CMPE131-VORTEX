Setup:

1. Install python at python.org  
   - Say yes to "Enable/Add Python to PATH" if prompted  
   - Complete Python install, and restart VS Code after installation  

py --version #type in terminal to verify python is installed  

2. Clone the Repository  

git clone https://github.com/diegocaliz05/CMPE131-VORTEX.git  
cd CMPE131-VORTEX  

3. Install dependencies:  

py -m pip install -r requirements.txt #copy and paste the line into terminal  

4. Run the app:  

py app.py #starts local flask server  

5. Open:  

http://127.0.0.1:5000  

Team Development Workflow:

1. Before starting new work:  

git checkout main  
git pull  
git checkout -b feature-name #see examples below  

examples:  
git checkout -b feature-login  
git checkout -b feature-calendar  
git checkout -b feature-database  

2. After making changes:  

git add .  
git commit -m "Describe what you changed"  
git push -u origin feature-name  

Then create a Pull Request on GitHub to merge your branch into main.  

***IMPORTANT: DO NOT make major feature changes directly on main!***
