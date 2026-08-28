from django.urls import path

from . import views

urlpatterns = [
    path("", views.panel, name="panel"),
    path("corridas/nueva/", views.run_new, name="nueva"),
    path("corridas/<str:session_id>/", views.session_detail, name="sesion"),
    path("corridas/<str:session_id>/reanudar/", views.session_resume, name="reanudar"),
    path("corridas/<str:session_id>/reiniciar-desde/<str:block>/", views.session_restart_from,
         name="reiniciar_desde"),
    path("clientes/<str:client_id>/bloques/<str:block>/", views.block_review, name="bloque"),
    path("clientes/<str:client_id>/bloques/<str:block>/decidir/", views.block_decide,
         name="decidir"),
    path("clientes/<str:client_id>/bloques/<str:block>/editar/", views.block_edit,
         name="editar_bloque"),
    path("propuestas/<str:client_id>/generar/", views.proposal_generate, name="propuesta_generar"),
    path("propuestas/<str:client_id>/<str:doc_type>/", views.proposal_view, name="propuesta_ver"),
    path("propuestas/<str:client_id>/<str:doc_type>/descargar/", views.proposal_download,
         name="propuesta_descargar"),
    path("mantenimiento/limpiar-pruebas/", views.clean_test_data, name="limpiar_pruebas"),
]
