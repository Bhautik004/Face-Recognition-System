from django.apps import apps as django_apps
Session     = django_apps.get_model("academics","Session")
Enrollment  = django_apps.get_model("academics","Enrollment")
UET         = django_apps.get_model("biometrics","UserEmbeddingTemplate")

sid = 46  # e.g. 42
sess = Session.objects.select_related("course_assignment").get(id=sid)

# enrolled student user_ids for this session:
user_ids = list(Enrollment.objects
    .filter(course_assignment=sess.course_assignment)
    .values_list("student__user_id", flat=True))
print("enrolled user_ids:", user_ids)

print("centroids available:", UET.objects.filter(user_id__in=user_ids).count())
missing = set(user_ids) - set(UET.objects.filter(user_id__in=user_ids).values_list("user_id", flat=True))
print("missing embeddings for user_ids:", missing)
