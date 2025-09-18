from import_export import resources, fields
from import_export.widgets import BooleanWidget
from django.contrib.auth import get_user_model

User = get_user_model()

class StudentResource(resources.ModelResource):
    # Optional explicit columns (nice for docs/validation)
    username = fields.Field(attribute="username", column_name="username")
    email    = fields.Field(attribute="email", column_name="email")
    first_name = fields.Field(attribute="first_name", column_name="first_name")
    last_name  = fields.Field(attribute="last_name", column_name="last_name")
    employee_code = fields.Field(attribute="employee_code", column_name="student_code")
    phone    = fields.Field(attribute="phone", column_name="phone")
    is_active = fields.Field(attribute="is_active", column_name="is_active", widget=BooleanWidget())

    class Meta:
        model = User
        import_id_fields = ("username",)   # treat username as unique key
        fields = ("username","email","first_name","last_name","employee_code","phone","is_active")
        skip_unchanged = True
        report_skipped = True

    def before_import_row(self, row, **kwargs):
        # enforce student role regardless of CSV value
        row["role"] = "student"
        # default is_active when not provided
        if "is_active" not in row or row["is_active"] in ("", None):
            row["is_active"] = True

    def after_import_row(self, row, row_result, **kwargs):
        # If CSV contains a 'password' column, hash it properly
        # Otherwise set a default and force change later as you like
        password = row.get("password") or "Student@123"  # default for testing
        username = row["username"]
        try:
            u = User.objects.get(username=username)
            if password:
                u.set_password(password)
                u.role = "student"
                u.is_active = bool(row.get("is_active", True))
                u.save()
        except User.DoesNotExist:
            # If row created a new user, set password post-create
            pass
