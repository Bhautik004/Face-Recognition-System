from django import forms

class CaptureImageWidget(forms.ClearableFileInput):
    template_name = "widgets/capture_file.html"

    class Media:
        # No external libs required; native getUserMedia
        js = ()
        css = {"all": ()}
