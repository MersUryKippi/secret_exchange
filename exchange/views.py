from django.shortcuts import render
from .models import SecretWeight, Secret

def index(request):
    return render(request, 'index.html')

def submit_page(request):
    return render(request, 'submit.html')

def secret_list(request):
    weights = SecretWeight.objects.all().order_by('weight')
    return render(request, 'secret_list.html', {'weights': weights})

def weight_detail(request, pk):
    weight = SecretWeight.objects.get(id=pk)
    count = Secret.objects.filter(weight=weight).count()
    return render(request, 'weight_detail.html', {'weight': weight, 'count': count})