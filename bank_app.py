from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from flask_sqlalchemy import SQLAlchemy
import matplotlib.pyplot as plt
import pandas as pd
from fpdf import FPDF
import io
import os
import base64
from datetime import datetime
from flask_mail import Mail, Message
from PyPDF2 import PdfWriter, PdfReader

app = Flask(__name__)
app.secret_key = 'securebankkey2025'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///intelligent_bank.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Flask-Mail config
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'admin@richardwambede.com'
app.config['MAIL_PASSWORD'] = 'wruzwcxeissvdqer'

mail = Mail(app)
db = SQLAlchemy(app)

# --- Models ---
class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    balance = db.Column(db.Float, default=0.0)
    transactions = db.relationship('Transaction', backref='customer', lazy=True)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(10), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/create_account', methods=['GET', 'POST'])
def create_account():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        if Customer.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return redirect(url_for('create_account'))
        new_customer = Customer(name=name, email=email)
        db.session.add(new_customer)
        db.session.commit()
        flash('Account created. Please login.', 'success')
        return redirect(url_for('home'))
    return render_template('create_account.html')

@app.route('/login', methods=['POST'])
def login():
    email = request.form['email']
    customer = Customer.query.filter_by(email=email).first()
    if customer:
        session['customer_id'] = customer.id
        return redirect(url_for('dashboard'))
    flash('Login failed. Email not found.', 'danger')
    return redirect(url_for('home'))

@app.route('/dashboard')
def dashboard():
    if 'customer_id' not in session:
        return redirect(url_for('home'))
    customer = Customer.query.get(session['customer_id'])
    return render_template('dashboard.html', customer=customer)

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))

@app.route('/deposit', methods=['POST'])
def deposit():
    amount = float(request.form['amount'])
    customer = Customer.query.get(session['customer_id'])
    customer.balance += amount
    db.session.add(Transaction(type='deposit', amount=amount, customer=customer))
    db.session.commit()
    flash('Deposit successful.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/withdraw', methods=['POST'])
def withdraw():
    amount = float(request.form['amount'])
    customer = Customer.query.get(session['customer_id'])
    if customer.balance >= amount:
        customer.balance -= amount
        db.session.add(Transaction(type='withdraw', amount=amount, customer=customer))
        db.session.commit()
        flash('Withdrawal successful.', 'success')
    else:
        flash('Insufficient balance.', 'danger')
    return redirect(url_for('dashboard'))

@app.route('/transactions')
def transactions():
    if 'customer_id' not in session:
        flash('Please log in to view your transactions.', 'warning')
        return redirect(url_for('home'))

    customer = Customer.query.get(session['customer_id'])
    txns = customer.transactions

    deposits = [t.amount for t in txns if t.type == 'deposit']
    withdrawals = [t.amount for t in txns if t.type == 'withdraw']

    fig1, ax1 = plt.subplots()
    ax1.pie([sum(deposits), sum(withdrawals)],
            labels=['Deposits', 'Withdrawals'], autopct='%1.1f%%')
    ax1.set_title('Your Financial Activity')
    buf1 = io.BytesIO()
    plt.savefig(buf1, format='png')
    buf1.seek(0)
    pie_chart = base64.b64encode(buf1.getvalue()).decode()
    plt.close()

    fig2, ax2 = plt.subplots()
    ax2.hist(deposits, bins=5, alpha=0.7, label='Deposits')
    ax2.hist(withdrawals, bins=5, alpha=0.7, label='Withdrawals')
    ax2.set_title('Transaction Distribution')
    ax2.legend()
    buf2 = io.BytesIO()
    plt.savefig(buf2, format='png')
    buf2.seek(0)
    hist_chart = base64.b64encode(buf2.getvalue()).decode()
    plt.close()

    return render_template(
        "transactions.html",
        transactions=txns,
        pie_chart=pie_chart,
        hist_chart=hist_chart
    )

@app.route('/email_report', methods=['POST'])
def email_report():
    if 'customer_id' not in session:
        flash('You must be logged in.', 'danger')
        return redirect(url_for('home'))

    customer = Customer.query.get(session['customer_id'])
    email = customer.email
    custom_password = request.form.get('pdf_password') or 'Bank2025Secure'

    data = [{
        'Date': t.timestamp.strftime('%Y-%m-%d %H:%M'),
        'Type': t.type.title(),
        'Amount ($)': f"{t.amount:.2f}"
    } for t in customer.transactions]
    df = pd.DataFrame(data)

    # Create Excel file
    excel_output = io.BytesIO()
    with pd.ExcelWriter(excel_output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Transactions')
    excel_output.seek(0)

    # Create and save PDF temporarily
    pdf = FPDF()
    pdf.add_page()
    if os.path.exists('static/logo.png'):
        pdf.image('static/logo.png', x=10, y=8, w=30)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(200, 10, txt="Mbale Intelligent Banking System", ln=True, align='C')
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"Transaction Report for {customer.name}", ln=True, align='C')
    pdf.ln(10)

    pdf.set_fill_color(200, 220, 255)
    pdf.cell(60, 10, "Date", border=1, fill=True)
    pdf.cell(60, 10, "Type", border=1, fill=True)
    pdf.cell(60, 10, "Amount ($)", border=1, fill=True)
    pdf.ln()
    for t in customer.transactions:
        pdf.cell(60, 10, t.timestamp.strftime('%Y-%m-%d %H:%M'), border=1)
        pdf.cell(60, 10, t.type.title(), border=1)
        pdf.cell(60, 10, f"${t.amount:.2f}", border=1)
        pdf.ln()

    # ✅ FIXED: Save + Encrypt PDF
    temp_path = 'temp_transaction_report.pdf'
    pdf.output(temp_path)
    with open(temp_path, 'rb') as f:
        reader = PdfReader(f)
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        writer.encrypt(custom_password)
        encrypted_pdf = io.BytesIO()
        writer.write(encrypted_pdf)
        encrypted_pdf.seek(0)
    os.remove(temp_path)

    # Send email
    msg = Message('Your Mbale Intelligent Banking Transaction Report',
                  sender=app.config['MAIL_USERNAME'],
                  recipients=[email])
    msg.body = f"""Dear {customer.name},

Attached is your transaction report.
The PDF file is password-protected.

Your password is: {custom_password}

Thank you for using Mbale Intelligent Banking.
"""

    msg.attach('transactions.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', excel_output.read())
    msg.attach('transactions_protected.pdf', 'application/pdf', encrypted_pdf.read())

    mail.send(msg)

    flash('Transaction report emailed successfully.', 'success')
    return redirect(url_for('dashboard'))


if __name__ == '__main__':
    if not os.path.exists('intelligent_bank.db'):
        with app.app_context():
            db.create_all()
    app.run(debug=True)
