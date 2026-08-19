from django.urls import path

from . import views

urlpatterns = [
    path("", views.panel, name="panel"),
    path("corridas/nueva/", views.run_new, name="nueva"),
    path("corridas/<str:session_id>/", views.session_detail, name="sesion"),
    path("corridas/<str:session_id>/reanudar/", views.session_resume, name="reanudar"),
    path("clientes/<str:client_id>/bloques/<str:block>/", views.block_review, name="bloque"),
    path("clientes/<str:client_id>/bloques/<str:block>/decidir/", views.block_decide,
         name="decidir"),
]
