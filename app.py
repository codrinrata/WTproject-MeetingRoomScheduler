from datetime import datetime, date
from flask import Flask, jsonify, make_response, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import check_password_hash

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///meetings.db'
app.config['SECRET_KEY'] = 'your_secret_key'
db = SQLAlchemy(app)

adminkey = "scrypt:32768:8:1$3h51ziIqVENrFBv3$bde94375a897723ed4cefade0175b73aef1bbf5f113b329c07f7314da8ab6142e21527050a0a239e1f3db15ea3f97fa9d2e99c70d1ac17c67b96094bd4d8cd71"

class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(200), nullable=False)
    meetings = db.relationship('Meeting', backref='room', lazy=True)

class Meeting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    attendee_count = db.Column(db.Integer, default=0)


@app.route('/', methods = ['GET', 'POST'])
def login():
    if request.method == 'POST':
        session['is_admin'] = False
        is_admin = request.form.get('is_admin') == 'admin'
        if is_admin:
            password = request.form.get('password')
            if check_password_hash(adminkey, password):
                session['is_admin'] = True
                return redirect(url_for('menu'))
            else:
                flash('Invalid Password!', 'error')
        else:
            return redirect(url_for('menu'))
    return render_template('login.html',hide_navbar=True)

@app.route('/menu', methods = ['GET', 'POST'])
def menu():
    if request.method == 'POST':
        option = request.form.get('option')
        if option == 'rooms':
            return redirect(url_for('display_rooms'))
        elif option == 'meetings':
            return redirect(url_for('display_meetings'))
        elif option == 'stats':
            return redirect(url_for('display_stats'))
    return render_template('menu.html')


@app.route('/rooms', methods=['GET', 'POST'])
def display_rooms():
    rooms = Room.query.all()
    meetings = Meeting.query.all()

    if request.method == 'POST' and session.get('is_admin'):
        name = request.form.get('name')
        location = request.form.get('location')

        if name and location:
            new_room = Room(name=name, location=location)
            db.session.add(new_room)
            db.session.commit()
            flash("Room added successfully!", "success")
        else:
            flash("Both name and location are required to add a room.", "error")

        return redirect(url_for('display_rooms'))

    return render_template('rooms.html', rooms=rooms, meetings=meetings)


@app.route('/delete_room/<int:room_id>', methods=['POST'])
def delete_room(room_id):
    if session.get('is_admin'):
        room = Room.query.get_or_404(room_id)
        db.session.delete(room)
        db.session.commit()
        flash(f"Room '{room.name}' deleted successfully!", "success")
    else:
        flash("You are not authorized to delete rooms.", "error")

    return redirect(url_for('display_rooms'))



@app.route('/meetings', methods=['GET', 'POST'])
def display_meetings():

    today = date.today()
    finished_meetings = Meeting.query.filter(Meeting.date < today).all()
    for meeting in finished_meetings:
        db.session.delete(meeting)
    db.session.commit()

    rooms = Room.query.all()
    meetings = Meeting.query.all()
    attended_meetings = request.cookies.get('attended_meetings', '')
    attended_set = set(map(int, attended_meetings.split(','))) if attended_meetings else set()

    if request.method == 'POST' and session.get('is_admin'):
        title = request.form.get('title')
        room_id = request.form.get('room_id')
        meeting_date = request.form.get('date')
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')

        if not (title and room_id and meeting_date and start_time and end_time):
            flash("All fields are required to create a meeting.", "error")
        else:
            try:
                meeting_date = datetime.strptime(meeting_date, '%Y-%m-%d').date()
                start_time = datetime.strptime(start_time, '%H:%M').time()
                end_time = datetime.strptime(end_time, '%H:%M').time()

                if start_time >= end_time:
                    flash("Start time must be before end time.", "error")
                else:
                    new_meeting = Meeting(
                        title=title,
                        room_id=room_id,
                        date=meeting_date,
                        start_time=start_time,
                        end_time=end_time
                    )
                    db.session.add(new_meeting)
                    db.session.commit()
                    flash("Meeting added successfully!", "success")
            except ValueError as e:
                flash("Invalid date or time format.", "error")

        return redirect(url_for('display_meetings'))

    return render_template('meetings.html', rooms=rooms, meetings=meetings, attended_set=attended_set)

@app.route('/attend/<int:meeting_id>', methods=['POST'])
def toggle_attendance(meeting_id):
    attended_meetings = request.cookies.get('attended_meetings', '')
    attended_set = set(map(int, attended_meetings.split(','))) if attended_meetings else set()

    meeting = Meeting.query.get(meeting_id)
    if not meeting:
        flash("Meeting not found.", "danger")
        return redirect(url_for('display_meetings'))

    if meeting_id in attended_set:
        attended_set.remove(meeting_id)
        meeting.attendee_count = max(0, meeting.attendee_count - 1)
        db.session.commit()
        flash("Successfully unattended the meeting.", "success")
    else:
        attended_set.add(meeting_id)
        meeting.attendee_count += 1
        db.session.commit()
        flash("Successfully registered for the meeting.", "success")

    response = make_response(redirect(url_for('display_meetings')))
    response.set_cookie('attended_meetings', ','.join(map(str, attended_set)), max_age=30 * 24 * 60 * 60)
    return response


@app.route('/delete_meeting/<int:meeting_id>', methods=['POST'])
def delete_meeting(meeting_id):
    if session.get('is_admin'):
        meeting = Meeting.query.get_or_404(meeting_id)
        db.session.delete(meeting)
        db.session.commit()
        flash(f"Meeting '{meeting.title}' deleted successfully!", "success")
    else:
        flash("You are not authorized to delete meetings.", "error")

    return redirect(url_for('display_meetings'))


@app.route('/stats', methods=['GET'])
def display_stats():
    rooms = Room.query.all()

    rooms_stats = []
    total_attendees = 0

    for room in rooms:
        room_meetings = room.meetings
        num_meetings = len(room_meetings)
        attendees_in_room = sum(meeting.attendee_count for meeting in room_meetings)
        
        rooms_stats.append({
            'room': room,
            'num_meetings': num_meetings,
            'attendees': attendees_in_room,
        })

        total_attendees += attendees_in_room

    return render_template(
        'stats.html',
        rooms_stats=rooms_stats,
        total_attendees=total_attendees,
    )


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)

