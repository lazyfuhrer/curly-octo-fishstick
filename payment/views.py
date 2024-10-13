import csv
import logging, traceback
from itertools import chain
import requests

from django.core.cache import cache
from django.db import transaction
from django.http import HttpResponse
from django.http import JsonResponse
from django.utils import timezone
from rest_framework import generics, filters, status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from appointment.models import Appointment
from appointment.serializers import AppointmentSerializer
from base.utils import generate_pdf_file, send_attachment_email, appointment_booked_by_patient_notification, confirm_payment_notification
from .models import Invoice, InvoiceItems, Payment
from .serializers import InvoiceSerializer, InvoiceItemsSerializer, \
    PaymentSerializer, BillingSerializer, InvoiceAllSerializer
from .utils import get_user_wallet_balance, add_user_wallet_balance, \
    get_user_advance_balance, API_URL, generate_phonepe_payload, \
    generate_x_verify_header, get_headers, MERCHANT_ID, \
    generate_random_string, base64_to_string

from appointment.serializers import AppointmentSerializer
from appointment.models import Procedure

logger = logging.getLogger('fuelapp')


class InvoiceList(generics.ListCreateAPIView):
    queryset = Invoice.objects.all()
    filter_backends = [filters.SearchFilter]
    serializer_class = InvoiceSerializer
    search_fields = ['invoice_number', 'appointment__patient__first_name',
                     'appointment__patient__last_name', 'appointment__patient__email']

    def get_queryset(self):
        queryset = Invoice.objects.all().order_by('-id')
        params = self.request.query_params
        if params and len(params) > 0:
            for param in params:
                if param not in ['page', 'search']:
                    queryset = queryset.filter(**{param: params[param]})

        return queryset


class InvoiceAll(viewsets.ViewSet):
    queryset = Invoice.objects.all()
    filter_backends = [filters.SearchFilter]
    serializer_class = InvoiceAllSerializer
    search_fields = ['invoice_number', 'appointment__patient__first_name',
                     'appointment__patient__last_name',
                     'appointment__patient__email']
    pagination_class = None

    def get_queryset(self):
        queryset = Invoice.objects.all().order_by('-id')
        params = self.request.query_params
        if params and len(params) > 0:
            for param in params:
                if param not in ['page', 'search']:
                    queryset = queryset.filter(**{param: params[param]})

        return queryset

    @action(detail=False, methods=['get'])
    def list(self, request):
        mixed_results = self.get_queryset()
        serializer = InvoiceAllSerializer(mixed_results, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def download_invoice_report(self, request):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="invoice_report.csv"'

        invoices = self.get_queryset()

        writer = csv.writer(response)
        writer.writerow(
            ['Invoice Number', 'Patient First Name', 'Patient Last Name', 'Patient Email', 'Patient Phone Number',
             'Grand Total'])

        for invoice in invoices:
            writer.writerow([invoice.invoice_number, invoice.patient.first_name,
                             invoice.patient.last_name, invoice.patient.email, invoice.patient.phone_number,
                             invoice.grand_total])

        return response


class InvoiceView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer

    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        appointment = instance.appointment
        appointment.payment_status = 'pending'
        appointment.save()
        return self.destroy(request, *args, **kwargs)


class InvoiceItemsList(generics.ListCreateAPIView):
    queryset = InvoiceItems.objects.all()
    serializer_class = InvoiceItemsSerializer

    def get_queryset(self):
        queryset = InvoiceItems.objects.all()
        params = self.request.query_params
        if params and len(params) > 0:
            for param in params:
                if param not in ['page', 'search']:
                    queryset = queryset.filter(**{param: params[param]})
        return queryset


class InvoiceItemsView(generics.RetrieveUpdateDestroyAPIView):
    queryset = InvoiceItems.objects.all()
    serializer_class = InvoiceItemsSerializer


class PaymentList(generics.ListCreateAPIView):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['invoice__appointment__patient__first_name',
                     'invoice__appointment__patient__last_name',
                     'invoice__appointment__patient__email',
                     'invoice__invoice_number']

    def get_queryset(self):
        queryset = Payment.objects.all().order_by('-id')
        params = self.request.query_params
        fields = [field.name for field in Payment._meta.fields]
        if params and len(params) > 0:
            for param in params:
                if param.split('__')[0] in fields:
                    queryset = queryset.filter(**{param: params[param]})
        return queryset

    def perform_create(self, serializer):
        # Set created_by and updated_by fields
        serializer.save(created_by=self.request.user,
                        updated_by=self.request.user)


class PaymentView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer


class CollectPayment(APIView):
    def patch(self, request, pk, format=None):
        with transaction.atomic():
            data = request.data
            items = data.pop('items')
            payments = data.pop('payment')
            userid = self.request.user.id
            grand_total = data.get('grand_total')
            appointment_id = data.get('appointment')
            data.update({'updated_by': userid})
            invoice = Invoice.objects.get(id=pk)
            invoice_serializer = InvoiceSerializer(invoice, data=data)
            prev_items = InvoiceItems.objects.filter(invoice=invoice.id)
            valid_items = []
            if invoice_serializer.is_valid():
                invoice_serializer.save()
                for item in items:
                    item['updated_by'] = userid
                    item_id = item['id']
                    prev_item = InvoiceItems.objects.get(id=item_id)
                    valid_items.append(item_id)
                    inv_items_serializer = InvoiceItemsSerializer(prev_item,
                                                                  data=item,
                                                                  partial=True)
                    if inv_items_serializer.is_valid():
                        inv_items_serializer.save()
                    else:
                        logger.error(f"update_payment pk {item_id} ->"
                                     f" {inv_items_serializer.errors} - "
                                     f"invoice items failed")
                        return Response(inv_items_serializer.errors,
                                        status=status.HTTP_400_BAD_REQUEST)
                # delete items that are not present in the request
                prev_items.exclude(id__in=valid_items).delete()
                payment_sum = 0
                for payment in payments:
                    payment['updated_by'] = userid
                    pay_id = payment['id']
                    pay = Payment.objects.get(id=pay_id)

                    g_total = Invoice.objects.get(id=payment["invoice"]).grand_total
                    new_excess = float(payment["price"]) - g_total

                    if new_excess > payment["balance"]:
                        new_bal = new_excess - payment["balance"]
                        payment["excess_amount"] = new_excess
                        payment["balance"] += new_bal
                    elif new_excess < payment["balance"]:
                        new_bal = payment["balance"] - new_excess
                        payment["excess_amount"] = new_excess
                        payment["balance"] -= new_bal

                    payment_serializer = PaymentSerializer(pay, data=payment, partial=True)
                    if payment_serializer.is_valid():
                        payment_serializer.save()
                        payment_sum += payment_serializer.data['price']
                    else:
                        logger.error(f"update_payment pk {pay_id} ->"
                                     f" {payment_serializer.errors} - "
                                     f"payment failed")        
                if grand_total >= payment_sum:
                    appointment = Appointment.objects.get(id=appointment_id)
                    appointment.payment_status = 'collected'
                    appointment.save()
                return Response(invoice_serializer.data,
                                status=status.HTTP_202_ACCEPTED)
            else:
                logger.error(f"update_payment"
                             f" {invoice_serializer.errors} - "
                             f"invoice failed")
                return Response(invoice_serializer.errors,
                                status=status.HTTP_400_BAD_REQUEST)

    def post(self, request):
        data = request.data
        print(data)
        userid = self.request.user.id
        partial = data.pop('partial', False)
        data.update({'created_by': userid,
                     'updated_by': userid})
        items = data.pop('items')
        payment = {}
        transaction_id = data.pop('payment_transaction_id')
        payment_status = data.pop('payment_status')
        payment_type = data.pop('payment_type')
        payment_mode = data.pop('payment_mode')
        amount = float(data.pop('amount', 0) or 0)
        date = data.get('date')
        notes = data.get('notes')
        wallet_deduct = data.pop('wallet_deduct')
        wallet_balance = float(data.pop('wallet_balance'))
        appid = data['appointment']
        appointment = Appointment.objects.get(id=appid)
        patient = appointment.patient
        clinic = appointment.clinic
        data.update({'patient': patient.id, 'clinic': clinic.id})

        # InvoiceSerializer
        invoice_serializer = InvoiceSerializer(data=data)
        if invoice_serializer.is_valid():
            invoice_serializer.save()
            invoice = invoice_serializer.data
            invoice_id = invoice['id']

            # InvoiceItemsSerializer
            for item in items:
                item['created_by'] = userid
                item['updated_by'] = userid
                item['invoice'] = invoice_id

            inv_items_serializer = InvoiceItemsSerializer(data=items,
                                                          many=True)
            grand_total = float(invoice['grand_total'])
            balance = (amount + wallet_balance) - grand_total if wallet_deduct else amount - grand_total
            if inv_items_serializer.is_valid():
                inv_items_serializer.save()
                if amount > 0:
                    payment.update({
                        'patient': patient.id,
                        'clinic': clinic.id,
                        'transaction_id': transaction_id,
                        'price': amount,
                        'payment_status': payment_status,
                        'invoice': invoice_id,
                        'balance': balance if 0 < balance <= amount else 0,
                        'excess_amount': balance if 0 < balance <= amount else 0,
                        'type': payment_type,
                        'mode': payment_mode,
                        'created_by': userid,
                        'collected_on': date,
                        'pay_notes': notes,
                        'updated_by': userid})
                    # PaymentSerializer
                    payment_serializer = PaymentSerializer(data=payment)
                    if payment_serializer.is_valid():
                        payment_serializer.save()
                        Payment.objects.filter(id=payment_serializer.data.get('id')).update(
                            receipt_id=payment_serializer.data.get('id')
                        )
                    else:
                        logger.error(f"collect_payment"
                                     f" {payment_serializer.errors} - "
                                     f"payment failed")
                        return Response(payment_serializer.errors,
                                        status=status.HTTP_400_BAD_REQUEST)

                    # if balance is there add to wallet

                    # patient_id = appointment.patient.id

                if wallet_deduct:
                    # balance = wallet_balance - balance
                    invoice_balance = grand_total - wallet_balance
                    wallet_amount = wallet_balance if invoice_balance >= 0 else grand_total
                    if wallet_amount:
                        wallet_pay = {
                            'invoice': invoice_id,
                            'clinic': clinic.id,
                            'patient': patient.id,
                            'type': 'wallet',
                            'mode': 'offline',
                            'price': wallet_amount,
                            'transaction_id': 'wallet_payment',
                            'excess_amount': -abs(wallet_amount),
                            'transaction_type': 'wallet_payment',
                            'payment_status': 'success',
                            'collected_on': date,
                            'pay_notes': 'Wallet deducted for payment',
                            'created_by': userid,
                            'updated_by': userid
                        }
                        add_user_wallet_balance(wallet_amount, wallet_pay, patient.id)
                        # wallet_pay_serializer = PaymentSerializer(data=wallet_pay)
                        # if wallet_pay_serializer.is_valid():
                        #     wallet_pay_serializer.save()
                        # else:
                        #     logger.error(f"collect_payment"
                        #                  f" {wallet_pay_serializer.errors} - "
                        #                  f"payment failed")
                        #     return Response(wallet_pay_serializer.errors,
                        #                     status=status.HTTP_400_BAD_REQUEST)

                appointment.payment_status = 'partial_paid' if balance < 0 else 'collected'
                appointment.save()
                Invoice.objects.filter(id=invoice_id).update(is_paid=False if balance < 0 else True)
                return Response(invoice_serializer.data,
                                status=status.HTTP_201_CREATED)
            else:
                logger.error(f"collect_payment"
                             f" {inv_items_serializer.errors} - "
                             f"invoice items failed")
                return Response(inv_items_serializer.errors,
                                status=status.HTTP_400_BAD_REQUEST)
        logger.error(f"collect_payment"
                     f" {invoice_serializer.errors} - "
                     f"invoice failed")
        return Response(invoice_serializer.errors,
                        status=status.HTTP_400_BAD_REQUEST)


class CollectDuePayment(APIView):
    def patch(self, request, pk, format=None):
        return Response(status=status.HTTTP_405_METHOD_NOT_ALLOWED)

    def post(self, request):
        data = request.data
        userid = self.request.user.id
        data.update({'created_by': userid,
                     'updated_by': userid})
        payment = {}
        transaction_id = data.pop('payment_transaction_id')
        payment_status = data.pop('payment_status')
        payment_type = data.pop('payment_type')
        payment_mode = data.pop('payment_mode')
        amount = float(data.pop('amount', 0) or 0)
        invoice_id = data.pop('invoice')
        date = data.get('date')
        notes = data.get('notes')
        wallet_deduct = data.pop('wallet_deduct')
        wallet_balance = data.pop('wallet_balance')

        invoice = Invoice.objects.get(id=invoice_id)
        invoice_serializer = InvoiceSerializer(invoice)
        invoice_data = invoice_serializer.data
        appointment = Appointment.objects.get(id=invoice_data['appointment'])
        patient = appointment.patient
        clinic = appointment.clinic
        due = invoice_data['due_amount']
        balance = amount - due
        # balance = balance if balance > 0 else 0
        if due > 0:
            if amount > 0:
                payment.update({
                    'transaction_id': transaction_id,
                    'price': amount,
                    'payment_status': payment_status,
                    'invoice': invoice_id,
                    'clinic': clinic.id,
                    'collected_on': date,
                    'type': payment_type,
                    'balance': balance if balance > 0 else 0,
                    'excess_amount': balance if balance > 0 else 0,
                    'mode': payment_mode,
                    'pay_notes': notes,
                    'created_by': userid,
                    'updated_by': userid,
                    'patient': patient.id
                })
                payment_serializer = PaymentSerializer(data=payment)
                if payment_serializer.is_valid():
                    payment_serializer.save()
                    Payment.objects.filter(id=payment_serializer.data.get('id')).update(
                        receipt_id=payment_serializer.data.get('id')
                    )

                else:
                    return Response(payment_serializer.errors,
                                    status=status.HTTP_400_BAD_REQUEST)

            if wallet_deduct:
                balance = wallet_balance - balance
                total_deduct = due - wallet_balance
                wallet_amount = wallet_balance if total_deduct >= 0 else due
                if wallet_amount:
                    wallet_pay = {
                        'invoice': invoice_id,
                        'clinic': clinic.id,
                        'patient': patient.id,
                        'type': 'wallet',
                        'mode': 'offline',
                        'price': wallet_amount,
                        'transaction_id': 'wallet_payment',
                        'excess_amount': -abs(wallet_amount),
                        'transaction_type': 'wallet_payment',
                        'payment_status': 'success',
                        'collected_on': date,
                        'pay_notes': 'Wallet deducted for payment',
                        'created_by': userid,
                        'updated_by': userid
                    }

                    # wallet_pay_serializer = PaymentSerializer(data=wallet_pay)
                    # if wallet_pay_serializer.is_valid():
                    #     wallet_pay_serializer.save()
                    # else:
                    #     logger.error(f"collect_payment"
                    #                  f" {wallet_pay_serializer.errors} - "
                    #                  f"payment failed")
                    #     return Response(wallet_pay_serializer.errors,
                    #                     status=status.HTTP_400_BAD_REQUEST)
                    # add_user_wallet_balance(
                    #     wallet_amount,
                    #     patient.id,
                    #     invoice_id,
                    #     userid,
                    #     'deduct balance from wallet for due payment'
                    # )

                    add_user_wallet_balance(wallet_amount, wallet_pay, patient.id)
                # balance = float(amount) - due
                # if balance != 0:
                #     patient_id = invoice_data['patient']
                #     # get user from appoint ment
                #     add_user_wallet_balance(balance, patient_id,
                #                             invoice_id, userid)
            try:
                appointment.payment_status = 'partial_paid' if balance < 0 else 'collected'
                appointment.save()
                Invoice.objects.filter(id=invoice_id).update(is_paid=False if balance < 0 else True)
            except Exception as e:
                logger.error(f"error on update payment status - {e}")
                return Response({'message': 'failed to update appointment status after due payment'},
                                status=status.HTTP_417_EXPECTATION_FAILED)
            return Response(invoice_serializer.data,
                            status=status.HTTP_201_CREATED)

        else:
            return Response({'message': 'No due amount'}, status=204)


# class WalletList(generics.ListCreateAPIView):
#     queryset = Wallet.objects.all()
#     serializer_class = WalletSerializer
#
#     def get_queryset(self):
#         queryset = Wallet.objects.all()
#         params = self.request.query_params
#         if params and len(params) > 0:
#             for param in params:
#                 if param not in ['page', 'search']:
#                     queryset = queryset.filter(**{param: params[param]})
#         return queryset


class WalletBalanceView(APIView):
    def get(self, request, user_id):
        # Get sum of debit and credit for the authenticated user
        final_balance = get_user_wallet_balance(user_id)

        return JsonResponse(
            {'user_id': request.user.id, 'final_balance': final_balance})


class AdvanceBalanceView(APIView):
    def get(self, request, user_id):
        # Get sum of debit and credit for the authenticated user
        exclude_invoice = request.query_params.get('invoice__exclude', None)
        final_balance = get_user_advance_balance(user_id, exclude_invoice)

        return JsonResponse(
            {'user_id': request.user.id, 'final_balance': final_balance})


# class WalletView(generics.RetrieveUpdateDestroyAPIView):
#     queryset = Wallet.objects.all()
#     serializer_class = WalletSerializer


class GenerateInvoicePDFView(APIView):
    def get(self, request, pk):
        invoice = Invoice.objects.get(id=pk)
        context = {}
        invoice_data = InvoiceSerializer(invoice).data
        template_name = 'pdf/invoice.html'
        # Generate the PDF
        appointment = Appointment.objects.get(
            id=invoice_data['appointment']
        )
        appointment_data = AppointmentSerializer(appointment).data
        context.update({
            'invoice': invoice_data,
            'appointment': appointment_data,
        })
        pdf_file = generate_pdf_file(template_name, context)

        # Create an HTTP response with the PDF attachment
        response = HttpResponse(pdf_file, content_type='application/pdf')
        response['Content-Disposition'] = 'filename="invoice.pdf"'

        return response


class SendInvoiceEmailView(APIView):
    def get(self, request, pk):
        invoice = Invoice.objects.get(id=pk)
        invoice_data = InvoiceSerializer(invoice)
        template_name = 'email/invoice.html'
        pdf_template = 'invoice.html'
        to_email = invoice_data.data['patient_email']
        subject = f'Atlas - Invoice #{invoice_data.data["invoice_number"]}'

        # Send the invoice email
        send_attachment_email(template_name, pdf_template, invoice_data.data,
                              to_email,
                              subject)
        return Response(status=status.HTTTP_200_OK)


class BillingView(viewsets.ViewSet):

    def list(self, request):
        mixed_results = self.get_queryset()
        serializer = BillingSerializer(mixed_results, many=True)
        return Response(serializer.data)

    def get_queryset(self):

        invoice_results = Invoice.objects.all()
        invoice_fields = [field.name for field in Invoice._meta.get_fields()]

        payment_results = Payment.objects.all().exclude(
            invoice__isnull=False)
        payment_fields = [field.name for field in Payment._meta.get_fields()]

        params = self.request.query_params
        remove_all = ['page', 'search']
        if params and len(params) > 0:
            for param in params:
                if param in invoice_fields or param.split('__')[0] in invoice_fields and param not in remove_all:
                    invoice_results = invoice_results.filter(**{param: params[param]})

                if param in payment_fields or param.split('__')[0] in payment_fields and param not in remove_all:
                    payment_results = payment_results.filter(**{param: params[param]})

        for payment in payment_results:
            payment.sorting_date = payment.collected_on

        for invoice in invoice_results:
            invoice.sorting_date = invoice.date

        result_list = sorted(chain(payment_results, invoice_results), key=lambda data: data.sorting_date, reverse=True)

        return result_list

# class BillingView(APIView):
#     def get(self, request):
#         # Number of items per page
#         items_per_page = 10
#
#         # Get the mixed results queryset
#         mixed_results = (Invoice.objects.all()
#                          | Payment.objects.exclude(invoice__isnull=False))
#
#         # Apply pagination
#         paginator = PageNumberPagination()
#         paginator.page_size = items_per_page
#         mixed_results_page = paginator.paginate_queryset(mixed_results, request)
#
#         # Serialize the queryset
#         serializer = MixedResultsSerializer(mixed_results_page, many=True)
#
#         return paginator.get_paginated_response(serializer.data)

def process_payment(appointment_transaction_id, amount=500):
    base64_request, finalXHeader = generate_phonepe_payload(appointment_transaction_id, amount)
    payment_url = f"{API_URL}/pay"
    req = {"request": base64_request}
    headers = get_headers(finalXHeader)
    response = requests.post(payment_url, headers=headers, json=req)
    return response

class PaymentStatusView(APIView):
    permission_classes = []

    def post(self, request):
        merchant_id = MERCHANT_ID

        encoded_tx_id = request.data.get('transaction_id')
        if not encoded_tx_id:
            return Response({
                'state': False,
                'data': {
                    'Error': ['transaction_id is required']
                }
            }, status=status.HTTP_400_BAD_REQUEST)
        
        decoded_tx_id = base64_to_string(encoded_tx_id)
        appointment_transaction_id, merchant_transaction_id = decoded_tx_id.split(':')

        input_string = f"/pg/v1/status/{merchant_id}/{merchant_transaction_id}"
        finalXHeader = generate_x_verify_header(input_string)
        status_url = f"{API_URL}/status/{merchant_id}/{merchant_transaction_id}"
        headers = get_headers(finalXHeader)

        appointment_data = cache.get(appointment_transaction_id)
        if appointment_data is None:
            return Response({
                'state': False,
                'data': {
                    'CacheError': ['Data not found inside cache']
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            response = requests.get(status_url, headers=headers)
            response.raise_for_status()
            response_data = response.json()
            code = response_data.get('code')

            if not response_data.get('success'):
                return Response({
                    'state': False,
                    'code': code,
                    'data': {
                        'Error': [response_data["message"]]
                    }
                }, status=response.status_code)

            if code == 'PAYMENT_SUCCESS':
                amount = round(response_data["data"]["amount"] / 100)
                procedure = Procedure.objects.filter(clinic_id=appointment_data['clinic'], name='Advance Amount').first()
                serializer = AppointmentSerializer(data=appointment_data, context={'request': request})

                with transaction.atomic():
                    if serializer.is_valid():
                        appointment = serializer.save()

                    invoice = Invoice.objects.create(
                        appointment=appointment,
                        invoice_number=appointment.id,
                        created_by_id=appointment_data['created_by'],
                        updated_by_id=appointment_data['updated_by'],
                        patient_id=appointment_data['patient'],
                        is_paid=True,
                        grand_total=amount,
                        clinic_id=appointment_data['clinic']
                    )

                    InvoiceItems.objects.create(
                        invoice=invoice,
                        procedure=procedure,
                        quantity=1,
                        price=amount,
                        total=amount,
                        discount=0.0,
                        total_after_discount=amount,
                        status=True,
                        created_by_id=appointment_data['created_by'],
                        updated_by_id=appointment_data['updated_by'],
                    )

                    payment = Payment.objects.create(
                        patient_id=appointment_data['patient'],
                        price=amount,
                        balance=amount,
                        excess_amount=amount,
                        created_by_id=appointment_data['created_by'],
                        updated_by_id=appointment_data['updated_by'],
                        status=True,
                        type="cash",
                        transaction_id=generate_random_string(),
                        mode="online",
                        clinic_id=appointment_data['clinic'],
                        payment_status="success",
                        invoice=invoice,
                        transaction_type="collected",
                        collected_on=timezone.now().strftime('%Y-%m-%d')
                    )
                    payment.receipt_id = payment.id
                    payment.save()

                    confirm_payment_notification(appointment_data)
                    appointment_booked_by_patient_notification(appointment_data)
                    
                    cache.delete(appointment_transaction_id)
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            logger.error(traceback.format_exc())
            return Response({
                'state': False,
                'data': {
                    'Error': [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response({
            'state': True,
            'message': 'Appointment created successfully',
        }, status=status.HTTP_201_CREATED)   