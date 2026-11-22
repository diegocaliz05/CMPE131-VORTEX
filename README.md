# Vortex club calendar

## Run the project on Windows

Extract the ZIP. Open the folder containing app.py in VS Code. In its terminal, run:

```powershell
py -m pip install -r requirements.txt
py app.py
```

Open http://127.0.0.1:5000. On macOS or Linux, use python3 instead of py.
On first launch, Vortex creates vortex.db beside app.py and prepares local demo accounts.

| Account | Email | Password |
| --- | --- | --- |
| Robotics officer | officer@vortex.edu | password123 |
| Chess officer | chess.officer@vortex.edu | password123 |
| Robotics member | member@vortex.edu | password123 |

Sign in as an officer to create an event. It starts as tentative. Confirm it,
then sign in as the member in a private browser window to check the calendar and
notifications. A new self-registered account can browse confirmed events.
Use List view or Month view and filter by keyword, club, date, room, or event type.
The list shows 25 events per page and keeps the active filters when you move between pages. In Notifications, select Unread only or Mark all as read to manage your inbox.
Event and account data persist across restarts. Stop the server with Ctrl+C.

## Run tests

From the same folder:

```powershell
py -m unittest discover -s tests -t . -v
```

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
