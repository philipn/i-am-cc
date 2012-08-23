from django.conf.urls import patterns, include, url
from django.views.generic.simple import direct_to_template
from django.views.decorators.cache import never_cache

from tastypie.api import Api

from profiles.views import (InstagramLicenseUpdate, index, instagram_list,
    photo_page)
from profiles.resources import InstagramResource, InstagramPhotoResource

api = Api(api_name='api')
api.register(InstagramResource())
api.register(InstagramPhotoResource())

urlpatterns = patterns('',
    url(r'^$', index, name="index"),
    url(r'^setup/', never_cache(InstagramLicenseUpdate.as_view()),
        name="instagram-setup"),
    url(r'^instagram/(?P<username>.*)/(?P<photo_id>.*)',
        photo_page, name="instagram-photo"),
    url(r'^instagram/(?P<username>.*)', instagram_list, name="instagram-list"),
    url(r'^instagram-done/', direct_to_template,
        {'template': 'profiles/done.html'}),
    url(r'^instagram-stopped/', direct_to_template,
        {'template': 'profiles/stopped.html'}),
    url(r'^about-api/', direct_to_template,
        {'template': 'about_api.html'}, name='about-api'),
    url(r'^manifesto/', direct_to_template,
        {'template': 'manifesto.html'}),
    url(r'^', include(api.urls)),
    url(r'', include('auth.urls')),
)

