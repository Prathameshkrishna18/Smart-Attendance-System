import cv2
import numpy as np
import face_recognition
import pandas as pd
import os
import schedule
import time
import threading
from datetime import datetime, timedelta
from twilio.rest import Client
import tkinter as tk
from tkinter import ttk, messagebox


TWILIO_SID = "your_twilio_sid"
TWILIO_AUTH_TOKEN = "your_twilio_auth_token"
TWILIO_PHONE_NUMBER = "your_twilio_phone_number"


students = {
    "Prathamesh Chavan": {"roll_no": 1, "image": "Bill_Gates.jpg", "parent_contact": "+1234567890"},
    "Mark Zuckerberg": {"roll_no": 2, "image": "mark_img.jpg", "parent_contact": "+1234567891"},
    "Jack Ma": {"roll_no": 3, "image": "jack_img.jpg", "parent_contact": "+1234567892"},
    "Akshada Jadhav": {"roll_no": 4, "image": "Akshada_img.jpg", "parent_contact": "+1234567893"},
    "Isha Jadhav": {"roll_no": 5, "image": "Isha_img.jpg", "parent_contact": "+1234567894"},
    "Kiran Kambale": {"roll_no": 6, "image": "Kiran.jpg", "parent_contact": "+1234567894"},
    "Vaishnavi Arde": {"roll_no": 7, "image": "Vaishnavi.jpg", "parent_contact": "+1234567894"},
    "Pranjal Dhavane": {"roll_no": 8, "image": "Pranjal.jpg", "parent_contact": "+1234567894"},
}


known_faces = []
student_names = []
student_roll_numbers = []
last_attendance_time = {}


def load_students():
    for name, details in students.items():
        image_path = details["image"]
        if os.path.exists(image_path):
            image = face_recognition.load_image_file(image_path)
            encoding = face_recognition.face_encodings(image)
            if encoding:
                known_faces.append(encoding[0])
                student_names.append(name)
                student_roll_numbers.append(details["roll_no"])
                last_attendance_time[details["roll_no"]] = None  
            else:
                print(f"Warning: No face found in {image_path}")
        else:
            print(f"Warning: Image not found at {image_path}")


def mark_attendance(name, roll_no, subject):
    now = datetime.now()
    date_string = now.strftime("%Y-%m-%d")
    time_string = now.strftime("%H:%M:%S")
    
    
    last_time = last_attendance_time[roll_no]
    if last_time:
        time_diff = now - last_time
        if time_diff < timedelta(minutes=30):  
            print(f"{name} (Roll No: {roll_no}) has already marked attendance recently.")
            return
    
    
    last_attendance_time[roll_no] = now

    
    df = pd.DataFrame([[name, roll_no, date_string, time_string, subject]], columns=["Name", "Roll Number", "Date", "Time", "Subject"])
    

    if not os.path.exists("Student_Attendence.csv"):
        df.to_csv("Student_Attendence.csv", index=False)
    else:
    
        attendance_df = pd.read_csv("Student_Attendence.csv", names=["Name", "Roll Number", "Date", "Time", "Subject"])

    
        attendance_df["Date"] = attendance_df["Date"].astype(str)
        attendance_df["Time"] = attendance_df["Time"].astype(str)

        today_attendance = attendance_df[
            (attendance_df["Roll Number"] == roll_no) &
            (attendance_df["Subject"] == subject) &
            (attendance_df["Date"] == date_string)
        ]
        
        if today_attendance.empty:
            df.to_csv("Student_Attendence.csv", mode="a", header=False, index=False)
            print(f"Attendance Marked: {name} (Roll No: {roll_no}) for {subject} on {date_string} at {time_string}")
        else:
            print(f"Attendance already marked for {name} (Roll No: {roll_no}) for {subject} on {date_string}.")


def recognize_faces(subject):
    cap = cv2.VideoCapture(0)

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
        rgb_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

        face_locations = face_recognition.face_locations(rgb_frame)
        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

        for encoding, location in zip(face_encodings, face_locations):
            matches = face_recognition.compare_faces(known_faces, encoding)
            face_distances = face_recognition.face_distance(known_faces, encoding)
            best_match_index = np.argmin(face_distances) if face_distances.size > 0 else None

            if best_match_index is not None and matches[best_match_index]:
                name = student_names[best_match_index]
                roll_no = student_roll_numbers[best_match_index]
                mark_attendance(name, roll_no, subject)

    
                y1, x2, y2, x1 = location
                y1, x2, y2, x1 = y1 * 4, x2 * 4, y2 * 4, x1 * 4
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, f"{name} (Roll: {roll_no})", (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

        cv2.imshow("Face Attendance", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


def send_absent_sms():
    today_date = datetime.now().strftime("%Y-%m-%d")
    try:
        attendance_df = pd.read_csv("Student_Attendence.csv", names=["Name", "Roll Number", "Date", "Time", "Subject"])
    except FileNotFoundError:
        print("No attendance records found!")
        return

    
    present_students = attendance_df[attendance_df["Date"] == today_date]["Roll Number"].unique()

    
    all_students = set(student["roll_no"] for student in students.values())
    absent_students = all_students - set(present_students)

    
    client = Client(TWILIO_SID, TWILIO_AUTH_TOKEN)
    
    for roll_no in absent_students:
        for name, details in students.items():
            if details["roll_no"] == roll_no:
                message_body = f"Your son {name} (Roll No: {roll_no}) is not present today."
                parent_contact = details["parent_contact"]
                try:
                    client.messages.create(body=message_body, from_=TWILIO_PHONE_NUMBER, to=parent_contact)
                    print(f"Sent SMS to parent of {name} (Roll No: {roll_no})")
                except Exception as e:
                    print(f"Failed to send SMS to {parent_contact}: {e}")


def schedule_sms():
    schedule.every().day.at("17:00").do(send_absent_sms)
    while True:
        schedule.run_pending()
        time.sleep(1)


def create_admin_gui():
    root = tk.Tk()
    root.title("Admin Control Panel")
    root.geometry("600x400")

    
    subject_var = tk.StringVar()
    subjects = ["Math", "Science", "English", "History", "Computer Science"]

    
    def start_face_recognition():
        subject = subject_var.get()
        if subject:
            threading.Thread(target=recognize_faces, args=(subject,), daemon=True).start()
        else:
            messagebox.showwarning("Error", "Please select a subject first!")


    tk.Label(root, text="Select Subject:", font=("Arial", 12)).pack(pady=10)
    subject_dropdown = ttk.Combobox(root, textvariable=subject_var, values=subjects, font=("Arial", 12))
    subject_dropdown.pack(pady=10)


    tk.Button(root, text="Start Face Recognition", command=start_face_recognition, height=2, width=30).pack(pady=10)


    def view_attendance():
        attendance_window = tk.Toplevel(root)
        attendance_window.title("Attendance Records")
        attendance_window.geometry("500x300")

        tree = ttk.Treeview(attendance_window, columns=("Name", "Roll Number", "Date", "Time", "Subject"), show="headings")
        tree.heading("Name", text="Name")
        tree.heading("Roll Number", text="Roll Number")
        tree.heading("Date", text="Date")
        tree.heading("Time", text="Time")
        tree.heading("Subject", text="Subject")
        tree.pack(fill="both", expand=True)

        try:
            df = pd.read_csv("Student_Attendence.csv", names=["Name", "Roll Number", "Date", "Time", "Subject"])
            for index, row in df.iterrows():
                tree.insert("", "end", values=(row["Name"], row["Roll Number"], row["Date"], row["Time"], row["Subject"]))
        except FileNotFoundError:
            messagebox.showerror("Error", "No attendance records found!")

    tk.Button(root, text="View Attendance", command=view_attendance, height=2, width=30).pack(pady=10)

    
    tk.Button(root, text="Send Absent SMS", command=send_absent_sms, height=2, width=30).pack(pady=10)


    tk.Button(root, text="Exit", command=root.quit, height=2, width=30).pack(pady=10)

    root.mainloop()


if __name__ == "__main__":
    load_students()
    sms_thread = threading.Thread(target=schedule_sms, daemon=True)
    sms_thread.start()
    create_admin_gui()
