from datetime import datetime, timedelta

from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _

from social_auth.signals import pre_update
from auth import InstagramBackend
from utils import expire_view_cache

LICENSES = (
    ('CC0', 'Creative Commons Public Domain'),
    ('CC-BY', 'Creative Commons Attribution'),
    ('CC-BY-SA', 'Creative Commons Attribution-ShareAlike'),
    ('CC-BY-NC', 'Creative Commons Attribution-NonCommercial'),
    ('CC-BY-ND', 'Creative Commons Attribution-NoDerivs'),
    ('CC-BY-NC-SA', 'Creative Commons Attribution-NonCommercial-ShareAlike'),
    ('CC-BY-NC-ND', 'Creative Commons Attribution-NonCommercial-NoDerivs'),
)

LICENSE_URL_MAP = {
    'CC0': 'http://creativecommons.org/publicdomain/zero/1.0/',
    'CC-BY': 'http://creativecommons.org/licenses/by/3.0/',
    'CC-BY-SA': 'http://creativecommons.org/licenses/by-sa/3.0/',
    'CC-BY-NC': 'http://creativecommons.org/licenses/by-nc/3.0/',
    'CC-BY-ND': 'http://creativecommons.org/licenses/by-nd/3.0/',
    'CC-BY-NC-SA': 'http://creativecommons.org/licenses/by-nc-sa/3.0/',
    'CC-BY-NC-ND': 'http://creativecommons.org/licenses/by-nc-nd/3.0/',
}


class InstagramInfo(models.Model):
    user = models.ForeignKey(User)

    instagram_username = models.CharField(
        _("Instagram account"), null=True, blank=True, max_length=250)
    instagram_id = models.IntegerField()
    full_name = models.CharField(null=True, max_length=250)
    avatar_url = models.URLField(null=True)
    website = models.URLField(null=True)

    license = models.CharField(choices=LICENSES, max_length=25,
        default='CC-BY', blank=False)
    start_date = models.DateTimeField(null=True)
    end_date = models.DateTimeField(null=True)

    last_used_in_api = models.DateTimeField(null=True)

    def license_full_name(self):
        for abbrv, full in LICENSES:
            if self.license == abbrv:
                return full

    def license_url(self):
        return LICENSE_URL_MAP[self.license]


def invalidate_index(sender, instance, created, **kws):
    if created:
        expire_view_cache("index")


post_save.connect(invalidate_index, sender=InstagramInfo)


class InstagramPhoto(models.Model):
    """
    A CC-licensed instagram photo that's associated with an InstagramInfo
    record.

    Mirrors the JSON response from Instagram.
    """
    license_info = models.ForeignKey(InstagramInfo)

    caption = models.TextField(null=True, blank=True)
    created_time = models.DateTimeField(null=True, blank=True)
    filter = models.CharField(max_length=250, null=True, blank=True)
    photo_id = models.CharField(max_length=250, null=True, blank=True)
    image_low_resolution = models.URLField(null=True, blank=True)
    image_standard_resolution = models.URLField(null=True, blank=True)
    image_thumbnail = models.URLField(null=True, blank=True)
    link = models.URLField(null=True, blank=True)
    # XXX TODO make this a M2M field
    tags = models.TextField(null=True, blank=True)
    # XXX TODO make this GeoDjango aware
    location = models.TextField(null=True, blank=True)

    def get_absolute_url(self):
        return reverse('instagram-photo', kwargs={
            'username': self.license_info.instagram_username,
            'photo_id': self.id
        })


def instagram_user_init(sender, user, response, details, **kwargs):
    if InstagramInfo.objects.filter(user=user, end_date__gte=datetime.now()):
        info = InstagramInfo.objects.filter(user=user).order_by('-end_date')[0]
    # Partially-filled-out form from before
    elif InstagramInfo.objects.filter(user=user, start_date=None):
        info = InstagramInfo.objects.filter(user=user, start_date=None)[0]
    else:
        # Create a new instance because their previous one expired
        info = InstagramInfo(user=user)
    info.instagram_username = details['username']
    info.instagram_id = details['user_id']
    info.website = details.get('website', None)
    info.avatar_url = details['avatar_url']
    # Full name stored as first_name by InstagramBackend
    info.full_name = details['first_name'].strip() or details['username']
    info.save()
    return True

pre_update.connect(instagram_user_init, sender=InstagramBackend)
