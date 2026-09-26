from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.generic import FormView, View
from django.urls import reverse_lazy

class LoginView(FormView):
    template_name = "accounts/login.html"
    form_class = AuthenticationForm
    success_url = reverse_lazy("dashboard")

    def form_valid(self, form):
        user = form.get_user()
        login(self.request, user)
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["hide_nav"] = True
        return ctx

class LogoutView(View):
    def post(self, request):
        logout(request)
        return redirect("login")
    def get(self, request):
        logout(request)
        return redirect("login")
