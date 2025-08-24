"""
Database models for Workforce Scheduler
"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

# Initialize SQLAlchemy
db = SQLAlchemy()

class Employee(UserMixin, db.Model):
    """Employee model with authentication support"""
    __tablename__ = 'employee'
    
    # Primary key
    id = db.Column(db.Integer, primary_key=True)
    
    # Authentication fields
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255))
    
    # Basic info
    name = db.Column(db.String(100), nullable=False)
    employee_id = db.Column(db.String(50), unique=True, index=True)
    phone = db.Column(db.String(20))
    
    # Work info
    position_id = db.Column(db.Integer)
    department = db.Column(db.String(50))
    crew = db.Column(db.String(1))
    is_supervisor = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    hire_date = db.Column(db.Date)
    
    # Status and availability
    is_active = db.Column(db.Boolean, default=True)
    max_hours_per_week = db.Column(db.Integer, default=48)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    time_off_requests = db.relationship('TimeOffRequest', back_populates='employee', lazy='dynamic')
    swap_requests_from = db.relationship('ShiftSwapRequest', foreign_keys='ShiftSwapRequest.from_employee_id', 
                                        back_populates='from_employee', lazy='dynamic')
    swap_requests_to = db.relationship('ShiftSwapRequest', foreign_keys='ShiftSwapRequest.to_employee_id', 
                                      back_populates='to_employee', lazy='dynamic')
    
    def set_password(self, password):
        """Set password hash"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check password against hash"""
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<Employee {self.email}>'


class TimeOffRequest(db.Model):
    """Time off request model"""
    __tablename__ = 'time_off_request'
    
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.String(200))
    status = db.Column(db.String(20), default='pending')  # pending, approved, denied
    
    # Approval info
    reviewed_by = db.Column(db.Integer, db.ForeignKey('employee.id'))
    reviewed_at = db.Column(db.DateTime)
    review_notes = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    employee = db.relationship('Employee', foreign_keys=[employee_id], back_populates='time_off_requests')
    reviewer = db.relationship('Employee', foreign_keys=[reviewed_by])
    
    def __repr__(self):
        return f'<TimeOffRequest {self.employee_id} {self.start_date}-{self.end_date}>'


class ShiftSwapRequest(db.Model):
    """Shift swap request model"""
    __tablename__ = 'shift_swap_request'
    
    id = db.Column(db.Integer, primary_key=True)
    from_employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    to_employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'))
    shift_date = db.Column(db.Date, nullable=False)
    shift_start = db.Column(db.Time)
    shift_end = db.Column(db.Time)
    reason = db.Column(db.String(200))
    status = db.Column(db.String(20), default='pending')  # pending, approved, denied
    
    # Approval info
    reviewed_by = db.Column(db.Integer, db.ForeignKey('employee.id'))
    reviewed_at = db.Column(db.DateTime)
    review_notes = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    from_employee = db.relationship('Employee', foreign_keys=[from_employee_id], back_populates='swap_requests_from')
    to_employee = db.relationship('Employee', foreign_keys=[to_employee_id], back_populates='swap_requests_to')
    reviewer = db.relationship('Employee', foreign_keys=[reviewed_by])
    
    def __repr__(self):
        return f'<ShiftSwapRequest {self.from_employee_id}->{self.to_employee_id} {self.shift_date}>'


class Schedule(db.Model):
    """Schedule model for shifts"""
    __tablename__ = 'schedule'
    
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    date = db.Column(db.Date, nullable=False, index=True)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    position = db.Column(db.String(50))
    notes = db.Column(db.Text)
    
    # Status
    is_published = db.Column(db.Boolean, default=False)
    is_confirmed = db.Column(db.Boolean, default=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    employee = db.relationship('Employee', backref=db.backref('schedules', lazy='dynamic'))
    
    # Indexes
    __table_args__ = (
        db.Index('idx_schedule_date_employee', 'date', 'employee_id'),
    )
    
    def __repr__(self):
        return f'<Schedule {self.employee_id} {self.date} {self.start_time}-{self.end_time}>'


class Position(db.Model):
    """Position/Role model"""
    __tablename__ = 'position'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    department = db.Column(db.String(50))
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Position {self.name}>'


class Availability(db.Model):
    """Employee availability model"""
    __tablename__ = 'availability'
    
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    day_of_week = db.Column(db.Integer, nullable=False)  # 0=Monday, 6=Sunday
    start_time = db.Column(db.Time)
    end_time = db.Column(db.Time)
    is_available = db.Column(db.Boolean, default=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    employee = db.relationship('Employee', backref=db.backref('availabilities', lazy='dynamic'))
    
    # Constraints
    __table_args__ = (
        db.UniqueConstraint('employee_id', 'day_of_week', name='_employee_day_uc'),
    )
    
    def __repr__(self):
        return f'<Availability {self.employee_id} Day:{self.day_of_week}>'
