from django import template
register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key, '')

@register.filter
def contains(value_set, item):
    return item in value_set
