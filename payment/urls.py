from django.urls import path, include

from .views import PaymentList, PaymentView, \
    CollectPayment, InvoiceList, InvoiceView, InvoiceItemsList, \
    InvoiceItemsView, CollectDuePayment, \
    SendInvoiceEmailView, GenerateInvoicePDFView, WalletBalanceView, \
    BillingView, AdvanceBalanceView, InvoiceAll, \
    PaymentStatusView

# , WalletList, WalletView,

collectpayment = [
    path('', CollectPayment.as_view(), name="collect_payment"),
    path('<int:pk>/', CollectPayment.as_view(), name="update_payment"),
    path('due/', CollectDuePayment.as_view(), name="collect_due_payment"),
    path('due/<int:pk>/', CollectDuePayment.as_view(),
         name="update_due_payment"),
]

invoice = [
    path('', InvoiceList.as_view(), name='invoiceList'),
    # path('all/', InvoiceAll.as_view(), name='invoiceAll'),
    # path('download-invoice-report/',
    #      InvoiceAll.as_view({'get': 'download_invoice_report'}),
    #      name='download_invoice_report'),

    path('all/', InvoiceAll.as_view({'get': 'list'}), name='invoiceAll'),
    # Assuming 'list' is the method to list all invoices
    path('download-invoice-report/', InvoiceAll.as_view({'get': 'download_invoice_report'}),
         name='download_invoice_report'),

    path('<int:pk>/', include([
        path('', InvoiceView.as_view(), name='invoiceView'),
        path('sendmail/', SendInvoiceEmailView.as_view(),
             name='send_invoice_email'),
        path('download/', GenerateInvoicePDFView.as_view(),
             name='generate_invoice_pdf'),
    ])),
    path('items/', InvoiceItemsList.as_view(),
         name='invoice_items_list'),
    path('items/<int:pk>/', InvoiceItemsView.as_view(),
         name='invoiceitemsView')

]

wallet = [
    # path('', WalletList.as_view(), name='walletList'),
    # path('<int:pk>/', WalletView.as_view(), name='walletView'),
    path('balance/<int:user_id>/', WalletBalanceView.as_view(),
         name='wallet_balance'),
    path('advance/<int:user_id>/', AdvanceBalanceView.as_view(),
         name='advance_balance'),
]

payment = [
    path('', PaymentList.as_view(), name='paymentList'),
    path('<int:pk>/', PaymentView.as_view(), name='paymentView'),
]

payment_urls = [
    path('invoice/', include(invoice)),
    path('payment/', include(payment)),
    path('wallet/', include(wallet)),
    path('collectpayment/', include(collectpayment)),
    path('billing/', BillingView.as_view({'get': 'list'}), name='billing'),
    path('payment/status/', PaymentStatusView.as_view(), name='payment-status')
]
