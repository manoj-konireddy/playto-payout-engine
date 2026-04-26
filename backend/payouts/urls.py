from django.urls import path

from .views import MerchantDashboardView, PayoutListCreateView

urlpatterns = [
    path('merchant/dashboard', MerchantDashboardView.as_view(), name='merchant-dashboard'),
    path('payouts', PayoutListCreateView.as_view(), name='payouts-list-create'),
]
