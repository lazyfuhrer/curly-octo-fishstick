import datetime
import logging

from dateutil import parser
from django.utils import timezone

from base.helpers.email import EmailUtils
from base.helpers.sms import SMSUtils
from fuelapp.constants import MANAGER

logger = logging.getLogger('fuelapp')


def get_appointment_related_object(appointment, include_doctor=False):
    from clinic.models import Clinic
    from clinic.serializers import ClinicSerializer
    from user.models import User
    from user.serializers import UserSerializer
    patient_id = appointment.get('patient_id', None) or appointment.get(
        'patient',
        None)
    clinic_id = appointment.get('clinic_id', None) or appointment.get(
        'clinic',
        None)
    doctor_id = appointment.get('doctor_id', None) or appointment.get(
        'doctor',
        None)
    ret = []
    if patient_id:
        user = User.objects.get(id=patient_id)
        ret.append(UserSerializer(user).data)
    if clinic_id:
        clinic = Clinic.objects.get(id=clinic_id)
        ret.append(ClinicSerializer(clinic).data)
    if include_doctor and doctor_id:
        doctor = User.objects.get(id=doctor_id)
        ret.append(UserSerializer(doctor).data)
    return ret


def convert_to_local_time(time):
    return timezone.localtime(parser.isoparse(str(time)))


def suffix(d):
    return {1: 'st', 2: 'nd', 3: 'rd'}.get(d % 20, 'th')


def custom_strftime(format, t=datetime.datetime.now()):
    return t.strftime(format).replace('{S}', str(t.day) + suffix(t.day))


def appointment_booked_notification(data):
    template_name = "email/appointment_booked.html"
    appointment = data['appointment']
    user, clinic_data = get_appointment_related_object(appointment)
    to_email = user.get('email')
    booked_on = convert_to_local_time(appointment['scheduled_from'])
    date_on = custom_strftime('{S} of %B', booked_on)
    subject = f"Atlas - Confirmation of Your Upcoming Appointment on {date_on}"

    # map_link review_link
    context = {
        'full_name': user.get('full_name'),
        'clinic_location': clinic_data.get('name'),
        'clinic_phone_no': clinic_data.get('phone_no_1'),
        'clinic_map_url': clinic_data.get('map_link'),
        'clinic_address': clinic_data.get('full_address'),
        'booked_date': booked_on.strftime('%d-%m-%Y'),
        'booked_time': booked_on.strftime('%I:%M %p'),
    }
    context.update(MANAGER)
    EmailUtils(to_email, subject, template_name, context).send()
    sms = SMSUtils('create_appointment')
    sms_data = {
        'first_name': user.get('first_name'),
        'clinic_location': clinic_data.get('name'),
        'booked_date': booked_on.strftime('%d-%m-%Y'),
    }
    sms.send(user.get('phone_number')[-10:], sms_data)


def send_appointment_confirmed_email(data):
    template_name = "email/appointment_confirmed.html"
    appointment = data['appointment']
    user, clinic_data = get_appointment_related_object(appointment)
    to_email = user.get('email')
    booked_on = convert_to_local_time(appointment['scheduled_from'])
    date_on = custom_strftime('{S} of %B', booked_on)

    subject = f"Appointment Confirmed on {date_on}"

    context = {
        'full_name': user.get('full_name'),
        'clinic_location': clinic_data.get('name'),
        'clinic_phone_no': clinic_data.get('phone_no_1'),
        'clinic_map_url': clinic_data.get('map_link'),
        'clinic_address': clinic_data.get('full_address'),
        'booked_date': booked_on.strftime('%d-%m-%Y'),
        'booked_time': booked_on.strftime('%I:%M %p'),
    }
    context.update(MANAGER)
    EmailUtils(to_email, subject, template_name, context).send()
    sms = SMSUtils('create_appointment')
    sms_data = {
        'first_name': user.get('first_name'),
        'clinic_location': clinic_data.get('name'),
        'booked_date': booked_on.strftime('%d-%m-%Y'),
    }
    sms.send(user.get('phone_number')[-10:], sms_data)


def appointment_instructions_notification(data):
    template_name = "email/appointment_instructions.html"
    appointment = data['appointment']
    user, clinic_data = get_appointment_related_object(appointment)
    to_email = user.get('email')
    booked_on = convert_to_local_time(appointment['scheduled_from'])
    date_on = custom_strftime('{S} of %B', booked_on)
    subject = "Pre-Appointment Instructions for Your Upcoming " \
              f"Clinic Visit {date_on}"
    context = {
        'full_name': user.get('full_name'),
        'clinic_location': clinic_data.get('name'),
        'clinic_phone_no': clinic_data.get('phone_no_1'),
        'clinic_map_url': clinic_data.get('map_link'),
        'clinic_address': clinic_data.get('full_address'),
        'booked_date': booked_on.strftime('%d-%m-%Y'),
        'booked_time': booked_on.strftime('%I:%M %p'),
    }
    context.update(MANAGER)
    EmailUtils(to_email, subject, template_name, context).send()
    sms = SMSUtils('appointment_instruction')
    sms_data = {
        'first_name': user.get('first_name'),
        'clinic_map_url': clinic_data.get('map_link'),
    }
    sms.send(user.get('phone_number')[-10:], sms_data)


def appointment_feedback_notification(data):
    template_name = "email/appointment_feedback.html"
    subject = "Request for Your Valuable Feedback - Help Us Serve You Better"
    appointment = data['appointment']
    user, clinic_data = get_appointment_related_object(appointment)
    to_email = user.get('email')
    booked_on = convert_to_local_time(appointment['scheduled_from'])
    context = {
        'full_name': user.get('full_name'),
        'clinic_location': clinic_data.get('name'),
        'clinic_phone_no': clinic_data.get('phone_no_1'),
        'clinic_map_url': clinic_data.get('map_link'),
        'clinic_address': clinic_data.get('full_address'),
        'booked_date': booked_on.strftime('%d-%m-%Y'),
        'booked_time': booked_on.strftime('%I:%M %p'),
    }
    context.update(MANAGER)
    EmailUtils(to_email, subject, template_name, context).send()
    sms = SMSUtils('review_appointment')
    sms_data = {
        'first_name': user.get('first_name'),
        'clinic_location': clinic_data.get('name'),
        'clinic_map_url': clinic_data.get('map_link'),
    }
    sms.send(user.get('phone_number')[-10:], sms_data)


def send_appointment_reminder_email(data):
    template_name = "email/appointment_reminder.html"
    appointment = data['appointment']
    user, clinic_data = get_appointment_related_object(appointment)
    subject = f"Reminder: Appointment Tomorrow at {clinic_data.get('name')}"
    to_email = user.get('email')
    booked_on = convert_to_local_time(appointment['scheduled_from'])
    context = {
        'full_name': user.get('full_name'),
        'clinic_location': clinic_data.get('name'),
        'clinic_phone_no': clinic_data.get('phone_no_1'),
        'clinic_map_url': clinic_data.get('map_link'),
        'clinic_address': clinic_data.get('full_address'),
        'booked_date': booked_on.strftime('%d-%m-%Y'),
        'booked_time': booked_on.strftime('%I:%M %p'),
    }
    context.update(MANAGER)
    EmailUtils(to_email, subject, template_name, context).send()


def send_appointment_cancelled_email(data):
    template_name = "email/appointment_cancelled.html"

    appointment = data['appointment']
    user, clinic_data, doctor = get_appointment_related_object(appointment,
                                                               include_doctor=True)
    booked_on = convert_to_local_time(appointment['scheduled_from'])
    date_on = custom_strftime('{S} of %B', booked_on)
    subject = f"Cancelled: Appointment Tomorrow at {clinic_data.get('name')} " \
              f"{date_on}"
    to_email = user.get('email')

    context = {
        'full_name': user.get('full_name'),
        'clinic_location': clinic_data.get('name'),
        'clinic_phone_no': clinic_data.get('phone_no_1'),
        'clinic_map_url': clinic_data.get('map_link'),
        'clinic_address': clinic_data.get('full_address'),
        'booked_date': booked_on.strftime('%d-%m-%Y'),
        'booked_time': booked_on.strftime('%I:%M %p'),
    }
    context.update(MANAGER)
    EmailUtils(to_email, subject, template_name, context).send()
    sms = SMSUtils('cancelled_appointment')
    sms_data = {
        'first_name': user.get('first_name'),
        'clinic_location': clinic_data.get('name'),
        'booked_date': booked_on.strftime('%d-%m-%Y')
    }
    sms.send(user.get('phone_number')[-10:], sms_data)


def send_appointment_followup_email(data):
    template_name = "email/appointment_followup.html"
    subject = "Follow-Up and Summary of Your Recent Appointment"
    appointment = data['appointment']
    user, clinic_data, doctor = get_appointment_related_object(appointment,
                                                               include_doctor=True)
    to_email = user.get('email')
    booked_on = convert_to_local_time(appointment['scheduled_from'])
    context = {
        'full_name': user.get('full_name'),
        'clinic_location': clinic_data.get('name'),
        'clinic_phone_no': clinic_data.get('phone_no_1'),
        'clinic_map_url': clinic_data.get('map_link'),
        'clinic_address': clinic_data.get('full_address'),
        'doctor_name': doctor.get('full_name'),
        'booked_date': booked_on.strftime('%d-%m-%Y'),
        'booked_time': booked_on.strftime('%I:%M %p'),
    }
    context.update(MANAGER)
    EmailUtils(to_email, subject, template_name, context).send()


def send_appointment_reschedule_email(data):
    template_name = "email/appointment_reschedule.html"

    appointment = data['appointment']
    booked_on = convert_to_local_time(appointment['scheduled_from'])
    date_on = custom_strftime('{S} of %B', booked_on)
    subject = f"Appointment Rescheduled {date_on} "
    user, clinic_data = get_appointment_related_object(appointment)
    to_email = user.get('email')

    context = {
        'full_name': user.get('full_name'),
        'clinic_location': clinic_data.get('name'),
        'clinic_phone_no': clinic_data.get('phone_no_1'),
        'clinic_map_url': clinic_data.get('map_link'),
        'clinic_address': clinic_data.get('full_address'),
        'booked_date': booked_on.strftime('%d-%m-%Y'),
        'booked_time': booked_on.strftime('%I:%M %p'),
    }
    context.update(MANAGER)
    EmailUtils(to_email, subject, template_name, context).send()

def appointment_booked_by_patient_notification(appointment_data):
    from clinic.models import Clinic
    from user.models import User
    patient_id = appointment_data['patient']
    clinic_id = appointment_data['clinic']
    patient = User.objects.get(id=patient_id)
    clinic = Clinic.objects.get(id=clinic_id)
    scheduled_from = appointment_data['scheduled_from']
    booked_on = convert_to_local_time(scheduled_from)
    date = booked_on.strftime('%d-%m-%Y')
    time = booked_on.strftime('%I:%M %p')
    
    context = {
        'first_name': patient.first_name,
        'clinic_name': clinic.name,
        'date_and_time': f"{date} at {time}"
    }
    
    EmailUtils(patient.email, "Appointment Confirmation", "email/appointment_booked_by_patient", context).send()

    sms = SMSUtils('appointment_booked_by_patient')
    sms.send(patient.phone_number[-10:], context)    

def confirm_payment_notification(appointment_data):
    from clinic.models import Clinic
    from user.models import User
    patient_id = appointment_data['patient']
    clinic_id = appointment_data['clinic']
    patient = User.objects.get(id=patient_id)
    clinic = Clinic.objects.get(id=clinic_id)
    
    context = {
        'first_name': patient.first_name,
        'clinic_name': clinic.name,
    }
    
    EmailUtils(patient.email, "Payment Confirmation", "email/confirm-payment", context).send()

    sms = SMSUtils('confirm_payment')
    sms.send(patient.phone_number[-10:], context)    

def convert_timedelta(duration):
    if not duration:
        return 0
    days, seconds = duration.days, duration.seconds
    hours = days * 24 + seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = (seconds % 60)
    # return hours, minutes, seconds
    return (f"{hours:02d} Hr " if hours else "") + (f"{minutes:02d} Min "
                                                    if minutes else "") + \
        (f"{seconds:02d} Sec " if seconds else "")


def price_format(value, simple=False):
    if not value:
        return "₹ 0.00"
    try:
        value = float(value)
    except (TypeError, ValueError):
        return value
    if simple:
        if value >= 10000000:  # Crore
            return f'₹ {value / 10000000:,.2f} Cr'
        elif value >= 100000:  # Lakh
            return f'₹ {value / 100000:,.2f} L'
    return f'₹ {value:,.2f}'
    # return "₹ {:.2f}/-".format(price)


def str_to_date(str, input_format, output_format):
    return datetime.datetime.strptime(str, input_format).strftime(output_format)


from django.shortcuts import render
from weasyprint import HTML


def generate_pdf_file(template_name, context):
    # Render the HTML template
    html_string = render(None, template_name, context).content.decode("utf-8")

    # Create a WeasyPrint HTML object
    html = HTML(string=html_string)

    # Generate PDF
    pdf_file = html.write_pdf()

    return pdf_file


def send_attachment_email(template_name, pdf_template, context, to_email, \
                          subject):
    # Generate the PDF
    pdf_file = generate_pdf_file(pdf_template, context)

    # Create an EmailMessage object
    # email = EmailMessage(
    #     subject,
    #     'Attached is your document.',
    #     'from@example.com',
    #     [to_email],
    # )

    # Attach the PDF file
    # email.attach('document.pdf', pdf_file, 'application/pdf')

    # Send the email
    # email.send()
    EmailUtils(to_email, subject, template_name, context).send()
