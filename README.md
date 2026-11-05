# Setup

## 1. Install Python at python.org

- Say yes to **"Enable/Add Python to PATH"** if prompted.
- Complete Python install, and restart VS Code after installation.

Type this in the terminal to verify Python is installed:

```bash
py --version
```

## 2. Clone the Repository

```bash
git clone https://github.com/diegocaliz05/CMPE131-VORTEX.git
cd CMPE131-VORTEX
```

## 3. Install dependencies

Copy and paste this line into the terminal:

```bash
py -m pip install -r requirements.txt
```

## 4. Run the app

Starts the local Flask server:

```bash
py app.py
```

## 5. Open

```text
http://127.0.0.1:5000
```

# Team Development Workflow

## 1. Before starting new work

```bash
git checkout main
git pull
git checkout -b feature-name
```

See examples below:

```bash
git checkout -b feature-login
git checkout -b feature-calendar
git checkout -b feature-database
```

## 2. After making changes

```bash
git add .
git commit -m "Describe what you changed"
git push -u origin feature-name
```

Then create a Pull Request on GitHub to merge your branch into `main`.

**IMPORTANT: DO NOT make major feature changes directly on `main`!**
