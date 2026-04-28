from django.contrib import admin
from django.urls import path
from exchange import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.index, name='index'),
    path('submit/', views.submit_page, name='submit'),
    path('submit/success/', views.submit_success, name='submit_success'),
    path('secrets/', views.secret_list, name='secret_list'),
    path('weight/<int:pk>/', views.weight_detail, name='weight_detail'),
    path('my/', views.my_secrets, name='my_secrets'),
    path('secret/<int:pk>/delete/', views.delete_secret, name='delete_secret'),
    path('exchange/', views.do_exchange, name='do_exchange'),
    path('exchange/burn/<int:exchange_id>/', views.burn_secret, name='burn_secret'),
]