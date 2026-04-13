from flask import Flask, render_template, request, redirect, url_for, session, flash, json
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from threading import Lock
import os
from sqlalchemy.exc import IntegrityError
from sqlalchemy import case, event, func
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
app = Flask(__name__, template_folder='templates')
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-here')

# Database setup
# Build absolute default path for SQLite to avoid relative path issues
_default_db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'tickfix.db')
os.makedirs(os.path.dirname(_default_db_path), exist_ok=True)
_default_db_uri = f"sqlite:///{_default_db_path}"
_env_db_uri = os.getenv('DATABASE_URI')
if _env_db_uri and _env_db_uri.startswith('sqlite:///'):
    _rel_path = _env_db_uri[len('sqlite:///'):]
    if not os.path.isabs(_rel_path):
        _abs_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), _rel_path)
        os.makedirs(os.path.dirname(_abs_path), exist_ok=True)
        _env_db_uri = f"sqlite:///{_abs_path}"
app.config['SQLALCHEMY_DATABASE_URI'] = _env_db_uri or _default_db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
mutex = Lock()

# --- Models (Strictly Separate) ---
class Customer(db.Model):
    customer_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    unique_id = db.Column(db.String(50), unique=True, nullable=False)
    address = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    
    def __repr__(self):
        return f"<Customer {self.customer_id}: {self.name}>"

class Agent(db.Model):
    agent_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    
    def __repr__(self):
        return f"<Agent {self.agent_id}: {self.name}>"

class Ticket(db.Model):
    ticket_id = db.Column(db.Integer, primary_key=True)
    issue_description = db.Column(db.String(500), nullable=False)
    priority = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), default='Pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)
    
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.customer_id'), nullable=False)
    agent_id = db.Column(db.Integer, db.ForeignKey('agent.agent_id'))
    
    customer = db.relationship('Customer', backref='tickets')
    agent = db.relationship('Agent', backref='assigned_tickets')
    
    def __repr__(self):
        return f"<Ticket {self.ticket_id}: {self.status}>"

# --- Utility Functions (Separate Session Management) ---
def auto_detect_priority(issue_description):
    """
    Automatically detect priority based on keywords in the issue description.
    Payment and refund issues are always urgent, others are normal.
    Returns 'Urgent' or 'Normal' priority.
    """
    issue_lower = issue_description.lower()
    
    # Payment and refund related keywords - always urgent
    payment_refund_keywords = [
        'payment', 'refund', 'money', 'charge', 'charged', 'billing', 'bill',
        'invoice', 'transaction', 'credit card', 'debit card', 'bank',
        'paypal', 'payment failed', 'payment error', 'double charge', 'overcharged',
        'unauthorized charge', 'wrong amount', 'refund request', 'money back',
        'subscription', 'auto renewal', 'cancel subscription'
    ]
    
    # Check if any payment/refund keywords are present
    for keyword in payment_refund_keywords:
        if keyword in issue_lower:
            return 'Urgent'
    
    # If no payment/refund keywords found, default to Normal
    return 'Normal'

def apply_priority_before_insert(mapper, connection, target):
    computed = auto_detect_priority(target.issue_description or "")
    # Always enforce Urgent for payment/refund issues
    if computed == 'Urgent' and target.priority != 'Urgent':
        target.priority = 'Urgent'
    else:
        # Normalize/validate other values
        if not target.priority or target.priority not in ('Urgent', 'Normal'):
            target.priority = computed

event.listen(Ticket, 'before_insert', apply_priority_before_insert)

def get_customer_session():
    # Only checks for customer_id in session
    if 'customer_id' in session:
        return Customer.query.get(session['customer_id'])
    return None

def get_agent_session():
    # Only checks for agent_id in session
    if 'agent_id' in session:
        return Agent.query.get(session['agent_id'])
    return None

# --- Main Routes ---
@app.route('/')
def home():
    return render_template('dashboard.html') 

@app.route('/logout')
def logout():
    # Clears session regardless of role
    session.clear()
    flash('You have been logged out.')
    return redirect(url_for('home'))

# ------------------- Customer Management (Only Customers) -------------------

@app.route('/customer/register', methods=['GET', 'POST'])
def customer_register():
    if request.method == 'POST':
        # Creates only a Customer record
        try:
            new_customer = Customer(
                name=request.form['name'],
                unique_id=request.form['unique_id'],
                address=request.form['address'],
                phone=request.form['phone'],
                email=request.form['email'],
                password=request.form['password'] 
            )
            db.session.add(new_customer)
            db.session.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('customer_login'))
        
        except IntegrityError:
            db.session.rollback() 
            flash('Error: This email or Unique ID is already registered. Please try a different one.', 'danger')
            return redirect(url_for('customer_register'))
            
    return render_template('customer/register.html')

@app.route('/customer/login', methods=['GET', 'POST'])
def customer_login():
    if request.method == 'POST':
        # Queries only the Customer table
        customer = Customer.query.filter_by(email=request.form['email']).first()
        if customer and customer.password == request.form['password']:
            session['customer_id'] = customer.customer_id # Sets customer session key
            flash('Login successful!')
            return redirect(url_for('customer_dashboard'))
        flash('Invalid email or password.', 'danger')
    return render_template('customer/login.html')

@app.route('/customer/dashboard')
def customer_dashboard():
    customer = get_customer_session()
    if not customer:
        return redirect(url_for('customer_login'))
    
    tickets = Ticket.query.filter_by(customer_id=customer.customer_id).order_by(Ticket.created_at.desc()).all()
    return render_template('customer/dashboard.html', customer=customer, tickets=tickets)

@app.route('/customer/new_ticket', methods=['GET', 'POST'])
def new_ticket():
    customer = get_customer_session()
    if not customer:
        return redirect(url_for('customer_login'))

    if request.method == 'POST':
        issue_description = request.form['issue_description']
        auto_priority = auto_detect_priority(issue_description)
        
        new_ticket = Ticket(
            customer_id=customer.customer_id,
            issue_description=issue_description,
            priority=auto_priority,
            status='Pending'
        )
        db.session.add(new_ticket)
        db.session.commit()
        flash(f'Ticket {new_ticket.ticket_id} created successfully! Priority automatically set to: {auto_priority}', 'success')
        
        return render_template('customer/confirmation.html')
    
    return render_template('customer/new_ticket.html')

# ------------------- Agent Management (Only Agents) -------------------

@app.route('/agent/register', methods=['GET', 'POST'])
def agent_register():
    if request.method == 'POST':
        # Creates only an Agent record
        try:
            new_agent = Agent(
                name=request.form['name'],
                email=request.form['email'],
                password=request.form['password']
            )
            db.session.add(new_agent)
            db.session.commit()
            flash('Agent registration successful! Please log in.', 'success')
            return redirect(url_for('agent_login'))
        except IntegrityError:
            db.session.rollback() 
            flash('Error: This email is already registered for an agent.', 'danger')
            return redirect(url_for('agent_register'))
            
    return render_template('agent/register.html')

@app.route('/agent/login', methods=['GET', 'POST'])
def agent_login():
    if request.method == 'POST':
        # Queries only the Agent table
        email = request.form['email'].strip()
        password = request.form['password']
        agent = Agent.query.filter(func.trim(Agent.email) == email).first()
        if agent and agent.password == password:
            session['agent_id'] = agent.agent_id # Sets agent session key
            if agent.is_admin:
                return redirect(url_for('admin_dashboard'))
            
            flash('Login successful!')
            return redirect(url_for('agent_dashboard'))
        flash('Invalid email or password.', 'danger')
    return render_template('agent/login.html')

@app.route('/agent/dashboard')
def agent_dashboard():
    agent = get_agent_session()
    if not agent:
        return redirect(url_for('agent_login'))
    
    tickets = Ticket.query.filter_by(status='Pending').order_by(
        case((Ticket.priority == 'Urgent', 1), else_=0).desc(),
        Ticket.created_at.asc()
    ).all()
    
    customers = Customer.query.all()
    
    return render_template('agent/dashboard.html', agent=agent, tickets=tickets, customers=customers)

@app.route('/agent/pick_ticket', methods=['POST'])
def pick_ticket():
    agent = get_agent_session()
    if not agent:
        return redirect(url_for('agent_login'))
    
    with mutex:
        ticket = Ticket.query.filter_by(status='Pending').order_by(
            case((Ticket.priority == 'Urgent', 1), else_=0).desc(),
            Ticket.created_at.asc()
        ).first()
        
        if ticket:
            ticket.status = 'In-progress'
            ticket.agent_id = agent.agent_id
            db.session.commit()
            flash(f'Ticket {ticket.ticket_id} picked successfully!', 'success')
            return redirect(url_for('ticket_detail', ticket_id=ticket.ticket_id))
        else:
            flash('No pending tickets available right now.', 'info')
            return redirect(url_for('agent_dashboard'))

@app.route('/agent/ticket/<int:ticket_id>')
def ticket_detail(ticket_id):
    if 'agent_id' not in session:
        return redirect(url_for('agent_login'))
    
    ticket = Ticket.query.get_or_404(ticket_id)
    customer = ticket.customer
    
    return render_template('agent/ticket_detail.html', ticket=ticket, customer=customer)

@app.route('/agent/resolve_ticket/<int:ticket_id>', methods=['POST'])
def resolve_ticket(ticket_id):
    if 'agent_id' not in session:
        return redirect(url_for('agent_login'))
    
    ticket = Ticket.query.get_or_404(ticket_id)
    ticket.status = 'Resolved'
    ticket.resolved_at = datetime.utcnow()
    db.session.commit()
    flash('Ticket resolved!', 'success')
    
    return redirect(url_for('agent_dashboard'))

# ------------------- Admin Dashboard -------------------
@app.route('/admin/dashboard')
def admin_dashboard():
    agent = get_agent_session()
    if not agent or not agent.is_admin:
        flash('Unauthorized access. Admin privileges required.', 'danger')
        return redirect(url_for('home'))

    tickets = Ticket.query.all()
    customers = Customer.query.all()
    agents = Agent.query.all()
    
    # --- Analytics Calculations ---
    total_resolution_seconds = 0
    agent_workload = {agent.agent_id: {'name': agent.name, 'resolved_count': 0, 'in_progress_count': 0} for agent in agents}
    resolved_tickets_count = 0

    for ticket in tickets:
        if ticket.status == 'Resolved' and ticket.resolved_at and ticket.created_at:
            time_diff = ticket.resolved_at - ticket.created_at
            total_resolution_seconds += time_diff.total_seconds()
            resolved_tickets_count += 1
            if ticket.agent_id in agent_workload:
                agent_workload[ticket.agent_id]['resolved_count'] += 1
        
        if ticket.status == 'In-progress' and ticket.agent_id in agent_workload:
            agent_workload[ticket.agent_id]['in_progress_count'] += 1

    if resolved_tickets_count > 0:
        avg_seconds = total_resolution_seconds / resolved_tickets_count
        hours, remainder = divmod(avg_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        average_resolution_time = f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"
    else:
        average_resolution_time = "N/A (No tickets resolved)"
    
    return render_template(
        'admin/dashboard.html', 
        tickets=tickets, 
        customers=customers, 
        agents=agents,
        average_resolution_time=average_resolution_time,
        total_resolved_tickets=resolved_tickets_count,
        agent_workload=agent_workload
    )


@app.route('/admin/delete_ticket/<int:ticket_id>', methods=['POST'])
def admin_delete_ticket(ticket_id):
    """Admin-only: delete a ticket from the system."""
    admin_agent = get_agent_session()
    if not admin_agent or not admin_agent.is_admin:
        flash('Unauthorized action. Admin privileges required.', 'danger')
        return redirect(url_for('home'))

    ticket = Ticket.query.get_or_404(ticket_id)
    db.session.delete(ticket)
    db.session.commit()
    flash(f'Ticket {ticket_id} deleted.', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/delete_customer/<int:customer_id>', methods=['POST'])
def admin_delete_customer(customer_id):
    """Admin-only: delete a customer and all of their tickets."""
    admin_agent = get_agent_session()
    if not admin_agent or not admin_agent.is_admin:
        flash('Unauthorized action. Admin privileges required.', 'danger')
        return redirect(url_for('home'))

    customer = Customer.query.get_or_404(customer_id)

    # Remove all tickets belonging to this customer first to avoid
    # foreign key constraint issues and keep data consistent.
    Ticket.query.filter_by(customer_id=customer.customer_id).delete(synchronize_session=False)

    db.session.delete(customer)
    db.session.commit()
    flash(f'Customer {customer_id} and their tickets were deleted.', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/delete_agent/<int:agent_id>', methods=['POST'])
def admin_delete_agent(agent_id):
    """Admin-only: delete an agent. Tickets are kept but unassigned.

    - Any tickets assigned to this agent will have agent_id cleared.
    - Tickets that were In-progress are returned to the Pending queue.
    """
    admin_agent = get_agent_session()
    if not admin_agent or not admin_agent.is_admin:
        flash('Unauthorized action. Admin privileges required.', 'danger')
        return redirect(url_for('home'))

    agent_obj = Agent.query.get_or_404(agent_id)

    # Prevent an admin from deleting their own account while logged in.
    if agent_obj.agent_id == admin_agent.agent_id:
        flash('You cannot delete your own admin account while logged in.', 'danger')
        return redirect(url_for('admin_dashboard'))

    # Unassign tickets from this agent but keep the ticket history.
    tickets = Ticket.query.filter_by(agent_id=agent_obj.agent_id).all()
    for t in tickets:
        if t.status == 'In-progress':
            t.status = 'Pending'
        t.agent_id = None

    db.session.delete(agent_obj)
    db.session.commit()
    flash(f'Agent {agent_id} deleted. Their tickets were returned to the queue or left resolved.', 'success')
    return redirect(url_for('admin_dashboard'))


if __name__ == '__main__':
    with app.app_context():
        db.create_all() 
        
        # --- Default Admin Creation ---
        if Agent.query.filter(func.trim(Agent.email) == 'admin@tickfix.app').first() is None:
            default_admin = Agent(
                name='Admin TickFix',
                email='admin@tickfix.app',
                password='admin',  
                is_admin=True     
            )
            db.session.add(default_admin)
            db.session.commit()
            print("Default Admin created: admin@tickfix.app / admin")
        # ---------------------------
        
    host = os.environ.get('FLASK_RUN_HOST', '127.0.0.1')
    port = int(os.environ.get('FLASK_RUN_PORT') or os.environ.get('PORT') or 5050)
    debug = os.environ.get('FLASK_DEBUG', 'True').lower() in ('1', 'true', 'yes')
    app.run(host=host, port=port, debug=debug)