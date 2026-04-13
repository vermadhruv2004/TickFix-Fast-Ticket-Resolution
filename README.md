# TickFix - Smart Ticket Resolution (formerly ResolveXX)

TickFix is a Flask-based customer support ticketing system that allows customers to submit support tickets and agents/admins to manage, prioritize, and resolve them.

## Features

- Customer registration and authentication
- Ticket submission with automatic priority detection
- Agent dashboard for ticket management
- Admin interface for system administration
- SQLite database for data persistence

## Setup

1. **Clone the repository**
   ```bash
   # The repository name may still be ResolveXX, but the application is TickFix
   git clone https://github.com/Samarth-0026/ResolveXX.git
   cd ResolveXX
   ```

2. **Create and activate a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   Create a `.env` file with the following content:
   ```
   SECRET_KEY=your-secret-key-here
   DATABASE_URI=sqlite:///instance/tickfix.db
   ```

5. **Initialize the database**
   ```bash
   flask shell
   >>> from app import db
   >>> db.create_all()
   >>> exit()
   ```

6. **Run the development server**
   ```bash
   flask run
   ```

7. **Access the application**
   - Customer interface: http://localhost:5000/
   - Agent login: http://localhost:5000/agent/login
   - Admin login: http://localhost:5000/agent/login (use an agent account with admin privileges)

## Project Structure

- `app.py` - Main application file
- `templates/` - HTML templates
- `static/` - Static files (CSS, JS, images)
- `instance/` - Database and other instance-specific files (not in version control)
- `requirements.txt` - Python dependencies

## License

This project is licensed under the MIT License.
