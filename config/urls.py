from django.contrib import admin
from django.urls import path
from exchange import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.index, name='index'),
    path('submit/', views.submit_page, name='submit'),
    path('secrets/', views.secret_list, name='secret_list'),
    path('weight/<int:pk>/', views.weight_detail, name='weight_detail'),
    path('submit/success/', views.submit_success, name='submit_success'),
]