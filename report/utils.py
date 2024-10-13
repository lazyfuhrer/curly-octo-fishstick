from django.db.models import Count, F, Avg, Q, Sum, Value, Case, DecimalField, When, CharField
from django.db.models.functions import Concat, Coalesce, TruncDate, TruncMonth
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from appointment.models import Appointment, Category, Procedure
from base.utils import convert_timedelta, price_format, str_to_date
from payment.models import Payment, Invoice, Wallet, InvoiceItems


class AppointmentReport:
    def __init__(self, clinic_id=None, from_date=None, to_date=None):
        self.clinic_id = clinic_id
        self.from_date = str_to_date(from_date, '%Y-%m-%dT%H:%M:%S',
                                     '%Y-%m-%dT00:00:00') if from_date \
            else from_date
        self.to_date = str_to_date(to_date, '%Y-%m-%dT%H:%M:%S',
                                   '%Y-%m-%dT23:59:59') if to_date else \
            to_date
        self.fdate = str_to_date(self.from_date, '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d')
        self.tdate = str_to_date(self.to_date, '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d')

    def get_appointment_filter_conditions(self, check_clinic=True,
                                          check_date=True):
        conditions = Q()
        if self.clinic_id is not None and check_clinic:
            conditions &= Q(clinic=self.clinic_id)
        if self.from_date is not None and self.to_date is not None and \
                check_date:
            conditions &= Q(
                scheduled_from__range=(self.from_date, self.to_date))
        return conditions

    def get_filter_conditions_invoice_items(self):
        conditions = Q()
        if self.fdate is not None and self.tdate is not None:
            conditions &= Q(
                created_at__range=(self.fdate, self.tdate))
        if self.clinic_id is not None:
            conditions &= Q(invoice__clinic=self.clinic_id)
        return conditions

    def get_filter_conditions_invoiceitems(self):
        conditions = Q()
        if self.fdate is not None and self.tdate is not None:
            conditions &= Q(
                invoice__date__range=(self.fdate, self.tdate))
        if self.clinic_id is not None:
            conditions &= Q(invoice__clinic=self.clinic_id)
        return conditions

    def get_filter_conditions_payment(self):
        conditions = Q()
        if self.clinic_id is not None:
            conditions &= Q(clinic=self.clinic_id)
        if self.fdate is not None and self.tdate is not None:
            conditions &= Q(
                collected_on__range=(self.fdate, self.tdate))
        return conditions

    def get_filter_conditions_invoices(self):
        conditions = Q()
        if self.fdate is not None and self.tdate is not None:
            conditions &= Q(
                date__range=(self.fdate, self.tdate))
        if self.clinic_id is not None:
            conditions &= Q(clinic=self.clinic_id)
        return conditions

    def get_filter_conditions_invoice_items(self):
        conditions = Q()
        if self.fdate is not None and self.tdate is not None:
            conditions &= Q(
                created_at__range=(self.fdate, self.tdate))
        if self.clinic_id is not None:
            conditions &= Q(invoice__clinic=self.clinic_id)
        return conditions

    def appointment_summary(self):

        count_doctors = self.get_doctors_appointments()
        # count_categories, categories_appointments =
        # self.get_categories_appointments()
        # count_procedures, procedures_appointments =
        # self.get_procedure_appointments()
        chiropractic_appointments = self.get_category_appointments_count(
            'Chiropractic')
        physiotherapy_appointments = self.get_category_appointments_count(
            'Physiotherapy')
        session_12_12_appointments = self.get_procedure_appointments_count(
            'Chiropractic '
            'Treatment Plan > '
            'Session 12/12')
        session_20_20_appointments = self.get_procedure_appointments_count(
            'Chiropractic '
            'Treatment Plan > '
            'Session 20/20')
        physiotherapy_1_12_appointments = self.get_procedure_appointments_count('Physiotherapy Plus - 1/12'
                                                            ) + self.get_procedure_appointments_count(
                                                                       'Physiotherapy Standard - 1/12')
        
        physiotherapy_12_12_appointments = self.get_procedure_appointments_count('Physiotherapy Plus - 12/12'
                                                            ) + self.get_procedure_appointments_count(
                                                                       'Physiotherapy Standard - 12/12')
        
        physiotherapy_1_20_appointments = self.get_procedure_appointments_count('Physiotherapy Plus - 1/20'
                                                            ) + self.get_procedure_appointments_count(
                                                                       'Physiotherapy Standard - 1/20')
        
        physiotherapy_20_20_appointments = self.get_procedure_appointments_count('Physiotherapy Plus - 20/20'
                                                            ) + self.get_procedure_appointments_count(
                                                                       'Physiotherapy Standard - 20/20')

        return {
            'total_appointments': self.get_total(),
            'count_of_doctors_with_appointments': count_doctors,
            'chiropractic_appointments': chiropractic_appointments,
            'physiotherapy_appointments': physiotherapy_appointments,
            'session_12_12_appointments': session_12_12_appointments,
            'session_20_20_appointments': session_20_20_appointments,
            # 'count_of_categories_appointments': count_categories,
            # 'count_of_procedures_appointments': count_procedures,
            # 'total_advance_payments': self.get_advance_payment_count(),
            'avg_waiting_time': self.get_avg_waiting_time(),
            'avg_treatment_time': self.get_avg_treatment_time(),

            'chiropractic_session_1_12':
                self.get_procedure_appointments_count('Chiropractic '
                                                        'Treatment Plan > '
                                                        'Session 1/12'),
            'chiropractic_session_12_12':
                self.get_procedure_appointments_count('Chiropractic '
                                                        'Treatment Plan > '
                                                        'Session 12/12'),
            'chiropractic_session_1_20':
                self.get_procedure_appointments_count('Chiropractic '
                                                        'Treatment Plan > '
                                                        'Session 1/20'),
            'chiropractic_session_20_20':
                self.get_procedure_appointments_count('Chiropractic '
                                                        'Treatment Plan > '
                                                        'Session 20/20'),
            'total_earnings_chiropractic_sessions': price_format(self.get_category_total_income(
                            'Chiropractic')-self.get_category_total_discount('Chiropractic')),

            'physiotherapy_sessions_1_12': physiotherapy_1_12_appointments,
            'physiotherapy_sessions_12_12': physiotherapy_12_12_appointments,
            'physiotherapy_sessions_1_20': physiotherapy_1_20_appointments,
            'physiotherapy_sessions_20_20': physiotherapy_20_20_appointments,
            'total_earnings_Physiotherapy_sessions': price_format(self.get_category_total_income(
                            'Physiotherapy')-self.get_category_total_discount('Physiotherapy')),

            'cancelled_by_doctors': self.get_cancelled_doctors_count(),
            'cancelled_by_patients': self.get_cancelled_patients_count(),
            'no_cancelled_appointments': self.get_count_on_status('cancelled'),
            'total_cost_cancelled_appointments': price_format(self.get_cancelled_appointments_earning()),
            'no_show': self.get_count_on_status('not_visited'),
            'total_cost_no_show_appointments': price_format(self.get_cost_on_status('not_visited')),

            'patients': self.get_patients_count(),
            'old_patients': self.get_old_patients(),
            'new_patients': self.get_new_patients(),
            'chiropractic_patients': self.get_unique_patients_by_category(
                'Chiropractic'),  # 'Chiropractic',
            'physiotherapy_patients': self.get_unique_patients_by_category(
                'Physiotherapy'),  # 'Physiotherapy',

            'total_income': price_format(self.get_total_income()),
            'total_discount': price_format(self.get_total_discount()),
            'total_earning': price_format(self.get_total_income()-self.get_total_discount()),
            'total_due_payment':price_format(self.get_due_amount()),
            'total_advance': price_format(self.get_total_advance()),

            'total_income_chiropractic': price_format(self.get_category_total_income('Chiropractic')),
            'total_discount_chiropractic': price_format(self.get_category_total_discount('Chiropractic')),
            'total_earning_chiropractic': price_format(self.get_category_total_income(
                            'Chiropractic')-self.get_category_total_discount('Chiropractic')),

            'total_income_physiotherapy': price_format(self.get_category_total_income('Physiotherapy')),
            'total_discount_physiotherapy': price_format(self.get_category_total_discount('Physiotherapy')),
            'total_earning_physiotherapy': price_format(self.get_category_total_income(
                            'Physiotherapy')-self.get_category_total_discount('Physiotherapy')),
        }

    def revenue_summary(self):
        return {
            'total_appointments': self.get_total(),
            'total_revenue': self.get_total_income(),
            'total_advance_payments': self.get_advance_payment_count(),
            'avg_waiting_time': self.get_avg_waiting_time(),
            'avg_treatment_time': self.get_avg_treatment_time(),

            'chiropracti_session_1_12':
                self.get_procedure_appointments_count('Chiropractic '
                                                        'Treatment Plan > '
                                                        'Session 1/12'),
            'chiropracti_session_12_12':
                self.get_procedure_appointments_count('Chiropractic '
                                                        'Treatment Plan > '
                                                        'Session 12/12'),
            'chiropracti_session_1_20':
                self.get_procedure_appointments_count('Chiropractic '
                                                        'Treatment Plan > '
                                                        'Session 1/20'),
            'chiropracti_session_20_20':
                self.get_procedure_appointments_count('Chiropractic '
                                                        'Treatment Plan > '
                                                        'Session 20/20'),

            'total_income': price_format(self.get_total_income()+self.get_total_discount()),
            'total_discount': price_format(self.get_total_discount()),
            'total_earning': price_format((self.get_total_income()+self.get_total_discount())-self.get_total_discount()),
        }

    def income_summary(self):
        cost = self.get_total_income()
        discount = self.get_total_discount()
        total = cost + discount
        return {
            'cost': price_format(total),
            'discount': price_format(discount),
            'income_after_discount': price_format(total - discount),
            'tax': price_format(self.get_tax()),
            'invoice_amount': price_format(self.get_invoices_amount()),
        }

    def billing_summary(self):
        invoice_grand_total = self.get_total_income()
        discount = self.get_total_discount()
        total = invoice_grand_total + discount
        payment = self.get_total_payments()
        # due_amount = invoice_grand_total - payment
        total_due = self.get_due_amount()

        return {
            'total_income': price_format(total),
            'total_discount': price_format(discount),
            'total_after_discount': price_format(invoice_grand_total),
            'total_dues': price_format(total_due),
            'total_payments': price_format(payment),
        }

    def get_total(self):
        total = Appointment.objects.filter(
            self.get_appointment_filter_conditions()
        ).count()
        return total

    def get_category_appointments_count(self, category_name):
        total_cat_appointments = Appointment.objects.filter(
            self.get_appointment_filter_conditions(),
            category__name=category_name
        ).count()
        return total_cat_appointments
        
    def get_category_total_income(self, category_name):
        total_revenue = Invoice.objects.filter(
            self.get_filter_conditions_invoices(),
            appointment__category__name=category_name
        ).aggregate(
            total_revenue=Sum('grand_total', default=0)
        )
        return total_revenue['total_revenue']
    
    def get_category_total_discount(self, category_name):
        invoices = Invoice.objects.filter(
            self.get_filter_conditions_invoices(),
            appointment__category__name=category_name
        ).aggregate(
            total_discount=Sum('invoiceitems__discount', default=0)
        )
        return invoices['total_discount']

    def get_procedure_appointments_count(self, procedure_name):
        total_cat_appointments = Appointment.objects.filter(
            self.get_appointment_filter_conditions(),
            procedure__name=procedure_name
        ).count()
        return total_cat_appointments

    def get_procedure_appointments_earning(self, procedure_name):
        appointments = Appointment.objects.filter(
            self.get_appointment_filter_conditions(),
            procedure__name=procedure_name
        ).aggregate(total_earnings=Sum('procedure__cost', default=0))
        return appointments['total_earnings']
    
    def get_cancelled_appointments_earning(self):
        appointments = Appointment.objects.filter(
            self.get_appointment_filter_conditions(),
            appointment_status='cancelled'
        ).aggregate(total_earnings=Sum('procedure__cost', default=0))
        return appointments['total_earnings']

    def get_avg_treatment_time(self):
        avg_treatment_time = Appointment.objects.filter(
            self.get_appointment_filter_conditions()
        ).annotate(
            treatment_time=F('checked_out') - F('engaged_at')
        ).aggregate(avg_treatment_time=Avg('treatment_time'))
        return convert_timedelta(avg_treatment_time['avg_treatment_time'])

    def get_advance_payment_count(self):
        total_advance_payments = Appointment.objects.filter(
            self.get_appointment_filter_conditions(),
            Q(
                Q(payment_status='collected') | Q(
                    payment_status='partial_paid'),
            )
        ).count()
        return total_advance_payments

    def get_avg_waiting_time(self):
        avg_waiting_time = Appointment.objects.filter(
            self.get_appointment_filter_conditions()
        ).annotate(
            waiting_time=F('engaged_at') - F('checked_in')
        ).aggregate(avg_waiting_time=Avg('waiting_time'))
        return convert_timedelta(avg_waiting_time['avg_waiting_time'])

    def get_doctors_appointments(self):
        appointments = Appointment.objects.filter(
            self.get_appointment_filter_conditions(),
        ).aggregate(
            total_appointments=Count('doctor', unique=True)
        )
        return appointments['total_appointments']

    def get_categories_appointments(self):
        categories_appointments = Category.objects.exclude(
            appointment__isnull=True
        ).annotate(
            total_appointments=Count('appointment',
                                     filter=self.get_appointment_filter_conditions())
        )

        return categories_appointments.count(), categories_appointments

    def get_procedures_appointments(self):

        procedures_appointments = Procedure.objects.exclude(
            appointment__isnull=True
        ).annotate(
            total_appointments=Count('appointment',
                                     filter=self.get_appointment_filter_conditions())
        )

        return procedures_appointments.count(), procedures_appointments

    def get_cancelled_appointments(self):
        cancelled_appointments = Appointment.objects.filter(
            self.get_appointment_filter_conditions(),
            appointment_status='cancelled'
        ).count()
        return cancelled_appointments

    def get_total_income(self):
        total_revenue = Invoice.objects.filter(
            self.get_filter_conditions_invoices(),
        ).aggregate(
            total_revenue=Sum('grand_total', default=0)
        )
        return total_revenue['total_revenue']

    def get_total_advance(self):
        # invoices = Invoice.objects.filter(
        #     self.get_filter_conditions_invoices(),
        # )
        # total_amount = invoices.aggregate(
        #     total_amount=Sum('grand_total', default=0)
        # )['total_amount']
        #
        # wallet_payments = Wallet.objects.filter(
        #     invoice__in=invoices
        # ).aggregate(
        #     total=Sum('amount', default=0)
        # )['total']
        #
        # paid = self.get_total_payments()
        #
        # return max(0, (paid + wallet_payments - total_amount))
        balance = Payment.objects.filter(
            self.get_filter_conditions_payment(),
            transaction_type='collected'
        ).aggregate(
            total=Sum('excess_amount', default=0)
        )['total']
        return balance

    def get_due_amount(self):
        invoices = Invoice.objects.filter(
            self.get_filter_conditions_invoices(),
            appointment__payment_status='partial_paid'
        )
        partial_paid = invoices.aggregate(
            total_due_amount=Sum('grand_total', default=0)
        )
        invoice_payments = Payment.objects.filter(
            invoice__in=invoices
        ).aggregate(
            total=Sum('price', default=0)
        )
        wallet_payments = Wallet.objects.filter(
            invoice__in=invoices
        ).aggregate(
            total=Sum('amount', default=0)
        )
        payments = invoice_payments['total'] + wallet_payments['total']
        return partial_paid['total_due_amount'] - payments

    def get_cancelled_doctors_count(self):
        appointments = Appointment.objects.filter(
            self.get_appointment_filter_conditions(),
            appointment_status='cancelled',
            updated_by__groups__name='doctor'
        ).aggregate(
            cancelled_doctors_count=Count('doctor', distinct=True)
        )
        return appointments['cancelled_doctors_count']

    def get_cancelled_patients_count(self):
        appointments = Appointment.objects.filter(
            self.get_appointment_filter_conditions(),
            appointment_status='cancelled',
        ).exclude(
            updated_by__groups__name='doctor'
        ).aggregate(
            cancelled_patients_count=Count('patient', distinct=True)
        )
        return appointments['cancelled_patients_count']

    def get_count_on_status(self, status):
        return Appointment.objects.filter(
            self.get_appointment_filter_conditions(),
            appointment_status=status
        ).count()

    def get_cost_on_status(self, status):
        appointments = Appointment.objects.filter(
            self.get_appointment_filter_conditions(),
            appointment_status=status
        ).annotate(
            total_cost=Sum('procedure__cost', default=0)
        ).aggregate(total=Sum('total_cost', default=0))
        return appointments['total']
    
    def get_cost_on_cancelled_by_patient(self):
        appointments = Appointment.objects.filter(
            self.get_appointment_filter_conditions(),
            appointment_status='cancelled',
        ).exclude(
            updated_by__groups__name='doctor'
        ).annotate(
            total_cost=Sum('procedure__cost', default=0)
        ).aggregate(total=Sum('total_cost', default=0))
        return appointments['total']
    
    def get_cost_on_cancelled_by_doctor(self):
        appointments = Appointment.objects.filter(
            self.get_appointment_filter_conditions(),
            appointment_status='cancelled',
            updated_by__groups__name='doctor'
        ).annotate(
            total_cost=Sum('procedure__cost', default=0)
        ).aggregate(total=Sum('total_cost', default=0))
        return appointments['total']

    def get_patients_count(self):
        appointments = Appointment.objects.filter(
            self.get_appointment_filter_conditions(),
        ).aggregate(
            total_patients=Count('patient', distinct=True)
        )
        return appointments['total_patients']

    def get_old_patients(self):
        appointments = Appointment.objects.filter(
            self.get_appointment_filter_conditions(),
            #is_new=False,
            #Q(
             #   Q(is_new='False') | Q(
             #       is_new='True'),
            #)
        ).exclude(is_new=True).aggregate(
            total_patients=Count('patient', distinct=True)
        )
        return appointments['total_patients']

    def get_new_patients(self):
        appointments = Appointment.objects.filter(
            self.get_appointment_filter_conditions(),
            is_new=True
        ).aggregate(
            total_patients=Count('patient', distinct=True)
        )
        return appointments['total_patients']

    def get_unique_patients_by_category(self, category_name):
        return Appointment.objects.filter(
            self.get_appointment_filter_conditions(),
            category__name=category_name
        ).distinct('patient').count()

    def get_total_discount(self):
        invoices = Invoice.objects.filter(
            self.get_filter_conditions_invoices(),
        ).aggregate(
            total_discount=Sum('invoiceitems__discount', default=0)
        )
        return invoices['total_discount']

    def get_total_earning(self):
        invoices = Invoice.objects.filter(
            self.get_filter_conditions_invoices(),
        ).aggregate(total_earning=Sum('payment__price', default=0))
        return invoices['total_earning']

    def get_total_payments(self):
        collected = Payment.objects.filter(
            self.get_filter_conditions_payment(),
            transaction_type='collected',
        ).aggregate(total=Sum('price', default=0))

        paid = Payment.objects.filter(
            self.get_filter_conditions_payment(),
            transaction_type='paid',
        ).aggregate(total=Sum('price', default=0))

        return collected['total'] - paid['total']

    # def get_advance_payment(self):
    #     total = self.get_total_payments()
    #     invoice_payments = get_total_income
    #     invoices = Invoice.objects.filter(
    #         self.get_filter_conditions_invoices(),
    #     ).aggregate(grand_total=Sum('grand_total', default=0))
    #     advance = total - invoices['grand_total']
    #     return advance > 0 and advance or 0

    def payment_summary(self):
        return {
            'total_advance_payments': price_format(self.get_total_advance()),
            'total_payments': price_format(self.get_total_payments()),
        }

    def payment_mode_summary(self):
        payment_mode = Payment.objects.filter(
            self.get_filter_conditions_payment(),
        ).exclude(
            type='wallet'
        ).values('type').annotate(
            total=price_format(Sum('price', default=0))
        )
        total = price_format(
        payment_mode.aggregate(overall=Sum('total'))['overall'] or 0
        )
        payment_mode_list = list(payment_mode)
        payment_mode_list.append({
        'type': 'total',
        'total': total
        })

        return payment_mode_list

    def get_invoices_amount(self):
        invoices = Invoice.objects.filter(
            self.get_filter_conditions_invoices(),
        ).aggregate(grand_total=Sum('grand_total', default=0))
        return invoices['grand_total']

    def earnings_per_procedure(self):
        income = self.get_total_earning()
        discount = self.get_total_discount()
        earnings = income - discount
        invoice = Invoice.objects.filter(
            self.get_filter_conditions_invoices(),
        ).annotate(
            cost=Sum('invoiceitems__price', default=0),
            total_discount=Sum('invoiceitems__discount', default=0),
            income=Sum('invoiceitems__total_after_discount', default=0),
        ).values('appointment__procedure__name', 'cost', 'total_discount', 'income')
        return {
            'total_income': income,
            'total_discount': discount,
            'total_earnings': earnings,
            'table': invoice
        }

    def appointments_per_doctor(self):
        appoinments = Appointment.objects.filter(
            self.get_appointment_filter_conditions()
        ).values(
            full_name=Concat(F('doctor__first_name'), Value(' '
                                                            ), F('doctor__last_name'))
        ).annotate(
            total_appointments=Count('id'),
            total_attended_appointments=Count('id', filter=Q(appointment_status='checked_out')),
            total_cancelled_appointments=Count('id', filter=Q(appointment_status='cancelled')),
            total_no_show=Count('id', filter=Q(appointment_status='not_visited')))
        return appoinments

    def invoiced_income_per_doctor(self):
        # invoice = Invoice.objects.filter(
        #     self.get_filter_conditions_invoices()
        # ).values(
        #     full_name=Concat(F('appointment__doctor__first_name'), Value(' '),
        #                      F('appointment__doctor__last_name'))).annotate(
        #     cost=Sum('invoiceitems__price', default=0),
        #     discounts=Sum('invoiceitems__discount', default=0),
        #     income=Sum('invoiceitems__total_after_discount', default=0),
        #     tax=Sum('invoiceitems__tax_amount', default=0),
        #     invoice_amount=F('grand_total')
        # ).values('full_name', 'cost', 'discounts', 'income', 'tax', 'invoice_amount')
        conditions = self.get_filter_conditions_invoiceitems()

        # First aggregate by invoice
        invoice_items = InvoiceItems.objects.filter(
            conditions
        ).values(
            full_name=Concat(F('doctor__first_name'), Value(' '), F('doctor__last_name'), output_field=CharField())
        ).annotate(
            cost=Sum('price', default=0),
            discounts=Sum('discount', default=0),
            income=Sum('total_after_discount', default=0),
            tax=Sum('tax_amount', default=0),
            invoice_amount=Sum('invoice__grand_total', default=0)
        ).order_by('-full_name')

        return invoice_items


    def get_tax(self):
        invoices = InvoiceItems.objects.select_related('invoice').filter(
            self.get_filter_conditions_invoiceitems(),
        ).aggregate(tax=Sum('tax_amount', default=0))
        return invoices['tax']

    def payments_per_day(self):
    # Get daily aggregations
        daily_payments = Payment.objects.filter(
            self.get_filter_conditions_payment(),
            transaction_type='collected',
            payment_status='success'
        ).values('collected_on').annotate(
            upi_total=Sum(Case(When(type='upi', then='price'), output_field=DecimalField())),
            card_total=Sum(Case(When(type='card', then='price'), output_field=DecimalField())),
            cash_total=Sum(Case(When(type='cash', then='price'), output_field=DecimalField())),
            net_banking_total=Sum(Case(When(type='netbanking', then='price'), output_field=DecimalField())),
            wallet_total=Sum(Case(When(type='wallet', then='price'), output_field=DecimalField())),
            total=Sum('price')
        ).order_by('collected_on')

    # Calculate overall totals
        overall_totals = Payment.objects.filter(
            self.get_filter_conditions_payment(),
            transaction_type='collected',
            payment_status='success'
        ).aggregate(
            upi_total=Sum(Case(When(type='upi', then='price'), output_field=DecimalField())),
            card_total=Sum(Case(When(type='card', then='price'), output_field=DecimalField())),
            cash_total=Sum(Case(When(type='cash', then='price'), output_field=DecimalField())),
            net_banking_total=Sum(Case(When(type='netbanking', then='price'), output_field=DecimalField())),
            wallet_total=Sum(Case(When(type='wallet', then='price'), output_field=DecimalField())),
            total=Sum('price')
        )

    # Format the daily report
        daily_report = [
            {
                "date": payment['collected_on'],
                "upi": price_format(payment['upi_total'] or 0),
                "card": price_format(payment['card_total'] or 0),
                "cash": price_format(payment['cash_total'] or 0),
                "net_banking": price_format(payment['net_banking_total'] or 0),
                "wallet": price_format(payment['wallet_total'] or 0),
                "total": price_format(payment['total'] or 0),
            } for payment in daily_payments
        ]

    # Format the overall totals
        overall_report = {
            "date": "Total",
            "upi": price_format(overall_totals['upi_total'] or 0),
            "card": price_format(overall_totals['card_total'] or 0),
            "cash": price_format(overall_totals['cash_total'] or 0),
            "net_banking": price_format(overall_totals['net_banking_total'] or 0),
            "wallet": price_format(overall_totals['wallet_total'] or 0),
            "total": price_format(overall_totals['total'] or 0),
        }

    # Combine daily report with overall totals
        report = [overall_report] + daily_report

        return report
    
    def get_income_per_procedure(self, request):
        invoice = Invoice.objects.filter(
            self.get_filter_conditions_invoices(),
        ).values('invoiceitems__procedure__name').annotate(
            cost=Coalesce(Sum('invoiceitems__price'), Value(0.0)),
            total_discount=Coalesce(Sum('invoiceitems__discount'), Value(0.0)),
            income=Coalesce(Sum('invoiceitems__total_after_discount'), Value(0.0)),
        )
        invoice_list = list(invoice)
        procedure_aggregates = {}

        total_cost = 0.0
        total_discount = 0.0
        total_income = 0.0

        for item in invoice_list:
            if '>' in item['invoiceitems__procedure__name']:
                main_procedure_name = item['invoiceitems__procedure__name'].split(' ')[0].strip()

            elif '-' in item['invoiceitems__procedure__name']:
                main_procedure_name = item['invoiceitems__procedure__name'].split(' ')[0].strip()

            else:
                main_procedure_name = item['invoiceitems__procedure__name']

            if main_procedure_name in procedure_aggregates:
                procedure_aggregates[main_procedure_name]['cost'] += item['cost']
                procedure_aggregates[main_procedure_name]['total_discount'] += item['total_discount']
                procedure_aggregates[main_procedure_name]['income'] += item['income']
            else:
                procedure_aggregates[main_procedure_name] = {
                'cost': item['cost'],
                'total_discount': item['total_discount'],
                'income': item['income'],
                }

            total_cost += item['cost']
            total_discount += item['total_discount']
            total_income += item['income']

        result_list = []
        result_list.append({
        's.no.': '',
        'invoiceitems__procedure__name': 'total',
        'cost': total_cost,
        'total_discount': total_discount,
        'income': total_income,
        })

        for index, (procedure_name, aggregates) in enumerate(procedure_aggregates.items(), start=1):
            result_list.append({
                's.no.': index,
                'invoiceitems__procedure__name': procedure_name,
                'cost': aggregates['cost'],
                'total_discount': aggregates['total_discount'],
                'income': aggregates['income'],
            })

        page = request.GET.get('page', 1)
        paginator = Paginator(result_list, 50)

        try:
            paginated_result_list = paginator.page(page)
        except PageNotAnInteger:
            paginated_result_list = paginator.page(1)
        except EmptyPage:
            paginated_result_list = paginator.page(paginator.num_pages)

        return paginated_result_list.object_list
    
    def get_appointment_per_procedure(self, request):
        total_cat_appointments = list(
        Invoice.objects.filter(
            self.get_filter_conditions_invoices(),
        )
        .values('appointment__procedure__name',)
        .annotate(count=Count('appointment__procedure__name'))
    )
        procedure_aggregates = {}

        for item in total_cat_appointments:
            if '>' in item['appointment__procedure__name']:
                main_procedure_name = item['appointment__procedure__name'].split(' ')[0].strip()

            elif '-' in item['appointment__procedure__name']:
                main_procedure_name = item['appointment__procedure__name'].split(' ')[0].strip()

            else:
                main_procedure_name = item['appointment__procedure__name']
        
            if main_procedure_name in procedure_aggregates:
                procedure_aggregates[main_procedure_name] += item['count']
            else:
                procedure_aggregates[main_procedure_name] = item['count']

        result_list = []
        total_count = 0
        for index, (procedure_name, count) in enumerate(procedure_aggregates.items(), start=1):
            result_list.append({
            's.no.': index,
            'appointment__procedure__name': procedure_name,
            'count': count
            })
            total_count += count

        result_list.insert(0, {
            's.no.': '',
            'appointment__procedure__name': 'total_count',
            'count': total_count
        })

        page = request.GET.get('page', 1)
        paginator = Paginator(result_list, 20)

        try:
            paginated_result_list = paginator.page(page)
        except PageNotAnInteger:
            paginated_result_list = paginator.page(1)
        except EmptyPage:
            paginated_result_list = paginator.page(paginator.num_pages)

        return paginated_result_list.object_list

    def get_advance_payments(self):
        payment = list(Payment.objects.filter(
            self.get_filter_conditions_payment(),
        ).values(
            full_name=Concat(F('patient__first_name'), Value(' '
                                                            ), F('patient__last_name'))
        ).annotate(
            wallet=Sum('excess_amount', default=0),
            due=Sum('balance', default=0)
        ).values('patient__atlas_id', 'full_name', 'wallet', 'due'))

        total_wallet = sum(item['wallet'] for item in payment)
        total_due = sum(item['due'] for item in payment)

    
    # Append the total count as a dictionary to the list
        payment.append({"patient__atlas_id":"total", "wallet": total_wallet, "due": total_due})

        invoice_list = list(payment)
    
    # Add serial number to each entry in the list
        result_list = []
        for index, invoice in enumerate(invoice_list, start=1):
        # Create a new dictionary with 's.no' first
            invoice_with_serial = {'s.no.': index}
        
        # Add the remaining fields to the dictionary
            invoice_with_serial.update(invoice)
        
            result_list.append(invoice_with_serial)

        return result_list
    
    def get_appointment(self, request):
        appointment=self.get_appointment_per_procedure(request)
        page = request.GET.get('page', 1)
        paginator = Paginator(appointment, 20)

        try:
            paginated_result_list = paginator.page(page)
        except PageNotAnInteger:
            paginated_result_list = paginator.page(1)
        except EmptyPage:
            paginated_result_list = paginator.page(paginator.num_pages)

        return paginated_result_list.object_list

    def get_cancellations(self, request):
        total=self.get_count_on_status('cancelled')
        no_show=self.get_count_on_status('no_show')
        cancelled_by_doctors= self.get_cancelled_doctors_count()
        cancelled_by_patients=self.get_cancelled_patients_count()
        total_cost_cancelled_appointments= price_format(self.get_cancelled_appointments_earning())
        total_cost_no_show_appointments=price_format(self.get_cost_on_status('not_visited'))
        total_cost_cancelled_by_doctor=price_format(self.get_cost_on_cancelled_by_doctor())
        total_cost_cancelled_by_patient=price_format(self.get_cost_on_cancelled_by_patient())


        data = [
        {'s.no': '', '': 'total', 'count': total, 'total_cost_cancelled_appointments':total_cost_cancelled_appointments},
        {'s.no': '1', '': 'no_show', 'count': no_show, 'total_cost_no_show_appointments':total_cost_no_show_appointments},
        {'s.no': '2', '': 'cancelled_by_doctors', 'count': cancelled_by_doctors, 'total_cost_cancelled_by_doctor':total_cost_cancelled_by_doctor},
        {'s.no': '3', '': 'cancelled_by_patients', 'count': cancelled_by_patients, 'total_cost_cancelled_by_patient':total_cost_cancelled_by_patient},
    ]

        page = request.GET.get('page', 1)
        paginator = Paginator(data, 20)

        try:
            paginated_result_list = paginator.page(page)
        except PageNotAnInteger:
            paginated_result_list = paginator.page(1)
        except EmptyPage:
            paginated_result_list = paginator.page(paginator.num_pages)

        return paginated_result_list.object_list
    
    def get_daily_appointments(self, request):
        appointments_by_day = (
        Appointment.objects.filter(
            self.get_appointment_filter_conditions())
        .annotate(day=TruncDate('scheduled_from'))
        .values('scheduled_from')
        .annotate(total_appointments=Count('id'))
        .order_by('scheduled_from')
        )
    
        response_data = []
        overall_total = 0
    
        total_appointments = sum([item['total_appointments'] for item in appointments_by_day])
        response_data.append({
        "s.no": "",
        "day": "total",
        "total appointments": total_appointments
        })
    
        for index, item in enumerate(appointments_by_day, start=1):
            response_data.append({
            "s.no": index,
            "day": item['scheduled_from'].strftime('%Y-%m-%d'),
            "total appointments": item['total_appointments']
        })
            overall_total += item['total_appointments']

        page = request.GET.get('page', 1)
        paginator = Paginator(response_data, 20)

        try:
            paginated_result_list = paginator.page(page)
        except PageNotAnInteger:
            paginated_result_list = paginator.page(1)
        except EmptyPage:
            paginated_result_list = paginator.page(paginator.num_pages)

        return paginated_result_list.object_list
    

    def get_monthly_appointments(self, request):
        appointments_by_month = Appointment.objects.filter(
            self.get_appointment_filter_conditions()
        ).annotate(month=TruncMonth('scheduled_from')
            ).values('month'
            ).annotate(total_appointments=Count('id')
            ).order_by('month')
    
        response_data = []
    
        total_appointments = sum([item['total_appointments'] for item in appointments_by_month])
        response_data.append({
        "s.no": "",
        "month": "total",
        "total appointments": total_appointments
        })
    
        for index, item in enumerate(appointments_by_month, start=1):
            formatted_month = item['month'].strftime('%B %Y')  # Format to 'Month YYYY'
            response_data.append({
            "s.no": index,
            "month": formatted_month,
            "total appointments": item['total_appointments']
            })

        page = request.GET.get('page', 1)
        paginator = Paginator(response_data, 20)

        try:
            paginated_result_list = paginator.page(page)
        except PageNotAnInteger:
            paginated_result_list = paginator.page(1)
        except EmptyPage:
            paginated_result_list = paginator.page(paginator.num_pages)

        return paginated_result_list.object_list
