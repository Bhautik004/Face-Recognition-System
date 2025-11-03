from django import template
register = template.Library()

@register.filter
def equal(a, b):
    return a == b
