from django.urls import path, include
from knox import views as knox_views

from .views import RegistrationAPI, LoginAPI, ForgetPasswordAPI, UserAPI, \
    UserList, UserView, AddressView, AddressList, DoctorTimingView, \
    DoctorTimingList, LeavesView, LeavesList, ResendCode, \
    Verify, TestEmail, DoctorList, StaffList, DoctorView, StaffView, LeavesListView, \
    PatientHandleAPI, PatientVerifyOtpAPI, PatientLoginAPI

doctor = [
    path('', DoctorList.as_view(), name='Doctor'),
    path('<int:pk>/', DoctorView.as_view(), name='Doctor'),
    path('timing/', DoctorTimingList.as_view(), name='DoctorTimingList'),
    path('timing/<int:pk>/', DoctorTimingView.as_view(),
         name='DoctorTimingview'),
]

staff = [
    path('', StaffList.as_view(), name='StaffList'),
    path('<int:pk>/', StaffView.as_view(), name='StaffView'),
]

user_urls = [
    # 'knox.urls
    path('register/', RegistrationAPI.as_view()),
    path('login/', LoginAPI.as_view()),
    path('forget-password/', ForgetPasswordAPI.as_view()),
    path('resend-code/', ResendCode.as_view(),
         name='resend-code'),
    path('me/', UserAPI.as_view()),
    path('logout/', knox_views.LogoutView.as_view(), name='knox_logout'),
    path('verify-email/', Verify.as_view(),
         name='verify-email'),
    path('password_reset/',
         include('django_rest_passwordreset.urls', namespace='password_reset')),
    path('users/', UserList.as_view(), name='UserList'),
    path('user/<int:pk>/', UserView.as_view(), name='UsersView'),
    path('address/', AddressList.as_view(), name='AddressList'),
    path('address/<int:pk>/', AddressView.as_view(), name='AddressView'),
    path('doctor/', include(doctor)),
    path('staff/', include(staff)),
    path('test/email', TestEmail.as_view(), name='test_email'),
    path('patient/', PatientHandleAPI.as_view(), name='patient-handle'),
    path('patient/verify-otp/', PatientVerifyOtpAPI.as_view(), name='patient-verify-otp'),
    path('patient/login/', PatientLoginAPI.as_view(), name='patient-login'),
    path('block-calendar/create/', LeavesList.as_view(), name='DoctorLeaveList'),
    path('block-calendar/<int:pk>/', LeavesView.as_view(),
         name='DoctorLeaveview'),
    path('block-calendar/', LeavesListView.as_view(),
         name='DoctorLeaveview'),
]